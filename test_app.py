"""
test_app.py - Pruebas automatizadas para AulaTap API y Autenticación
"""
import unittest
from app import app
from database import db, Estudiante, Transaccion, Usuario, Canal, Evaluacion, EntregaTarea, DescargaMaterial

class AulaTapTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        with app.app_context():
            test_ruts = ['99.888.777-6', '19.111.222-3', '19.444.555-6', '18.999.888-7', '17.555.444-3']
            st_ids = [e.id for e in Estudiante.query.filter(Estudiante.rut.in_(test_ruts)).all()]
            if st_ids:
                EntregaTarea.query.filter(EntregaTarea.estudiante_id.in_(st_ids)).delete(synchronize_session=False)
                Transaccion.query.filter(Transaccion.estudiante_id.in_(st_ids)).delete(synchronize_session=False)
                DescargaMaterial.query.filter(DescargaMaterial.estudiante_id.in_(st_ids)).delete(synchronize_session=False)
                Estudiante.query.filter(Estudiante.id.in_(st_ids)).delete(synchronize_session=False)
            EntregaTarea.query.filter(EntregaTarea.titulo_tarea.like('%Test%')).delete(synchronize_session=False)
            Usuario.query.filter_by(username='profe_ciencias').delete(synchronize_session=False)
            Canal.query.filter_by(slug='ciencias-feria').delete(synchronize_session=False)
            db.session.commit()


    def test_unauthenticated_redirect(self):
        """Verifica que usuarios no autenticados sean redirigidos a /login."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_unauthenticated_api_blocked(self):
        """Verifica que llamadas a la API sin sesión retornen 401."""
        response = self.client.get('/api/estudiantes')
        self.assertEqual(response.status_code, 401)

    def test_login_invalid_credentials(self):
        """Verifica que credenciales erróneas fallen con 401."""
        response = self.client.post('/api/login', json={
            'username': 'docente',
            'password': 'password_incorrecto'
        })
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertIn('error', data)

    def test_login_and_authenticated_flow(self):
        """Verifica flujo completo: login exitoso, acceso a app y consultas API."""
        with self.client:
            # 1. Login exitoso
            login_res = self.client.post('/api/login', json={
                'username': 'docente',
                'password': 'admin123'
            })
            self.assertEqual(login_res.status_code, 200)
            login_data = login_res.get_json()
            self.assertTrue(login_data['success'])

            # 2. Acceso a página principal
            index_res = self.client.get('/')
            self.assertEqual(index_res.status_code, 200)
            self.assertIn(b'AulaTap', index_res.data)

            # 3. Lista de estudiantes
            students_res = self.client.get('/api/estudiantes')
            self.assertEqual(students_res.status_code, 200)
            students = students_res.get_json()
            self.assertIsInstance(students, list)
            self.assertGreater(len(students), 0)

            # 4. Búsqueda por NFC
            first_uid = "04:a1:b2:c3:d4:e5:01"
            nfc_res = self.client.get(f'/api/estudiantes/nfc/{first_uid}')
            self.assertEqual(nfc_res.status_code, 200)
            nfc_data = nfc_res.get_json()
            self.assertEqual(nfc_data['nombre_completo'], "Matías Ignacio Silva Valenzuela")

            # 5. Asignación de puntos
            first_id = students[0]['id']
            initial_pts = students[0]['puntaje_acumulado']
            assign_res = self.client.post(f'/api/estudiantes/{first_id}/puntos', json={
                'puntos': 3,
                'motivo': 'Participación en clases'
            })
            self.assertEqual(assign_res.status_code, 200)
            assign_data = assign_res.get_json()
            self.assertTrue(assign_data['success'])
            self.assertEqual(assign_data['estudiante']['puntaje_acumulado'], initial_pts + 3)

            # 6. Exportar Excel y CSV
            excel_res = self.client.get('/api/exportar/excel')
            self.assertEqual(excel_res.status_code, 200)
            self.assertEqual(excel_res.content_type, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            csv_res = self.client.get('/api/exportar/csv')
            self.assertEqual(csv_res.status_code, 200)
            self.assertIn("text/csv", csv_res.content_type)

            # 7. Logout
            logout_res = self.client.get('/logout')
            self.assertEqual(logout_res.status_code, 302)

            # Verificar que ya no tiene acceso tras logout
            after_res = self.client.get('/api/estudiantes')
            self.assertEqual(after_res.status_code, 401)

    def test_biblioteca_canales(self):
        """Verifica que se listen los canales de biblioteca."""
        res = self.client.get('/api/biblioteca/canales')
        self.assertEqual(res.status_code, 200)
        canales = res.get_json()
        self.assertGreaterEqual(len(canales), 2)
        slugs = [c['slug'] for c in canales]
        self.assertIn('guias', slugs)
        self.assertIn('clases', slugs)

    def test_biblioteca_materiales_segmentacion_por_curso(self):
        """Verifica que los materiales estén correctamente segmentados por curso."""
        # Consulta para 6B
        res_6b = self.client.get('/api/biblioteca/materiales?curso=6B')
        self.assertEqual(res_6b.status_code, 200)
        mats_6b = res_6b.get_json()
        # No debe contener materiales exclusivos de 7A
        for m in mats_6b:
            self.assertIn(m['curso'], ['6B', 'TODOS'])

        # Consulta para 7A
        res_7a = self.client.get('/api/biblioteca/materiales?curso=7A')
        self.assertEqual(res_7a.status_code, 200)
        mats_7a = res_7a.get_json()
        for m in mats_7a:
            self.assertIn(m['curso'], ['7A', 'TODOS'])

    def test_creacion_y_eliminacion_material_docente(self):
        """Verifica que el docente pueda crear y eliminar material en un canal."""
        # 1. Login
        self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})

        # 2. Crear material
        create_res = self.client.post('/api/biblioteca/materiales', json={
            'canal_slug': 'clases',
            'curso': '6B',
            'titulo': 'Clase Test Unitario',
            'descripcion': 'Probando creación de bitácora diaria',
            'tipo': 'texto',
            'fecha_clase': '2026-09-28'
        })
        self.assertEqual(create_res.status_code, 201)
        created_data = create_res.get_json()
        self.assertTrue(created_data['success'])
        mat_id = created_data['material']['id']
        self.assertEqual(created_data['material']['titulo'], 'Clase Test Unitario')

        # 3. Eliminar material
        del_res = self.client.delete(f'/api/biblioteca/materiales/{mat_id}')
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.get_json()
        self.assertTrue(del_data['success'])

    def test_portal_estudiante_identificacion(self):
        """Verifica acceso público al portal de estudiantes por RUT, NFC y curso."""
        # 1. Cargar vista HTML del portal
        portal_res = self.client.get('/portal')
        self.assertEqual(portal_res.status_code, 200)
        self.assertIn(b'Portal Estudiante', portal_res.data)

        # 2. Identificar por RUT
        rut_res = self.client.get('/api/portal/identificar?rut=21.345.678-9')
        self.assertEqual(rut_res.status_code, 200)
        rut_data = rut_res.get_json()
        self.assertTrue(rut_data['encontrado'])
        self.assertEqual(rut_data['estudiante']['nombre_completo'], 'Matías Ignacio Silva Valenzuela')
        self.assertEqual(rut_data['curso_activo'], '6B')

        # 3. Identificar por UID NFC
        nfc_res = self.client.get('/api/portal/identificar?nfc_uid=04:a1:b2:c3:d4:e5:01')
        self.assertEqual(nfc_res.status_code, 200)
        nfc_data = nfc_res.get_json()
        self.assertTrue(nfc_data['encontrado'])
        self.assertEqual(nfc_data['estudiante']['nombre_completo'], 'Matías Ignacio Silva Valenzuela')

        # 4. Acceder solo por Curso
        curso_res = self.client.get('/api/portal/identificar?curso=7A')
        self.assertEqual(curso_res.status_code, 200)
        curso_data = curso_res.get_json()
        self.assertEqual(curso_data['curso_activo'], '7A')
        for m in curso_data['materiales']:
            self.assertIn(m['curso'], ['7A', 'TODOS'])

    def test_admin_dashboard_y_permisos(self):
        """Verifica que /admin requiera autenticación y rol admin."""
        # 1. Sin autenticar
        unauth_res = self.client.get('/admin')
        self.assertEqual(unauth_res.status_code, 302)

        # 2. Con usuario docente/admin
        with self.client:
            self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})
            admin_res = self.client.get('/admin')
            self.assertEqual(admin_res.status_code, 200)
            self.assertIn(b'Panel de Administraci', admin_res.data)

    def test_pilar1_edicion_y_carga_masiva(self):
        """Pilar 1: Edición, eliminación e importación masiva de estudiantes."""
        with self.client:
            self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})

            # 1. Crear alumno para editar
            crear_res = self.client.post('/api/estudiantes', json={
                'nombre_completo': 'Alumno Temporal Admin',
                'curso': '6B',
                'rut': '99.888.777-6'
            })
            self.assertEqual(crear_res.status_code, 201)
            temp_id = crear_res.get_json()['id']

            # 2. Editar alumno
            put_res = self.client.put(f'/api/admin/estudiantes/{temp_id}', json={
                'nombre_completo': 'Alumno Editado Admin',
                'curso': '7A',
                'rut': '99.888.777-6',
                'nfc_uid': '04:99:99:99:99:99:99',
                'puntaje_acumulado': 5
            })
            self.assertEqual(put_res.status_code, 200)
            self.assertEqual(put_res.get_json()['estudiante']['curso'], '7A')
            self.assertEqual(put_res.get_json()['estudiante']['puntaje_acumulado'], 5)

            # 3. Descargar plantilla Excel
            plantilla_res = self.client.get('/api/admin/estudiantes/plantilla')
            self.assertEqual(plantilla_res.status_code, 200)
            self.assertIn("spreadsheetml.sheet", plantilla_res.content_type)

            # 4. Importación masiva CSV
            import io
            csv_content = "Nombre Completo;Curso;RUT;NFC\nPedro Pablo Gomez;6B;19.111.222-3;\nAna Maria Silva;7A;19.444.555-6;\n"
            data = {
                'file': (io.BytesIO(csv_content.encode('utf-8-sig')), 'alumnos.csv')
            }
            import_res = self.client.post('/api/admin/estudiantes/importar', data=data, content_type='multipart/form-data')
            self.assertEqual(import_res.status_code, 200)
            import_data = import_res.get_json()
            self.assertTrue(import_data['success'])
            self.assertGreaterEqual(import_data['creados'] + import_data['actualizados'], 2)


            # 5. Eliminar alumno de prueba
            del_res = self.client.delete(f'/api/admin/estudiantes/{temp_id}')
            self.assertEqual(del_res.status_code, 200)
            self.assertTrue(del_res.get_json()['success'])

    def test_pilar2_cierre_de_periodo(self):
        """Pilar 2: Cierre de semestre y reinicio de décimas con auditoría."""
        with self.client:
            self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})

            cierre_res = self.client.post('/api/admin/periodo/cerrar', json={
                'curso': '6B',
                'motivo': 'Cierre 1 Semestre Test'
            })
            self.assertEqual(cierre_res.status_code, 200)
            cierre_data = cierre_res.get_json()
            self.assertTrue(cierre_data['success'])

            # Verificar que estudiantes de 6B tienen 0 puntos ahora
            students_res = self.client.get('/api/estudiantes?curso=6B')
            for s in students_res.get_json():
                self.assertEqual(s['puntaje_acumulado'], 0)

    def test_pilar3_gestion_usuarios_y_docentes(self):
        """Pilar 3: Crear, listar, editar y eliminar usuarios docentes."""
        with self.client:
            self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})

            # 1. Crear nuevo docente
            new_u_res = self.client.post('/api/admin/usuarios', json={
                'username': 'profe_ciencias',
                'password': 'claveSegura123',
                'nombre': 'Profesor de Ciencias',
                'email': 'ciencias@colegio.cl',
                'rol': 'docente'
            })
            self.assertEqual(new_u_res.status_code, 201)
            u_id = new_u_res.get_json()['usuario']['id']

            # 2. Listar usuarios
            list_res = self.client.get('/api/admin/usuarios')
            self.assertEqual(list_res.status_code, 200)
            usernames = [u['username'] for u in list_res.get_json()]
            self.assertIn('profe_ciencias', usernames)

            # 3. Editar usuario
            edit_res = self.client.put(f'/api/admin/usuarios/{u_id}', json={
                'nombre': 'Profesor Ciencias Naturales',
                'rol': 'docente'
            })
            self.assertEqual(edit_res.status_code, 200)
            self.assertEqual(edit_res.get_json()['usuario']['nombre'], 'Profesor Ciencias Naturales')

            # 4. Eliminar usuario
            del_u_res = self.client.delete(f'/api/admin/usuarios/{u_id}')
            self.assertEqual(del_u_res.status_code, 200)

    def test_pilar4_canales_metricas_y_backup(self):
        """Pilar 4: Canales personalizados, métricas y backup de base de datos."""
        with self.client:
            self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})

            # 1. Crear nuevo canal
            new_c_res = self.client.post('/api/admin/canales', json={
                'slug': 'ciencias-feria',
                'titulo': 'Feria Científica 2026',
                'descripcion': 'Proyectos y bases del concurso',
                'icono': 'flask',
                'orden': 5
            })
            self.assertEqual(new_c_res.status_code, 201)
            canal_id = new_c_res.get_json()['canal']['id']

            # 2. Métricas del sistema
            metrics_res = self.client.get('/api/admin/mantenimiento/metricas')
            self.assertEqual(metrics_res.status_code, 200)
            m = metrics_res.get_json()
            self.assertIn('total_estudiantes', m)
            self.assertIn('espacio_disco_mb', m)

            # 3. Descargar backup de BD
            backup_res = self.client.get('/api/admin/mantenimiento/backup-db')
            self.assertEqual(backup_res.status_code, 200)
            self.assertEqual(backup_res.content_type, 'application/x-sqlite3')

            # 4. Eliminar canal personalizado
            del_c_res = self.client.delete(f'/api/admin/canales/{canal_id}')
            self.assertEqual(del_c_res.status_code, 200)

    def test_mockup_showcase_route(self):
        """Verifica que la vista de showcase/mockup cargue correctamente."""
        res = self.client.get('/mockup')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Showcase', res.data)
        self.assertIn(b'Mockup', res.data)

        demo_res = self.client.get('/demo')
        self.assertEqual(demo_res.status_code, 200)

    def test_evaluaciones_crud_and_portal(self):
        """Verifica CRUD de Evaluaciones en API docente y visualización en Portal Estudiante."""
        # 1. Intentar crear sin autenticación -> 401
        unauth_res = self.client.post('/api/evaluaciones', json={
            'titulo': 'Prueba Bloqueada',
            'curso': '6B',
            'fecha': '2026-10-15'
        })
        self.assertEqual(unauth_res.status_code, 401)

        # 2. Iniciar sesión como docente
        with self.client:
            self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})

            # 3. Crear evaluación válida
            create_res = self.client.post('/api/evaluaciones', json={
                'titulo': 'Prueba Test Unittest',
                'curso': '6B',
                'tipo': 'Prueba Sumativa',
                'fecha': '2026-10-20',
                'hora': '09:00',
                'descripcion': 'Contenidos de prueba para unittest',
                'max_decimas': 5
            })
            self.assertEqual(create_res.status_code, 201)
            create_data = create_res.get_json()
            self.assertTrue(create_data['success'])
            eval_id = create_data['evaluacion']['id']
            self.assertEqual(create_data['evaluacion']['titulo'], 'Prueba Test Unittest')

            # 4. Consultar evaluaciones por curso
            list_res = self.client.get('/api/evaluaciones?curso=6B')
            self.assertEqual(list_res.status_code, 200)
            items = list_res.get_json()
            self.assertTrue(any(it['id'] == eval_id for it in items))

            # 5. Actualizar evaluación (PUT)
            put_res = self.client.put(f'/api/evaluaciones/{eval_id}', json={
                'titulo': 'Prueba Test Unittest Modificada',
                'max_decimas': 7
            })
            self.assertEqual(put_res.status_code, 200)
            put_data = put_res.get_json()
            self.assertEqual(put_data['evaluacion']['titulo'], 'Prueba Test Unittest Modificada')
            self.assertEqual(put_data['evaluacion']['max_decimas'], 7)

            # 6. Consultar desde el portal del estudiante (GET /api/portal/evaluaciones?curso=6B)
            portal_res = self.client.get('/api/portal/evaluaciones?curso=6B')
            self.assertEqual(portal_res.status_code, 200)
            portal_items = portal_res.get_json()
            self.assertTrue(any(it['id'] == eval_id for it in portal_items))

            # 7. Consultar endpoint de identificar en el portal
            ident_res = self.client.get('/api/portal/identificar?curso=6B')
            self.assertEqual(ident_res.status_code, 200)
            ident_data = ident_res.get_json()
            self.assertIn('evaluaciones', ident_data)
            self.assertTrue(any(it['id'] == eval_id for it in ident_data['evaluaciones']))

            # 8. Eliminar evaluación (DELETE)
            del_res = self.client.delete(f'/api/evaluaciones/{eval_id}')
            self.assertEqual(del_res.status_code, 200)

            # Verificar que ya no existe
            get_deleted = self.client.get(f'/api/evaluaciones/{eval_id}')
            self.assertEqual(get_deleted.status_code, 404)

    def test_insignias_y_logros(self):
        """Verifica el cálculo de insignias en el portal y perfil de estudiantes."""
        with app.app_context():
            # Crear un estudiante para probar insignias
            estudiante = Estudiante(
                nombre_completo="Estudiante Test Insignias",
                rut="18.999.888-7",
                curso="6B",
                nfc_uid="04:ff:ee:dd:cc:bb:aa",
                puntaje_acumulado=22 # Desbloquea Gran Maestro y Primer Paso
            )
            db.session.add(estudiante)
            db.session.commit()

            # Agregar transacciones para desbloquear 'Racha de Fuego' y 'Compañero Solidario'
            from datetime import datetime, timezone, timedelta
            hoy = datetime.now(timezone.utc)
            t1 = Transaccion(estudiante_id=estudiante.id, puntos=5, motivo="Trabajo en equipo destacado", fecha_hora=hoy - timedelta(days=2))
            t2 = Transaccion(estudiante_id=estudiante.id, puntos=3, motivo="Participación", fecha_hora=hoy - timedelta(days=1))
            t3 = Transaccion(estudiante_id=estudiante.id, puntos=4, motivo="Resolución de problemas", fecha_hora=hoy)
            db.session.add_all([t1, t2, t3])
            db.session.commit()

            estudiante_id = estudiante.id

        # 1. Identificar en el portal y verificar insignias
        res = self.client.get('/api/portal/identificar?rut=18.999.888-7')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['encontrado'])
        self.assertIn('insignias', data['estudiante'])
        
        insignias = {ins['id']: ins for ins in data['estudiante']['insignias']}
        self.assertTrue(insignias['gran_maestro']['desbloqueado'])
        self.assertTrue(insignias['primer_paso']['desbloqueado'])
        self.assertTrue(insignias['racha_fuego']['desbloqueado'])
        self.assertTrue(insignias['companero_solidario']['desbloqueado'])

        # Limpiar
        with app.app_context():
            e = db.session.get(Estudiante, estudiante_id)
            if e:
                db.session.delete(e)
                db.session.commit()

    def test_buzon_entregas_flujo_completo(self):
        """Verifica el flujo completo de entrega de tareas por alumnos y revisión por docentes."""
        import io
        with app.app_context():
            estudiante = Estudiante(
                nombre_completo="Estudiante Buzón Test",
                rut="17.555.444-3",
                curso="6B",
                nfc_uid="04:11:22:33:44:55:66",
                puntaje_acumulado=2
            )
            db.session.add(estudiante)
            db.session.commit()
            estudiante_id = estudiante.id

        # 1. Alumno sube tarea con archivo simulado (multipart)
        file_content = b"%PDF-1.4 mock test pdf content for student homework"
        data = {
            'estudiante_id': str(estudiante_id),
            'titulo_tarea': 'Tarea Fracciones Resueltas',
            'comentario': 'Profe, adjunto ejercicios del 1 al 10',
            'file': (io.BytesIO(file_content), 'tarea_fracciones.pdf')
        }
        upload_res = self.client.post('/api/portal/entregas', data=data, content_type='multipart/form-data')
        self.assertEqual(upload_res.status_code, 201)
        upload_data = upload_res.get_json()
        self.assertTrue(upload_data['success'])
        entrega_id = upload_data['entrega']['id']
        self.assertEqual(upload_data['entrega']['estado'], 'pendiente')
        self.assertEqual(upload_data['entrega']['tipo_archivo'], 'pdf')

        # 2. Consultar entregas del alumno en el portal
        list_res = self.client.get(f'/api/portal/entregas?estudiante_id={estudiante_id}')
        self.assertEqual(list_res.status_code, 200)
        entregas_alumno = list_res.get_json()
        self.assertEqual(len(entregas_alumno), 1)
        self.assertEqual(entregas_alumno[0]['id'], entrega_id)

        # 3. Docente autenticado revisa buzón
        with self.client:
            self.client.post('/api/login', json={'username': 'docente', 'password': 'admin123'})
            
            # Verificar contador de pendientes
            count_res = self.client.get('/api/docente/entregas/contador-pendientes?curso=6B')
            self.assertEqual(count_res.status_code, 200)
            self.assertGreaterEqual(count_res.get_json()['pendientes'], 1)

            # Listar entregas pendientes
            doc_list = self.client.get('/api/docente/entregas?estado=pendiente')
            self.assertEqual(doc_list.status_code, 200)
            items = doc_list.get_json()
            self.assertTrue(any(it['id'] == entrega_id for it in items))

            # 4. Docente califica la entrega con +3 décimas y feedback
            calif_res = self.client.post(f'/api/docente/entregas/{entrega_id}/calificar', json={
                'puntos_bonus': 3,
                'retroalimentacion': '¡Excelente procedimiento y cálculos perfectos!',
                'estado': 'revisado'
            })
            self.assertEqual(calif_res.status_code, 200)
            calif_data = calif_res.get_json()
            self.assertTrue(calif_data['success'])
            self.assertEqual(calif_data['entrega']['estado'], 'revisado')
            self.assertEqual(calif_data['entrega']['puntos_otorgados'], 3)
            # El estudiante tenía 2 puntos acumulados, ahora debe tener 5
            self.assertEqual(calif_data['estudiante']['puntaje_acumulado'], 5)

            # 5. Descargar o visualizar archivo entregado
            download_res = self.client.get(f'/entregas/descargar/{entrega_id}')
            self.assertEqual(download_res.status_code, 200)
            self.assertEqual(download_res.data, file_content)
            download_res.close()

        # Limpieza
        with app.app_context():
            e = db.session.get(Estudiante, estudiante_id)
            if e:
                db.session.delete(e)
                db.session.commit()

if __name__ == '__main__':
    unittest.main()




