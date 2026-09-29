/**
 * admin.js - Lógica del Panel de Administración Central de AulaTap
 * Controla los 4 Pilares: Estudiantes, Cierre de Período, Usuarios y Mantenimiento.
 */

const AdminState = {
  activeTab: 'tab-estudiantes',
  students: [],
  courses: [],
  users: [],
  canales: []
};

// ========================================================
// TOASTS Y MODALES
// ========================================================
function showToast(msg, icon = '✨', isError = false) {
  const toast = document.getElementById('toast-notice');
  document.getElementById('toast-msg').textContent = msg;
  document.getElementById('toast-icon').textContent = icon;
  toast.classList.remove('error', 'success');
  toast.classList.add(isError ? 'error' : 'success');
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3200);
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('open');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text).replace(/[&<>"']/g, function(m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
  });
}

// ========================================================
// NAVEGACIÓN ENTRE PESTAÑAS (4 PILARES)
// ========================================================
function switchAdminTab(tabId) {
  AdminState.activeTab = tabId;
  document.querySelectorAll('.admin-tab-content').forEach(el => el.style.display = 'none');
  const target = document.getElementById(tabId);
  if (target) target.style.display = 'block';

  document.querySelectorAll('.admin-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('onclick').includes(tabId));
  });

  if (tabId === 'tab-estudiantes') loadStudents();
  if (tabId === 'tab-cierre') loadCierreCourses();
  if (tabId === 'tab-docentes') loadUsers();
  if (tabId === 'tab-canales-mantenimiento') {
    loadMetrics();
    loadCanales();
  }
}

// ========================================================
// PILAR 1: GESTIÓN DE ESTUDIANTES & CARGA MASIVA
// ========================================================
async function loadStudents() {
  const tbody = document.getElementById('admin-students-tbody');
  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-dim);">Cargando estudiantes...</td></tr>';

  try {
    const res = await fetch('/api/estudiantes');
    const students = await res.json();
    AdminState.students = students;

    // Actualizar cursos únicos
    const courses = [...new Set(students.map(s => s.curso))].sort();
    AdminState.courses = courses;
    updateCourseSelects(courses);

    renderStudentsTable(students);
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#f87171;padding:16px;">Error al cargar alumnos.</td></tr>';
  }
}

function updateCourseSelects(courses) {
  const filterSelect = document.getElementById('admin-filter-course');
  const currentVal = filterSelect.value;
  filterSelect.innerHTML = '<option value="todos">Todos los Cursos</option>';
  courses.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = `Curso ${c}`;
    filterSelect.appendChild(opt);
  });
  filterSelect.value = currentVal;
}

function filterStudentsTable() {
  const query = (document.getElementById('admin-search-student').value || '').trim().toLowerCase();
  const courseFilter = document.getElementById('admin-filter-course').value;

  let filtered = AdminState.students;
  if (courseFilter !== 'todos') {
    filtered = filtered.filter(s => s.curso === courseFilter);
  }

  if (query) {
    filtered = filtered.filter(s =>
      s.nombre_completo.toLowerCase().includes(query) ||
      (s.rut && s.rut.toLowerCase().includes(query)) ||
      (s.nfc_uid && s.nfc_uid.toLowerCase().includes(query))
    );
  }

  renderStudentsTable(filtered);
}

function renderStudentsTable(students) {
  const tbody = document.getElementById('admin-students-tbody');
  if (students.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-dim);">No se encontraron estudiantes.</td></tr>';
    return;
  }

  tbody.innerHTML = students.map((s, idx) => `
    <tr>
      <td style="color:var(--text-dim);font-weight:700;">${idx + 1}</td>
      <td style="font-weight:700;">${escapeHtml(s.nombre_completo)}</td>
      <td><span class="tag-pill course" style="font-size:0.75rem;">${s.curso}</span></td>
      <td style="font-size:0.8rem;color:var(--text-muted);">${escapeHtml(s.rut || 'S/R')}</td>
      <td>
        ${s.nfc_uid ? `<span class="tag-pill nfc-linked" style="font-size:0.72rem;font-family:monospace;">${s.nfc_uid}</span>` : '<span style="color:var(--text-dim);font-size:0.75rem;">Sin vincular</span>'}
      </td>
      <td style="text-align:center;">
        <span class="badge" style="font-weight:800;color:var(--accent-gold);font-size:0.95rem;">${s.puntaje_acumulado}</span>
      </td>
      <td style="text-align:center;">
        <div style="display:inline-flex;gap:4px;">
          <button class="btn-action-icon" title="Editar alumno" onclick="openEditStudentModal(${s.id})">✏️</button>
          <button class="btn-action-icon delete" title="Eliminar alumno" onclick="deleteStudent(${s.id}, '${escapeHtml(s.nombre_completo).replace(/'/g, "\\'")}')">🗑️</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function openNewStudentModal() {
  document.getElementById('edit-student-id').value = '';
  document.getElementById('edit-student-name').value = '';
  document.getElementById('edit-student-course').value = '';
  document.getElementById('edit-student-rut').value = '';
  document.getElementById('edit-student-nfc').value = '';
  document.getElementById('edit-student-points').value = '0';
  document.querySelector('#modal-edit-student .modal-title').innerHTML = '<span>➕</span> Nuevo Estudiante';
  openModal('modal-edit-student');
}

function openEditStudentModal(studentId) {
  const student = AdminState.students.find(s => s.id === studentId);
  if (!student) return;

  document.getElementById('edit-student-id').value = student.id;
  document.getElementById('edit-student-name').value = student.nombre_completo;
  document.getElementById('edit-student-course').value = student.curso;
  document.getElementById('edit-student-rut').value = student.rut || '';
  document.getElementById('edit-student-nfc').value = student.nfc_uid || '';
  document.getElementById('edit-student-points').value = student.puntaje_acumulado;
  document.querySelector('#modal-edit-student .modal-title').innerHTML = '<span>✏️</span> Editar Estudiante';
  openModal('modal-edit-student');
}

async function submitEditStudent() {
  const id = document.getElementById('edit-student-id').value;
  const nombre = document.getElementById('edit-student-name').value.trim();
  const curso = document.getElementById('edit-student-course').value.trim().toUpperCase();
  const rut = document.getElementById('edit-student-rut').value.trim();
  const nfc = document.getElementById('edit-student-nfc').value.trim().toLowerCase();
  const puntos = document.getElementById('edit-student-points').value;

  if (!nombre || !curso) {
    showToast('Nombre y curso son obligatorios.', '⚠️', true);
    return;
  }

  const payload = {
    nombre_completo: nombre,
    curso: curso,
    rut: rut || null,
    nfc_uid: nfc || null,
    puntaje_acumulado: puntos !== '' ? parseInt(puntos, 10) : 0
  };

  try {
    let url = '/api/estudiantes';
    let method = 'POST';

    if (id) {
      url = `/api/admin/estudiantes/${id}`;
      method = 'PUT';
    }

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok) {
      showToast(data.mensaje || 'Estudiante guardado con éxito.', '✅');
      closeModal('modal-edit-student');
      loadStudents();
    } else {
      showToast(data.error || 'Error al guardar estudiante.', '❌', true);
    }
  } catch (e) {
    showToast('Error de conexión con el servidor.', '⚠️', true);
  }
}

async function deleteStudent(studentId, name) {
  if (!confirm(`¿Estás seguro de eliminar permanentemente a "${name}" y todo su historial de puntos?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/admin/estudiantes/${studentId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, '🗑️');
      loadStudents();
    } else {
      showToast(data.error || 'No se pudo eliminar.', '❌', true);
    }
  } catch (err) {
    showToast('Error de conexión al eliminar alumno.', '⚠️', true);
  }
}

async function submitImportStudents(e) {
  e.preventDefault();
  const fileInput = document.getElementById('import-file-input');
  const btn = document.getElementById('btn-submit-import');
  const resultBox = document.getElementById('import-result-box');

  if (!fileInput.files.length) {
    showToast('Selecciona un archivo Excel o CSV.', '⚠️', true);
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Procesando archivo...';
  resultBox.style.display = 'none';

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const res = await fetch('/api/admin/estudiantes/importar', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (res.ok && data.success) {
      resultBox.style.display = 'block';
      resultBox.style.background = 'rgba(16, 185, 129, 0.15)';
      resultBox.style.border = '1px solid rgba(16, 185, 129, 0.4)';
      resultBox.style.color = '#6ee7b7';
      resultBox.innerHTML = `<strong>¡Importación exitosa!</strong><br>${data.mensaje}`;
      showToast('Nómina importada correctamente.', '🚀');
      fileInput.value = '';
      loadStudents();
    } else {
      resultBox.style.display = 'block';
      resultBox.style.background = 'rgba(239, 68, 68, 0.15)';
      resultBox.style.border = '1px solid rgba(239, 68, 68, 0.4)';
      resultBox.style.color = '#fca5a5';
      resultBox.innerHTML = `<strong>Error:</strong> ${data.error || 'No se pudo procesar el archivo.'}`;
    }
  } catch (err) {
    showToast('Error de red al importar estudiantes.', '❌', true);
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Procesar e Importar Alumnos';
  }
}

// ========================================================
// PILAR 2: CIERRE DE SEMESTRE / REINICIO DE DÉCIMAS
// ========================================================
async function loadCierreCourses() {
  const select = document.getElementById('cierre-course-select');
  try {
    const res = await fetch('/api/cursos');
    const courses = await res.json();
    select.innerHTML = '<option value="todos">🌟 TODOS los Cursos del Colegio</option>';
    courses.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = `Curso ${c}`;
      select.appendChild(opt);
    });
  } catch (e) {
    console.warn("Error cargando cursos en cierre:", e);
  }
}

function downloadPreCloseReport() {
  const curso = document.getElementById('cierre-course-select').value;
  window.location.href = `/api/exportar/excel?curso=${curso}`;
}

async function executeClosePeriod() {
  const curso = document.getElementById('cierre-course-select').value;
  const motivo = document.getElementById('cierre-motivo-input').value.trim() || 'Cierre de período regular';

  const cursoTexto = curso === 'todos' ? 'TODOS los cursos' : `el curso ${curso}`;
  const confirmMsg = `⚠️ ATENCIÓN: Estás a punto de cerrar el período para ${cursoTexto}.\n\n` +
    `• Las décimas actuales de los estudiantes volverán a 0.\n` +
    `• Se guardará el saldo en el historial de transacciones para auditoría.\n\n` +
    `¿Deseas continuar con el reinicio de puntajes?`;

  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch('/api/admin/periodo/cerrar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ curso, motivo })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, '🏁');
      alert(`✅ Cierre completado:\n${data.mensaje}`);
      loadStudents();
    } else {
      showToast(data.error || 'Error al ejecutar cierre.', '❌', true);
    }
  } catch (e) {
    showToast('Error de red al ejecutar cierre de ciclo.', '⚠️', true);
  }
}

// ========================================================
// PILAR 3: GESTIÓN DE DOCENTES Y EQUIPO
// ========================================================
async function loadUsers() {
  const tbody = document.getElementById('admin-users-tbody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:16px;color:var(--text-dim);">Cargando usuarios...</td></tr>';

  try {
    const res = await fetch('/api/admin/usuarios');
    const users = await res.json();
    AdminState.users = users;

    if (users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:16px;">No hay usuarios registrados.</td></tr>';
      return;
    }

    tbody.innerHTML = users.map(u => `
      <tr>
        <td><strong>${escapeHtml(u.username)}</strong></td>
        <td>${escapeHtml(u.nombre)}</td>
        <td style="color:var(--text-muted);font-size:0.8rem;">${escapeHtml(u.email || 'Sin correo')}</td>
        <td>
          <span class="tag-pill ${u.rol === 'admin' ? 'nfc-linked' : 'course'}" style="font-size:0.75rem;text-transform:uppercase;">
            ${u.rol === 'admin' ? '👑 Admin' : '👨‍🏫 Docente'}
          </span>
        </td>
        <td style="font-size:0.75rem;color:var(--text-dim);">${u.creado_en || 'Reciente'}</td>
        <td style="text-align:center;">
          <div style="display:inline-flex;gap:4px;">
            <button class="btn-action-icon" title="Editar usuario" onclick='openEditUserModal(${JSON.stringify(u)})'>✏️</button>
            <button class="btn-action-icon delete" title="Eliminar usuario" onclick="deleteUser(${u.id}, '${escapeHtml(u.nombre)}')">🗑️</button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#f87171;padding:16px;">Error al cargar usuarios.</td></tr>';
  }
}

function openNewUserModal() {
  document.getElementById('form-user-id').value = '';
  document.getElementById('form-user-name').value = '';
  document.getElementById('form-user-username').value = '';
  document.getElementById('form-user-username').disabled = false;
  document.getElementById('form-user-email').value = '';
  document.getElementById('form-user-role').value = 'docente';
  document.getElementById('form-user-pwd').value = '';
  document.getElementById('form-user-pwd').required = true;
  document.getElementById('hint-user-pwd').style.display = 'none';
  document.getElementById('user-modal-title').innerHTML = '<span>➕</span> Nuevo Usuario';
  openModal('modal-user-form');
}

function openEditUserModal(u) {
  document.getElementById('form-user-id').value = u.id;
  document.getElementById('form-user-name').value = u.nombre;
  document.getElementById('form-user-username').value = u.username;
  document.getElementById('form-user-username').disabled = true;
  document.getElementById('form-user-email').value = u.email || '';
  document.getElementById('form-user-role').value = u.rol;
  document.getElementById('form-user-pwd').value = '';
  document.getElementById('form-user-pwd').required = false;
  document.getElementById('hint-user-pwd').style.display = 'block';
  document.getElementById('user-modal-title').innerHTML = '<span>✏️</span> Editar Usuario';
  openModal('modal-user-form');
}

async function submitUserForm() {
  const id = document.getElementById('form-user-id').value;
  const nombre = document.getElementById('form-user-name').value.trim();
  const username = document.getElementById('form-user-username').value.trim().toLowerCase();
  const email = document.getElementById('form-user-email').value.trim().toLowerCase();
  const rol = document.getElementById('form-user-role').value;
  const password = document.getElementById('form-user-pwd').value.trim();

  if (!nombre) {
    showToast('El nombre es obligatorio.', '⚠️', true);
    return;
  }

  if (!id && (!username || !password)) {
    showToast('Usuario y contraseña son requeridos para nuevas cuentas.', '⚠️', true);
    return;
  }

  const payload = { nombre, email: email || null, rol };
  if (password) payload.password = password;
  if (!id) payload.username = username;

  try {
    let url = '/api/admin/usuarios';
    let method = 'POST';
    if (id) {
      url = `/api/admin/usuarios/${id}`;
      method = 'PUT';
    }

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, '✅');
      closeModal('modal-user-form');
      loadUsers();
    } else {
      showToast(data.error || 'Error al guardar usuario.', '❌', true);
    }
  } catch (e) {
    showToast('Error de conexión al guardar usuario.', '⚠️', true);
  }
}

async function deleteUser(userId, name) {
  if (!confirm(`¿Eliminar la cuenta del usuario "${name}"?`)) return;

  try {
    const res = await fetch(`/api/admin/usuarios/${userId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, '🗑️');
      loadUsers();
    } else {
      showToast(data.error || 'No se pudo eliminar el usuario.', '❌', true);
    }
  } catch (err) {
    showToast('Error de red al eliminar usuario.', '⚠️', true);
  }
}

// ========================================================
// PILAR 4: CANALES PERSONALIZADOS & MANTENIMIENTO
// ========================================================
async function loadMetrics() {
  const container = document.getElementById('admin-metrics-container');
  try {
    const res = await fetch('/api/admin/mantenimiento/metricas');
    const m = await res.json();

    container.innerHTML = `
      <div class="metric-card">
        <span class="metric-val">${m.total_estudiantes}</span>
        <span class="metric-label">Alumnos Registrados</span>
      </div>
      <div class="metric-card">
        <span class="metric-val">${m.total_cursos}</span>
        <span class="metric-label">Cursos Activos</span>
      </div>
      <div class="metric-card">
        <span class="metric-val">${m.puntos_actuales_totales}</span>
        <span class="metric-label">Décimas en Circulación</span>
      </div>
      <div class="metric-card">
        <span class="metric-val">${m.total_transacciones}</span>
        <span class="metric-label">Transacciones Formativas</span>
      </div>
      <div class="metric-card">
        <span class="metric-val">${m.total_materiales}</span>
        <span class="metric-label">Recursos en Biblioteca</span>
      </div>
      <div class="metric-card">
        <span class="metric-val">${m.espacio_disco_mb} <small style="font-size:0.9rem;font-weight:600;">MB</small></span>
        <span class="metric-label">Disco (Fotos / PDFs)</span>
      </div>
    `;
  } catch (err) {
    container.innerHTML = '<div style="color:#f87171;">Error al cargar métricas del sistema.</div>';
  }
}

async function loadCanales() {
  const list = document.getElementById('admin-canales-list');
  try {
    const res = await fetch('/api/biblioteca/canales');
    const canales = await res.json();
    AdminState.canales = canales;

    list.innerHTML = canales.map(c => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:rgba(30,41,69,0.7);border:1px solid var(--border-glass);border-radius:var(--radius-md);">
        <div>
          <div style="font-weight:800;font-size:0.9rem;color:#fff;">${escapeHtml(c.titulo)}</div>
          <div style="font-size:0.75rem;color:var(--text-dim);">slug: ${c.slug} • ${c.total_materiales} materiales</div>
        </div>
        <div style="display:flex;gap:4px;">
          <button class="btn-action-icon" title="Editar canal" onclick='openEditCanalModal(${JSON.stringify(c)})'>✏️</button>
          ${!['guias', 'clases'].includes(c.slug) ? `
            <button class="btn-action-icon delete" title="Eliminar canal" onclick="deleteCanal(${c.id}, '${escapeHtml(c.titulo)}')">🗑️</button>
          ` : '<span style="font-size:0.68rem;color:var(--text-dim);padding:4px;">Sistema</span>'}
        </div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = '<div style="color:#f87171;">Error al cargar canales.</div>';
  }
}

function openNewCanalModal() {
  document.getElementById('form-canal-id').value = '';
  document.getElementById('form-canal-titulo').value = '';
  document.getElementById('form-canal-slug').value = '';
  document.getElementById('form-canal-slug').disabled = false;
  document.getElementById('form-canal-orden').value = '4';
  document.getElementById('form-canal-desc').value = '';
  document.getElementById('canal-modal-title').innerHTML = '<span>➕</span> Nuevo Canal';
  openModal('modal-canal-form');
}

function openEditCanalModal(c) {
  document.getElementById('form-canal-id').value = c.id;
  document.getElementById('form-canal-titulo').value = c.titulo;
  document.getElementById('form-canal-slug').value = c.slug;
  document.getElementById('form-canal-slug').disabled = true;
  document.getElementById('form-canal-orden').value = c.orden || '0';
  document.getElementById('form-canal-desc').value = c.descripcion || '';
  document.getElementById('canal-modal-title').innerHTML = '<span>✏️</span> Editar Canal';
  openModal('modal-canal-form');
}

async function submitCanalForm() {
  const id = document.getElementById('form-canal-id').value;
  const titulo = document.getElementById('form-canal-titulo').value.trim();
  const slug = document.getElementById('form-canal-slug').value.trim().toLowerCase();
  const orden = document.getElementById('form-canal-orden').value;
  const descripcion = document.getElementById('form-canal-desc').value.trim();

  if (!titulo) {
    showToast('El título del canal es requerido.', '⚠️', true);
    return;
  }

  const payload = { titulo, orden: parseInt(orden, 10) || 0, descripcion };
  if (!id) payload.slug = slug;

  try {
    let url = '/api/admin/canales';
    let method = 'POST';
    if (id) {
      url = `/api/admin/canales/${id}`;
      method = 'PUT';
    }

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, '✅');
      closeModal('modal-canal-form');
      loadCanales();
    } else {
      showToast(data.error || 'Error al guardar canal.', '❌', true);
    }
  } catch (e) {
    showToast('Error de conexión al guardar canal.', '⚠️', true);
  }
}

async function deleteCanal(canalId, title) {
  if (!confirm(`¿Eliminar el canal "${title}" y todos sus materiales asociados?`)) return;

  try {
    const res = await fetch(`/api/admin/canales/${canalId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, '🗑️');
      loadCanales();
    } else {
      showToast(data.error || 'No se pudo eliminar el canal.', '❌', true);
    }
  } catch (err) {
    showToast('Error de conexión al eliminar canal.', '⚠️', true);
  }
}

// Inicialización de la pantalla
document.addEventListener('DOMContentLoaded', () => {
  loadStudents();

  // Cerrar modales con overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });
});
