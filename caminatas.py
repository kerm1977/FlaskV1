from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_file
from functools import wraps
from datetime import datetime, date, time # Importar time para manejar horas
import os
import json
from werkzeug.utils import secure_filename
from sqlalchemy import desc, func
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
import io # Importar io para manejar datos en memoria
from bs4 import BeautifulSoup # Importar BeautifulSoup para eliminar etiquetas HTML
import pytz # Importar pytz para manejo de zonas horarias
import locale # NUEVO: Importar módulo locale
from flask_wtf.csrf import generate_csrf # Añade esta línea
from sqlalchemy.exc import IntegrityError # NUEVO: Importar IntegrityError para manejar errores de integridad

# Intenta configurar el locale para español.
# La cadena exacta puede variar según el sistema operativo (Linux, Windows, macOS).
# Se prueban varias opciones comunes para asegurar que el nombre del mes se muestre en español.
try:
    locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8') # Para sistemas Unix/Linux
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'es_ES') # Otra opción para Unix/Linux
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Spanish_Spain.1252') # Para Windows
        except locale.Error:
            print("Advertencia: No se pudo configurar el locale a español. Las fechas podrían no mostrarse correctamente.")


# Importa db, User, Caminata, AbonoCaminata, caminata_participantes e Itinerario desde models.py
# Es CRUCIAL que db y los modelos se importen desde models.py
from models import db, User, Caminata, AbonoCaminata, caminata_participantes, Itinerario # MODIFICADO: Añade Itinerario

caminatas_bp = Blueprint('caminatas', __name__)

# Definir la zona horaria de Costa Rica
COSTA_RICA_TZ = pytz.timezone('America/Costa_Rica')
UTC_TZ = pytz.utc


# --- Decoradores ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'info')
            return redirect(url_for('login'))
        if 'role' not in session or session['role'] != 'Superuser': # Asume que 'Superuser' es el rol de administrador
            flash('Acceso denegado: Se requiere rol de administrador.', 'danger')
            return redirect(url_for('home')) # Redirige a una página de inicio o de acceso denegado
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas de Caminatas ---

# Ruta principal para ver todas las caminatas
@caminatas_bp.route('/ver_caminatas')
# @login_required # Comentado para permitir ver caminatas sin login, puedes descomentar si lo necesitas
def ver_caminatas():
    all_caminatas = Caminata.query.order_by(Caminata.fecha.desc()).all()
    search_actividad = request.args.get('actividad')

    if search_actividad:
        caminatas = Caminata.query.filter_by(actividad=search_actividad).all()
    else:
        caminatas = Caminata.query.all()

    return render_template('ver_caminatas.html', caminatas=caminatas, search_actividad=search_actividad)
  
# Ruta para crear una nueva caminata
@caminatas_bp.route('/crear_caminata', methods=['GET', 'POST'])
@login_required
def crear_caminata():
    if request.method == 'POST':
        nombre = request.form['nombre']
        actividad = request.form['actividad']
        etapa = request.form.get('etapa') 
        
        # --- Manejo de campos numéricos y de fecha con validación ---
        try:
            precio = float(request.form['precio']) if request.form['precio'] else 0.0 # Manejo de cadena vacía
        except ValueError:
            flash('El precio debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.crear_caminata'))

        fecha_str = request.form['fecha']
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha inválido. Utilice AAAA-MM-DD.', 'danger')
            return redirect(url_for('caminatas.crear_caminata'))

        try:
            distancia = float(request.form['distancia']) if request.form.get('distancia') else None
        except ValueError:
            flash('La distancia debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.crear_caminata'))

        try:
            altura_maxima = float(request.form['altura_maxima']) if request.form.get('altura_maxima') else None
        except ValueError:
            flash('La altura máxima debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.crear_caminata'))

        try:
            altura_minima = float(request.form['altura_minima']) if request.form.get('altura_minima') else None
        except ValueError:
            flash('La altura mínima debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.crear_caminata'))

        try:
            altura_positiva = float(request.form['altura_positiva']) if request.form.get('altura_positiva') else None
        except ValueError:
            flash('La altura positiva debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.crear_caminata'))

        try:
            altura_negativa = float(request.form['altura_negativa']) if request.form.get('altura_negativa') else None
        except ValueError:
            flash('La altura negativa debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.crear_caminata'))
        # --- Fin Manejo de campos numéricos y de fecha con validación ---

        # NUEVO: Manejo de campos de hora y duración
        hora_salida_str = request.form.get('hora_salida')
        hora_salida = None
        if hora_salida_str:
            try:
                hora_salida = datetime.strptime(hora_salida_str, '%H:%M').time()
            except ValueError:
                flash('Formato de Hora de Salida inválido. Utilice HH:MM.', 'danger')
                return redirect(url_for('caminatas.crear_caminata'))

        hora_regreso_str = request.form.get('hora_regreso')
        hora_regreso = None
        if hora_regreso_str:
            try:
                hora_regreso = datetime.strptime(hora_regreso_str, '%H:%M').time()
            except ValueError:
                flash('Formato de Hora de Regreso inválido. Utilice HH:MM.', 'danger')
                return redirect(url_for('caminatas.crear_caminata'))

        duracion_horas = None
        duracion_horas_str = request.form.get('duracion_horas')
        if duracion_horas_str:
            try:
                duracion_horas = float(duracion_horas_str)
            except ValueError:
                flash('La Duración (horas) debe ser un número válido.', 'danger')
                return redirect(url_for('caminatas.crear_caminata'))
        # FIN NUEVO

        dificultad = request.form.get('dificultad')
        capacidad_minima = request.form['capacidad_minima'] if request.form.get('capacidad_minima') else None
        capacidad_maxima = request.form['capacidad_maxima'] if request.form.get('capacidad_maxima') else None
        otros_datos_ckeditor = request.form.get('otros_datos_ckeditor')

        lugar_salida = request.form.get('lugar_salida')
        provincia = request.form.get('provincia')
        tipo_terreno = request.form.getlist('tipo_terreno') 
        tipo_transporte = request.form.getlist('tipo_transporte') 
        incluye = request.form.getlist('incluye') 
        tipo_clima = request.form.get('tipo_clima')


        imagen_caminata_url = None
        if 'imagen_caminata' in request.files:
            file = request.files['imagen_caminata']
            if file.filename != '':
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'caminatas')
                os.makedirs(upload_folder, exist_ok=True) 
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                imagen_caminata_url = os.path.join('uploads', 'caminatas', filename).replace("\\", "/")


        nueva_caminata = Caminata(
            nombre=nombre,
            actividad=actividad,
            etapa=etapa, 
            precio=precio,
            fecha=fecha,
            dificultad=dificultad,
            distancia=distancia,
            capacidad_minima=capacidad_minima,
            capacidad_maxima=capacidad_maxima,
            altura_maxima=altura_maxima,
            altura_minima=altura_minima,
            altura_positiva=altura_positiva,
            altura_negativa=altura_negativa,
            otros_datos=otros_datos_ckeditor,
            imagen_caminata_url=imagen_caminata_url,
            lugar_salida=lugar_salida,
            provincia=provincia,
            tipo_terreno=json.dumps(tipo_terreno), 
            tipo_transporte=json.dumps(tipo_transporte), 
            incluye=json.dumps(incluye), 
            tipo_clima=tipo_clima,
            # NUEVO: Asignar valores de hora y duración
            hora_salida=hora_salida,
            hora_regreso=hora_regreso,
            duracion_horas=duracion_horas
            # FIN NUEVO
        )
        db.session.add(nueva_caminata)
        db.session.commit()
        flash('Caminata creada exitosamente!', 'success')
        return redirect(url_for('caminatas.ver_caminatas'))
    
    actividad_opciones = [
        "El Camino de Costa Rica",
        "Parque Nacional",
        "Paseo",
        "Iniciante",
        "Básico",
        "Intermedio",
        "Dificil"
        "Avanzado",
        "Técnico"
    ]
    etapa_opciones = [
        "Etapa 1a - Parismina a Laguna Perlas 5.13k",
        "Etapa 1b - Muelle Goshen a Cimarrones 24.02k",
        "Etapa 2 - Cimarrones a Brisas 15.09k",
        "Etapa 3 - Brisas de Pacuarito a Tsiobata 15.05k",
        "Etapa 4 - Tsiobata a Tres Equis 6.85k",
        "Etapa 5 - Tres Equis a Pacayitas 13.30k",
        "Etapa 6 - Pacayitas a La Suiza 12.58k",
        "Etapa 7 - La Suiza a Humo de Pejibaye",
        "Etapa 8 - Humo de Pejibaye a Tapanti 16.58k",
        "Etapa 9 - Tapanti a Navarro del Muneco 24.40k",
        "Etapa 10 - Navarro del Muneco a Palo Verde",
        "Etapa 11 - Palo Verde a Cerro Alto 8.90k",
        "Etapa 12 - Cerro Alto a San Pablo de Leon Cortes 18.28k",
        "Etapa 13 - San Pablo de Leon Cortes a Napoles 16.41k",
        "Etapa 14 - Napoles a Naranjillo 13.35k",
        "Etapa 15 - Naranjillo a Esquipulas 12.01k",
        "Etapa 16 - Esquipulas a Quepos 22.72k",
        "--------------",
        "Etapas 1a & 1b / 29.32k",
        "Etapas 3 & 4 / 21.09k",
        "Etapas 14 & 15 / 25.36k"
    ]
    lugar_salida_opciones = [
        "Parque De Tres Ríos - Escuela",
        "Parque De Tres Ríos - Cruz Roja",
        "Parque De Tres Ríos - Letras",
        "Plaza de San Diego",
        "Iglesia San Diego"
    ]
    dificultad_opciones = [
        "Iniciante",
        "Básico",
        "Intermedio",
        "Avanzado",
        "Técnico"
    ]
    provincia_opciones = [
        "Cartago",
        "Alajuela",
        "Heredia",
        "San José",
        "Puntarenas",
        "Guanacaste",
        "Limón"
    ]
    tipo_terreno_opciones = [
        "Asfalto llano",
        "Asfalto Pendiente Básico",
        "Asfalto Pendiente Medio",
        "Asfalto Pendiente Difícil",
        "Lastre Pendiente Básico",
        "Lastre Pendiente Medio",
        "Lastre Pendiente Difícil",
        "Sendero Pendiente Básico",
        "Sendero Pendiente Medio",
        "Sendero Pendiente Difícil",
        "Montaña Pendiente Básico",
        "Montaña Pendiente Medio",
        "Montaña Pendiente Difícil",
        "Montaña Técnica",
        "Otros(Otras Señas de Terreno)"
    ]
    tipo_transporte_opciones = [
        "Moto",
        "Bus Público",
        "Buseta",
        "Automobil",
        "Lancha",
        "Ferry",
        "Avion"
    ]
    incluye_opciones = [
        "Transporte",
        "Transporte y Entrada",
        "Transporte y Guía",
        "Transporte y Alimentación",
        "Transporte, Entrada y Guía",
        "Transporte, Entrada y Alimentación",
        "Transporte, y Alimentación",
        "Transporte, Guía y Alimentación",
        "Todo menos Alimentación"
    ]
    tipo_clima_opciones = [
        "Clima Tropical Húmedo",
        "Clima Tropical Seco",
        "Clima Tropical Muy Húmedo",
        "Clima de Montaña"
    ]

    return render_template('crear_caminatas.html', 
                           actividad_opciones=actividad_opciones,
                           etapa_opciones=etapa_opciones, 
                           lugar_salida_opciones=lugar_salida_opciones,
                           dificultad_opciones=dificultad_opciones,
                           provincia_opciones=provincia_opciones,
                           tipo_terreno_opciones=tipo_terreno_opciones,
                           tipo_transporte_opciones=tipo_transporte_opciones,
                           incluye_opciones=incluye_opciones,
                           tipo_clima_opciones=tipo_clima_opciones
                           )

# Ruta para ver el detalle de una caminata
@caminatas_bp.route('/caminata/<int:caminata_id>')
# @login_required # Comentado para permitir ver detalles sin login, puedes descomentar si lo necesitas
def detalle_caminata(caminata_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    usuarios_registrados = User.query.all()

    # Preparar los datos de acompañantes y estado de abono para cada participante
    participantes_con_info = []

    for participant in caminata.participantes:
        ultimo_abono = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).order_by(desc(AbonoCaminata.fecha_abono)).first()

        estado_abono = ultimo_abono.opcion if ultimo_abono else None

        companion_names_for_participant = set()
        abonos_del_participante = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).all()
        for abono in abonos_del_participante:
            if abono.nombres_acompanantes:
                try:
                    names_list = json.loads(abono.nombres_acompanantes)
                    for name in names_list:
                        if name.strip():
                            companion_names_for_participant.add(name.strip())
                except json.JSONDecodeError:
                    print(f"Advertencia: No se pudo decodificar JSON para nombres_acompanantes: {abono.nombres_acompanantes}")
                    pass

        participantes_con_info.append({
            'id': participant.id,
            'nombre': participant.nombre,
            'primer_apellido': participant.primer_apellido,
            'username': participant.username,
            'email': participant.email,
            'telefono': participant.telefono,
            'estado_abono': estado_abono,
            'acompanantes': list(companion_names_for_participant)
        })

    return render_template(
        'detalle_caminatas.html',
        caminata=caminata,
        usuarios_registrados=usuarios_registrados,
        participantes_con_info=participantes_con_info,
        csrf_token=generate_csrf() # Añade esta línea
    )


# Ruta para editar una caminata
@caminatas_bp.route('/caminata/<int:caminata_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_caminata(caminata_id):
    caminata = Caminata.query.get_or_404(caminata_id)

    if request.method == 'POST':
        caminata.nombre = request.form['nombre']
        caminata.actividad = request.form['actividad']
        caminata.etapa = request.form.get('etapa') 
        
        # --- Manejo de campos numéricos y de fecha con validación en edición ---
        try:
            caminata.precio = float(request.form['precio']) if request.form['precio'] else 0.0
        except ValueError:
            flash('El precio debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))

        fecha_str = request.form['fecha']
        try:
            caminata.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha inválido. Utilice AAAA-MM-DD.', 'danger')
            return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))

        try:
            distancia = float(request.form['distancia']) if request.form.get('distancia') else None
        except ValueError:
            flash('La distancia debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))

        try:
            altura_maxima = float(request.form['altura_maxima']) if request.form.get('altura_maxima') else None
        except ValueError:
            flash('La altura máxima debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))

        try:
            altura_minima = float(request.form['altura_minima']) if request.form.get('altura_minima') else None
        except ValueError:
            flash('La altura mínima debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))

        try:
            caminata.altura_positiva = float(request.form['altura_positiva']) if request.form.get('altura_positiva') else None
        except ValueError:
            flash('La altura positiva debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))

        try:
            caminata.altura_negativa = float(request.form['altura_negativa']) if request.form.get('altura_negativa') else None
        except ValueError:
            flash('La altura negativa debe ser un número válido.', 'danger')
            return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))
        # --- Fin Manejo de campos numéricos y de fecha con validación en edición ---

        # NUEVO: Manejo de campos de hora y duración para edición
        hora_salida_str = request.form.get('hora_salida')
        if hora_salida_str:
            try:
                caminata.hora_salida = datetime.strptime(hora_salida_str, '%H:%M').time()
            except ValueError:
                flash('Formato de Hora de Salida inválido. Utilice HH:MM.', 'danger')
                return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))
        else:
            caminata.hora_salida = None # Si el campo está vacío, establecer a None

        hora_regreso_str = request.form.get('hora_regreso')
        if hora_regreso_str:
            try:
                caminata.hora_regreso = datetime.strptime(hora_regreso_str, '%H:%M').time()
            except ValueError:
                flash('Formato de Hora de Regreso inválido. Utilice HH:MM.', 'danger')
                return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))
        else:
            caminata.hora_regreso = None # Si el campo está vacío, establecer a None

        duracion_horas_str = request.form.get('duracion_horas')
        if duracion_horas_str:
            try:
                caminata.duracion_horas = float(duracion_horas_str)
            except ValueError:
                flash('La Duración (horas) debe ser un número válido.', 'danger')
                return redirect(url_for('caminatas.editar_caminata', caminata_id=caminata.id))
        else:
            caminata.duracion_horas = None # Si el campo está vacío, establecer a None
        # FIN NUEVO

        caminata.otros_datos = request.form.get('otros_datos_ckeditor')

        lugar_salida = request.form.get('lugar_salida')
        provincia = request.form.get('provincia')
        caminata.tipo_terreno = json.dumps(request.form.getlist('tipo_terreno')) 
        caminata.tipo_transporte = json.dumps(request.form.getlist('tipo_transporte')) 
        caminata.incluye = json.dumps(request.form.getlist('incluye')) 
        caminata.tipo_clima = request.form.get('tipo_clima')


        # Manejo de la imagen
        if 'imagen_caminata' in request.files:
            file = request.files['imagen_caminata']
            if file.filename != '':
                # Eliminar la imagen antigua si existe
                if caminata.imagen_caminata_url:
                    old_image_path = os.path.join(current_app.root_path, 'static', caminata.imagen_caminata_url)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'caminatas')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                caminata.imagen_caminata_url = os.path.join('uploads', 'caminatas', filename).replace("\\", "/")
        else:
            # Si no se sube nueva imagen, mantener la existente o establecer a None si se borró
            if request.form.get('current_imagen_caminata_url') == '': 
                caminata.imagen_caminata_url = None

        db.session.commit()
        flash('Caminata actualizada exitosamente!', 'success')
        return redirect(url_for('caminatas.detalle_caminata', caminata_id=caminata.id))
    
    actividad_opciones = [
        "El Camino de Costa Rica",
        "Parque Nacional",
        "Paseo",
        "Iniciante",
        "Básico",
        "Intermedio",
        "Avanzado",
        "Técnico"
    ]
    etapa_opciones = [
        "Etapa 1a - Parismina a Laguna Perlas 5.13k",
        "Etapa 1b - Muelle Goshen a Cimarrones 24.02k",
        "Etapa 2 - Cimarrones a Brisas 15.09k",
        "Etapa 3 - Brisas de Pacuarito a Tsiobata 15.05k",
        "Etapa 4 - Tsiobata a Tres Equis 6.85k",
        "Etapa 5 - Tres Equis a Pacayitas 13.30k",
        "Etapa 6 - Pacayitas a La Suiza 12.58k",
        "Etapa 7 - La Suiza a Humo de Pejibaye",
        "Etapa 8 - Humo de Pejibaye a Tapanti 16.58k",
        "Etapa 9 - Tapanti a Navarro del Muneco 24.40k",
        "Etapa 10 - Navarro del Muneco a Palo Verde",
        "Etapa 11 - Palo Verde a Cerro Alto 8.90k",
        "Etapa 12 - Cerro Alto a San Pablo de Leon Cortes 18.28k",
        "Etapa 13 - San Pablo de Leon Cortes a Napoles 16.41k",
        "Etapa 14 - Napoles a Naranjillo 13.35k",
        "Etapa 15 - Naranjillo a Esquipulas 12.01k",
        "Etapa 16 - Esquipulas a Quepos 22.72k",
        "--------------",
        "Etapas 1a & 1b / 29.32k",
        "Etapas 3 & 4 / 21.09k",
        "Etapas 14 & 15 / 25.36k"
    ]
    lugar_salida_opciones = [
        "Parque De Tres Ríos - Escuela",
        "Parque De Tres Ríos - Cruz Roja",
        "Parque De Tres Ríos - Letras",
        "Plaza de San Diego",
        "Iglesia San Diego"
    ]
    dificultad_opciones = [
        "Iniciante",
        "Básico",
        "Intermedio",
        "Avanzado",
        "Técnico"
    ]
    provincia_opciones = [
        "Cartago",
        "Alajuela",
        "Heredia",
        "San José",
        "Puntarenas",
        "Guanacaste",
        "Limón"
    ]
    tipo_terreno_opciones = [
        "Asfalto llano",
        "Asfalto Pendiente Básico",
        "Asfalto Pendiente Medio",
        "Asfalto Pendiente Difícil",
        "Lastre Pendiente Básico",
        "Lastre Pendiente Medio",
        "Lastre Pendiente Difícil",
        "Sendero Pendiente Básico",
        "Sendero Pendiente Medio",
        "Sendero Pendiente Difícil",
        "Montaña Pendiente Básico",
        "Montaña Pendiente Medio",
        "Montaña Pendiente Difícil",
        "Montaña Técnica",
        "Otros(Otras Señas de Terreno)"
    ]
    tipo_transporte_opciones = [
        "Moto",
        "Bus Público",
        "Buseta",
        "Automobil",
        "Lancha",
        "Ferry",
        "Avion"
    ]
    incluye_opciones = [
        "Transporte",
        "Transporte y Entrada",
        "Transporte y Guía",
        "Transporte y Alimentación",
        "Transporte, Entrada y Guía",
        "Transporte, Entrada y Alimentación",
        "Transporte, y Alimentación",
        "Transporte, Guía y Alimentación",
        "Todo menos Alimentación"
    ]
    tipo_clima_opciones = [
        "Clima Tropical Húmedo",
        "Clima Tropical Seco",
        "Clima Tropical Muy Húmedo",
        "Clima de Montaña"
    ]

    return render_template('editar_caminatas.html', 
                           caminata=caminata,
                           actividad_opciones=actividad_opciones,
                           etapa_opciones=etapa_opciones, 
                           lugar_salida_opciones=lugar_salida_opciones,
                           dificultad_opciones=dificultad_opciones,
                           provincia_opciones=provincia_opciones,
                           tipo_terreno_opciones=tipo_terreno_opciones,
                           tipo_transporte_opciones=tipo_transporte_opciones,
                           incluye_opciones=incluye_opciones,
                           tipo_clima_opciones=tipo_clima_opciones
                           )

# Ruta para eliminar una caminata
@caminatas_bp.route('/caminata/<int:caminata_id>/eliminar', methods=['POST'])
@login_required
@admin_required # Solo administradores pueden eliminar caminatas
def eliminar_caminata(caminata_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    try:
        # Paso 1: Eliminar todos los itinerarios asociados a esta caminata
        # Esto es crucial porque itinerario.caminata_id es NOT NULL
        itinerarios_asociados = Itinerario.query.filter_by(caminata_id=caminata.id).all()
        for itinerario in itinerarios_asociados:
            db.session.delete(itinerario)
        
        # Paso 2: Eliminar abonos asociados primero para evitar errores de restricción de clave externa
        AbonoCaminata.query.filter_by(caminata_id=caminata.id).delete()
        
        # Paso 3: Eliminar las asociaciones en la tabla intermedia caminata_participantes
        # Esto se hace vaciando la lista de participantes de la caminata
        caminata.participantes = [] 

        # Paso 4: Eliminar la caminata
        db.session.delete(caminata)
        db.session.commit()
        flash('Caminata y sus datos asociados (itinerarios, abonos, participantes) eliminados exitosamente.', 'success')
    except IntegrityError as e:
        db.session.rollback()
        # Este error es menos probable ahora, pero se mantiene por si hay otras restricciones
        flash(f'Error de integridad al eliminar la caminata: No se pudieron eliminar registros asociados. Detalles: {e}', 'danger')
        current_app.logger.error(f"IntegrityError al eliminar caminata {caminata_id}: {e}")
    except Exception as e:
        db.session.rollback()
        flash(f'Error inesperado al eliminar la caminata: {str(e)}', 'danger')
        current_app.logger.error(f"Error general al eliminar caminata {caminata_id}: {e}")
    return redirect(url_for('caminatas.ver_caminatas'))

# Ruta para añadir/quitar participantes de una caminata
@caminatas_bp.route('/caminata/<int:caminata_id>/participantes', methods=['POST'])
@login_required
def gestionar_participantes(caminata_id):
    caminata = Caminata.query.get_or_404(caminata_id)

    if 'add_participant' in request.form:
        user_id = request.form['user_id']
        participante = User.query.get_or_404(user_id)
        if participante not in caminata.participantes:
            caminata.participantes.append(participante)
            db.session.commit()
            flash(f'{participante.nombre} {participante.primer_apellido} ha sido añadido como participante.', 'success')
        else:
            flash(f'{participante.nombre} {participante.primer_apellido} ya es participante de esta caminata.', 'info')
    
    elif 'remove_participant' in request.form:
        user_id = request.form['user_id']
        participante = User.query.get_or_404(user_id)
        if participante in caminata.participantes:
            caminata.participantes.remove(participante)
            # También eliminar todos los abonos de este participante para esta caminata
            AbonoCaminata.query.filter_by(caminata_id=caminata.id, user_id=participante.id).delete()
            db.session.commit()
            flash(f'{participante.nombre} {participante.primer_apellido} ha sido eliminado de los participantes y todos sus abonos para esta caminata han sido borrados.', 'success')
        else:
            flash(f'{participante.nombre} {participante.primer_apellido} no es participante de esta caminata.', 'info')
            
    return redirect(url_for('caminatas.detalle_caminata', caminata_id=caminata.id))


# NUEVA RUTA: Gestionar Abonos
@caminatas_bp.route('/caminatas/<int:caminata_id>/abono/<int:user_id>', methods=['GET', 'POST'])
@login_required
def abono_caminata(caminata_id, user_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    participante = User.query.get_or_404(user_id)
    
    abonos = AbonoCaminata.query.filter_by(caminata_id=caminata.id, user_id=participante.id).order_by(desc(AbonoCaminata.fecha_abono)).all()
    
    # Convertir las fechas de los abonos a la zona horaria de Costa Rica para mostrar
    for abono in abonos:
        # Si la fecha es naive, la localizamos como UTC antes de convertir a CR_TZ
        if abono.fecha_abono.tzinfo is None:
            abono.fecha_abono = UTC_TZ.localize(abono.fecha_abono)
        abono.fecha_abono = abono.fecha_abono.astimezone(COSTA_RICA_TZ)

    total_abonado = sum(abono.monto_abono for abono in abonos)

    ultima_cantidad_acompanantes = 0
    if abonos:
        ultima_cantidad_acompanantes = abonos[0].cantidad_acompanantes
    
    total_personas = 1 + ultima_cantidad_acompanantes
    total_a_pagar_por_participante = caminata.precio * total_personas
    
    monto_restante = total_a_pagar_por_participante - total_abonado
    
    if request.method == 'POST':
        if 'add_abono' in request.form:
            opcion = request.form.get('opcion') 
            cantidad_acompanantes = int(request.form['cantidad_acompanantes'])
            monto_abono = float(request.form['monto_abono'])
            nombres_acompanantes_raw = request.form.get('nombres_acompanantes_raw', '')

            nombres_acompanantes_list = [name.strip() for name in nombres_acompanantes_raw.split(',') if name.strip()]
            nombres_acompanantes_json = json.dumps(nombres_acompanantes_list)

            if not opcion:
                flash('Por favor, selecciona una opción (Abono, Reserva, Cancelación).', 'danger')
                return redirect(url_for('caminatas.abono_caminata', caminata_id=caminata.id, user_id=participante.id))

            try:
                # Al crear un nuevo abono, aseguramos que la fecha se guarda en UTC
                # (naive, ya que db.DateTime no es timezone-aware por defecto)
                # Esto es crucial para una conversión consistente al mostrar.
                nuevo_abono = AbonoCaminata(
                    caminata_id=caminata.id,
                    user_id=participante.id,
                    opcion=opcion, 
                    cantidad_acompanantes=cantidad_acompanantes,
                    monto_abono=monto_abono,
                    fecha_abono=datetime.utcnow(), # <-- Cambio clave aquí: Guardar en UTC (naive)
                    nombres_acompanantes=nombres_acompanantes_json # Guardar nombres de acompañantes
                )
                db.session.add(nuevo_abono)
                db.session.commit()
                flash('Abono registrado exitosamente.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al registrar el abono: {e}', 'danger')
            return redirect(url_for('caminatas.abono_caminata', caminata_id=caminata.id, user_id=participante.id))
        elif 'delete_abono' in request.form:
            abono_id = request.form.get('abono_id')
            if abono_id:
                abono_to_delete = AbonoCaminata.query.get(abono_id)
                if abono_to_delete and abono_to_delete.caminata_id == caminata.id and abono_to_delete.user_id == participante.id:
                    db.session.delete(abono_to_delete)
                    db.session.commit()
                    flash('Abono eliminado exitosamente.', 'success')
                else:
                    flash('Error: Abono no encontrado o no corresponde a este participante/caminata.', 'danger')
            else:
                flash('Error: No se especificó el abono a eliminar.', 'danger')
            return redirect(url_for('caminatas.abono_caminata', caminata_id=caminata.id, user_id=participante.id))
    opcion_abono_opciones = ["Abono", "Reserva", "Cancelación"]
    cantidad_acompanantes_opciones = list(range(10))
    return render_template('abono_caminatas.html', caminata=caminata, participante=participante, abonos=abonos, total_abonado=total_abonado, monto_restante=monto_restante, total_a_pagar_por_participante=total_a_pagar_por_participante, opcion_abono_opciones=opcion_abono_opciones, cantidad_acompanantes_opciones=cantidad_acompanantes_opciones)

# --- Funciones de Exportación de Abonos (ya existentes en tu archivo) ---
@caminatas_bp.route('/caminatas/<int:caminata_id>/abono/<int:user_id>/export_pdf')
@login_required
def exportar_abono_pdf(caminata_id, user_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    participante = User.query.get_or_404(user_id)
    abonos = AbonoCaminata.query.filter_by(caminata_id=caminata.id, user_id=participante.id).order_by(desc(AbonoCaminata.fecha_abono)).all()

    # Convertir las fechas de los abonos a la zona horaria de Costa Rica para exportar
    for abono in abonos:
        if abono.fecha_abono.tzinfo is None:
            abono.fecha_abono = UTC_TZ.localize(abono.fecha_abono)
        abono.fecha_abono = abono.fecha_abono.astimezone(COSTA_RICA_TZ)

    total_abonado = sum(abono.monto_abono for abono in abonos)
    
    # Obtener el último estado del abono para mostrarlo en el resumen
    ultimo_abono = AbonoCaminata.query.filter_by(
        caminata_id=caminata.id,
        user_id=participante.id
    ).order_by(desc(AbonoCaminata.fecha_abono)).first()
    
    estado_general_participante = ultimo_abono.opcion if ultimo_abono else "Sin Abono/Reserva"


    ultima_cantidad_acompanantes = abonos[0].cantidad_acompanantes if abonos else 0
    total_personas = 1 + ultima_cantidad_acompanantes
    total_a_pagar_por_participante = caminata.precio * total_personas
    monto_restante = total_a_pagar_por_participante - total_abonado

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Detalle de Abonos para Caminata', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'Caminata: {caminata.nombre}', 0, 1)
    # MODIFICACIÓN: Formato con nombre del mes en español y primera letra en mayúscula
    pdf.cell(0, 10, f'Fecha de Caminata: {caminata.fecha.strftime("%d de %B de %Y")}', 0, 1)
    pdf.cell(0, 10, f'Participante: {participante.nombre} {participante.primer_apellido}', 0, 1)
    pdf.cell(0, 10, f'Precio por Persona: {caminata.precio:,.0f} CRC', 0, 1)
    pdf.cell(0, 10, f'Total a Pagar (incluyendo acompañantes): {total_a_pagar_por_participante:,.0f} CRC', 0, 1)
    pdf.set_text_color(0, 128, 0) # Green for total_abonado
    pdf.cell(0, 10, f'Total Abonado: {total_abonado:,.0f} CRC', 0, 1)
    
    # MODIFICACIÓN: Mostrar el estado general del participante
    if estado_general_participante == "Cancelación":
        pdf.set_text_color(255, 165, 0) # Naranja
        pdf.cell(0, 10, f'Estado del Participante: {estado_general_participante}', 0, 1)
    elif estado_general_participante == "Reserva":
        pdf.set_text_color(0, 0, 255) # Azul
        pdf.cell(0, 10, f'Estado del Participante: {estado_general_participante}', 0, 1)
    elif estado_general_participante == "Abono":
        pdf.set_text_color(0, 128, 0) # Verde
        pdf.cell(0, 10, f'Estado del Participante: {estado_general_participante}', 0, 1)
    else: # Por si no hay abonos o el estado no es claro
        pdf.set_text_color(0, 0, 0) # Negro
        pdf.cell(0, 10, f'Estado del Participante: {estado_general_participante}', 0, 1)
        
    if monto_restante > 0 and estado_general_participante != "Cancelación": # Solo mostrar monto restante si no está cancelado
        pdf.set_text_color(255, 0, 0) # Rojo para Monto Restante
        pdf.cell(0, 10, f'Monto Restante: {monto_restante:,.0f} CRC', 0, 1)
        
    pdf.set_text_color(0, 0, 0) # Volver a negro para el texto normal
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Historial de Abonos:', 0, 1)
    pdf.set_font('Arial', '', 10)
    if abonos:
        for abono in abonos:
            nombres_acom = json.loads(abono.nombres_acompanantes) if abono.nombres_acompanantes else []
            nombres_str = ", ".join(nombres_acom) if nombres_acom else "N/A"
            # MODIFICACIÓN: Mantener el formato numérico para el historial de abonos, si no se desea el nombre del mes aquí
            pdf.cell(0, 7, f'  Fecha: {abono.fecha_abono.strftime("%d/%m/%Y %H:%M")}', 0, 1)
            pdf.cell(0, 7, f'  Opción: {abono.opcion}', 0, 1) # Mostrar la opción de cada abono
            pdf.cell(0, 7, f'  Acompañantes: {abono.cantidad_acompanantes}', 0, 1)
            pdf.cell(0, 7, f'  Nombres: {nombres_str}', 0, 1)
            pdf.cell(0, 7, f'  Monto: {abono.monto_abono:,.0f} CRC', 0, 1)
            pdf.ln(2)
    else:
        pdf.cell(0, 10, 'No hay abonos registrados.', 0, 1)
    pdf_output = pdf.output(dest='S').encode('latin1')
    response = current_app.make_response(pdf_output)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=abono_caminata_{caminata.id}_{participante.id}.pdf'
    return response

@caminatas_bp.route('/caminatas/<int:caminata_id>/abono/<int:user_id>/export_jpg')
@login_required
def exportar_abono_jpg(caminata_id, user_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    participante = User.query.get_or_404(user_id)
    abonos = AbonoCaminata.query.filter_by(caminata_id=caminata.id, user_id=participante.id).order_by(desc(AbonoCaminata.fecha_abono)).all()

    for abono in abonos:
        if abono.fecha_abono.tzinfo is None:
            abono.fecha_abono = UTC_TZ.localize(abono.fecha_abono)
        abono.fecha_abono = abono.fecha_abono.astimezone(COSTA_RICA_TZ)

    total_abonado = sum(abono.monto_abono for abono in abonos)

    # Obtener el último estado del abono para mostrarlo en el resumen
    ultimo_abono = AbonoCaminata.query.filter_by(
        caminata_id=caminata.id,
        user_id=participante.id
    ).order_by(desc(AbonoCaminata.fecha_abono)).first()
    
    estado_general_participante = ultimo_abono.opcion if ultimo_abono else "Sin Abono/Reserva"

    ultima_cantidad_acompanantes = abonos[0].cantidad_acompanantes if abonos else 0
    total_personas = 1 + ultima_cantidad_acompanantes
    total_a_pagar_por_participante = caminata.precio * total_personas
    monto_restante = total_a_pagar_por_participante - total_abonado

    # Preparar el texto para la imagen
    text_lines = []
    text_lines.append("--- Detalle de Abonos para Caminata ---")
    text_lines.append(f"Caminata: {caminata.nombre}")
    text_lines.append(f"Fecha de Caminata: {caminata.fecha.strftime('%d de %B de %Y')}")
    text_lines.append(f"Participante: {participante.nombre} {participante.primer_apellido}")
    text_lines.append(f"Precio por Persona: {caminata.precio:,.0f} CRC")
    text_lines.append(f"Total a Pagar (incluyendo acompañantes): {total_a_pagar_por_participante:,.0f} CRC")
    text_lines.append(f"Total Abonado: {total_abonado:,.0f} CRC")
    text_lines.append(f"Estado del Participante: {estado_general_participante}") # Mostrar el estado general

    if monto_restante > 0 and estado_general_participante != "Cancelación":
        text_lines.append(f"Monto Restante: {monto_restante:,.0f} CRC")
    
    text_lines.append("")
    text_lines.append("--- Historial de Abonos ---")

    if abonos:
        for i, abono in enumerate(abonos):
            nombres_acom = json.loads(abono.nombres_acompanantes) if abono.nombres_acompanantes else []
            nombres_str = ", ".join(nombres_acom) if nombres_acom else "N/A"
            # MODIFICACIÓN: Mantener el formato numérico para el historial de abonos, si no se desea el nombre del mes aquí
            text_lines.append(f"  {i+1}. Fecha: {abono.fecha_abono.strftime('%d/%m/%Y %H:%M')}")
            text_lines.append(f"     Opción: {abono.opcion}") # Mostrar la opción de cada abono
            text_lines.append(f"     Acompañantes: {abono.cantidad_acompanantes}")
            text_lines.append(f"     Nombres: {nombres_str}")
            text_lines.append(f"     Monto: {abono.monto_abono:,.0f} CRC")
            text_lines.append("")
    else:
        text_lines.append("No hay abonos registrados.")

    # Convertir a cadena de texto para dibujar en la imagen
    full_text = "\n".join(text_lines)

    # Configuración de la fuente y tamaño
    font_size = 20
    font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'arial.ttf')
    try:
        font = ImageFont.truetype(font_path, font_size)
        font_bold = ImageFont.truetype(font_path.replace('.ttf', 'bd.ttf'), font_size) # Asume que hay un arialbd.ttf
        font_small = ImageFont.truetype(font_path, int(font_size * 0.8)) # Fuente más pequeña para detalles
        font_italic = ImageFont.truetype(font_path.replace('.ttf', 'i.ttf'), font_size) # Asume que hay un ariali.ttf
    except IOError:
        print("Advertencia: No se encontraron las fuentes Arial. Usando la fuente por defecto.")
        font = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_italic = ImageFont.load_default()

    # Calcular el tamaño de la imagen necesario
    # Usar ImageDraw para obtener el tamaño real del texto
    dummy_img = Image.new('RGB', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    # Calcular dimensiones de cada línea para el ajuste dinámico
    lines = full_text.split('\n')
    max_line_width = 0
    total_text_height = 0
    
    # Calcular la altura y el ancho máximo considerando las diferentes fuentes
    for line in lines:
        current_font = font
        if line.startswith("---"):
            current_font = font_bold
        elif line.strip().startswith(("Fecha:", "Opción:", "Acompañantes:", "Nombres:", "Monto:")): # Modificado para incluir "Opción"
            current_font = font_small
        
        # Calcular el tamaño del cuadro delimitador del texto
        bbox = dummy_draw.textbbox((0, 0), line, font=current_font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1] + 5 # Añadir un pequeño margen entre líneas

        max_line_width = max(max_line_width, line_width)
        total_text_height += line_height

    padding = 20
    img_width = int(max_line_width + (2 * padding))
    img_height = int(total_text_height + (2 * padding)) # Usar la altura calculada
    
    img = Image.new('RGB', (img_width, img_height), color='white')
    d = ImageDraw.Draw(img)

    y_offset = padding
    for line in lines:
        current_font = font
        if line.startswith("---"):
            current_font = font_bold
        elif line.strip().startswith(("Fecha:", "Opción:", "Acompañantes:", "Nombres:", "Monto:")): # Modificado para incluir "Opción"
            current_font = font_small

        d.text((padding, y_offset), line, fill=(0, 0, 0), font=current_font) 
        # Volver a calcular la altura de la línea con la fuente correcta
        bbox = d.textbbox((0,0), line, font=current_font)
        line_height_actual = bbox[3] - bbox[1] + 5
        y_offset += line_height_actual


    # Guardar la imagen en un buffer de memoria
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)

    return send_file(img_byte_arr, mimetype='image/jpeg', as_attachment=True, download_name=f'abono_caminata_{caminata.id}_{participante.id}.jpg')


@caminatas_bp.route('/caminatas/<int:caminata_id>/abono/<int:user_id>/export_txt')
@login_required
def exportar_abono_txt(caminata_id, user_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    participante = User.query.get_or_404(user_id)
    abonos = AbonoCaminata.query.filter_by(caminata_id=caminata.id, user_id=participante.id).order_by(desc(AbonoCaminata.fecha_abono)).all()

    # Convertir las fechas de los abonos a la zona horaria de Costa Rica para exportar
    for abono in abonos:
        if abono.fecha_abono.tzinfo is None:
            abono.fecha_abono = UTC_TZ.localize(abono.fecha_abono)
        abono.fecha_abono = abono.fecha_abono.astimezone(COSTA_RICA_TZ)

    total_abonado = sum(abono.monto_abono for abono in abonos)
    
    # Obtener el último estado del abono para mostrarlo en el resumen
    ultimo_abono = AbonoCaminata.query.filter_by(
        caminata_id=caminata.id,
        user_id=participante.id
    ).order_by(desc(AbonoCaminata.fecha_abono)).first()
    
    estado_general_participante = ultimo_abono.opcion if ultimo_abono else "Sin Abono/Reserva"

    ultima_cantidad_acompanantes = abonos[0].cantidad_acompanantes if abonos else 0
    total_personas = 1 + ultima_cantidad_acompanantes
    total_a_pagar_por_participante = caminata.precio * total_personas
    monto_restante = total_a_pagar_por_participante - total_abonado

    content = []
    content.append("--- Detalle de Abonos para Caminata ---\n\n")
    content.append(f"Caminata: {caminata.nombre}\n")
    # MODIFICACIÓN: Formato con nombre del mes en español y primera letra en mayúscula
    content.append(f"Fecha de Caminata: {caminata.fecha.strftime('%d de %B de %Y')}\n") 
    content.append(f"Actividad: {caminata.actividad}\n")
    content.append(f"Dificultad: {caminata.dificultad if caminata.dificultad else 'N/A'}\n")
    content.append(f"Distancia: {caminata.distancia:.1f} km\n" if caminata.distancia is not None else "Distancia: N/A\n")
    content.append(f"\nParticipante: {participante.nombre} {participante.primer_apellido} ({participante.username})\n")
    content.append(f"Total a Pagar (incluyendo acompañantes): ¢{total_a_pagar_por_participante:,.0f}\n")
    content.append(f"Total Abonado: ¢{total_abonado:,.0f}\n")
    content.append(f"Estado del Participante: {estado_general_participante}\n") # Mostrar el estado general

    # MODIFICACIÓN: Lógica condicional para Monto Restante/Estado Cancelado en TXT
    if monto_restante > 0 and estado_general_participante != "Cancelación":
        content.append(f"Monto Restante: ¢{monto_restante:,.0f}\n")
    content.append("\n--- Historial de Abonos ---\n")

    if abonos:
        for abono in abonos:
            nombres_acom = json.loads(abono.nombres_acompanantes) if abono.nombres_acompanantes else []
            nombres_str = ", ".join(nombres_acom) if nombres_acom else "N/A"
            # MODIFICACIÓN: Mantener el formato numérico para el historial de abonos, si no se desea el nombre del mes aquí
            content.append(f"Fecha: {abono.fecha_abono.strftime('%d/%m/%Y %H:%M')}\n") 
            content.append(f"  Opción: {abono.opcion}\n") 
            content.append(f"  Cantidad de Acompañantes: {abono.cantidad_acompanantes}\n")
            content.append(f"  Nombres de Acompañantes: {nombres_str}\n")
            content.append(f"  Monto Abonado: ¢{abono.monto_abono:,.0f}\n")
    else:
        content.append("No hay abonos registrados para este participante en esta caminata aún.\n")

    txt_output = "".join(content)
    
    response = current_app.make_response(txt_output)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Content-Disposition'] = f'attachment; filename=abono_caminata_{caminata.id}_{participante.id}.txt'
    return response


# --- RUTAS DE EXPORTACIÓN DE DETALLE DE CAMINATA ---

# Helper para formatear los detalles de la caminata en texto plano
def _get_caminata_details_as_text(caminata, participantes_con_info=None):
    """Genera una cadena de texto con los detalles de la caminata para exportación.
    Incluye información de participantes, sus acompañantes y su estado de abono,
    filtrando los valores 'N/A' y '0'.
    """
    if participantes_con_info is None:
        participantes_con_info = []

    details = []

    # Helper function to check if a value should be excluded
    def should_exclude(value):
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return True
        if isinstance(value, (int, float)) and value == 0:
            return True
        return False

    # Detalle de la Caminata
    if caminata.nombre and not should_exclude(caminata.nombre):
        details.append(f"Detalle de la Caminata: {caminata.nombre}")
        details.append(f"----------------------------------------")

    if caminata.actividad and not should_exclude(caminata.actividad):
        details.append(f"Actividad: {caminata.actividad}")
    if caminata.etapa and not should_exclude(caminata.etapa):
        details.append(f"Etapa: {caminata.etapa}")
    if caminata.precio is not None and not should_exclude(caminata.precio):
        details.append(f"Precio: {caminata.precio:,.0f} CRC")
    if caminata.fecha:
        details.append(f"Fecha: {caminata.fecha.strftime('%d de %B de %Y')}")
    if caminata.hora_salida and not should_exclude(caminata.hora_salida):
        details.append(f"Hora de Salida: {caminata.hora_salida.strftime('%H:%M')}")
    if caminata.hora_regreso and not should_exclude(caminata.hora_regreso):
        details.append(f"Hora de Regreso: {caminata.hora_regreso.strftime('%H:%M')}")
    if caminata.duracion_horas is not None and not should_exclude(caminata.duracion_horas):
        details.append(f"Duración (horas): {caminata.duracion_horas}")
    if caminata.lugar_salida and not should_exclude(caminata.lugar_salida):
        details.append(f"Lugar de Salida: {caminata.lugar_salida}")
    if caminata.dificultad and not should_exclude(caminata.dificultad):
        details.append(f"Dificultad: {caminata.dificultad}")
    if caminata.distancia is not None and not should_exclude(caminata.distancia):
        details.append(f"Distancia: {caminata.distancia} km")
    if caminata.capacidad_minima is not None and not should_exclude(caminata.capacidad_minima):
        details.append(f"Capacidad Mínima: {caminata.capacidad_minima}")
    if caminata.capacidad_maxima is not None and not should_exclude(caminata.capacidad_maxima):
        details.append(f"Capacidad Máxima: {caminata.capacidad_maxima}")
    if caminata.nombre_guia and not should_exclude(caminata.nombre_guia):
        details.append(f"Nombre del Guía: {caminata.nombre_guia}")
    if caminata.se_requiere and not should_exclude(caminata.se_requiere):
        details.append(f"Se Requiere: {caminata.se_requiere}")
    if caminata.provincia and not should_exclude(caminata.provincia):
        details.append(f"Provincia: {caminata.provincia}")
    if caminata.tipo_terreno:
        terreno_list = json.loads(caminata.tipo_terreno)
        if terreno_list and not should_exclude(terreno_list):
            details.append(f"Tipo de Terreno: {', '.join(terreno_list)}")
    if caminata.otras_senas_terreno and not should_exclude(caminata.otras_senas_terreno):
        details.append(f"Otras Señas del Terreno: {caminata.otras_senas_terreno}")
    if caminata.tipo_transporte:
        transporte_list = json.loads(caminata.tipo_transporte)
        if transporte_list and not should_exclude(transporte_list):
            details.append(f"Tipo de Transporte: {', '.join(transporte_list)}")
    if caminata.incluye:
        incluye_list = json.loads(caminata.incluye)
        if incluye_list and not should_exclude(incluye_list):
            details.append(f"Incluye: {', '.join(incluye_list)}")
    if caminata.cuenta_con:
        cuenta_con_list = json.loads(caminata.cuenta_con)
        if cuenta_con_list and not should_exclude(cuenta_con_list):
            details.append(f"Cuenta con: {', '.join(cuenta_con_list)}")
    if caminata.tipo_clima and not should_exclude(caminata.tipo_clima):
        details.append(f"Tipo de Clima: {caminata.tipo_clima}")
    if caminata.altura_maxima is not None and not should_exclude(caminata.altura_maxima):
        details.append(f"Altura Máxima: {caminata.altura_maxima} m")
    if caminata.altura_minima is not None and not should_exclude(caminata.altura_minima):
        details.append(f"Altura Mínima: {caminata.altura_minima} m")
    if caminata.altura_positiva is not None and not should_exclude(caminata.altura_positiva):
        details.append(f"Altura Positiva: {caminata.altura_positiva} m")
    if caminata.altura_negativa is not None and not should_exclude(caminata.altura_negativa):
        details.append(f"Altura Negativa: {caminata.altura_negativa} m")
    if caminata.otros_datos and not should_exclude(caminata.otros_datos):
        clean_otros_datos = BeautifulSoup(caminata.otros_datos, "html.parser").get_text()
        if clean_otros_datos.strip(): 
            details.append(f"\nOtros Datos:\n{clean_otros_datos.strip()}")

    details.append("\n--- Participantes de la Caminata ---")
    if participantes_con_info: 
        participant_counter = 1
        for participant_info in participantes_con_info:
            status_text = ""
            if participant_info.get('estado_abono'):
                if participant_info['estado_abono'] == 'Reserva':
                    status_text = " (Estado: RESERVADO)"
                elif participant_info['estado_abono'] == 'Abono':
                    status_text = " (Estado: ABONO)"
                elif participant_info['estado_abono'] == 'Cancelación':
                    status_text = " (Estado: CANCELADO)"
            
            # Asegurarse de que el nombre de participante y el nombre de usuario no estén vacíos/N/A
            if (participant_info['nombre'] and not should_exclude(participant_info['nombre'])) and \
               (participant_info['primer_apellido'] and not should_exclude(participant_info['primer_apellido'])) and \
               (participant_info['username'] and not should_exclude(participant_info['username'])):
                details.append(f"  {participant_counter}. {participant_info['nombre']} {participant_info['primer_apellido']} ({participant_info['username']}){status_text}")
                
                if participant_info.get('email') and not should_exclude(participant_info['email']):
                    details.append(f"    Email: {participant_info['email']}")
                if participant_info.get('telefono') and not should_exclude(participant_info['telefono']):
                    details.append(f"    Teléfono: {participant_info['telefono']}")
                
                # Si hay acompañantes registrados para este participante
                if participant_info.get('acompanantes'):
                    # Filtrar nombres de acompañantes vacíos/None
                    filtered_companions = [c for c in participant_info['acompanantes'] if c and not should_exclude(c)]
                    if filtered_companions:
                        companion_sub_counter = 1
                        details.append(f"    Acompañante(s) registrado(s) por {participant_info['nombre']}:")
                        for companion_name in filtered_companions:
                            details.append(f"      {companion_sub_counter}. {companion_name}")
                            companion_sub_counter += 1
                participant_counter += 1
    else:
        details.append("No hay participantes registrados para esta caminata aún.")

    return "\n".join(details)


@caminatas_bp.route('/caminatas/exportar/pdf/<int:caminata_id>', methods=['GET'])
@login_required
def exportar_caminata_pdf(caminata_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    
    # Replicar la lógica de detalle_caminata para obtener participantes_con_info
    participantes_con_info = []
    for participant in caminata.participantes:
        ultimo_abono = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).order_by(desc(AbonoCaminata.fecha_abono)).first()
        estado_abono = ultimo_abono.opcion if ultimo_abono else None 

        companion_names_for_participant = set()
        abonos_del_participante = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).all()
        for abono in abonos_del_participante:
            if abono.nombres_acompanantes:
                try: 
                    names_list = json.loads(abono.nombres_acompanantes)
                    for name in names_list:
                        if name.strip():
                            companion_names_for_participant.add(name.strip())
                except json.JSONDecodeError:
                    print(f"Advertencia: No se pudo decodificar JSON para nombres_acompanantes en exportación PDF: {abono.nombres_acompanantes}")
                    pass 
        
        participantes_con_info.append({
            'id': participant.id,
            'nombre': participant.nombre,
            'primer_apellido': participant.primer_apellido,
            'username': participant.username,
            'email': participant.email,
            'telefono': participant.telefono,
            'estado_abono': estado_abono,
            'acompanantes': list(companion_names_for_participant)
        })

    caminata_text = _get_caminata_details_as_text(caminata, participantes_con_info) 

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(0, 10, "Detalles de la Caminata", 0, 1, 'C')
    pdf.ln(10) 

    
    for line in caminata_text.split('\n'):
        # Ajustar el tamaño de la fuente si la línea es demasiado larga
        if len(line) > 70: 
            pdf.set_font("Arial", size=9)
        elif line.strip().startswith(tuple(str(i) + '.' for i in range(1, 10))): # Para participantes numerados (1. 2. etc.)
            pdf.set_font("Arial", 'B', 10) # Negrita para participantes
        elif line.startswith('    Email:') or line.startswith('    Teléfono:'): # Para contactos
            pdf.set_font("Arial", '', 9)
        elif line.startswith('    Acompañante(s)'): # Para encabezado de acompañantes
            pdf.set_font("Arial", 'I', 9) # Itálica para el encabezado
        elif line.strip().startswith(tuple('      ' + str(i) + '.' for i in range(1, 10))): # Para nombres de acompañantes numerados
            pdf.set_font("Arial", '', 9)
        else:
            pdf.set_font("Arial", size=10)

        pdf.multi_cell(0, 7, line.encode('latin-1', 'replace').decode('latin-1'))
    
    response = current_app.response_class(pdf.output(dest='S').encode('latin1'), mimetype='application/pdf')
    response.headers.set('Content-Disposition', 'attachment', filename=f'caminata_{caminata.nombre}.pdf')
    return response

@caminatas_bp.route('/caminatas/exportar/txt/<int:caminata_id>', methods=['GET'])
@login_required
def exportar_caminata_txt(caminata_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    
    # Replicar la lógica de detalle_caminata para obtener participantes_con_info
    participantes_con_info = []
    for participant in caminata.participantes:
        ultimo_abono = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).order_by(desc(AbonoCaminata.fecha_abono)).first()
        estado_abono = ultimo_abono.opcion if ultimo_abono else None 

        companion_names_for_participant = set()
        abonos_del_participante = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).all()
        for abono in abonos_del_participante:
            if abono.nombres_acompanantes:
                try: 
                    names_list = json.loads(abono.nombres_acompanantes)
                    for name in names_list:
                        if name.strip():
                            companion_names_for_participant.add(name.strip())
                except json.JSONDecodeError:
                    print(f"Advertencia: No se pudo decodificar JSON para nombres_acompanantes en exportación TXT: {abono.nombres_acompanantes}")
                    pass 
        
        participantes_con_info.append({
            'id': participant.id,
            'nombre': participant.nombre,
            'primer_apellido': participant.primer_apellido,
            'username': participant.username,
            'email': participant.email,
            'telefono': participant.telefono,
            'estado_abono': estado_abono,
            'acompanantes': list(companion_names_for_participant)
        })

    caminata_text = _get_caminata_details_as_text(caminata, participantes_con_info) 

    buffer = io.BytesIO()
    buffer.write(caminata_text.encode('utf-8'))
    buffer.seek(0)

    response = current_app.response_class(buffer.getvalue(), mimetype='text/plain')
    response.headers.set('Content-Disposition', 'attachment', filename=f'caminata_{caminata.nombre}.txt')
    return response

@caminatas_bp.route('/caminatas/exportar/jpg/<int:caminata_id>', methods=['GET'])
@login_required
def exportar_caminata_jpg(caminata_id):
    caminata = Caminata.query.get_or_404(caminata_id)
    
    # Replicar la lógica de detalle_caminata para obtener participantes_con_info
    participantes_con_info = []
    for participant in caminata.participantes:
        ultimo_abono = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).order_by(desc(AbonoCaminata.fecha_abono)).first()
        estado_abono = ultimo_abono.opcion if ultimo_abono else None 

        companion_names_for_participant = set()
        abonos_del_participante = AbonoCaminata.query.filter_by(
            caminata_id=caminata.id,
            user_id=participant.id
        ).all()
        for abono in abonos_del_participante:
            if abono.nombres_acompanantes:
                try: 
                    names_list = json.loads(abono.nombres_acompanantes)
                    for name in names_list:
                        if name.strip():
                            companion_names_for_participant.add(name.strip())
                except json.JSONDecodeError:
                    print(f"Advertencia: No se pudo decodificar JSON para nombres_acompanantes en exportación JPG: {abono.nombres_acompanantes}")
                    pass 
        
        participantes_con_info.append({
            'id': participant.id,
            'nombre': participant.nombre,
            'primer_apellido': participant.primer_apellido,
            'username': participant.username,
            'email': participant.email,
            'telefono': participant.telefono,
            'estado_abono': estado_abono,
            'acompanantes': list(companion_names_for_participant)
        })

    caminata_text = _get_caminata_details_as_text(caminata, participantes_con_info) 

    temp_img = Image.new('RGB', (1, 1))
    d_temp = ImageDraw.Draw(temp_img)

    font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'arial.ttf')
    try:
        font = ImageFont.truetype(font_path, 18)
        font_small = ImageFont.truetype(font_path, 14) # Fuente más pequeña para detalles
        font_bold = ImageFont.truetype(os.path.join(current_app.root_path, 'static', 'fonts', 'arialbd.ttf'), 18) # Fuente negrita
        font_italic = ImageFont.truetype(os.path.join(current_app.root_path, 'static', 'fonts', 'ariali.ttf'), 14) # Fuente itálica
    except IOError:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_italic = ImageFont.load_default()
        print(f"ADVERTENCIA: No se encontró la fuente en {font_path}. Usando la fuente por defecto.")

    lines = caminata_text.split('\n')
    
    # Calcular la altura necesaria para la imagen de forma más dinámica
    total_text_height = 0
    max_line_width = 0
    for line in lines:
        current_font = font
        if line.startswith("--- Participantes de la Caminata ---"):
            current_font = font_bold
        # Aquí se añade la lógica para detectar líneas de participantes con el estado
        elif line.strip().startswith(tuple(str(i) + '.' for i in range(1, 100))): 
            current_font = font_bold
        elif line.startswith("    Email:") or line.startswith("    Teléfono:"):
            current_font = font_small
        elif line.startswith("    Acompañante(s)"):
            current_font = font_italic
        elif line.strip().startswith(tuple('      ' + str(i) + '.' for i in range(1, 100))):
            current_font = font_small

        # Usar textbbox para calcular el tamaño exacto del texto
        bbox = d_temp.textbbox((0,0), line, font=current_font)
        line_height = bbox[3] - bbox[1] + 5 # Alto del texto más un pequeño padding
        line_width = bbox[2] - bbox[0]
        
        total_text_height += line_height
        if line_width > max_line_width:
            max_line_width = line_width
    
    padding = 30
    img_width = int(max_line_width + (2 * padding))
    img_height = int(total_text_height + (2 * padding)) # Usar la altura calculada
    
    img = Image.new('RGB', (img_width, img_height), color='white')
    d = ImageDraw.Draw(img)

    y_offset = padding
    for line in lines:
        current_font = font
        if line.startswith("--- Participantes de la Caminata ---"):
            current_font = font_bold
        # Aquí se añade la lógica para detectar líneas de participantes con el estado
        elif line.strip().startswith(tuple(str(i) + '.' for i in range(1, 100))):
            current_font = font_bold
        elif line.startswith("    Email:") or line.startswith("    Teléfono:"):
            current_font = font_small
        elif line.startswith("    Acompañante(s)"):
            current_font = font_italic
        elif line.strip().startswith(tuple('      ' + str(i) + '.' for i in range(1, 100))):
            current_font = font_small

        d.text((padding, y_offset), line, fill=(0, 0, 0), font=current_font) 
        # Volver a calcular la altura de la línea con la fuente correcta
        bbox = d.textbbox((0,0), line, font=current_font)
        line_height_actual = bbox[3] - bbox[1] + 5
        y_offset += line_height_actual

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)

    response = current_app.response_class(buffer.getvalue(), mimetype='image/jpeg')
    response.headers.set('Content-Disposition', 'attachment', filename=f'caminata_{caminata.nombre}.jpg')
    return response

