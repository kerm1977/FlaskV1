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

    # Expresiones regulares más robustas para YouTube
    youtube_patterns = [
        re.compile(r'(?:https?:\/\/)?(?:www\.)?(?:m\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|)([a-zA-Z0-9_-]{11})(?:\S+)?'),
        re.compile(r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})(?:\S+)?')
    ]

    for pattern in youtube_patterns:
        youtube_match = pattern.search(video_url)
        if youtube_match:
            video_id = youtube_match.group(1)
            return f"https://www.youtube.com/embed/{video_id}"

    # Expresiones regulares para Facebook
    facebook_patterns = [
        re.compile(r'(?:https?:\/\/)?(?:www\.)?(?:facebook\.com)\/watch\/\?v=(\d+)'),
        re.compile(r'(?:https?:\/\/)?(?:www\.)?(?:facebook\.com)\/([a-zA-Z0-9\.]+)\/videos\/(?:vb\.\d+\/)?(\d+)(?:\S+)?')
    ]

    for pattern in facebook_patterns:
        facebook_match = pattern.search(video_url)
        if facebook_match:
            # Para Facebook, el plugin de video usa la URL original como el parámetro 'href'
            # y requiere el width para que se muestre correctamente en el iframe.
            return f"https://www.facebook.com/plugins/video.php?href={video_url}&show_text=0&width=1280"
    
    # Si no se reconoce ninguna plataforma de video conocida, devuelve None
    return None

@rutas_bp.route('/rutas')
@role_required(['Superuser', 'Usuario Regular']) # Asegúrate de que los usuarios regulares también puedan ver las rutas
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
        try:
            db.session.add(nueva_ruta)
            db.session.commit()
            flash('Ruta creada exitosamente.', 'success')
            return redirect(url_for('rutas.ver_rutas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la ruta: {e}', 'danger')
            current_app.logger.error(f"Error al crear ruta: {e}")
    
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
        
        try:
            db.session.commit()
            flash('Ruta actualizada exitosamente.', 'success')
            return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la ruta: {e}', 'danger')
            current_app.logger.error(f"Error al actualizar ruta {ruta_id}: {e}")
    
    return render_template('editar_rutas.html', ruta=ruta, provincias=PROVINCIAS)

@rutas_bp.route('/rutas/<int:ruta_id>')
@role_required(['Superuser', 'Usuario Regular']) # Asegúrate de que los usuarios regulares también puedan ver los detalles
def detalle_ruta(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))
        
    embed_url = get_embed_url(ruta.enlace_video) if ruta.enlace_video else None
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

    # Se eliminan las referencias a fecha_creacion y fecha_modificacion
    content = f"Nombre de la Ruta: {ruta.nombre}\n" \
              f"Provincia: {ruta.provincia}\n" \
              f"Detalle: {ruta.detalle}\n" \
              f"Enlace de Video: {ruta.enlace_video if ruta.enlace_video else 'N/A'}\n"

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
    y_position -= (line_height * 2) # Ajuste de espacio tras eliminar fechas

    c.setFont('Helvetica-Bold', 12)
    c.drawString(100, y_position, "Detalle de la Ruta:")
    y_position -= line_height
    c.setFont('Helvetica', 10)
    
    # Limpiar el HTML del detalle para el PDF
    clean_detail = re.sub('<[^<]+?>', '', ruta.detalle)
    lines = clean_detail.split('\n')
    for line in lines:
        # Dividir líneas largas si exceden el ancho de la página
        words = line.split(' ')
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            # Estimación simple del ancho del texto (ajusta según sea necesario)
            if c.stringWidth(test_line, 'Helvetica', 10) < 400: # Ancho de 400 puntos, ajusta si es necesario
                current_line.append(word)
            else:
                if y_position < 50:
                    c.showPage()
                    c.setFont('Helvetica', 10)
                    y_position = 750
                c.drawString(100, y_position, ' '.join(current_line))
                y_position -= line_height
                current_line = [word]
        if current_line:
            if y_position < 50:
                c.showPage()
                c.setFont('Helvetica', 10)
                y_position = 750
            c.drawString(100, y_position, ' '.join(current_line))
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
    flash('La exportación a JPG desde el servidor no está implementada directamente. Considere usar una solución de captura de pantalla en el cliente (navegador) o un servicio externo si es indispensable.', 'info')
    return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta_id))

