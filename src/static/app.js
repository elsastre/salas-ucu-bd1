const apiBase = window.location?.origin || '';
const qs = (sel) => document.querySelector(sel);
const qsa = (sel) => Array.from(document.querySelectorAll(sel));

const toastHostId = 'toast-container';
let toastTimer = null;

const ALLOWED_ESTADOS = ['activa', 'cancelada', 'sin_asistencia', 'finalizada'];
const CI_REGEX = /^\d{1,2}\.?\d{3}\.?\d{3}-?\d$/;
const NAME_REGEX = /[a-zA-ZÁÉÍÓÚÜÑáéíóúüñ]/;

const state = {
  edificios: [],
  turnos: [],
};

function requestSubmit(form) {
  if (!form) return;
  if (typeof form.requestSubmit === 'function') {
    form.requestSubmit();
  } else {
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  }
}

// Accepts boolean, numeric (1/0) or string ('1'/'0') admin flags and
// also treats docentes/posgrado as admins.
function computeIsAdmin(user) {
  if (!user) return false;
  if (typeof user.isAdmin === 'boolean') return user.isAdmin;

  const byFlag =
    user.es_admin === true || user.es_admin === 1 || user.es_admin === '1';
  const tipo = (user.tipo_participante || '').toString().toLowerCase();
  const byRole = ['docente', 'posgrado'].includes(tipo);

  return byFlag || byRole;
}

const sessionManager = {
  currentUser: null,
  save(user) {
    const enriched = { ...user, isAdmin: computeIsAdmin(user) };
    this.currentUser = enriched;
    window.currentUser = enriched;
    updateSessionUI();
  },
  clear() {
    this.currentUser = null;
    window.currentUser = null;
    updateSessionUI();
  },
  isAdmin() {
    return !!this.currentUser?.isAdmin;
  },
};

function requireLogin(msgEl) {
  if (!sessionManager.currentUser) {
    setAlert(msgEl, 'Debes iniciar sesión para usar esta sección', 'error');
    throw new Error('login-required');
  }
}

function requireAdmin(msgEl) {
  if (!sessionManager.isAdmin()) {
    setAlert(msgEl, 'Solo administradores pueden realizar esta acción', 'error');
    throw new Error('admin-required');
  }
}

function setAlert(el, message, type = '') {
  if (!el) return;
  el.textContent = message || '';
  el.className = `alert${type ? ` ${type}` : ''}`;
  if (type === 'error' && message) showToast(message, 'error');
}

function showToast(message, tone = 'info') {
  const host = qs(`#${toastHostId}`);
  if (!host || !message) return;
  const toast = document.createElement('div');
  toast.className = `toast ${tone}`;
  toast.textContent = message;
  host.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('visible'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

async function apiRequest(method, url, body, msgEl) {
  if (msgEl) setAlert(msgEl, 'Cargando...');
  try {
    const res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch (_) {
      payload = text;
    }
    if (!res.ok) {
      const detail = payload?.detail || payload?.message || null;
      const error = new Error(detail || `Error ${res.status}`);
      error.status = res.status;
      error.detail = detail;
      throw error;
    }
    if (msgEl) setAlert(msgEl, 'Listo', 'success');
    return payload;
  } catch (err) {
    if (msgEl) setAlert(msgEl, err.message, 'error');
    throw err;
  }
}

function parseCiList(value) {
  return (value || '')
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean);
}

function normalizeCi(ci) {
  const digits = (ci || '').replace(/\D/g, '');
  if (digits.length >= 7 && digits.length <= 8) return digits;
  return null;
}

function validateCi(value, msgEl) {
  if (!value) {
    setAlert(msgEl, 'La CI es obligatoria', 'error');
    return null;
  }
  const digits = normalizeCi(value);
  if (!digits || !(CI_REGEX.test(value) || /^\d{7,8}$/.test(value))) {
    setAlert(msgEl, 'Formato de CI inválido (usa 7 u 8 dígitos, con o sin puntos/guiones)', 'error');
    return null;
  }
  return digits;
}

function validateCiList(raw, msgEl) {
  const list = parseCiList(raw);
  const normalized = [];
  for (const ci of list) {
    const n = validateCi(ci, msgEl);
    if (!n) return null;
    normalized.push(n);
  }
  return normalized;
}

function validateName(value, field, msgEl) {
  const clean = (value || '').trim();
  if (clean.length < 2 || !NAME_REGEX.test(clean)) {
    setAlert(msgEl, `${field} debe tener al menos 2 caracteres con letras`, 'error');
    return null;
  }
  return clean;
}

function fillSelect(select, options, { includeAll = false, allLabel = 'Todos' } = {}) {
  if (!select) return;
  select.innerHTML = '';
  if (includeAll) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = allLabel;
    select.appendChild(opt);
  }
  options.forEach((o) => {
    const opt = document.createElement('option');
    if (typeof o === 'string') {
      opt.value = o;
      opt.textContent = o || '—';
    } else {
      opt.value = o.value;
      opt.textContent = o.label;
    }
    select.appendChild(opt);
  });
}

function tablePlaceholder(tbody, text = 'Sin datos') {
  tbody.innerHTML = `<tr><td colspan="10" class="table-placeholder">${text}</td></tr>`;
}

const navigation = (() => {
  function show(targetId) {
    const tab = qsa('.tab').find((t) => t.dataset.target === targetId);
    if (tab?.disabled) return;
    qsa('.panel').forEach((p) => p.classList.remove('visible'));
    qs(`#${targetId}`)?.classList.add('visible');
    qsa('.tab').forEach((t) => t.classList.toggle('active', t.dataset.target === targetId));
  }

  function init() {
    qsa('.tab').forEach((tab) =>
      tab.addEventListener('click', () => show(tab.dataset.target))
    );
  }

  return { init, show };
})();

const combos = {
  async loadEdificios() {
    const data = await apiRequest('GET', `${apiBase}/edificios`);
    state.edificios = data.map((d) => d.edificio);
    const opts = state.edificios.map((e) => ({ value: e, label: e }));
    fillSelect(qs('#salas-filtro-edificio'), opts, { includeAll: true });
    fillSelect(qs('#sala-edificio'), opts);
    fillSelect(qs('#res-edificio'), opts);
    fillSelect(qs('#disp-edificio'), opts);
    fillSelect(qs('#reservas-filtro-edificio'), opts, { includeAll: true });
    if (state.edificios.length) {
      ['#sala-edificio', '#res-edificio', '#disp-edificio'].forEach((sel) => {
        const el = qs(sel);
        if (el) el.value = state.edificios[0];
      });
    }
  },
  async loadTurnos() {
    const data = await apiRequest('GET', `${apiBase}/turnos`);
    state.turnos = data;
    fillSelect(qs('#res-turno'), data.map((t) => ({ value: t.id_turno, label: `${t.id_turno} · ${t.hora_inicio} - ${t.hora_fin}` })));
  },
  async loadSalasFor(edificio, select) {
    if (!edificio) {
      fillSelect(select, []);
      return;
    }
    const data = await apiRequest('GET', `${apiBase}/salas?edificio=${encodeURIComponent(edificio)}`);
    fillSelect(select, data.map((s) => ({ value: s.nombre_sala, label: `${s.nombre_sala} (${s.tipo_sala}, cap ${s.capacidad})` })));
  },
};

const salasUI = (() => {
  let editing = null;

  async function list() {
    const msg = qs('#salas-msg');
    try {
      requireLogin(msg);
    } catch (_) {
      return tablePlaceholder(qs('#salas-table'), 'Inicia sesión para ver salas');
    }
    const filtro = qs('#salas-filtro-edificio').value;
    const url = filtro ? `${apiBase}/salas?edificio=${encodeURIComponent(filtro)}` : `${apiBase}/salas`;
    const data = await apiRequest('GET', url, null, msg);
    renderTable(data || []);
  }

  function renderTable(items) {
    const tbody = qs('#salas-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin salas');
    tbody.innerHTML = '';
    items.forEach((s) => {
      const tr = document.createElement('tr');
      const actions = sessionManager.isAdmin()
        ? `<div class="table-actions">
            <button class="btn link" data-action="edit" data-edificio="${s.edificio}" data-nombre="${s.nombre_sala}">Editar</button>
            <button class="btn link" data-action="delete" data-edificio="${s.edificio}" data-nombre="${s.nombre_sala}">Eliminar</button>
          </div>`
        : '<span class="muted">Solo administradores</span>';
      const tipo = (s.tipo_sala || '').toString().toUpperCase();
      tr.innerHTML = `
        <td>${s.edificio}</td>
        <td>${s.nombre_sala}</td>
        <td class="numeric">${s.capacidad}</td>
        <td><span class="badge">${tipo}</span></td>
        <td>${actions}</td>`;
      tbody.appendChild(tr);
    });
  }

  function resetForm() {
    editing = null;
    qs('#salas-form').reset();
    qs('#sala-edificio').disabled = false;
    qs('#sala-nombre').readOnly = false;
    setAlert(qs('#sala-form-msg'), '');
  }

  async function submit(evt) {
    evt.preventDefault();
    const payload = {
      edificio: qs('#sala-edificio').value,
      nombre_sala: qs('#sala-nombre').value.trim(),
      capacidad: Number(qs('#sala-capacidad').value),
      tipo_sala: qs('#sala-tipo').value,
    };
    if (!payload.edificio || !payload.nombre_sala) return;

    const msg = qs('#sala-form-msg');
    setAlert(msg, '');
    try {
      requireAdmin(msg);
    } catch (_) {
      return;
    }
    const isEdit = Boolean(editing);
    const url = isEdit
      ? `${apiBase}/salas/${encodeURIComponent(editing.edificio)}/${encodeURIComponent(editing.nombre_sala)}`
      : `${apiBase}/salas`;
    const method = isEdit ? 'PUT' : 'POST';
    try {
      await apiRequest(
        method,
        url,
        isEdit
          ? { nombre_sala: payload.nombre_sala, capacidad: payload.capacidad, tipo_sala: payload.tipo_sala }
          : payload,
        msg,
      );
      setAlert(msg, isEdit ? 'Sala actualizada' : 'Sala creada', 'success');
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
    const msg = qs('#salas-msg');
    try {
      requireAdmin(msg);
    } catch (_) {
      return;
    }
    const { action, edificio, nombre } = btn.dataset;
    if (action === 'edit') {
      editing = { edificio, nombre_sala: nombre };
      qs('#sala-edificio').value = edificio;
      qs('#sala-nombre').value = nombre;
      qs('#sala-capacidad').value = btn.closest('tr').children[2].textContent;
      qs('#sala-tipo').value = btn.closest('tr').children[3].textContent.trim();
      qs('#sala-edificio').disabled = true;
      qs('#sala-nombre').readOnly = false;
    }
    if (action === 'delete') {
      if (!confirm(`¿Eliminar sala ${nombre} de ${edificio}?`)) return;
      try {
        await apiRequest('DELETE', `${apiBase}/salas/${encodeURIComponent(edificio)}/${encodeURIComponent(nombre)}`, null, qs('#salas-msg'));
        await list();
      } catch (_) {}
    }
  }

  function init() {
    qs('#salas-refresh').addEventListener('click', list);
    qs('#salas-filtro-edificio').addEventListener('change', list);
    qs('#salas-form').addEventListener('submit', submit);
    qs('#sala-reset').addEventListener('click', resetForm);
    qs('#salas-table').addEventListener('click', handleAction);
    list();
  }

  return { init, list, resetForm };
})();

const participantesUI = (() => {
  let editing = null;

  async function list() {
    const filtro = qs('#participantes-search').value.trim();
    const msg = qs('#participantes-msg');
    try {
      requireLogin(msg);
    } catch (_) {
      return tablePlaceholder(qs('#participantes-table'), 'Inicia sesión para ver participantes');
    }
    try {
      setAlert(msg, '');
      if (filtro) {
        const ci = validateCi(filtro, msg);
        if (!ci) return;
        const data = await apiRequest('GET', `${apiBase}/participantes/${encodeURIComponent(ci)}`, null, msg);
        render(Array.isArray(data) ? data : [data]);
      } else {
        const data = await apiRequest('GET', `${apiBase}/participantes`, null, msg);
        render(data || []);
      }
    } catch (_) {}
  }

  function render(items) {
    const tbody = qs('#participantes-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin participantes');
    tbody.innerHTML = '';
    items.forEach((p) => {
      const tr = document.createElement('tr');
      const actions = sessionManager.isAdmin()
        ? `<div class="table-actions">
            <button class="btn link" data-action="edit" data-ci="${p.ci}">Editar</button>
            <button class="btn link" data-action="delete" data-ci="${p.ci}">Eliminar</button>
          </div>`
        : '<span class="muted">Solo administradores</span>';
      const tipo = (p.tipo_participante || '—').toString().toUpperCase();
      tr.innerHTML = `
        <td>${p.ci}</td>
        <td>${p.apellido}, ${p.nombre}</td>
        <td><span class="badge neutral">${tipo}</span></td>
        <td>${p.email}</td>
        <td>${actions}</td>`;
      tbody.appendChild(tr);
    });
  }

  function resetForm() {
    editing = null;
    qs('#participantes-form').reset();
    qs('#part-ci').readOnly = false;
    qs('#part-ci').value = '';
    setAlert(qs('#participantes-form-msg'), '');
  }

  async function submit(evt) {
    evt.preventDefault();
    const msg = qs('#participantes-form-msg');
    setAlert(msg, '');
    try {
      requireAdmin(msg);
    } catch (_) {
      return;
    }
    const ciNorm = validateCi(qs('#part-ci').value.trim(), msg);
    const nombre = validateName(qs('#part-nombre').value, 'Nombre', msg);
    const apellido = validateName(qs('#part-apellido').value, 'Apellido', msg);
    const email = (qs('#part-email').value || '').trim();
    const tipo_participante = qs('#part-tipo').value;
    if (!ciNorm || !nombre || !apellido) return;
    if (!email.includes('@')) return setAlert(msg, 'Email inválido', 'error');

    const payload = { ci: ciNorm, nombre, apellido, email, tipo_participante };
    const isEdit = Boolean(editing);
    const url = isEdit ? `${apiBase}/participantes/${encodeURIComponent(editing)}` : `${apiBase}/participantes`;
    const method = isEdit ? 'PUT' : 'POST';
    try {
      await apiRequest(
        method,
        url,
        isEdit ? { nombre, apellido, email, tipo_participante } : payload,
        msg,
      );
      setAlert(msg, isEdit ? 'Participante actualizado' : 'Participante creado', 'success');
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
    const msg = qs('#participantes-msg');
    try {
      requireAdmin(msg);
    } catch (_) {
      return;
    }
    const ci = btn.dataset.ci;
    if (btn.dataset.action === 'edit') {
      const row = btn.closest('tr').children;
      qs('#part-ci').value = ci;
      qs('#part-nombre').value = row[1].textContent.split(', ')[1];
      qs('#part-apellido').value = row[1].textContent.split(', ')[0];
      qs('#part-tipo').value = row[2].textContent.trim();
      qs('#part-email').value = row[3].textContent;
      qs('#part-ci').readOnly = true;
      editing = ci;
    }
    if (btn.dataset.action === 'delete') {
      if (!confirm(`¿Eliminar participante ${ci}?`)) return;
      try {
        await apiRequest('DELETE', `${apiBase}/participantes/${encodeURIComponent(ci)}`, null, qs('#participantes-msg'));
        await list();
      } catch (_) {}
    }
  }

  function init() {
    qs('#participantes-refresh').addEventListener('click', list);
    qs('#participantes-form').addEventListener('submit', submit);
    qs('#participantes-table').addEventListener('click', handleAction);
    qs('#part-reset').addEventListener('click', resetForm);
    list();
  }

  return { init, list };
})();

const turnosUI = (() => {
  let editing = null;

  async function list() {
    const msg = qs('#turnos-msg');
    try {
      requireLogin(msg);
    } catch (_) {
      return tablePlaceholder(qs('#turnos-table'), 'Inicia sesión para ver turnos');
    }
    const data = await apiRequest('GET', `${apiBase}/turnos`, null, msg);
    render(data || []);
    await combos.loadTurnos();
  }

  function render(items) {
    const tbody = qs('#turnos-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin turnos');
    tbody.innerHTML = '';
    items.forEach((t) => {
      const tr = document.createElement('tr');
      const actions = sessionManager.isAdmin()
        ? `<div class="table-actions">
            <button class="btn link" data-action="edit" data-id="${t.id_turno}">Editar</button>
            <button class="btn link" data-action="delete" data-id="${t.id_turno}">Eliminar</button>
          </div>`
        : '<span class="muted">Solo administradores</span>';
      tr.innerHTML = `
        <td class="numeric">${t.id_turno}</td>
        <td>${t.hora_inicio}</td>
        <td>${t.hora_fin}</td>
        <td>${actions}</td>`;
      tbody.appendChild(tr);
    });
  }

  function resetForm() {
    editing = null;
    qs('#turnos-form').reset();
    qs('#turno-id').readOnly = false;
    setAlert(qs('#turnos-form-msg'), '');
  }

  async function submit(evt) {
    evt.preventDefault();
    const id = Number(qs('#turno-id').value);
    const hora_inicio = qs('#turno-inicio').value + ':00';
    const hora_fin = qs('#turno-fin').value + ':00';
    if (!qs('#turno-inicio').value || !qs('#turno-fin').value) return;
    const payload = { id_turno: id, hora_inicio, hora_fin };
    const isEdit = Boolean(editing);
    const url = isEdit ? `${apiBase}/turnos/${id}` : `${apiBase}/turnos`;
    const method = isEdit ? 'PUT' : 'POST';
    try {
      requireAdmin(qs('#turnos-form-msg'));
      await apiRequest(method, url, isEdit ? { hora_inicio, hora_fin } : payload, qs('#turnos-form-msg'));
      setAlert(qs('#turnos-form-msg'), isEdit ? 'Turno actualizado' : 'Turno creado', 'success');
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
    const msg = qs('#turnos-msg');
    try {
      requireAdmin(msg);
    } catch (_) {
      return;
    }
    const id = btn.dataset.id;
    if (btn.dataset.action === 'edit') {
      const row = btn.closest('tr').children;
      qs('#turno-id').value = row[0].textContent;
      qs('#turno-inicio').value = row[1].textContent.slice(0, 5);
      qs('#turno-fin').value = row[2].textContent.slice(0, 5);
      qs('#turno-id').readOnly = true;
      editing = id;
    }
    if (btn.dataset.action === 'delete') {
      if (!confirm(`¿Eliminar turno ${id}?`)) return;
      try {
        await apiRequest('DELETE', `${apiBase}/turnos/${id}`, null, qs('#turnos-msg'));
        await list();
      } catch (_) {}
    }
  }

  function init() {
    qs('#turnos-refresh').addEventListener('click', list);
    qs('#turnos-form').addEventListener('submit', submit);
    qs('#turnos-table').addEventListener('click', handleAction);
    qs('#turno-reset').addEventListener('click', resetForm);
    list();
  }

  return { init, list };
})();

const reservasUI = (() => {
  function normalizeEstado(est) {
    return ALLOWED_ESTADOS.includes(est) ? est : 'activa';
  }

  function turnoLabel(id) {
    const turno = state.turnos.find((t) => Number(t.id_turno) === Number(id));
    return turno ? `${turno.hora_inicio} - ${turno.hora_fin}` : `Turno ${id}`;
  }

  function estadoBadge(estado) {
    const normalized = (estado || '').toString().toLowerCase();
    const label = (estado || '').toString().toUpperCase();
    const tone = {
      activa: 'success',
      finalizada: 'neutral',
      sin_asistencia: 'warn',
      cancelada: 'danger',
    }[normalized] || 'neutral';
    return `<span class="badge ${tone}">${label}</span>`;
  }

  function notificarSanciones(resp) {
    if (Array.isArray(resp?.sanciones_creadas) && resp.sanciones_creadas.length > 0) {
      const msg = resp.sanciones_creadas
        .map((s) => `CI ${s.ci}, sanción del ${s.fecha_inicio} al ${s.fecha_fin}`)
        .join('\n');
      showToast(`Sanción aplicada:\n${msg}`, 'warning');
    }
  }

  async function list() {
    const msg = qs('#reservas-msg');
    try {
      requireLogin(msg);
    } catch (_) {
      tablePlaceholder(qs('#reservas-table'), 'Inicia sesión para ver reservas');
      const count = qs('#reservas-count');
      if (count) count.textContent = 'Mostrando 0 de 0 reservas.';
      return;
    }
    const fecha = qs('#reservas-filtro-fecha').value;
    const edificio = qs('#reservas-filtro-edificio').value;
    const estado = qs('#reservas-filtro-estado').value;
    const params = new URLSearchParams();
    if (fecha) params.append('fecha', fecha);
    if (edificio) params.append('edificio', edificio);
    if (!sessionManager.isAdmin() && sessionManager.currentUser?.ci) {
      params.append('ci', sessionManager.currentUser.ci);
    }
    const url = `${apiBase}/reservas${params.toString() ? `?${params.toString()}` : ''}`;
    const data = await apiRequest('GET', url, null, qs('#reservas-msg'));
    const rows = (data || []).filter((r) => !estado || r.estado === estado);
    render(rows, data?.length || 0);
  }

  function render(items, total = 0) {
    const tbody = qs('#reservas-table');
    const count = qs('#reservas-count');
    if (!items.length) {
      tablePlaceholder(tbody, 'Sin reservas');
      if (count) count.textContent = `Mostrando 0 de ${total || 0} reservas.`;
      return;
    }
    tbody.innerHTML = '';
    items.forEach((r) => {
      const participantes = r.participantes ? r.participantes.split(',') : [];
      const horaLabel = turnoLabel(r.id_turno);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="numeric">${r.id_reserva}</td>
        <td>${r.edificio}</td>
        <td>${r.nombre_sala}</td>
        <td>${r.fecha}</td>
        <td>${horaLabel}</td>
        <td>${estadoBadge(r.estado)}</td>
        <td class="wrap">${participantes.join(', ') || '—'}</td>
        <td>
          <div class="table-actions tight">
            <select data-reserva="${r.id_reserva}" class="estado-select">
              ${ALLOWED_ESTADOS
                .map((e) => {
                  const label = (e || '').toString().toUpperCase();
                  return `<option value="${e}" ${e === r.estado ? 'selected' : ''}>${label}</option>`;
                })
                .join('')}
            </select>
            <button class="btn link" data-action="estado" data-id="${r.id_reserva}">GUARDAR ESTADO</button>
          </div>
        </td>`;
      tbody.appendChild(tr);
    });

    if (count) count.textContent = `Mostrando ${items.length} de ${total || items.length} reservas.`;
  }

  async function submit(evt) {
    evt.preventDefault();
    const msg = qs('#reservas-form-msg');
    setAlert(msg, '');
    try {
      requireLogin(msg);
    } catch (_) {
      return;
    }
    const payload = {
      fecha: qs('#res-fecha').value,
      edificio: qs('#res-edificio').value,
      nombre_sala: qs('#res-sala').value,
      id_turno: Number(qs('#res-turno').value),
      participantes: validateCiList(qs('#res-participantes').value, msg),
      estado: normalizeEstado(qs('#res-estado').value),
    };
    if (!payload.fecha || !payload.edificio || !payload.nombre_sala || !payload.id_turno || !payload.participantes) {
      return;
    }
    try {
      await apiRequest('POST', `${apiBase}/reservas`, payload, msg);
      setAlert(msg, 'Reserva creada', 'success');
      await list();
      qs('#reservas-form').reset();
    } catch (_) {}
  }

  async function updateEstado(evt) {
    const btn = evt.target.closest('button[data-action="estado"]');
    if (!btn) return;
    try {
      requireLogin(qs('#reservas-msg'));
    } catch (_) {
      return;
    }
    const id = btn.dataset.id;
    const select = btn.closest('tr').querySelector('.estado-select');
    const estado = select.value;
    try {
      const resp = await apiRequest('PATCH', `${apiBase}/reservas/${id}`, { estado }, qs('#reservas-msg'));
      notificarSanciones(resp);
      await list();
    } catch (_) {}
  }

  async function registrarAsistencia(evt) {
    evt.preventDefault();
    const id = qs('#asis-id').value;
    const msg = qs('#asistencia-msg');
    setAlert(msg, '');
    try {
      requireLogin(msg);
    } catch (_) {
      return;
    }
    const presentes = validateCiList(qs('#asis-presentes').value, msg) || [];
    if (!id) return;
    try {
      const resp = await apiRequest(
        'POST',
        `${apiBase}/reservas/${id}/asistencia`,
        { presentes, sancionar_ausentes: qs('#asis-sancionar').checked },
        msg,
      );
      setAlert(msg, 'Asistencia registrada', 'success');
      notificarSanciones(resp);
      await list();
    } catch (_) {}
  }

  function init() {
    qs('#reservas-refresh').addEventListener('click', list);
    qs('#reservas-ver-todas').addEventListener('click', (e) => {
      e.preventDefault();
      qs('#reservas-filtro-fecha').value = '';
      qs('#reservas-filtro-edificio').value = '';
      qs('#reservas-filtro-estado').value = '';
      list();
    });
    qs('#reservas-form').addEventListener('submit', submit);
    qs('#reservas-table').addEventListener('click', updateEstado);
    qs('#asistencia-form').addEventListener('submit', registrarAsistencia);
    qs('#res-edificio').addEventListener('change', (e) => combos.loadSalasFor(e.target.value, qs('#res-sala')));
    qs('#reservar-como-yo').addEventListener('click', () => {
      const msg = qs('#reservas-form-msg');
      try {
        requireLogin(msg);
      } catch (_) {
        return;
      }
      const field = qs('#res-participantes');
      const ci = sessionManager.currentUser?.ci;
      if (!ci) return;
      const existing = parseCiList(field.value);
      if (!existing.includes(ci)) existing.push(ci);
      field.value = existing.join(', ');
      setAlert(msg, 'Se añadió tu CI automáticamente', 'success');
    });
    list();
  }

  return { init, list };
})();

const disponibilidadUI = (() => {
  async function consultar(evt) {
    evt.preventDefault();
    try {
      requireLogin(qs('#disponibilidad-msg'));
    } catch (_) {
      return;
    }
    const fecha = qs('#disp-fecha').value;
    const edificio = qs('#disp-edificio').value;
    const sala = qs('#disp-sala').value;
    if (!fecha || !edificio || !sala) return;
    const url = `${apiBase}/disponibilidad?fecha=${encodeURIComponent(fecha)}&edificio=${encodeURIComponent(edificio)}&nombre_sala=${encodeURIComponent(sala)}`;
    const data = await apiRequest('GET', url, null, qs('#disponibilidad-msg'));
    render(data || [], { fecha, edificio, sala });
  }

  function render(items, meta) {
    const tbody = qs('#disponibilidad-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin turnos para mostrar');
    tbody.innerHTML = '';
    items.forEach((t) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${t.id_turno}</td>
        <td>${t.hora_inicio} - ${t.hora_fin}</td>
        <td>${t.reservado ? `Reservado (${t.estado_reserva || '—'})` : 'Libre'}</td>
        <td>${
          t.reservado
            ? ''
            : `<button class="btn link" data-action="reservar" data-turno="${t.id_turno}" data-fecha="${meta.fecha}" data-edificio="${meta.edificio}" data-sala="${meta.sala}">Reservar</button>`
        }</td>`;
      tbody.appendChild(tr);
    });
  }

  function handleAction(evt) {
    const btn = evt.target.closest('button[data-action="reservar"]');
    if (!btn) return;
    qs('#res-fecha').value = btn.dataset.fecha;
    qs('#res-edificio').value = btn.dataset.edificio;
    combos.loadSalasFor(btn.dataset.edificio, qs('#res-sala')).then(() => {
      qs('#res-sala').value = btn.dataset.sala;
    });
    qs('#res-turno').value = btn.dataset.turno;
    setAlert(qs('#reservas-form-msg'), 'Turno precargado desde disponibilidad', 'success');
    document.querySelector('[data-target="reservas-section"]').click();
  }

  function init() {
    qs('#disponibilidad-form').addEventListener('submit', consultar);
    qs('#disponibilidad-table').addEventListener('click', handleAction);
    qs('#disp-edificio').addEventListener('change', (e) => combos.loadSalasFor(e.target.value, qs('#disp-sala')));
  }

  return { init };
})();

const sancionesUI = (() => {
  let editing = null;

  async function list() {
    const ci = qs('#sanciones-filtro-ci').value.trim();
    const msg = qs('#sanciones-msg');
    try {
      requireAdmin(msg);
    } catch (_) {
      return tablePlaceholder(qs('#sanciones-table'), 'Solo administradores');
    }
    setAlert(msg, '');
    let params = '';
    if (ci) {
      const norm = validateCi(ci, msg);
      if (!norm) return;
      params = `?ci=${encodeURIComponent(norm)}`;
    }
    const data = await apiRequest('GET', `${apiBase}/sanciones${params}`, null, msg);
    render(data || []);
  }

  function render(items) {
    const tbody = qs('#sanciones-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin sanciones');
    tbody.innerHTML = '';
    items.forEach((s) => {
      const ciRaw = s.ci_sancionado || s.ci_participante || s.ci || s.sancionado?.ci || '';
      const ci = normalizeCi(ciRaw) || ciRaw;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${ci}</td>
        <td>${s.fecha_inicio}</td>
        <td>${s.fecha_fin}</td>
        <td>
          <div class="table-actions">
            <button class="btn link" data-action="edit" data-ci="${ci}" data-inicio="${s.fecha_inicio}" data-fin="${s.fecha_fin}">Editar</button>
            <button class="btn link" data-action="delete" data-ci="${ci}" data-inicio="${s.fecha_inicio}">Eliminar</button>
          </div>
        </td>`;
      tbody.appendChild(tr);
    });
  }

  function resetForm() {
    editing = null;
    qs('#sanciones-form').reset();
    qs('#sancion-ci').readOnly = false;
    qs('#sancion-inicio').readOnly = false;
    setAlert(qs('#sanciones-form-msg'), '');
  }

  async function submit(evt) {
    evt.preventDefault();
    const ci = qs('#sancion-ci').value.trim();
    const fecha_inicio = qs('#sancion-inicio').value;
    const fecha_fin = qs('#sancion-fin').value;
    const msg = qs('#sanciones-form-msg');
    setAlert(msg, '');
    try {
      requireAdmin(msg);
    } catch (_) {
      return;
    }
    const normCi = validateCi(ci, msg);
    if (!normCi || !fecha_inicio || !fecha_fin) return;
    try {
      if (editing) {
        await apiRequest('PUT', `${apiBase}/sanciones/${encodeURIComponent(normCi)}/${fecha_inicio}`, { fecha_fin }, msg);
        setAlert(msg, 'Sanción actualizada', 'success');
      } else {
        await apiRequest('POST', `${apiBase}/sanciones`, { ci_participante: normCi, fecha_inicio, fecha_fin }, msg);
        setAlert(msg, 'Sanción creada', 'success');
      }
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
    const msg = qs('#sanciones-msg');
    try {
      requireAdmin(msg);
    } catch (_) {
      return;
    }
    const ci = btn.dataset.ci;
    const inicio = btn.dataset.inicio;
    if (btn.dataset.action === 'edit') {
      editing = { ci, inicio };
      qs('#sancion-ci').value = ci;
      qs('#sancion-inicio').value = inicio;
      qs('#sancion-fin').value = btn.dataset.fin;
      qs('#sancion-ci').readOnly = true;
      qs('#sancion-inicio').readOnly = true;
    }
    if (btn.dataset.action === 'delete') {
      if (!confirm('¿Eliminar sanción?')) return;
      const normCi = normalizeCi(ci);
      if (!normCi) {
        setAlert(msg, 'Formato de CI inválido', 'error');
        return;
      }
      try {
        await apiRequest('DELETE', `${apiBase}/sanciones/${encodeURIComponent(normCi)}/${inicio}`, null, qs('#sanciones-msg'));
        await list();
      } catch (_) {}
    }
  }

  function init() {
    qs('#sanciones-refresh').addEventListener('click', list);
    qs('#sanciones-form').addEventListener('submit', submit);
    qs('#sanciones-table').addEventListener('click', handleAction);
    qs('#sancion-reset').addEventListener('click', resetForm);
    list();
  }

  return { init };
})();

const reportesUI = (() => {
  const loaders = [];

  function renderTable(tbody, data, keys) {
    if (!data || !data.length) return tablePlaceholder(tbody, 'Sin datos');
    tbody.innerHTML = '';
    data.forEach((row) => {
      const tr = document.createElement('tr');
      tr.innerHTML = keys.map((k) => `<td>${row[k]}</td>`).join('');
      tbody.appendChild(tr);
    });
  }

  async function fetchReport(url, msgEl, adminOnly = false) {
    try {
      requireLogin(msgEl);
      if (adminOnly) requireAdmin(msgEl);
    } catch (_) {
      return null;
    }
    return apiRequest('GET', url, null, msgEl);
  }

  function bindReport(formSelector, buildUrl, tableSelector, columns, msgSelector, opts = {}) {
    const form = qs(formSelector);
    const table = qs(tableSelector);
    const msg = qs(msgSelector);
    const handler = async (evt) => {
      if (evt) evt.preventDefault();
      const url = buildUrl();
      try {
        const data = await fetchReport(url, msg, opts.adminOnly);
        if (!data) return;
        if (opts.render) {
          opts.render(table, data);
        } else {
          renderTable(table, data, columns);
        }
      } catch (err) {
        setAlert(msg, err.message, 'error');
      }
    };
    form?.addEventListener('submit', handler);
    loaders.push(handler);
    return handler;
  }

  function renderEfectividad(tbody, data) {
    if (!data) return tablePlaceholder(tbody, 'Sin datos');
    const rows = [
      { estado: 'finalizada', total: data.total_finalizadas, porcentaje: `${data.porcentaje_finalizadas}%` },
      { estado: 'cancelada', total: data.total_canceladas, porcentaje: `${data.porcentaje_canceladas}%` },
      { estado: 'sin_asistencia', total: data.total_sin_asistencia, porcentaje: `${data.porcentaje_sin_asistencia}%` },
    ];
    renderTable(tbody, rows, ['estado', 'total', 'porcentaje']);
  }

  function init() {
    bindReport(
      '#rep-salas-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-salas-desde').value) params.append('desde', qs('#rep-salas-desde').value);
        if (qs('#rep-salas-hasta').value) params.append('hasta', qs('#rep-salas-hasta').value);
        params.append('limit', qs('#rep-salas-limit').value || 10);
        return `${apiBase}/reportes/salas-mas-usadas?${params.toString()}`;
      },
      '#reporte-salas',
      ['edificio', 'nombre_sala', 'total_reservas'],
      '#rep-salas-msg',
    );

    bindReport(
      '#rep-turnos-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-turnos-desde').value) params.append('desde', qs('#rep-turnos-desde').value);
        if (qs('#rep-turnos-hasta').value) params.append('hasta', qs('#rep-turnos-hasta').value);
        params.append('limit', qs('#rep-turnos-limit').value || 10);
        return `${apiBase}/reportes/turnos-mas-demandados?${params.toString()}`;
      },
      '#reporte-turnos',
      ['id_turno', 'hora_inicio', 'hora_fin', 'total_reservas'],
      '#rep-turnos-msg',
    );

    bindReport(
      '#rep-promedio-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-promedio-desde').value) params.append('desde', qs('#rep-promedio-desde').value);
        if (qs('#rep-promedio-hasta').value) params.append('hasta', qs('#rep-promedio-hasta').value);
        return `${apiBase}/reportes/promedio-participantes-por-sala?${params.toString()}`;
      },
      '#reporte-promedio',
      ['edificio', 'nombre_sala', 'promedio_participantes'],
      '#rep-promedio-msg',
    );

    bindReport(
      '#rep-carrera-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-carrera-desde').value) params.append('desde', qs('#rep-carrera-desde').value);
        if (qs('#rep-carrera-hasta').value) params.append('hasta', qs('#rep-carrera-hasta').value);
        return `${apiBase}/reportes/reservas-por-carrera-facultad?${params.toString()}`;
      },
      '#reporte-carrera',
      ['facultad', 'nombre_programa', 'total_reservas'],
      '#rep-carrera-msg',
    );

    bindReport(
      '#rep-ocupacion-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-ocupacion-desde').value) params.append('desde', qs('#rep-ocupacion-desde').value);
        if (qs('#rep-ocupacion-hasta').value) params.append('hasta', qs('#rep-ocupacion-hasta').value);
        return `${apiBase}/reportes/ocupacion-por-edificio?${params.toString()}`;
      },
      '#reporte-ocupacion',
      ['edificio', 'total_reservas', 'porcentaje_sobre_total'],
      '#rep-ocupacion-msg',
    );

    bindReport(
      '#rep-rol-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-rol-desde').value) params.append('desde', qs('#rep-rol-desde').value);
        if (qs('#rep-rol-hasta').value) params.append('hasta', qs('#rep-rol-hasta').value);
        return `${apiBase}/reportes/reservas-y-asistencias-por-rol?${params.toString()}`;
      },
      '#reporte-rol',
      ['rol', 'tipo_programa', 'total_reservas', 'con_asistencia', 'sin_asistencia', 'canceladas'],
      '#rep-rol-msg',
    );

    bindReport(
      '#rep-sanciones-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-sanciones-desde').value) params.append('desde', qs('#rep-sanciones-desde').value);
        if (qs('#rep-sanciones-hasta').value) params.append('hasta', qs('#rep-sanciones-hasta').value);
        return `${apiBase}/reportes/sanciones-por-rol?${params.toString()}`;
      },
      '#reporte-sanciones',
      ['rol', 'tipo_programa', 'total_sanciones'],
      '#rep-sanciones-msg',
      { adminOnly: true },
    );

    bindReport(
      '#rep-efectividad-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-efectividad-desde').value) params.append('desde', qs('#rep-efectividad-desde').value);
        if (qs('#rep-efectividad-hasta').value) params.append('hasta', qs('#rep-efectividad-hasta').value);
        return `${apiBase}/reportes/efectividad-reservas?${params.toString()}`;
      },
      '#reporte-efectividad',
      ['estado', 'total', 'porcentaje'],
      '#rep-efectividad-msg',
      { render: renderEfectividad },
    );

    bindReport(
      '#rep-uso-rol-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-uso-rol-desde').value) params.append('desde', qs('#rep-uso-rol-desde').value);
        if (qs('#rep-uso-rol-hasta').value) params.append('hasta', qs('#rep-uso-rol-hasta').value);
        return `${apiBase}/reportes/uso-por-rol?${params.toString()}`;
      },
      '#reporte-uso-rol',
      ['rol', 'tipo_programa', 'total_reservas'],
      '#rep-uso-rol-msg',
    );

    bindReport(
      '#rep-top-participantes-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-top-desde').value) params.append('desde', qs('#rep-top-desde').value);
        if (qs('#rep-top-hasta').value) params.append('hasta', qs('#rep-top-hasta').value);
        params.append('limit', qs('#rep-top-limit').value || 5);
        return `${apiBase}/reportes/top-participantes?${params.toString()}`;
      },
      '#reporte-top',
      ['ci', 'nombre', 'apellido', 'total_reservas'],
      '#rep-top-msg',
    );

    bindReport(
      '#rep-no-show-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-no-show-desde').value) params.append('desde', qs('#rep-no-show-desde').value);
        if (qs('#rep-no-show-hasta').value) params.append('hasta', qs('#rep-no-show-hasta').value);
        params.append('limit', qs('#rep-no-show-limit').value || 5);
        return `${apiBase}/reportes/salas-no-show?${params.toString()}`;
      },
      '#reporte-no-show',
      ['edificio', 'nombre_sala', 'total_sin_asistencia'],
      '#rep-no-show-msg',
    );

    bindReport(
      '#rep-distribucion-form',
      () => {
        const params = new URLSearchParams();
        if (qs('#rep-distribucion-desde').value) params.append('desde', qs('#rep-distribucion-desde').value);
        if (qs('#rep-distribucion-hasta').value) params.append('hasta', qs('#rep-distribucion-hasta').value);
        return `${apiBase}/reportes/distribucion-semana-turno?${params.toString()}`;
      },
      '#reporte-distribucion',
      ['dia_semana', 'id_turno', 'total_reservas'],
      '#rep-distribucion-msg',
    );

    loaders.forEach((fn) => fn());
  }

  return { init, reload: () => loaders.forEach((fn) => fn()) };
})();

function setTodayDefaults() {
  const today = new Date().toISOString().split('T')[0];
  ['#res-fecha', '#disp-fecha'].forEach((sel) => {
    const el = qs(sel);
    if (el && !el.value) el.value = today;
  });
}

function updateSessionUI() {
  const shell = qs('#app-shell') || qs('#mainTabs');
  const loginCard = qs('#loginCard') || qs('#login-card');
  const sessionCard = qs('#session-card');
  const info = qs('#session-info');
  const tags = qs('#session-tags');
  const loginMsg = qs('#loginMessage') || qs('#login-msg');
  const loginInput = document.getElementById('ciLogin') || qs('#login-ci');
  const hasUser = !!sessionManager.currentUser;
  const isAdmin = sessionManager.isAdmin();
  document.body.classList.toggle('has-session', hasUser);
  document.body.classList.toggle('is-admin', isAdmin);
  if (shell) shell.style.display = hasUser ? 'block' : 'none';
  if (loginCard) loginCard.style.display = hasUser ? 'none' : 'block';
  if (sessionCard) sessionCard.style.display = hasUser ? 'flex' : 'none';
  if (!hasUser && loginInput) loginInput.focus();
  if (!hasUser && loginMsg) setAlert(loginMsg, '');
  if (info) {
    if (hasUser) {
      const u = sessionManager.currentUser;
      info.innerHTML = `
        <div class="session-name">${u.nombre} ${u.apellido}</div>
        <div class="session-meta">CI ${u.ci}</div>
      `;
    } else {
      info.textContent = 'Sin sesión activa.';
    }
  }
  if (tags) {
    tags.innerHTML = '';
    if (hasUser) {
      const u = sessionManager.currentUser;
      const role = document.createElement('span');
      role.className = 'badge role';
      role.textContent = (u.tipo_participante || '').toString().toUpperCase();
      tags.appendChild(role);
      if (isAdmin) {
        const admin = document.createElement('span');
        admin.className = 'badge role admin';
        admin.textContent = 'ADMIN';
        tags.appendChild(admin);
      }
    }
  }
  applyRoleGuards();
}

function applyRoleGuards() {
  const isAdmin = sessionManager.isAdmin();
  qsa('[data-role="admin"]').forEach((el) => {
    if (el.tagName === 'BUTTON') {
      el.disabled = !isAdmin;
      el.classList.toggle('tab-disabled', !isAdmin);
      el.style.display = isAdmin ? '' : 'none';
    } else {
      el.classList.toggle('locked', !isAdmin);
    }
  });

  qsa('.panel[data-role="admin"]').forEach((panel) => {
    panel.classList.toggle('restricted', !isAdmin);
  });

  const activeTab = qs('.tab.active');
  const visibleTabs = qsa('.tab').filter((t) => !t.disabled && t.style.display !== 'none');
  if (!visibleTabs.length) return;
  if (!activeTab || activeTab.disabled || activeTab.style.display === 'none') {
    navigation.show(visibleTabs[0].dataset.target);
  }
}

let appInitialized = false;

async function startApp() {
  if (!sessionManager.currentUser) return;
  if (!appInitialized) {
    navigation.init();
    setTodayDefaults();
    await combos.loadEdificios();
    await combos.loadTurnos();
    await combos.loadSalasFor(qs('#res-edificio').value, qs('#res-sala'));
    await combos.loadSalasFor(qs('#disp-edificio').value, qs('#disp-sala'));
    salasUI.init();
    participantesUI.init();
    turnosUI.init();
    reservasUI.init();
    disponibilidadUI.init();
    sancionesUI.init();
    reportesUI.init();
    qs('#reload-data').addEventListener('click', async (e) => {
      e.preventDefault();
      await combos.loadEdificios();
      await combos.loadTurnos();
      await reservasUI.list();
      await salasUI.list();
    });
    appInitialized = true;
  } else {
    await combos.loadEdificios();
    await combos.loadTurnos();
    await combos.loadSalasFor(qs('#res-edificio').value, qs('#res-sala'));
    await combos.loadSalasFor(qs('#disp-edificio').value, qs('#disp-sala'));
    await salasUI.list();
    await participantesUI.list();
    await turnosUI.list();
    await reservasUI.list();
    reportesUI.reload();
    qs('#sanciones-refresh')?.click();
  }
  updateSessionUI();
}

async function handleLogin(evt) {
  evt.preventDefault();
  const msg = qs('#loginMessage') || qs('#login-msg');
  const submitBtn = qs('#loginSubmit') || qs('#login-submit');
  const ciInput = qs('#ciLogin') || qs('#login-ci');
  setAlert(msg, '');
  const normalizedCi = normalizeCi(ciInput?.value);
  if (!normalizedCi) {
    setAlert(msg, 'La CI debe tener 7 u 8 dígitos (con o sin puntos/guiones).', 'error');
    return;
  }
  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Ingresando...';
    }
    const user = await apiRequest('POST', `${apiBase}/auth/login`, { ci: normalizedCi }, msg);
    sessionManager.save(user);
    setAlert(msg, 'Sesión iniciada correctamente', 'success');
    const loginCard = qs('#loginCard') || qs('#login-card');
    const shell = qs('#app-shell') || qs('#mainTabs');
    if (loginCard) loginCard.style.display = 'none';
    if (shell) shell.style.display = 'block';
    await startApp();
  } catch (err) {
    if (err?.status === 404) {
      setAlert(msg, 'No se encontró un participante con esa CI', 'error');
    } else if (err?.status === 422) {
      setAlert(msg, 'Formato de CI inválido. Revisa los dígitos ingresados.', 'error');
    } else {
      setAlert(msg, 'Ocurrió un error al iniciar sesión. Intenta más tarde.', 'error');
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Entrar';
    }
  }
}

let bootstrapStarted = false;

function bootstrap() {
  if (bootstrapStarted) return;
  bootstrapStarted = true;
  sessionManager.clear();
  updateSessionUI();
  const loginForm = document.getElementById('frmLogin') || qs('#login-form');
  const loginInput = document.getElementById('ciLogin') || qs('#login-ci');
  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }
  loginInput?.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      requestSubmit(loginForm);
    }
  });
  qs('#logout-btn').addEventListener('click', () => {
    sessionManager.clear();
    updateSessionUI();
  });
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrap);
} else {
  bootstrap();
}
