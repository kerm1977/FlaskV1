from flask import Blueprint, render_template, session, redirect, url_for, flash, current_app, request, send_file, Response
from models import db, Project, User # Importa db, Project y User de models.py
from datetime import datetime, date
from werkzeug.utils import secure_filename
import os
import io
from sqlalchemy import or_
from functools import wraps # Importar wraps para decoradores

# Librerías para exportación
from fpdf import FPDF # Para exportar a PDF
from PIL import Image, ImageDraw, ImageFont # Para exportar a JPG

# CORRECTO: Esta es la parte de la URL que se guarda en la DB (relativa a la carpeta 'static')
# Y la que url_for('static', filename=...) espera
PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE = os.path.join('uploads', 'project_images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """
    Verifica si la extensión del archivo está permitida.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Creamos un Blueprint para organizar las rutas relacionadas con proyectos
proyecto_bp = Blueprint('proyecto', __name__, url_prefix='/proyectos')

# Decorador para roles (si no lo tienes, puedes omitirlo o adaptarlo)
def role_required(roles):
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


@proyecto_bp.route('/ver_proyectos')
def ver_proyectos():
    """
    Muestra una lista de todos los proyectos registrados, con funcionalidad de búsqueda.
    Requiere que el usuario esté logueado.
    """
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))

    search_query = request.args.get('search_query', '').strip()

    try:
        query = Project.query
        
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                or_(
                    Project.nombre_proyecto.ilike(search_pattern),
                    Project.propuesta_por.ilike(search_pattern),
                    Project.provincia.ilike(search_pattern),
                    Project.dificultad.ilike(search_pattern),
                    Project.transporte_terrestre.ilike(search_pattern),
                    Project.nombre_lugar.ilike(search_pattern),
                    Project.contacto_lugar.ilike(search_pattern),
                    Project.telefono_lugar.ilike(search_pattern),
                    Project.tipo_terreno.ilike(search_pattern),
                    Project.mas_tipo_terreno.ilike(search_pattern),
                    Project.nombres_acompanantes.ilike(search_pattern),
                    Project.recomendaciones.ilike(search_pattern),
                    Project.notas_adicionales.ilike(search_pattern)
                )
            )
        
        all_projects = query.all()
        
        # Calcular presupuesto restante para cada proyecto
        for project in all_projects:
            project.presupuesto_restante = (project.presupuesto_total or 0) - \
                                           (project.costo_entrada or 0) - \
                                           (project.costo_guia or 0) - \
                                           (project.costo_transporte or 0)
        
        return render_template('ver_proyectos.html', projects=all_projects, search_query=search_query)
    except Exception as e:
        flash(f'Error al cargar los proyectos: {e}', 'danger')
        return redirect(url_for('home'))

@proyecto_bp.route('/crear_proyecto', methods=['GET', 'POST'])
def crear_proyecto():
    """
    Muestra y procesa el formulario para crear un nuevo proyecto.
    Requiere que el usuario esté logueado.
    """
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para crear proyectos.', 'info')
        return redirect(url_for('login'))

    # Opciones para los campos de selección
    propuesta_por_opciones = ["Jenny Ceciliano Cordoba", "Kenneth Ruiz Matamoros", "Otro"]
    # Cargar todos los contactos (usuarios) para la selección de invitados
    contactos_opciones = User.query.with_entities(User.id, User.nombre, User.primer_apellido, User.segundo_apellido).all()
    provincia_opciones = ["No Aplica", "Cartago", "Limón", "Alajuela", "Puntarenas", "Heredia", "Guanacaste", "San José"]
    dificultad_opciones = ["No Aplica", "Iniciante", "Básico", "Intermedio", "Avanzado", "Técnico"]
    transporte_terrestre_opciones = ["No Aplica", "Autobús", "Buseta", "Auto", "Moto", "4x4"]
    si_no_aplica_opciones = ["No Aplica", "Si"] # Para Acuatico, Aereo, Precio Entrada
    tipo_terreno_opciones = ["No Aplica", "Asfalto", "Acuatico", "Lastre", "Arena", "Montañoso"]

    if request.method == 'POST':
        try:
            nombre_proyecto = request.form['nombre_proyecto']
            propuesta_por = request.form['propuesta_por']
            nombre_invitado_id = request.form.get('nombre_invitado') # Puede ser None si "No Aplica" o similar
            
            provincia = request.form.get('provincia')
            fecha_actividad_propuesta_str = request.form.get('fecha_actividad_propuesta')
            dificultad = request.form.get('dificultad')
            transporte_terrestre = request.form.get('transporte_terrestre')
            transporte_acuatico = request.form.get('transporte_acuatico')
            transporte_aereo = request.form.get('transporte_aereo')
            precio_entrada_aplica = request.form.get('precio_entrada_aplica')
            nombre_lugar = request.form.get('nombre_lugar')
            contacto_lugar = request.form.get('contacto_lugar')
            telefono_lugar = request.form.get('telefono_lugar')
            tipo_terreno = request.form.get('tipo_terreno')
            mas_tipo_terreno = request.form.get('mas_tipo_terreno')
            
            # Convertir valores de presupuesto a float, manejar None si están vacíos
            presupuesto_total = float(request.form['presupuesto_total']) if request.form['presupuesto_total'] else 0.0
            costo_entrada = float(request.form['costo_entrada']) if request.form['costo_entrada'] else 0.0
            costo_guia = float(request.form['costo_guia']) if request.form['costo_guia'] else 0.0
            costo_transporte = float(request.form['costo_transporte']) if request.form['costo_transporte'] else 0.0
            
            nombres_acompanantes = request.form.get('nombres_acompanantes')
            recomendaciones = request.form.get('recomendaciones')
            notas_adicionales = request.form.get('notas_adicionales')

            fecha_actividad_propuesta = None
            if fecha_actividad_propuesta_str:
                try:
                    fecha_actividad_propuesta = datetime.strptime(fecha_actividad_propuesta_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de fecha de actividad propuesta inválido.', 'danger')
                    return render_template('crear_proyecto.html', **locals()) # Pasa todas las variables locales

            # Manejo de la imagen del proyecto
            imagen_proyecto_url = None
            if 'imagen_proyecto' in request.files:
                file = request.files['imagen_proyecto']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{nombre_proyecto}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                    # Asegúrate de que la carpeta exista
                    upload_folder = os.path.join(current_app.root_path, 'static', PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE)
                    os.makedirs(upload_folder, exist_ok=True)
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    imagen_proyecto_url = os.path.join(PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE, filename).replace('\\', '/')
            
            new_project = Project(
                nombre_proyecto=nombre_proyecto,
                imagen_proyecto_url=imagen_proyecto_url,
                propuesta_por=propuesta_por if propuesta_por != "Otro" else request.form.get('otro_propuesta_por_texto'),
                nombre_invitado_id=nombre_invitado_id if nombre_invitado_id else None,
                provincia=provincia if provincia != "No Aplica" else None,
                fecha_actividad_propuesta=fecha_actividad_propuesta,
                dificultad=dificultad if dificultad != "No Aplica" else None,
                transporte_terrestre=transporte_terrestre if transporte_terrestre != "No Aplica" else None,
                transporte_acuatico=transporte_acuatico if transporte_acuatico != "No Aplica" else None,
                transporte_aereo=transporte_aereo if transporte_aereo != "No Aplica" else None,
                precio_entrada_aplica=precio_entrada_aplica if precio_entrada_aplica != "No Aplica" else None,
                nombre_lugar=nombre_lugar,
                contacto_lugar=contacto_lugar,
                telefono_lugar=telefono_lugar,
                tipo_terreno=tipo_terreno if tipo_terreno != "No Aplica" else None,
                mas_tipo_terreno=mas_tipo_terreno,
                presupuesto_total=presupuesto_total,
                costo_entrada=costo_entrada,
                costo_guia=costo_guia,
                costo_transporte=costo_transporte,
                nombres_acompanantes=nombres_acompanantes,
                recomendaciones=recomendaciones,
                notas_adicionales=notas_adicionales
            )

            db.session.add(new_project)
            db.session.commit()
            flash('¡Proyecto creado exitosamente!', 'success')
            return redirect(url_for('proyecto.ver_proyectos'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el proyecto: {e}', 'danger')
            return render_template('crear_proyecto.html', **locals()) # Pasa todas las variables locales

    return render_template('crear_proyecto.html', 
                           propuesta_por_opciones=propuesta_por_opciones,
                           contactos_opciones=contactos_opciones,
                           provincia_opciones=provincia_opciones,
                           dificultad_opciones=dificultad_opciones,
                           transporte_terrestre_opciones=transporte_terrestre_opciones,
                           si_no_aplica_opciones=si_no_aplica_opciones,
                           tipo_terreno_opciones=tipo_terreno_opciones)

@proyecto_bp.route('/detalle_proyecto/<int:project_id>')
def detalle_proyecto(project_id):
    """
    Muestra los detalles completos de un proyecto específico.
    Requiere que el usuario esté logueado.
    """
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para acceder a esta página.', 'info')
        return redirect(url_for('login'))

    project = Project.query.get_or_404(project_id)

    # Calcular presupuesto restante para este proyecto
    project.presupuesto_restante = (project.presupuesto_total or 0) - \
                                   (project.costo_entrada or 0) - \
                                   (project.costo_guia or 0) - \
                                   (project.costo_transporte or 0)

    # Si hay una imagen del proyecto, construimos la URL estática
    imagen_proyecto_url = None
    if project.imagen_proyecto_url:
        with current_app.app_context():
            imagen_proyecto_url = url_for('static', filename=project.imagen_proyecto_url)
    
    return render_template('detalle_proyecto.html', project=project, imagen_proyecto_url=imagen_proyecto_url)

@proyecto_bp.route('/editar_proyecto/<int:project_id>', methods=['GET', 'POST'])
def editar_proyecto(project_id):
    """
    Muestra y procesa el formulario para editar un proyecto.
    Requiere que el usuario esté logueado.
    """
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para editar proyectos.', 'info')
        return redirect(url_for('login'))

    project = Project.query.get_or_404(project_id)

    # Opciones para los campos de selección (igual que en crear_proyecto)
    propuesta_por_opciones = ["Jenny Ceciliano Cordoba", "Kenneth Ruiz Matamoros", "Otro"]
    contactos_opciones = User.query.with_entities(User.id, User.nombre, User.primer_apellido, User.segundo_apellido).all()
    provincia_opciones = ["No Aplica", "Cartago", "Limón", "Alajuela", "Puntarenas", "Heredia", "Guanacaste", "San José"]
    dificultad_opciones = ["No Aplica", "Iniciante", "Básico", "Intermedio", "Avanzado", "Técnico"]
    transporte_terrestre_opciones = ["No Aplica", "Autobús", "Buseta", "Auto", "Moto", "4x4"]
    si_no_aplica_opciones = ["No Aplica", "Si"]
    tipo_terreno_opciones = ["No Aplica", "Asfalto", "Acuatico", "Lastre", "Arena", "Montañoso"]

    if request.method == 'POST':
        try:
            project.nombre_proyecto = request.form['nombre_proyecto']
            
            propuesta_por_form = request.form['propuesta_por']
            if propuesta_por_form == "Otro":
                project.propuesta_por = request.form.get('otro_propuesta_por_texto')
            else:
                project.propuesta_por = propuesta_por_form

            nombre_invitado_id = request.form.get('nombre_invitado')
            project.nombre_invitado_id = nombre_invitado_id if nombre_invitado_id else None # Actualizar ID de invitado

            project.provincia = request.form.get('provincia') if request.form.get('provincia') != "No Aplica" else None
            
            fecha_actividad_propuesta_str = request.form.get('fecha_actividad_propuesta')
            if fecha_actividad_propuesta_str:
                project.fecha_actividad_propuesta = datetime.strptime(fecha_actividad_propuesta_str, '%Y-%m-%d').date()
            else:
                project.fecha_actividad_propuesta = None

            project.dificultad = request.form.get('dificultad') if request.form.get('dificultad') != "No Aplica" else None
            project.transporte_terrestre = request.form.get('transporte_terrestre') if request.form.get('transporte_terrestre') != "No Aplica" else None
            project.transporte_acuatico = request.form.get('transporte_acuatico') if request.form.get('transporte_acuatico') != "No Aplica" else None
            project.transporte_aereo = request.form.get('transporte_aereo') if request.form.get('transporte_aereo') != "No Aplica" else None
            project.precio_entrada_aplica = request.form.get('precio_entrada_aplica') if request.form.get('precio_entrada_aplica') != "No Aplica" else None
            
            project.nombre_lugar = request.form.get('nombre_lugar')
            project.contacto_lugar = request.form.get('contacto_lugar')
            project.telefono_lugar = request.form.get('telefono_lugar')
            project.tipo_terreno = request.form.get('tipo_terreno') if request.form.get('tipo_terreno') != "No Aplica" else None
            project.mas_tipo_terreno = request.form.get('mas_tipo_terreno')

            project.presupuesto_total = float(request.form['presupuesto_total']) if request.form['presupuesto_total'] else 0.0
            project.costo_entrada = float(request.form['costo_entrada']) if request.form['costo_entrada'] else 0.0
            project.costo_guia = float(request.form['costo_guia']) if request.form['costo_guia'] else 0.0
            project.costo_transporte = float(request.form['costo_transporte']) if request.form['costo_transporte'] else 0.0

            project.nombres_acompanantes = request.form.get('nombres_acompanantes')
            project.recomendaciones = request.form.get('recomendaciones')
            project.notas_adicionales = request.form.get('notas_adicionales')

            # Manejo de la imagen del proyecto
            if 'imagen_proyecto' in request.files:
                file = request.files['imagen_proyecto']
                if file.filename != '' and allowed_file(file.filename):
                    # Eliminar la imagen anterior si existe y no es la por defecto (aunque no tenemos una por defecto para proyectos)
                    if project.imagen_proyecto_url:
                        old_image_filename = os.path.basename(project.imagen_proyecto_url)
                        upload_folder = os.path.join(current_app.root_path, 'static', PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE)
                        old_image_path = os.path.join(upload_folder, old_image_filename)
                        
                        if os.path.exists(old_image_path):
                            os.unlink(old_image_path)
                    
                    filename = secure_filename(f"{project.nombre_proyecto}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                    upload_folder = os.path.join(current_app.root_path, 'static', PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE)
                    os.makedirs(upload_folder, exist_ok=True) # Asegurarse de que la carpeta exista
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    project.imagen_proyecto_url = os.path.join(PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE, filename).replace('\\', '/')
                elif file.filename == '' and request.form.get('clear_image_proyecto'): # Si se marca la casilla para borrar
                    if project.imagen_proyecto_url:
                        old_image_filename = os.path.basename(project.imagen_proyecto_url)
                        upload_folder = os.path.join(current_app.root_path, 'static', PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE)
                        old_image_path = os.path.join(upload_folder, old_image_filename)
                        if os.path.exists(old_image_path):
                            os.unlink(old_image_path)
                        project.imagen_proyecto_url = None # Borrar la URL de la DB

            project.fecha_ultima_actualizacion = datetime.utcnow()

            db.session.commit()
            flash('¡Proyecto actualizado exitosamente!', 'success')
            return redirect(url_for('proyecto.detalle_proyecto', project_id=project.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el proyecto: {e}', 'danger')
            return render_template('editar_proyecto.html', project=project, 
                                   propuesta_por_opciones=propuesta_por_opciones,
                                   contactos_opciones=contactos_opciones,
                                   provincia_opciones=provincia_opciones,
                                   dificultad_opciones=dificultad_opciones,
                                   transporte_terrestre_opciones=transporte_terrestre_opciones,
                                   si_no_aplica_opciones=si_no_aplica_opciones,
                                   tipo_terreno_opciones=tipo_terreno_opciones)

    # Si es GET request
    imagen_proyecto_url = None
    if project.imagen_proyecto_url:
        with current_app.app_context():
            imagen_proyecto_url = url_for('static', filename=project.imagen_proyecto_url)

    # Determinar si el campo propuesta_por es "Otro" para mostrar el input de texto
    is_propuesta_por_otro = project.propuesta_por not in propuesta_por_opciones

    return render_template('editar_proyecto.html', project=project, imagen_proyecto_url=imagen_proyecto_url,
                           propuesta_por_opciones=propuesta_por_opciones,
                           contactos_opciones=contactos_opciones,
                           provincia_opciones=provincia_opciones,
                           dificultad_opciones=dificultad_opciones,
                           transporte_terrestre_opciones=transporte_terrestre_opciones,
                           si_no_aplica_opciones=si_no_aplica_opciones,
                           tipo_terreno_opciones=tipo_terreno_opciones,
                           is_propuesta_por_otro=is_propuesta_por_otro)

@proyecto_bp.route('/eliminar_proyecto/<int:project_id>', methods=['POST'])
def eliminar_proyecto(project_id):
    """
    Elimina un proyecto de la base de datos.
    Requiere método POST y que el usuario esté logueado.
    """
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para realizar esta acción.', 'info')
        return redirect(url_for('login'))

    project_to_delete = Project.query.get_or_404(project_id)

    try:
        # Eliminar el archivo de imagen del proyecto si existe
        if project_to_delete.imagen_proyecto_url:
            upload_folder = os.path.join(current_app.root_path, 'static', PROJECT_IMAGE_UPLOAD_FOLDER_RELATIVE)
            file_path = os.path.join(upload_folder, os.path.basename(project_to_delete.imagen_proyecto_url))
            if os.path.exists(file_path):
                os.unlink(file_path)

        db.session.delete(project_to_delete)
        db.session.commit()
        flash(f'El proyecto "{project_to_delete.nombre_proyecto}" ha sido eliminado exitosamente.', 'success')
        return redirect(url_for('proyecto.ver_proyectos'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el proyecto: {e}', 'danger')
        return redirect(url_for('proyecto.detalle_proyecto', project_id=project_id))


# --- Rutas de Exportación para Proyectos ---

@proyecto_bp.route('/exportar_txt/<int:project_id>')
def exportar_txt(project_id):
    """
    Exporta los detalles de un proyecto individual a un archivo de texto (.txt).
    """
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para exportar proyectos.', 'info')
        return redirect(url_for('login'))

    project = Project.query.get_or_404(project_id)

    # Calcular presupuesto restante
    presupuesto_restante = (project.presupuesto_total or 0) - \
                           (project.costo_entrada or 0) - \
                           (project.costo_guia or 0) - \
                           (project.costo_transporte or 0)

    content = f"""
Detalles del Proyecto: {project.nombre_proyecto}

Propuesto por: {project.propuesta_por or 'N/A'}
Invitado: {project.nombre_invitado.nombre if project.nombre_invitado else 'N/A'} {project.nombre_invitado.primer_apellido if project.nombre_invitado else ''} {project.nombre_invitado.segundo_apellido if project.nombre_invitado and project.nombre_invitado.segundo_apellido else ''} (ID: {project.nombre_invitado.id if project.nombre_invitado else 'N/A'})
Provincia: {project.provincia or 'N/A'}
Fecha de Actividad Propuesta: {project.fecha_actividad_propuesta.strftime('%d/%m/%Y') if project.fecha_actividad_propuesta else 'N/A'}
Dificultad: {project.dificultad or 'N/A'}

Transporte Terrestre: {project.transporte_terrestre or 'N/A'}
Transporte Acuático: {project.transporte_acuatico or 'No'}
Transporte Aéreo: {project.transporte_aereo or 'No'}
Precio Entrada Aplica: {project.precio_entrada_aplica or 'No'}

Información del Lugar:
  Nombre del Lugar: {project.nombre_lugar or 'N/A'}
  Contacto del Lugar: {project.contacto_lugar or 'N/A'}
  Teléfono del Lugar: {project.telefono_lugar or 'N/A'}

Tipo de Terreno: {project.tipo_terreno or 'N/A'}
Más Tipo de Terreno: {project.mas_tipo_terreno or 'N/A'}

Costos:
  Presupuesto Total: ¢{project.presupuesto_total:.2f}
  Costo de Entrada: ¢{project.costo_entrada:.2f}
  Costo de Guía: ¢{project.costo_guia:.2f}
  Costo de Transporte: ¢{project.costo_transporte:.2f}
  Presupuesto Restante: ¢{presupuesto_restante:.2f}

Nombres de Acompañantes: {project.nombres_acompanantes or 'N/A'}
Recomendaciones: {project.recomendaciones or 'N/A'}
Notas Adicionales: {project.notas_adicionales or 'N/A'}

Fecha de Creación: {project.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')}
Última Actualización: {project.fecha_ultima_actualizacion.strftime('%d/%m/%Y %H:%M:%S') if project.fecha_ultima_actualizacion else 'N/A'}
"""
    buffer = io.BytesIO(content.encode('utf-8'))

    return send_file(
        buffer,
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'{project.nombre_proyecto}.txt'
    )

@proyecto_bp.route('/exportar_proyecto_pdf/<int:project_id>')
# Puedes añadir un decorador de rol si quieres restringir el acceso:
# @role_required(['Superuser', 'Administrador'])
def exportar_proyecto_pdf(project_id):
    project = Project.query.get_or_404(project_id)

    # Calcular presupuesto restante
    presupuesto_restante = (project.presupuesto_total or 0) - \
                           (project.costo_entrada or 0) - \
                           (project.costo_guia or 0) - \
                           (project.costo_transporte or 0)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Detalle del Proyecto: {project.nombre_proyecto}", ln=True, align="C")
    pdf.ln(10) # Salto de línea

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 7, txt="Información General:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, txt=f"Nombre: {project.nombre_proyecto}")
    pdf.multi_cell(0, 6, txt=f"Propuesto por: {project.propuesta_por if project.propuesta_por else 'N/A'}")
    # Asegúrate de que project.nombre_invitado sea un objeto User válido antes de acceder a sus atributos
    invitado_nombre = f"{project.nombre_invitado.nombre} {project.nombre_invitado.primer_apellido} {project.nombre_invitado.segundo_apellido if project.nombre_invitado.segundo_apellido else ''}" if project.nombre_invitado else 'N/A'
    pdf.multi_cell(0, 6, txt=f"Invitado: {invitado_nombre}")
    pdf.multi_cell(0, 6, txt=f"Provincia: {project.provincia if project.provincia else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Fecha Actividad Propuesta: {project.fecha_actividad_propuesta.strftime('%d/%m/%Y') if project.fecha_actividad_propuesta else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Dificultad: {project.dificultad if project.dificultad else 'N/A'}")
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 7, txt="Detalles de Transporte y Costos:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, txt=f"Transporte Terrestre: {project.transporte_terrestre if project.transporte_terrestre else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Transporte Acuático: {project.transporte_acuatico if project.transporte_acuatico else 'No Aplica'}")
    pdf.multi_cell(0, 6, txt=f"Transporte Aéreo: {project.transporte_aereo if project.transporte_aereo else 'No Aplica'}")
    pdf.multi_cell(0, 6, txt=f"Precio Entrada Aplica: {project.precio_entrada_aplica if project.precio_entrada_aplica else 'No Aplica'}")
    pdf.multi_cell(0, 6, txt=f"Presupuesto Total: ¢{project.presupuesto_total if project.presupuesto_total is not None else 0:,.0f}")
    pdf.multi_cell(0, 6, txt=f"Costo de Entrada: ¢{project.costo_entrada if project.costo_entrada is not None else 0:,.0f}")
    pdf.multi_cell(0, 6, txt=f"Costo de Guía: ¢{project.costo_guia if project.costo_guia is not None else 0:,.0f}")
    pdf.multi_cell(0, 6, txt=f"Costo de Transporte: ¢{project.costo_transporte if project.costo_transporte is not None else 0:,.0f}")
    pdf.multi_cell(0, 6, txt=f"Presupuesto Restante: ¢{presupuesto_restante:,.0f}") # Usar la variable calculada
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 7, txt="Información del Lugar y Terreno:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, txt=f"Nombre del Lugar: {project.nombre_lugar if project.nombre_lugar else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Contacto del Lugar: {project.contacto_lugar if project.contacto_lugar else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Teléfono del Lugar: {project.telefono_lugar if project.telefono_lugar else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Tipo de Terreno: {project.tipo_terreno if project.tipo_terreno else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Más Detalles del Tipo de Terreno: {project.mas_tipo_terreno if project.mas_tipo_terreno else 'N/A'}")
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 7, txt="Detalles Adicionales:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, txt=f"Nombres de Acompañantes: {project.nombres_acompanantes if project.nombres_acompanantes else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Recomendaciones: {project.recomendaciones if project.recomendaciones else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Notas Adicionales: {project.notas_adicionales if project.notas_adicionales else 'N/A'}")
    pdf.multi_cell(0, 6, txt=f"Fecha de Creación: {project.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')}")
    pdf.multi_cell(0, 6, txt=f"Última Actualización: {project.fecha_ultima_actualizacion.strftime('%d/%m/%Y %H:%M:%S') if project.fecha_ultima_actualizacion else 'N/A'}")
    pdf.ln(5)

    response = Response(pdf.output(dest='S').encode('latin1'), mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename=detalle_proyecto_{project.nombre_proyecto}.pdf'
    return response

@proyecto_bp.route('/exportar_proyecto_jpg/<int:project_id>')
# Puedes añadir un decorador de rol si quieres restringir el acceso:
# @role_required(['Superuser', 'Administrador'])
def exportar_proyecto_jpg(project_id):
    project = Project.query.get_or_404(project_id)

    # Calcular presupuesto restante
    presupuesto_restante = (project.presupuesto_total or 0) - \
                           (project.costo_entrada or 0) - \
                           (project.costo_guia or 0) - \
                           (project.costo_transporte or 0)

    # Crear el texto para la imagen
    text_content = f"""
Detalle del Proyecto: {project.nombre_proyecto}

Información General:
  Nombre: {project.nombre_proyecto}
  Propuesto por: {project.propuesta_por if project.propuesta_por else 'N/A'}
  Invitado: {project.nombre_invitado.nombre if project.nombre_invitado else 'N/A'} {project.nombre_invitado.primer_apellido if project.nombre_invitado else ''}
  Provincia: {project.provincia if project.provincia else 'N/A'}
  Fecha Actividad Propuesta: {project.fecha_actividad_propuesta.strftime('%d/%m/%Y') if project.fecha_actividad_propuesta else 'N/A'}
  Dificultad: {project.dificultad if project.dificultad else 'N/A'}

Detalles de Transporte y Costos:
  Transporte Terrestre: {project.transporte_terrestre if project.transporte_terrestre else 'N/A'}
  Transporte Acuático: {project.transporte_acuatico if project.transporte_acuatico else 'No Aplica'}
  Transporte Aéreo: {project.transporte_aereo if project.transporte_aereo else 'No Aplica'}
  Precio Entrada Aplica: {project.precio_entrada_aplica if project.precio_entrada_aplica else 'No Aplica'}
  Presupuesto Total: ¢{project.presupuesto_total if project.presupuesto_total is not None else 0:,.0f}
  Costo de Entrada: ¢{project.costo_entrada if project.costo_entrada is not None else 0:,.0f}
  Costo de Guía: ¢{project.costo_guia if project.costo_guia is not None else 0:,.0f}
  Costo de Transporte: ¢{project.costo_transporte if project.costo_transporte is not None else 0:,.0f}
  Presupuesto Restante: ¢{presupuesto_restante:,.0f}

Información del Lugar y Terreno:
  Nombre del Lugar: {project.nombre_lugar if project.nombre_lugar else 'N/A'}
  Contacto del Lugar: {project.contacto_lugar if project.contacto_lugar else 'N/A'}
  Teléfono del Lugar: {project.telefono_lugar if project.telefono_lugar else 'N/A'}
  Tipo de Terreno: {project.tipo_terreno if project.tipo_terreno else 'N/A'}
  Más Detalles del Tipo de Terreno: {project.mas_tipo_terreno if project.mas_tipo_terreno else 'N/A'}

Detalles Adicionales:
  Nombres de Acompañantes: {project.nombres_acompanantes if project.nombres_acompanantes else 'N/A'}
  Recomendaciones: {project.recomendaciones if project.recomendaciones else 'N/A'}
  Notas Adicionales: {project.notas_adicionales if project.notas_adicionales else 'N/A'}
  Fecha de Creación: {project.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')}
  Última Actualización: {project.fecha_ultima_actualizacion.strftime('%d/%m/%Y %H:%M:%S') if project.fecha_ultima_actualizacion else 'N/A'}
"""
    # Eliminar saltos de línea extra al inicio y final
    text_content = text_content.strip()

    # Define la fuente y el tamaño
    try:
        # Asegúrate de que esta ruta sea correcta en tu proyecto
        font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'arial.ttf')
        font = ImageFont.truetype(font_path, 18)
        font_bold = ImageFont.truetype(font_path, 18) # Puedes usar otra fuente para negrita si tienes
    except IOError:
        font = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        print("Advertencia: No se encontró la fuente 'arial.ttf'. Usando la fuente por defecto.")

    # Calcular el tamaño de la imagen necesario
    lines = text_content.split('\n')
    line_height = 25 # Altura aproximada por línea
    padding = 30
    img_width = 800
    img_height = len(lines) * line_height + (2 * padding)

    img = Image.new('RGB', (img_width, img_height), color='white')
    d = ImageDraw.Draw(img)

    y_offset = padding
    for line in lines:
        current_font = font
        if line.startswith("Detalle del Proyecto:") or \
           line.startswith("Información General:") or \
           line.startswith("Detalles de Transporte y Costos:") or \
           line.startswith("Información del Lugar y Terreno:") or \
           line.startswith("Detalles Adicionales:"):
            current_font = font_bold

        d.text((padding, y_offset), line, fill=(0, 0, 0), font=current_font)
        y_offset += line_height

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)

    return send_file(buffer, mimetype='image/jpeg', as_attachment=True, download_name=f'detalle_proyecto_{project.nombre_proyecto}.jpg')


# Función para exportar TODOS los proyectos a TXT
@proyecto_bp.route('/exportar_todos_txt')
def exportar_todos_txt():
    """
    Exporta los detalles de TODOS los proyectos a un único archivo de texto (.txt).
    """
    if 'logged_in' not in session or not session['logged_in']:
        flash('Por favor, inicia sesión para exportar todos los proyectos.', 'info')
        return redirect(url_for('login'))

    all_projects = Project.query.all()
    full_content = []

    for project in all_projects:
        presupuesto_restante = (project.presupuesto_total or 0) - \
                               (project.costo_entrada or 0) - \
                               (project.costo_guia or 0) - \
                               (project.costo_transporte or 0)
        
        full_content.append(f"""
--- Proyecto: {project.nombre_proyecto} ---
ID: {project.id}
Propuesto por: {project.propuesta_por or 'N/A'}
Invitado: {project.nombre_invitado.nombre if project.nombre_invitado else 'N/A'} {project.nombre_invitado.primer_apellido if project.nombre_invitado else ''} {project.nombre_invitado.segundo_apellido if project.nombre_invitado and project.nombre_invitado.segundo_apellido else ''} (ID: {project.nombre_invitado.id if project.nombre_invitado else 'N/A'})
Provincia: {project.provincia or 'N/A'}
Fecha de Actividad Propuesta: {project.fecha_actividad_propuesta.strftime('%d/%m/%Y') if project.fecha_actividad_propuesta else 'N/A'}
Dificultad: {project.dificultad or 'N/A'}
Transporte Terrestre: {project.transporte_terrestre or 'N/A'}
Transporte Acuático: {project.transporte_acuatico or 'No'}
Transporte Aéreo: {project.transporte_aereo or 'No'}
Precio Entrada Aplica: {project.precio_entrada_aplica or 'No'}
Nombre del Lugar: {project.nombre_lugar or 'N/A'}
Contacto del Lugar: {project.contacto_lugar or 'N/A'}
Teléfono del Lugar: {project.telefono_lugar or 'N/A'}
Tipo de Terreno: {project.tipo_terreno or 'N/A'}
Más Tipo de Terreno: {project.mas_tipo_terreno or 'N/A'}
Presupuesto Total: ¢{project.presupuesto_total:.2f}
Costo de Entrada: ¢{project.costo_entrada:.2f}
Costo de Guía: ¢{project.costo_guia:.2f}
Costo de Transporte: ¢{project.costo_transporte:.2f}
Presupuesto Restante: ¢{presupuesto_restante:.2f}
Nombres de Acompañantes: {project.nombres_acompanantes or 'N/A'}
Recomendaciones: {project.recomendaciones or 'N/A'}
Notas Adicionales: {project.notas_adicionales or 'N/A'}
Fecha de Creación: {project.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')}
Última Actualización: {project.fecha_ultima_actualizacion.strftime('%d/%m/%Y %H:%M:%S') if project.fecha_ultima_actualizacion else 'N/A'}
--------------------------------------------------
""")
    
    final_content = "\n".join(full_content)
    buffer = io.BytesIO(final_content.encode('utf-8'))

    return send_file(
        buffer,
        mimetype='text/plain',
        as_attachment=True,
        download_name='todos_los_proyectos.txt'
    )
