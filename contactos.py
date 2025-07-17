# Modified contactos.py
from flask import Blueprint, render_template, session, redirect, url_for, flash, current_app, request, send_file
from models import db, User 
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import io
from sqlalchemy import or_ 
from functools import wraps 

# Librerías para exportación
import vobject
import openpyxl

AVATAR_UPLOAD_FOLDER_RELATIVE = os.path.join('uploads', 'avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """
    Verifica si la extensión del archivo está permitida.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Creamos un Blueprint para organizar las rutas relacionadas con contactos
contactos_bp = Blueprint('contactos', __name__, url_prefix='/contactos')

# DECORADOR PARA ROLES
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


@contactos_bp.route('/ver_contactos')
@role_required(['Superuser', 'Administrador', 'Usuario Regular']) # Todos pueden ver contactos
def ver_contactos():
    """
    Muestra una lista de todos los usuarios registrados, con funcionalidad de búsqueda.
    Requiere que el usuario esté logueado.
    """
    search_query = request.args.get('search_query', '').strip() # Obtener el término de búsqueda

    try:
        query = User.query
        
        if search_query:
            # Construir la condición de búsqueda para cada campo relevante
            search_pattern = f"%{search_query}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_pattern),
                    User.nombre.ilike(search_pattern),
                    User.primer_apellido.ilike(search_pattern),
                    User.segundo_apellido.ilike(search_pattern),
                    User.telefono.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.telefono_emergencia.ilike(search_pattern),
                    User.nombre_emergencia.ilike(search_pattern),
                    User.empresa.ilike(search_pattern),
                    User.cedula.ilike(search_pattern),
                    User.direccion.ilike(search_pattern),
                    User.actividad.ilike(search_pattern),
                    User.capacidad.ilike(search_pattern),
                    User.participacion.ilike(search_pattern),
                    # NUEVOS CAMPOS EN BÚSQUEDA
                    User.tipo_sangre.ilike(search_pattern),
                    User.poliza.ilike(search_pattern),
                    User.aseguradora.ilike(search_pattern),
                    User.alergias.ilike(search_pattern),
                    User.enfermedades_cronicas.ilike(search_pattern)
                )
            )
        
        all_users = query.all() # Ejecutar la consulta (con o sin filtro)
        return render_template('ver_contactos.html', users=all_users, search_query=search_query, current_role=session.get('role'))
    except Exception as e:
        flash(f'Error al cargar los contactos: {e}', 'danger')
        return redirect(url_for('home'))

@contactos_bp.route('/ver_detalle/<int:user_id>')
@role_required(['Superuser', 'Administrador', 'Usuario Regular']) # Todos pueden ver el detalle
def ver_detalle(user_id):
    """
    Muestra los detalles completos de un contacto específico.
    Requiere que el usuario esté logueado.
    """
    user = User.query.get_or_404(user_id) # Busca el usuario por ID, o devuelve 404 si no lo encuentra

    # Si hay un avatar_url, construimos la URL estática
    avatar_url = None
    if user.avatar_url:
        with current_app.app_context(): # Necesario para url_for en un blueprint
            avatar_url = url_for('static', filename=user.avatar_url)
    else:
        with current_app.app_context():
            avatar_url = url_for('static', filename='images/defaults/default_avatar.png')

    return render_template('detalle_contactos.html', user=user, avatar_url=avatar_url, current_role=session.get('role'))


@contactos_bp.route('/eliminar_contacto/<int:user_id>', methods=['POST'])
@role_required('Superuser') # Solo Superusers pueden eliminar
def eliminar_contacto(user_id):
    """
    Elimina un contacto de la base de datos.
    Requiere método POST y que el usuario sea Superuser.
    """
    user_to_delete = User.query.get_or_404(user_id)

    # Evitar que un Superuser se elimine a sí mismo accidentalmente o el último Superuser
    if session.get('user_id') == user_to_delete.id:
        flash('No puedes eliminar tu propia cuenta mientras estás logueado.', 'danger')
        return redirect(url_for('contactos.ver_detalle', user_id=user_id))

    # Verificar si es el último Superuser
    if user_to_delete.role == 'Superuser':
        superuser_count = User.query.filter_by(role='Superuser').count()
        if superuser_count <= 1: # Si solo queda 1 Superuser (el que se intenta eliminar)
            flash('No se puede eliminar el último Superuser. Debe haber al menos un Superuser en el sistema.', 'danger')
            return redirect(url_for('contactos.ver_detalle', user_id=user_id))


    try:
        # Opcional: Eliminar el archivo de avatar si no es el por defecto
        if user_to_delete.avatar_url and 'default_avatar.png' not in user_to_delete.avatar_url:
            file_path_check_1 = os.path.join(current_app.root_path, 'static', user_to_delete.avatar_url)
            file_path_check_2 = os.path.join(current_app.root_path, user_to_delete.avatar_url)

            if os.path.exists(file_path_check_1):
                os.unlink(file_path_check_1)
            elif os.path.exists(file_path_check_2):
                os.unlink(file_path_check_2)
            # else: archivo no encontrado o ya eliminado, no hay problema
                

        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f'El usuario "{user_to_delete.username}" ha sido eliminado exitosamente.', 'success')
        return redirect(url_for('contactos.ver_contactos')) # Redirige a la lista de contactos
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el usuario: {e}', 'danger')
        return redirect(url_for('contactos.ver_detalle', user_id=user_id))


@contactos_bp.route('/editar_contacto/<int:user_id>', methods=['GET', 'POST'])
@role_required(['Superuser', 'Administrador', 'Usuario Regular']) # MODIFICACIÓN: Permitir a Usuario Regular acceder
def editar_contacto(user_id):
    """
    Muestra y procesa el formulario para editar un contacto.
    Requiere que el usuario sea Superuser, Administrador o un Usuario Regular editando su propio perfil.
    """
    user = User.query.get_or_404(user_id)

    logged_in_user_role = session.get('role')
    logged_in_user_id = session.get('user_id')

    # MODIFICACIÓN: Si es un usuario regular, solo puede editar su propio perfil
    if logged_in_user_role == 'Usuario Regular' and str(logged_in_user_id) != str(user_id):
        flash('No tienes permiso para editar el perfil de otro usuario.', 'danger')
        return redirect(url_for('perfil.ver_perfil')) # Redirige a la página de perfil del propio usuario

    # DEFINICIÓN DE LAS OPCIONES: Añadidas aquí para que estén disponibles
    actividad_opciones = ["No Aplica", "La Tribu", "Senderista", "Enfermería", "Cocina", "Confección y Diseño", "Restaurante", "Transporte Terrestre", "Transporte Acuatico", "Transporte Aereo", "Migración", "Parque Nacional", "Refugio Silvestre", "Centro de Atracción", "Lugar para Caminata", "Acarreo", "Oficina de trámite", "Primeros Auxilios", "Farmacia", "Taller", "Abogado", "Mensajero", "Tienda", "Polizas", "Aerolínea", "Guía", "Banco", "Otros"]
    capacidad_opciones = ["Seleccionar Capacidad", "Rápido", "Intermedio", "Básico", "Iniciante"]
    participacion_opciones = ["No Aplica", "Solo de La Tribu", "Constante", "Inconstante", "El Camino de Costa Rica", "Parques Nacionales", "Paseo | Recreativo", "Revisar/Eliminar"]
    tipo_sangre_opciones = ["Seleccionar Tipo", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    # Lista de provincias de Costa Rica en el orden solicitado
    provincia_opciones = ["Cartago", "Limón", "Puntarenas", "San José", "Heredia", "Guanacaste", "Alajuela"]
    # OPCIONES DE ROL para el SELECT de roles (solo si el usuario logueado es Superuser)
    role_opciones = ['Usuario Regular', 'Administrador', 'Superuser'];


    if request.method == 'POST':
        try:
            # Actualizar campos obligatorios
            user.nombre = request.form['nombre']
            user.primer_apellido = request.form['primer_apellido']
            user.telefono = request.form['telefono']
            
            # Solo permitir cambiar el username si el usuario logueado es Superuser o si es el propio usuario
            # Y si el username no es el del usuario actual, verificar unicidad
            new_username = request.form['username']
            if new_username != user.username:
                existing_username_user = User.query.filter_by(username=new_username).first()
                if existing_username_user and existing_username_user.id != user.id:
                    flash('El nombre de usuario ya está en uso. Por favor, elige otro.', 'danger')
                    return render_template('editar_contacto.html', user=user, 
                                           actividad_opciones=actividad_opciones, 
                                           capacidad_opciones=capacidad_opciones, 
                                           participacion_opciones=participacion_opciones,
                                           tipo_sangre_opciones=tipo_sangre_opciones,
                                           provincia_opciones=provincia_opciones,
                                           logged_in_user_role=logged_in_user_role,
                                           role_opciones=role_opciones) # Pasa las opciones en caso de error
            user.username = new_username

            # Solo permitir cambiar el email si el usuario logueado es Superuser o si es el propio usuario
            # Y si el email no es el del usuario actual, verificar unicidad
            new_email = request.form.get('email')
            if new_email and new_email.lower() != (user.email.lower() if user.email else ''):
                existing_email_user = User.query.filter_by(email=new_email.lower()).first()
                if existing_email_user and existing_email_user.id != user.id:
                    flash('Ese correo electrónico ya está registrado. Por favor, usa otro.', 'danger')
                    return render_template('editar_contacto.html', user=user, 
                                           actividad_opciones=actividad_opciones, 
                                           capacidad_opciones=capacidad_opciones, 
                                           participacion_opciones=participacion_opciones,
                                           tipo_sangre_opciones=tipo_sangre_opciones,
                                           provincia_opciones=provincia_opciones,
                                           logged_in_user_role=logged_in_user_role,
                                           role_opciones=role_opciones) # Pasa las opciones en caso de error
            user.email = new_email.lower() if new_email else None

            # Actualizar campos opcionales
            user.segundo_apellido = request.form.get('segundo_apellido')
            user.telefono_emergencia = request.form.get('telefono_emergencia')
            user.nombre_emergencia = request.form.get('nombre_emergencia')
            user.empresa = request.form.get('empresa')
            user.cedula = request.form.get('cedula')
            # Capturar el valor de la provincia del select
            provincia_seleccionada = request.form.get('direccion')
            user.direccion = provincia_seleccionada if provincia_seleccionada else None # Guardar la provincia seleccionada
            
            # Capturar valores de los select y asignarlos (solo si es Superuser)
            if logged_in_user_role == 'Superuser':
                actividad = request.form.get('actividad')
                user.actividad = actividad if actividad != "No Aplica" else None

                capacidad = request.form.get('capacidad')
                user.capacidad = capacidad if capacidad != "Seleccionar Capacidad" else None

                participacion = request.form.get('participacion')
                user.participacion = participacion if participacion != "No Aplica" else None

            # NUEVOS CAMPOS: Actualizar desde el formulario
            fecha_cumpleanos_str = request.form.get('fecha_cumpleanos')
            if fecha_cumpleanos_str:
                user.fecha_cumpleanos = datetime.strptime(fecha_cumpleanos_str, '%Y-%m-%d').date()
            else:
                user.fecha_cumpleanos = None # Permitir limpiar el campo

            user.tipo_sangre = request.form.get('tipo_sangre')
            if user.tipo_sangre == "Seleccionar Tipo": # Si no se seleccionó un tipo específico
                user.tipo_sangre = None

            user.poliza = request.form.get('poliza')
            user.aseguradora = request.form.get('aseguradora')
            user.alergias = request.form.get('alergias')
            user.enfermedades_cronicas = request.form.get('enfermedades_cronicas')

            # Manejo del avatar - MODIFICACIÓN INICIA AQUÍ
            if 'avatar' in request.files:
                file = request.files['avatar']
                # Solo procesar si un archivo fue realmente seleccionado y es permitido
                if file.filename != '' and allowed_file(file.filename):
                    # Eliminar el avatar anterior si no es el por defecto
                    if user.avatar_url and 'default_avatar.png' not in user.avatar_url:
                        old_avatar_filename = os.path.basename(user.avatar_url)
                        old_avatar_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_avatar_filename)
                        
                        if os.path.exists(old_avatar_path):
                            os.unlink(old_avatar_path)
                    
                    # Guardar el nuevo avatar con un nombre seguro
                    filename = secure_filename(f"{user.username}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                    
                    # Usar la ruta de subida ABSOLUTA definida en app.py para guardar el archivo
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    # Guardar la ruta relativa correcta en la base de datos (relativa a la carpeta 'static')
                    user.avatar_url = os.path.join(AVATAR_UPLOAD_FOLDER_RELATIVE, filename).replace('\\', '/')
                # Si file.filename está vacío (no se seleccionó un nuevo archivo),
                # no hacemos nada con user.avatar_url, así se conserva el valor actual.
                # La lógica que eliminaba el avatar y lo ponía por defecto si file.filename == ''
                # ha sido eliminada para evitar la pérdida accidental del avatar.
            # Manejo del avatar - MODIFICACIÓN TERMINA AQUÍ

            # Manejo del campo de rol (solo si el usuario logueado es Superuser)
            if logged_in_user_role == 'Superuser':
                new_role = request.form.get('role')
                if new_role and new_role in role_opciones:
                    # Lógica para limitar a 2 superusuarios
                    if new_role == 'Superuser' and user.role != 'Superuser':
                        current_superusers = User.query.filter_by(role='Superuser').count()
                        if current_superusers >= 2:
                            flash('No se pueden asignar más de 2 Superusers. Cambia el rol de otro usuario primero.', 'danger')
                            db.session.rollback() # Revertir cualquier cambio antes de este punto
                            return render_template('editar_contacto.html', user=user, 
                                                   actividad_opciones=actividad_opciones, 
                                                   capacidad_opciones=capacidad_opciones, 
                                                   participacion_opciones=participacion_opciones,
                                                   tipo_sangre_opciones=tipo_sangre_opciones,
                                                   provincia_opciones=provincia_opciones,
                                                   logged_in_user_role=logged_in_user_role,
                                                   role_opciones=role_opciones)
                    user.role = new_role
                else:
                    # Si el rol enviado no es válido o está vacío, no se actualiza.
                    # Esto también maneja el caso de que un Superuser intente limpiar el campo de rol
                    # para un Superuser, lo que podría reducir el conteo por debajo de 1.
                    # Si el rol del usuario original es Superuser y se intenta cambiar a algo inválido,
                    # se mantiene el rol actual.
                    pass


            # Actualizar la fecha de actualización
            user.fecha_actualizacion = datetime.utcnow()

            db.session.commit()
            flash('¡Contacto actualizado exitosamente!', 'success')
            # Redirigir a ver_perfil si el usuario editó su propio perfil
            if str(logged_in_user_id) == str(user_id):
                return redirect(url_for('perfil.ver_perfil'))
            else:
                return redirect(url_for('contactos.ver_detalle', user_id=user.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el contacto: {e}', 'danger')
            # Si el error es de username duplicado, podríamos ser más específicos
            if 'UNIQUE constraint failed' in str(e) and 'username' in str(e):
                flash('El nombre de usuario ya está en uso. Por favor, elige otro.', 'danger')
            if 'UNIQUE constraint failed' in str(e) and 'email' in str(e):
                flash('El correo electrónico ya está en uso. Por favor, elige otro.', 'danger')

            return render_template('editar_contacto.html', user=user, 
                                   actividad_opciones=actividad_opciones, 
                                   capacidad_opciones=capacidad_opciones, 
                                   participacion_opciones=participacion_opciones,
                                   tipo_sangre_opciones=tipo_sangre_opciones,
                                   provincia_opciones=provincia_opciones,
                                   logged_in_user_role=logged_in_user_role, # Pasa el rol para mostrar/ocultar el campo
                                   role_opciones=role_opciones) # Pasa las opciones en caso de error

    # SI ES UN GET REQUEST: Asegurarse de pasar las opciones también
    avatar_url = None
    if user.avatar_url:
        with current_app.app_context():
            avatar_url = url_for('static', filename=user.avatar_url)
    else:
        with current_app.app_context():
            avatar_url = url_for('static', filename='images/defaults/default_avatar.png')

    return render_template('editar_contacto.html', user=user, avatar_url=avatar_url,
                           actividad_opciones=actividad_opciones, 
                           capacidad_opciones=capacidad_opciones, 
                           participacion_opciones=participacion_opciones,
                           tipo_sangre_opciones=tipo_sangre_opciones,
                           provincia_opciones=provincia_opciones,
                           logged_in_user_role=logged_in_user_role, # Pasa el rol para mostrar/ocultar el campo
                           role_opciones=role_opciones) # Pasa las opciones aquí también


# Rutas de Exportación (Individual)
@contactos_bp.route('/exportar_vcard/<int:user_id>')
@role_required(['Superuser', 'Administrador']) # Solo Superusers y Administradores pueden exportar vCard individual
def exportar_vcard(user_id):
    """
    Exporta los datos de un contacto individual a un archivo VCard (.vcf).
    """
    user = User.query.get_or_404(user_id)

    # Inicializar all_vcard_data antes del bloque try/except
    all_vcard_data = [] 

    try:
        card = vobject.vCard()
        
        # Nombre
        card.add('n')
        card.n.value = vobject.vcard.Name(family=user.primer_apellido, given=user.nombre, additional=user.segundo_apellido if user.segundo_apellido else '')
        
        # Nombre completo para pantalla
        card.add('fn')
        card.fn.value = f"{user.nombre} {user.primer_apellido} {user.segundo_apellido if user.segundo_apellido else ''}".strip()

        # Teléfono
        if user.telefono:
            tel = card.add('tel')
            tel.type_param = 'CELL'
            tel.value = user.telefono
        if user.telefono_emergencia:
            tel_emergencia = card.add('tel')
            tel_emergencia.type_param = 'WORK'
            tel_emergencia.params['X-LABEL'] = ['Emergencia'] 
            tel_emergencia.value = user.telefono_emergencia

        if user.email:
            email = card.add('email')
            email.type_param = 'INTERNET'
            email.value = user.email

        if user.direccion:
            adr = card.add('adr')
            adr.type_param = 'HOME'
            adr.value = vobject.vcard.Address(street=user.direccion) 
            
        if user.empresa:
            card.add('org').value = user.empresa

        # Otros campos que puedan tener sentido en un vCard (ej. TÍTULO, NOTAS, etc.)
        if user.actividad:
            card.add('title').value = user.actividad
        if user.cedula:
            # Se añade el rol al campo NOTE del vCard
            card.add('note').value = f"Cédula: {user.cedula}, Rol: {user.role}" 
        
        if user.avatar_url and 'default_avatar.png' not in user.avatar_url:
            with current_app.app_context():
                full_avatar_url = url_for('static', filename=user.avatar_url, _external=True)
                photo = card.add('photo')
                photo.value = full_avatar_url
                photo.type_param = 'URI'

        if user.fecha_actualizacion:
            card.add('rev').value = user.fecha_actualizacion.isoformat()
        
        # Serializa cada vCard y añádelo a la lista
        all_vcard_data.append(card.serialize())
            
        # Une todas las vCards en una sola cadena
        final_vcf_content = "\n".join(all_vcard_data)

        buffer = io.BytesIO(final_vcf_content.encode('utf-8'))

        return send_file(
            buffer,
            mimetype='text/vcard',
            as_attachment=True,
            download_name=f'{user.username}.vcf'
        )
    except Exception as e:
        flash(f'Error al exportar contactos: {e}', 'danger')
        return redirect(url_for('contactos.ver_detalle', user_id=user_id))

@contactos_bp.route('/exportar_excel/<int:user_id>')
@role_required(['Superuser', 'Administrador']) # Solo Superusers y Administradores pueden exportar Excel individual
def exportar_excel(user_id):
    """
    Exporta los datos de un contacto individual a un archivo Excel (.xlsx).
    """
    user = User.query.get_or_404(user_id)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Detalles de Contacto"

    # Encabezados
    headers = [
        "Campo", "Valor"
    ]
    sheet.append(headers)

    # Datos del usuario
    # Convertimos los campos a string para evitar problemas de formato en Excel
    data = [
        ("Nombre de Usuario", str(user.username)),
        ("Nombre", str(user.nombre)),
        ("Primer Apellido", str(user.primer_apellido)),
        ("Segundo Apellido", str(user.segundo_apellido) if user.segundo_apellido else ""),
        ("Teléfono", str(user.telefono)),
        ("Email", str(user.email) if user.email else ""),
        ("Teléfono Emergencia", str(user.telefono_emergencia) if user.telefono_emergencia else ""),
        ("Nombre Contacto Emergencia", str(user.nombre_emergencia) if user.nombre_emergencia else ""),
        ("Empresa", str(user.empresa) if user.empresa else ""),
        ("Cédula", str(user.cedula) if user.cedula else ""),
        ("Dirección", str(user.direccion) if user.direccion else ""),
        ("Actividad", str(user.actividad) if user.actividad else ""),
        ("Capacidad", str(user.capacidad) if user.capacidad else ""),
        ("Participación", str(user.participacion) if user.participacion else ""),
        ("Fecha de Registro", user.fecha_registro.strftime('%d/%m/%Y %H:%M')),
        ("Última Actualización", user.fecha_actualizacion.strftime('%d/%m/%Y %H:%M') if user.fecha_actualizacion else "N/A"),
        ("Rol", str(user.role)) # Añadir el rol al Excel
    ]

    for row_data in data:
        sheet.append(row_data)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0) # Regresar al inicio del buffer para que send_file pueda leerlo

    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{user.username}_contacto.xlsx'
    )

# Ruta: Exportar TODOS los contactos a Excel (Formato de lista)
@contactos_bp.route('/exportar_todos_excel')
@role_required(['Superuser', 'Administrador']) # Solo Superusers y Administradores pueden exportar todos a Excel
def exportar_todos_excel():
    """
    Exporta los datos de TODOS los contactos a un archivo Excel (.xlsx) en formato de lista tradicional (filas por usuario, columnas por campo).
    """
    try:
        all_users = User.query.all()

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Todos los Contactos"

        # Encabezados de las columnas para el formato de lista
        headers = [
            "Nombre de Usuario", "Nombre", "Primer Apellido", "Segundo Apellido",
            "Teléfono", "Email", "Teléfono Emergencia", "Nombre Contacto Emergencia",
            "Empresa", "Cédula", "Dirección", "Actividad", "Capacidad", "Participación",
            "Fecha de Registro", "Última Actualización", "Rol" # Añadir el rol
        ]
        sheet.append(headers)

        # Iterar sobre cada usuario y añadir sus datos como una fila
        for user in all_users:
            row_data = [
                str(user.username),
                str(user.nombre),
                str(user.primer_apellido),
                str(user.segundo_apellido) if user.segundo_apellido else "",
                str(user.telefono),
                str(user.email) if user.email else "",
                str(user.telefono_emergencia) if user.telefono_emergencia else "",
                str(user.nombre_emergencia) if user.nombre_emergencia else "",
                str(user.empresa) if user.empresa else "",
                str(user.cedula) if user.cedula else "",
                str(user.direccion) if user.direccion else "",
                str(user.actividad) if user.actividad else "",
                str(user.capacidad) if user.capacidad else "",
                str(user.participacion) if user.participacion else "",
                user.fecha_registro.strftime('%d/%m/%Y %H:%M'),
                user.fecha_actualizacion.strftime('%d/%m/%Y %H:%M') if user.fecha_actualizacion else "N/A",
                str(user.role) # Añadir el rol
            ]
            sheet.append(row_data)

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='todos_los_contactos.xlsx'
        )
    except Exception as e:
        flash(f'Error al exportar todos los contactos a Excel: {e}', 'danger')
        return redirect(url_for('contactos.ver_contactos'))

# Ruta: Exportar TODOS los contactos a VCard
@contactos_bp.route('/exportar_todos_vcard')
@role_required(['Superuser', 'Administrador']) # Solo Superusers y Administradores pueden exportar todos a VCard
def exportar_todos_vcard():
    """
    Exporta los datos de TODOS los contactos a un archivo VCard (.vcf) consolidado.
    """
    # Inicializar all_vcard_data antes del bloque try/except
    all_vcard_data = [] 

    try:
        all_users = User.query.all()
        

        for user in all_users:
            card = vobject.vCard()
            
            card.add('n')
            card.n.value = vobject.vcard.Name(family=user.primer_apellido, given=user.nombre, additional=user.segundo_apellido if user.segundo_apellido else '')
            
            card.add('fn')
            card.fn.value = f"{user.nombre} {user.primer_apellido} {user.segundo_apellido if user.segundo_apellido else ''}".strip()

            if user.telefono:
                tel = card.add('tel')
                tel.type_param = 'CELL'
                tel.value = user.telefono
            if user.telefono_emergencia:
                tel_emergencia = card.add('tel')
                tel_emergencia.type_param = 'WORK'
                tel_emergencia.params['X-LABEL'] = ['Emergencia'] 
                tel_emergencia.value = user.telefono_emergencia

            if user.email:
                email = card.add('email')
                email.type_param = 'INTERNET'
                email.value = user.email

            if user.direccion:
                adr = card.add('adr')
                adr.type_param = 'HOME'
                adr.value = vobject.vcard.Address(street=user.direccion) 
                
            if user.empresa:
                card.add('org').value = user.empresa

            if user.actividad:
                card.add('title').value = user.actividad
            if user.cedula:
                # Se añade el rol al campo NOTE del vCard
                card.add('note').value = f"Cédula: {user.cedula}, Rol: {user.role}" 
            
            if user.avatar_url and 'default_avatar.png' not in user.avatar_url:
                with current_app.app_context():
                    full_avatar_url = url_for('static', filename=user.avatar_url, _external=True)
                    photo = card.add('photo')
                    photo.value = full_avatar_url
                    photo.type_param = 'URI'

            if user.fecha_actualizacion:
                card.add('rev').value = user.fecha_actualizacion.isoformat()
            
            # Serializa cada vCard y añádelo a la lista
            all_vcard_data.append(card.serialize())
        
        # Une todas las vCards en una sola cadena
        final_vcf_content = "\n".join(all_vcard_data)

        buffer = io.BytesIO(final_vcf_content.encode('utf-8'))

        return send_file(
            buffer,
            mimetype='text/vcard',
            as_attachment=True,
            download_name='todos_los_contactos.vcf'
        )
    except Exception as e:
        flash(f'Error al exportar todos los contactos a VCard: {e}', 'danger')
        return redirect(url_for('contactos.ver_contactos'))

# NUEVA RUTA: Interfaz de Administración de Roles
@contactos_bp.route('/admin/manage_roles', methods=['GET', 'POST']) # CAMBIO AQUÍ: Añadido '/admin'
@role_required('Superuser') # Solo los Superusers pueden acceder a esta interfaz
def admin_manage_roles():
    """
    Permite a los Superusers ver y modificar los roles de todos los usuarios.
    Muestra un listado de usuarios con un selector de rol para cada uno.
    """
    role_opciones = ['Usuario Regular', 'Administrador', 'Superuser']

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        new_role = request.form.get('new_role')

        if not user_id or not new_role:
            flash('Datos incompletos para actualizar el rol.', 'danger')
            return redirect(url_for('contactos.admin_manage_roles'))

        user_to_update = User.query.get(user_id)
        if not user_to_update:
            flash('Usuario no encontrado.', 'danger')
            return redirect(url_for('contactos.admin_manage_roles'))

        if new_role not in role_opciones:
            flash('Error: Rol no válido.', 'danger')
            return redirect(url_for('contactos.admin_manage_roles'))

        # Lógica para evitar que el Superuser logueado cambie su propio rol a algo que no sea Superuser
        if str(session.get('user_id')) == str(user_to_update.id) and user_to_update.role == 'Superuser' and new_role != 'Superuser':
            flash('No puedes cambiar tu propio rol de Superuser a otro rol desde esta interfaz. Pide a otro Superuser que lo haga si es necesario.', 'danger')
            return redirect(url_for('contactos.admin_manage_roles'))

        # Lógica para limitar a 2 Superusuarios
        if new_role == 'Superuser' and user_to_update.role != 'Superuser':
            current_superusers = User.query.filter_by(role='Superuser').count()
            if current_superusers >= 2:
                flash('No se pueden asignar más de 2 Superusers. Cambia el rol de otro Superuser primero.', 'danger')
                return redirect(url_for('contactos.admin_manage_roles'))
        
        # Si el usuario es un Superuser y se le cambia el rol a otro (por otro Superuser)
        # Asegurarse de que no se elimina el último Superuser accidentalmente
        if user_to_update.role == 'Superuser' and new_role != 'Superuser':
            superuser_count_before_change = User.query.filter_by(role='Superuser').count()
            if superuser_count_before_change <= 1:
                flash('No se puede cambiar el rol del último Superuser a un rol inferior. Debe haber al menos un Superuser en el sistema.', 'danger')
                return redirect(url_for('contactos.admin_manage_roles'))

        user_to_update.role = new_role
        try:
            db.session.commit()
            flash(f'Rol de {user_to_update.username} actualizado a "{new_role}".', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el rol: {e}', 'danger')

        return redirect(url_for('contactos.admin_manage_roles'))

    # Si es GET request, mostrar la lista de usuarios y sus roles
    # Por defecto, mostrar solo Superusers y Administradores
    admin_users = User.query.filter(User.role.in_(['Superuser', 'Administrador'])).order_by(User.role.desc(), User.username.asc()).all()

    # Búsqueda de usuarios regulares
    search_query_regular = request.args.get('search_query_regular', '').strip()
    regular_users = []
    if search_query_regular:
        search_pattern = f"%{search_query_regular}%"
        regular_users = User.query.filter(
            User.role == 'Usuario Regular',
            or_(
                User.username.ilike(search_pattern),
                User.nombre.ilike(search_pattern),
                User.primer_apellido.ilike(search_pattern),
                User.segundo_apellido.ilike(search_pattern),
                User.email.ilike(search_pattern)
            )
        ).order_by(User.username.asc()).all()
    else:
        # Si no hay búsqueda, no mostrar usuarios regulares por defecto en esta sección
        # o mostrar un número limitado si se desea (aquí no los mostraremos para mantener la separación)
        pass # No fetch all regular users by default

    return render_template('admin_roles.html', admin_users=admin_users, regular_users=regular_users, search_query_regular=search_query_regular)

