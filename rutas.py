# rutas.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, make_response
from models import db, Ruta # Importa db y el nuevo modelo Ruta
from functools import wraps # Importar wraps para el decorador role_required
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as pdf_canvas # Renombrado para evitar conflicto con Flask canvas
import re # NUEVO: Importar re para expresiones regulares

# Crea un Blueprint para el módulo de rutas
rutas_bp = Blueprint('rutas', __name__, template_folder='templates')

# Lista de provincias de Costa Rica
PROVINCIAS = ["Alajuela", "Cartago", "Heredia", "Puntarenas", "Limón", "Guanacaste", "San José"]

# DECORADOR PARA ROLES (MOVIDO AQUÍ DESDE app.py)
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
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_embed_url(video_url):
    """
    Función para obtener la URL de incrustación de videos de YouTube o Facebook.
    Esto permite que los videos se muestren correctamente en la vista de detalle.
    """
    if not video_url:
        return None

    # Intentar con YouTube
    youtube_match = re.search(r'(?:https?:\/\/)?(?:www\.)?(?:m\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|)([a-zA-Z0-9_-]{11})(?:\S+)?', video_url)
    if youtube_match:
        video_id = youtube_match.group(1)
        # CORRECCIÓN: Usa la URL de incrustación estándar de YouTube
        return f"https://www.youtube.com/embed/{video_id}"

    # Intentar con Facebook
    # Expresión regular para capturar el ID de video de Facebook desde "watch/?v="
    facebook_watch_match = re.search(r'(?:https?:\/\/)?(?:www\.)?(?:facebook\.com)\/watch\/\?v=(\d+)', video_url)
    if facebook_watch_match:
        # Para Facebook, el plugin de video usa la URL original como el parámetro 'href'
        return f"https://www.facebook.com/plugins/video.php?href={video_url}&show_text=0&width=1280"
    
    # Si no se reconoce ninguna plataforma de video conocida, devuelve None
    return None

@rutas_bp.route('/rutas')
# @role_required(['Superuser', 'Usuario Regular'])
def ver_rutas():
    # Obtener el parámetro 'provincia' de la URL si existe
    provincia_seleccionada = request.args.get('provincia')

    if provincia_seleccionada and provincia_seleccionada != 'Todas':
        rutas = Ruta.query.filter_by(provincia=provincia_seleccionada).order_by(Ruta.nombre).all()
    else:
        rutas = Ruta.query.order_by(Ruta.provincia, Ruta.nombre).all()
        provincia_seleccionada = 'Todas' # Asegura que el dropdown muestre 'Todas' si no hay filtro o es inválido
    
    rutas_por_provincia = {}
    for ruta in rutas:
        if ruta.provincia not in rutas_por_provincia:
            rutas_por_provincia[ruta.provincia] = []
        rutas_por_provincia[ruta.provincia].append(ruta)
            
    return render_template('ver_rutas.html', 
                           rutas_por_provincia=rutas_por_provincia, 
                           provincias=PROVINCIAS, # Pasa la lista completa de provincias
                           provincia_seleccionada=provincia_seleccionada) # Pasa la provincia seleccionada para el dropdown

@rutas_bp.route('/rutas/crear', methods=['GET', 'POST'])
@role_required('Superuser')
def crear_ruta():
    if request.method == 'POST':
        nombre = request.form['nombre']
        provincia = request.form['provincia']
        detalle = request.form['detalle']
        enlace_video = request.form.get('enlace_video')

        if not nombre or not provincia:
            flash('El nombre y la provincia son campos obligatorios.', 'danger')
            return render_template('crear_rutas.html', provincias=PROVINCIAS)

        nueva_ruta = Ruta(
            nombre=nombre,
            provincia=provincia,
            detalle=detalle,
            enlace_video=enlace_video
        )
        db.session.add(nueva_ruta)
        db.session.commit()
        flash('Ruta creada exitosamente.', 'success')
        return redirect(url_for('rutas.ver_rutas'))
    
    return render_template('crear_rutas.html', provincias=PROVINCIAS)

@rutas_bp.route('/rutas/editar/<int:ruta_id>', methods=['GET', 'POST'])
@role_required('Superuser')
def editar_ruta(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))

    if request.method == 'POST':
        ruta.nombre = request.form['nombre']
        ruta.provincia = request.form['provincia']
        ruta.detalle = request.form['detalle']
        ruta.enlace_video = request.form.get('enlace_video')
        
        db.session.commit()
        flash('Ruta actualizada exitosamente.', 'success')
        return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta.id))
    
    return render_template('editar_rutas.html', ruta=ruta, provincias=PROVINCIAS)

@rutas_bp.route('/rutas/<int:ruta_id>')
# @role_required(['Superuser', 'Usuario Regular'])
def detalle_ruta(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))
        
    embed_url = get_embed_url(ruta.enlace_video) if ruta.enlace_video else None
    # Si estás usando Flask-WTF o similar para CSRF, asegúrate de pasar el token aquí
    # Por ejemplo, si usas Flask-WTF, podrías tener form.csrf_token en tu contexto
    # Para este ejemplo, asumimos que csrf_token es una variable global o que Flask-WTF
    # lo inyecta automáticamente. Si no, necesitarás un Formulario Flask-WTF para generarlo.
    return render_template('detalle_rutas.html', ruta=ruta, embed_url=embed_url)

@rutas_bp.route('/rutas/eliminar/<int:ruta_id>', methods=['POST'])
@role_required('Superuser')
def eliminar_ruta(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))

    try:
        db.session.delete(ruta)
        db.session.commit()
        flash('Ruta eliminada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback() # Deshacer cualquier cambio si hay un error
        flash(f'Error al eliminar la ruta: {e}', 'danger')
        current_app.logger.error(f"Error al eliminar ruta {ruta_id}: {e}") # Registrar el error
    
    return redirect(url_for('rutas.ver_rutas'))

@rutas_bp.route('/rutas/exportar/txt/<int:ruta_id>')
@role_required(['Superuser', 'Usuario Regular'])
def exportar_ruta_txt(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada para exportar.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))

    # Manejo de AttributeError para fecha_creacion y fecha_modificacion
    fecha_creacion_str = ruta.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S') if hasattr(ruta, 'fecha_creacion') and ruta.fecha_creacion else 'N/A'
    fecha_modificacion_str = ruta.fecha_modificacion.strftime('%Y-%m-%d %H:%M:%S') if hasattr(ruta, 'fecha_modificacion') and ruta.fecha_modificacion else 'N/A'

    content = f"Nombre de la Ruta: {ruta.nombre}\n" \
              f"Provincia: {ruta.provincia}\n" \
              f"Detalle: {ruta.detalle}\n" \
              f"Enlace de Video: {ruta.enlace_video if ruta.enlace_video else 'N/A'}\n" \
              f"Fecha de Creación: {fecha_creacion_str}\n" \
              f"Última Modificación: {fecha_modificacion_str}\n"

    response = make_response(content)
    response.headers["Content-Disposition"] = f"attachment; filename=ruta_{ruta.nombre.replace(' ', '_').lower()}.txt"
    response.headers["Content-type"] = "text/plain; charset=utf-8"
    return response

@rutas_bp.route('/rutas/exportar/pdf/<int:ruta_id>')
@role_required(['Superuser', 'Usuario Regular'])
def exportar_ruta_pdf(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada para exportar.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))

    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=letter)
    
    y_position = 750
    line_height = 15

    c.setFont('Helvetica-Bold', 14)
    c.drawString(100, y_position, f"Detalles de la Ruta: {ruta.nombre}")
    y_position -= (line_height * 2)

    c.setFont('Helvetica', 10)
    c.drawString(100, y_position, f"Provincia: {ruta.provincia}")
    y_position -= line_height
    c.drawString(100, y_position, f"Enlace de Video: {ruta.enlace_video if ruta.enlace_video else 'N/A'}")
    y_position -= line_height
    
    # Manejo de AttributeError para fecha_creacion y fecha_modificacion
    if hasattr(ruta, 'fecha_creacion') and ruta.fecha_creacion:
        c.drawString(100, y_position, f"Fecha de Creación: {ruta.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        c.drawString(100, y_position, "Fecha de Creación: N/A")
    y_position -= line_height

    if hasattr(ruta, 'fecha_modificacion') and ruta.fecha_modificacion:
        c.drawString(100, y_position, f"Última Modificación: {ruta.fecha_modificacion.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        c.drawString(100, y_position, "Última Modificación: N/A")
    y_position -= (line_height * 2)

    c.setFont('Helvetica-Bold', 12)
    c.drawString(100, y_position, "Detalle de la Ruta:")
    y_position -= line_height
    c.setFont('Helvetica', 10)
    
    for line in ruta.detalle.split('\n'):
        if y_position < 50:
            c.showPage()
            c.setFont('Helvetica', 10)
            y_position = 750
        c.drawString(100, y_position, line)
        y_position -= line_height

    c.save()
    pdf_data = buffer.getvalue()
    buffer.close()

    response = make_response(pdf_data)
    response.headers["Content-Disposition"] = f"attachment; filename=ruta_{ruta.nombre.replace(' ', '_').lower()}.pdf"
    response.headers["Content-type"] = "application/pdf"
    return response

@rutas_bp.route('/rutas/exportar/jpg/<int:ruta_id>')
@role_required(['Superuser', 'Usuario Regular'])
def exportar_ruta_jpg(ruta_id):
    flash('La exportación a JPG desde el servidor no está implementada directamente. Considere usar una solución de captura de pantalla en el cliente (navegador).', 'info')
    return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta_id))
