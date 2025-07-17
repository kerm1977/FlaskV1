from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from models import db, InternationalTravel, User # Importa los modelos necesarios
from datetime import datetime, date
import json # Para manejar los datos JSON de la checklist
import io # Para manejar archivos en memoria

# Importaciones adicionales para PDF y JPG
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from PIL import Image, ImageDraw, ImageFont


# Crear un Blueprint para la gestión de viajes internacionales
intern_bp = Blueprint('intern', __name__, url_prefix='/intern')

# Decorador para requerir inicio de sesión
def login_required_intern(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Lista de opciones para aerolíneas (puedes expandirla)
AEROLINEA_OPTIONS = sorted([ # Ordenar alfabéticamente
    "Avianca", "American Airlines", "Copa", "Volaris", "Jetblue", "Sansa", "Spirit", "United", "Wingo", "KLM", "Iberia", "Lufthansa", "Latam Airlines", "IberoJet", "Delta", "AirFrance", "Alaska", "AeroMéxico", "Arajet", "Air Canadá", "Airtransat", "Green Airways", "Southwest", "Edelweiss", "Frontier", "GOL"
])

# Lista de opciones para países de América (puedes expandirla)
PAIS_DESTINO_AMERICA_OPTIONS = sorted([ # Ordenar alfabéticamente
    "Panamá", "Nicaragua", "El Salvador", "Honduras", "Guatemala", "México", "Estados Unidos", "Canadá", "Alaska", "Colombia", "Venezuela", "Ecuador", "Perú", "Bolivia", "Paraguay", "Argentina", "Brazil", "Chile", "Belice", "Guyana", "Surinam", "Guyana Francesa"
])

# Opciones para campos Si/No/Aplica
SI_NO_APLICA_OPTIONS = ["No Aplica", "Si"]

# Opciones para campos Necesita VISA
NECESITA_VISA_OPTIONS = ["No Aplica", "Si"]

# Lista de opciones para Declaración de Tarjetas
DECLARACION_TARJETAS_OPTIONS = sorted([
    "Banco de Costa Rica (BCR)", "Banco Nacional de Costa Rica (BNCR)", "Banco Popular",
    "Mucap", "Mutual", "BAC Credomatic", "Banco Cathay", "Banco BCT", "Banco CMB",
    "Banco Davivienda", "Banco General", "Banco Improsa", "Banco Lafise", "Banco Promérica",
    "Prival Bank", "Scotiabank", "Coopealianza", "Coopeande", "CoopeAnde No. 1",
    "CoopeAnde No. 2", "CoopeAnde No. 3", "CoopeAnde No. 4", "CoopeAnde No. 5",
    "CoopeAnde No. 6", "CoopeAnde No. 7", "CoopeAnde No. 8", "CoopeAnde No. 9",
    "CoopeAnde No. 10", "CoopeAnde No. 11", "CoopeCaja", "Caja de ANDE", "COOPENAE",
    "COOPEUCHA", "COOPESANRAMON", "COOPESERVIDORES", "COOPEUNA", "CREDECOOP"
])

# Filtro personalizado para formatear fechas
@intern_bp.app_template_filter('format_date')
def format_date_filter(value):
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    return value


# Ruta principal para listar viajes internacionales
@intern_bp.route('/')
@login_required_intern
def index():
    travels = InternationalTravel.query.all()
    # CORREGIDO: Se cambia 'listar_intern.html' a 'ver_intern.html'
    return render_template('ver_intern.html', travels=travels)

# Ruta para crear un nuevo viaje internacional
@intern_bp.route('/crear', methods=['GET', 'POST'])
@login_required_intern
def crear_intern():
    contact_options = User.query.order_by(User.nombre).all()

    if request.method == 'POST':
        # Obtener datos del formulario
        contact_id = request.form.get('contact_id')
        
        # Datos de contacto (manual o de usuario existente)
        if contact_id and contact_id != 'manual':
            # Si se seleccionó un contacto existente
            selected_contact = User.query.get(contact_id)
            if not selected_contact:
                flash('El contacto seleccionado no es válido.', 'danger')
                # Mantener los datos del formulario si hay un error para que el usuario no los pierda
                form_data = request.form.to_dict(flat=False) # Convierte a diccionario para rellenar
                
                # Manejar los campos multiselect en form_data para rellenar el formulario
                form_data['declaracion_tarjetas'] = request.form.getlist('declaracion_tarjetas')
                form_data['pais_destino_america'] = request.form.getlist('pais_destino_america')
                
                for key, value in form_data.items():
                    if isinstance(value, list) and len(value) == 1:
                        form_data[key] = value[0] # Desempacar si es lista de un solo elemento
                return render_template('crear_intern.html', 
                                   contact_options=contact_options, 
                                   aerolinea_options=AEROLINEA_OPTIONS, 
                                   pais_destino_america_options=PAIS_DESTINO_AMERICA_OPTIONS,
                                   si_no_aplica_options=SI_NO_APLICA_OPTIONS,
                                   necesita_visa_options=NECESITA_VISA_OPTIONS,
                                   declaracion_tarjetas_options=DECLARACION_TARJETAS_OPTIONS, 
                                   form_data=form_data)


            new_travel = InternationalTravel(contact_id=selected_contact.id)
            # Asegurarse de que los campos manuales estén vacíos si se usa un contacto existente
            new_travel.nombre_contacto_manual = None
            new_travel.apellido_contacto_manual = None
            new_travel.telefono_contacto_manual = None
            new_travel.email_contacto_manual = None
        else:
            # Si se ingresaron datos manualmente o se seleccionó 'manual'
            new_travel = InternationalTravel(
                nombre_contacto_manual=request.form.get('nombre_contacto_manual'),
                apellido_contacto_manual=request.form.get('apellido_contacto_manual'),
                telefono_contacto_manual=request.form.get('telefono_contacto_manual'),
                email_contacto_manual=request.form.get('email_contacto_manual')
            )
            # Asegurarse de que contact_id sea None si se usa contacto manual
            new_travel.contact_id = None

        # Información General del Viaje
        # MODIFICADO: Obtener lista y convertir a JSON string para almacenar
        new_travel.declaracion_tarjetas = json.dumps(request.form.getlist('declaracion_tarjetas')) 
        fecha_reporte_str = request.form.get('fecha_reporte')
        new_travel.fecha_reporte = datetime.strptime(fecha_reporte_str, '%Y-%m-%d').date() if fecha_reporte_str else None
        new_travel.vigencia_pasaporte = request.form.get('vigencia_pasaporte')
        # MODIFICADO: Obtener lista y convertir a JSON string para almacenar
        new_travel.pais_destino_america = json.dumps(request.form.getlist('pais_destino_america'))

        # Vuelo de IDA
        new_travel.aerolinea_ida = request.form.get('aerolinea_ida')
        fecha_ida_str = request.form.get('fecha_vuelo_ida')
        new_travel.fecha_vuelo_ida = datetime.strptime(fecha_ida_str, '%Y-%m-%d').date() if fecha_ida_str else None
        new_travel.hora_salida_ida = request.form.get('hora_salida_ida')
        new_travel.hora_llegada_ida = request.form.get('hora_llegada_ida')
        new_travel.numero_vuelo_ida = request.form.get('numero_vuelo_ida')
        new_travel.codigo_confirmacion_ida = request.form.get('codigo_confirmacion_ida')
        new_travel.numero_asiento_ida = request.form.get('numero_asiento_ida')
        new_travel.check_in_ida = request.form.get('check_in_ida')
        new_travel.check_out_ida = request.form.get('check_out_ida')
        new_travel.total_tickete_ida = float(request.form.get('total_tickete_ida')) if request.form.get('total_tickete_ida') else None
        new_travel.impuesto_incluido_ida = request.form.get('impuesto_incluido_ida')
        new_travel.nombre_aeropuerto_ida = request.form.get('nombre_aeropuerto_ida')
        new_travel.paises_escala_ida = request.form.get('paises_escala_ida')
        new_travel.aeropuerto_escala_ida = request.form.get('aeropuerto_escala_ida')
        new_travel.carga_permitida_maleta_mano_ida = request.form.get('carga_permitida_maleta_mano_ida')
        new_travel.precio_maleta_mano_ida = float(request.form.get('precio_maleta_mano_ida')) if request.form.get('precio_maleta_mano_ida') else None
        new_travel.necesita_visa_ida = request.form.get('necesita_visa_ida')
        new_travel.telefono1_aeropuerto_ida = request.form.get('telefono1_aeropuerto_ida')
        new_travel.telefono2_aeropuerto_ida = request.form.get('telefono2_aeropuerto_ida')
        new_travel.telefono1_aerolinea_ida = request.form.get('telefono1_aerolinea_ida')
        new_travel.telefono2_aerolinea_ida = request.form.get('telefono2_aerolinea_ida')
        new_travel.telefono1_embajada_consulado_ida = request.form.get('telefono1_embajada_consulado_ida')
        new_travel.telefono2_embajada_consulado_ida = request.form.get('telefono2_embajada_consulado_ida')

        # Vuelo de VUELTA
        new_travel.aerolinea_vuelta = request.form.get('aerolinea_vuelta')
        fecha_vuelta_str = request.form.get('fecha_vuelo_vuelta')
        new_travel.fecha_vuelo_vuelta = datetime.strptime(fecha_vuelta_str, '%Y-%m-%d').date() if fecha_vuelta_str else None
        new_travel.hora_salida_vuelta = request.form.get('hora_salida_vuelta')
        new_travel.hora_llegada_vuelta = request.form.get('hora_llegada_vuelta')
        new_travel.cantidad_dias_vuelta = int(request.form.get('cantidad_dias_vuelta')) if request.form.get('cantidad_dias_vuelta') else None
        new_travel.numero_vuelo_vuelta = request.form.get('numero_vuelo_vuelta')
        new_travel.codigo_confirmacion_vuelta = request.form.get('codigo_confirmacion_vuelta')
        new_travel.numero_asiento_vuelta = request.form.get('numero_asiento_vuelta')
        new_travel.check_in_vuelta = request.form.get('check_in_vuelta')
        new_travel.check_out_vuelta = request.form.get('check_out_vuelta')
        new_travel.total_tickete_pp_vuelta = float(request.form.get('total_tickete_pp_vuelta')) if request.form.get('total_tickete_pp_vuelta') else None
        new_travel.impuesto_incluido_vuelta = request.form.get('impuesto_incluido_vuelta')
        new_travel.nombre_aeropuerto_vuelta = request.form.get('nombre_aeropuerto_vuelta')
        new_travel.paises_escala_vuelta = request.form.get('paises_escala_vuelta')
        new_travel.aeropuerto_escala_vuelta = request.form.get('aeropuerto_escala_vuelta')
        new_travel.carga_permitida_maleta_mano_vuelta = request.form.get('carga_permitida_maleta_mano_vuelta')
        new_travel.precio_maleta_mano_vuelta = float(request.form.get('precio_maleta_mano_vuelta')) if request.form.get('precio_maleta_mano_vuelta') else None
        new_travel.necesita_visa_vuelta = request.form.get('necesita_visa_vuelta')
        new_travel.telefono1_aeropuerto_vuelta = request.form.get('telefono1_aeropuerto_vuelta')
        new_travel.telefono2_aeropuerto_vuelta = request.form.get('telefono2_aeropuerto_vuelta')
        new_travel.telefono1_aerolinea_vuelta = request.form.get('telefono1_aerolinea_vuelta')
        new_travel.telefono2_aerolinea_vuelta = request.form.get('telefono2_aerolinea_vuelta')
        new_travel.telefono1_embajada_consulado_vuelta = request.form.get('telefono1_embajada_consulado_vuelta')
        new_travel.telefono2_embajada_consulado_vuelta = request.form.get('telefono2_embajada_consulado_vuelta')
        new_travel.otro_telefono_vuelta = request.form.get('otro_telefono_vuelta')
        new_travel.nombre_estadia_vuelta = request.form.get('nombre_estadia_vuelta')
        new_travel.telefono1_estadia_vuelta = request.form.get('telefono1_estadia_vuelta')
        new_travel.telefono2_estadia_vuelta = request.form.get('telefono2_estadia_vuelta')

        # Vuelo de ESCALA (opcional)
        new_travel.otra_aerolinea_escala = request.form.get('otra_aerolinea_escala')
        fecha_escala_str = request.form.get('fecha_vuelo_escala')
        new_travel.fecha_vuelo_escala = datetime.strptime(fecha_escala_str, '%Y-%m-%d').date() if fecha_escala_str else None
        new_travel.hora_salida_escala = request.form.get('hora_salida_escala')
        new_travel.hora_llegada_escala = request.form.get('hora_llegada_escala')
        new_travel.numero_vuelo_escala = request.form.get('numero_vuelo_escala')
        new_travel.codigo_confirmacion_escala = request.form.get('codigo_confirmacion_escala')
        new_travel.numero_asiento_escala = request.form.get('numero_asiento_escala')
        new_travel.enlace_telefono_check_in_escala = request.form.get('enlace_telefono_check_in_escala')
        new_travel.enlace_telefono_check_out_escala = request.form.get('enlace_telefono_check_out_escala')
        new_travel.total_tickete_pp_escala = float(request.form.get('total_tickete_pp_escala')) if request.form.get('total_tickete_pp_escala') else None
        new_travel.impuesto_incluido_escala = request.form.get('impuesto_incluido_escala')
        new_travel.nombre_aeropuerto_escala = request.form.get('nombre_aeropuerto_escala')
        new_travel.paises_escala_escala = request.form.get('paises_escala_escala')
        new_travel.aeropuerto_escala_escala = request.form.get('aeropuerto_escala_escala')
        new_travel.carga_permitida_maleta_mano_escala = request.form.get('carga_permitida_maleta_mano_escala')
        new_travel.precio_maleta_mano_escala = float(request.form.get('precio_maleta_mano_escala')) if request.form.get('precio_maleta_mano_escala') else None
        new_travel.necesita_visa_escala = request.form.get('necesita_visa_escala')
        new_travel.telefono1_aeropuerto_escala = request.form.get('telefono1_aeropuerto_escala')
        new_travel.telefono2_aeropuerto_escala = request.form.get('telefono2_aeropuerto_escala')
        new_travel.telefono1_aerolinea_escala = request.form.get('telefono1_aerolinea_escala')
        new_travel.telefono2_aerolinea_escala = request.form.get('telefono2_aerolinea_escala')
        new_travel.telefono1_embajada_consulado_escala = request.form.get('telefono1_embajada_consulado_escala')
        new_travel.telefono2_embajada_consulado_escala = request.form.get('telefono2_embajada_consulado_escala')
        new_travel.otro_telefono_escala = request.form.get('otro_telefono_escala')
        new_travel.nombre_estadia_escala = request.form.get('nombre_estadia_escala')
        new_travel.telefono1_estadia_escala = request.form.get('telefono1_estadia_escala')
        new_travel.telefono2_estadia_escala = request.form.get('telefono2_estadia_escala')
        new_travel.otros_detalles_escala = request.form.get('otros_detalles_escala')

        # Información Adicional de Contacto y Estadía (general)
        new_travel.otro_telefono = request.form.get('otro_telefono')
        new_travel.nombre_estadia = request.form.get('nombre_estadia')
        new_travel.telefono1_estadia = request.form.get('telefono1_estadia')
        new_travel.telefono2_estadia = request.form.get('telefono2_estadia')
        new_travel.estadia_email = request.form.get('estadia_email')
        new_travel.otra_estadia_nombre = request.form.get('otra_estadia_nombre')
        new_travel.telefono1_otra_estadia = request.form.get('telefono1_otra_estadia')
        new_travel.telefono2_otra_estadia = request.form.get('telefono2_otra_estadia')

        # Tour Operador / Guía
        new_travel.nombre_tour_operador = request.form.get('nombre_tour_operador')
        new_travel.telefono_tour_operador1 = request.form.get('telefono_tour_operador1')
        new_travel.telefono_tour_operador2 = request.form.get('telefono_tour_operador2')
        new_travel.email_tour_operador = request.form.get('email_tour_operador')
        new_travel.total_operador_pp = float(request.form.get('total_operador_pp')) if request.form.get('total_operador_pp') else None

        # Contacto de Transporte
        new_travel.contacto_transporte_responsable = request.form.get('contacto_transporte_responsable')
        new_travel.contacto_transporte_telefono = request.form.get('contacto_transporte_telefono')
        new_travel.contacto_transporte_otro_telefono = request.form.get('contacto_transporte_otro_telefono')
        new_travel.contacto_transporte_otros_detalles = request.form.get('contacto_transporte_otros_detalles')

        # Recordatorios (checklist JSON)
        recordatorios_json_str = request.form.get('recordatorios_json')
        if recordatorios_json_str:
            try:
                new_travel.recordatorios_json = recordatorios_json_str
            except json.JSONDecodeError:
                new_travel.recordatorios_json = '[]' # Default to empty array on error
        else:
            new_travel.recordatorios_json = '[]'
        
        # Notas Generales (CKEditor)
        new_travel.notas_generales_ckeditor = request.form.get('notas_generales_ckeditor')

        try:
            db.session.add(new_travel)
            db.session.commit()
            flash('Viaje internacional creado exitosamente!', 'success')
            return redirect(url_for('intern.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el viaje: {e}', 'danger')
            # Puedes loggear el error completo para depuración
            print(f"Error al crear viaje internacional: {e}")
            # Re-renderiza el formulario con los datos enviados para que el usuario no los pierda
            form_data = request.form.to_dict(flat=False) # Convierte a diccionario para rellenar
            
            # Asegurarse de que los campos multiselect en form_data sean listas
            form_data['declaracion_tarjetas'] = request.form.getlist('declaracion_tarjetas')
            form_data['pais_destino_america'] = request.form.getlist('pais_destino_america')

            for key, value in form_data.items():
                if isinstance(value, list) and len(value) == 1:
                    form_data[key] = value[0] # Desempacar si es lista de un solo elemento
            return render_template('crear_intern.html', 
                                   contact_options=contact_options, 
                                   aerolinea_options=AEROLINEA_OPTIONS, 
                                   pais_destino_america_options=PAIS_DESTINO_AMERICA_OPTIONS,
                                   si_no_aplica_options=SI_NO_APLICA_OPTIONS,
                                   necesita_visa_options=NECESITA_VISA_OPTIONS,
                                   declaracion_tarjetas_options=DECLARACION_TARJETAS_OPTIONS, 
                                   form_data=form_data)


    return render_template(
        'crear_intern.html',
        contact_options=contact_options,
        aerolinea_options=AEROLINEA_OPTIONS,
        pais_destino_america_options=PAIS_DESTINO_AMERICA_OPTIONS,
        si_no_aplica_options=SI_NO_APLICA_OPTIONS,
        necesita_visa_options=NECESITA_VISA_OPTIONS,
        declaracion_tarjetas_options=DECLARACION_TARJETAS_OPTIONS 
    )

# Ruta para ver detalles de un viaje internacional
@intern_bp.route('/detalle/<int:travel_id>')
@login_required_intern
def detalle_intern(travel_id):
    travel = InternationalTravel.query.get_or_404(travel_id)
    
    # MODIFICADO: Convertir JSON string a lista para rellenar el formulario en GET request
    # Asegúrate de que travel.declaracion_tarjetas sea una cadena JSON válida. Si es None o vacía, usa '[]'.
    try:
        selected_declaracion_tarjetas = json.loads(travel.declaracion_tarjetas or '[]')
    except json.JSONDecodeError:
        selected_declaracion_tarjetas = [] # Default to empty array on error

    try:
        selected_pais_destino_america = json.loads(travel.pais_destino_america or '[]')
    except json.JSONDecodeError:
        selected_pais_destino_america = [] # Default to empty array on error
    
    # También asegurar que recordatorios_json se parsea correctamente para la plantilla
    try:
        recordatorios_data = json.loads(travel.recordatorios_json or '[]')
    except json.JSONDecodeError:
        recordatorios_data = [] # Default to empty array on error


    return render_template('detalle_intern.html', 
                           travel=travel,
                           selected_declaracion_tarjetas=selected_declaracion_tarjetas, # Pasa las opciones seleccionadas
                           selected_pais_destino_america=selected_pais_destino_america, # Pasa las opciones seleccionadas
                           recordatorios_data=recordatorios_data) # Pasa los recordatorios parseados

# Ruta para editar un viaje internacional existente
@intern_bp.route('/editar/<int:travel_id>', methods=['GET', 'POST'])
@login_required_intern
def editar_intern(travel_id):
    travel = InternationalTravel.query.get_or_404(travel_id)
    contact_options = User.query.order_by(User.nombre).all()

    if request.method == 'POST':
        # Obtener datos del formulario
        contact_id = request.form.get('contact_id')

        # Manejo de contacto
        if contact_id and contact_id != 'manual':
            travel.contact_id = contact_id
            travel.nombre_contacto_manual = None
            travel.apellido_contacto_manual = None
            travel.telefono_contacto_manual = None
            travel.email_contacto_manual = None
        else:
            travel.contact_id = None
            travel.nombre_contacto_manual = request.form.get('nombre_contacto_manual')
            travel.apellido_contacto_manual = request.form.get('apellido_contacto_manual')
            travel.telefono_contacto_manual = request.form.get('telefono_contacto_manual')
            travel.email_contacto_manual = request.form.get('email_contacto_manual')

        # Actualizar campos
        # MODIFICADO: Obtener lista y convertir a JSON string para almacenar
        travel.declaracion_tarjetas = json.dumps(request.form.getlist('declaracion_tarjetas'))
        fecha_reporte_str = request.form.get('fecha_reporte')
        travel.fecha_reporte = datetime.strptime(fecha_reporte_str, '%Y-%m-%d').date() if fecha_reporte_str else None
        travel.vigencia_pasaporte = request.form.get('vigencia_pasaporte') # Ahora es Código de Reporte
        # MODIFICADO: Obtener lista y convertir a JSON string para almacenar
        travel.pais_destino_america = json.dumps(request.form.getlist('pais_destino_america'))

        # Vuelo de IDA
        travel.aerolinea_ida = request.form.get('aerolinea_ida')
        fecha_ida_str = request.form.get('fecha_vuelo_ida')
        travel.fecha_vuelo_ida = datetime.strptime(fecha_ida_str, '%Y-%m-%d').date() if fecha_ida_str else None
        travel.hora_salida_ida = request.form.get('hora_salida_ida')
        travel.hora_llegada_ida = request.form.get('hora_llegada_ida')
        travel.numero_vuelo_ida = request.form.get('numero_vuelo_ida')
        travel.codigo_confirmacion_ida = request.form.get('codigo_confirmacion_ida')
        travel.numero_asiento_ida = request.form.get('numero_asiento_ida')
        travel.check_in_ida = request.form.get('check_in_ida')
        travel.check_out_ida = request.form.get('check_out_ida')
        travel.total_tickete_ida = float(request.form.get('total_tickete_ida')) if request.form.get('total_tickete_ida') else None
        travel.impuesto_incluido_ida = request.form.get('impuesto_incluido_ida')
        travel.nombre_aeropuerto_ida = request.form.get('nombre_aeropuerto_ida')
        travel.paises_escala_ida = request.form.get('paises_escala_ida')
        travel.aeropuerto_escala_ida = request.form.get('aeropuerto_escala_ida')
        travel.carga_permitida_maleta_mano_ida = request.form.get('carga_permitida_maleta_mano_ida')
        travel.precio_maleta_mano_ida = float(request.form.get('precio_maleta_mano_ida')) if request.form.get('precio_maleta_mano_ida') else None
        travel.necesita_visa_ida = request.form.get('necesita_visa_ida')
        travel.telefono1_aeropuerto_ida = request.form.get('telefono1_aeropuerto_ida')
        travel.telefono2_aeropuerto_ida = request.form.get('telefono2_aeropuerto_ida')
        travel.telefono1_aerolinea_ida = request.form.get('telefono1_aerolinea_ida')
        travel.telefono2_aerolinea_ida = request.form.get('telefono2_aerolinea_ida')
        travel.telefono1_embajada_consulado_ida = request.form.get('telefono1_embajada_consulado_ida')
        travel.telefono2_embajada_consulado_ida = request.form.get('telefono2_embajada_consulado_ida')

        # Vuelo de VUELTA
        travel.aerolinea_vuelta = request.form.get('aerolinea_vuelta')
        fecha_vuelta_str = request.form.get('fecha_vuelo_vuelta')
        travel.fecha_vuelo_vuelta = datetime.strptime(fecha_vuelta_str, '%Y-%m-%d').date() if fecha_vuelta_str else None
        travel.hora_salida_vuelta = request.form.get('hora_salida_vuelta')
        travel.hora_llegada_vuelta = request.form.get('hora_llegada_vuelta')
        travel.cantidad_dias_vuelta = int(request.form.get('cantidad_dias_vuelta')) if request.form.get('cantidad_dias_vuelta') else None
        travel.numero_vuelo_vuelta = request.form.get('numero_vuelo_vuelta')
        travel.codigo_confirmacion_vuelta = request.form.get('codigo_confirmacion_vuelta')
        travel.numero_asiento_vuelta = request.form.get('numero_asiento_vuelta')
        travel.check_in_vuelta = request.form.get('check_in_vuelta')
        travel.check_out_vuelta = request.form.get('check_out_vuelta')
        travel.total_tickete_pp_vuelta = float(request.form.get('total_tickete_pp_vuelta')) if request.form.get('total_tickete_pp_vuelta') else None
        travel.impuesto_incluido_vuelta = request.form.get('impuesto_incluido_vuelta')
        travel.nombre_aeropuerto_vuelta = request.form.get('nombre_aeropuerto_vuelta')
        travel.paises_escala_vuelta = request.form.get('paises_escala_vuelta')
        travel.aeropuerto_escala_vuelta = request.form.get('aeropuerto_escala_vuelta')
        travel.carga_permitida_maleta_mano_vuelta = request.form.get('carga_permitida_maleta_mano_vuelta')
        travel.precio_maleta_mano_vuelta = float(request.form.get('precio_maleta_mano_vuelta')) if request.form.get('precio_maleta_mano_vuelta') else None
        travel.necesita_visa_vuelta = request.form.get('necesita_visa_vuelta')
        travel.telefono1_aeropuerto_vuelta = request.form.get('telefono1_aeropuerto_vuelta')
        travel.telefono2_aeropuerto_vuelta = request.form.get('telefono2_aeropuerto_vuelta')
        travel.telefono1_aerolinea_vuelta = request.form.get('telefono1_aerolinea_vuelta')
        travel.telefono2_aerolinea_vuelta = request.form.get('telefono2_aerolinea_vuelta')
        travel.telefono1_embajada_consulado_vuelta = request.form.get('telefono1_embajada_consulado_vuelta')
        travel.telefono2_embajada_consulado_vuelta = request.form.get('telefono2_embajada_consulado_vuelta')
        travel.otro_telefono_vuelta = request.form.get('otro_telefono_vuelta')
        travel.nombre_estadia_vuelta = request.form.get('nombre_estadia_vuelta')
        travel.telefono1_estadia_vuelta = request.form.get('telefono1_estadia_vuelta')
        travel.telefono2_estadia_vuelta = request.form.get('telefono2_estadia_vuelta')

        # Vuelo de ESCALA (opcional)
        travel.otra_aerolinea_escala = request.form.get('otra_aerolinea_escala')
        fecha_escala_str = request.form.get('fecha_vuelo_escala')
        travel.fecha_vuelo_escala = datetime.strptime(fecha_escala_str, '%Y-%m-%d').date() if fecha_escala_str else None
        travel.hora_salida_escala = request.form.get('hora_salida_escala')
        travel.hora_llegada_escala = request.form.get('hora_llegada_escala')
        travel.numero_vuelo_escala = request.form.get('numero_vuelo_escala')
        travel.codigo_confirmacion_escala = request.form.get('codigo_confirmacion_escala')
        travel.numero_asiento_escala = request.form.get('numero_asiento_escala')
        travel.enlace_telefono_check_in_escala = request.form.get('enlace_telefono_check_in_escala')
        travel.enlace_telefono_check_out_escala = request.form.get('enlace_telefono_check_out_escala')
        travel.total_tickete_pp_escala = float(request.form.get('total_tickete_pp_escala')) if request.form.get('total_tickete_pp_escala') else None
        travel.impuesto_incluido_escala = request.form.get('impuesto_incluido_escala')
        travel.nombre_aeropuerto_escala = request.form.get('nombre_aeropuerto_escala')
        travel.paises_escala_escala = request.form.get('paises_escala_escala')
        travel.aeropuerto_escala_escala = request.form.get('aeropuerto_escala_escala')
        travel.carga_permitida_maleta_mano_escala = request.form.get('carga_permitida_maleta_mano_escala')
        travel.precio_maleta_mano_escala = float(request.form.get('precio_maleta_mano_escala')) if request.form.get('precio_maleta_mano_escala') else None
        travel.necesita_visa_escala = request.form.get('necesita_visa_escala')
        travel.telefono1_aeropuerto_escala = request.form.get('telefono1_aeropuerto_escala')
        travel.telefono2_aeropuerto_escala = request.form.get('telefono2_aeropuerto_escala')
        travel.telefono1_aerolinea_escala = request.form.get('telefono1_aerolinea_escala')
        travel.telefono2_aerolinea_escala = request.form.get('telefono2_aerolinea_escala')
        travel.telefono1_embajada_consulado_escala = request.form.get('telefono1_embajada_consulado_escala')
        travel.telefono2_embajada_consulado_escala = request.form.get('telefono2_embajada_consulado_escala')
        travel.otro_telefono_escala = request.form.get('otro_telefono_escala')
        travel.nombre_estadia_escala = request.form.get('nombre_estadia_escala')
        travel.telefono1_estadia_escala = request.form.get('telefono1_estadia_escala')
        travel.telefono2_estadia_escala = request.form.get('telefono2_estadia_escala')
        travel.otros_detalles_escala = request.form.get('otros_detalles_escala')


        # Información Adicional de Contacto y Estadía (general)
        travel.otro_telefono = request.form.get('otro_telefono')
        travel.nombre_estadia = request.form.get('nombre_estadia')
        travel.telefono1_estadia = request.form.get('telefono1_estadia')
        travel.telefono2_estadia = request.form.get('telefono2_estadia')
        travel.estadia_email = request.form.get('estadia_email')
        travel.otra_estadia_nombre = request.form.get('otra_estadia_nombre')
        travel.telefono1_otra_estadia = request.form.get('telefono1_otra_estadia')
        travel.telefono2_otra_estadia = request.form.get('telefono2_otra_estadia')

        # Tour Operador / Guía
        travel.nombre_tour_operador = request.form.get('nombre_tour_operador')
        travel.telefono_tour_operador1 = request.form.get('telefono_tour_operador1')
        travel.telefono_tour_operador2 = request.form.get('telefono_tour_operador2')
        travel.email_tour_operador = request.form.get('email_tour_operador')
        travel.total_operador_pp = float(request.form.get('total_operador_pp')) if request.form.get('total_operador_pp') else None

        # Contacto de Transporte
        travel.contacto_transporte_responsable = request.form.get('contacto_transporte_responsable')
        travel.contacto_transporte_telefono = request.form.get('contacto_transporte_telefono')
        travel.contacto_transporte_otro_telefono = request.form.get('contacto_transporte_otro_telefono')
        travel.contacto_transporte_otros_detalles = request.form.get('contacto_transporte_otros_detalles')

        # Recordatorios (checklist JSON)
        recordatorios_json_str = request.form.get('recordatorios_json')
        if recordatorios_json_str:
            try:
                travel.recordatorios_json = recordatorios_json_str
            except json.JSONDecodeError:
                travel.recordatorios_json = '[]' # Default to empty array on error
        else:
            travel.recordatorios_json = '[]'

        # Notas Generales (CKEditor)
        travel.notas_generales_ckeditor = request.form.get('notas_generales_ckeditor')

        try:
            db.session.commit()
            flash('Viaje internacional actualizado exitosamente!', 'success')
            return redirect(url_for('intern.detalle_intern', travel_id=travel.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el viaje: {e}', 'danger')
            print(f"Error al actualizar viaje internacional: {e}")
            # Re-renderiza el formulario con los datos enviados para que el usuario no los pierda
            form_data = request.form.to_dict(flat=False) # Convierte a diccionario para rellenar

            # Asegurarse de que los campos multiselect en form_data sean listas
            form_data['declaracion_tarjetas'] = request.form.getlist('declaracion_tarjetas')
            form_data['pais_destino_america'] = request.form.getlist('pais_destino_america')

            for key, value in form_data.items():
                if isinstance(value, list) and len(value) == 1:
                    form_data[key] = value[0] # Desempacar si es lista de un solo elemento
            return render_template('editar_intern.html', 
                                   travel=travel, 
                                   contact_options=contact_options, 
                                   aerolinea_options=AEROLINEA_OPTIONS, 
                                   pais_destino_america_options=PAIS_DESTINO_AMERICA_OPTIONS,
                                   si_no_aplica_options=SI_NO_APLICA_OPTIONS,
                                   necesita_visa_options=NECESITA_VISA_OPTIONS,
                                   declaracion_tarjetas_options=DECLARACION_TARJETAS_OPTIONS, 
                                   form_data=form_data)


    # MODIFICADO: Convertir JSON string a lista para rellenar el formulario en GET request
    # Asegúrate de que travel.declaracion_tarjetas sea una cadena JSON válida. Si es None o vacía, usa '[]'.
    try:
        selected_declaracion_tarjetas = json.loads(travel.declaracion_tarjetas or '[]')
    except json.JSONDecodeError:
        selected_declaracion_tarjetas = [] # Default to empty array on error

    try:
        selected_pais_destino_america = json.loads(travel.pais_destino_america or '[]')
    except json.JSONDecodeError:
        selected_pais_destino_america = [] # Default to empty array on error
    
    return render_template(
        'editar_intern.html',
        travel=travel,
        contact_options=contact_options,
        aerolinea_options=AEROLINEA_OPTIONS,
        pais_destino_america_options=PAIS_DESTINO_AMERICA_OPTIONS,
        si_no_aplica_options=SI_NO_APLICA_OPTIONS,
        necesita_visa_options=NECESITA_VISA_OPTIONS,
        declaracion_tarjetas_options=DECLARACION_TARJETAS_OPTIONS,
        selected_declaracion_tarjetas=selected_declaracion_tarjetas, # Pasa las opciones seleccionadas
        selected_pais_destino_america=selected_pais_destino_america # Pasa las opciones seleccionadas
    )

# Ruta para eliminar un viaje internacional
@intern_bp.route('/eliminar/<int:travel_id>', methods=['POST'])
@login_required_intern
def eliminar_intern(travel_id):
    travel = InternationalTravel.query.get_or_404(travel_id)
    try:
        db.session.delete(travel)
        db.session.commit()
        flash('Viaje internacional eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el viaje: {e}', 'danger')
        print(f"Error al eliminar viaje internacional: {e}")
    return redirect(url_for('intern.index'))

# Función auxiliar para generar el contenido del itinerario, omitiendo campos vacíos
def generate_itinerary_content(travel):
    content_parts = []
    
    content_parts.append(f"Detalles del Viaje Internacional ID: {travel.id}\n")

    # Información de Contacto
    contact_info = []
    if travel.contact:
        contact_info.append(f"Contacto Registrado: {travel.contact.nombre} {travel.contact.primer_apellido}")
        if travel.contact.telefono: contact_info.append(f"Teléfono: {travel.contact.telefono}")
        if travel.contact.email: contact_info.append(f"Email: {travel.contact.email}")
    else:
        if travel.nombre_contacto_manual: contact_info.append(f"Nombre Contacto Manual: {travel.nombre_contacto_manual}")
        if travel.apellido_contacto_manual: contact_info.append(f"Apellido Contacto Manual: {travel.apellido_contacto_manual}")
        if travel.telefono_contacto_manual: contact_info.append(f"Teléfono Contacto Manual: {travel.telefono_contacto_manual}")
        if travel.email_contacto_manual: contact_info.append(f"Email Contacto Manual: {travel.email_contacto_manual}")
    if contact_info:
        content_parts.append("\n--- Contacto ---")
        content_parts.extend(contact_info)

    # Información General del Viaje
    general_info = []
    try:
        declaracion_tarjetas_list = json.loads(travel.declaracion_tarjetas or '[]')
        if declaracion_tarjetas_list:
            general_info.append(f"Declaración de Tarjetas: {', '.join(declaracion_tarjetas_list)}")
    except json.JSONDecodeError:
        pass
    if travel.fecha_reporte: general_info.append(f"Fecha de Reporte: {travel.fecha_reporte.strftime('%Y-%m-%d')}")
    if travel.vigencia_pasaporte: general_info.append(f"Código de Reporte: {travel.vigencia_pasaporte}")
    try:
        pais_destino_america_list = json.loads(travel.pais_destino_america or '[]')
        if pais_destino_america_list:
            general_info.append(f"País Destino América: {', '.join(pais_destino_america_list)}")
    except json.JSONDecodeError:
        pass
    if general_info:
        content_parts.append("\n--- Información General del Viaje ---")
        content_parts.extend(general_info)

    # Vuelo de IDA
    ida_info = []
    if travel.aerolinea_ida: ida_info.append(f"Aerolínea Ida: {travel.aerolinea_ida}")
    if travel.fecha_vuelo_ida: ida_info.append(f"Fecha de Vuelo Ida: {travel.fecha_vuelo_ida.strftime('%Y-%m-%d')}")
    if travel.hora_salida_ida: ida_info.append(f"Hora de Salida Ida: {travel.hora_salida_ida}")
    if travel.hora_llegada_ida: ida_info.append(f"Hora de Llegada Ida: {travel.hora_llegada_ida}")
    if travel.numero_vuelo_ida: ida_info.append(f"Número de Vuelo Ida: {travel.numero_vuelo_ida}")
    if travel.codigo_confirmacion_ida: ida_info.append(f"Código de Confirmación Ida: {travel.codigo_confirmacion_ida}")
    if travel.numero_asiento_ida: ida_info.append(f"Número de Asiento Ida: {travel.numero_asiento_ida}")
    if travel.check_in_ida: ida_info.append(f"Check-In Ida: {travel.check_in_ida}")
    if travel.check_out_ida: ida_info.append(f"Check-Out Ida: {travel.check_out_ida}")
    if travel.total_tickete_ida is not None: ida_info.append(f"Total Ticket Ida: {travel.total_tickete_ida}")
    if travel.impuesto_incluido_ida: ida_info.append(f"Impuesto Incluido Ida: {travel.impuesto_incluido_ida}")
    if travel.nombre_aeropuerto_ida: ida_info.append(f"Nombre del Aeropuerto Ida: {travel.nombre_aeropuerto_ida}")
    if travel.paises_escala_ida: ida_info.append(f"Países de Escala Ida: {travel.paises_escala_ida}")
    if travel.aeropuerto_escala_ida: ida_info.append(f"Aeropuerto de Escala Ida: {travel.aeropuerto_escala_ida}")
    if travel.carga_permitida_maleta_mano_ida: ida_info.append(f"Carga Permitida Maleta Mano Ida: {travel.carga_permitida_maleta_mano_ida}")
    if travel.precio_maleta_mano_ida is not None: ida_info.append(f"Precio Maleta Mano Ida: {travel.precio_maleta_mano_ida}")
    if travel.necesita_visa_ida: ida_info.append(f"Necesita VISA Ida: {travel.necesita_visa_ida}")
    if travel.telefono1_aeropuerto_ida: ida_info.append(f"Teléfono 1 Aeropuerto Ida: {travel.telefono1_aeropuerto_ida}")
    if travel.telefono2_aeropuerto_ida: ida_info.append(f"Teléfono 2 Aeropuerto Ida: {travel.telefono2_aeropuerto_ida}")
    if travel.telefono1_aerolinea_ida: ida_info.append(f"Teléfono 1 Aerolínea Ida: {travel.telefono1_aerolinea_ida}")
    if travel.telefono2_aerolinea_ida: ida_info.append(f"Teléfono 2 Aerolínea Ida: {travel.telefono2_aerolinea_ida}")
    if travel.telefono1_embajada_consulado_ida: ida_info.append(f"Teléfono 1 Embajada - Consulado Ida: {travel.telefono1_embajada_consulado_ida}")
    if travel.telefono2_embajada_consulado_ida: ida_info.append(f"Teléfono 2 Embajada - Consulado Ida: {travel.telefono2_embajada_consulado_ida}")
    if ida_info:
        content_parts.append("\n--- Vuelo de IDA ---")
        content_parts.extend(ida_info)

    # Vuelo de VUELTA
    vuelta_info = []
    if travel.aerolinea_vuelta: vuelta_info.append(f"Aerolínea Vuelta: {travel.aerolinea_vuelta}")
    if travel.fecha_vuelo_vuelta: vuelta_info.append(f"Fecha de Vuelo Vuelta: {travel.fecha_vuelo_vuelta.strftime('%Y-%m-%d')}")
    if travel.hora_salida_vuelta: vuelta_info.append(f"Hora de Salida Vuelta: {travel.hora_salida_vuelta}")
    if travel.hora_llegada_vuelta: vuelta_info.append(f"Hora de Llegada Vuelta: {travel.hora_llegada_vuelta}")
    if travel.cantidad_dias_vuelta is not None: vuelta_info.append(f"Cantidad de Días Vuelta: {travel.cantidad_dias_vuelta}")
    if travel.numero_vuelo_vuelta: vuelta_info.append(f"Número de Vuelo Vuelta: {travel.numero_vuelo_vuelta}")
    if travel.codigo_confirmacion_vuelta: vuelta_info.append(f"Código de Confirmación Vuelta: {travel.codigo_confirmacion_vuelta}")
    if travel.numero_asiento_vuelta: vuelta_info.append(f"Número de Asiento Vuelta: {travel.numero_asiento_vuelta}")
    if travel.check_in_vuelta: vuelta_info.append(f"Check-In Vuelta: {travel.check_in_vuelta}")
    if travel.check_out_vuelta: vuelta_info.append(f"Check-Out Vuelta: {travel.check_out_vuelta}")
    if travel.total_tickete_pp_vuelta is not None: vuelta_info.append(f"Total Ticket P.P Vuelta: {travel.total_tickete_pp_vuelta}")
    if travel.impuesto_incluido_vuelta: vuelta_info.append(f"Impuesto Incluido Vuelta: {travel.impuesto_incluido_vuelta}")
    if travel.nombre_aeropuerto_vuelta: vuelta_info.append(f"Nombre del Aeropuerto Vuelta: {travel.nombre_aeropuerto_vuelta}")
    if travel.paises_escala_vuelta: vuelta_info.append(f"Países de Escala Vuelta: {travel.paises_escala_vuelta}")
    if travel.aeropuerto_escala_vuelta: vuelta_info.append(f"Aeropuerto de Escala Vuelta: {travel.aeropuerto_escala_vuelta}")
    if travel.carga_permitida_maleta_mano_vuelta: vuelta_info.append(f"Carga Permitida Maleta Mano Vuelta: {travel.carga_permitida_maleta_mano_vuelta}")
    if travel.precio_maleta_mano_vuelta is not None: vuelta_info.append(f"Precio Maleta Mano Vuelta: {travel.precio_maleta_mano_vuelta}")
    if travel.necesita_visa_vuelta: vuelta_info.append(f"Necesita VISA Vuelta: {travel.necesita_visa_vuelta}")
    if travel.telefono1_aeropuerto_vuelta: vuelta_info.append(f"Teléfono 1 Aeropuerto Vuelta: {travel.telefono1_aeropuerto_vuelta}")
    if travel.telefono2_aeropuerto_vuelta: vuelta_info.append(f"Teléfono 2 Aeropuerto Vuelta: {travel.telefono2_aeropuerto_vuelta}")
    if travel.telefono1_aerolinea_vuelta: vuelta_info.append(f"Teléfono 1 Aerolínea Vuelta: {travel.telefono1_aerolinea_vuelta}")
    if travel.telefono2_aerolinea_vuelta: vuelta_info.append(f"Teléfono 2 Aerolínea Vuelta: {travel.telefono2_aerolinea_vuelta}")
    if travel.telefono1_embajada_consulado_vuelta: vuelta_info.append(f"Teléfono 1 Embajada - Consulado Vuelta: {travel.telefono1_embajada_consulado_vuelta}")
    if travel.telefono2_embajada_consulado_vuelta: vuelta_info.append(f"Teléfono 2 Embajada - Consulado Vuelta: {travel.telefono2_embajada_consulado_vuelta}")
    if travel.otro_telefono_vuelta: vuelta_info.append(f"Otro Teléfono Vuelta: {travel.otro_telefono_vuelta}")
    if travel.nombre_estadia_vuelta: vuelta_info.append(f"Nombre Estadía Vuelta: {travel.nombre_estadia_vuelta}")
    if travel.telefono1_estadia_vuelta: vuelta_info.append(f"Teléfono 1 Estadía Vuelta: {travel.telefono1_estadia_vuelta}")
    if travel.telefono2_estadia_vuelta: vuelta_info.append(f"Teléfono 2 Estadía Vuelta: {travel.telefono2_estadia_vuelta}")
    if vuelta_info:
        content_parts.append("\n--- Vuelo de VUELTA ---")
        content_parts.extend(vuelta_info)

    # Vuelo de ESCALA
    escala_info = []
    if travel.otra_aerolinea_escala: escala_info.append(f"Otra Aerolínea Escala: {travel.otra_aerolinea_escala}")
    if travel.fecha_vuelo_escala: escala_info.append(f"Fecha de Vuelo Escala: {travel.fecha_vuelo_escala.strftime('%Y-%m-%d')}")
    if travel.hora_salida_escala: escala_info.append(f"Hora de Salida Escala: {travel.hora_salida_escala}")
    if travel.hora_llegada_escala: escala_info.append(f"Hora de Llegada Escala: {travel.hora_llegada_escala}")
    if travel.numero_vuelo_escala: escala_info.append(f"Número de Vuelo Escala: {travel.numero_vuelo_escala}")
    if travel.codigo_confirmacion_escala: escala_info.append(f"Código de Confirmación Escala: {travel.codigo_confirmacion_escala}")
    if travel.numero_asiento_escala: escala_info.append(f"Número de Asiento Escala: {travel.numero_asiento_escala}")
    if travel.enlace_telefono_check_in_escala: escala_info.append(f"Enlace o Teléfono Check-In Escala: {travel.enlace_telefono_check_in_escala}")
    if travel.enlace_telefono_check_out_escala: escala_info.append(f"Enlace o Teléfono Check-Out Escala: {travel.enlace_telefono_check_out_escala}")
    if travel.total_tickete_pp_escala is not None: escala_info.append(f"Total Ticket P.P Escala: {travel.total_tickete_pp_escala}")
    if travel.impuesto_incluido_escala: escala_info.append(f"Impuesto Incluido Escala: {travel.impuesto_incluido_escala}")
    if travel.nombre_aeropuerto_escala: escala_info.append(f"Nombre del Aeropuerto Escala: {travel.nombre_aeropuerto_escala}")
    if travel.paises_escala_escala: escala_info.append(f"Países de Escala Escala: {travel.paises_escala_escala}")
    if travel.aeropuerto_escala_escala: escala_info.append(f"Aeropuerto de Escala Escala: {travel.aeropuerto_escala_escala}")
    if travel.carga_permitida_maleta_mano_escala: escala_info.append(f"Carga Permitida Maleta Mano Escala: {travel.carga_permitida_maleta_mano_escala}")
    if travel.precio_maleta_mano_escala is not None: escala_info.append(f"Precio Maleta Mano Escala: {travel.precio_maleta_mano_escala}")
    if travel.necesita_visa_escala: escala_info.append(f"Necesita VISA Escala: {travel.necesita_visa_escala}")
    if travel.telefono1_aeropuerto_escala: escala_info.append(f"Teléfono 1 Aeropuerto Escala: {travel.telefono1_aeropuerto_escala}")
    if travel.telefono2_aeropuerto_escala: escala_info.append(f"Teléfono 2 Aeropuerto Escala: {travel.telefono2_aeropuerto_escala}")
    if travel.telefono1_aerolinea_escala: escala_info.append(f"Teléfono 1 Aerolínea Escala: {travel.telefono1_aerolinea_escala}")
    if travel.telefono2_aerolinea_escala: escala_info.append(f"Teléfono 2 Aerolínea Escala: {travel.telefono2_aerolinea_escala}")
    if travel.telefono1_embajada_consulado_escala: escala_info.append(f"Teléfono 1 Embajada - Consulado Escala: {travel.telefono1_embajada_consulado_escala}")
    if travel.telefono2_embajada_consulado_escala: escala_info.append(f"Teléfono 2 Embajada - Consulado Escala: {travel.telefono2_embajada_consulado_escala}")
    if travel.otro_telefono_escala: escala_info.append(f"Otro Teléfono Escala: {travel.otro_telefono_escala}")
    if travel.nombre_estadia_escala: escala_info.append(f"Nombre Estadía Escala: {travel.nombre_estadia_escala}")
    if travel.telefono1_estadia_escala: escala_info.append(f"Teléfono 1 Estadía Escala: {travel.telefono1_estadia_escala}")
    if travel.telefono2_estadia_escala: escala_info.append(f"Teléfono 2 Estadía Escala: {travel.telefono2_estadia_escala}")
    if travel.otros_detalles_escala: escala_info.append(f"Otros Detalles Escala: {travel.otros_detalles_escala}")
    if escala_info:
        content_parts.append("\n--- Vuelo de ESCALA ---")
        content_parts.extend(escala_info)

    # Información Adicional de Contacto y Estadía
    adicional_info = []
    if travel.otro_telefono: adicional_info.append(f"Otro Teléfono: {travel.otro_telefono}")
    if travel.nombre_estadia: adicional_info.append(f"Nombre Estadía: {travel.nombre_estadia}")
    if travel.telefono1_estadia: adicional_info.append(f"Teléfono 1 Estadía: {travel.telefono1_estadia}")
    if travel.telefono2_estadia: adicional_info.append(f"Teléfono 2 Estadía: {travel.telefono2_estadia}")
    if travel.estadia_email: adicional_info.append(f"Estadía Email: {travel.estadia_email}")
    if travel.otra_estadia_nombre: adicional_info.append(f"Nombre Otra Estadía: {travel.otra_estadia_nombre}")
    if travel.telefono1_otra_estadia: adicional_info.append(f"Teléfono 1 Otra Estadía: {travel.telefono1_otra_estadia}")
    if travel.telefono2_otra_estadia: adicional_info.append(f"Teléfono 2 Otra Estadía: {travel.telefono2_otra_estadia}")
    if adicional_info:
        content_parts.append("\n--- Contactos y Estadía Adicional (General) ---")
        content_parts.extend(adicional_info)

    # Tour Operador / Guía
    tour_info = []
    if travel.nombre_tour_operador: tour_info.append(f"Nombre Tour Operador / Guía: {travel.nombre_tour_operador}")
    if travel.telefono_tour_operador1: tour_info.append(f"Teléfono 1 Tour Operador / Guía: {travel.telefono_tour_operador1}")
    if travel.telefono_tour_operador2: tour_info.append(f"Teléfono 2 Tour Operador / Guía: {travel.telefono_tour_operador2}")
    if travel.email_tour_operador: tour_info.append(f"Email Tour Operador / Guía: {travel.email_tour_operador}")
    if travel.total_operador_pp is not None: tour_info.append(f"Total Operador P.P: {travel.total_operador_pp}")
    if tour_info:
        content_parts.append("\n--- Tour Operador / Guía ---")
        content_parts.extend(tour_info)

    # Contacto de Transporte
    transporte_info = []
    if travel.contacto_transporte_responsable: transporte_info.append(f"Nombre Responsable: {travel.contacto_transporte_responsable}")
    if travel.contacto_transporte_telefono: transporte_info.append(f"Teléfono Responsable: {travel.contacto_transporte_telefono}")
    if travel.contacto_transporte_otro_telefono: transporte_info.append(f"Otro Teléfono: {travel.contacto_transporte_otro_telefono}")
    if travel.contacto_transporte_otros_detalles: transporte_info.append(f"Otros Detalles: {travel.contacto_transporte_otros_detalles}")
    if transporte_info:
        content_parts.append("\n--- Contacto de Transporte ---")
        content_parts.extend(transporte_info)

    # Checklist de Recordatorios
    recordatorios_info = []
    try:
        recordatorios_data = json.loads(travel.recordatorios_json or '[]')
    except json.JSONDecodeError:
        recordatorios_data = []
    if recordatorios_data:
        for item in recordatorios_data:
            status = "[X]" if item.get('completed') else "[ ]"
            recordatorios_info.append(f"{status} {item.get('text', 'N/A')}")
    if recordatorios_info:
        content_parts.append("\n--- Recordatorios ---")
        content_parts.extend(recordatorios_info)
    # Si no hay recordatorios, la sección completa se omite

    # Notas Generales
    if travel.notas_generales_ckeditor and travel.notas_generales_ckeditor.strip():
        content_parts.append("\n--- Notas Generales ---")
        content_parts.append(travel.notas_generales_ckeditor.strip())

    return "\n".join(content_parts)


# RUTA MODIFICADA: Exportar a TXT
@intern_bp.route('/exportar_txt/<int:travel_id>')
@login_required_intern
def exportar_txt(travel_id):
    travel = InternationalTravel.query.get_or_404(travel_id)
    content = generate_itinerary_content(travel) # Utiliza la nueva función auxiliar

    buffer = io.BytesIO(content.encode('utf-8'))
    buffer.seek(0) # Vuelve al inicio del buffer

    return send_file(
        buffer,
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'viaje_internacional_{travel.id}.txt'
    )

# RUTA MODIFICADA: Exportar a PDF
@intern_bp.route('/exportar_pdf/<int:travel_id>')
@login_required_intern
def exportar_pdf(travel_id):
    travel = InternationalTravel.query.get_or_404(travel_id)
    content = generate_itinerary_content(travel) # Utiliza la nueva función auxiliar

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para párrafos para manejar texto preformateado
    code_style = ParagraphStyle(
        name='CodeStyle',
        parent=styles['Normal'],
        fontName='Helvetica', # Use Helvetica, a standard font
        fontSize=10,
        leading=12,
        alignment=TA_LEFT,
        whiteSpace='pre', # Preserva los espacios en blanco
        wordWrap='CJK' # Ayuda con el salto de línea para texto preformateado
    )

    story = []
    
    # Divide el contenido en líneas y crea párrafos
    for line in content.split('\n'):
        # Reemplaza las líneas vacías con un pequeño espaciador para mantener el diseño
        if line.strip() == '':
            story.append(Spacer(1, 0.1 * inch))
        else:
            story.append(Paragraph(line, code_style))

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'viaje_internacional_{travel.id}.pdf'
    )


# RUTA MODIFICADA: Exportar a JPG
@intern_bp.route('/exportar_jpg/<int:travel_id>')
@login_required_intern
def exportar_jpg(travel_id):
    travel = InternationalTravel.query.get_or_404(travel_id)
    content = generate_itinerary_content(travel) # Utiliza la nueva función auxiliar

    # Dimensiones de la imagen base
    # Ancho fijo, altura estimada en función de la cantidad de líneas de contenido
    img_width = 800
    line_height = 25 # Estimado para el tamaño de fuente 20 y espaciado
    padding_top = 50
    padding_bottom = 50
    padding_left = 50

    # Estimar la altura de la imagen
    num_lines = content.count('\n') + 1 # Contar líneas para estimar altura
    img_height = num_lines * line_height + padding_top + padding_bottom
    
    img = Image.new('RGB', (img_width, img_height), color = (255, 255, 255)) # Fondo blanco
    d = ImageDraw.Draw(img)

    try:
        # Intenta cargar una fuente. Usa una por defecto si no se encuentra.
        # Asegúrate de que 'arial.ttf' esté disponible en tu sistema o especifica una ruta completa.
        font = ImageFont.truetype("arial.ttf", 20) 
    except IOError:
        font = ImageFont.load_default() # Fuente de reserva

    # Dibuja el texto completo.
    # d.multiline_text puede manejar saltos de línea automáticamente
    d.multiline_text((padding_left, padding_top), content, fill=(0,0,0), font=font, spacing=5) # Texto negro

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='image/jpeg',
        as_attachment=True,
        download_name=f'viaje_internacional_{travel.id}.jpg'
    )
