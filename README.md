# 🏅 AulaTap - PWA Docente NFC & Biblioteca Digital por Canales

**AulaTap** es una plataforma web móvil progresiva (PWA) para salas de clases que integra:
1. **Evaluación Formativa & Gamificación NFC**: Asignación rápida de décimas y méritos mediante lectura de tarjetas/llaveros NFC o búsqueda manual en tiempo real.
2. **Biblioteca Digital por Canales**: Espacio organizado en canales temáticos (*Guías y Material*, *Clases del Día a Día* y *Avisos*) con segmentación estricta por curso.
3. **Calendario Híbrido de Evaluaciones & Pruebas**: Agenda y mini-calendario interactivo para programar pruebas, controles y trabajos prácticos, con cuenta regresiva, temarios y metas de décimas canjeables.
4. **Portal del Estudiante (Student Hub)**: Portal público donde el alumno ingresa acercando su llavero NFC o con su RUT para revisar sus décimas, fechas de próximas evaluaciones y descargar exclusivamente el material pedagógico correspondiente a su curso.
5. **Sistema de Insignias y Logros Desbloqueables (Badges)**: Medallas gamificadas con efectos sonoros Web Audio (*⚡ Racha de Fuego, 🤝 Compañero Solidario, 📚 Lector Imparable, 👑 Gran Maestro, 📤 Misión Cumplida, ⭐ Primer Paso*).
6. **Buzón Digital de Entrega de Tareas / Trabajos**: Los estudiantes suben fotografías de sus cuadernos (con soporte directo para cámara móvil) o archivos PDF; el docente revisa las evidencias en pantalla completa con Lightbox, califica en 1 clic y añade retroalimentación pedagógica.

---

## 🚀 1. Stack Tecnológico

- **Backend**: Python 3.10+ con Flask.
- **Base de Datos**: SQLite local (`decipuntos.db`) administrado con Flask-SQLAlchemy (Estudiantes, Transacciones, Canales, Materiales, Evaluaciones, Entregas y Descargas).
- **Almacenamiento Seguro**: Carpeta `/uploads/biblioteca` y `/uploads/entregas` con validación de extensiones y visualización controlada.
- **Frontend**: HTML5 Semántico, Vanilla CSS Gamificado (Glassmorphism, Cyber-Indigo & Gold) y Vanilla JavaScript ES6+.
- **Hardware & API**: **Web NFC API (`NDEFReader`)** para lectura instantánea de credenciales NFC tanto en el panel docente como en el portal del estudiante.
- **Gamificación & UX**: Web Audio API para efectos sonoros sintetizados, Canvas Particles para explosión de monedas y animaciones CSS fluidas.
- **Exportación**: Reportes en **Excel (.xlsx)** con formato enriquecido (OpenPyXL) y **CSV UTF-8 con BOM** para libro de clases.

---

## 📂 2. Estructura del Proyecto

```text
Docente-NFC/
├── app.py                     # Servidor Flask, endpoints API REST, buzón y portal
├── database.py                # Modelos SQLAlchemy (Estudiante, Transaccion, Canal, Material, Evaluacion, EntregaTarea, DescargaMaterial)
├── seed.py                    # Script de inicialización con alumnos, canales y materiales
├── test_app.py                # Suite de pruebas unitarias automatizadas (17 tests exhaustivos)
├── uploads/
│   ├── biblioteca/            # Almacenamiento de archivos y guías compartidas
│   └── entregas/              # Tareas, PDFs y fotos de cuadernos subidas por alumnos
├── templates/
│   ├── index.html             # Vista principal PWA Docente (Evaluación, Buzón, Biblioteca y Calendario)
│   ├── login.html             # Pantalla de acceso docente y enlace al portal estudiantil
│   ├── portal_estudiante.html # Portal del estudiante con insignias, entregas, calendario y guías
│   └── admin.html             # Panel de administración central (4 pilares)
└── static/
    ├── css/
    │   └── styles.css         # Sistema de diseño gamificado con Glassmorphism y Dark Mode
    ├── js/
    │   ├── nfc_app.js         # Lógica Web NFC, buzón docente, calificaciones y modales
    │   └── admin.js           # Lógica del dashboard de administración central (CRUD, Carga, Backups)
    ├── icons/
    │   ├── icon-192.svg       # Icono vectorial PWA 192x192
    │   └── icon-512.svg       # Icono vectorial PWA 512x512
    ├── manifest.json          # Manifiesto de aplicación web instalable (PWA)
    └── sw.js                  # Service Worker con soporte offline para portal y app
```



---

## 🛠️ 3. Instalación y Puesta en Marcha

### Requisitos:
- Python 3.10 o superior (probado en Python 3.14).
- Dependencias (Flask, Flask-SQLAlchemy, openpyxl, cryptography):
  ```bash
  pip install Flask Flask-SQLAlchemy openpyxl cryptography
  ```

### Paso 1: Poblar la Base de Datos Inicial
Ejecuta el script de siembra para crear las tablas en `decipuntos.db` y registrar los 7 estudiantes iniciales de prueba (cursos 6B y 7A con UIDs asignados):
```bash
python seed.py
```

### Paso 2: Ejecutar el Servidor
```bash
python app.py
```
Por defecto, la app estará disponible en:
- Desde tu PC: `http://localhost:5000`
- Desde otros dispositivos en la misma red local: `http://<TU_IP_LOCAL>:5000`

### 🔑 Credenciales de Acceso Docente (Iniciales):
- **Usuario**: `docente`
- **Contraseña**: `admin123`
*(La pantalla de inicio de sesión incluye un botón para autocompletar credenciales en 1 clic durante pruebas).*

---

## 📲 4. Cómo Habilitar Web NFC en Chrome Android (HTTPS Obligatorio)

La especificación de **Web NFC API (`window.NDEFReader`)** en Google Chrome para Android exige estrictamente un **Contexto Seguro** (`HTTPS` o `localhost`). Para probarlo con tu teléfono en sala de clases, tienes 3 alternativas muy sencillas:

### Opción A: Chrome Remote Debugging (Port Forwarding por USB) — *Recomendado sin instalar nada extra*
1. Conecta tu teléfono Android al PC mediante cable USB con la depuración USB activada.
2. En Google Chrome de tu computadora, entra a:
   ```text
   chrome://inspect/#devices
   ```
3. Haz clic en **Port forwarding...** y configura:
   - Port: `5000`
   - IP address and port: `localhost:5000`
4. En el Chrome de tu celular Android, abre simplemente:
   ```text
   http://localhost:5000
   ```
   *Como el navegador lo reconoce como `localhost`, habilita Web NFC al 100% sin certificados SSL.*

---

### Opción B: Cloudflare Tunnels (Túnel HTTPS gratuito y seguro)
Si quieres usar el teléfono por WiFi sin cable USB:
1. Descarga `cloudflared` o usa npx:
   ```bash
   npx localtunnel --port 5000
   # o con Cloudflare:
   cloudflared tunnel --url http://localhost:5000
   ```
2. Te dará una URL pública con HTTPS (ej: `https://decipuntos-docente.trycloudflare.com`).
3. Abre esa URL en Chrome de Android ¡y el chip NFC funcionará de inmediato!

---

### Opción C: HTTPS con Certificado Ad-hoc de Flask
Para correr Flask directamente con HTTPS:
Edita al final de `app.py`:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc', debug=True)
```
Al entrar desde tu celular (`https://<TU_IP>:5000`), Chrome mostrará una advertencia de seguridad por ser un certificado autofirmado; pulsa en *"Configuración avanzada -> Continuar a la dirección (no seguro)"*.

---

## 🎮 5. Características Principales

1. **Detección Automática por NFC**:
   - Acerca una tarjeta escolar o llavero NFC al sensor del teléfono.
   - El sistema captura el `serialNumber` del tag y consulta `/api/estudiantes/nfc/<uid>`.
   - Se muestra instantáneamente el estudiante, su rango gamificado y sus décimas.
2. **Simulador NFC Integrado**:
   - ¿Estás probando en una computadora o dispositivo sin NFC? Pulsa el botón **"Simulador"** en la barra inferior o el badge de estado.
   - Podrás simular lecturas de tarjetas reales de la base de datos con un solo clic.
3. **Búsqueda Manual en Vivo**:
   - Si un alumno no lleva su credencial, escribe su nombre, apellido o RUT en el buscador superior.
4. **Asignación Rápida de Décimas**:
   - Botones rápidos: **+1 pt**, **+2 pt**, **+3 pt**.
   - Selector de motivos de clase: *Participación, Tarea, Buena Conducta, Trabajo en clases, Trabajo en equipo, Resolución de problemas*.
   - Botón *"Confirmar Asignación"* con sonido de victoria (Web Audio API) y lluvia de confetti y monedas.
5. **Reportería y Descarga a Excel**:
   - Modal de estadísticas con total de décimas otorgadas y promedio por alumno.
   - Tabla filtrable por curso.
   - Botón **Excel (.xlsx)** con celdas formateadas, bordes y estilos listo para pasar al libro de clases.
   - Botón **CSV** con delimitador `;` y codificación UTF-8-BOM para compatibilidad directa con Excel en español.
6. **Vinculación NFC en 2 pasos**:
   - Asocia una tarjeta física no registrada a cualquier alumno de la lista en segundos desde el modal "Vincular".
7. **PWA Instalable**:
   - Incluye `manifest.json` y `sw.js` para instalarse como aplicación nativa en la pantalla de inicio de Android.

---

## 🧪 6. Pruebas Automatizadas

Para validar la integridad de la base de datos, lógica de insignias, buzón de entregas y todos los endpoints de la API REST:
```bash
python test_app.py
```
Resultado:
```text
Ran 17 tests in 0.560s
OK
```
