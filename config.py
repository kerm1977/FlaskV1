# config.py (o dentro de app.py si no tienes un archivo de configuración separado)
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'una_clave_secreta_muy_dificil_de_adivinar'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///db.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # --- NUEVO: Configuración para la carpeta de subidas ---
    # Asegúrate de que esta ruta sea absoluta y que el usuario que ejecuta la app tenga permisos de escritura.
    # Se recomienda usar una ruta absoluta para evitar problemas.
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Límite de 16 MB para el tamaño de los archivos






# PYTHONANYWHERE---------------------------------------------------------

# import os

# # LOCAL------------------------------------------------------------------

# basedir = os.path.abspath(os.path.dirname(__file__))

# class Config:
#     SECRET_KEY = 'tu_clave_secreta_aqui'
#     # SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'db.db')
#     SQLALCHEMY_TRACK_MODIFICATIONS = False

#     # PYTHONANYWHERE---------------------------------------------------------

#     # Asegúrate de que esta sea la configuración activa para PythonAnywhere
#     # Descomenta y usa esta línea cuando despliegues en PythonAnywhere
#     SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://kenth1977:LaTribu1977@kenth1977.mysql.pythonanywhere-services.com/kenth1977$db'

#     # Configuración del pool de conexiones para evitar "Lost connection"
#     # pool_recycle: Recicla las conexiones después de X segundos de inactividad.
#     # PythonAnywhere cierra las conexiones inactivas después de 300 segundos (5 minutos).
    # Establecerlo un poco por debajo de ese valor ayuda a que SQLAlchemy cierre y reabra
    # la conexión antes de que el servidor lo haga.
#     SQLALCHEMY_ENGINE_OPTIONS = {
#         "pool_pre_ping": True, # Prueba la conexión antes de usarla del pool
#         "pool_recycle": 280,   # Recicla conexiones después de 280 segundos (un poco menos de 5 minutos)
#         "pool_timeout": 60,    # Tiempo máximo de espera para obtener una conexión del pool
#         "pool_size": 10        # Número de conexiones en el pool (ajustar según necesidad y límites de PythonAnywhere)
#     }
