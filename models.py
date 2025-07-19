# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from datetime import datetime, date, time # Importar date y time para manejar fechas y horas
import json # Importar json para los campos de texto que almacenarán listas/diccionarios

# Instanciamos SQLAlchemy y Bcrypt aquí, pero no los asociamos aún a la app
# Esto se hará en app.py con db.init_app(app)
db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate() # Instanciamos Migrate aquí también

# Tabla de asociación para la relación muchos-a-muchos entre Note y User
# para los usuarios autorizados a ver una nota.
note_viewers = db.Table('note_viewers',
    db.Column('note_id', db.Integer, db.ForeignKey('note.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

# NUEVA: Tabla de asociación para la relación muchos-a-muchos entre Caminata y User (para participantes)
caminata_participantes = db.Table('caminata_participantes',
    db.Column('caminata_id', db.Integer, db.ForeignKey('caminata.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)


# Definición del modelo de usuario (existente)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Campos obligatorios
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    primer_apellido = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    # CORRECCIÓN: Cambiado de 'fecha_fecha_creacion' a 'fecha_registro'
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    # Campos opcionales (existentes)
    avatar_url = db.Column(db.String(255), default='images/defaults/default_avatar.png')
    segundo_apellido = db.Column(db.String(100), nullable=True)
    telefono_emergencia = db.Column(db.String(20), nullable=True)
    nombre_emergencia = db.Column(db.String(100), nullable=True)
    empresa = db.Column(db.String(100), nullable=True)
    cedula = db.Column(db.String(50), nullable=True)
    direccion = db.Column(db.String(255), nullable=True) # Campo de Dirección existente
    email = db.Column(db.String(120), unique=True, nullable=True)
    actividad = db.Column(db.String(50), nullable=True)
    capacidad = db.Column(db.String(50), nullable=True)
    participacion = db.Column(db.String(50), nullable=True)

    # NUEVOS CAMPOS AÑADIDOS
    fecha_cumpleanos = db.Column(db.Date, nullable=True) # Para la fecha de cumpleaños
    tipo_sangre = db.Column(db.String(5), nullable=True) # Para el tipo de sangre (ej. A+, O-)
    poliza = db.Column(db.String(100), nullable=True) # Número o nombre de póliza
    aseguradora = db.Column(db.String(100), nullable=True) # Nombre de la aseguradora
    alergias = db.Column(db.Text, nullable=True) # Para alergias (texto largo)
    enfermedades_cronicas = db.Column(db.Text, nullable=True) # Para enfermedades crónicas (texto largo)
    
    # Campos adicionales de user (del código anterior)
    # CAMBIO: profile_image ahora es nullable=True para permitir migraciones sin error
    profile_image = db.Column(db.String(20), nullable=True, default='default.jpg')
    is_admin = db.Column(db.Boolean, default=False)
    fecha_nacimiento = db.Column(db.Date, nullable=True) # Originalmente 'fecha_nacimiento'
    genero = db.Column(db.String(10), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True) # Para registrar la última sesión

    # NUEVO CAMPO: Role para el sistema de permisos
    role = db.Column(db.String(50), default='Usuario Regular', nullable=False) # Añadir el campo de rol


    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.nombre}')"

# MODELO Project (existente)
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_proyecto = db.Column(db.String(255), nullable=False)
    imagen_proyecto_url = db.Column(db.String(255), nullable=True) # Para guardar la URL de la imagen

    # Relacionado con la propuesta
    propuesta_por = db.Column(db.String(100), nullable=True) # Jenny Ceciliano Cordoba, Kenneth Ruiz Matamoros, Otro
    
    # Campo para el invitado (relación con User)
    nombre_invitado_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    nombre_invitado = db.relationship('User', foreign_keys=[nombre_invitado_id]) # Relación con el modelo User

    provincia = db.Column(db.String(50), nullable=True)
    fecha_actividad_propuesta = db.Column(db.Date, nullable=True)
    dificultad = db.Column(db.String(50), nullable=True) # No Aplica, Iniciante, Básico, Intermedio, Avanzado, Técnico

    transporte_terrestre = db.Column(db.String(50), nullable=True) # Autobús, Buseta, Auto, Moto, 4x4
    transporte_acuatico = db.Column(db.String(2), nullable=True) # Si/No aplica
    transporte_aereo = db.Column(db.String(2), nullable=True) # Si/No aplica
    precio_entrada_aplica = db.Column(db.String(2), nullable=True) # Si/No aplica

    nombre_lugar = db.Column(db.String(255), nullable=True)
    contacto_lugar = db.Column(db.String(255), nullable=True)
    telefono_lugar = db.Column(db.String(20), nullable=True)
    tipo_terreno = db.Column(db.String(50), nullable=True) # No aplica, Asfalto, Acuatico, Lastre, Arena, Montañoso
    mas_tipo_terreno = db.Column(db.Text, nullable=True) # Campo adicional para especificar más tipos de terreno

    presupuesto_total = db.Column(db.Float, nullable=True)
    costo_entrada = db.Column(db.Float, nullable=True)
    costo_guia = db.Column(db.Float, nullable=True)
    costo_transporte = db.Column(db.Float, nullable=True)

    nombres_acompanantes = db.Column(db.Text, nullable=True) # Para múltiples nombres, separados por comas o similar
    recomendaciones = db.Column(db.Text, nullable=True)
    notas_adicionales = db.Column(db.Text, nullable=True)
    
    # Autofecha de creado de nota (fecha de creación del proyecto)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_ultima_actualizacion = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    def __repr__(self):
        return f"Project('{self.nombre_proyecto}', '{self.propuesta_por}', '{self.fecha_actividad_propuesta}')"

# MODELO Note (existente, con nueva columna)
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(255), nullable=True) # URL de la imagen de la nota
    content = db.Column(db.Text, nullable=True) # Contenido de la nota con formato HTML

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    # Campo para indicar si la nota es pública
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    # NUEVO CAMPO: Para almacenar el color de fondo de la nota
    background_color = db.Column(db.String(20), default='#FFFFFF', nullable=False) # Valor por defecto blanco

    # Relación con el usuario que crea la nota
    # CORRECCIÓN: Añadir ondelete='CASCADE' y passive_deletes=True
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    creator = db.relationship('User', backref=db.backref('created_notes', lazy=True, cascade="all, delete-orphan"), foreign_keys=[creator_id])

    # Relación muchos-a-muchos con usuarios que pueden ver una nota
    # secondary apunta a la tabla de asociación definida arriba
    authorized_viewers = db.relationship(
        'User', secondary=note_viewers, lazy='subquery',
        backref=db.backref('viewable_notes', lazy=True)
    )

    def __repr__(self):
        return f"Note('{self.title}', Creator ID: {self.creator_id}, Public: {self.is_public}, Color: {self.background_color})"

# NUEVO MODELO: InternationalTravel
class InternationalTravel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Selector de Contactos registrados
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    contact = db.relationship('User', backref='international_travels', foreign_keys=[contact_id])
    
    # Si no existe contacto registrado
    nombre_contacto_manual = db.Column(db.String(100), nullable=True)
    apellido_contacto_manual = db.Column(db.String(100), nullable=True)
    telefono_contacto_manual = db.Column(db.String(20), nullable=True)
    email_contacto_manual = db.Column(db.String(120), nullable=True)

    # Información General
    # MODIFICADO: Cambiado a db.Text para almacenar JSON de múltiples selecciones
    declaracion_tarjetas = db.Column(db.Text, nullable=True)
    fecha_reporte = db.Column(db.Date, nullable=True) # NUEVO CAMPO: Fecha de Reporte
    vigencia_pasaporte = db.Column(db.String(255), nullable=True) # Ahora es Código de Reporte

    # País Destino América
    # MODIFICADO: Cambiado a db.Text para almacenar JSON de múltiples selecciones
    pais_destino_america = db.Column(db.Text, nullable=True)

    # Vuelo de IDA
    aerolinea_ida = db.Column(db.String(100), nullable=True)
    fecha_vuelo_ida = db.Column(db.Date, nullable=True)
    hora_salida_ida = db.Column(db.String(10), nullable=True) # Ej: "14:30"
    hora_llegada_ida = db.Column(db.String(10), nullable=True)
    numero_vuelo_ida = db.Column(db.String(50), nullable=True)
    codigo_confirmacion_ida = db.Column(db.String(50), nullable=True)
    numero_asiento_ida = db.Column(db.String(20), nullable=True)
    check_in_ida = db.Column(db.String(255), nullable=True) # URL o info
    check_out_ida = db.Column(db.String(255), nullable=True) # URL o info
    total_tickete_ida = db.Column(db.Float, nullable=True)
    impuesto_incluido_ida = db.Column(db.String(10), nullable=True) # "No Aplica", "Si"
    nombre_aeropuerto_ida = db.Column(db.String(255), nullable=True)
    paises_escala_ida = db.Column(db.String(255), nullable=True) # Puede ser una lista separada por comas
    aeropuerto_escala_ida = db.Column(db.String(255), nullable=True)
    carga_permitida_maleta_mano_ida = db.Column(db.String(50), nullable=True) # Ej: "10kg"
    precio_maleta_mano_ida = db.Column(db.Float, nullable=True)
    necesita_visa_ida = db.Column(db.String(10), nullable=True) # "No Aplica", "Si"
    telefono1_aeropuerto_ida = db.Column(db.String(20), nullable=True)
    telefono2_aeropuerto_ida = db.Column(db.String(20), nullable=True)
    telefono1_aerolinea_ida = db.Column(db.String(20), nullable=True)
    telefono2_aerolinea_ida = db.Column(db.String(20), nullable=True)
    telefono1_embajada_consulado_ida = db.Column(db.String(20), nullable=True)
    telefono2_embajada_consulado_ida = db.Column(db.String(20), nullable=True)

    # Vuelo de Vuelta
    aerolinea_vuelta = db.Column(db.String(100), nullable=True)
    fecha_vuelo_vuelta = db.Column(db.Date, nullable=True)
    hora_salida_vuelta = db.Column(db.String(10), nullable=True)
    hora_llegada_vuelta = db.Column(db.String(10), nullable=True)
    cantidad_dias_vuelta = db.Column(db.Integer, nullable=True)
    numero_vuelo_vuelta = db.Column(db.String(50), nullable=True)
    codigo_confirmacion_vuelta = db.Column(db.String(50), nullable=True)
    numero_asiento_vuelta = db.Column(db.String(20), nullable=True)
    check_in_vuelta = db.Column(db.String(255), nullable=True)
    check_out_vuelta = db.Column(db.String(255), nullable=True)
    total_tickete_pp_vuelta = db.Column(db.Float, nullable=True)
    impuesto_incluido_vuelta = db.Column(db.String(10), nullable=True)
    nombre_aeropuerto_vuelta = db.Column(db.String(255), nullable=True)
    paises_escala_vuelta = db.Column(db.String(255), nullable=True)
    aeropuerto_escala_vuelta = db.Column(db.String(255), nullable=True)
    carga_permitida_maleta_mano_vuelta = db.Column(db.String(50), nullable=True)
    precio_maleta_mano_vuelta = db.Column(db.Float, nullable=True)
    necesita_visa_vuelta = db.Column(db.String(10), nullable=True)
    telefono1_aeropuerto_vuelta = db.Column(db.String(20), nullable=True)
    telefono2_aeropuerto_vuelta = db.Column(db.String(20), nullable=True)
    telefono1_aerolinea_vuelta = db.Column(db.String(20), nullable=True)
    telefono2_aerolinea_vuelta = db.Column(db.String(20), nullable=True)
    telefono1_embajada_consulado_vuelta = db.Column(db.String(20), nullable=True)
    telefono2_embajada_consulado_vuelta = db.Column(db.String(20), nullable=True)
    otro_telefono_vuelta = db.Column(db.String(20), nullable=True)
    nombre_estadia_vuelta = db.Column(db.String(255), nullable=True)
    telefono1_estadia_vuelta = db.Column(db.String(20), nullable=True)
    telefono2_estadia_vuelta = db.Column(db.String(20), nullable=True)

    # Vuelo con Escala (Nota)
    otra_aerolinea_escala = db.Column(db.String(100), nullable=True)
    fecha_vuelo_escala = db.Column(db.Date, nullable=True)
    hora_salida_escala = db.Column(db.String(10), nullable=True)
    hora_llegada_escala = db.Column(db.String(10), nullable=True)
    numero_vuelo_escala = db.Column(db.String(50), nullable=True)
    codigo_confirmacion_escala = db.Column(db.String(50), nullable=True)
    numero_asiento_escala = db.Column(db.String(20), nullable=True)
    enlace_telefono_check_in_escala = db.Column(db.String(255), nullable=True)
    enlace_telefono_check_out_escala = db.Column(db.String(255), nullable=True)
    total_tickete_pp_escala = db.Column(db.Float, nullable=True)
    impuesto_incluido_escala = db.Column(db.String(10), nullable=True)
    nombre_aeropuerto_escala = db.Column(db.String(255), nullable=True)
    paises_escala_escala = db.Column(db.String(255), nullable=True)
    aeropuerto_escala_escala = db.Column(db.String(255), nullable=True)
    carga_permitida_maleta_mano_escala = db.Column(db.String(50), nullable=True)
    precio_maleta_mano_escala = db.Column(db.Float, nullable=True)
    necesita_visa_escala = db.Column(db.String(10), nullable=True)
    telefono1_aeropuerto_escala = db.Column(db.String(20), nullable=True)
    telefono2_aeropuerto_escala = db.Column(db.String(20), nullable=True)
    telefono1_aerolinea_escala = db.Column(db.String(20), nullable=True)
    telefono2_aerolinea_escala = db.Column(db.String(20), nullable=True)
    telefono1_embajada_consulado_escala = db.Column(db.String(20), nullable=True)
    telefono2_embajada_consulado_escala = db.Column(db.String(20), nullable=True)
    otro_telefono_escala = db.Column(db.String(20), nullable=True)
    nombre_estadia_escala = db.Column(db.String(255), nullable=True)
    telefono1_estadia_escala = db.Column(db.String(20), nullable=True)
    telefono2_estadia_escala = db.Column(db.String(20), nullable=True)
    otros_detalles_escala = db.Column(db.Text, nullable=True)

    # Otros Teléfonos y Estadías
    otro_telefono = db.Column(db.String(20), nullable=True) # Este es el 'Otro Teléfono' global
    nombre_estadia = db.Column(db.String(255), nullable=True) # Este es el 'Nombre Estadía' global
    telefono1_estadia = db.Column(db.String(20), nullable=True) # Este es el 'Teléfono 1 Estadía' global
    telefono2_estadia = db.Column(db.String(20), nullable=True) # Este es el 'Teléfono 2 Estadía' global
    estadia_email = db.Column(db.String(120), nullable=True)

    otra_estadia_nombre = db.Column(db.String(255), nullable=True)
    telefono1_otra_estadia = db.Column(db.String(20), nullable=True)
    telefono2_otra_estadia = db.Column(db.String(20), nullable=True)

    # Tour Operador / Guía
    nombre_tour_operador = db.Column(db.String(255), nullable=True)
    telefono_tour_operador1 = db.Column(db.String(20), nullable=True)
    telefono_tour_operador2 = db.Column(db.String(20), nullable=True)
    email_tour_operador = db.Column(db.String(120), nullable=True)
    total_operador_pp = db.Column(db.Float, nullable=True)

    # Contacto de Transporte
    contacto_transporte_responsable = db.Column(db.String(255), nullable=True)
    contacto_transporte_telefono = db.Column(db.String(20), nullable=True)
    contacto_transporte_otro_telefono = db.Column(db.String(20), nullable=True)
    contacto_transporte_otros_detalles = db.Column(db.Text, nullable=True)

    # Checklist de recordatorios (como una cadena de texto JSON o similar, o tabla separada si es muy complejo)
    recordatorios_json = db.Column(db.Text, nullable=True) # Almacenará un JSON de [{'text': 'item', 'completed': False}]

    # Notas generales
    notas_generales_ckeditor = db.Column(db.Text, nullable=True) # Para CKEditor content

    # Fechas de creación y actualización
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    def __repr__(self):
        return f"InternationalTravel(ID: {self.id}, País Destino: {self.pais_destino_america})"

# NUEVO MODELO: Caminata
class Caminata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    imagen_caminata_url = db.Column(db.String(255), nullable=True)
    actividad = db.Column(db.String(100), nullable=False)
    
    # CAMBIO CRUCIAL: 'pais' renombrado a 'etapa'
    etapa = db.Column(db.String(255), nullable=True)
    
    nombre = db.Column(db.String(255), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    
    # Campos de tiempo y costos que deben coincidir con HTML/caminatas.py
    hora = db.Column(db.Time, nullable=True) # De crear_caminatas.html
    hora_salida = db.Column(db.Time, nullable=True) # De editar_caminatas.html y caminatas.py
    hora_regreso = db.Column(db.Time, nullable=True) # De editar_caminatas.html
    
    costo_b = db.Column(db.Float, nullable=True) # De crear_caminatas.html
    costo_c = db.Column(db.Float, nullable=True) # De crear_caminatas.html
    costo_extranjeros = db.Column(db.Float, nullable=True) # De crear_caminatas.html

    lugar_salida = db.Column(db.String(255), nullable=True)
    dificultad = db.Column(db.String(50), nullable=True)
    distancia = db.Column(db.Float, nullable=True)
    
    # CAMBIO CRUCIAL: Capacidad minima y maxima a tipo String
    capacidad_minima = db.Column(db.String(50), nullable=True)
    capacidad_maxima = db.Column(db.String(50), nullable=True)
    
    nombre_guia = db.Column(db.String(255), nullable=True)
    se_requiere = db.Column(db.String(100), nullable=True)
    provincia = db.Column(db.String(50), nullable=True)
    tipo_terreno = db.Column(db.Text, nullable=True)  # Almacenar como JSON
    otras_senas_terreno = db.Column(db.Text, nullable=True)
    tipo_transporte = db.Column(db.Text, nullable=True)  # Almacenar como JSON
    incluye = db.Column(db.Text, nullable=True)  # Almacenar como JSON
    cuenta_con = db.Column(db.Text, nullable=True)  # Almacenar como JSON
    tipo_clima = db.Column(db.String(100), nullable=True)
    altura_maxima = db.Column(db.Float, nullable=True)
    altura_minima = db.Column(db.Float, nullable=True)
    
    # Desniveles adicionales de editar_caminatas.html
    desnivel = db.Column(db.Float, nullable=True) # General desnivel, de crear_caminatas.html
    desnivel_positivo = db.Column(db.Float, nullable=True)
    desnivel_negativo = db.Column(db.Float, nullable=True)

    altura_positiva = db.Column(db.Float, nullable=True)
    altura_negativa = db.Column(db.Float, nullable=True)
    
    # Renombrado de 'otros_datos_ckeditor' a 'otros_datos' para consistencia con caminatas.py
    otros_datos = db.Column(db.Text, nullable=True) 

    duracion_horas = db.Column(db.Float, nullable=True) # De crear_caminatas.html

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relación muchos-a-muchos con usuarios que participan en la caminata
    participantes = db.relationship(
        'User', secondary=caminata_participantes, lazy='subquery',
        backref=db.backref('caminatas_participa', lazy=True)
    )

    # Relación uno a muchos con AbonoCaminata
    abonos = db.relationship('AbonoCaminata', backref='caminata', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Caminata('{self.nombre}', '{self.fecha}', '{self.actividad}')"

    # NUEVO: Añadir índices para mejorar el rendimiento de las consultas
    __table_args__ = (
        db.Index('idx_caminata_fecha_desc', fecha.desc()), # Índice para ordenar por fecha descendente
        db.Index('idx_caminata_actividad', actividad),       # Índice para filtrar por actividad
    )


# NUEVO MODELO: AbonoCaminata
class AbonoCaminata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    caminata_id = db.Column(db.Integer, db.ForeignKey('caminata.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Usuario que realiza el abono
    user = db.relationship('User', backref='abonos_realizados')

    opcion = db.Column(db.String(50), nullable=False) # Pago Total, Reserva, Abono
    cantidad_acompanantes = db.Column(db.Integer, default=0, nullable=False)
    nombres_acompanantes = db.Column(db.Text, nullable=True) # JSON de nombres de acompañantes
    monto_abono = db.Column(db.Float, nullable=False)
    fecha_abono = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"AbonoCaminata(Caminata: {self.caminata_id}, User: {self.user_id}, Monto: {self.monto_abono})"

# Modelo para "Pagos" (NUEVO)
class Pagos(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Usuario que creó el pago
    nombre_caminata = db.Column(db.String(255), nullable=False)
    flyer_imagen_url = db.Column(db.String(255), nullable=True)
    precio_paquete = db.Column(db.Float, default=0)
    capacidad = db.Column(db.Integer, default=0)
    tipo_cambio = db.Column(db.Float, default=0)

    # Transporte
    precio_buseta = db.Column(db.Float, default=0)
    cantidad_busetas = db.Column(db.Integer, default=0)
    precio_acuatico = db.Column(db.Float, default=0)
    cantidad_acuatico = db.Column(db.Integer, default=0)
    precio_aereo = db.Column(db.Float, default=0)
    cantidad_aereo = db.Column(db.Integer, default=0)
    precio_otros_transporte = db.Column(db.Float, default=0)
    cantidad_otros_transporte = db.Column(db.Integer, default=0)
    descripcion_otros_transporte = db.Column(db.String(255), nullable=True)

    # Otros Generales (Guías)
    precio_guias = db.Column(db.Float, default=0)
    precio_guia_por_persona = db.Column(db.Float, default=0) # NUEVO CAMPO
    cantidad_guias = db.Column(db.Integer, default=0)

    # Otros Personales
    precio_estadia = db.Column(db.Float, default=0)
    cantidad_dias_estadia = db.Column(db.Integer, default=1) # Se inicializa en 1
    precio_impuestos = db.Column(db.Float, default=0)
    precio_banos = db.Column(db.Float, default=0)
    precio_servicios_sanitarios = db.Column(db.Float, default=0)
    precio_desayuno = db.Column(db.Float, default=0)
    cantidad_dias_desayuno = db.Column(db.Integer, default=1) # Se inicializa en 1
    precio_merienda = db.Column(db.Float, default=0)
    cantidad_dias_merienda = db.Column(db.Integer, default=1) # Se inicializa en 1
    precio_almuerzo = db.Column(db.Float, default=0)
    cantidad_dias_almuerzo = db.Column(db.Integer, default=1) # Se inicializa en 1
    precio_acarreo = db.Column(db.Float, default=0)
    precio_cafe = db.Column(db.Float, default=0)
    cantidad_dias_cafe = db.Column(db.Integer, default=1) # Se inicializa en 1
    precio_cena = db.Column(db.Float, default=0)
    cantidad_dias_cena = db.Column(db.Integer, default=1) # Se inicializa en 1
    precio_entrada = db.Column(db.Float, default=0)
    precio_reconocimiento = db.Column(db.Float, default=0)
    precio_permisos = db.Column(db.Float, default=0)
    precio_pasaporte = db.Column(db.Float, default=0)
    precio_otros1_personales = db.Column(db.Float, default=0)
    descripcion_otros1_personales = db.Column(db.String(255), nullable=True)
    precio_otros2_personales = db.Column(db.Float, default=0)
    descripcion_otros2_personales = db.Column(db.String(255), nullable=True)
    precio_otros3_personales = db.Column(db.Float, default=0)
    descripcion_otros3_personales = db.Column(db.String(255), nullable=True)
    precio_otros4_personales = db.Column(db.Float, default=0)
    descripcion_otros4_personales = db.Column(db.String(255), nullable=True)

    # Totales (calculados y almacenados para referencia rápida)
    total_general_transporte = db.Column(db.Float, default=0)
    total_individual_transporte = db.Column(db.Float, default=0)
    total_general_guias = db.Column(db.Float, default=0)
    total_individual_guias = db.Column(db.Float, default=0)
    total_individual_personales = db.Column(db.Float, default=0)
    total_general_total = db.Column(db.Float, default=0)
    total_individual_total = db.Column(db.Float, default=0)
    ganancia_pp = db.Column(db.Float, default=0)
    ganancia_gral = db.Column(db.Float, default=0)

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True) # Añadir fecha_actualizacion

    def __repr__(self):
        return f'<Pagos {self.nombre_caminata}>'

# NUEVO MODELO: CalendarEvent
class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    flyer_imagen_url = db.Column(db.String(255), nullable=True) # Opcional
    nombre_actividad = db.Column(db.String(255), nullable=False)
    fecha_actividad = db.Column(db.Date, nullable=False)
    hora_actividad = db.Column(db.Time, nullable=True) # Nullable si es evento de todo el día
    descripcion = db.Column(db.Text, nullable=True) # Para CKEditor Full
    
    # Etiqueta del evento (Evento de La Tribu, Evento Externo, Fechas de Cumpleaños, Celebraciones)
    nombre_etiqueta = db.Column(db.String(50), nullable=False) 
    
    es_todo_el_dia = db.Column(db.Boolean, default=False, nullable=False) # Si se selecciona, advierte
    
    # Almacenar correos electrónicos como JSON (lista de strings)
    correos_notificacion = db.Column(db.Text, nullable=True) 

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relación con el usuario que crea el evento
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', backref='created_calendar_events', foreign_keys=[creator_id])

    def __repr__(self):
        return f"CalendarEvent('{self.nombre_actividad}', '{self.fecha_actividad}', '{self.hora_actividad}')"


# NUEVO MODELO: Instruction
class Instruction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Relación con la Caminata (SELECT CON LAS CAMINATAS QUE EXISTEN ACTIVAS)
    caminata_id = db.Column(db.Integer, db.ForeignKey('caminata.id'), nullable=False)
    caminata = db.relationship('Caminata', backref='instrucciones')

    dificultad = db.Column(db.String(50), nullable=True) # Iniciante, Básico, Intermedio, Avanzado, Técnico
    distancia = db.Column(db.Float, nullable=True)
    capacidad = db.Column(db.String(20), nullable=True) # 14, 17, 28, 31, 42
    lugar_salida = db.Column(db.String(255), nullable=True) # Parque de Tres Ríos - Escuela, etc.
    fecha_salida = db.Column(db.Date, nullable=True)
    hora_salida = db.Column(db.Time, nullable=True)
    fecha_caminata = db.Column(db.Date, nullable=True)
    hora_inicio_caminata = db.Column(db.Time, nullable=True)
    
    # UN INPUT LLAMADO RECOGEMOS EN: QUE PERMITA IR AGREGANDO ELEMENTOS (JSON)
    recogemos_en = db.Column(db.Text, nullable=True) # Almacenar como JSON de strings

    # PARA EL CAMINO:
    hidratacion = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    litros_hidratacion = db.Column(db.String(20), nullable=True) # ej. "2.lts"
    tennis_ligera = db.Column(db.String(20), nullable=True) # SI
    tennis_runner = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    tennis_hiking_baja = db.Column(db.String(20), nullable=True) # OPCIONAL
    zapato_cana_media = db.Column(db.String(20), nullable=True) # OPCIONAL
    zapato_cana_alta = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    bastones = db.Column(db.String(20), nullable=True) # NO NECESARIOS
    foco_headlamp = db.Column(db.String(20), nullable=True) # Siempre
    snacks = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    repelente = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    poncho = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    guantes = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    bloqueador = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL
    ropa_cambio = db.Column(db.String(20), nullable=True) # SI, NO, OPCIONAL

    # OTRAS RECOMENDACIONES: (CKEDITOR)
    otras_recomendaciones = db.Column(db.Text, nullable=True)

    # NORMAS GENERALES: (CKEDITOR)
    normas_generales = db.Column(db.Text, nullable=True)

    # OTRAS INDICACIONES GENERALES: (CKEDITOR)
    otras_indicaciones_generales = db.Column(db.Text, nullable=True)

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    def __repr__(self):
        return f"Instruction(Caminata_ID: {self.caminata_id}, Fecha Caminata: {self.fecha_caminata})"



class Song(db.Model):
    """Modelo de la base de datos para una canción."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    artist = db.Column(db.String(255), nullable=True)
    album = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), unique=True, nullable=False) # Ruta al archivo de audio
    cover_image_path = db.Column(db.String(500), nullable=True) # Ruta a la carátula

    # Relación con Playlist (muchas a muchas)
    # CORRECCIÓN: back_populates debe apuntar a la propiedad 'songs' en Playlist
    playlists = db.relationship('Playlist', secondary='playlist_songs', back_populates='songs')

    def __repr__(self):
        return f'<Song {self.title} by {self.artist}>'

class Playlist(db.Model):
    """Modelo de la base de datos para una lista de reproducción."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    
    # Relación con Song (muchas a muchas)
    # CORRECCIÓN: back_populates debe apuntar a la propiedad 'playlists' en Song
    songs = db.relationship('Song', secondary='playlist_songs', back_populates='playlists')

    def __repr__(self):
        return f'<Playlist {self.name}>'

# Tabla de asociación para la relación muchos a muchos entre Song y Playlist
playlist_songs = db.Table('playlist_songs',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlist.id'), primary_key=True),
    db.Column('song_id', db.Integer, db.ForeignKey('song.id'), primary_key=True)
)

# NUEVO MODELO: Itinerario
class Itinerario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    caminata_id = db.Column(db.Integer, db.ForeignKey('caminata.id'), nullable=False)
    caminata = db.relationship('Caminata', backref='itinerarios')

    lugar_salida = db.Column(db.String(255), nullable=True)
    hora_salida = db.Column(db.Time, nullable=True)
    puntos_recogida = db.Column(db.Text, nullable=True) # Almacenar como JSON de strings
    contenido_itinerario = db.Column(db.Text, nullable=True) # CKEditor completo
    pasaremos_a_comer = db.Column(db.String(20), nullable=True) # "No aplica", "Si", "No"

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    def __repr__(self):
        return f"Itinerario(Caminata: {self.caminata.nombre}, Fecha: {self.caminata.fecha})"

# Podrías agregar un modelo para Carátula (CoverArt) si quisieras una gestión más granular,
# pero por simplicidad, la ruta de la carátula se incluye en Song por ahora.
# class CoverArt(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     path = db.Column(db.String(500), unique=True, nullable=False)
#     song_id = db.Column(db.Integer, db.ForeignKey('song.id'), unique=True)
#     song = db.relationship('Song', backref=db.backref('cover_art', uselist=False))



class AboutUs(db.Model):
    __tablename__ = 'about_us' # Nombre de la tabla en la base de datos

    id = db.Column(db.Integer, primary_key=True)
    logo_filename = db.Column(db.String(255), nullable=False) # Nombre del archivo del logo
    logo_info = db.Column(db.Text, nullable=True) # Información del logo (para el modal)
    title = db.Column(db.String(255), nullable=False) # Título de la sección
    detail = db.Column(db.Text, nullable=False) # Contenido principal (con CKEditor)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AboutUs {self.title}>"


# NUEVO MODELO: Ruta
class Ruta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    provincia = db.Column(db.String(50), nullable=False)
    detalle = db.Column(db.Text, nullable=True) # Para CKEditor o texto largo
    enlace_video = db.Column(db.String(500), nullable=True) # Enlace compatible con Facebook/YouTube


    def __repr__(self):
        return f"Ruta(Nombre: {self.nombre}, Provincia: {self.provincia})"

