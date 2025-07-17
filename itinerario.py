from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify, send_file, Response
from functools import wraps
from datetime import datetime, date, time
import json
import io
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup # Para limpiar HTML de CKEditor
import os # ¡IMPORTANTE! Añadir esta línea para usar os.path.join

# Importa db y los modelos necesarios
from models import db, Itinerario, Caminata, Instruction, User

itinerario_bp = Blueprint('itinerario', __name__, template_folder='templates')

# Decorador para requerir inicio de sesión
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta para ver todos los itinerarios
@itinerario_bp.route('/')
@login_required
def ver_itinerario():
    # Obtener todos los itinerarios, ordenados por la fecha de la caminata asociada
    itinerarios = Itinerario.query.join(Caminata).order_by(Caminata.fecha.desc()).all()
    return render_template('ver_itinerario.html', itinerarios=itinerarios)

# Ruta para crear un nuevo itinerario
@itinerario_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear_itinerario():
    caminatas_activas = Caminata.query.filter(Caminata.fecha >= date.today()).order_by(Caminata.fecha.asc()).all()
    pasaremos_a_comer_opciones = ["No aplica", "Si", "No"]

    # Valores por defecto para el formulario en GET o si hay errores en POST
    form_data = {
        'caminata_id': '',
        'lugar_salida': '',
        'hora_salida': '',
        'puntos_recogida': json.dumps([]), # Lista vacía por defecto
        'contenido_itinerario': '',
        'pasaremos_a_comer': 'No aplica'
    }

    if request.method == 'POST':
        caminata_id = request.form.get('caminata_id')
        lugar_salida = request.form.get('lugar_salida')
        hora_salida_str = request.form.get('hora_salida')
        puntos_recogida_list = request.form.getlist('puntos_recogida[]')
        contenido_itinerario = request.form.get('contenido_itinerario')
        pasaremos_a_comer = request.form.get('pasaremos_a_comer')

        # Actualizar form_data con los valores enviados para repopular el formulario en caso de error
        form_data.update({
            'caminata_id': caminata_id,
            'lugar_salida': lugar_salida,
            'hora_salida': hora_salida_str,
            'puntos_recogida': json.dumps([item for item in puntos_recogida_list if item.strip()]), # Limpiar vacíos
            'contenido_itinerario': contenido_itinerario,
            'pasaremos_a_comer': pasaremos_a_comer
        })

        if not caminata_id:
            flash('Por favor, selecciona una caminata.', 'danger')
            return render_template('crear_itinerario.html', caminatas_activas=caminatas_activas, 
                                   pasaremos_a_comer_opciones=pasaremos_a_comer_opciones, form_data=form_data)
        
        caminata = Caminata.query.get(caminata_id)
        if not caminata:
            flash('Caminata seleccionada no válida.', 'danger')
            return render_template('crear_itinerario.html', caminatas_activas=caminatas_activas, 
                                   pasaremos_a_comer_opciones=pasaremos_a_comer_opciones, form_data=form_data)

        # Validar si ya existe un itinerario para esta caminata
        existing_itinerario = Itinerario.query.filter_by(caminata_id=caminata_id).first()
        if existing_itinerario:
            flash(f'Ya existe un itinerario para la caminata "{caminata.nombre}". Por favor, edita el existente.', 'danger')
            return render_template('crear_itinerario.html', caminatas_activas=caminatas_activas, 
                                   pasaremos_a_comer_opciones=pasaremos_a_comer_opciones, form_data=form_data)

        hora_salida = None
        if hora_salida_str:
            try:
                hora_salida = datetime.strptime(hora_salida_str, '%H:%M').time()
            except ValueError:
                flash('Formato de hora de salida inválido. Utilice HH:MM.', 'danger')
                return render_template('crear_itinerario.html', caminatas_activas=caminatas_activas, 
                                       pasaremos_a_comer_opciones=pasaremos_a_comer_opciones, form_data=form_data)

        new_itinerario = Itinerario(
            caminata_id=caminata_id,
            lugar_salida=lugar_salida,
            hora_salida=hora_salida,
            puntos_recogida=json.dumps([item for item in puntos_recogida_list if item.strip()]),
            contenido_itinerario=contenido_itinerario,
            pasaremos_a_comer=pasaremos_a_comer
        )

        try:
            db.session.add(new_itinerario)
            db.session.commit()
            flash('Itinerario creado exitosamente!', 'success')
            return redirect(url_for('itinerario.detalle_itinerario', itinerario_id=new_itinerario.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el itinerario: {e}', 'danger')
            current_app.logger.error(f"Error al crear itinerario: {e}")
            return render_template('crear_itinerario.html', caminatas_activas=caminatas_activas, 
                                   pasaremos_a_comer_opciones=pasaremos_a_comer_opciones, form_data=form_data)

    return render_template('crear_itinerario.html', caminatas_activas=caminatas_activas, 
                           pasaremos_a_comer_opciones=pasaremos_a_comer_opciones, form_data=form_data)

# Ruta AJAX para obtener datos de la caminata y su instrucción asociada
@itinerario_bp.route('/get_caminata_data/<int:caminata_id>')
@login_required
def get_caminata_data(caminata_id):
    caminata = Caminata.query.get(caminata_id)
    if not caminata:
        return jsonify({'lugar_salida': '', 'hora_salida': ''})

    # Intentar obtener la instrucción asociada a la caminata
    instruction = Instruction.query.filter_by(caminata_id=caminata.id).first()

    lugar_salida = ""
    hora_salida = ""

    if instruction:
        lugar_salida = instruction.lugar_salida if instruction.lugar_salida else ""
        hora_salida = instruction.hora_salida.strftime('%H:%M') if instruction.hora_salida else ""
    else:
        # Si no hay instrucción, usar los datos de la caminata directamente
        lugar_salida = caminata.lugar_salida if caminata.lugar_salida else ""
        hora_salida = caminata.hora_salida.strftime('%H:%M') if caminata.hora_salida else ""

    return jsonify({'lugar_salida': lugar_salida, 'hora_salida': hora_salida})


# Ruta para ver el detalle de un itinerario
@itinerario_bp.route('/detalle/<int:itinerario_id>')
@login_required
def detalle_itinerario(itinerario_id):
    itinerario = Itinerario.query.get_or_404(itinerario_id)
    
    puntos_recogida_list = []
    if itinerario.puntos_recogida:
        try:
            puntos_recogida_list = json.loads(itinerario.puntos_recogida)
        except json.JSONDecodeError:
            puntos_recogida_list = ["Error al cargar puntos de recogida."]

    # Obtener la URL de las instrucciones si existen para esta caminata
    instruccion = Instruction.query.filter_by(caminata_id=itinerario.caminata.id).first()
    instrucciones_url = None
    if instruccion:
        instrucciones_url = url_for('instrucciones.detalle_instrucciones', instruction_id=instruccion.id)

    return render_template('detalle_itinerario.html', 
                           itinerario=itinerario, 
                           puntos_recogida_list=puntos_recogida_list,
                           instrucciones_url=instrucciones_url)

# Ruta para editar un itinerario
@itinerario_bp.route('/editar/<int:itinerario_id>', methods=['GET', 'POST'])
@login_required
def editar_itinerario(itinerario_id):
    itinerario = Itinerario.query.get_or_404(itinerario_id)
    caminatas_activas = Caminata.query.filter(Caminata.fecha >= date.today()).order_by(Caminata.fecha.asc()).all()
    pasaremos_a_comer_opciones = ["No aplica", "Si", "No"]

    if request.method == 'POST':
        itinerario.caminata_id = request.form.get('caminata_id')
        itinerario.lugar_salida = request.form.get('lugar_salida')
        hora_salida_str = request.form.get('hora_salida')
        puntos_recogida_list = request.form.getlist('puntos_recogida[]')
        itinerario.contenido_itinerario = request.form.get('contenido_itinerario')
        itinerario.pasaremos_a_comer = request.form.get('pasaremos_a_comer')

        if not itinerario.caminata_id:
            flash('Por favor, selecciona una caminata.', 'danger')
            return render_template('editar_itinerario.html', itinerario=itinerario, 
                                   caminatas_activas=caminatas_activas, 
                                   pasaremos_a_comer_opciones=pasaremos_a_comer_opciones)
        
        # Validar si ya existe un itinerario para la nueva caminata seleccionada (excluyendo el actual)
        existing_itinerario_for_caminata = Itinerario.query.filter(
            Itinerario.caminata_id == itinerario.caminata_id,
            Itinerario.id != itinerario_id
        ).first()
        if existing_itinerario_for_caminata:
            flash(f'Ya existe un itinerario para la caminata seleccionada. Edita el existente o elige otra caminata.', 'danger')
            return render_template('editar_itinerario.html', itinerario=itinerario, 
                                   caminatas_activas=caminatas_activas, 
                                   pasaremos_a_comer_opciones=pasaremos_a_comer_opciones)

        if hora_salida_str:
            try:
                itinerario.hora_salida = datetime.strptime(hora_salida_str, '%H:%M').time()
            except ValueError:
                flash('Formato de hora de salida inválido. Utilice HH:MM.', 'danger')
                return render_template('editar_itinerario.html', itinerario=itinerario, 
                                       caminatas_activas=caminatas_activas, 
                                       pasaremos_a_comer_opciones=pasaremos_a_comer_opciones)
        else:
            itinerario.hora_salida = None

        itinerario.puntos_recogida = json.dumps([item for item in puntos_recogida_list if item.strip()])

        try:
            db.session.commit()
            flash('Itinerario actualizado exitosamente!', 'success')
            return redirect(url_for('itinerario.detalle_itinerario', itinerario_id=itinerario.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el itinerario: {e}', 'danger')
            current_app.logger.error(f"Error al actualizar itinerario {itinerario_id}: {e}")
            return render_template('editar_itinerario.html', itinerario=itinerario, 
                                   caminatas_activas=caminatas_activas, 
                                   pasaremos_a_comer_opciones=pasaremos_a_comer_opciones)

    # Para GET request, decodificar puntos_recogida para el formulario
    if itinerario.puntos_recogida:
        try:
            itinerario.puntos_recogida = json.loads(itinerario.puntos_recogida)
        except json.JSONDecodeError:
            itinerario.puntos_recogida = [] # Asegurar que sea una lista vacía si hay error
    else:
        itinerario.puntos_recogida = []

    return render_template('editar_itinerario.html', itinerario=itinerario, 
                           caminatas_activas=caminatas_activas, 
                           pasaremos_a_comer_opciones=pasaremos_a_comer_opciones)

# Ruta para eliminar un itinerario
@itinerario_bp.route('/eliminar/<int:itinerario_id>', methods=['POST'])
@login_required
def eliminar_itinerario(itinerario_id):
    itinerario = Itinerario.query.get_or_404(itinerario_id)
    
    try:
        db.session.delete(itinerario)
        db.session.commit()
        flash('Itinerario eliminado exitosamente!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el itinerario: {e}', 'danger')
        current_app.logger.error(f"Error al eliminar itinerario {itinerario_id}: {e}")
    
    return redirect(url_for('itinerario.ver_itinerario'))

# --- Funciones de Exportación ---

def _get_itinerario_details_as_text(itinerario):
    """Genera una cadena de texto con los detalles del itinerario para exportación."""
    details = []
    details.append(f"Itinerario para la Caminata: {itinerario.caminata.nombre}")
    details.append(f"Fecha de la Caminata: {itinerario.caminata.fecha.strftime('%d-%m-%Y')}")
    details.append("----------------------------------------")

    if itinerario.lugar_salida:
        details.append(f"Lugar de Salida: {itinerario.lugar_salida}")
    if itinerario.hora_salida:
        details.append(f"Hora de Salida: {itinerario.hora_salida.strftime('%H:%M')}")
    
    puntos_recogida_list = []
    if itinerario.puntos_recogida:
        try:
            puntos_recogida_list = json.loads(itinerario.puntos_recogida)
        except json.JSONDecodeError:
            puntos_recogida_list = ["Error al cargar puntos de recogida."]

    if puntos_recogida_list:
        details.append("\nPuntos de Recogida:")
        for i, punto in enumerate(puntos_recogida_list):
            details.append(f"  {i+1}. {punto}")
    
    if itinerario.pasaremos_a_comer:
        details.append(f"\nPasaremos a comer: {itinerario.pasaremos_a_comer}")

    if itinerario.contenido_itinerario:
        clean_contenido = BeautifulSoup(itinerario.contenido_itinerario, "html.parser").get_text()
        if clean_contenido.strip():
            details.append(f"\nContenido del Itinerario:\n{clean_contenido.strip()}")
    
    details.append(f"\nFecha de Creación: {itinerario.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')}")
    details.append(f"Última Modificación: {itinerario.fecha_modificacion.strftime('%Y-%m-%d %H:%M:%S') if itinerario.fecha_modificacion else 'N/A'}")

    return "\n".join(details)

@itinerario_bp.route('/exportar/pdf/<int:itinerario_id>')
@login_required
def exportar_itinerario_pdf(itinerario_id):
    itinerario = Itinerario.query.get_or_404(itinerario_id)
    itinerario_text = _get_itinerario_details_as_text(itinerario)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.multi_cell(0, 10, f"ITINERARIO DE LA CAMINATA: {itinerario.caminata.nombre.upper()}", align='C')
    pdf.ln(10)

    for line in itinerario_text.split('\n'):
        if line.startswith("---"):
            pdf.set_font("Arial", style='B', size=12)
        elif line.startswith("  "): # Puntos de recogida
            pdf.set_font("Arial", size=10)
        elif line.startswith("Contenido del Itinerario:"):
            pdf.set_font("Arial", style='B', size=12)
        else:
            pdf.set_font("Arial", size=10)
        
        pdf.multi_cell(0, 7, line.encode('latin-1', 'replace').decode('latin-1'))
    
    pdf_output = pdf.output(dest='S').encode('latin-1')
    pdf_stream = io.BytesIO(pdf_output)
    pdf_stream.seek(0)

    filename = f"itinerario_{itinerario.caminata.nombre.replace(' ', '_').lower()}.pdf"
    return send_file(
        pdf_stream,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@itinerario_bp.route('/exportar/txt/<int:itinerario_id>')
@login_required
def exportar_itinerario_txt(itinerario_id):
    itinerario = Itinerario.query.get_or_404(itinerario_id)
    itinerario_text = _get_itinerario_details_as_text(itinerario)

    buffer = io.BytesIO()
    buffer.write(itinerario_text.encode('utf-8'))
    buffer.seek(0)
    
    filename = f"itinerario_{itinerario.caminata.nombre.replace(' ', '_').lower()}.txt"
    return send_file(
        buffer,
        mimetype='text/plain',
        as_attachment=True,
        download_name=filename
    )

@itinerario_bp.route('/exportar/jpg/<int:itinerario_id>')
@login_required
def exportar_itinerario_jpg(itinerario_id):
    itinerario = Itinerario.query.get_or_404(itinerario_id)
    itinerario_text = _get_itinerario_details_as_text(itinerario)

    # Configuración de la fuente y tamaño
    font_size = 20
    font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'arial.ttf')
    try:
        font = ImageFont.truetype(font_path, font_size)
        font_bold = ImageFont.truetype(os.path.join(current_app.root_path, 'static', 'fonts', 'arialbd.ttf'), font_size)
        font_small = ImageFont.truetype(font_path, int(font_size * 0.8))
    except IOError:
        print("Advertencia: No se encontraron las fuentes Arial. Usando la fuente por defecto.")
        font = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Calcular el tamaño de la imagen necesario
    dummy_img = Image.new('RGB', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    lines = itinerario_text.split('\n')
    max_line_width = 0
    total_text_height = 0
    
    for line in lines:
        current_font = font
        if line.startswith("---") or line.startswith("Contenido del Itinerario:"):
            current_font = font_bold
        elif line.startswith("  "): # Puntos de recogida
            current_font = font_small
        
        bbox = dummy_draw.textbbox((0, 0), line, font=current_font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1] + 5 # Añadir un pequeño margen entre líneas

        max_line_width = max(max_line_width, line_width)
        total_text_height += line_height

    padding = 30
    img_width = int(max_line_width + (2 * padding))
    img_height = int(total_text_height + (2 * padding))
    
    img = Image.new('RGB', (img_width, img_height), color='white')
    d = ImageDraw.Draw(img)

    y_offset = padding
    for line in lines:
        current_font = font
        if line.startswith("---") or line.startswith("Contenido del Itinerario:"):
            current_font = font_bold
        elif line.startswith("  "): # Puntos de recogida
            current_font = font_small

        d.text((padding, y_offset), line, fill=(0, 0, 0), font=current_font) 
        bbox = d.textbbox((0,0), line, font=current_font)
        line_height_actual = bbox[3] - bbox[1] + 5
        y_offset += line_height_actual

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)

    filename = f"itinerario_{itinerario.caminata.nombre.replace(' ', '_').lower()}.jpg"
    return send_file(img_byte_arr, mimetype='image/jpeg', as_attachment=True, download_name=filename)
