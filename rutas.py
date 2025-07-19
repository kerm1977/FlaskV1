# rutas.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, make_response
from models import db, Ruta # Importa db y el nuevo modelo Ruta
from functools import wraps # Importar wraps para el decorador role_required
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as pdf_canvas # Renombrado para evitar conflicto con Flask canvas
from datetime import datetime, date # Importar datetime y date para manejar fechas
import re # NUEVO: Importar re para expresiones regulares

# Crea un Blueprint para el módulo de rutas
rutas_bp = Blueprint('rutas', __name__, template_folder='templates')

# Lista de provincias de Costa Rica
PROVINCIAS = ["Alajuela", "Cartago", "Heredia", "Puntarenas", "Limón", "Guanacaste", "San José"]

# NUEVA: Lista de categorías de búsqueda, con las provincias primero, luego el separador y las nuevas opciones
CATEGORIAS_BUSQUEDA = [
    "Todas las Categorías", # Opción por defecto para mostrar todo
] + sorted(PROVINCIAS) + [ # Añade las provincias ordenadas alfabéticamente
    "Otros", # Nueva etiqueta de grupo
    "Internacional", # Nueva categoría: Internacional
    "Caminatas Programadas", # Nueva categoría 1
    "Caminatas por Reconocer" # Nueva categoría 2
]

# Define la categoría permitida para la exportación masiva
ALLOWED_EXPORT_CATEGORY = "Caminatas Programadas"

# Define las categorías que están explícitamente prohibidas para la exportación masiva
FORBIDDEN_MASS_EXPORT_CATEGORIES = PROVINCIAS + ["Internacional", "Caminatas por Reconocer", "Otros"]


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
                # Mensaje específico para el acceso a detalle_ruta
                if f.__name__ == 'detalle_ruta':
                    flash('SOLO ADMINISTRADORES PUEDEN VER EL CONTENIDO.', 'danger') # Mensaje más claro
                else:
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
        re.compile(r'(?:https?:\/\/)?(?:www\.)?(?:m\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|)([a-zA-Z0-9_-]{11})(?:\S+)?'),
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

# Helper function to return an empty PDF or TXT document
def _return_empty_pdf_or_txt(is_pdf=True):
    """
    Función de ayuda para devolver un documento PDF o TXT vacío
    con un mensaje indicando que la categoría no es exportable.
    """
    if is_pdf:
        buffer = BytesIO()
        c = pdf_canvas.Canvas(buffer, pagesize=letter)
        c.setFont('Helvetica', 12)
        c.drawString(100, 750, "No hay rutas disponibles para exportar en la categoría seleccionada.")
        c.save()
        pdf_data = buffer.getvalue()
        buffer.close()
        response = make_response(pdf_data)
        response.headers["Content-Disposition"] = f"attachment; filename=rutas_no_exportables.pdf"
        response.headers["Content-type"] = "application/pdf"
        return response
    else:
        content = "No hay rutas disponibles para exportar en la categoría seleccionada."
        response = make_response(content)
        response.headers["Content-Disposition"] = f"attachment; filename=rutas_no_exportables.txt"
        response.headers["Content-type"] = "text/plain; charset=utf-8"
        return response


@rutas_bp.route('/rutas')
# @role_required(['Superuser', 'Usuario Regular']) # COMENTADO: Ahora los usuarios regulares también pueden ver las rutas
def ver_rutas():
    # Obtener el parámetro 'categoria' de la URL si existe
    categoria_seleccionada = request.args.get('categoria')

    # Consulta inicial para todas las rutas
    query = Ruta.query

    # Aplicar filtro si se seleccionó una categoría específica (que no sea "Todas las Categorías" o "Otros")
    if categoria_seleccionada and categoria_seleccionada != 'Todas las Categorías' and categoria_seleccionada != 'Otros':
        query = query.filter_by(provincia=categoria_seleccionada) # El campo 'provincia' ahora almacena la categoría

    # Obtener todas las rutas filtradas
    rutas = query.order_by(Ruta.provincia, Ruta.nombre).all()
    
    # Si no se seleccionó ninguna categoría o se seleccionó "Todas las Categorías",
    # asegúrate de que el dropdown muestre "Todas las Categorías"
    if not categoria_seleccionada:
        categoria_seleccionada = 'Todas las Categorías'
    
    # Agrupar las rutas por su "provincia" (que ahora es la categoría)
    # Esto se hace aquí en Python para evitar la lógica compleja en Jinja2
    rutas_por_categoria = {}
    for ruta in rutas:
        if ruta.provincia not in rutas_por_categoria:
            rutas_por_categoria[ruta.provincia] = []
        rutas_por_categoria[ruta.provincia].append(ruta)

    return render_template('ver_rutas.html', 
                           rutas_por_categoria=rutas_por_categoria, # Pasa las rutas agrupadas por categoría
                           categorias_busqueda=CATEGORIAS_BUSQUEDA, # Pasa la lista completa de categorías para el dropdown
                           provincia_seleccionada=categoria_seleccionada) # Pasa la categoría seleccionada para el dropdown

@rutas_bp.route('/rutas/crear', methods=['GET', 'POST'])
@role_required('Superuser')
def crear_ruta():
    if request.method == 'POST':
        nombre = request.form['nombre']
        # El campo 'provincia' del formulario ahora almacenará la categoría seleccionada
        categoria = request.form['provincia'] 
        detalle = request.form['detalle']
        enlace_video = request.form.get('enlace_video')
        
        # Obtener y procesar la fecha
        fecha_str = request.form.get('fecha')
        fecha = None
        if fecha_str:
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de fecha inválido. Por favor, usa YYYY-MM-DD.', 'danger')
                return redirect(url_for('rutas.crear_ruta'))

        # Obtener y procesar el precio
        precio_str = request.form.get('precio')
        precio = None
        if precio_str:
            try:
                # Convertir a entero primero, luego a float para el modelo
                precio = float(int(precio_str)) 
            except ValueError:
                flash('Formato de precio inválido. Por favor, ingresa un número entero.', 'danger')
                return redirect(url_for('rutas.crear_ruta'))


        if not nombre or not categoria:
            flash('El nombre y la categoría son campos obligatorios.', 'danger')
            return render_template('crear_rutas.html', categorias_busqueda=CATEGORIAS_BUSQUEDA)

        nueva_ruta = Ruta(
            nombre=nombre,
            provincia=categoria, # Guardamos la categoría en el campo 'provincia'
            detalle=detalle,
            enlace_video=enlace_video,
            fecha=fecha, # Asignar la fecha procesada
            precio=precio # Asignar el precio procesado
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
    
    # Filtrar CATEGORIAS_BUSQUEDA para no incluir "Todas las Categorías" ni "Otros" en el formulario de creación
    categorias_para_formulario = [cat for cat in CATEGORIAS_BUSQUEDA if cat != 'Todas las Categorías' and cat != 'Otros']
    return render_template('crear_rutas.html', categorias_busqueda=categorias_para_formulario) # Pasa las categorías filtradas al formulario

@rutas_bp.route('/rutas/editar/<int:ruta_id>', methods=['GET', 'POST'])
@role_required('Superuser')
def editar_ruta(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))

    if request.method == 'POST':
        ruta.nombre = request.form['nombre']
        # El campo 'provincia' del formulario ahora almacenará la categoría seleccionada
        ruta.provincia = request.form['provincia'] 
        ruta.detalle = request.form['detalle']
        ruta.enlace_video = request.form.get('enlace_video')

        # Obtener y procesar la fecha
        fecha_str = request.form.get('fecha')
        ruta.fecha = None # Resetear la fecha por si se envía vacía
        if fecha_str:
            try:
                ruta.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de fecha inválido. Por favor, usa YYYY-MM-DD.', 'danger')
                return redirect(url_for('rutas.editar_ruta', ruta_id=ruta.id))

        # Obtener y procesar el precio
        precio_str = request.form.get('precio')
        ruta.precio = None # Resetear el precio por si se envía vacío
        if precio_str:
            try:
                # Convertir a entero primero, luego a float para el modelo
                precio = float(int(precio_str))
            except ValueError:
                flash('Formato de precio inválido. Por favor, ingresa un número entero.', 'danger')
                return redirect(url_for('rutas.editar_ruta', ruta_id=ruta.id))
        
        try:
            db.session.commit()
            flash('Ruta actualizada exitosamente.', 'success')
            return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la ruta: {e}', 'danger')
            current_app.logger.error(f"Error al actualizar ruta {ruta_id}: {e}")
    
    # Filtrar CATEGORIAS_BUSQUEDA para no incluir "Todas las Categorías" ni "Otros" en el formulario de edición
    categorias_para_formulario = [cat for cat in CATEGORIAS_BUSQUEDA if cat != 'Todas las Categorías' and cat != 'Otros']
    return render_template('editar_rutas.html', ruta=ruta, categorias_busqueda=categorias_para_formulario) # Pasa las categorías filtradas al formulario

@rutas_bp.route('/rutas/<int:ruta_id>')
@role_required(['Superuser', 'Usuario Regular']) # Los usuarios regulares también pueden ver el detalle de la ruta
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
# @role_required(['Superuser', 'Usuario Regular']) # COMENTADO
def exportar_ruta_txt(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada para exportar.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))

    # Lógica para restringir la exportación a "Caminatas Programadas" para Usuario Regular
    user_role = session.get('role')
    if user_role == 'Usuario Regular' and ruta.provincia != ALLOWED_EXPORT_CATEGORY:
        flash(f'Como Usuario Regular, solo puedes exportar rutas de "{ALLOWED_EXPORT_CATEGORY}".', 'danger')
        return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta.id))

    # Se eliminan las referencias a fecha_creacion y fecha_modificacion
    # Se eliminó la línea de categoría para la exportación individual
    content = f"Nombre de la Ruta: {ruta.nombre}\n" \
              f"Detalle: {ruta.detalle}\n" \
              f"Enlace de Video: {ruta.enlace_video if ruta.enlace_video else 'N/A'}\n" \
              f"Fecha: {ruta.fecha.strftime('%d/%m/%Y') if ruta.fecha else 'N/A'}\n" \
              f"Precio: ¢{int(ruta.precio) if ruta.precio is not None else 'N/A'}\n" # Precio sin decimales

    response = make_response(content)
    response.headers["Content-Disposition"] = f"attachment; filename=ruta_{ruta.nombre.replace(' ', '_').lower()}.txt"
    response.headers["Content-type"] = "text/plain; charset=utf-8"
    return response

@rutas_bp.route('/rutas/exportar/pdf/<int:ruta_id>')
# @role_required(['Superuser', 'Usuario Regular']) # COMENTADO
def exportar_ruta_pdf(ruta_id):
    ruta = db.session.get(Ruta, ruta_id)
    if not ruta:
        flash('Ruta no encontrada para exportar.', 'danger')
        return redirect(url_for('rutas.ver_rutas'))

    # Lógica para restringir la exportación a "Caminatas Programadas" para Usuario Regular
    user_role = session.get('role')
    if user_role == 'Usuario Regular' and ruta.provincia != ALLOWED_EXPORT_CATEGORY:
        flash(f'Como Usuario Regular, solo puedes exportar rutas de "{ALLOWED_EXPORT_CATEGORY}".', 'danger')
        return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta.id))

    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=letter)
    
    y_position = 750
    line_height = 15

    c.setFont('Helvetica-Bold', 14)
    c.drawString(100, y_position, f"Detalles de la Ruta: {ruta.nombre}")
    y_position -= (line_height * 2)

    c.setFont('Helvetica', 10)
    # Se eliminó la línea de categoría para la exportación individual en PDF
    
    c.drawString(100, y_position, f"Fecha: {ruta.fecha.strftime('%d/%m/%Y') if ruta.fecha else 'N/A'}") # Añadido fecha
    y_position -= line_height
    c.drawString(100, y_position, f"Precio: ¢{int(ruta.precio) if ruta.precio is not None else 'N/A'}\n") # Añadido precio sin decimales
    y_position -= line_height
    c.drawString(100, y_position, f"Enlace de Video: {ruta.enlace_video if ruta.enlace_video else 'N/A'}")
    y_position -= (line_height * 2) # Ajuste de espacio tras añadir campos

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
    filename = f"ruta_{ruta.nombre.replace(' ', '_').lower()}.pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "application/pdf"
    return response

@rutas_bp.route('/rutas/exportar/jpg/<int:ruta_id>')
@role_required(['Superuser', 'Usuario Regular'])
def exportar_ruta_jpg(ruta_id):
    flash('La exportación a JPG desde el servidor no está implementada directamente. Considere usar una solución de captura de pantalla en el cliente (navegador) o un servicio externo si es indispensable.', 'info')
    return redirect(url_for('rutas.detalle_ruta', ruta_id=ruta_id))


# NUEVAS RUTAS PARA EXPORTAR TODAS LAS RUTAS (o las filtradas por la categoría seleccionada)
@rutas_bp.route('/rutas/exportar/todas/pdf')
# Eliminado: @role_required(['Superuser', 'Usuario Regular'])
def exportar_todas_rutas_pdf():
    categoria_seleccionada = request.args.get('categoria')
    
    # Si la categoría solicitada está en la lista de categorías prohibidas para exportación masiva
    if categoria_seleccionada in FORBIDDEN_MASS_EXPORT_CATEGORIES:
        flash(f'La categoría "{categoria_seleccionada}" no puede ser exportada en este formato masivo.', 'danger')
        return _return_empty_pdf_or_txt(is_pdf=True)

    query = Ruta.query

    if categoria_seleccionada == ALLOWED_EXPORT_CATEGORY:
        query = query.filter_by(provincia=ALLOWED_EXPORT_CATEGORY)
    elif categoria_seleccionada == 'Todas las Categorías' or not categoria_seleccionada: # Si no se selecciona categoría, se considera "Todas las Categorías"
        # Si se selecciona "Todas las Categorías", se excluyen las categorías prohibidas de los resultados
        query = query.filter(Ruta.provincia.notin_(FORBIDDEN_MASS_EXPORT_CATEGORIES))
    else:
        # Para cualquier otra categoría no reconocida o no permitida explícitamente
        flash(f'Categoría de exportación no válida: "{categoria_seleccionada}".', 'danger')
        return _return_empty_pdf_or_txt(is_pdf=True)

    rutas = query.order_by(Ruta.provincia, Ruta.nombre).all()

    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=letter)
    
    y_position = 750
    line_height = 15
    page_number = 1

    def add_page_header(canvas_obj, y_pos, current_page_num):
        canvas_obj.setFont('Helvetica-Bold', 10)
        canvas_obj.drawString(500, 770, f"Página {current_page_num}")
        canvas_obj.setFont('Helvetica-Bold', 14)
        canvas_obj.drawString(100, y_pos, "Listado de Rutas Disponibles")
        canvas_obj.setFont('Helvetica', 10)
        return y_pos - (line_height * 2)

    y_position = add_page_header(c, y_position, page_number)

    if not rutas:
        c.drawString(100, y_position, "No hay rutas disponibles para exportar.")
    else:
        current_category = None
        for ruta in rutas:
            if y_position < 70: # Si queda poco espacio, añadir nueva página
                c.showPage()
                page_number += 1
                y_position = 750
                y_position = add_page_header(c, y_position, page_number)
                current_category = None # Resetear categoría para nuevo encabezado en la nueva página

            # Solo se muestra la categoría si es la primera vez que aparece o si cambia
            if ruta.provincia != current_category:
                if current_category is not None: # No añadir línea antes del primer encabezado
                    y_position -= line_height # Espacio entre categorías
                c.setFont('Helvetica-Bold', 12)
                c.drawString(100, y_position, f"Categoría: {ruta.provincia}")
                y_position -= line_height
                c.setFont('Helvetica', 10)
                current_category = ruta.provincia
            
            c.drawString(110, y_position, f"  - Nombre: {ruta.nombre}")
            y_position -= line_height
            c.drawString(110, y_position, f"    Fecha: {ruta.fecha.strftime('%d/%m/%Y') if ruta.fecha else 'N/A'}") # Añadido fecha
            y_position -= line_height
            c.drawString(110, y_position, f"    Precio: ¢{int(ruta.precio) if ruta.precio is not None else 'N/A'}") # Añadido precio sin decimales
            y_position -= line_height
            c.drawString(110, y_position, f"    Detalle: {re.sub('<[^<]+?>', '', ruta.detalle)[:100]}...") # Limpiar HTML y truncar
            y_position -= line_height
            c.drawString(110, y_position, f"    Video: {ruta.enlace_video if ruta.enlace_video else 'N/A'}")
            y_position -= (line_height * 1.5) # Espacio entre rutas

    c.save()
    pdf_data = buffer.getvalue()
    buffer.close()

    response = make_response(pdf_data)
    filename = f"todas_las_rutas_{categoria_seleccionada.replace(' ', '_').lower()}.pdf" if categoria_seleccionada and categoria_seleccionada != 'Todas las Categorías' else "todas_las_rutas.pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "application/pdf"
    return response


@rutas_bp.route('/rutas/exportar/todas/txt')
# Eliminado: @role_required(['Superuser', 'Usuario Regular'])
def exportar_todas_rutas_txt():
    categoria_seleccionada = request.args.get('categoria')

    # Si la categoría solicitada está en la lista de categorías prohibidas para exportación masiva
    if categoria_seleccionada in FORBIDDEN_MASS_EXPORT_CATEGORIES:
        flash(f'La categoría "{categoria_seleccionada}" no puede ser exportada en este formato masivo.', 'danger')
        return _return_empty_pdf_or_txt(is_pdf=False)

    query = Ruta.query
    if categoria_seleccionada == ALLOWED_EXPORT_CATEGORY:
        query = query.filter_by(provincia=ALLOWED_EXPORT_CATEGORY)
    elif categoria_seleccionada == 'Todas las Categorías' or not categoria_seleccionada: # Si no se selecciona categoría, se considera "Todas las Categorías"
        # Si se selecciona "Todas las Categorías", se excluyen las categorías prohibidas de los resultados
        query = query.filter(Ruta.provincia.notin_(FORBIDDEN_MASS_EXPORT_CATEGORIES))
    else:
        # Para cualquier otra categoría no reconocida o no permitida explícitamente
        flash(f'Categoría de exportación no válida: "{categoria_seleccionada}".', 'danger')
        return _return_empty_pdf_or_txt(is_pdf=False)

    rutas = query.order_by(Ruta.provincia, Ruta.nombre).all()

    content = "Listado de Rutas Disponibles\n\n"
    if not rutas:
        content += "No hay rutas disponibles para exportar."
    else:
        current_category = None
        for ruta in rutas:
            # Solo se muestra la categoría si es la primera vez que aparece o si cambia
            if ruta.provincia != current_category:
                content += f"\n--- Categoría: {ruta.provincia} ---\n"
                current_category = ruta.provincia
            content += f"Nombre: {ruta.nombre}\n"
            content += f"Fecha: {ruta.fecha.strftime('%d/%m/%Y') if ruta.fecha else 'N/A'}\n" # Añadido fecha
            content += f"Precio: ¢{int(ruta.precio) if ruta.precio is not None else 'N/A'}\n" # Añadido precio sin decimales
            content += f"Detalle: {re.sub('<[^<]+?>', '', ruta.detalle)}\n" # Limpiar HTML
            content += f"Enlace de Video: {ruta.enlace_video if ruta.enlace_video else 'N/A'}\n\n"

    response = make_response(content)
    filename = f"todas_las_rutas_{categoria_seleccionada.replace(' ', '_').lower()}.txt" if categoria_seleccionada and categoria_seleccionada != 'Todas las Categorías' else "todas_las_rutas.txt"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/plain; charset=utf-8"
    return response

@rutas_bp.route('/rutas/exportar/todas/jpg')
@role_required(['Superuser', 'Usuario Regular'])
def exportar_todas_rutas_jpg():
    flash('La exportación de todas las rutas a JPG desde el servidor no está implementada directamente. Considere usar una solución de captura de pantalla en el cliente (navegador) o un servicio externo si es indispensable.', 'info')
    return redirect(url_for('rutas.ver_rutas', categoria=request.args.get('categoria'))) # Redirigir a la vista actual
