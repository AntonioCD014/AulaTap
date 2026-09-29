/**
 * AulaTap - Frontend Logic & Web NFC Controller
 * Web NFC API (NDEFReader), Audio Feedback, Gamification, Modals, Reporting.
 */

// Interceptor para redirección automática a /login si la sesión expira
const _originalFetch = window.fetch;
window.fetch = async (...args) => {
  const response = await _originalFetch(...args);
  if (response.status === 401 && !window.location.pathname.includes('/login')) {
    window.location.href = '/login';
  }
  return response;
};

// Estado global de la aplicación
const AppState = {
  activeStudent: null,
  selectedPoints: 1,
  selectedReason: "Participación",
  selectedCourse: "todos",
  isNfcListening: false,
  isScanningForBinding: false,
  ndefReader: null,
  isNfcSupported: false,
  targetBindingStudentId: null
};

// ========================================================
// SISTEMA DE AUDIO GAMIFICADO (Web Audio API)
// ========================================================
const SoundFX = {
  ctx: null,
  init() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.ctx = new AudioContext();
      }
    } catch (e) {
      console.warn("Web Audio API no soportado:", e);
    }
  },
  playTone(freq, type = 'sine', duration = 0.15, gainVal = 0.1) {
    if (!this.ctx) this.init();
    if (!this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

    gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start();
    osc.stop(this.ctx.currentTime + duration);
  },
  tap() {
    this.playTone(600, 'triangle', 0.08, 0.08);
  },
  nfcScanned() {
    // Sonido bifónico de escaneo NFC
    this.playTone(880, 'sine', 0.1, 0.12);
    setTimeout(() => this.playTone(1320, 'sine', 0.18, 0.15), 90);
  },
  pointsAwarded() {
    // Fanfarria estilo moneda / nivel
    const notes = [523.25, 659.25, 783.99, 1046.50]; // Do, Mi, Sol, Do alto
    notes.forEach((freq, idx) => {
      setTimeout(() => {
        this.playTone(freq, 'triangle', 0.18, 0.18);
      }, idx * 75);
    });
  },
  error() {
    this.playTone(220, 'sawtooth', 0.25, 0.15);
  }
};

// ========================================================
// CONFETTI CANVAS PARTICLES
// ========================================================
const ConfettiFX = {
  canvas: null,
  ctx: null,
  particles: [],
  animId: null,

  init() {
    this.canvas = document.getElementById('confetti-canvas');
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.resize();
    window.addEventListener('resize', () => this.resize());
  },

  resize() {
    if (!this.canvas) return;
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  },

  burst(x, y) {
    if (!this.ctx) return;
    const colors = ['#06b6d4', '#8b5cf6', '#fbbf24', '#ec4899', '#10b981', '#ffffff'];
    const count = 55;

    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Math.random() * 9 + 4;
      this.particles.push({
        x: x || window.innerWidth / 2,
        y: y || window.innerHeight / 2,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 3,
        size: Math.random() * 8 + 4,
        color: colors[Math.floor(Math.random() * colors.length)],
        rotation: Math.random() * 360,
        rotationSpeed: (Math.random() - 0.5) * 15,
        alpha: 1,
        decay: Math.random() * 0.02 + 0.015,
        isCoin: Math.random() > 0.6
      });
    }

    if (!this.animId) {
      this.loop();
    }
  },

  loop() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.28; // gravedad
      p.rotation += p.rotationSpeed;
      p.alpha -= p.decay;

      if (p.alpha <= 0) {
        this.particles.splice(i, 1);
        continue;
      }

      this.ctx.save();
      this.ctx.globalAlpha = p.alpha;
      this.ctx.translate(p.x, p.y);
      this.ctx.rotate((p.rotation * Math.PI) / 180);
      this.ctx.fillStyle = p.color;

      if (p.isCoin) {
        // Monedita dorada
        this.ctx.beginPath();
        this.ctx.arc(0, 0, p.size / 1.5, 0, Math.PI * 2);
        this.ctx.fill();
      } else {
        // Cuadro o estrella
        this.ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.7);
      }

      this.ctx.restore();
    }

    if (this.particles.length > 0) {
      this.animId = requestAnimationFrame(() => this.loop());
    } else {
      this.animId = null;
    }
  }
};

// ========================================================
// GESTOR DE TOAST NOTIFICATIONS
// ========================================================
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast-notice');
  const msgEl = document.getElementById('toast-msg');
  if (!toast || !msgEl) return;

  msgEl.textContent = message;
  toast.className = `toast-notice ${type} show`;

  if (type === 'error') {
    SoundFX.error();
  }

  setTimeout(() => {
    toast.className = 'toast-notice';
  }, 3200);
}

// ========================================================
// CONTROLADOR DE WEB NFC API (NDEFReader)
// ========================================================
const NfcManager = {
  async init() {
    const badge = document.getElementById('nfc-status-badge');
    const badgeText = document.getElementById('nfc-status-text');

    if ('NDEFReader' in window) {
      AppState.isNfcSupported = true;
      try {
        AppState.ndefReader = new NDEFReader();
        this.setupEventListeners();
        badge.className = 'nfc-badge active';
        badgeText.textContent = 'NFC Listo (Toca para iniciar)';
      } catch (err) {
        console.warn("Error al inicializar NDEFReader:", err);
        this.setFallbackStatus("NFC Error");
      }
    } else {
      AppState.isNfcSupported = false;
      this.setFallbackStatus("Simulador NFC");
      console.log("Web NFC no soportado en este navegador/dispositivo. Modo simulador habilitado.");
    }
  },

  setFallbackStatus(label) {
    const badge = document.getElementById('nfc-status-badge');
    const badgeText = document.getElementById('nfc-status-text');
    badge.className = 'nfc-badge simulated';
    badgeText.textContent = label;
  },

  async startScan() {
    if (!AppState.isNfcSupported) {
      // Abrir modal de simulación directa
      openModal('modal-simulator');
      return;
    }

    const badge = document.getElementById('nfc-status-badge');
    const badgeText = document.getElementById('nfc-status-text');

    try {
      await AppState.ndefReader.scan();
      AppState.isNfcListening = true;
      badge.className = 'nfc-badge listening';
      badgeText.textContent = 'Escaneando...';
      showToast('Lector NFC activo. Acerca la tarjeta escolar.', 'success');
    } catch (error) {
      console.error('Error al iniciar escaneo NFC:', error);
      if (error.name === 'NotAllowedError') {
        showToast('Permiso de NFC denegado en el navegador.', 'error');
      } else {
        showToast('No se pudo activar NFC: ' + error.message, 'error');
      }
      this.setFallbackStatus('NFC Detenido');
    }
  },

  setupEventListeners() {
    if (!AppState.ndefReader) return;

    AppState.ndefReader.addEventListener("readingerror", () => {
      SoundFX.error();
      showToast("Error al leer la tarjeta. Intenta acercarla nuevamente.", "error");
    });

    AppState.ndefReader.addEventListener("reading", ({ message, serialNumber }) => {
      const uid = (serialNumber || "").trim().toLowerCase();
      console.log(`[NFC Read] UID detectado: ${uid}`);

      SoundFX.nfcScanned();

      // Si estábamos en modo de vinculación
      if (AppState.isScanningForBinding) {
        handleNfcBindingDetected(uid);
      } else {
        handleNfcStudentRead(uid);
      }
    });
  }
};

// ========================================================
// MANEJO DE LECTURA DE ESTUDIANTE POR NFC
// ========================================================
async function handleNfcStudentRead(uid) {
  if (!uid) {
    showToast("No se pudo extraer el UID del tag NFC.", "error");
    return;
  }

  showToast(`Tag detectado (${uid}). Buscando estudiante...`, 'success');

  try {
    const res = await fetch(`/api/estudiantes/nfc/${encodeURIComponent(uid)}`);
    if (res.ok) {
      const studentData = await res.json();
      setStudentActive(studentData);
      showToast(`¡Hola, ${studentData.nombre_completo}!`, 'success');
      SoundFX.nfcScanned();
    } else if (res.status === 404) {
      // Tarjeta no registrada: Ofrecer vinculación
      SoundFX.error();
      if (confirm(`La tarjeta [${uid}] no está registrada. ¿Deseas vincularla a un estudiante ahora?`)) {
        openBindingModalWithUid(uid);
      }
    } else {
      showToast("Error al consultar estudiante por NFC.", "error");
    }
  } catch (err) {
    console.error("Error al buscar estudiante NFC:", err);
    showToast("Error de conexión al leer tarjeta.", "error");
  }
}

// ========================================================
// SELECCIÓN Y RENDERIZADO DEL ESTUDIANTE ACTIVO
// ========================================================
function setStudentActive(student) {
  AppState.activeStudent = student;

  const emptyCard = document.getElementById('student-card-empty');
  const activeCard = document.getElementById('student-card-active');
  const btnAssign = document.getElementById('btn-assign');

  if (!student) {
    emptyCard.style.display = 'block';
    activeCard.style.display = 'none';
    const badgesBox = document.getElementById('card-student-badges-box');
    if (badgesBox) badgesBox.style.display = 'none';
    btnAssign.disabled = true;
    return;
  }

  emptyCard.style.display = 'none';
  activeCard.style.display = 'block';
  btnAssign.disabled = false;

  // Actualizar datos del alumno
  document.getElementById('card-student-name').textContent = student.nombre_completo;
  document.getElementById('card-student-course').textContent = student.curso;
  document.getElementById('card-student-rut').textContent = student.rut ? `RUT: ${student.rut}` : 'Sin RUT';

  // Avatar iniciales
  const initials = student.nombre_completo
    .split(' ')
    .slice(0, 2)
    .map(p => p[0])
    .join('')
    .toUpperCase();
  document.getElementById('card-avatar-initials').textContent = initials;

  // Badge NFC
  const nfcBadge = document.getElementById('card-nfc-badge');
  if (student.nfc_uid) {
    nfcBadge.className = 'tag-pill nfc-linked';
    nfcBadge.innerHTML = `<span>📶</span> ${student.nfc_uid.substring(0, 14)}...`;
    nfcBadge.title = `UID completo: ${student.nfc_uid}`;
  } else {
    nfcBadge.className = 'tag-pill nfc-unlinked';
    nfcBadge.innerHTML = `<span>➕</span> Sin tarjeta NFC`;
    nfcBadge.title = "Toca para vincular tarjeta a este alumno";
    nfcBadge.onclick = () => openBindingModalForStudent(student.id);
  }

  // Puntos
  renderStudentScore(student.puntaje_acumulado);

  // Insignias y Logros de Honor
  renderStudentBadgesTeacher(student);

  // Historial reciente
  renderStudentHistory(student.historial || []);

  // Scroll suave al inicio si es mobile
  window.scrollTo({ top: 120, behavior: 'smooth' });
}

function renderStudentScore(points) {
  const digitsEl = document.getElementById('card-score-digits');
  const rankEl = document.getElementById('card-score-rank');

  digitsEl.textContent = points;

  // Rango gamificado
  let rank = "Novato";
  let icon = "🌱";
  if (points >= 15) {
    rank = "Leyenda Escolar";
    icon = "👑";
  } else if (points >= 10) {
    rank = "Maestro";
    icon = "⚡";
  } else if (points >= 6) {
    rank = "Destacado";
    icon = "🌟";
  } else if (points >= 3) {
    rank = "Aprendiz";
    icon = "⭐";
  }

  rankEl.innerHTML = `${icon} Rango: ${rank}`;
}

function renderStudentHistory(transactions) {
  const listEl = document.getElementById('card-mini-history-list');
  listEl.innerHTML = '';

  if (!transactions || transactions.length === 0) {
    listEl.innerHTML = '<div class="mini-history-item" style="color:var(--text-dim);">Sin registros recientes.</div>';
    return;
  }

  transactions.forEach(t => {
    const item = document.createElement('div');
    item.className = 'mini-history-item';
    const isPositive = t.puntos >= 0;
    const sign = isPositive ? `+${t.puntos}` : `${t.puntos}`;
    const ptsClass = isPositive ? 'pts-plus' : 'pts-minus';

    item.innerHTML = `
      <span>${escapeHtml(t.motivo)}</span>
      <span class="${ptsClass}">${sign} pt</span>
    `;
    listEl.appendChild(item);
  });
}

// ========================================================
// GESTIÓN Y SINCRONIZACIÓN DE SELECCIÓN DE PUNTOS
// ========================================================
function updatePointsSelection(value) {
  const numVal = parseInt(value, 10);
  const finalVal = isNaN(numVal) ? 0 : numVal;
  AppState.selectedPoints = finalVal;

  const pointButtons = document.querySelectorAll('.point-pill-btn');
  const customBox = document.querySelector('.custom-points-box');
  const customBadge = document.getElementById('custom-points-badge');
  const customInput = document.getElementById('custom-points-input');
  const suffixEl = document.getElementById('stepper-suffix');
  const btnAssign = document.getElementById('btn-assign');
  const qpChips = document.querySelectorAll('.qp-chip');

  // Sincronizar input si no tiene el foco
  if (customInput && document.activeElement !== customInput) {
    customInput.value = finalVal;
  }

  // Singular / Plural
  const absVal = Math.abs(finalVal);
  const unitLabel = absVal === 1 ? 'décima' : 'décimas';
  if (suffixEl) suffixEl.textContent = unitLabel;

  // Verificar si coincide con +1, +2 o +3
  let matchedQuick = false;
  pointButtons.forEach(btn => {
    const pts = parseInt(btn.dataset.points, 10);
    if (pts === finalVal) {
      btn.classList.add('active');
      matchedQuick = true;
    } else {
      btn.classList.remove('active');
    }
  });

  // Resaltar chips rápidos si coinciden
  qpChips.forEach(chip => {
    const cVal = parseInt(chip.dataset.customVal, 10);
    if (cVal === finalVal) {
      chip.classList.add('active');
    } else {
      chip.classList.remove('active');
    }
  });

  // Estado del badge y caja de personalización
  if (customBox && customBadge) {
    if (matchedQuick) {
      customBox.classList.remove('is-custom-active');
      customBadge.classList.remove('highlight');
      customBadge.textContent = `Rápido (${finalVal >= 0 ? '+' : ''}${finalVal})`;
    } else {
      customBox.classList.add('is-custom-active');
      customBadge.classList.add('highlight');
      customBadge.textContent = `Personalizado (${finalVal >= 0 ? '+' : ''}${finalVal})`;
    }
  }

  // Actualizar texto del botón principal de confirmación
  if (btnAssign) {
    const sign = finalVal >= 0 ? `+${finalVal}` : `${finalVal}`;
    const actionLabel = finalVal < 0 ? 'Confirmar Descuento' : 'Confirmar Asignación';
    btnAssign.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
      </svg>
      ${actionLabel} (${sign} ${unitLabel})
    `;
  }
}

// ========================================================
// ASIGNACIÓN DE PUNTOS
// ========================================================
async function submitPointsAssignment() {
  if (!AppState.activeStudent) {
    showToast("Selecciona o escanea un estudiante primero.", "error");
    return;
  }

  const btnAssign = document.getElementById('btn-assign');
  btnAssign.disabled = true;

  try {
    const response = await fetch(`/api/estudiantes/${AppState.activeStudent.id}/puntos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        puntos: AppState.selectedPoints,
        motivo: AppState.selectedReason
      })
    });

    const data = await response.json();

    if (response.ok && data.success) {
      // Feedback Gamificado: Fanfarria de sonido y lluvia de confetti
      SoundFX.pointsAwarded();
      const rect = btnAssign.getBoundingClientRect();
      ConfettiFX.burst(rect.left + rect.width / 2, rect.top);

      // Actualizar estado local
      AppState.activeStudent.puntaje_acumulado = data.estudiante.puntaje_acumulado;
      if (!AppState.activeStudent.historial) AppState.activeStudent.historial = [];
      AppState.activeStudent.historial.unshift(data.transaccion);

      // Renderizar actualización
      renderStudentScore(AppState.activeStudent.puntaje_acumulado);
      if (data.estudiante && data.estudiante.insignias) {
        AppState.activeStudent.insignias = data.estudiante.insignias;
        AppState.activeStudent.insignias_desbloqueadas = data.estudiante.insignias_desbloqueadas;
        AppState.activeStudent.total_insignias = data.estudiante.total_insignias;
        renderStudentBadgesTeacher(AppState.activeStudent);
      }
      renderStudentHistory(AppState.activeStudent.historial);

      showToast(`¡+${AppState.selectedPoints} asignado a ${data.estudiante.nombre_completo}!`, 'success');
    } else {
      showToast(data.error || "No se pudo asignar el puntaje.", "error");
    }
  } catch (err) {
    console.error("Error al asignar puntos:", err);
    showToast("Error de conexión al registrar los puntos.", "error");
  } finally {
    btnAssign.disabled = false;
  }
}

// ========================================================
// BÚSQUEDA MANUAL INTERACTIVA Y FILTROS
// ========================================================
let searchDebounceTimeout = null;

async function onSearchInputChanged(event) {
  const query = event.target.value.trim();
  const dropdown = document.getElementById('search-dropdown');

  clearTimeout(searchDebounceTimeout);

  if (query.length === 0) {
    dropdown.style.display = 'none';
    dropdown.innerHTML = '';
    return;
  }

  searchDebounceTimeout = setTimeout(async () => {
    try {
      const url = `/api/estudiantes?curso=${AppState.selectedCourse}&q=${encodeURIComponent(query)}`;
      const res = await fetch(url);
      const results = await res.json();

      dropdown.innerHTML = '';
      if (results.length === 0) {
        dropdown.innerHTML = '<div style="padding:12px;font-size:0.8rem;color:var(--text-dim);text-align:center;">No se encontraron estudiantes.</div>';
        dropdown.style.display = 'block';
        return;
      }

      results.forEach(student => {
        const item = document.createElement('div');
        item.className = 'search-item';
        item.innerHTML = `
          <div class="search-item-info">
            <span class="search-item-name">${escapeHtml(student.nombre_completo)}</span>
            <span class="search-item-sub">${student.curso} • ${student.rut || 'Sin RUT'} ${student.nfc_uid ? '• 📶 NFC' : ''}</span>
          </div>
          <span class="search-item-pts">${student.puntaje_acumulado} pts</span>
        `;
        item.onclick = async () => {
          dropdown.style.display = 'none';
          document.getElementById('manual-search-input').value = '';
          // Cargar datos completos con historial
          const detRes = await fetch(`/api/estudiantes/${student.id}`);
          const fullData = await detRes.json();
          setStudentActive(fullData);
          SoundFX.tap();
        };
        dropdown.appendChild(item);
      });

      dropdown.style.display = 'block';
    } catch (e) {
      console.error("Error en búsqueda:", e);
    }
  }, 220);
}

// ========================================================
// MODAL DE VINCULACIÓN NFC
// ========================================================
function openBindingModalWithUid(uid = '') {
  AppState.isScanningForBinding = true;
  document.getElementById('bind-uid-input').value = uid;
  document.getElementById('bind-detected-uid').textContent = uid || 'Esperando acercamiento...';
  loadStudentsForBindingSelect();
  openModal('modal-binding');
}

function openBindingModalForStudent(studentId) {
  AppState.targetBindingStudentId = studentId;
  AppState.isScanningForBinding = true;
  document.getElementById('bind-uid-input').value = '';
  document.getElementById('bind-detected-uid').textContent = 'Acerca tarjeta al teléfono...';
  loadStudentsForBindingSelect(studentId);
  openModal('modal-binding');
}

async function loadStudentsForBindingSelect(preselectId = null) {
  const select = document.getElementById('bind-student-select');
  select.innerHTML = '<option value="">Cargando estudiantes...</option>';

  try {
    const res = await fetch('/api/estudiantes');
    const students = await res.json();
    select.innerHTML = '<option value="">-- Selecciona el estudiante --</option>';

    students.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      const nfcTag = s.nfc_uid ? ' (Ya tiene tarjeta)' : ' (Sin tarjeta)';
      opt.textContent = `${s.nombre_completo} [${s.curso}]${nfcTag}`;
      if (preselectId && s.id === preselectId) {
        opt.selected = true;
      } else if (!preselectId && AppState.activeStudent && s.id === AppState.activeStudent.id) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
  } catch (err) {
    select.innerHTML = '<option value="">Error al cargar alumnos</option>';
  }
}

function handleNfcBindingDetected(uid) {
  document.getElementById('bind-uid-input').value = uid;
  document.getElementById('bind-detected-uid').textContent = `Detectado: ${uid}`;
  showToast(`Tarjeta detectada: ${uid}`, 'success');
}

async function submitNfcBinding() {
  const studentId = document.getElementById('bind-student-select').value;
  const uid = document.getElementById('bind-uid-input').value.trim();

  if (!studentId) {
    showToast("Selecciona a qué estudiante vincular la tarjeta.", "error");
    return;
  }
  if (!uid) {
    showToast("Ingresa o escanea el UID de la tarjeta.", "error");
    return;
  }

  try {
    const res = await fetch(`/api/estudiantes/${studentId}/vincular-nfc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nfc_uid: uid })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, 'success');
      SoundFX.pointsAwarded();
      closeModal('modal-binding');
      AppState.isScanningForBinding = false;

      // Si es el alumno activo, actualizar su badge
      if (AppState.activeStudent && AppState.activeStudent.id === parseInt(studentId)) {
        AppState.activeStudent.nfc_uid = uid;
        setStudentActive(AppState.activeStudent);
      }
    } else {
      showToast(data.error || "No se pudo vincular la tarjeta.", "error");
    }
  } catch (e) {
    showToast("Error de conexión al vincular tarjeta.", "error");
  }
}

// ========================================================
// MODAL DE REPORTES Y EXPORTACIÓN
// ========================================================
async function loadReportsData() {
  const courseFilter = document.getElementById('report-course-filter').value;
  const tbody = document.getElementById('ranking-table-body');
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:16px;">Cargando reporte...</td></tr>';

  try {
    const res = await fetch(`/api/estudiantes?curso=${courseFilter}`);
    const students = await res.json();

    // Ordenar por puntaje descendente
    students.sort((a, b) => b.puntaje_acumulado - a.puntaje_acumulado);

    // Calcular estadísticas
    const totalPuntos = students.reduce((acc, curr) => acc + curr.puntaje_acumulado, 0);
    const promedio = students.length > 0 ? (totalPuntos / students.length).toFixed(1) : 0;

    document.getElementById('stat-total-points').textContent = totalPuntos;
    document.getElementById('stat-average-points').textContent = promedio;

    tbody.innerHTML = '';
    if (students.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:16px;">No hay estudiantes en este curso.</td></tr>';
      return;
    }

    students.forEach((s, idx) => {
      const tr = document.createElement('tr');
      let rankClass = '';
      if (idx === 0) rankClass = 'rank-top1';
      else if (idx === 1) rankClass = 'rank-top2';
      else if (idx === 2) rankClass = 'rank-top3';

      tr.innerHTML = `
        <td><span class="rank-pill ${rankClass}">${idx + 1}</span></td>
        <td>
          <div style="font-weight:700;">${escapeHtml(s.nombre_completo)}</div>
          <div style="font-size:0.7rem;color:var(--text-dim);">${s.curso} • ${s.rut || 'S/R'}</div>
        </td>
        <td><strong style="color:var(--accent-gold);">${s.puntaje_acumulado}</strong></td>
        <td>
          <button class="tag-pill" style="cursor:pointer;border:none;" onclick="selectStudentFromReport(${s.id})">Ver</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#f87171;">Error al cargar reporte.</td></tr>';
  }
}

async function selectStudentFromReport(studentId) {
  closeModal('modal-reports');
  const res = await fetch(`/api/estudiantes/${studentId}`);
  const data = await res.json();
  setStudentActive(data);
  SoundFX.tap();
}

function exportExcel() {
  const courseFilter = document.getElementById('report-course-filter').value;
  window.location.href = `/api/exportar/excel?curso=${courseFilter}`;
}

function exportCsv() {
  const courseFilter = document.getElementById('report-course-filter').value;
  window.location.href = `/api/exportar/csv?curso=${courseFilter}`;
}

// ========================================================
// SIMULADOR NFC INTEGRADO (Para pruebas en PC o sin chip)
// ========================================================
async function loadSimulatorTags() {
  const container = document.getElementById('sim-tags-container');
  container.innerHTML = '<div style="font-size:0.8rem;color:var(--text-dim);padding:8px;">Cargando tarjetas de prueba...</div>';

  try {
    const res = await fetch('/api/estudiantes');
    const students = await res.json();

    container.innerHTML = '';
    const linkedStudents = students.filter(s => s.nfc_uid);

    if (linkedStudents.length === 0) {
      container.innerHTML = '<div style="font-size:0.8rem;color:var(--text-dim);">No hay tarjetas vinculadas registradas.</div>';
    } else {
      linkedStudents.forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'dock-btn active';
        btn.style.width = '100%';
        btn.style.margin = '4px 0';
        btn.style.justifyContent = 'space-between';
        btn.style.display = 'flex';
        btn.style.flexDirection = 'row';
        btn.style.padding = '8px 12px';
        btn.innerHTML = `
          <div style="text-align:left;">
            <strong>${escapeHtml(s.nombre_completo)}</strong> (${s.curso})
            <div style="font-family:monospace;font-size:0.68rem;color:var(--accent-cyan);">${s.nfc_uid}</div>
          </div>
          <span style="font-size:0.75rem;background:rgba(255,255,255,0.1);padding:2px 8px;border-radius:10px;">Simular Tap</span>
        `;
        btn.onclick = () => {
          closeModal('modal-simulator');
          SoundFX.nfcScanned();
          if (AppState.isScanningForBinding) {
            handleNfcBindingDetected(s.nfc_uid);
          } else {
            handleNfcStudentRead(s.nfc_uid);
          }
        };
        container.appendChild(btn);
      });
    }
  } catch (e) {
    container.innerHTML = '<div style="color:#f87171;">Error al cargar simulador.</div>';
  }
}

function simulateCustomUid() {
  const customUid = document.getElementById('sim-custom-uid').value.trim();
  if (!customUid) {
    showToast("Ingresa un UID para simular.", "error");
    return;
  }
  closeModal('modal-simulator');
  SoundFX.nfcScanned();
  if (AppState.isScanningForBinding) {
    handleNfcBindingDetected(customUid);
  } else {
    handleNfcStudentRead(customUid);
  }
}

// ========================================================
// MODAL PARA NUEVO ESTUDIANTE
// ========================================================
async function submitNewStudent() {
  const nombre = document.getElementById('new-student-name').value.trim();
  const curso = document.getElementById('new-student-course').value.trim();
  const rut = document.getElementById('new-student-rut').value.trim();
  const nfcUid = document.getElementById('new-student-nfc').value.trim();

  if (!nombre || !curso) {
    showToast("Nombre y curso son obligatorios.", "error");
    return;
  }

  try {
    const res = await fetch('/api/estudiantes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nombre_completo: nombre,
        curso: curso,
        rut: rut || null,
        nfc_uid: nfcUid || null
      })
    });

    const data = await res.json();
    if (res.ok) {
      showToast(`Estudiante ${data.nombre_completo} creado exitosamente.`, 'success');
      SoundFX.pointsAwarded();
      closeModal('modal-new-student');
      // Limpiar inputs
      document.getElementById('new-student-name').value = '';
      document.getElementById('new-student-rut').value = '';
      document.getElementById('new-student-nfc').value = '';
      // Activar al nuevo estudiante
      setStudentActive(data);
      // Recargar selectores de curso si se introdujo un nuevo curso
      loadCursos();
    } else {
      showToast(data.error || "Error al crear estudiante", "error");
    }
  } catch (err) {
    showToast("Error de conexión al crear estudiante.", "error");
  }
}

// ========================================================
// GESTIÓN DE MODALES
// ========================================================
function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) {
    el.classList.add('open');
    if (modalId === 'modal-reports') loadReportsData();
    if (modalId === 'modal-simulator') loadSimulatorTags();
  }
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.remove('open');
  if (modalId === 'modal-binding') AppState.isScanningForBinding = false;
}

// ========================================================
// CARGA DE CURSOS DINÁMICOS
// ========================================================
async function loadCursos() {
  try {
    const res = await fetch('/api/cursos');
    const cursos = await res.json();

    const courseSelect = document.getElementById('course-filter-select');
    const reportFilter = document.getElementById('report-course-filter');
    const bibFilter = document.getElementById('bib-filter-course');
    const newMatCurso = document.getElementById('new-mat-curso');
    const calFilter = document.getElementById('cal-filter-course');
    const evalInputCurso = document.getElementById('eval-input-curso');
    const buzonFilter = document.getElementById('buzon-filter-curso');

    // Mantener opción 'todos'
    courseSelect.innerHTML = '<option value="todos">Todos los cursos</option>';
    reportFilter.innerHTML = '<option value="todos">Todos los cursos</option>';
    if (bibFilter) bibFilter.innerHTML = '<option value="todos">Todos los cursos</option>';
    if (newMatCurso) newMatCurso.innerHTML = '<option value="TODOS">TODOS los Cursos</option>';
    if (calFilter) calFilter.innerHTML = '<option value="todos">Todos los cursos</option>';
    if (evalInputCurso) evalInputCurso.innerHTML = '<option value="TODOS">TODOS los Cursos</option>';
    if (buzonFilter) buzonFilter.innerHTML = '<option value="todos">Todos los Cursos</option>';

    cursos.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = `Curso ${c}`;
      courseSelect.appendChild(opt);

      const optReport = document.createElement('option');
      optReport.value = c;
      optReport.textContent = `Curso ${c}`;
      reportFilter.appendChild(optReport);

      if (bibFilter) {
        const optBib = document.createElement('option');
        optBib.value = c;
        optBib.textContent = `Curso ${c}`;
        bibFilter.appendChild(optBib);
      }

      if (newMatCurso) {
        const optNew = document.createElement('option');
        optNew.value = c;
        optNew.textContent = `Solo Curso ${c}`;
        newMatCurso.appendChild(optNew);
      }

      if (calFilter) {
        const optCal = document.createElement('option');
        optCal.value = c;
        optCal.textContent = `Curso ${c}`;
        calFilter.appendChild(optCal);
      }

      if (evalInputCurso) {
        const optEval = document.createElement('option');
        optEval.value = c;
        optEval.textContent = `Solo Curso ${c}`;
        evalInputCurso.appendChild(optEval);
      }

      if (buzonFilter) {
        const optBuzon = document.createElement('option');
        optBuzon.value = c;
        optBuzon.textContent = `Curso ${c}`;
        buzonFilter.appendChild(optBuzon);
      }
    });
  } catch (e) {
    console.error("Error al cargar cursos:", e);
  }
}

// ========================================================
// BIBLIOTECA DIGITAL Y BITÁCORA DE CLASES (DOCENTE)
// ========================================================
const BibliotecaDocenteState = {
  activeChannel: 'todos',
  materials: [],
  selectedType: 'archivo'
};

function openBibliotecaModal() {
  openModal('modal-biblioteca');
  loadBibliotecaMaterialesDocente();
}

function setDocenteChannel(channelSlug) {
  BibliotecaDocenteState.activeChannel = channelSlug;
  const tabs = document.querySelectorAll('#docente-channel-nav .channel-tab-btn');
  tabs.forEach(t => {
    if (t.dataset.channel === channelSlug) {
      t.classList.add('active');
    } else {
      t.classList.remove('active');
    }
  });
  renderBibliotecaDocenteFeed();
  SoundFX.tap();
}

function toggleNewMaterialForm() {
  const panel = document.getElementById('bib-new-material-panel');
  const isHidden = panel.style.display === 'none' || panel.style.display === '';
  panel.style.display = isHidden ? 'block' : 'none';
  if (isHidden) {
    onCanalChangeInForm();
  }
}

function onCanalChangeInForm() {
  const canal = document.getElementById('new-mat-canal').value;
  const wrapFecha = document.getElementById('wrap-mat-fecha');
  const fechaInput = document.getElementById('new-mat-fecha');
  if (canal === 'clases') {
    wrapFecha.style.display = 'block';
    if (!fechaInput.value) {
      const today = new Date().toISOString().split('T')[0];
      fechaInput.value = today;
    }
  } else {
    wrapFecha.style.display = 'none';
  }
}

function setMaterialType(type) {
  BibliotecaDocenteState.selectedType = type;
  document.getElementById('btn-type-file').classList.toggle('active', type === 'archivo');
  document.getElementById('btn-type-link').classList.toggle('active', type === 'enlace');
  document.getElementById('btn-type-text').classList.toggle('active', type === 'texto');

  document.getElementById('wrap-input-file').style.display = type === 'archivo' ? 'block' : 'none';
  document.getElementById('wrap-input-link').style.display = type === 'enlace' ? 'block' : 'none';
  SoundFX.tap();
}

async function loadBibliotecaMaterialesDocente() {
  const courseFilter = document.getElementById('bib-filter-course').value;
  const feed = document.getElementById('bib-docente-feed');
  feed.innerHTML = '<div style="text-align:center;padding:16px;font-size:0.82rem;color:var(--text-dim);">Cargando materiales...</div>';

  try {
    const url = `/api/biblioteca/materiales?curso=${courseFilter}`;
    const res = await fetch(url);
    const materials = await res.json();
    BibliotecaDocenteState.materials = materials;
    renderBibliotecaDocenteFeed();
  } catch (err) {
    feed.innerHTML = '<div style="color:#f87171;padding:12px;text-align:center;">Error al cargar la biblioteca.</div>';
  }
}

function renderBibliotecaDocenteFeed() {
  const feed = document.getElementById('bib-docente-feed');
  const activeChannel = BibliotecaDocenteState.activeChannel;
  let items = BibliotecaDocenteState.materials;

  if (activeChannel !== 'todos') {
    items = items.filter(m => m.canal_slug === activeChannel);
  }

  if (items.length === 0) {
    feed.innerHTML = `
      <div style="text-align:center;padding:24px 16px;background:rgba(255,255,255,0.02);border:1px dashed var(--border-glass);border-radius:var(--radius-md);">
        <div style="font-size:1.8rem;margin-bottom:6px;">📭</div>
        <div style="font-weight:700;font-size:0.9rem;color:#fff;">Sin materiales en esta sección</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">Toca "+ Publicar" arriba para agregar una guía o registrar la clase de hoy.</div>
      </div>
    `;
    return;
  }

  feed.innerHTML = items.map(m => {
    let dateStr = '';
    if (m.fecha_clase) {
      dateStr = `🗓️ Clase: ${m.fecha_clase}`;
    } else if (m.creado_en) {
      dateStr = `Publicado: ${m.creado_en.substring(0, 10)}`;
    }

    const typeClass = m.canal_slug === 'clases' ? 'clase' : (m.canal_slug === 'guias' ? 'guia' : 'aviso');

    let actionBtn = '';
    if (m.tipo === 'archivo' && m.url_recurso) {
      actionBtn = `
        <a href="/biblioteca/descargar/${m.id}?download=1" class="tag-pill" style="text-decoration:none;color:#a5b4fc;border-color:rgba(165,180,252,0.4);" download>
          📥 Descargar (${escapeHtml(m.nombre_archivo || 'Archivo')})
        </a>
      `;
    } else if (m.tipo === 'enlace' && m.url_recurso) {
      actionBtn = `
        <a href="${m.url_recurso}" target="_blank" rel="noopener noreferrer" class="tag-pill" style="text-decoration:none;color:#67e8f9;border-color:rgba(6,182,212,0.4);">
          🔗 Abrir Enlace
        </a>
      `;
    }

    const escapedTitle = escapeHtml(m.titulo).replace(/'/g, "\\'");

    return `
      <div class="docente-resource-item ${typeClass}">
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="tag-pill course" style="font-size:0.7rem;padding:2px 8px;">${m.curso}</span>
            <span class="tag-pill" style="font-size:0.7rem;padding:2px 8px;">${m.canal_titulo || m.canal_slug}</span>
          </div>
          <span style="font-size:0.72rem;color:var(--text-dim);">${dateStr}</span>
        </div>

        <h4 style="font-size:0.95rem;font-weight:800;color:#fff;margin:2px 0;">${escapeHtml(m.titulo)}</h4>
        ${m.descripcion ? `<p style="font-size:0.8rem;color:var(--text-muted);line-height:1.4;white-space:pre-line;">${escapeHtml(m.descripcion)}</p>` : ''}

        <div style="display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;margin-top:4px;">
          <div>${actionBtn}</div>
          <button type="button" class="tag-pill" style="cursor:pointer;color:#f87171;border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.1);" onclick="deleteBibliotecaMaterial(${m.id}, '${escapedTitle}')">
            🗑️ Eliminar
          </button>
        </div>
      </div>
    `;
  }).join('');
}

async function submitNewMaterial(event) {
  event.preventDefault();
  const btn = document.getElementById('btn-save-material');
  btn.disabled = true;
  btn.textContent = 'Publicando...';

  try {
    const canalSlug = document.getElementById('new-mat-canal').value;
    const curso = document.getElementById('new-mat-curso').value;
    const titulo = document.getElementById('new-mat-titulo').value.trim();
    const desc = document.getElementById('new-mat-desc').value.trim();
    const fecha = document.getElementById('new-mat-fecha').value;
    const url = document.getElementById('new-mat-url').value.trim();
    const fileInput = document.getElementById('new-mat-file');

    const formData = new FormData();
    formData.append('canal_slug', canalSlug);
    formData.append('curso', curso);
    formData.append('titulo', titulo);
    formData.append('descripcion', desc);
    formData.append('tipo', BibliotecaDocenteState.selectedType);
    if (fecha) formData.append('fecha_clase', fecha);
    if (url) formData.append('url_recurso', url);
    if (fileInput.files.length > 0) {
      formData.append('file', fileInput.files[0]);
    }

    const res = await fetch('/api/biblioteca/materiales', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje || 'Material publicado con éxito.', 'success');
      SoundFX.pointsAwarded();
      document.getElementById('form-upload-material').reset();
      toggleNewMaterialForm();
      loadBibliotecaMaterialesDocente();
    } else {
      showToast(data.error || 'No se pudo publicar el material.', 'error');
    }
  } catch (err) {
    showToast('Error de conexión al subir el material.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '💾 Publicar en Biblioteca';
  }
}

async function deleteBibliotecaMaterial(id, title) {
  if (!confirm(`¿Estás seguro de eliminar "${title}" de la biblioteca?`)) return;

  try {
    const res = await fetch(`/api/biblioteca/materiales/${id}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.mensaje, 'success');
      SoundFX.tap();
      loadBibliotecaMaterialesDocente();
    } else {
      showToast(data.error || 'Error al eliminar material.', 'error');
    }
  } catch (e) {
    showToast('Error de conexión al eliminar material.', 'error');
  }
}


// ========================================================
// HELPERS
// ========================================================
function escapeHtml(text) {
  if (!text) return '';
  return text.replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[m];
  });
}

// ========================================================
// INICIALIZACIÓN DE LA APLICACIÓN
// ========================================================
document.addEventListener('DOMContentLoaded', () => {
  SoundFX.init();
  ConfettiFX.init();
  NfcManager.init();
  loadCursos();
  updateBuzonPendingCounter();

  // Registrar Service Worker PWA
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('Service Worker registrado correctamente:', reg.scope))
      .catch(err => console.warn('Fallo registro Service Worker:', err));
  }

  // Click en badge NFC de la cabecera
  const nfcBadge = document.getElementById('nfc-status-badge');
  nfcBadge.addEventListener('click', () => {
    SoundFX.tap();
    NfcManager.startScan();
  });

  // Botón Scan en el banner
  const btnScanBanner = document.getElementById('btn-scan-banner');
  if (btnScanBanner) {
    btnScanBanner.addEventListener('click', () => {
      SoundFX.tap();
      NfcManager.startScan();
    });
  }

  // Filtro de Curso
  const courseSelect = document.getElementById('course-filter-select');
  courseSelect.addEventListener('change', (e) => {
    AppState.selectedCourse = e.target.value;
    SoundFX.tap();
    // Limpiar búsqueda si hay
    document.getElementById('manual-search-input').value = '';
    document.getElementById('search-dropdown').style.display = 'none';
  });

  // Buscador interactivo
  const searchInput = document.getElementById('manual-search-input');
  searchInput.addEventListener('input', onSearchInputChanged);

  // Cerrar dropdown si se hace click afuera
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrap')) {
      document.getElementById('search-dropdown').style.display = 'none';
    }
  });

  // Inicializar selección en +1 décima
  updatePointsSelection(1);

  // Selector de puntos rápidos (+1, +2, +3)
  const pointButtons = document.querySelectorAll('.point-pill-btn');
  pointButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const pts = parseInt(btn.dataset.points, 10);
      updatePointsSelection(pts);
      SoundFX.tap();
    });
  });

  // Botón Stepper: Disminuir (-)
  const btnDec = document.getElementById('btn-dec-points');
  if (btnDec) {
    btnDec.addEventListener('click', () => {
      updatePointsSelection(AppState.selectedPoints - 1);
      SoundFX.tap();
    });
  }

  // Botón Stepper: Aumentar (+)
  const btnInc = document.getElementById('btn-inc-points');
  if (btnInc) {
    btnInc.addEventListener('click', () => {
      updatePointsSelection(AppState.selectedPoints + 1);
      SoundFX.tap();
    });
  }

  // Input de personalización directa
  const customInput = document.getElementById('custom-points-input');
  if (customInput) {
    customInput.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      updatePointsSelection(isNaN(val) ? 0 : val);
    });
    customInput.addEventListener('change', (e) => {
      const val = parseInt(e.target.value, 10);
      updatePointsSelection(isNaN(val) ? 0 : val);
    });
  }

  // Chips rápidos (-1, +4, +5, +10)
  const qpChips = document.querySelectorAll('.qp-chip');
  qpChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const val = parseInt(chip.dataset.customVal, 10);
      updatePointsSelection(val);
      SoundFX.tap();
    });
  });

  // Selector de motivos
  const reasonTags = document.querySelectorAll('.reason-tag');
  reasonTags.forEach(tag => {
    tag.addEventListener('click', () => {
      reasonTags.forEach(t => t.classList.remove('active'));
      tag.classList.add('active');
      AppState.selectedReason = tag.dataset.reason;
      SoundFX.tap();
    });
  });

  // Botón Asignar Décimas
  const btnAssign = document.getElementById('btn-assign');
  btnAssign.addEventListener('click', () => {
    submitPointsAssignment();
  });

  // Modal Reportes cambio de filtro
  document.getElementById('report-course-filter').addEventListener('change', () => {
    loadReportsData();
  });

  // Cerrar modales con overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });
});

// ========================================================
// CALENDARIO HÍBRIDO Y EVALUACIONES (DOCENTE)
// ========================================================
const CalendarioState = {
  currentDate: new Date(),
  selectedDateStr: null,
  evaluaciones: []
};

const MESES_ES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
];

const DIAS_ES = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];

function openCalendarioModal() {
  openModal('modal-calendario');
  const mainFilter = document.getElementById('course-filter-select');
  const calFilter = document.getElementById('cal-filter-course');
  if (mainFilter && calFilter && mainFilter.value) {
    calFilter.value = mainFilter.value;
  }
  loadDocenteEvaluaciones();
}

function toggleNewEvaluacionForm(resetData = true) {
  const panel = document.getElementById('eval-form-panel');
  if (!panel) return;
  const isHidden = panel.style.display === 'none' || panel.style.display === '';
  panel.style.display = isHidden ? 'block' : 'none';

  if (isHidden && resetData) {
    document.getElementById('eval-form-title').textContent = '✨ Nueva Evaluación';
    document.getElementById('eval-edit-id').value = '';
    document.getElementById('eval-input-titulo').value = '';
    document.getElementById('eval-input-tipo').value = 'Prueba Sumativa';
    document.getElementById('eval-input-hora').value = '08:30';
    document.getElementById('eval-input-max-decimas').value = '5';
    document.getElementById('eval-input-desc').value = '';

    const calFilter = document.getElementById('cal-filter-course');
    const inputCurso = document.getElementById('eval-input-curso');
    if (calFilter && inputCurso && calFilter.value !== 'todos') {
      inputCurso.value = calFilter.value;
    }

    const fechaInput = document.getElementById('eval-input-fecha');
    if (fechaInput) {
      if (CalendarioState.selectedDateStr) {
        fechaInput.value = CalendarioState.selectedDateStr;
      } else {
        const todayStr = new Date().toISOString().split('T')[0];
        fechaInput.value = todayStr;
      }
    }
  }
  SoundFX.tap();
}

async function loadDocenteEvaluaciones() {
  const courseFilter = document.getElementById('cal-filter-course')?.value || 'todos';
  const listEl = document.getElementById('eval-docente-list');
  if (listEl) {
    listEl.innerHTML = '<div style="text-align:center;padding:16px;font-size:0.82rem;color:var(--text-dim);">Cargando evaluaciones...</div>';
  }

  try {
    const url = courseFilter === 'todos' ? '/api/evaluaciones' : `/api/evaluaciones?curso=${encodeURIComponent(courseFilter)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Error al consultar evaluaciones');
    const data = await res.json();
    CalendarioState.evaluaciones = data;
    renderMiniCalendar();
    renderEvaluacionesList();
  } catch (err) {
    console.error('Error al cargar evaluaciones:', err);
    if (listEl) {
      listEl.innerHTML = '<div style="text-align:center;padding:16px;font-size:0.82rem;color:#fca5a5;">Error al cargar las evaluaciones</div>';
    }
  }
}

function renderMiniCalendar() {
  const grid = document.getElementById('cal-days-grid');
  const monthTitle = document.getElementById('cal-month-name');
  if (!grid || !monthTitle) return;

  const year = CalendarioState.currentDate.getFullYear();
  const month = CalendarioState.currentDate.getMonth();

  monthTitle.textContent = `${MESES_ES[month]} ${year}`;
  grid.innerHTML = '';

  const firstDayIndex = new Date(year, month, 1).getDay(); // 0 es Domingo
  // Ajustar para que Lunes sea 0 y Domingo sea 6
  const startingCol = (firstDayIndex + 6) % 7;

  const totalDays = new Date(year, month + 1, 0).getDate();

  // Celdas vacías iniciales
  for (let i = 0; i < startingCol; i++) {
    const emptyCell = document.createElement('div');
    emptyCell.className = 'calendar-day-cell empty';
    grid.appendChild(emptyCell);
  }

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  // Agrupar evaluaciones por fecha YYYY-MM-DD
  const evMap = {};
  CalendarioState.evaluaciones.forEach(ev => {
    if (!ev.fecha) return;
    if (!evMap[ev.fecha]) evMap[ev.fecha] = [];
    evMap[ev.fecha].push(ev);
  });

  // Generar celdas de días
  for (let day = 1; day <= totalDays; day++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const cell = document.createElement('div');
    cell.className = 'calendar-day-cell';
    cell.textContent = day;

    if (dateStr === todayStr) {
      cell.classList.add('today');
    }

    if (dateStr === CalendarioState.selectedDateStr) {
      cell.classList.add('selected');
    }

    // Dots indicadores de eventos
    if (evMap[dateStr] && evMap[dateStr].length > 0) {
      const dotsWrap = document.createElement('div');
      dotsWrap.className = 'calendar-day-dots';

      const tiposUnicos = [...new Set(evMap[dateStr].map(e => e.tipo))];
      tiposUnicos.slice(0, 3).forEach(tipo => {
        const dot = document.createElement('span');
        let tipoClass = 'prueba';
        if (tipo.includes('Control')) tipoClass = 'control';
        else if (tipo.includes('Trabajo')) tipoClass = 'trabajo';
        else if (tipo.includes('Presentación') || tipo.includes('Disertación')) tipoClass = 'presentacion';
        dot.className = `cal-dot ${tipoClass}`;
        dotsWrap.appendChild(dot);
      });
      cell.appendChild(dotsWrap);
    }

    cell.addEventListener('click', () => {
      SoundFX.tap();
      if (CalendarioState.selectedDateStr === dateStr) {
        CalendarioState.selectedDateStr = null;
      } else {
        CalendarioState.selectedDateStr = dateStr;
      }
      renderMiniCalendar();
      renderEvaluacionesList();
    });

    grid.appendChild(cell);
  }
}

function calPrevMonth() {
  CalendarioState.currentDate.setMonth(CalendarioState.currentDate.getMonth() - 1);
  renderMiniCalendar();
  SoundFX.tap();
}

function calNextMonth() {
  CalendarioState.currentDate.setMonth(CalendarioState.currentDate.getMonth() + 1);
  renderMiniCalendar();
  SoundFX.tap();
}

function calGoToday() {
  CalendarioState.currentDate = new Date();
  renderMiniCalendar();
  SoundFX.tap();
}

function clearDateFilter() {
  CalendarioState.selectedDateStr = null;
  renderMiniCalendar();
  renderEvaluacionesList();
  SoundFX.tap();
}

function renderEvaluacionesList() {
  const listEl = document.getElementById('eval-docente-list');
  const statusText = document.getElementById('eval-agenda-status-text');
  const btnClear = document.getElementById('btn-clear-date-filter');
  if (!listEl) return;

  let filtered = CalendarioState.evaluaciones;

  if (CalendarioState.selectedDateStr) {
    filtered = filtered.filter(e => e.fecha === CalendarioState.selectedDateStr);
    const parts = CalendarioState.selectedDateStr.split('-');
    statusText.textContent = `Evaluaciones del ${parts[2]}/${parts[1]}/${parts[0]}`;
    if (btnClear) btnClear.style.display = 'inline-block';
  } else {
    statusText.textContent = 'Próximas Evaluaciones';
    if (btnClear) btnClear.style.display = 'none';
  }

  if (!filtered || filtered.length === 0) {
    listEl.innerHTML = `
      <div style="text-align:center; padding: 24px 14px; background: rgba(22, 30, 50, 0.4); border-radius: var(--radius-md); border: 1px dashed var(--border-glass);">
        <div style="font-size: 1.6rem; margin-bottom: 6px;">📅</div>
        <div style="font-size: 0.85rem; font-weight: 700; color: #fff;">No hay evaluaciones ${CalendarioState.selectedDateStr ? 'en este día' : 'agendadas'}</div>
        <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 4px;">Usa el botón "+ Agendar" para programar pruebas o controles.</div>
      </div>
    `;
    return;
  }

  listEl.innerHTML = '';
  filtered.forEach(ev => {
    const card = document.createElement('div');

    let tipoClass = 'prueba';
    let cardTipoClass = 'tipo-prueba';
    if (ev.tipo.includes('Control')) { tipoClass = 'control'; cardTipoClass = 'tipo-control'; }
    else if (ev.tipo.includes('Trabajo')) { tipoClass = 'trabajo'; cardTipoClass = 'tipo-trabajo'; }
    else if (ev.tipo.includes('Presentación') || ev.tipo.includes('Disertación')) { tipoClass = 'presentacion'; cardTipoClass = 'tipo-presentacion'; }

    card.className = `eval-card ${cardTipoClass}`;

    // Cálculo de tiempo
    let timeBadgeHtml = '';
    const d = ev.dias_restantes;
    if (d === 0) {
      timeBadgeHtml = `<span class="eval-time-badge urgent">🎯 ¡Hoy!</span>`;
    } else if (d === 1) {
      timeBadgeHtml = `<span class="eval-time-badge urgent">🔔 Mañana</span>`;
    } else if (d > 1 && d <= 3) {
      timeBadgeHtml = `<span class="eval-time-badge urgent">⏳ En ${d} días</span>`;
    } else if (d > 3 && d <= 7) {
      timeBadgeHtml = `<span class="eval-time-badge soon">⏳ En ${d} días</span>`;
    } else if (d > 7) {
      timeBadgeHtml = `<span class="eval-time-badge normal">📅 En ${d} días</span>`;
    } else if (d !== null && d < 0) {
      timeBadgeHtml = `<span class="eval-time-badge past">✓ Realizada</span>`;
    }

    // Formato de fecha legible
    let fechaLegible = ev.fecha || '';
    if (ev.fecha) {
      const parts = ev.fecha.split('-');
      const dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
      const diaSemana = DIAS_ES[dateObj.getDay()];
      fechaLegible = `${diaSemana} ${parts[2]} de ${MESES_ES[parseInt(parts[1]) - 1]}`;
    }

    card.innerHTML = `
      <div class="eval-card-top">
        <div class="eval-badge-group">
          <span class="eval-badge ${tipoClass}">${escapeHtml(ev.tipo)}</span>
          <span class="tag-pill course">${ev.curso === 'TODOS' ? 'Todos los Cursos' : 'Curso ' + escapeHtml(ev.curso)}</span>
        </div>
        ${timeBadgeHtml}
      </div>

      <div class="eval-card-title">${escapeHtml(ev.titulo)}</div>

      <div class="eval-card-meta">
        <span style="display:flex; align-items:center; gap:4px; color:#cbd5e1;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
          </svg>
          ${fechaLegible}
        </span>
        ${ev.hora ? `
          <span style="display:flex; align-items:center; gap:4px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            ${escapeHtml(ev.hora)} hrs
          </span>
        ` : ''}
      </div>

      ${ev.descripcion ? `
        <div class="eval-card-desc">
          <strong>Temario / Apuntes:</strong> ${escapeHtml(ev.descripcion)}
        </div>
      ` : ''}

      <div class="eval-card-footer">
        <div class="eval-decimas-meta" title="Tope de décimas de AulaTap aplicables a esta nota">
          ⭐ Hasta +${ev.max_decimas} décimas canjeables
        </div>
        <div class="eval-actions-group">
          <button class="btn-eval-action" onclick="openEditEvaluacion(${ev.id})" title="Editar evaluación">
            ✏️ Editar
          </button>
          <button class="btn-eval-action delete" onclick="deleteEvaluacion(${ev.id})" title="Eliminar evaluación">
            🗑️
          </button>
        </div>
      </div>
    `;

    listEl.appendChild(card);
  });
}

function openEditEvaluacion(id) {
  const ev = CalendarioState.evaluaciones.find(e => e.id === id);
  if (!ev) return;

  const panel = document.getElementById('eval-form-panel');
  if (panel) panel.style.display = 'block';

  document.getElementById('eval-form-title').textContent = '✏️ Editar Evaluación';
  document.getElementById('eval-edit-id').value = ev.id;
  document.getElementById('eval-input-titulo').value = ev.titulo || '';
  document.getElementById('eval-input-curso').value = ev.curso || 'TODOS';
  document.getElementById('eval-input-tipo').value = ev.tipo || 'Prueba Sumativa';
  document.getElementById('eval-input-fecha').value = ev.fecha || '';
  document.getElementById('eval-input-hora').value = ev.hora || '08:30';
  document.getElementById('eval-input-max-decimas').value = ev.max_decimas || 5;
  document.getElementById('eval-input-desc').value = ev.descripcion || '';

  SoundFX.tap();
}

async function handleSaveEvaluacion(e) {
  e.preventDefault();

  const id = document.getElementById('eval-edit-id').value;
  const titulo = document.getElementById('eval-input-titulo').value.trim();
  const curso = document.getElementById('eval-input-curso').value;
  const tipo = document.getElementById('eval-input-tipo').value;
  const fecha = document.getElementById('eval-input-fecha').value;
  const hora = document.getElementById('eval-input-hora').value.trim();
  const max_decimas = parseInt(document.getElementById('eval-input-max-decimas').value, 10) || 5;
  const descripcion = document.getElementById('eval-input-desc').value.trim();

  if (!titulo || !fecha) {
    showToast('Título y fecha son obligatorios', '⚠️');
    return;
  }

  const payload = { titulo, curso, tipo, fecha, hora, max_decimas, descripcion };
  const btnSubmit = document.getElementById('btn-save-eval-submit');
  if (btnSubmit) btnSubmit.disabled = true;

  try {
    const isEdit = !!id;
    const url = isEdit ? `/api/evaluaciones/${id}` : '/api/evaluaciones';
    const method = isEdit ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Error al guardar la evaluación');
    }

    SoundFX.pointsAwarded();
    showToast(isEdit ? '¡Evaluación actualizada!' : '¡Evaluación agendada exitosamente!', '📅');
    toggleNewEvaluacionForm(false);
    document.getElementById('eval-form-panel').style.display = 'none';
    loadDocenteEvaluaciones();
  } catch (err) {
    SoundFX.error();
    showToast(err.message || 'Error de conexión', '❌');
  } finally {
    if (btnSubmit) btnSubmit.disabled = false;
  }
}

async function deleteEvaluacion(id) {
  if (!confirm('¿Estás seguro de que deseas eliminar esta evaluación del calendario?')) return;

  try {
    const res = await fetch(`/api/evaluaciones/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error al eliminar');

    SoundFX.tap();
    showToast('Evaluación eliminada correctamente', '🗑️');
    loadDocenteEvaluaciones();
  } catch (err) {
    SoundFX.error();
    showToast(err.message || 'Error de conexión', '❌');
  }
}

// ========================================================
// FORMATO DE FECHA PARA ENTREGAS
// ========================================================
function formatDeliveryDateTime(isoString) {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}`;
  } catch (e) {
    return isoString;
  }
}

// ========================================================
// INSIGNIAS Y LOGROS DEL ESTUDIANTE (VISTA DOCENTE)
// ========================================================
function renderStudentBadgesTeacher(student) {
  const container = document.getElementById('card-student-badges-box');
  const listEl = document.getElementById('card-student-badges-list');
  const countEl = document.getElementById('card-badges-count');

  if (!container || !listEl) return;

  if (!student || !student.insignias || student.insignias.length === 0) {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'block';
  const unlockedCount = student.insignias_desbloqueadas !== undefined 
    ? student.insignias_desbloqueadas 
    : student.insignias.filter(b => b.desbloqueada).length;
  const totalCount = student.total_insignias || student.insignias.length;
  if (countEl) countEl.textContent = `${unlockedCount} / ${totalCount}`;

  listEl.innerHTML = '';
  student.insignias.forEach(b => {
    const pill = document.createElement('div');
    if (b.desbloqueada) {
      pill.className = 'mini-badge-pill';
      pill.style.cssText = `background: ${b.color_glow || 'rgba(245, 158, 11, 0.15)'}; color: ${b.color_txt || '#fde68a'}; border: 1px solid ${b.color_borde || 'rgba(245, 158, 11, 0.35)'}; cursor: default;`;
      pill.title = `${b.nombre}: ${b.descripcion} (${b.progreso_txt || 'Completado'})`;
      pill.innerHTML = `<span>${b.icono}</span> <span>${escapeHtml(b.nombre)}</span>`;
    } else {
      pill.className = 'mini-badge-pill';
      pill.style.cssText = 'background: rgba(30, 41, 59, 0.4); color: #64748b; border: 1px dashed rgba(148, 163, 184, 0.2); opacity: 0.65; cursor: default;';
      pill.title = `Bloqueado: ${b.nombre} - ${b.descripcion} (${b.progreso_txt || '0%'})`;
      pill.innerHTML = `<span style="filter: grayscale(1);">🔒</span> <span style="text-decoration: line-through; opacity: 0.7;">${escapeHtml(b.nombre)}</span>`;
    }
    listEl.appendChild(pill);
  });
}

// ========================================================
// CONTADOR DEL BUZÓN DE ENTREGAS
// ========================================================
async function updateBuzonPendingCounter() {
  const badge = document.getElementById('dock-entregas-badge');
  if (!badge) return;

  try {
    const res = await fetch('/api/docente/entregas/contador-pendientes');
    if (!res.ok) return;
    const data = await res.json();
    const count = data.pendientes || 0;
    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  } catch (e) {
    console.debug('Error al obtener contador de pendientes del buzón:', e);
  }
}

// ========================================================
// BUZÓN DE TAREAS Y ENTREGAS (DOCENTE)
// ========================================================
const BuzonDocenteState = {
  estado: 'pendiente',
  entregas: []
};

function openBuzonEntregasModal() {
  openModal('modal-buzon-entregas');
  loadDocenteEntregas();
}

function setDocenteEntregaEstadoFilter(estado) {
  BuzonDocenteState.estado = estado;
  
  const btnPend = document.getElementById('btn-filtro-pendientes');
  const btnRev = document.getElementById('btn-filtro-revisadas');
  const btnTodas = document.getElementById('btn-filtro-todas');

  if (btnPend) btnPend.classList.toggle('active', estado === 'pendiente');
  if (btnRev) btnRev.classList.toggle('active', estado === 'revisado');
  if (btnTodas) btnTodas.classList.toggle('active', estado === 'todos');

  loadDocenteEntregas();
}

async function loadDocenteEntregas() {
  const container = document.getElementById('buzon-docente-feed');
  if (!container) return;

  const cursoSelect = document.getElementById('buzon-filter-curso');
  const curso = cursoSelect ? cursoSelect.value : 'todos';
  const estado = BuzonDocenteState.estado;

  container.innerHTML = `
    <div style="text-align: center; padding: 30px; color: var(--text-muted);">
      <div style="font-size: 1.8rem; margin-bottom: 8px;">⏳</div>
      <div>Cargando entregas de los estudiantes...</div>
    </div>
  `;

  try {
    const res = await fetch(`/api/docente/entregas?curso=${encodeURIComponent(curso)}&estado=${encodeURIComponent(estado)}`);
    if (!res.ok) throw new Error('Error al cargar entregas');
    const entregas = await res.json();
    BuzonDocenteState.entregas = entregas;

    renderDocenteEntregasFeed(entregas);
    updateBuzonPendingCounter();
  } catch (err) {
    container.innerHTML = `
      <div style="text-align: center; padding: 30px; color: #ef4444;">
        <div style="font-size: 1.8rem; margin-bottom: 8px;">⚠️</div>
        <div>Error al cargar las entregas: ${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}

function renderDocenteEntregasFeed(entregas) {
  const container = document.getElementById('buzon-docente-feed');
  if (!container) return;

  if (!entregas || entregas.length === 0) {
    const estadoTxt = BuzonDocenteState.estado === 'pendiente' ? 'pendientes' : (BuzonDocenteState.estado === 'revisado' ? 'revisadas' : '');
    container.innerHTML = `
      <div style="text-align: center; padding: 40px 20px; background: rgba(15, 23, 42, 0.4); border-radius: var(--radius-lg); border: 1px dashed var(--border-glass);">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">📭</div>
        <div style="font-size: 0.95rem; font-weight: 700; color: #cbd5e1;">No hay entregas ${estadoTxt}</div>
        <p style="font-size: 0.78rem; color: var(--text-dim); margin-top: 4px; max-width: 360px; margin-left: auto; margin-right: auto;">
          Cuando los estudiantes suban fotos de sus cuadernos o archivos PDF desde su portal, aparecerán aquí para tu revisión y asignación de décimas.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  entregas.forEach(d => {
    const card = document.createElement('div');
    card.className = `delivery-card status-${d.estado}`;
    card.id = `delivery-card-${d.id}`;

    // Estudiante initials
    const nameParts = (d.estudiante_nombre || 'Estudiante').split(' ');
    const initials = nameParts.length >= 2 ? (nameParts[0][0] + nameParts[1][0]).toUpperCase() : nameParts[0].substring(0, 2).toUpperCase();

    // Fecha legible
    const fechaTxt = formatDeliveryDateTime(d.fecha_entrega);

    // Titulo asociado
    let asociacionHtml = '<span style="color: var(--text-muted);">Entrega general de clase</span>';
    if (d.material_titulo) {
      asociacionHtml = `<span>📚 Guía: <strong>${escapeHtml(d.material_titulo)}</strong></span>`;
    } else if (d.evaluacion_titulo) {
      asociacionHtml = `<span>📅 Evaluación: <strong>${escapeHtml(d.evaluacion_titulo)}</strong></span>`;
    }

    // Preview de archivo
    let previewHtml = '';
    if (d.tipo_archivo === 'imagen') {
      previewHtml = `
        <div class="delivery-preview-box">
          <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
            <img src="${d.archivo_url}" alt="Foto tarea" class="delivery-preview-thumb" onclick="openDocenteLightbox('${d.archivo_url}', '${escapeHtml(d.estudiante_nombre)} - ${escapeHtml(d.nombre_original)}')" title="Toca para ampliar foto">
            <div style="min-width: 0;">
              <div style="font-size: 0.82rem; font-weight: 700; color: #f1f5f9; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                📸 ${escapeHtml(d.nombre_original)}
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8;">
                Fotografía de cuaderno / evidencia
              </div>
            </div>
          </div>
          <div style="display: flex; gap: 6px; flex-shrink: 0;">
            <button type="button" class="qp-chip" onclick="openDocenteLightbox('${d.archivo_url}', '${escapeHtml(d.estudiante_nombre)} - ${escapeHtml(d.nombre_original)}')">
              🔍 Zoom
            </button>
            <a href="${d.archivo_url}" target="_blank" class="qp-chip" style="text-decoration: none;" title="Abrir original en pestaña nueva">
              ↗ Abrir
            </a>
          </div>
        </div>
      `;
    } else if (d.tipo_archivo === 'pdf') {
      previewHtml = `
        <div class="delivery-preview-box">
          <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
            <div style="font-size: 2rem;">📄</div>
            <div style="min-width: 0;">
              <div style="font-size: 0.82rem; font-weight: 700; color: #f1f5f9; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                ${escapeHtml(d.nombre_original)}
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8;">
                Documento PDF
              </div>
            </div>
          </div>
          <a href="${d.archivo_url}" target="_blank" class="qp-chip" style="text-decoration: none; flex-shrink: 0;">
            ↗ Ver PDF
          </a>
        </div>
      `;
    } else {
      previewHtml = `
        <div class="delivery-preview-box">
          <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
            <div style="font-size: 2rem;">📎</div>
            <div style="min-width: 0;">
              <div style="font-size: 0.82rem; font-weight: 700; color: #f1f5f9; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                ${escapeHtml(d.nombre_original)}
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8;">
                Archivo adjunto
              </div>
            </div>
          </div>
          <a href="${d.archivo_url}" download class="qp-chip" style="text-decoration: none; flex-shrink: 0;">
            ⬇ Descargar
          </a>
        </div>
      `;
    }

    // Comentario del alumno
    const studentCommentHtml = d.comentario_estudiante ? `
      <div class="delivery-student-comment">
        💬 "${escapeHtml(d.comentario_estudiante)}"
      </div>
    ` : '';

    // Sección de calificación / Feedback
    let feedbackGradeHtml = '';
    if (d.estado === 'revisado') {
      feedbackGradeHtml = `
        <div class="teacher-feedback-bubble">
          <div class="teacher-feedback-header">
            <span>👨‍🏫 Revisión Docente Realizada</span>
            <span style="color: #fbbf24;">+${d.puntos_otorgados || 0} Décimas</span>
          </div>
          <div style="font-size: 0.82rem; color: #e2e8f0; font-weight: 600; margin-top: 4px;">
            "${escapeHtml(d.retroalimentacion || 'Excelente trabajo.')}"
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 0.7rem; color: #94a3b8;">
            <span>Revisado el ${formatDeliveryDateTime(d.fecha_revision)}</span>
            <button type="button" class="btn btn-outline" style="padding: 3px 8px; font-size: 0.68rem;" onclick="toggleDocenteEditarCalificacion(${d.id})">
              ✏️ Modificar
            </button>
          </div>
        </div>

        <div id="panel-editar-calificacion-${d.id}" class="delivery-grade-panel" style="display: none; margin-top: 8px;">
          ${renderCalificarFormInnerHtml(d)}
        </div>
      `;
    } else {
      feedbackGradeHtml = `
        <div class="delivery-grade-panel">
          ${renderCalificarFormInnerHtml(d)}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="delivery-header">
        <div class="delivery-student-info">
          <div class="avatar-circle" style="width: 38px; height: 38px; font-size: 0.85rem;">
            ${initials}
          </div>
          <div>
            <div style="font-size: 0.88rem; font-weight: 800; color: #ffffff;">
              ${escapeHtml(d.estudiante_nombre)}
            </div>
            <div style="font-size: 0.72rem; color: var(--text-muted); display: flex; align-items: center; gap: 6px; margin-top: 2px;">
              <span class="tag-pill course" style="padding: 1px 6px; font-size: 0.65rem;">Curso ${escapeHtml(d.estudiante_curso)}</span>
              <span>RUT: ${escapeHtml(d.estudiante_rut)}</span>
            </div>
          </div>
        </div>

        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
          <span class="delivery-status-pill ${d.estado}">
            ${d.estado === 'pendiente' ? '⏳ Pendiente' : '✅ Revisado'}
          </span>
          <span style="font-size: 0.68rem; color: var(--text-dim);">
            ${fechaTxt}
          </span>
        </div>
      </div>

      <div style="font-size: 0.78rem; color: #93c5fd; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); padding: 6px 10px; border-radius: 6px;">
        ${asociacionHtml}
      </div>

      ${studentCommentHtml}

      ${previewHtml}

      ${feedbackGradeHtml}
    `;

    container.appendChild(card);
  });
}

function renderCalificarFormInnerHtml(d) {
  const currentPts = d.puntos_otorgados !== null ? d.puntos_otorgados : 1;
  const currentFb = d.retroalimentacion || '';

  return `
    <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.75rem; font-weight: 800; color: #a5b4fc; text-transform: uppercase;">
      <span>⭐ Calificar y Asignar Décimas</span>
      <span style="color: #fbbf24;">Premio al Esfuerzo</span>
    </div>

    <!-- Selector Rápido de Décimas -->
    <div style="display: flex; gap: 6px; flex-wrap: wrap;">
      <input type="hidden" id="grade-puntos-val-${d.id}" value="${currentPts}">
      ${[0, 1, 2, 3, 5].map(pts => `
        <button type="button" 
          class="qp-chip btn-grade-pill-${d.id} ${pts === currentPts ? 'active' : ''}" 
          onclick="selectDocenteGradePoints(${d.id}, ${pts}, this)"
          style="flex: 1; min-width: 44px; text-align: center; font-weight: 800;">
          +${pts}
        </button>
      `).join('')}
    </div>

    <!-- Comentario / Retroalimentación -->
    <textarea id="grade-feedback-${d.id}" class="form-input" rows="2" 
      placeholder="Escribe un comentario alentador (Ej: ¡Excelente resolución, pasos muy claros!)..." 
      style="resize: none; font-size: 0.8rem;">${escapeHtml(currentFb)}</textarea>

    <div style="display: flex; gap: 8px; justify-content: flex-end;">
      <button type="button" class="btn btn-primary" id="btn-submit-grade-${d.id}" onclick="submitCalificarEntrega(${d.id})" style="padding: 7px 16px; font-size: 0.8rem;">
        ⭐ Guardar Calificación
      </button>
    </div>
  `;
}

function selectDocenteGradePoints(entregaId, puntos, btn) {
  const hiddenInput = document.getElementById(`grade-puntos-val-${entregaId}`);
  if (hiddenInput) hiddenInput.value = puntos;

  const allPills = document.querySelectorAll(`.btn-grade-pill-${entregaId}`);
  allPills.forEach(p => p.classList.remove('active'));
  if (btn) btn.classList.add('active');

  SoundFX.tap();
}

function toggleDocenteEditarCalificacion(entregaId) {
  const panel = document.getElementById(`panel-editar-calificacion-${entregaId}`);
  if (panel) {
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  }
}

async function submitCalificarEntrega(entregaId) {
  const btn = document.getElementById(`btn-submit-grade-${entregaId}`);
  const hiddenInput = document.getElementById(`grade-puntos-val-${entregaId}`);
  const feedbackInput = document.getElementById(`grade-feedback-${entregaId}`);

  const puntos = parseInt(hiddenInput?.value || 1, 10);
  const retroalimentacion = feedbackInput?.value?.trim() || '';

  if (btn) btn.disabled = true;

  try {
    const res = await fetch(`/api/docente/entregas/${entregaId}/calificar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ puntos, retroalimentacion })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error al calificar la entrega');

    // Efecto de celebración
    SoundFX.pointsAwarded();
    if (btn) {
      const rect = btn.getBoundingClientRect();
      ConfettiFX.burst(rect.left + rect.width / 2, rect.top);
    }

    showToast(`¡Entrega calificada! +${puntos} décimas registradas`, '⭐');

    // Si el alumno calificado es el que está activo en pantalla, actualizar su score e insignias
    if (AppState.activeStudent && data.estudiante && AppState.activeStudent.id === data.estudiante.id) {
      AppState.activeStudent.puntaje_acumulado = data.estudiante.puntaje_acumulado;
      renderStudentScore(AppState.activeStudent.puntaje_acumulado);
      fetch(`/api/estudiantes/${AppState.activeStudent.id}`)
        .then(r => r.json())
        .then(refreshed => {
          if (refreshed.id) {
            AppState.activeStudent = refreshed;
            renderStudentBadgesTeacher(refreshed);
            renderStudentHistory(refreshed.historial || []);
          }
        }).catch(() => {});
    }

    // Actualizar contador y lista
    updateBuzonPendingCounter();
    loadDocenteEntregas();
  } catch (err) {
    SoundFX.error();
    showToast(err.message || 'Error al calificar', '❌');
    if (btn) btn.disabled = false;
  }
}

// Lightbox Docente
function openDocenteLightbox(imgSrc, caption) {
  const modal = document.getElementById('modal-docente-lightbox');
  const img = document.getElementById('docente-lightbox-img');
  const cap = document.getElementById('docente-lightbox-caption');

  if (!modal || !img) return;

  img.src = imgSrc;
  if (cap) cap.textContent = caption || '';
  modal.classList.add('open');
  SoundFX.tap();
}

function closeDocenteLightbox(event) {
  if (event && event.target && event.target.id === 'docente-lightbox-img') return;
  const modal = document.getElementById('modal-docente-lightbox');
  const img = document.getElementById('docente-lightbox-img');

  if (modal) modal.classList.remove('open');
  if (img) img.src = '';
}

