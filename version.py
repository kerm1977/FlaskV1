# version.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db # IMPORTANTE: Importa la instancia de 'db' desde models.py
from datetime import datetime
from functools import wraps # Necesario para el decorador role_required

# DECORADOR PARA ROLES (Ahora definido dentro de version.py)
def role_required(roles):
    """
    Decorador para restringir el acceso a rutas basadas en roles.
    `roles` puede ser una cadena (un solo rol) o una lista de cadenas (múltiples roles).
    """
    if not isinstance(roles, list):
        roles = [roles]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session or not session['logged_in']:
                flash('Por favor, inicia sesión para acceder a esta página.', 'info')
                return redirect(url_for('login'))
            
            user_role = session.get('role')
            if user_role not in roles:
                flash('No tienes permiso para acceder a esta página.', 'danger')
                return redirect(url_for('home')) # O a una página de "Acceso Denegado"
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Definición del modelo Version AHORA EN version.py
class Version(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=True) # Ahora nullable=True
    parrafo = db.Column(db.Text, nullable=True) # Contenido del párrafo
    nombre_version = db.Column(db.String(100), nullable=False)
    numero_version = db.Column(db.String(50), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True) # CKEditor content
    pendiente = db.Column(db.Text, nullable=True) # CKEditor content
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    provincia = db.Column(db.String(100), nullable=True) # Nuevo campo para provincia

    def __repr__(self):
        return f'<Version {self.nombre_version} - {self.numero_version}>'

version_bp = Blueprint('version', __name__)

@version_bp.route('/ver_versiones')
def ver_versiones():
    """
    Muestra una lista de todas las versiones registradas.
    """
    versiones = Version.query.order_by(Version.fecha_creacion.desc()).all()
    return render_template('ver_versiones.html', versiones=versiones)

@version_bp.route('/crear_version', methods=['GET', 'POST'])
@role_required('Superuser') # Solo Superusers pueden crear versiones
def crear_version():
    """
    Permite a un Superuser crear una nueva versión de la aplicación.
    """
    provincia_opciones = ["San José", "Alajuela", "Cartago", "Heredia", "Guanacaste", "Puntarenas", "Limón"]

    if request.method == 'POST':
        titulo = request.form.get('titulo') # Usar .get() para campos opcionales
        parrafo = request.form.get('parrafo')
        nombre_version = request.form['nombre_version']
        numero_version = request.form['numero_version']
        descripcion = request.form.get('descripcion')
        pendiente = request.form.get('pendiente')
        provincia = request.form.get('provincia')

        # Validar solo los campos obligatorios: nombre_version y numero_version
        if not all([nombre_version, numero_version]):
            flash('Por favor, completa los campos obligatorios: Nombre de la Versión y Número de la Versión.', 'danger')
            return render_template('crear_version.html', provincia_opciones=provincia_opciones)

        # Verificar si el número de versión ya existe para asegurar unicidad
        existing_version = Version.query.filter_by(numero_version=numero_version).first()
        if existing_version:
            flash('Ese número de versión ya existe. Por favor, elige otro.', 'danger')
            return render_template('crear_version.html', provincia_opciones=provincia_opciones)

        nueva_version = Version(
            titulo=titulo,
            parrafo=parrafo,
            nombre_version=nombre_version,
            numero_version=numero_version,
            descripcion=descripcion,
            pendiente=pendiente,
            fecha_creacion=datetime.utcnow(),
            fecha_modificacion=datetime.utcnow(),
            provincia=provincia if provincia != "Seleccionar Provincia" else None
        )
        try:
            db.session.add(nueva_version)
            db.session.commit()
            flash('Versión creada exitosamente.', 'success')
            return redirect(url_for('version.ver_versiones'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la versión: {e}', 'danger')

    return render_template('crear_version.html', provincia_opciones=provincia_opciones)

@version_bp.route('/editar_version/<int:version_id>', methods=['GET', 'POST'])
@role_required('Superuser') # Solo Superusers pueden editar versiones
def editar_version(version_id):
    """
    Permite a un Superuser editar una versión existente.
    """
    version = Version.query.get_or_404(version_id)
    provincia_opciones = ["San José", "Alajuela", "Cartago", "Heredia", "Guanacaste", "Puntarenas", "Limón"]

    if request.method == 'POST':
        version.titulo = request.form.get('titulo') # Usar .get() para campos opcionales
        version.parrafo = request.form.get('parrafo')
        version.nombre_version = request.form['nombre_version']
        
        nuevo_numero_version = request.form['numero_version']
        # Validar solo los campos obligatorios: nombre_version y numero_version
        if not all([version.nombre_version, nuevo_numero_version]):
            flash('Por favor, completa los campos obligatorios: Nombre de la Versión y Número de la Versión.', 'danger')
            return render_template('editar_version.html', version=version, provincia_opciones=provincia_opciones)

        # Verificar si el nuevo número de versión ya existe y no es el de la versión actual
        if nuevo_numero_version != version.numero_version:
            existing_version = Version.query.filter_by(numero_version=nuevo_numero_version).first()
            if existing_version:
                flash('Ese número de versión ya existe. Por favor, elige otro.', 'danger')
                return render_template('editar_version.html', version=version, provincia_opciones=provincia_opciones)
        version.numero_version = nuevo_numero_version
        
        version.descripcion = request.form.get('descripcion')
        version.pendiente = request.form.get('pendiente')
        version.provincia = request.form.get('provincia') if request.form.get('provincia') != "Seleccionar Provincia" else None
        version.fecha_modificacion = datetime.utcnow() # Actualizar fecha de modificación

        try:
            db.session.commit()
            flash('Versión actualizada exitosamente.', 'success')
            return redirect(url_for('version.detalle_version', version_id=version.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la versión: {e}', 'danger')

    return render_template('editar_version.html', version=version, provincia_opciones=provincia_opciones)

@version_bp.route('/detalle_version/<int:version_id>')
def detalle_version(version_id):
    """
    Muestra todos los detalles de una versión específica.
    """
    version = Version.query.get_or_404(version_id)
    return render_template('detalle_version.html', version=version)

@version_bp.route('/eliminar_version/<int:version_id>', methods=['POST'])
@role_required('Superuser') # Solo Superusers pueden eliminar versiones
def eliminar_version(version_id):
    """
    Permite a un Superuser eliminar una versión.
    """
    version = Version.query.get_or_404(version_id)
    try:
        db.session.delete(version)
        db.session.commit()
        flash('Versión eliminada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la versión: {e}', 'danger')
    return redirect(url_for('version.ver_versiones'))
