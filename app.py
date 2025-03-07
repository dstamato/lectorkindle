from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text  # Importar text() para ejecutar SQL directo
import os
import re

app = Flask(__name__)

# Configuración de SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db?check_same_thread=False"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Definir modelos en la base de datos
class Libro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), unique=True, nullable=False)
    autor = db.Column(db.String(255), nullable=False)
    subrayados = db.relationship("Subrayado", backref="libro", lazy=True)

class Subrayado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    libro_id = db.Column(db.Integer, db.ForeignKey("libro.id"), nullable=False)

# Crear la base de datos y activar WAL
with app.app_context():
    db.create_all()
    db.session.execute(text("PRAGMA journal_mode=WAL;"))
    db.session.commit()

def extraer_autor(titulo):
    """Extrae el autor del libro si está entre paréntesis en el título."""
    match = re.search(r"\((.*?)\)", titulo)
    if match:
        return match.group(1).strip()
    return "Autor desconocido"

@app.route("/")
def index():
    """Carga y muestra la lista de libros almacenados en la base de datos."""
    libros = db.session.query(
        Libro.id, 
        Libro.titulo, 
        Libro.autor, 
        db.func.count(Subrayado.id).label("cantidad_subrayados")
    ).outerjoin(Subrayado).group_by(Libro.id).order_by(db.desc("cantidad_subrayados")).all()

    total_libros = len(libros)
    
    # Convertimos los resultados en un formato que Jinja pueda leer bien
    libros_info = [{"id": libro.id, "titulo": libro.titulo, "autor": libro.autor, "subrayados": libro.cantidad_subrayados} for libro in libros]

    return render_template("index.html", libros=libros_info, total_libros=total_libros)

@app.route("/libro/<int:libro_id>")
def ver_libro(libro_id):
    """Muestra los subrayados de un libro específico."""
    libro = Libro.query.get_or_404(libro_id)  # 🔥 Obtiene el libro específico
    subrayados = Subrayado.query.filter_by(libro_id=libro.id).all()  # 🔥 Obtiene los subrayados

    return render_template("libro.html", libro=libro, subrayados=subrayados)

@app.route("/subir", methods=["POST"])
def subir_archivo():
    """Procesa el archivo subido y almacena los datos en SQLite."""
    if "archivo" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400

    archivo = request.files["archivo"]
    if archivo.filename == "":
        return jsonify({"error": "El archivo está vacío"}), 400

    contenido = archivo.read().decode("utf-8")
    entries = contenido.split("==========")

    for entry in entries:
        lineas = entry.strip().split("\n")
        if len(lineas) >= 3:
            titulo = lineas[0].strip()
            autor = extraer_autor(titulo)
            texto = "\n".join(lineas[3:]).strip()

            # Verifica si el libro ya existe, si no, agrégalo
            libro = Libro.query.filter_by(titulo=titulo).first()
            if not libro:
                libro = Libro(titulo=titulo, autor=autor)
                db.session.add(libro)
                db.session.commit()

            # Guardar subrayado
            subrayado = Subrayado(texto=texto, libro_id=libro.id)
            db.session.add(subrayado)

    db.session.commit()
    db.session.remove()

    return jsonify({"mensaje": "Archivo subido y procesado exitosamente"}), 200

if __name__ == "__main__":
    app.run(debug=True)
