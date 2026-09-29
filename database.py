"""
database.py - Módulo de base de datos para DeciPuntos
Gestión de SQLite y modelos con SQLAlchemy.
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    rol = db.Column(db.String(20), default='docente', nullable=False)
    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nombre': self.nombre,
            'email': self.email,
            'rol': self.rol
        }

class Estudiante(db.Model):
    __tablename__ = 'estudiantes'

    id = db.Column(db.Integer, primary_key=True)
    rut = db.Column(db.String(20), unique=True, nullable=True)
    nombre_completo = db.Column(db.String(120), nullable=False)
    curso = db.Column(db.String(30), nullable=False)
    nfc_uid = db.Column(db.String(64), unique=True, nullable=True)
    puntaje_acumulado = db.Column(db.Integer, default=0, nullable=False)

    transacciones = db.relationship('Transaccion', backref='estudiante', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'rut': self.rut,
            'nombre_completo': self.nombre_completo,
            'curso': self.curso,
            'nfc_uid': self.nfc_uid,
            'puntaje_acumulado': self.puntaje_acumulado,
            'total_transacciones': len(self.transacciones)
        }

class Transaccion(db.Model):
    __tablename__ = 'transacciones'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    puntos = db.Column(db.Integer, nullable=False)
    motivo = db.Column(db.String(100), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'estudiante_id': self.estudiante_id,
            'estudiante_nombre': self.estudiante.nombre_completo if self.estudiante else None,
            'estudiante_curso': self.estudiante.curso if self.estudiante else None,
            'puntos': self.puntos,
            'motivo': self.motivo,
            'fecha_hora': self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')
        }

class Canal(db.Model):
    __tablename__ = 'canales'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    icono = db.Column(db.String(50), default='folder', nullable=False)
    orden = db.Column(db.Integer, default=0, nullable=False)

    materiales = db.relationship('MaterialBiblioteca', backref='canal', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'titulo': self.titulo,
            'descripcion': self.descripcion,
            'icono': self.icono,
            'orden': self.orden,
            'total_materiales': len(self.materiales)
        }

class MaterialBiblioteca(db.Model):
    __tablename__ = 'materiales_biblioteca'

    id = db.Column(db.Integer, primary_key=True)
    canal_id = db.Column(db.Integer, db.ForeignKey('canales.id'), nullable=False)
    curso = db.Column(db.String(30), nullable=False) # '6B', '7A', 'TODOS'
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    tipo = db.Column(db.String(20), default='archivo', nullable=False) # 'archivo', 'enlace', 'texto'
    url_recurso = db.Column(db.String(300), nullable=True)
    nombre_archivo = db.Column(db.String(255), nullable=True)
    tamano_bytes = db.Column(db.Integer, nullable=True)
    fecha_clase = db.Column(db.Date, nullable=True)
    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'canal_id': self.canal_id,
            'canal_slug': self.canal.slug if self.canal else None,
            'canal_titulo': self.canal.titulo if self.canal else None,
            'curso': self.curso,
            'titulo': self.titulo,
            'descripcion': self.descripcion,
            'tipo': self.tipo,
            'url_recurso': self.url_recurso,
            'nombre_archivo': self.nombre_archivo,
            'tamano_bytes': self.tamano_bytes,
            'fecha_clase': self.fecha_clase.strftime('%Y-%m-%d') if self.fecha_clase else None,
            'creado_en': self.creado_en.strftime('%Y-%m-%d %H:%M:%S')
        }

class Evaluacion(db.Model):
    __tablename__ = 'evaluaciones'

    id = db.Column(db.Integer, primary_key=True)
    curso = db.Column(db.String(30), nullable=False) # '6B', '7A', 'TODOS'
    titulo = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(50), default='Prueba Sumativa', nullable=False) # 'Prueba Sumativa', 'Control Corto', 'Trabajo Práctico', 'Presentación / Disertación'
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(10), nullable=True) # '08:30'
    descripcion = db.Column(db.Text, nullable=True) # Temario o contenidos
    max_decimas = db.Column(db.Integer, default=5, nullable=False)
    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        # Calcular días restantes
        hoy = datetime.now().date()
        dias_restantes = (self.fecha - hoy).days if self.fecha else None

        return {
            'id': self.id,
            'curso': self.curso,
            'titulo': self.titulo,
            'tipo': self.tipo,
            'fecha': self.fecha.strftime('%Y-%m-%d') if self.fecha else None,
            'hora': self.hora,
            'descripcion': self.descripcion,
            'max_decimas': self.max_decimas,
            'dias_restantes': dias_restantes,
            'creado_en': self.creado_en.strftime('%Y-%m-%d %H:%M:%S')
        }

class EntregaTarea(db.Model):
    __tablename__ = 'entregas_tareas'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('materiales_biblioteca.id'), nullable=True)
    evaluacion_id = db.Column(db.Integer, db.ForeignKey('evaluaciones.id'), nullable=True)
    titulo_tarea = db.Column(db.String(150), nullable=False)
    comentario = db.Column(db.Text, nullable=True)
    archivo_nombre = db.Column(db.String(255), nullable=False)
    archivo_url = db.Column(db.String(300), nullable=False) # Nombre de archivo guardado en uploads/entregas
    tipo_archivo = db.Column(db.String(50), default='imagen', nullable=False) # 'imagen', 'pdf', 'documento'
    tamano_bytes = db.Column(db.Integer, nullable=True)
    estado = db.Column(db.String(30), default='pendiente', nullable=False) # 'pendiente', 'revisado'
    puntos_otorgados = db.Column(db.Integer, default=0, nullable=False)
    retroalimentacion = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    revisado_en = db.Column(db.DateTime, nullable=True)

    estudiante = db.relationship('Estudiante', backref=db.backref('entregas', lazy=True, cascade='all, delete-orphan'))
    material = db.relationship('MaterialBiblioteca', backref=db.backref('entregas', lazy=True, cascade='all, delete-orphan'))
    evaluacion = db.relationship('Evaluacion', backref=db.backref('entregas', lazy=True, cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'estudiante_id': self.estudiante_id,
            'estudiante_nombre': self.estudiante.nombre_completo if self.estudiante else None,
            'estudiante_curso': self.estudiante.curso if self.estudiante else None,
            'estudiante_rut': self.estudiante.rut if self.estudiante else None,
            'material_id': self.material_id,
            'material_titulo': self.material.titulo if self.material else None,
            'evaluacion_id': self.evaluacion_id,
            'evaluacion_titulo': self.evaluacion.titulo if self.evaluacion else None,
            'titulo_tarea': self.titulo_tarea,
            'comentario': self.comentario,
            'archivo_nombre': self.archivo_nombre,
            'archivo_url': self.archivo_url,
            'tipo_archivo': self.tipo_archivo,
            'tamano_bytes': self.tamano_bytes,
            'estado': self.estado,
            'puntos_otorgados': self.puntos_otorgados,
            'retroalimentacion': self.retroalimentacion,
            'creado_en': self.creado_en.strftime('%Y-%m-%d %H:%M:%S'),
            'revisado_en': self.revisado_en.strftime('%Y-%m-%d %H:%M:%S') if self.revisado_en else None
        }

class DescargaMaterial(db.Model):
    __tablename__ = 'descargas_materiales'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('materiales_biblioteca.id'), nullable=False)
    fecha_descarga = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    estudiante = db.relationship('Estudiante', backref=db.backref('descargas', lazy=True, cascade='all, delete-orphan'))
    material = db.relationship('MaterialBiblioteca', backref=db.backref('descargas', lazy=True, cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'estudiante_id': self.estudiante_id,
            'material_id': self.material_id,
            'fecha_descarga': self.fecha_descarga.strftime('%Y-%m-%d %H:%M:%S')
        }


