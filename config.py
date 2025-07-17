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






# # Importa os para manejar variables de entorno y rutas
# import os

# # Define la clase de configuración principal para la aplicación Flask
# class Config:
#     # Clave secreta para proteger las sesiones de usuario y otras operaciones de seguridad
#     # Se recomienda obtenerla de una variable de entorno para mayor seguridad
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'una-cadena-dificil-de-adivinar'

#     # Configuración de la base de datos SQLAlchemy
#     # URI de la base de datos, obtenida de una variable de entorno o usando una predeterminada
#     SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
#         'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.db')

#     # Deshabilita el seguimiento de modificaciones de objetos SQLAlchemy para ahorrar recursos
#     # y evitar advertencias, ya que no es necesario para la mayoría de las aplicaciones
#     SQLALCHEMY_TRACK_MODIFICATIONS = False

#     # Configuración del reciclaje de la conexión de la base de datos para SQLAlchemy
#     # Establecerlo un poco por debajo de ese valor ayuda a que SQLAlchemy cierre y reabra
#     # conexiones de base de datos inactivas, evitando problemas de conexión persistente.
#     SQLALCHEMY_POOL_RECYCLE = 299 # La línea problemática ha sido corregida aquí con un '#'

#     # Configuración del tamaño del pool de conexiones de la base de datos
#     SQLALCHEMY_POOL_SIZE = 10

#     # Configuración del tiempo de espera del pool de conexiones
#     SQLALCHEMY_POOL_TIMEOUT = 30