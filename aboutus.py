# aboutus.py
import os
import io
import re
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from werkzeug.utils import secure_filename

# Importa la instancia de la base de datos y el modelo AboutUs desde models.py
from models import db, AboutUs

# Importa las bibliotecas para la generación de imágenes y PDF
from PIL import Image, ImageDraw, ImageFont # Para exportar a JPG
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER


# Define el Blueprint para el módulo "Acerca de Nosotros"
aboutus_bp = Blueprint('aboutus', __name__)

# Extensiones de archivo permitidas para el logo
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Función auxiliar para verificar si la extensión del archivo es permitida
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ruta para ver la sección "Acerca de Nosotros"
@aboutus_bp.route('/ver', methods=['GET'])
def ver_aboutus():
    # Intenta obtener la entrada más reciente de AboutUs.
    # Se asume que solo habrá una sección "Acerca de Nosotros" en la aplicación.
    about_us_entry = AboutUs.query.order_by(AboutUs.created_at.desc()).first()
    return render_template('ver_aboutus.html', about_us_entry=about_us_entry)

# Ruta para crear una nueva sección "Acerca de Nosotros"
@aboutus_bp.route('/crear', methods=['GET', 'POST'])
def crear_aboutus():
    if request.method == 'POST':
        print("DEBUG: Solicitud POST recibida en /aboutus/crear") # DEBUG
        try:
            # Obtiene los datos del formulario
            title = request.form['title']
            detail = request.form['detail']
            logo_info = request.form['logo_info']
            print(f"DEBUG: Datos del formulario - Título: '{title}', Info Logo: '{logo_info}'") # DEBUG

            # Manejo de la subida del archivo del logo
            if 'logo' not in request.files:
                flash('No se seleccionó ningún archivo de logo', 'danger')
                print("DEBUG: No se encontró el archivo 'logo' en request.files.") # DEBUG
                return redirect(request.url)
            logo_file = request.files['logo']

            if logo_file.filename == '':
                flash('No se seleccionó ningún archivo de logo', 'danger')
                print("DEBUG: El nombre del archivo de logo está vacío.") # DEBUG
                return redirect(request.url)

            if logo_file and allowed_file(logo_file.filename):
                # Guarda el archivo de forma segura
                filename = secure_filename(logo_file.filename)
                # Usar la carpeta específica para imágenes de AboutUs
                upload_folder = current_app.config['ABOUTUS_IMAGE_UPLOAD_FOLDER']
                filepath = os.path.join(upload_folder, filename)

                # Asegurarse de que la carpeta de subidas exista
                os.makedirs(upload_folder, exist_ok=True)
                
                logo_file.save(filepath)
                print(f"DEBUG: Archivo de logo guardado en: {filepath}") # DEBUG

                # Verifica si ya existe una entrada de AboutUs. Si existe, la actualiza.
                # Esto mantiene una única sección "Acerca de Nosotros".
                existing_about_us = AboutUs.query.first()
                if existing_about_us:
                    # Si ya existe, elimina el logo anterior si es diferente
                    if existing_about_us.logo_filename and existing_about_us.logo_filename != filename:
                        old_logo_path = os.path.join(upload_folder, existing_about_us.logo_filename)
                        if os.path.exists(old_logo_path):
                            os.remove(old_logo_path)
                            print(f"DEBUG: Logo anterior eliminado: {old_logo_path}")

                    # Actualiza los campos
                    existing_about_us.logo_filename = filename
                    existing_about_us.logo_info = logo_info
                    existing_about_us.title = title
                    existing_about_us.detail = detail
                    flash('Sección "Acerca de Nosotros" actualizada exitosamente!', 'success')
                    print("DEBUG: Sección 'Acerca de Nosotros' existente actualizada.") # DEBUG
                else:
                    # Si no existe, crea una nueva entrada
                    new_about_us = AboutUs(
                        logo_filename=filename,
                        logo_info=logo_info,
                        title=title,
                        detail=detail
                    )
                    db.session.add(new_about_us)
                    flash('Sección "Acerca de Nosotros" creada exitosamente!', 'success')
                    print("DEBUG: Nueva sección 'Acerca de Nosotros' creada.") # DEBUG

                db.session.commit() # Guarda los cambios en la base de datos
                print("DEBUG: Cambios en la base de datos confirmados. Redirigiendo a ver_aboutus.") # DEBUG
                return redirect(url_for('aboutus.ver_aboutus'))
            else:
                flash('Tipo de archivo no permitido para el logo. Solo PNG, JPG, JPEG.', 'danger')
                print("DEBUG: Tipo de archivo de logo no permitido.") # DEBUG
        except Exception as e:
            db.session.rollback() # En caso de error, revierte la transacción
            flash(f'Error al procesar la solicitud: {str(e)}', 'danger')
            print(f"ERROR: Fallo en la función crear_aboutus: {str(e)}") # DEBUG
            # Opcional: imprimir el traceback completo para más detalles en desarrollo
            import traceback
            traceback.print_exc()
            return redirect(request.url) # Redirige de vuelta con el mensaje de error

    return render_template('crear_aboutus.html')

# Ruta para editar una sección "Acerca de Nosotros" existente
@aboutus_bp.route('/editar/<int:aboutus_id>', methods=['GET', 'POST'])
def editar_aboutus(aboutus_id):
    # Obtiene la entrada de AboutUs por su ID, o devuelve un 404 si no se encuentra
    about_us_entry = AboutUs.query.get_or_404(aboutus_id)

    if request.method == 'POST':
        try:
            # Actualiza los campos de la entrada existente
            about_us_entry.title = request.form['title']
            about_us_entry.detail = request.form['detail']
            about_us_entry.logo_info = request.form['logo_info']

            # Manejo de la actualización del archivo del logo
            if 'logo' in request.files and request.files['logo'].filename != '':
                logo_file = request.files['logo']
                if logo_file and allowed_file(logo_file.filename):
                    # Si ya existe un logo, lo elimina del sistema de archivos
                    if about_us_entry.logo_filename:
                        old_logo_path = os.path.join(current_app.config['ABOUTUS_IMAGE_UPLOAD_FOLDER'], about_us_entry.logo_filename)
                        if os.path.exists(old_logo_path):
                            os.remove(old_logo_path)
                            print(f"DEBUG: Logo anterior eliminado durante edición: {old_logo_path}")

                    # Guarda el nuevo logo
                    filename = secure_filename(logo_file.filename)
                    filepath = os.path.join(current_app.config['ABOUTUS_IMAGE_UPLOAD_FOLDER'], filename)
                    logo_file.save(filepath)
                    about_us_entry.logo_filename = filename
                    print(f"DEBUG: Nuevo logo guardado durante edición: {filepath}")
                else:
                    flash('Tipo de archivo no permitido para el logo. Solo PNG, JPG, JPEG.', 'danger')
                    return redirect(request.url)
            else:
                print("DEBUG: No se seleccionó un nuevo archivo de logo para la edición o el nombre del archivo estaba vacío.")


            db.session.commit() # Guarda los cambios en la base de datos
            flash('Sección "Acerca de Nosotros" actualizada exitosamente!', 'success')
            return redirect(url_for('aboutus.ver_aboutus'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la sección "Acerca de Nosotros": {str(e)}', 'danger')
            print(f"ERROR: Fallo en la función editar_aboutus: {str(e)}") # DEBUG
            import traceback
            traceback.print_exc()
            return redirect(request.url)

    return render_template('editar_aboutus.html', about_us_entry=about_us_entry)

# Ruta para eliminar una sección "Acerca de Nosotros"
@aboutus_bp.route('/eliminar/<int:aboutus_id>', methods=['POST'])
def eliminar_aboutus(aboutus_id):
    # Obtiene la entrada de AboutUs por su ID, o devuelve un 404 si no se encuentra
    about_us_entry = AboutUs.query.get_or_404(aboutus_id)
    try:
        # Elimina el archivo de logo asociado del sistema de archivos
        if about_us_entry.logo_filename:
            logo_path = os.path.join(current_app.config['ABOUTUS_IMAGE_UPLOAD_FOLDER'], about_us_entry.logo_filename)
            if os.path.exists(logo_path):
                os.remove(logo_path)
                print(f"DEBUG: Logo eliminado del sistema de archivos: {logo_path}")

        db.session.delete(about_us_entry) # Elimina la entrada de la base de datos
        db.session.commit() # Guarda los cambios
        flash('Sección "Acerca de Nosotros" eliminada exitosamente!', 'success')
        print(f"DEBUG: Sección AboutUs {aboutus_id} eliminada de la base de datos.")
    except Exception as e:
        db.session.rollback() # Revierte la transacción en caso de error
        flash(f'Error al eliminar la sección "Acerca de Nosotros": {str(e)}', 'danger')
        print(f"ERROR: Fallo al eliminar aboutus: {str(e)}") # DEBUG
    return redirect(url_for('aboutus.ver_aboutus'))

# Ruta para exportar el contenido de "Acerca de Nosotros" a diferentes formatos
@aboutus_bp.route('/exportar/<int:aboutus_id>/<string:format>', methods=['GET'])
def exportar_aboutus(aboutus_id, format):
    about_us_entry = AboutUs.query.get_or_404(aboutus_id)

    # Contenido base para la exportación
    content = f"Título: {about_us_entry.title}\n\n" \
              f"Información del Logo: {about_us_entry.logo_info}\n\n" \
              f"Detalle: {about_us_entry.detail}\n\n" \
              f"Fecha de Creación: {about_us_entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n" \
              f"Fecha de Modificación: {about_us_entry.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"

    if format == 'txt':
        # Exportar a TXT (UTF-8)
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='acerca_de_nosotros.txt', mimetype='text/plain; charset=utf-8')
    elif format == 'pdf':
        # Exportar a PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Estilo para el título
        title_style = ParagraphStyle('TitleStyle',
                                     parent=styles['h1'],
                                     alignment=TA_CENTER,
                                     spaceAfter=14)
        story.append(Paragraph(about_us_entry.title, title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Imagen del Logo (si existe)
        if about_us_entry.logo_filename:
            logo_path = os.path.join(current_app.config['ABOUTUS_IMAGE_UPLOAD_FOLDER'], about_us_entry.logo_filename)
            if os.path.exists(logo_path):
                try:
                    img = RLImage(logo_path)
                    # Ajusta el tamaño de la imagen para que encaje en el PDF
                    img.drawHeight = 1 * inch * img.drawHeight / img.drawWidth
                    img.drawWidth = 1 * inch
                    story.append(img)
                    story.append(Spacer(1, 0.1 * inch))
                except Exception as e:
                    print(f"Error al cargar la imagen para PDF: {e}")
                    # Continúa sin la imagen si hay un error
                    pass

        # Información del Logo
        story.append(Paragraph("<b>Información del Logo:</b>", styles['Normal']))
        story.append(Paragraph(about_us_entry.logo_info, styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Detalle (contenido principal)
        story.append(Paragraph("<b>Detalle:</b>", styles['Normal']))
        # Elimina las etiquetas HTML del contenido de CKEditor para la exportación a PDF
        clean_detail = re.sub('<[^<]+?>', '', about_us_entry.detail)
        story.append(Paragraph(clean_detail, styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Fechas
        story.append(Paragraph(f"<b>Fecha de Creación:</b> {about_us_entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(Paragraph(f"<b>Fecha de Modificación:</b> {about_us_entry.updated_at.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))

        doc.build(story) # Construye el documento PDF
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='acerca_de_nosotros.pdf', mimetype='application/pdf')
    elif format == 'jpg':
        # Exportar a JPG (generando una imagen del texto)
        img_width = 800
        padding = 20
        font_size_title = 24
        font_size_body = 16

        # Estimar la altura necesaria para el texto. Es una estimación.
        # Se eliminan las etiquetas HTML para el cálculo y la visualización.
        clean_detail = re.sub('<[^<]+?>', '', about_us_entry.detail)
        text_content_for_jpg = (
            f"Título: {about_us_entry.title}\n\n"
            f"Información del Logo: {about_us_entry.logo_info}\n\n"
            f"Detalle: {clean_detail}\n\n"
            f"Fecha de Creación: {about_us_entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Fecha de Modificación: {about_us_entry.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Crear una imagen temporal para calcular el tamaño del texto
        temp_img = Image.new('RGB', (1, 1))
        temp_d = ImageDraw.Draw(temp_img)
        try:
            # Intenta cargar una fuente que soporte UTF-8
            font_path_title = "arial.ttf" # Común en Windows
            font_path_body = "arial.ttf"
            if not os.path.exists(font_path_title):
                # Fallback para Linux/macOS
                font_path_title = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path_body):
                font_path_body = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

            font_title_calc = ImageFont.truetype(font_path_title, font_size_title)
            font_body_calc = ImageFont.truetype(font_path_body, font_size_body)
        except IOError:
            print("No se pudo cargar la fuente, usando la fuente PIL predeterminada.")
            font_title_calc = ImageFont.load_default()
            font_body_calc = ImageFont.load_default()
            font_size_title = 16 # Ajustar tamaño para la fuente predeterminada
            font_size_body = 10

        # Calcular la altura necesaria para el texto con ajuste de línea
        current_y_estimate = padding
        # Title
        current_y_estimate += font_size_title + 10
        # Logo Info
        current_y_estimate += font_size_body + 10
        # Detail
        current_y_estimate += font_size_body + 5 # "Detalle:" label
        words = clean_detail.split(' ')
        current_line_words = []
        for word in words:
            test_line = ' '.join(current_line_words + [word])
            if temp_d.textlength(test_line, font=font_body_calc) < img_width - 2 * padding:
                current_line_words.append(word)
            else:
                current_y_estimate += font_size_body + 2
                current_line_words = [word]
        if current_line_words:
            current_y_estimate += font_size_body + 2
        current_y_estimate += 10 # Spacer
        # Dates
        current_y_estimate += (font_size_body + 2) * 2

        img_height = max(400, int(current_y_estimate + padding)) # Asegura una altura mínima

        img = Image.new('RGB', (img_width, img_height), color = (255, 255, 255))
        d = ImageDraw.Draw(img)

        # Re-load fonts for drawing on the actual image
        try:
            font_title = ImageFont.truetype(font_path_title, font_size_title)
            font_body = ImageFont.truetype(font_path_body, font_size_body)
        except IOError:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()


        y_text = padding

        # Dibujar Título
        d.text((padding, y_text), f"Título: {about_us_entry.title}", fill=(0,0,0), font=font_title)
        y_text += font_size_title + 10

        # Dibujar Información del Logo
        d.text((padding, y_text), f"Información del Logo: {about_us_entry.logo_info}", fill=(0,0,0), font=font_body)
        y_text += font_size_body + 10

        # Dibujar Detalle (con ajuste de línea)
        d.text((padding, y_text), "Detalle:", fill=(0,0,0), font=font_body)
        y_text += font_size_body + 5
        lines_to_draw = []
        current_line_words = []
        for word in words: # Use words from clean_detail calculated earlier
            test_line = ' '.join(current_line_words + [word])
            if d.textlength(test_line, font=font_body) < img_width - 2 * padding:
                current_line_words.append(word)
            else:
                lines_to_draw.append(' '.join(current_line_words))
                current_line_words = [word]
        if current_line_words:
            lines_to_draw.append(' '.join(current_line_words))

        for line in lines_to_draw:
            d.text((padding, y_text), line, fill=(0,0,0), font=font_body)
            y_text += font_size_body + 2

        y_text += 10 # Espaciador

        # Dibujar Fechas
        d.text((padding, y_text), f"Fecha de Creación: {about_us_entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}", fill=(0,0,0), font=font_body)
        y_text += font_size_body + 2
        d.text((padding, y_text), f"Fecha de Modificación: {about_us_entry.updated_at.strftime('%Y-%m-%d %H:%M:%S')}", fill=(0,0,0), font=font_body)

        # Guarda la imagen en un buffer y la envía como archivo
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='acerca_de_nosotros.jpg', mimetype='image/jpeg')
    else:
        flash('Formato de exportación no válido.', 'danger')
        return redirect(url_for('aboutus.ver_aboutus'))
