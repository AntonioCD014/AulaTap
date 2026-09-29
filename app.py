"""
app.py - Backend Flask para DeciPuntos PWA
Gestión de estudiantes, asignación de puntos por NFC/manual, reportería y exportación.
"""
import io
import os
import csv
from datetime import datetime, date, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, session, redirect, url_for
from werkzeug.utils import secure_filename
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from database import db, Estudiante, Transaccion, Usuario, Canal, MaterialBiblioteca, Evaluacion, EntregaTarea, DescargaMaterial

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuración SQLite y Almacenamiento de Archivos
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'decipuntos.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'biblioteca')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
UPLOAD_ENTREGAS_FOLDER = os.path.join(BASE_DIR, 'uploads', 'entregas')
os.makedirs(UPLOAD_ENTREGAS_FOLDER, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'aulatap-docente-nfc-secret-key-2026'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_ENTREGAS_FOLDER'] = UPLOAD_ENTREGAS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # Máximo 32 MB por archivo

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg', 'webp', 'mp4', 'zip', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Inicializar SQLAlchemy
db.init_app(app)

# Crear tablas automáticamente al arrancar
with app.app_context():
    db.create_all()


# ==========================================
# DECORADORES DE AUTENTICACIÓN Y ROLES
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'No autorizado. Debe iniciar sesión.'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'No autorizado. Debe iniciar sesión.'}), 401
            return redirect(url_for('login'))
        if session.get('user_role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Acceso denegado. Se requieren permisos de administrador.'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# RUTAS DE PWA (Manifest & Service Worker)
# ==========================================
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_sw():
    response = send_from_directory('static', 'sw.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response

# ==========================================
# SHOWCASE & MOCKUP INTERACTIVO
# ==========================================
@app.route('/mockup')
@app.route('/demo')
def show_mockup():
    """Showcase y demo interactiva del ecosistema AulaTap."""
    return render_template('mockup.html')


# ==========================================
# RUTAS DE AUTENTICACIÓN (LOGIN & LOGOUT)
# ==========================================
@app.route('/login')
def login():
    """Muestra la pantalla de inicio de sesión."""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """Valida credenciales y crea la sesión del docente."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña son requeridos.'}), 400

    usuario = Usuario.query.filter(
        (db.func.lower(Usuario.username) == username.lower()) |
        (db.func.lower(Usuario.email) == username.lower())
    ).first()

    if not usuario or not usuario.check_password(password):
        return jsonify({'error': 'Credenciales inválidas. Verifique usuario y clave.'}), 401

    # Establecer sesión
    session['user_id'] = usuario.id
    session['user_name'] = usuario.nombre
    session['username'] = usuario.username
    session['user_role'] = usuario.rol

    return jsonify({
        'success': True,
        'usuario': usuario.to_dict(),
        'mensaje': f'Bienvenido/a, {usuario.nombre}'
    })

@app.route('/logout')
def logout():
    """Cierra la sesión del docente y redirige al login."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Cierra la sesión vía API."""
    session.clear()
    return jsonify({'success': True, 'mensaje': 'Sesión cerrada exitosamente.'})

@app.route('/api/me', methods=['GET'])
def api_me():
    """Retorna los datos del usuario actual en sesión."""
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 401
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        session.clear()
        return jsonify({'authenticated': False}), 401
    return jsonify({
        'authenticated': True,
        'usuario': usuario.to_dict()
    })

# ==========================================
# RUTA PRINCIPAL (PROTEGIDA)
# ==========================================
@app.route('/')
@login_required
def index():
    return render_template(
        'index.html',
        usuario_nombre=session.get('user_name', 'Docente'),
        usuario_rol=session.get('user_role', 'docente')
    )


# ==========================================
# API DE ESTUDIANTES (PROTEGIDAS)
# ==========================================
@app.route('/api/estudiantes', methods=['GET'])
@login_required
def get_estudiantes():
    """Obtiene la lista de estudiantes con filtro opcional de curso o búsqueda."""
    curso = request.args.get('curso')
    query = request.args.get('q', '').strip().lower()

    stmt = Estudiante.query
    if curso and curso != 'todos':
        stmt = stmt.filter(Estudiante.curso == curso)

    estudiantes = stmt.order_by(Estudiante.nombre_completo.asc()).all()

    if query:
        estudiantes = [
            e for e in estudiantes
            if query in e.nombre_completo.lower()
            or (e.rut and query in e.rut.lower())
            or (e.nfc_uid and query in e.nfc_uid.lower())
        ]

    return jsonify([e.to_dict() for e in estudiantes])

def calcular_insignias_estudiante(estudiante):
    """
    Calcula dinámicamente el estado y progreso de todas las insignias/logros para un estudiante.
    Retorna una lista de diccionarios con el detalle de cada insignia.
    """
    if not estudiante:
        return []

    # 1. Racha de Fuego: Participó en 3 clases o fechas distintas
    fechas_transacciones = set()
    transacciones_equipo = 0
    for t in estudiante.transacciones:
        if t.puntos > 0:
            fechas_transacciones.add(t.fecha_hora.date())
        motivo_lower = (t.motivo or '').lower()
        if any(w in motivo_lower for w in ['equipo', 'colabora', 'compañer', 'solidari', 'grupo', 'pareja']):
            transacciones_equipo += 1

    dias_participacion = len(fechas_transacciones)
    racha_desbloqueada = dias_participacion >= 3

    # 2. Compañero Solidario: Reconocido por trabajo en equipo
    companero_desbloqueado = transacciones_equipo >= 1

    # 3. Lector Imparable: Descargó materiales o guías de estudio
    materiales_descargados = set()
    if hasattr(estudiante, 'descargas'):
        for d in estudiante.descargas:
            materiales_descargados.add(d.material_id)
    total_descargas = len(materiales_descargados)
    lector_desbloqueado = total_descargas >= 2

    # 4. Gran Maestro: Acumuló 20+ décimas en el semestre
    gran_maestro_desbloqueado = (estudiante.puntaje_acumulado >= 20)

    # 5. Misión Cumplida: Envió al menos 1 tarea o evidencia al buzón
    total_entregas = len(estudiante.entregas) if hasattr(estudiante, 'entregas') else 0
    mision_desbloqueada = total_entregas >= 1

    # 6. Primer Paso: Obtuvo su primera décima
    primer_paso_desbloqueado = (estudiante.puntaje_acumulado >= 1)

    insignias = [
        {
            'id': 'racha_fuego',
            'nombre': 'Racha de Fuego',
            'icono': '⚡',
            'categoria': 'Participación',
            'rareza': 'Especial',
            'descripcion': 'Participó en 3 clases o actividades distintas.',
            'desbloqueado': racha_desbloqueada,
            'progreso_actual': min(dias_participacion, 3),
            'meta': 3,
            'unidad': 'clases',
            'color': '#f59e0b',
            'gradiente': 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)'
        },
        {
            'id': 'companero_solidario',
            'nombre': 'Compañero Solidario',
            'icono': '🤝',
            'categoria': 'Convivencia',
            'rareza': 'Épica',
            'descripcion': 'Reconocido por trabajo colaborativo o en equipo.',
            'desbloqueado': companero_desbloqueado,
            'progreso_actual': min(transacciones_equipo, 1),
            'meta': 1,
            'unidad': 'mención',
            'color': '#10b981',
            'gradiente': 'linear-gradient(135deg, #059669 0%, #10b981 100%)'
        },
        {
            'id': 'lector_imparable',
            'nombre': 'Lector Imparable',
            'icono': '📚',
            'categoria': 'Estudio',
            'rareza': 'Rara',
            'descripcion': 'Descargó y revisó las guías y materiales de la unidad.',
            'desbloqueado': lector_desbloqueado,
            'progreso_actual': min(total_descargas, 2),
            'meta': 2,
            'unidad': 'guías',
            'color': '#06b6d4',
            'gradiente': 'linear-gradient(135deg, #0284c7 0%, #06b6d4 100%)'
        },
        {
            'id': 'gran_maestro',
            'nombre': 'Gran Maestro',
            'icono': '👑',
            'categoria': 'Excelencia',
            'rareza': 'Legendaria',
            'descripcion': 'Acumuló 20 o más décimas en el período escolar.',
            'desbloqueado': gran_maestro_desbloqueado,
            'progreso_actual': min(estudiante.puntaje_acumulado, 20),
            'meta': 20,
            'unidad': 'décimas',
            'color': '#8b5cf6',
            'gradiente': 'linear-gradient(135deg, #7c3aed 0%, #d946ef 100%)'
        },
        {
            'id': 'mision_cumplida',
            'nombre': 'Misión Cumplida',
            'icono': '📤',
            'categoria': 'Responsabilidad',
            'rareza': 'Especial',
            'descripcion': 'Envió una tarea o evidencia resuelta al buzón digital.',
            'desbloqueado': mision_desbloqueada,
            'progreso_actual': min(total_entregas, 1),
            'meta': 1,
            'unidad': 'tarea',
            'color': '#ec4899',
            'gradiente': 'linear-gradient(135deg, #db2777 0%, #f43f5e 100%)'
        },
        {
            'id': 'primer_paso',
            'nombre': 'Primer Paso',
            'icono': '⭐',
            'categoria': 'Inicio',
            'rareza': 'Común',
            'descripcion': 'Obtuvo su primera décima por mérito en clase.',
            'desbloqueado': primer_paso_desbloqueado,
            'progreso_actual': min(estudiante.puntaje_acumulado, 1),
            'meta': 1,
            'unidad': 'décima',
            'color': '#3b82f6',
            'gradiente': 'linear-gradient(135deg, #2563eb 0%, #60a5fa 100%)'
        }
    ]

    return insignias

@app.route('/api/estudiantes/<int:estudiante_id>', methods=['GET'])
@login_required
def get_estudiante(estudiante_id):
    """Obtiene un estudiante y su historial reciente de transacciones e insignias."""
    estudiante = db.get_or_404(Estudiante, estudiante_id)
    transacciones = (
        Transaccion.query
        .filter_by(estudiante_id=estudiante.id)
        .order_by(Transaccion.fecha_hora.desc())
        .limit(10)
        .all()
    )

    data = estudiante.to_dict()
    data['historial'] = [t.to_dict() for t in transacciones]
    insignias = calcular_insignias_estudiante(estudiante)
    data['insignias'] = insignias
    data['total_insignias_desbloqueadas'] = sum(1 for i in insignias if i['desbloqueado'])
    data['total_insignias'] = len(insignias)
    return jsonify(data)

@app.route('/api/estudiantes/nfc/<path:uid>', methods=['GET'])
@login_required
def get_estudiante_by_nfc(uid):
    """
    Busca al estudiante asociado a un UID NFC (soporta normalización).
    """
    clean_uid = uid.strip().lower()
    estudiante = Estudiante.query.filter(
        db.func.lower(Estudiante.nfc_uid) == clean_uid
    ).first()

    if not estudiante:
        return jsonify({
            'error': 'Tarjeta no registrada',
            'nfc_uid': clean_uid,
            'message': f'La tarjeta con UID {clean_uid} no está vinculada a ningún estudiante.'
        }), 404

    transacciones = (
        Transaccion.query
        .filter_by(estudiante_id=estudiante.id)
        .order_by(Transaccion.fecha_hora.desc())
        .limit(5)
        .all()
    )

    data = estudiante.to_dict()
    data['historial'] = [t.to_dict() for t in transacciones]
    insignias = calcular_insignias_estudiante(estudiante)
    data['insignias'] = insignias
    data['total_insignias_desbloqueadas'] = sum(1 for i in insignias if i['desbloqueado'])
    data['total_insignias'] = len(insignias)
    return jsonify(data)

@app.route('/api/estudiantes', methods=['POST'])
@login_required
def create_estudiante():
    """Registra un nuevo estudiante."""
    data = request.get_json() or {}
    nombre = data.get('nombre_completo', '').strip()
    curso = data.get('curso', '').strip().upper()
    rut = data.get('rut', '').strip() or None
    nfc_uid = data.get('nfc_uid', '').strip().lower() or None

    if not nombre or not curso:
        return jsonify({'error': 'El nombre completo y el curso son obligatorios.'}), 400

    if rut and Estudiante.query.filter_by(rut=rut).first():
        return jsonify({'error': f'El RUT {rut} ya se encuentra registrado.'}), 400

    if nfc_uid and Estudiante.query.filter_by(nfc_uid=nfc_uid).first():
        return jsonify({'error': f'El UID NFC {nfc_uid} ya está asignado a otro estudiante.'}), 400

    nuevo = Estudiante(
        nombre_completo=nombre,
        curso=curso,
        rut=rut,
        nfc_uid=nfc_uid,
        puntaje_acumulado=0
    )
    db.session.add(nuevo)
    db.session.commit()

    return jsonify(nuevo.to_dict()), 201

@app.route('/api/estudiantes/<int:estudiante_id>/puntos', methods=['POST'])
@login_required
def asignar_puntos(estudiante_id):
    """Asigna o resta puntos/décimas a un estudiante y registra la transacción."""
    estudiante = db.get_or_404(Estudiante, estudiante_id)
    data = request.get_json() or {}

    try:
        puntos = int(data.get('puntos', 1))
    except (ValueError, TypeError):
        return jsonify({'error': 'Puntaje inválido'}), 400

    motivo = data.get('motivo', 'Participación').strip() or 'Participación'

    # Actualizar acumulado (evitar negativos si es política del aula, o permitir hasta 0)
    nuevo_puntaje = estudiante.puntaje_acumulado + puntos
    if nuevo_puntaje < 0:
        nuevo_puntaje = 0

    estudiante.puntaje_acumulado = nuevo_puntaje

    # Registrar transacción
    transaccion = Transaccion(
        estudiante_id=estudiante.id,
        puntos=puntos,
        motivo=motivo
    )
    db.session.add(transaccion)
    db.session.commit()

    insignias = calcular_insignias_estudiante(estudiante)
    est_dict = estudiante.to_dict()
    est_dict['insignias'] = insignias
    est_dict['total_insignias_desbloqueadas'] = sum(1 for i in insignias if i.get('desbloqueado') or i.get('desbloqueada'))
    est_dict['total_insignias'] = len(insignias)

    return jsonify({
        'success': True,
        'estudiante': est_dict,
        'transaccion': transaccion.to_dict(),
        'mensaje': f'Se han asignado {puntos:+d} punto(s) a {estudiante.nombre_completo}.'
    })

@app.route('/api/estudiantes/<int:estudiante_id>/vincular-nfc', methods=['POST'])
@login_required
def vincular_nfc(estudiante_id):
    """Vincula una tarjeta o llavero NFC a un estudiante."""
    estudiante = db.get_or_404(Estudiante, estudiante_id)
    data = request.get_json() or {}
    uid = data.get('nfc_uid', '').strip().lower()

    if not uid:
        return jsonify({'error': 'El UID de la tarjeta es requerido'}), 400

    # Verificar si otra persona ya tiene esa tarjeta
    otro = Estudiante.query.filter(
        db.func.lower(Estudiante.nfc_uid) == uid,
        Estudiante.id != estudiante.id
    ).first()

    if otro:
        return jsonify({
            'error': f'Esa tarjeta ya está asignada a {otro.nombre_completo} ({otro.curso}).'
        }), 409

    estudiante.nfc_uid = uid
    db.session.commit()

    return jsonify({
        'success': True,
        'estudiante': estudiante.to_dict(),
        'mensaje': f'Tarjeta {uid} vinculada correctamente a {estudiante.nombre_completo}.'
    })

@app.route('/api/estudiantes/<int:estudiante_id>/desvincular-nfc', methods=['POST'])
@login_required
def desvincular_nfc(estudiante_id):
    """Quita el UID de la tarjeta de un estudiante."""
    estudiante = db.get_or_404(Estudiante, estudiante_id)
    estudiante.nfc_uid = None
    db.session.commit()

    return jsonify({
        'success': True,
        'estudiante': estudiante.to_dict(),
        'mensaje': f'Tarjeta desvinculada de {estudiante.nombre_completo}.'
    })

# ==========================================
# RUTAS DE UTILIDAD & REPORTES
# ==========================================
@app.route('/api/cursos', methods=['GET'])
@login_required
def get_cursos():
    """Obtiene la lista de cursos únicos registrados."""
    cursos = [c[0] for c in db.session.query(Estudiante.curso).distinct().order_by(Estudiante.curso.asc()).all()]
    return jsonify(cursos)

@app.route('/api/transacciones/recientes', methods=['GET'])
@login_required
def get_transacciones_recientes():
    """Obtiene el registro de las últimas transacciones realizadas."""
    transacciones = (
        Transaccion.query
        .order_by(Transaccion.fecha_hora.desc())
        .limit(20)
        .all()
    )
    return jsonify([t.to_dict() for t in transacciones])

# ==========================================
# EXPORTACIÓN (EXCEL & CSV)
# ==========================================
@app.route('/api/exportar/excel', methods=['GET'])
@login_required
def exportar_excel():
    """Genera y descarga un archivo Excel (.xlsx) con el resumen de puntos por alumno."""
    curso = request.args.get('curso')

    query = Estudiante.query
    if curso and curso != 'todos':
        query = query.filter(Estudiante.curso == curso)

    estudiantes = query.order_by(Estudiante.curso.asc(), Estudiante.nombre_completo.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = f"AulaTap_{curso or 'General'}"

    # Estilos de encabezado
    header_fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
    header_font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=11)
    bold_font = Font(name="Calibri", size=11, bold=True)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Título del reporte
    ws.merge_cells('A1:F1')
    title_cell = ws['A1']
    title_cell.value = f"REPORTE DE EVALUACIÓN FORMATIVA - AULATAP - {curso.upper() if curso and curso != 'todos' else 'TODOS LOS CURSOS'}"
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells('A2:F2')
    sub_cell = ws['A2']
    sub_cell.value = f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Total Alumnos: {len(estudiantes)}"
    sub_cell.font = Font(name="Calibri", size=10, italic=True, color="64748B")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18

    # Encabezados
    headers = ["#", "Curso", "RUT / ID", "Estudiante", "UID Tarjeta NFC", "Décimas / Puntos"]
    ws.append([]) # Fila 3 vacía
    ws.append(headers)
    ws.row_dimensions[4].height = 24

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align if col_idx in [1, 2, 3, 5, 6] else left_align
        cell.border = thin_border

    # Datos
    for idx, e in enumerate(estudiantes, 1):
        row_num = 4 + idx
        ws.append([
            idx,
            e.curso,
            e.rut or "S/R",
            e.nombre_completo,
            e.nfc_uid or "No vinculada",
            e.puntaje_acumulado
        ])
        ws.row_dimensions[row_num].height = 20

        for col_idx in range(1, 7):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = bold_font if col_idx == 6 else data_font
            cell.alignment = center_align if col_idx in [1, 2, 3, 5, 6] else left_align
            cell.border = thin_border

            # Resaltar puntajes
            if col_idx == 6 and e.puntaje_acumulado > 0:
                cell.fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")

    # Ajustar ancho de columnas
    col_widths = [6, 12, 18, 38, 26, 18]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    # Guardar en memoria y enviar
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"AulaTap_{curso or 'General'}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/exportar/csv', methods=['GET'])
@login_required
def exportar_csv():
    """Genera y descarga un CSV con codificación UTF-8-SIG para abrir en Excel en español."""
    curso = request.args.get('curso')

    query = Estudiante.query
    if curso and curso != 'todos':
        query = query.filter(Estudiante.curso == curso)

    estudiantes = query.order_by(Estudiante.curso.asc(), Estudiante.nombre_completo.asc()).all()

    output = io.StringIO()
    # Punto y coma para compatibilidad directa con Excel en español / Chile / Latam
    writer = csv.writer(output, delimiter=';')

    writer.writerow(["#", "Curso", "RUT", "Nombre Completo", "UID Tarjeta NFC", "Puntos Acumulados"])
    for idx, e in enumerate(estudiantes, 1):
        writer.writerow([
            idx,
            e.curso,
            e.rut or "",
            e.nombre_completo,
            e.nfc_uid or "",
            e.puntaje_acumulado
        ])

    # Convertir a bytes con BOM (utf-8-sig)
    csv_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    filename = f"AulaTap_{curso or 'General'}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    return send_file(
        csv_bytes,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )

# ==========================================
# BIBLIOTECA DIGITAL Y CANALES
# ==========================================

@app.route('/api/biblioteca/canales', methods=['GET'])
def get_biblioteca_canales():
    """Retorna la lista de canales disponibles en la biblioteca."""
    canales = Canal.query.order_by(Canal.orden.asc()).all()
    return jsonify([c.to_dict() for c in canales])

@app.route('/api/biblioteca/materiales', methods=['GET'])
def get_biblioteca_materiales():
    """
    Obtiene los materiales de la biblioteca con filtros de curso, canal y búsqueda.
    Accesible para docentes y estudiantes.
    """
    curso = request.args.get('curso', '').strip().upper()
    canal_slug = request.args.get('canal', '').strip().lower()
    canal_id = request.args.get('canal_id', type=int)
    query = request.args.get('q', '').strip().lower()

    stmt = MaterialBiblioteca.query

    # Filtrar por canal
    if canal_id:
        stmt = stmt.filter(MaterialBiblioteca.canal_id == canal_id)
    elif canal_slug and canal_slug != 'todos':
        stmt = stmt.join(Canal).filter(Canal.slug == canal_slug)

    # Filtrar por curso (un curso ve el suyo y además los materiales 'TODOS')
    if curso and curso != 'TODOS':
        stmt = stmt.filter(MaterialBiblioteca.curso.in_([curso, 'TODOS']))

    # Orden cronológico: clases por fecha_clase desc, otros por creado_en desc
    materiales = stmt.order_by(
        MaterialBiblioteca.fecha_clase.desc().nullslast(),
        MaterialBiblioteca.creado_en.desc()
    ).all()

    if query:
        materiales = [
            m for m in materiales
            if query in m.titulo.lower()
            or (m.descripcion and query in m.descripcion.lower())
            or (m.curso and query in m.curso.lower())
        ]

    return jsonify([m.to_dict() for m in materiales])

@app.route('/api/biblioteca/materiales', methods=['POST'])
@login_required
def create_biblioteca_material():
    """
    Crea un nuevo material en la biblioteca (archivo, enlace web o texto/apunte).
    Solo para docentes autenticados.
    """
    # Detectar si viene como multipart/form-data o JSON
    if request.content_type and 'multipart/form-data' in request.content_type:
        canal_id = request.form.get('canal_id', type=int)
        canal_slug = request.form.get('canal_slug', '').strip().lower()
        curso = request.form.get('curso', 'TODOS').strip().upper()
        titulo = request.form.get('titulo', '').strip()
        descripcion = request.form.get('descripcion', '').strip() or None
        tipo = request.form.get('tipo', 'archivo').strip().lower()
        url_recurso = request.form.get('url_recurso', '').strip() or None
        fecha_clase_str = request.form.get('fecha_clase', '').strip()
        file = request.files.get('file')
    else:
        data = request.get_json() or {}
        canal_id = data.get('canal_id')
        canal_slug = data.get('canal_slug', '').strip().lower()
        curso = data.get('curso', 'TODOS').strip().upper()
        titulo = data.get('titulo', '').strip()
        descripcion = data.get('descripcion', '').strip() or None
        tipo = data.get('tipo', 'enlace').strip().lower()
        url_recurso = data.get('url_recurso', '').strip() or None
        fecha_clase_str = data.get('fecha_clase', '').strip()
        file = None

    if not titulo:
        return jsonify({'error': 'El título del material es obligatorio.'}), 400

    if not canal_id and canal_slug:
        canal_obj = Canal.query.filter_by(slug=canal_slug).first()
        if canal_obj:
            canal_id = canal_obj.id

    if not canal_id:
        return jsonify({'error': 'Debe seleccionar un canal válido.'}), 400

    # Parsear fecha de la clase si corresponde
    fecha_clase = None
    if fecha_clase_str:
        try:
            fecha_clase = datetime.strptime(fecha_clase_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    nombre_archivo = None
    tamano_bytes = None

    # Procesar archivo si se envió
    if file and file.filename:
        if not allowed_file(file.filename):
            return jsonify({'error': 'Tipo de archivo no permitido. Formatos aceptados: PDF, Office, imágenes, videos o ZIP.'}), 400

        original_filename = secure_filename(file.filename) or 'archivo_adjunto'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{original_filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
        file.save(filepath)

        tipo = 'archivo'
        url_recurso = saved_filename
        nombre_archivo = file.filename
        tamano_bytes = os.path.getsize(filepath)

    nuevo_material = MaterialBiblioteca(
        canal_id=canal_id,
        curso=curso,
        titulo=titulo,
        descripcion=descripcion,
        tipo=tipo,
        url_recurso=url_recurso,
        nombre_archivo=nombre_archivo,
        tamano_bytes=tamano_bytes,
        fecha_clase=fecha_clase
    )
    db.session.add(nuevo_material)
    db.session.commit()

    return jsonify({
        'success': True,
        'material': nuevo_material.to_dict(),
        'mensaje': 'Material añadido a la biblioteca exitosamente.'
    }), 201

@app.route('/api/biblioteca/materiales/<int:material_id>', methods=['DELETE'])
@login_required
def delete_biblioteca_material(material_id):
    """Elimina un material de la biblioteca y su archivo físico si aplica."""
    material = db.get_or_404(MaterialBiblioteca, material_id)

    # Si tenía archivo físico local, eliminarlo del disco
    if material.tipo == 'archivo' and material.url_recurso:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], material.url_recurso)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                app.logger.warning(f"No se pudo eliminar archivo físico {filepath}: {e}")

    db.session.delete(material)
    db.session.commit()

    return jsonify({
        'success': True,
        'mensaje': f'Material "{material.titulo}" eliminado con éxito.'
    })

@app.route('/biblioteca/descargar/<int:material_id>')
def descargar_recurso(material_id):
    """Permite ver o descargar un recurso de la biblioteca o redirige si es enlace web."""
    material = db.get_or_404(MaterialBiblioteca, material_id)

    if material.tipo == 'enlace' and material.url_recurso:
        return redirect(material.url_recurso)

    if material.tipo == 'archivo' and material.url_recurso:
        return send_from_directory(
            app.config['UPLOAD_FOLDER'],
            material.url_recurso,
            as_attachment=request.args.get('download', '0') == '1',
            download_name=material.nombre_archivo or material.url_recurso
        )

    return jsonify({'error': 'Este material no contiene un archivo descargable.'}), 404

# ==========================================
# RUTAS DE EVALUACIONES Y CALENDARIO
# ==========================================
@app.route('/api/evaluaciones', methods=['GET'])
def get_evaluaciones():
    """
    Retorna la lista de evaluaciones ordenadas por fecha ascendente.
    Soporta filtros opcionales por curso, mes y año.
    """
    curso = request.args.get('curso', '').strip().upper()
    mes = request.args.get('mes', type=int)
    anio = request.args.get('anio', type=int)

    query = Evaluacion.query

    if curso and curso != 'TODOS':
        query = query.filter(Evaluacion.curso.in_([curso, 'TODOS']))

    if anio:
        query = query.filter(db.extract('year', Evaluacion.fecha) == anio)
    if mes:
        query = query.filter(db.extract('month', Evaluacion.fecha) == mes)

    evaluaciones = query.order_by(Evaluacion.fecha.asc(), Evaluacion.hora.asc().nullslast()).all()
    return jsonify([e.to_dict() for e in evaluaciones])

@app.route('/api/evaluaciones/<int:eval_id>', methods=['GET'])
def get_evaluacion_by_id(eval_id):
    """Retorna una evaluación específica por ID."""
    evaluacion = Evaluacion.query.get_or_404(eval_id)
    return jsonify(evaluacion.to_dict())

@app.route('/api/evaluaciones', methods=['POST'])
@login_required
def create_evaluacion():
    """Crea una nueva evaluación o prueba agendada."""
    data = request.get_json() or {}
    titulo = data.get('titulo', '').strip()
    curso = data.get('curso', 'TODOS').strip().upper()
    tipo = data.get('tipo', 'Prueba Sumativa').strip()
    fecha_str = data.get('fecha', '').strip()
    hora = data.get('hora', '').strip() or None
    descripcion = data.get('descripcion', '').strip() or None
    max_decimas = data.get('max_decimas', 5)

    if not titulo:
        return jsonify({'error': 'El título de la evaluación es obligatorio.'}), 400
    if not fecha_str:
        return jsonify({'error': 'La fecha de la evaluación es obligatoria.'}), 400

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Utilice AAAA-MM-DD.'}), 400

    try:
        max_decimas = int(max_decimas)
    except (TypeError, ValueError):
        max_decimas = 5

    nueva_eval = Evaluacion(
        curso=curso,
        titulo=titulo,
        tipo=tipo,
        fecha=fecha,
        hora=hora,
        descripcion=descripcion,
        max_decimas=max(0, max_decimas)
    )

    db.session.add(nueva_eval)
    db.session.commit()

    return jsonify({
        'success': True,
        'mensaje': 'Evaluación agendada exitosamente.',
        'evaluacion': nueva_eval.to_dict()
    }), 201

@app.route('/api/evaluaciones/<int:eval_id>', methods=['PUT'])
@login_required
def update_evaluacion(eval_id):
    """Actualiza una evaluación existente."""
    evaluacion = Evaluacion.query.get_or_404(eval_id)
    data = request.get_json() or {}

    if 'titulo' in data:
        titulo = data['titulo'].strip()
        if not titulo:
            return jsonify({'error': 'El título no puede estar vacío.'}), 400
        evaluacion.titulo = titulo

    if 'curso' in data:
        evaluacion.curso = data['curso'].strip().upper() or 'TODOS'

    if 'tipo' in data:
        evaluacion.tipo = data['tipo'].strip()

    if 'fecha' in data:
        fecha_str = data['fecha'].strip()
        try:
            evaluacion.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Utilice AAAA-MM-DD.'}), 400

    if 'hora' in data:
        evaluacion.hora = data['hora'].strip() or None

    if 'descripcion' in data:
        evaluacion.descripcion = data['descripcion'].strip() or None

    if 'max_decimas' in data:
        try:
            evaluacion.max_decimas = max(0, int(data['max_decimas']))
        except (TypeError, ValueError):
            pass

    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': 'Evaluación actualizada correctamente.',
        'evaluacion': evaluacion.to_dict()
    })

@app.route('/api/evaluaciones/<int:eval_id>', methods=['DELETE'])
@login_required
def delete_evaluacion(eval_id):
    """Elimina una evaluación agendada."""
    evaluacion = Evaluacion.query.get_or_404(eval_id)
    db.session.delete(evaluacion)
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': 'Evaluación eliminada correctamente.'
    })

@app.route('/api/portal/evaluaciones', methods=['GET'])
def get_portal_evaluaciones():
    """
    Retorna las evaluaciones para el portal del estudiante según su curso.
    """
    curso = request.args.get('curso', '').strip().upper()
    query = Evaluacion.query

    if curso and curso != 'TODOS':
        query = query.filter(Evaluacion.curso.in_([curso, 'TODOS']))

    evaluaciones = query.order_by(Evaluacion.fecha.asc(), Evaluacion.hora.asc().nullslast()).all()
    return jsonify([e.to_dict() for e in evaluaciones])

# ==========================================
# PORTAL DEL ESTUDIANTE (VISTA PÚBLICA)
# ==========================================
@app.route('/portal')
def portal_estudiante():
    """Vista web amigable para que estudiantes consulten sus clases, guías y décimas."""
    return render_template('portal_estudiante.html')

@app.route('/api/portal/cursos', methods=['GET'])
def get_portal_cursos():
    """Retorna la lista de cursos disponibles para el portal de estudiantes."""
    cursos = [c[0] for c in db.session.query(Estudiante.curso).distinct().order_by(Estudiante.curso.asc()).all()]
    return jsonify(cursos)

@app.route('/api/portal/identificar', methods=['GET'])
def portal_identificar():
    """
    Busca al estudiante mediante NFC UID o RUT, o carga el material directo del curso.
    """
    nfc_uid = request.args.get('nfc_uid', '').strip().lower()
    rut = request.args.get('rut', '').strip().upper()
    curso = request.args.get('curso', '').strip().upper()

    estudiante = None

    if nfc_uid:
        estudiante = Estudiante.query.filter(db.func.lower(Estudiante.nfc_uid) == nfc_uid).first()
    elif rut:
        # Búsqueda flexible de RUT eliminando puntos y guión
        rut_clean = rut.replace('.', '').replace('-', '').lower()
        todos_estudiantes = Estudiante.query.all()
        for e in todos_estudiantes:
            if e.rut:
                e_clean = e.rut.replace('.', '').replace('-', '').lower()
                if e_clean == rut_clean:
                    estudiante = e
                    break

    # Si se identificó a un estudiante específico
    if estudiante:
        curso_efectivo = estudiante.curso
        transacciones = (
            Transaccion.query
            .filter_by(estudiante_id=estudiante.id)
            .order_by(Transaccion.fecha_hora.desc())
            .limit(6)
            .all()
        )
        data_estudiante = estudiante.to_dict()
        data_estudiante['historial'] = [t.to_dict() for t in transacciones]
        insignias = calcular_insignias_estudiante(estudiante)
        data_estudiante['insignias'] = insignias
        data_estudiante['total_insignias_desbloqueadas'] = sum(1 for i in insignias if i['desbloqueado'])
        data_estudiante['total_insignias'] = len(insignias)

        entregas = (
            EntregaTarea.query
            .filter_by(estudiante_id=estudiante.id)
            .order_by(EntregaTarea.creado_en.desc())
            .all()
        )
        data_estudiante['entregas'] = [e.to_dict() for e in entregas]
    elif curso and curso != 'TODOS':
        curso_efectivo = curso
        data_estudiante = None
    else:
        curso_efectivo = 'TODOS'
        data_estudiante = None

    # Obtener canales
    canales = Canal.query.order_by(Canal.orden.asc()).all()

    # Obtener materiales para el curso efectivo
    query_mat = MaterialBiblioteca.query
    if curso_efectivo != 'TODOS':
        query_mat = query_mat.filter(MaterialBiblioteca.curso.in_([curso_efectivo, 'TODOS']))

    materiales = query_mat.order_by(
        MaterialBiblioteca.fecha_clase.desc().nullslast(),
        MaterialBiblioteca.creado_en.desc()
    ).all()

    # Obtener evaluaciones para el curso efectivo
    query_eval = Evaluacion.query
    if curso_efectivo != 'TODOS':
        query_eval = query_eval.filter(Evaluacion.curso.in_([curso_efectivo, 'TODOS']))
    evaluaciones = query_eval.order_by(Evaluacion.fecha.asc(), Evaluacion.hora.asc().nullslast()).all()

    return jsonify({
        'encontrado': estudiante is not None or curso != '',
        'estudiante': data_estudiante,
        'curso_activo': curso_efectivo,
        'canales': [c.to_dict() for c in canales],
        'materiales': [m.to_dict() for m in materiales],
        'evaluaciones': [e.to_dict() for e in evaluaciones],
        'entregas': data_estudiante.get('entregas', []) if data_estudiante else []
    })


# ==========================================
# BUZÓN DE ENTREGAS & TAREAS (PORTAL & DOCENTE)
# ==========================================
@app.route('/api/portal/entregas', methods=['POST'])
def portal_crear_entrega():
    """
    Permite a un estudiante subir una entrega de tarea, guía o trabajo (PDF, foto, Word).
    """
    estudiante_id = request.form.get('estudiante_id', type=int)
    material_id = request.form.get('material_id', type=int) or None
    evaluacion_id = request.form.get('evaluacion_id', type=int) or None
    titulo_tarea = request.form.get('titulo_tarea', '').strip()
    comentario = request.form.get('comentario', '').strip() or None
    file = request.files.get('file')

    if not estudiante_id:
        return jsonify({'error': 'Estudiante no identificado.'}), 400

    estudiante = db.session.get(Estudiante, estudiante_id)
    if not estudiante:
        return jsonify({'error': 'Estudiante no encontrado.'}), 404

    if not titulo_tarea:
        return jsonify({'error': 'El título o descripción de la tarea es obligatorio.'}), 400

    if not file or not file.filename:
        return jsonify({'error': 'Debe adjuntar un archivo (foto, PDF o documento).'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Formato no permitido. Formatos aceptados: PDF, Office, fotos/imágenes o ZIP.'}), 400

    original_filename = secure_filename(file.filename) or 'tarea_adjunta'
    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
    if ext in {'jpg', 'jpeg', 'png', 'webp', 'gif'}:
        tipo_archivo = 'imagen'
    elif ext == 'pdf':
        tipo_archivo = 'pdf'
    else:
        tipo_archivo = 'documento'

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    saved_filename = f"entrega_e{estudiante_id}_{timestamp}_{original_filename}"
    filepath = os.path.join(app.config['UPLOAD_ENTREGAS_FOLDER'], saved_filename)
    file.save(filepath)
    tamano_bytes = os.path.getsize(filepath)

    nueva_entrega = EntregaTarea(
        estudiante_id=estudiante_id,
        material_id=material_id,
        evaluacion_id=evaluacion_id,
        titulo_tarea=titulo_tarea,
        comentario=comentario,
        archivo_nombre=file.filename,
        archivo_url=saved_filename,
        tipo_archivo=tipo_archivo,
        tamano_bytes=tamano_bytes,
        estado='pendiente'
    )
    db.session.add(nueva_entrega)
    db.session.commit()

    return jsonify({
        'success': True,
        'mensaje': '¡Tarea entregada exitosamente al profesor!',
        'entrega': nueva_entrega.to_dict(),
        'insignias': calcular_insignias_estudiante(estudiante)
    }), 201

@app.route('/api/portal/entregas', methods=['GET'])
def portal_listar_entregas():
    """Retorna las entregas de tareas del estudiante."""
    estudiante_id = request.args.get('estudiante_id', type=int)
    if not estudiante_id:
        return jsonify({'error': 'Parámetro estudiante_id requerido.'}), 400
    entregas = (
        EntregaTarea.query
        .filter_by(estudiante_id=estudiante_id)
        .order_by(EntregaTarea.creado_en.desc())
        .all()
    )
    return jsonify([e.to_dict() for e in entregas])

@app.route('/api/portal/descargar-material/<int:material_id>')
def portal_descargar_material(material_id):
    """
    Descarga material y registra la lectura/descarga para el estudiante (habilita insignia Lector Imparable).
    """
    estudiante_id = request.args.get('estudiante_id', type=int)
    if estudiante_id:
        estudiante = db.session.get(Estudiante, estudiante_id)
        material = db.session.get(MaterialBiblioteca, material_id)
        if estudiante and material:
            existe = DescargaMaterial.query.filter_by(estudiante_id=estudiante_id, material_id=material_id).first()
            if not existe:
                descarga = DescargaMaterial(estudiante_id=estudiante_id, material_id=material_id)
                db.session.add(descarga)
                db.session.commit()

    return descargar_recurso(material_id)

@app.route('/api/docente/entregas', methods=['GET'])
@login_required
def docente_listar_entregas():
    """Lista las entregas recibidas de estudiantes con filtros por curso y estado."""
    curso = request.args.get('curso', 'todos').strip().upper()
    estado = request.args.get('estado', 'todos').strip().lower()
    material_id = request.args.get('material_id', type=int)

    query = EntregaTarea.query.join(Estudiante)
    if curso and curso != 'TODOS':
        query = query.filter(Estudiante.curso == curso)
    if estado and estado in ('pendiente', 'revisado'):
        query = query.filter(EntregaTarea.estado == estado)
    if material_id:
        query = query.filter(EntregaTarea.material_id == material_id)

    entregas = query.order_by(EntregaTarea.creado_en.desc()).all()
    return jsonify([e.to_dict() for e in entregas])

@app.route('/api/docente/entregas/contador-pendientes', methods=['GET'])
@login_required
def docente_contador_entregas_pendientes():
    """Retorna la cantidad de entregas pendientes de revisión."""
    curso = request.args.get('curso', 'todos').strip().upper()
    query = EntregaTarea.query.filter_by(estado='pendiente')
    if curso and curso != 'TODOS':
        query = query.join(Estudiante).filter(Estudiante.curso == curso)
    count = query.count()
    return jsonify({'pendientes': count})

@app.route('/api/docente/entregas/<int:entrega_id>/calificar', methods=['POST'])
@login_required
def docente_calificar_entrega(entrega_id):
    """
    Revisa una entrega, añade retroalimentación docente y opcionalmente otorga décimas.
    """
    entrega = db.get_or_404(EntregaTarea, entrega_id)
    data = request.get_json() or {}

    puntos_bonus = data.get('puntos_bonus', 0)
    try:
        puntos_bonus = max(0, int(puntos_bonus))
    except (ValueError, TypeError):
        puntos_bonus = 0

    retroalimentacion = data.get('retroalimentacion', '').strip() or None
    estado = data.get('estado', 'revisado').strip()

    # Si se otorgan puntos y no se habían otorgado antes en esta entrega
    puntos_a_sumar = puntos_bonus - entrega.puntos_otorgados
    if puntos_a_sumar > 0:
        entrega.estudiante.puntaje_acumulado += puntos_a_sumar
        transaccion = Transaccion(
            estudiante_id=entrega.estudiante_id,
            puntos=puntos_a_sumar,
            motivo=f"Tarea: {entrega.titulo_tarea}"
        )
        db.session.add(transaccion)
    elif puntos_a_sumar < 0:
        entrega.estudiante.puntaje_acumulado = max(0, entrega.estudiante.puntaje_acumulado + puntos_a_sumar)

    entrega.estado = estado
    entrega.puntos_otorgados = puntos_bonus
    entrega.retroalimentacion = retroalimentacion
    entrega.revisado_en = datetime.now(timezone.utc)

    db.session.commit()

    return jsonify({
        'success': True,
        'mensaje': f'Entrega revisada exitosamente. Décimas asignadas: +{puntos_bonus}.',
        'entrega': entrega.to_dict(),
        'estudiante': entrega.estudiante.to_dict()
    })

@app.route('/entregas/descargar/<int:entrega_id>')
def descargar_entrega(entrega_id):
    """Permite previsualizar o descargar un archivo entregado por un estudiante."""
    entrega = db.get_or_404(EntregaTarea, entrega_id)
    as_attachment = request.args.get('download', '0') == '1'
    return send_from_directory(
        app.config['UPLOAD_ENTREGAS_FOLDER'],
        entrega.archivo_url,
        as_attachment=as_attachment,
        download_name=entrega.archivo_nombre or entrega.archivo_url
    )



# ==========================================
# MÓDULO DE ADMINISTRACIÓN (VISTA & APIS)
# ==========================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Vista principal del panel de administración."""
    return render_template(
        'admin.html',
        usuario_nombre=session.get('user_name', 'Administrador'),
        usuario_rol=session.get('user_role', 'admin')
    )

# --- PILAR 1: GESTIÓN DE ESTUDIANTES & CARGA MASIVA ---

@app.route('/api/admin/estudiantes/<int:estudiante_id>', methods=['PUT'])
@admin_required
def admin_update_estudiante(estudiante_id):
    """Actualiza datos del estudiante (nombre, curso, rut, nfc_uid, puntaje)."""
    estudiante = db.get_or_404(Estudiante, estudiante_id)
    data = request.get_json() or {}

    nombre = data.get('nombre_completo', '').strip()
    curso = data.get('curso', '').strip().upper()
    rut = data.get('rut', '').strip() or None
    nfc_uid = data.get('nfc_uid', '').strip().lower() or None
    puntaje = data.get('puntaje_acumulado')

    if not nombre or not curso:
        return jsonify({'error': 'Nombre y curso son obligatorios.'}), 400

    if rut:
        otro_rut = Estudiante.query.filter(Estudiante.rut == rut, Estudiante.id != estudiante.id).first()
        if otro_rut:
            return jsonify({'error': f'El RUT {rut} ya pertenece a {otro_rut.nombre_completo}.'}), 409

    if nfc_uid:
        otro_nfc = Estudiante.query.filter(db.func.lower(Estudiante.nfc_uid) == nfc_uid, Estudiante.id != estudiante.id).first()
        if otro_nfc:
            return jsonify({'error': f'El UID NFC {nfc_uid} ya está asignado a {otro_nfc.nombre_completo}.'}), 409

    estudiante.nombre_completo = nombre
    estudiante.curso = curso
    estudiante.rut = rut
    estudiante.nfc_uid = nfc_uid
    if puntaje is not None:
        try:
            estudiante.puntaje_acumulado = max(0, int(puntaje))
        except (ValueError, TypeError):
            pass

    db.session.commit()
    return jsonify({
        'success': True,
        'estudiante': estudiante.to_dict(),
        'mensaje': f'Estudiante {estudiante.nombre_completo} actualizado correctamente.'
    })

@app.route('/api/admin/estudiantes/<int:estudiante_id>', methods=['DELETE'])
@admin_required
def admin_delete_estudiante(estudiante_id):
    """Elimina definitivamente a un estudiante del sistema."""
    estudiante = db.get_or_404(Estudiante, estudiante_id)
    nombre = estudiante.nombre_completo
    db.session.delete(estudiante)
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'Estudiante {nombre} eliminado correctamente.'
    })

@app.route('/api/admin/estudiantes/plantilla', methods=['GET'])
@admin_required
def admin_descargar_plantilla():
    """Genera y descarga una plantilla Excel de ejemplo para carga masiva de alumnos."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Alumnos_Plantilla"

    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    headers = ["Nombre Completo *", "Curso *", "RUT / Identificador", "UID Tarjeta NFC (Opcional)"]
    ws.append(headers)

    for col_idx in range(1, 5):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ejemplos = [
        ["Martina Belén Morales Silva", "6B", "21.987.654-3", ""],
        ["Lucas Matías Gómez Soto", "6B", "22.345.678-9", ""],
        ["Fernanda Paz Rojas Muñoz", "7A", "20.890.123-4", "04:12:34:56:78:90:99"]
    ]
    for row in ejemplos:
        ws.append(row)

    col_widths = [32, 14, 24, 30]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Plantilla_Alumnos_AulaTap.xlsx"
    )

@app.route('/api/admin/estudiantes/importar', methods=['POST'])
@admin_required
def admin_importar_estudiantes():
    """
    Importa estudiantes en masa desde un archivo Excel (.xlsx) o CSV.
    Detecta automáticamente encabezados y crea o actualiza según RUT.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No se adjuntó ningún archivo.'}), 400

    file = request.files['file']
    filename = file.filename.lower()

    if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
        return jsonify({'error': 'Formato no soportado. Suba un archivo Excel (.xlsx) o CSV.'}), 400

    filas = []

    try:
        if filename.endswith('.xlsx'):
            wb = load_workbook(file, data_only=True)
            sheet = wb.active
            for row in sheet.iter_rows(values_only=True):
                if any(row):
                    filas.append([str(c).strip() if c is not None else '' for c in row])
        else:
            # Procesar CSV
            content = file.stream.read().decode('utf-8-sig', errors='replace')
            delimiter = ';' if ';' in content else (',' if ',' in content else '\t')
            reader = csv.reader(io.StringIO(content), delimiter=delimiter)
            for row in reader:
                if any(row):
                    filas.append([c.strip() for c in row])
    except Exception as e:
        return jsonify({'error': f'Error al leer archivo: {str(e)}'}), 400

    if len(filas) < 2:
        return jsonify({'error': 'El archivo no contiene suficientes filas de datos.'}), 400

    headers = [h.lower() for h in filas[0]]
    # Detectar índices de columnas
    idx_nombre = -1
    idx_curso = -1
    idx_rut = -1
    idx_nfc = -1

    for i, h in enumerate(headers):
        if any(term in h for term in ['nombre', 'estudiante', 'alumno']):
            idx_nombre = i
        elif 'curso' in h or 'nivel' in h:
            idx_curso = i
        elif any(term in h for term in ['rut', 'run', 'identificador', 'dni']):
            idx_rut = i
        elif any(term in h for term in ['nfc', 'uid', 'tarjeta']):
            idx_nfc = i

    # Si no encontró por nombre de encabezado, usar posiciones por defecto
    if idx_nombre == -1: idx_nombre = 0
    if idx_curso == -1: idx_curso = 1
    if idx_rut == -1 and len(headers) > 2: idx_rut = 2
    if idx_nfc == -1 and len(headers) > 3: idx_nfc = 3

    creados = 0
    actualizados = 0

    for fila_idx, row in enumerate(filas[1:], start=2):
        if len(row) <= max(idx_nombre, idx_curso):
            continue
        nombre = row[idx_nombre].strip()
        curso = row[idx_curso].strip().upper()

        if not nombre or not curso:
            continue

        rut = row[idx_rut].strip() if idx_rut != -1 and idx_rut < len(row) and row[idx_rut].strip() else None
        nfc = row[idx_nfc].strip().lower() if idx_nfc != -1 and idx_nfc < len(row) and row[idx_nfc].strip() else None

        # Buscar si ya existe por RUT
        estudiante = None
        if rut:
            estudiante = Estudiante.query.filter_by(rut=rut).first()
        if not estudiante:
            # Buscar por nombre exacto y curso
            estudiante = Estudiante.query.filter_by(nombre_completo=nombre, curso=curso).first()

        if estudiante:
            estudiante.nombre_completo = nombre
            estudiante.curso = curso
            if rut: estudiante.rut = rut
            if nfc: estudiante.nfc_uid = nfc
            actualizados += 1
        else:
            nuevo = Estudiante(
                nombre_completo=nombre,
                curso=curso,
                rut=rut,
                nfc_uid=nfc,
                puntaje_acumulado=0
            )
            db.session.add(nuevo)
            creados += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'creados': creados,
        'actualizados': actualizados,
        'mensaje': f'Importación completada: {creados} nuevo(s) alumno(s), {actualizados} actualizado(s).'
    })

# --- PILAR 2: CIERRE DE PERÍODO / REINICIO DE DÉCIMAS ---

@app.route('/api/admin/periodo/cerrar', methods=['POST'])
@admin_required
def admin_cerrar_periodo():
    """
    Cierra el período escolar/semestre:
    1. Registra una auditoría de cierre.
    2. Reinicia los puntajes acumulados a 0.
    """
    data = request.get_json() or {}
    curso = data.get('curso', 'todos').strip()
    motivo = data.get('motivo', 'Cierre de período regular').strip()

    stmt = Estudiante.query
    if curso and curso != 'todos':
        stmt = stmt.filter(Estudiante.curso == curso.upper())

    estudiantes = stmt.all()

    alumnos_afectados = len(estudiantes)
    puntos_totales_reiniciados = 0

    for e in estudiantes:
        if e.puntaje_acumulado > 0:
            puntos_totales_reiniciados += e.puntaje_acumulado
            # Crear transacción de auditoría de cierre
            t = Transaccion(
                estudiante_id=e.id,
                puntos=-e.puntaje_acumulado,
                motivo=f"{motivo} (Saldo canjeado: {e.puntaje_acumulado} pts)"
            )
            db.session.add(t)
            e.puntaje_acumulado = 0

    db.session.commit()

    return jsonify({
        'success': True,
        'alumnos_afectados': alumnos_afectados,
        'puntos_reiniciados': puntos_totales_reiniciados,
        'mensaje': f'Período cerrado exitosamente para {alumnos_afectados} estudiante(s). Total décimas reiniciadas: {puntos_totales_reiniciados}.'
    })

# --- PILAR 3: GESTIÓN DE DOCENTES Y USUARIOS ---

@app.route('/api/admin/usuarios', methods=['GET'])
@admin_required
def admin_get_usuarios():
    """Lista todos los usuarios docentes y administradores."""
    usuarios = Usuario.query.order_by(Usuario.rol.asc(), Usuario.nombre.asc()).all()
    resultado = []
    for u in usuarios:
        d = u.to_dict()
        d['creado_en'] = u.creado_en.strftime('%Y-%m-%d %H:%M') if u.creado_en else None
        resultado.append(d)
    return jsonify(resultado)

@app.route('/api/admin/usuarios', methods=['POST'])
@admin_required
def admin_create_usuario():
    """Crea una nueva cuenta de usuario (docente o admin)."""
    data = request.get_json() or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '').strip()
    nombre = data.get('nombre', '').strip()
    email = data.get('email', '').strip().lower() or None
    rol = data.get('rol', 'docente').strip().lower()

    if not username or not password or not nombre:
        return jsonify({'error': 'Usuario, contraseña y nombre completo son obligatorios.'}), 400

    if Usuario.query.filter_by(username=username).first():
        return jsonify({'error': f'El nombre de usuario "{username}" ya está en uso.'}), 409

    if email and Usuario.query.filter_by(email=email).first():
        return jsonify({'error': f'El correo "{email}" ya está registrado.'}), 409

    if rol not in ['admin', 'docente']:
        rol = 'docente'

    nuevo = Usuario(
        username=username,
        nombre=nombre,
        email=email,
        rol=rol
    )
    nuevo.set_password(password)
    db.session.add(nuevo)
    db.session.commit()

    return jsonify({
        'success': True,
        'usuario': nuevo.to_dict(),
        'mensaje': f'Usuario {nuevo.nombre} ({nuevo.rol}) creado con éxito.'
    }), 201

@app.route('/api/admin/usuarios/<int:user_id>', methods=['PUT'])
@admin_required
def admin_update_usuario(user_id):
    """Actualiza datos y contraseña de un usuario."""
    usuario = db.get_or_404(Usuario, user_id)
    data = request.get_json() or {}

    nombre = data.get('nombre', '').strip()
    email = data.get('email', '').strip().lower() or None
    rol = data.get('rol', '').strip().lower()
    nueva_clave = data.get('password', '').strip()

    if nombre:
        usuario.nombre = nombre
    if email is not None:
        otro = Usuario.query.filter(Usuario.email == email, Usuario.id != usuario.id).first()
        if otro:
            return jsonify({'error': f'El correo {email} ya pertenece a otro usuario.'}), 409
        usuario.email = email
    if rol in ['admin', 'docente']:
        # Evitar quitarse a sí mismo el rol admin
        if usuario.id == session.get('user_id') and rol != 'admin':
            return jsonify({'error': 'No puedes quitarte el rol de administrador a ti mismo.'}), 400
        usuario.rol = rol

    if nueva_clave:
        usuario.set_password(nueva_clave)

    db.session.commit()
    return jsonify({
        'success': True,
        'usuario': usuario.to_dict(),
        'mensaje': f'Usuario {usuario.nombre} actualizado con éxito.'
    })

@app.route('/api/admin/usuarios/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_usuario(user_id):
    """Elimina un usuario (impide eliminar la cuenta propia activa)."""
    if user_id == session.get('user_id'):
        return jsonify({'error': 'No puedes eliminar tu propia cuenta en sesión.'}), 400

    usuario = db.get_or_404(Usuario, user_id)
    nombre = usuario.nombre
    db.session.delete(usuario)
    db.session.commit()

    return jsonify({
        'success': True,
        'mensaje': f'Cuenta de {nombre} eliminada correctamente.'
    })

# --- PILAR 4: CANALES & MANTENIMIENTO ---

@app.route('/api/admin/canales', methods=['POST'])
@admin_required
def admin_create_canal():
    """Crea un nuevo canal personalizado en la biblioteca."""
    data = request.get_json() or {}
    slug = data.get('slug', '').strip().lower()
    titulo = data.get('titulo', '').strip()
    descripcion = data.get('descripcion', '').strip() or None
    icono = data.get('icono', 'folder').strip()
    orden = data.get('orden', 0)

    if not slug or not titulo:
        return jsonify({'error': 'Identificador (slug) y título del canal son obligatorios.'}), 400

    slug_clean = secure_filename(slug).replace('_', '-').lower()
    if Canal.query.filter_by(slug=slug_clean).first():
        return jsonify({'error': f'El canal con identificador "{slug_clean}" ya existe.'}), 409

    canal = Canal(
        slug=slug_clean,
        titulo=titulo,
        descripcion=descripcion,
        icono=icono,
        orden=int(orden)
    )
    db.session.add(canal)
    db.session.commit()

    return jsonify({
        'success': True,
        'canal': canal.to_dict(),
        'mensaje': f'Canal "{canal.titulo}" creado exitosamente.'
    }), 201

@app.route('/api/admin/canales/<int:canal_id>', methods=['PUT'])
@admin_required
def admin_update_canal(canal_id):
    """Actualiza datos de un canal."""
    canal = db.get_or_404(Canal, canal_id)
    data = request.get_json() or {}

    titulo = data.get('titulo', '').strip()
    descripcion = data.get('descripcion', '').strip()
    icono = data.get('icono', '').strip()
    orden = data.get('orden')

    if titulo: canal.titulo = titulo
    if descripcion is not None: canal.descripcion = descripcion or None
    if icono: canal.icono = icono
    if orden is not None:
        try:
            canal.orden = int(orden)
        except ValueError:
            pass

    db.session.commit()
    return jsonify({
        'success': True,
        'canal': canal.to_dict(),
        'mensaje': f'Canal "{canal.titulo}" actualizado.'
    })

@app.route('/api/admin/canales/<int:canal_id>', methods=['DELETE'])
@admin_required
def admin_delete_canal(canal_id):
    """Elimina un canal de la biblioteca."""
    canal = db.get_or_404(Canal, canal_id)
    if canal.slug in ['guias', 'clases']:
        return jsonify({'error': 'Los canales principales "guias" y "clases" no pueden eliminarse.'}), 400

    titulo = canal.titulo
    db.session.delete(canal)
    db.session.commit()

    return jsonify({
        'success': True,
        'mensaje': f'Canal "{titulo}" eliminado correctamente.'
    })

@app.route('/api/admin/mantenimiento/backup-db', methods=['GET'])
@admin_required
def admin_descargar_backup_db():
    """Genera y descarga una copia exacta de la base de datos decipuntos.db."""
    if not os.path.exists(DB_PATH):
        return jsonify({'error': 'Archivo de base de datos no encontrado.'}), 404

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Backup_AulaTap_BD_{timestamp}.db"
    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name=filename,
        mimetype='application/x-sqlite3'
    )

@app.route('/api/admin/mantenimiento/metricas', methods=['GET'])
@admin_required
def admin_get_metricas():
    """Calcula estadísticas y métricas generales del sistema."""
    total_estudiantes = Estudiante.query.count()
    cursos = [c[0] for c in db.session.query(Estudiante.curso).distinct().all()]
    total_transacciones = Transaccion.query.count()
    total_materiales = MaterialBiblioteca.query.count()
    total_usuarios = Usuario.query.count()
    total_canales = Canal.query.count()

    puntos_totales = db.session.query(db.func.sum(Estudiante.puntaje_acumulado)).scalar() or 0

    # Calcular espacio ocupado en disco por uploads
    espacio_bytes = 0
    total_archivos = 0
    if os.path.exists(UPLOAD_FOLDER):
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for f in files:
                fp = os.path.join(root, f)
                espacio_bytes += os.path.getsize(fp)
                total_archivos += 1

    espacio_mb = round(espacio_bytes / (1024 * 1024), 2)

    return jsonify({
        'total_estudiantes': total_estudiantes,
        'total_cursos': len(cursos),
        'cursos': cursos,
        'total_transacciones': total_transacciones,
        'puntos_actuales_totales': puntos_totales,
        'total_materiales': total_materiales,
        'total_canales': total_canales,
        'total_usuarios': total_usuarios,
        'archivos_subidos': total_archivos,
        'espacio_disco_mb': espacio_mb
    })

if __name__ == '__main__':
    import socket
    port = int(os.environ.get('PORT', 5000))
    # En macOS el puerto 5000 suele estar ocupado por AirPlay Receiver
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('127.0.0.1', port)) == 0 and 'PORT' not in os.environ:
            print("[INFO] Puerto 5000 en uso (AirPlay Receiver en macOS). Usando puerto 5001...")
            port = 5001

    print(f"🚀 Iniciando AulaTap en http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)

