"""
seed.py - Script para inicializar la base de datos con datos de prueba.
Crea la base de datos decipuntos.db y añade 5 estudiantes de prueba con UIDs NFC simulados.
"""
from datetime import date, timedelta
from database import db, Estudiante, Transaccion, Usuario, Canal, MaterialBiblioteca, Evaluacion
from app import app

import sys

# Asegurar codificación UTF-8 en Windows terminal
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def seed_database():
    with app.app_context():
        # Crear tablas si no existen
        db.create_all()

        # Crear usuario docente por defecto si no existe
        if Usuario.query.filter_by(username='docente').first() is None:
            docente = Usuario(
                username='docente',
                nombre='Profesor Titular',
                email='docente@colegio.cl',
                rol='admin'
            )

            docente.set_password('admin123')
            db.session.add(docente)
            db.session.commit()
            print("[OK] Usuario 'docente' creado con contrasena 'admin123'.")
        else:
            print("[INFO] Usuario 'docente' ya existe.")

        # Verificar si ya existen estudiantes
        if Estudiante.query.count() == 0:
            print("[INFO] Poblando la base de datos con estudiantes de prueba...")

            estudiantes_data = [
                {
                    "nombre_completo": "Matías Ignacio Silva Valenzuela",
                    "rut": "21.345.678-9",
                    "curso": "6B",
                    "nfc_uid": "04:a1:b2:c3:d4:e5:01",
                    "puntaje_acumulado": 4
                },
                {
                    "nombre_completo": "Sofía Valentina Castro Morales",
                    "rut": "21.987.654-3",
                    "curso": "6B",
                    "nfc_uid": "04:f2:e3:d4:c5:b6:02",
                    "puntaje_acumulado": 7
                },
                {
                    "nombre_completo": "Benjamín Andrés Rojas Muñoz",
                    "rut": "22.111.222-K",
                    "curso": "6B",
                    "nfc_uid": "04:33:44:55:66:77:03",
                    "puntaje_acumulado": 2
                },
                {
                    "nombre_completo": "Valentina Isidora Pérez Soto",
                    "rut": "21.777.888-1",
                    "curso": "6B",
                    "nfc_uid": "04:88:99:aa:bb:cc:04",
                    "puntaje_acumulado": 5
                },
                {
                    "nombre_completo": "Lucas Gabriel Tapia Herrera",
                    "rut": "22.456.789-0",
                    "curso": "6B",
                    "nfc_uid": "04:dd:ee:ff:00:11:05",
                    "puntaje_acumulado": 1
                },
                {
                    "nombre_completo": "Camila Ignacia Fuentes Leiva",
                    "rut": "20.890.123-4",
                    "curso": "7A",
                    "nfc_uid": "04:12:34:56:78:90:06",
                    "puntaje_acumulado": 6
                },
                {
                    "nombre_completo": "Joaquín Alonso Vargas Cruz",
                    "rut": "21.234.567-8",
                    "curso": "7A",
                    "nfc_uid": None, # Sin tarjeta asignada aún para probar vinculación
                    "puntaje_acumulado": 3
                }
            ]

            for data in estudiantes_data:
                estudiante = Estudiante(
                    nombre_completo=data["nombre_completo"],
                    rut=data["rut"],
                    curso=data["curso"],
                    nfc_uid=data["nfc_uid"],
                    puntaje_acumulado=data["puntaje_acumulado"]
                )
                db.session.add(estudiante)
                db.session.flush()

                # Crear una transacción inicial de bienvenida/tarea si tiene puntos
                if data["puntaje_acumulado"] > 0:
                    transaccion = Transaccion(
                        estudiante_id=estudiante.id,
                        puntos=data["puntaje_acumulado"],
                        motivo="Puntos acumulados del período"
                    )
                    db.session.add(transaccion)

            db.session.commit()
            print(f"[OK] Se agregaron {len(estudiantes_data)} estudiantes exitosamente.")
        else:
            print("[INFO] La base de datos ya contiene estudiantes registrados.")

        # Poblar canales por defecto
        canales_defecto = [
            {
                "slug": "guias",
                "titulo": "Guías y Material de Estudio",
                "descripcion": "Fichas, guías prácticas, lecturas y documentos de apoyo.",
                "icono": "file-text",
                "orden": 1
            },
            {
                "slug": "clases",
                "titulo": "Clases del Día a Día",
                "descripcion": "Bitácora diaria, apuntes de clase, tareas del día y resúmenes.",
                "icono": "calendar",
                "orden": 2
            },
            {
                "slug": "avisos",
                "titulo": "Avisos y Novedades",
                "descripcion": "Comunicados importantes, fechas de pruebas y anuncios del curso.",
                "icono": "bell",
                "orden": 3
            }
        ]

        canales_map = {}
        for c_data in canales_defecto:
            canal = Canal.query.filter_by(slug=c_data["slug"]).first()
            if not canal:
                canal = Canal(
                    slug=c_data["slug"],
                    titulo=c_data["titulo"],
                    descripcion=c_data["descripcion"],
                    icono=c_data["icono"],
                    orden=c_data["orden"]
                )
                db.session.add(canal)
                db.session.flush()
                print(f"[OK] Canal creado: {canal.titulo}")
            canales_map[c_data["slug"]] = canal

        db.session.commit()

        # Poblar materiales de prueba si no existen
        if MaterialBiblioteca.query.count() == 0:
            materiales_data = [
                {
                    "canal_id": canales_map["guias"].id,
                    "curso": "6B",
                    "titulo": "Guía N° 4: Fracciones y Números Mixtos",
                    "descripcion": "Ejercicios resueltos y práctica para la prueba de fin de unidad. Resolver en el cuaderno.",
                    "tipo": "enlace",
                    "url_recurso": "https://curriculumnacional.mineduc.cl",
                    "fecha_clase": None
                },
                {
                    "canal_id": canales_map["guias"].id,
                    "curso": "6B",
                    "titulo": "Ficha Desafío: Problemas con Decimales (+2 Décimas)",
                    "descripcion": "Guía voluntaria de ejercitación avanzada. Entregar resuelta antes del viernes para sumar décimas.",
                    "tipo": "enlace",
                    "url_recurso": "https://www.geogebra.org",
                    "fecha_clase": None
                },
                {
                    "canal_id": canales_map["clases"].id,
                    "curso": "6B",
                    "titulo": "Clase 26/09: Suma de Fracciones con Distinto Denominador",
                    "descripcion": "Objetivo: Comprender y calcular sumas de fracciones mediante MCM. Tarea: ejercicios 1 al 5 página 42 del texto escolar.",
                    "tipo": "texto",
                    "url_recurso": None,
                    "fecha_clase": date(2026, 9, 26)
                },
                {
                    "canal_id": canales_map["clases"].id,
                    "curso": "6B",
                    "titulo": "Clase 28/09: Estrategias de Resolución de Problemas",
                    "descripcion": "Resolución de problemas en parejas. Felicitaciones a los estudiantes que obtuvieron décimas por trabajo colaborativo.",
                    "tipo": "texto",
                    "url_recurso": None,
                    "fecha_clase": date(2026, 9, 28)
                },
                {
                    "canal_id": canales_map["guias"].id,
                    "curso": "7A",
                    "titulo": "Guía N° 3: Introducción a Ecuaciones Lineales",
                    "descripcion": "Ficha explicativa paso a paso con balanzas y despeje de incógnitas.",
                    "tipo": "enlace",
                    "url_recurso": "https://curriculumnacional.mineduc.cl",
                    "fecha_clase": None
                },
                {
                    "canal_id": canales_map["clases"].id,
                    "curso": "7A",
                    "titulo": "Clase 27/09: Traducción a Lenguaje Algebraico",
                    "descripcion": "Objetivo: Modelar situaciones del lenguaje común a lenguaje algebraico. Próxima clase: resolución con coeficientes fraccionarios.",
                    "tipo": "texto",
                    "url_recurso": None,
                    "fecha_clase": date(2026, 9, 27)
                },
                {
                    "canal_id": canales_map["avisos"].id,
                    "curso": "TODOS",
                    "titulo": "Reglamento de Sala y Sistema de Décimas AulaTap",
                    "descripcion": "Criterios de entrega de décimas: participación activa (+1), trabajo en equipo (+2), tareas destacadas (+3). Se canjean al cierre de período.",
                    "tipo": "texto",
                    "url_recurso": None,
                    "fecha_clase": None
                }
            ]

            for m in materiales_data:
                mat = MaterialBiblioteca(
                    canal_id=m["canal_id"],
                    curso=m["curso"],
                    titulo=m["titulo"],
                    descripcion=m["descripcion"],
                    tipo=m["tipo"],
                    url_recurso=m["url_recurso"],
                    fecha_clase=m["fecha_clase"]
                )
                db.session.add(mat)

            db.session.commit()
            print(f"[OK] Se agregaron {len(materiales_data)} materiales de biblioteca de prueba.")

        # Verificar si existen evaluaciones
        if Evaluacion.query.count() == 0:
            print("[INFO] Poblando evaluaciones y pruebas de prueba...")
            hoy = date.today()
            evaluaciones_data = [
                {
                    "curso": "6B",
                    "titulo": "Prueba Sumativa N° 2: Fracciones y Decimales",
                    "tipo": "Prueba Sumativa",
                    "fecha": hoy + timedelta(days=4),
                    "hora": "08:30",
                    "descripcion": "Temario: Suma y resta de fracciones con distinto denominador, números mixtos, problemas contextualizados. Traer calculadora básica y lápiz grafito.",
                    "max_decimas": 5
                },
                {
                    "curso": "6B",
                    "titulo": "Control Acumulativo: Operaciones Combinadas",
                    "tipo": "Control Corto",
                    "fecha": hoy + timedelta(days=11),
                    "hora": "10:15",
                    "descripcion": "Prioridad de operaciones (PAPOMUDAS) y resolución rápida de 5 ejercicios.",
                    "max_decimas": 3
                },
                {
                    "curso": "7A",
                    "titulo": "Evaluación Parcial: Ecuaciones de Primer Grado",
                    "tipo": "Prueba Sumativa",
                    "fecha": hoy + timedelta(days=6),
                    "hora": "11:45",
                    "descripcion": "Contenidos: Lenguaje algebraico, reducción de términos semejantes y resolución de ecuaciones lineales con enteros.",
                    "max_decimas": 5
                },
                {
                    "curso": "TODOS",
                    "titulo": "Feria Científica y Matemática Escolar",
                    "tipo": "Trabajo Práctico",
                    "fecha": hoy + timedelta(days=16),
                    "hora": "09:00",
                    "descripcion": "Presentación de maquetas y experimentos grupales. Rúbrica en Biblioteca Digital.",
                    "max_decimas": 8
                }
            ]
            for ev in evaluaciones_data:
                nueva_ev = Evaluacion(
                    curso=ev["curso"],
                    titulo=ev["titulo"],
                    tipo=ev["tipo"],
                    fecha=ev["fecha"],
                    hora=ev["hora"],
                    descripcion=ev["descripcion"],
                    max_decimas=ev["max_decimas"]
                )
                db.session.add(nueva_ev)
            db.session.commit()
            print(f"[OK] Se agregaron {len(evaluaciones_data)} evaluaciones de prueba.")

if __name__ == "__main__":
    seed_database()
