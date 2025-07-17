from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_file, Response
from models import db, CalendarEvent, User
import os
from werkzeug.utils import secure_filename
from datetime import datetime, date, time
import json
import io
from openpyxl import Workbook
from fpdf import FPDF

# Crear el Blueprint para el módulo de calendario
calendario_bp = Blueprint('calendario', __name__, template_folder='templates')

# NOTA: La configuración de CALENDAR_IMAGE_UPLOAD_FOLDER y la creación del directorio
# se han movido a app.py para asegurar que current_app esté disponible.
# Aquí simplemente nos referiremos a ellas a través de current_app.config.

# La función allowed_file también se asume que está adjunta a current_app.

# Ruta para ver todos los eventos del calendario
@calendario_bp.route('/')
def ver_calendario():
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))
    
    # Obtener el parámetro de búsqueda por etiqueta
    search_tag = request.args.get('tag', '').strip()

    if search_tag:
        # Si hay una etiqueta de búsqueda, filtrar los eventos
        eventos = CalendarEvent.query.filter_by(nombre_etiqueta=search_tag).order_by(CalendarEvent.fecha_actividad.desc()).all()
    else:
        # Si no hay etiqueta de búsqueda, mostrar todos los eventos
        eventos = CalendarEvent.query.order_by(CalendarEvent.fecha_actividad.desc()).all()
        
    # Obtener todas las etiquetas únicas para el buscador
    etiquetas_disponibles = db.session.query(CalendarEvent.nombre_etiqueta).distinct().all()
    etiquetas_disponibles = [tag[0] for tag in etiquetas_disponibles if tag[0]] # Limpiar tuplas y None
    
    return render_template('ver_calendario.html', eventos=eventos, search_tag=search_tag, etiquetas_disponibles=etiquetas_disponibles)


# Ruta para crear un nuevo evento del calendario
@calendario_bp.route('/crear', methods=['GET', 'POST'])
def crear_calendario():
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))

    etiqueta_opciones = ["Evento de La Tribu", "Evento Externo", "Fechas de Cumpleaños", "Celebraciones"]

    if request.method == 'POST':
        nombre_actividad = request.form.get('nombre_actividad')
        fecha_actividad_str = request.form.get('fecha_actividad')
        hora_actividad_str = request.form.get('hora_actividad') # Puede ser None si es todo el día
        descripcion = request.form.get('descripcion')
        nombre_etiqueta = request.form.get('nombre_etiqueta')
        es_todo_el_dia = 'es_todo_el_dia' in request.form # Checkbox
        correos_notificacion_str = request.form.get('correos_notificacion')
        
        # Validación de campos obligatorios
        if not nombre_actividad or not fecha_actividad_str or not nombre_etiqueta:
            flash('Por favor, completa todos los campos obligatorios.', 'danger')
            return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones)

        try:
            fecha_actividad = datetime.strptime(fecha_actividad_str, '%Y-%m-%d').date()
            hora_actividad = None
            if not es_todo_el_dia and hora_actividad_str:
                hora_actividad = datetime.strptime(hora_actividad_str, '%H:%M').time()
        except ValueError as e:
            flash(f'Formato de fecha u hora inválido: {e}', 'danger')
            return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones,
                                       nombre_actividad=nombre_actividad, fecha_actividad=fecha_actividad_str,
                                       hora_actividad=hora_actividad_str, descripcion=descripcion,
                                       nombre_etiqueta=nombre_etiqueta, es_todo_el_dia=es_todo_el_dia,
                                       correos_notificacion=correos_notificacion_str)

        # Validación de duplicados
        existing_event_query = CalendarEvent.query.filter_by(fecha_actividad=fecha_actividad)
        
        if es_todo_el_dia:
            # Si el nuevo evento es de todo el día, verificar si ya hay un evento de todo el día para esa fecha
            # o si hay eventos con hora específica.
            if existing_event_query.filter_by(es_todo_el_dia=True).first():
                flash('Ya existe un evento de todo el día programado para esta fecha.', 'danger')
                return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones,
                                       nombre_actividad=nombre_actividad, fecha_actividad=fecha_actividad_str,
                                       hora_actividad=hora_actividad_str, descripcion=descripcion,
                                       nombre_etiqueta=nombre_etiqueta, es_todo_el_dia=es_todo_el_dia,
                                       correos_notificacion=correos_notificacion_str)
            if existing_event_query.filter(CalendarEvent.es_todo_el_dia == False).first():
                flash('Ya existen eventos con hora específica programados para esta fecha. No se puede crear un evento de todo el día.', 'danger')
                return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones,
                                       nombre_actividad=nombre_actividad, fecha_actividad=fecha_actividad_str,
                                       hora_actividad=hora_actividad_str, descripcion=descripcion,
                                       nombre_etiqueta=nombre_etiqueta, es_todo_el_dia=es_todo_el_dia,
                                       correos_notificacion=correos_notificacion_str)
        else:
            # Si el nuevo evento tiene una hora específica
            if existing_event_query.filter_by(es_todo_el_dia=True).first():
                flash('Ya existe un evento de todo el día programado para esta fecha. No se puede agregar un evento con hora específica.', 'danger')
                return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones,
                                       nombre_actividad=nombre_actividad, fecha_actividad=fecha_actividad_str,
                                       hora_actividad=hora_actividad_str, descripcion=descripcion,
                                       nombre_etiqueta=nombre_etiqueta, es_todo_el_dia=es_todo_el_dia,
                                       correos_notificacion=correos_notificacion_str)
            
            if hora_actividad:
                if existing_event_query.filter_by(hora_actividad=hora_actividad).first():
                    flash('Ya existe una actividad programada para esta fecha y hora. Por favor, elige otra hora o fecha.', 'danger')
                    return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones,
                                           nombre_actividad=nombre_actividad, fecha_actividad=fecha_actividad_str,
                                           hora_actividad=hora_actividad_str, descripcion=descripcion,
                                           nombre_etiqueta=nombre_etiqueta, es_todo_el_dia=es_todo_el_dia,
                                           correos_notificacion=correos_notificacion_str)

        # Manejo de correos de notificación
        correos_list = []
        if correos_notificacion_str:
            # Separar por comas y limpiar espacios, filtrar vacíos
            correos_list = [email.strip() for email in correos_notificacion_str.split(',') if email.strip()]
            # Opcional: añadir validación de formato de correo aquí
        
        correos_json = json.dumps(correos_list)

        flyer_imagen_url = None
        if 'flyer_imagen' in request.files:
            flyer_file = request.files['flyer_imagen']
            # Usa la función allowed_file global de current_app
            if flyer_file and current_app.allowed_file(flyer_file.filename):
                filename = secure_filename(flyer_file.filename)
                # Usa la ruta de subida de imágenes de calendario configurada en app.py
                file_path = os.path.join(current_app.config['CALENDAR_IMAGE_UPLOAD_FOLDER'], filename)
                flyer_file.save(file_path)
                flyer_imagen_url = 'uploads/calendar_images/' + filename
            elif flyer_file.filename != '':
                flash('Tipo de archivo de imagen no permitido. Solo se aceptan PNG, JPG, JPEG, GIF.', 'warning')
                return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones,
                                       nombre_actividad=nombre_actividad, fecha_actividad=fecha_actividad_str,
                                       hora_actividad=hora_actividad_str, descripcion=descripcion,
                                       nombre_etiqueta=nombre_etiqueta, es_todo_el_dia=es_todo_el_dia,
                                       correos_notificacion=correos_notificacion_str)
        
        # Asocia el evento al usuario logeado
        creator_id = session.get('user_id')
        if not creator_id:
            flash('Error: No se pudo identificar al usuario creador del evento.', 'danger')
            return redirect(url_for('login')) # Redirige al login si no hay usuario

        new_event = CalendarEvent(
            flyer_imagen_url=flyer_imagen_url,
            nombre_actividad=nombre_actividad,
            fecha_actividad=fecha_actividad,
            hora_actividad=hora_actividad,
            descripcion=descripcion,
            nombre_etiqueta=nombre_etiqueta,
            es_todo_el_dia=es_todo_el_dia,
            correos_notificacion=correos_json,
            creator_id=creator_id
        )

        try:
            db.session.add(new_event)
            db.session.commit()
            flash('Evento de calendario creado exitosamente!', 'success')
            
            # TODO: Lógica para enviar correos electrónicos de notificación aquí
            # Esto requeriría una configuración de SMTP en la aplicación.
            # current_app.logger.info(f"Notificación enviada a: {correos_list}")

            return redirect(url_for('calendario.ver_calendario'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el evento de calendario: {e}', 'danger')
            current_app.logger.error(f"Error al crear evento de calendario: {e}")
            return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones,
                                   nombre_actividad=nombre_actividad, fecha_actividad=fecha_actividad_str,
                                   hora_actividad=hora_actividad_str, descripcion=descripcion,
                                   nombre_etiqueta=nombre_etiqueta, es_todo_el_dia=es_todo_el_dia,
                                   correos_notificacion=correos_notificacion_str)

    # Si es GET request, simplemente renderiza el formulario vacío
    return render_template('crear_calendario.html', etiqueta_opciones=etiqueta_opciones)


# Ruta para editar un evento del calendario
@calendario_bp.route('/editar/<int:event_id>', methods=['GET', 'POST'])
def editar_calendario(event_id):
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))
    
    evento = CalendarEvent.query.get_or_404(event_id)
    etiqueta_opciones = ["Evento de La Tribu", "Evento Externo", "Fechas de Cumpleaños", "Celebraciones"]

    if request.method == 'POST':
        evento.nombre_actividad = request.form.get('nombre_actividad')
        fecha_actividad_str = request.form.get('fecha_actividad')
        hora_actividad_str = request.form.get('hora_actividad')
        evento.descripcion = request.form.get('descripcion')
        evento.nombre_etiqueta = request.form.get('nombre_etiqueta')
        evento.es_todo_el_dia = 'es_todo_el_dia' in request.form
        correos_notificacion_str = request.form.get('correos_notificacion')

        # Validación de campos obligatorios
        if not evento.nombre_actividad or not fecha_actividad_str or not evento.nombre_etiqueta:
            flash('Por favor, completa todos los campos obligatorios.', 'danger')
            return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)

        try:
            evento.fecha_actividad = datetime.strptime(fecha_actividad_str, '%Y-%m-%d').date()
            if not evento.es_todo_el_dia and hora_actividad_str:
                evento.hora_actividad = datetime.strptime(hora_actividad_str, '%H:%M').time()
            else:
                evento.hora_actividad = None # Asegurarse de que sea None si es todo el día
        except ValueError as e:
            flash(f'Formato de fecha u hora inválido: {e}', 'danger')
            return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)

        # Validación de duplicados (excluyendo el propio evento que se está editando)
        existing_event_query = CalendarEvent.query.filter(
            CalendarEvent.fecha_actividad == evento.fecha_actividad,
            CalendarEvent.id != event_id
        )

        if evento.es_todo_el_dia:
            if existing_event_query.filter_by(es_todo_el_dia=True).first():
                flash('Ya existe un evento de todo el día programado para esta fecha.', 'danger')
                return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)
            if existing_event_query.filter(CalendarEvent.es_todo_el_dia == False).first():
                flash('Ya existen eventos con hora específica programados para esta fecha. No se puede crear un evento de todo el día.', 'danger')
                return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)
        else:
            if existing_event_query.filter_by(es_todo_el_dia=True).first():
                flash('Ya existe un evento de todo el día programado para esta fecha. No se puede agregar un evento con hora específica.', 'danger')
                return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)
            
            if evento.hora_actividad:
                if existing_event_query.filter_by(hora_actividad=evento.hora_actividad).first():
                    flash('Ya existe una actividad programada para esta fecha y hora. Por favor, elige otra hora o fecha.', 'danger')
                    return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)

        # Manejo de correos de notificación
        correos_list = []
        if correos_notificacion_str:
            correos_list = [email.strip() for email in correos_notificacion_str.split(',') if email.strip()]
        evento.correos_notificacion = json.dumps(correos_list)

        # Manejo de la imagen
        if 'flyer_imagen' in request.files:
            flyer_file = request.files['flyer_imagen']
            # Usa la función allowed_file global de current_app
            if flyer_file and current_app.allowed_file(flyer_file.filename):
                # Eliminar imagen antigua si existe
                if evento.flyer_imagen_url:
                    try:
                        old_path = os.path.join(current_app.root_path, 'static', evento.flyer_imagen_url)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        current_app.logger.warning(f"No se pudo eliminar la imagen antigua del evento {event_id}: {e}")

                filename = secure_filename(flyer_file.filename)
                # Usa la ruta de subida de imágenes de calendario configurada en app.py
                file_path = os.path.join(current_app.config['CALENDAR_IMAGE_UPLOAD_FOLDER'], filename)
                flyer_file.save(file_path)
                evento.flyer_imagen_url = 'uploads/calendar_images/' + filename
            elif flyer_file.filename != '':
                flash('Tipo de archivo de imagen no permitido. Solo se aceptan PNG, JPG, JPEG, GIF.', 'warning')
                return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)
        
        try:
            db.session.commit()
            flash('Evento de calendario actualizado exitosamente!', 'success')
            return redirect(url_for('calendario.detalle_calendario', event_id=evento.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el evento de calendario: {e}', 'danger')
            current_app.logger.error(f"Error al actualizar evento {event_id}: {e}")
            return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)

    # Convertir correos de JSON a string para el textarea en GET request
    if evento.correos_notificacion:
        try:
            evento.correos_notificacion = ', '.join(json.loads(evento.correos_notificacion))
        except json.JSONDecodeError:
            evento.correos_notificacion = "Error al cargar correos."
    
    return render_template('editar_calendario.html', evento=evento, etiqueta_opciones=etiqueta_opciones)


# Ruta para ver el detalle de un evento
@calendario_bp.route('/detalle/<int:event_id>')
def detalle_calendario(event_id):
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))
    
    evento = CalendarEvent.query.get_or_404(event_id)
    
    # Decodificar correos para mostrarlos
    correos_list = []
    if evento.correos_notificacion:
        try:
            correos_list = json.loads(evento.correos_notificacion)
        except json.JSONDecodeError:
            correos_list = ["Error al cargar correos."]

    return render_template('detalle_calendario.html', evento=evento, correos_list=correos_list)


# Ruta para eliminar un evento
@calendario_bp.route('/eliminar/<int:event_id>', methods=['POST'])
def eliminar_calendario(event_id):
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))
        
    evento = CalendarEvent.query.get_or_404(event_id)
    
    try:
        # Eliminar la imagen asociada si existe
        if evento.flyer_imagen_url:
            try:
                file_path = os.path.join(current_app.root_path, 'static', evento.flyer_imagen_url)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                current_app.logger.warning(f"No se pudo eliminar la imagen del evento {event_id}: {e}")

        db.session.delete(evento)
        db.session.commit()
        flash('Evento de calendario eliminado exitosamente!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el evento de calendario: {e}', 'danger')
        current_app.logger.error(f"Error al eliminar evento {event_id}: {e}")
    
    return redirect(url_for('calendario.ver_calendario'))


# --- Rutas de Exportación ---

@calendario_bp.route('/exportar/excel/<int:event_id>')
def exportar_excel(event_id):
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))

    evento = CalendarEvent.query.get_or_404(event_id) 

    wb = Workbook()
    ws = wb.active
    ws.title = f"Evento {evento.nombre_actividad}"

    ws.append(["DETALLE DEL EVENTO DE CALENDARIO"])
    ws.append([])
    ws.append(["Nombre de la Actividad:", evento.nombre_actividad])
    ws.append(["Fecha de la Actividad:", evento.fecha_actividad.strftime('%Y-%m-%d')])
    ws.append(["Hora de la Actividad:", evento.hora_actividad.strftime('%H:%M') if evento.hora_actividad else "Evento de todo el día"])
    ws.append(["Descripción:", evento.descripcion if evento.descripcion else "N/A"])
    ws.append(["Etiqueta:", evento.nombre_etiqueta])
    ws.append(["Es todo el día:", "Sí" if evento.es_todo_el_dia else "No"])
    
    correos_list = []
    if evento.correos_notificacion:
        try:
            correos_list = json.loads(evento.correos_notificacion)
        except json.JSONDecodeError:
            correos_list = ["Error al cargar correos."]
    ws.append(["Correos de Notificación:", ", ".join(correos_list) if correos_list else "N/A"])
    
    ws.append(["Fecha de Creación:", evento.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')])
    ws.append(["Última Modificación:", evento.fecha_modificacion.strftime('%Y-%m-%d %H:%M:%S') if evento.fecha_modificacion else "N/A"])

    excel_stream = io.BytesIO()
    wb.save(excel_stream)
    excel_stream.seek(0)

    filename = f"{evento.nombre_actividad.replace(' ', '_').lower()}_evento.xlsx"
    return Response(excel_stream.read(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={"Content-Disposition": f"attachment;filename={filename}"})


@calendario_bp.route('/exportar/pdf/<int:event_id>')
def exportar_pdf(event_id):
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))
    
    evento = CalendarEvent.query.get_or_404(event_id)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.multi_cell(0, 10, f"DETALLE DEL EVENTO DE CALENDARIO - {evento.nombre_actividad.upper()}", align='C')
    pdf.ln(10)

    pdf.set_font("Arial", style='B', size=12)
    pdf.multi_cell(0, 10, "INFORMACIÓN DEL EVENTO")
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, f"Nombre de la Actividad: {evento.nombre_actividad}")
    pdf.multi_cell(0, 7, f"Fecha de la Actividad: {evento.fecha_actividad.strftime('%Y-%m-%d')}")
    pdf.multi_cell(0, 7, f"Hora de la Actividad: {evento.hora_actividad.strftime('%H:%M') if evento.hora_actividad else 'Evento de todo el día'}")
    
    pdf.multi_cell(0, 7, f"Etiqueta: {evento.nombre_etiqueta}")
    pdf.multi_cell(0, 7, f"Es todo el día: {'Sí' if evento.es_todo_el_dia else 'No'}")

    correos_list = []
    if evento.correos_notificacion:
        try:
            correos_list = json.loads(evento.correos_notificacion)
        except json.JSONDecodeError:
            correos_list = ["Error al cargar correos."]
    pdf.multi_cell(0, 7, f"Correos de Notificación: {', '.join(correos_list) if correos_list else 'N/A'}")
    
    pdf.multi_cell(0, 7, f"Fecha de Creación: {evento.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.multi_cell(0, 7, f"Última Modificación: {evento.fecha_modificacion.strftime('%Y-%m-%d %H:%M:%S') if evento.fecha_modificacion else 'N/A'}")
    
    pdf.ln(5)
    pdf.set_font("Arial", style='B', size=12)
    pdf.multi_cell(0, 10, "DESCRIPCIÓN")
    pdf.set_font("Arial", size=10)
    # FPDF no renderiza HTML directamente, así que pasamos el texto plano
    # Si CKEditor es usado para HTML, esto mostrará el HTML como texto plano.
    pdf.multi_cell(0, 7, evento.descripcion if evento.descripcion else "No hay descripción disponible.")


    pdf_output = pdf.output(dest='S').encode('latin-1')
    pdf_stream = io.BytesIO(pdf_output)
    pdf_stream.seek(0)

    filename = f"{evento.nombre_actividad.replace(' ', '_').lower()}_evento.pdf"
    return send_file(
        pdf_stream,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@calendario_bp.route('/exportar/jpg/<int:event_id>')
def exportar_jpg(event_id):
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))
    
    flash('La exportación a JPG requiere herramientas adicionales (ej. un navegador headless para renderizar la página a imagen) y no está implementada directamente.', 'info')
    return redirect(url_for('calendario.detalle_calendario', event_id=event_id))

@calendario_bp.route('/exportar/txt/<int:event_id>')
def exportar_txt(event_id):
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))

    evento = CalendarEvent.query.get_or_404(event_id)

    correos_list = []
    if evento.correos_notificacion:
        try:
            correos_list = json.loads(evento.correos_notificacion)
        except json.JSONDecodeError:
            correos_list = ["Error al cargar correos."]

    content = f"Detalles del Evento de Calendario: {evento.nombre_actividad}\n\n" \
              f"Información:\n" \
              f"  Nombre de la Actividad: {evento.nombre_actividad}\n" \
              f"  Fecha de la Actividad: {evento.fecha_actividad.strftime('%Y-%m-%d')}\n" \
              f"  Hora de la Actividad: {evento.hora_actividad.strftime('%H:%M') if evento.hora_actividad else 'Evento de todo el día'}\n" \
              f"  Etiqueta: {evento.nombre_etiqueta}\n" \
              f"  Es todo el día: {'Sí' if evento.es_todo_el_dia else 'No'}\n" \
              f"  Correos de Notificación: {', '.join(correos_list) if correos_list else 'N/A'}\n" \
              f"  Fecha de Creación: {evento.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')}\n" \
              f"  Última Modificación: {evento.fecha_modificacion.strftime('%Y-%m-%d %H:%M:%S') if evento.fecha_modificacion else 'N/A'}\n\n" \
              f"Descripción:\n{evento.descripcion if evento.descripcion else 'No hay descripción disponible.'}\n"

    buffer = io.BytesIO()
    buffer.write(content.encode('utf-8'))
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'evento_{evento.nombre_actividad.replace(" ", "_").lower()}.txt'
    )
