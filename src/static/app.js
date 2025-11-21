const apiBase = '';
const qs = (sel) => document.querySelector(sel);
const qsa = (sel) => Array.from(document.querySelectorAll(sel));

const ALLOWED_ESTADOS = ['activa', 'cancelada', 'sin_asistencia', 'finalizada'];

const state = {
  edificios: [],
  turnos: [],
};

function setAlert(el, message, type = '') {
  if (!el) return;
  el.textContent = message || '';
  el.className = `alert${type ? ` ${type}` : ''}`;
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
    let payload = text ? JSON.parse(text) : null;
    if (!res.ok) {
      const detail = payload?.detail ? `: ${payload.detail}` : '';
      throw new Error(`Error ${res.status}${detail}`);
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
    qsa('.panel').forEach((p) => p.classList.remove('visible'));
    qs(`#${targetId}`)?.classList.add('visible');
    qsa('.tab').forEach((t) => t.classList.toggle('active', t.dataset.target === targetId));
  }

  function init() {
    qsa('.tab').forEach((tab) =>
      tab.addEventListener('click', () => show(tab.dataset.target))
    );
  }

  return { init };
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
    const filtro = qs('#salas-filtro-edificio').value;
    const url = filtro ? `${apiBase}/salas?edificio=${encodeURIComponent(filtro)}` : `${apiBase}/salas`;
    const data = await apiRequest('GET', url, null, qs('#salas-msg'));
    renderTable(data || []);
  }

  function renderTable(items) {
    const tbody = qs('#salas-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin salas');
    tbody.innerHTML = '';
    items.forEach((s) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${s.edificio}</td>
        <td>${s.nombre_sala}</td>
        <td>${s.capacidad}</td>
        <td><span class="badge">${s.tipo_sala}</span></td>
        <td>
          <div class="table-actions">
            <button class="btn link" data-action="edit" data-edificio="${s.edificio}" data-nombre="${s.nombre_sala}">Editar</button>
            <button class="btn link" data-action="delete" data-edificio="${s.edificio}" data-nombre="${s.nombre_sala}">Eliminar</button>
          </div>
        </td>`;
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
    const isEdit = Boolean(editing);
    const url = isEdit
      ? `${apiBase}/salas/${encodeURIComponent(editing.edificio)}/${encodeURIComponent(editing.nombre_sala)}`
      : `${apiBase}/salas`;
    const method = isEdit ? 'PUT' : 'POST';
    try {
      await apiRequest(method, url, isEdit ? { capacidad: payload.capacidad, tipo_sala: payload.tipo_sala } : payload, msg);
      setAlert(msg, isEdit ? 'Sala actualizada' : 'Sala creada', 'success');
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
    const { action, edificio, nombre } = btn.dataset;
    if (action === 'edit') {
      editing = { edificio, nombre_sala: nombre };
      qs('#sala-edificio').value = edificio;
      qs('#sala-nombre').value = nombre;
      qs('#sala-capacidad').value = btn.closest('tr').children[2].textContent;
      qs('#sala-tipo').value = btn.closest('tr').children[3].textContent.trim();
      qs('#sala-edificio').disabled = true;
      qs('#sala-nombre').readOnly = true;
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
      if (filtro) {
        const data = await apiRequest('GET', `${apiBase}/participantes/${encodeURIComponent(filtro)}`, null, msg);
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
      tr.innerHTML = `
        <td>${p.ci}</td>
        <td>${p.apellido}, ${p.nombre}</td>
        <td>${p.email}</td>
        <td>
          <div class="table-actions">
            <button class="btn link" data-action="edit" data-ci="${p.ci}">Editar</button>
            <button class="btn link" data-action="delete" data-ci="${p.ci}">Eliminar</button>
          </div>
        </td>`;
      tbody.appendChild(tr);
    });
  }

  function resetForm() {
    editing = null;
    qs('#participantes-form').reset();
    qs('#part-ci').readOnly = false;
    setAlert(qs('#participantes-form-msg'), '');
  }

  async function submit(evt) {
    evt.preventDefault();
    const payload = {
      ci: qs('#part-ci').value.trim(),
      nombre: qs('#part-nombre').value.trim(),
      apellido: qs('#part-apellido').value.trim(),
      email: qs('#part-email').value.trim(),
    };
    if (!payload.ci || !payload.email.includes('@')) {
      return setAlert(qs('#participantes-form-msg'), 'Completa CI y email válido', 'error');
    }
    const isEdit = Boolean(editing);
    const url = isEdit ? `${apiBase}/participantes/${encodeURIComponent(payload.ci)}` : `${apiBase}/participantes`;
    const method = isEdit ? 'PUT' : 'POST';
    try {
      await apiRequest(method, url, isEdit ? { nombre: payload.nombre, apellido: payload.apellido, email: payload.email } : payload, qs('#participantes-form-msg'));
      setAlert(qs('#participantes-form-msg'), isEdit ? 'Participante actualizado' : 'Participante creado', 'success');
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
    const ci = btn.dataset.ci;
    if (btn.dataset.action === 'edit') {
      const row = btn.closest('tr').children;
      qs('#part-ci').value = ci;
      qs('#part-nombre').value = row[1].textContent.split(', ')[1];
      qs('#part-apellido').value = row[1].textContent.split(', ')[0];
      qs('#part-email').value = row[2].textContent;
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

  return { init };
})();

const turnosUI = (() => {
  let editing = null;

  async function list() {
    const data = await apiRequest('GET', `${apiBase}/turnos`, null, qs('#turnos-msg'));
    render(data || []);
    await combos.loadTurnos();
  }

  function render(items) {
    const tbody = qs('#turnos-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin turnos');
    tbody.innerHTML = '';
    items.forEach((t) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${t.id_turno}</td>
        <td>${t.hora_inicio}</td>
        <td>${t.hora_fin}</td>
        <td>
          <div class="table-actions">
            <button class="btn link" data-action="edit" data-id="${t.id_turno}">Editar</button>
            <button class="btn link" data-action="delete" data-id="${t.id_turno}">Eliminar</button>
          </div>
        </td>`;
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
      await apiRequest(method, url, isEdit ? { hora_inicio, hora_fin } : payload, qs('#turnos-form-msg'));
      setAlert(qs('#turnos-form-msg'), isEdit ? 'Turno actualizado' : 'Turno creado', 'success');
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
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

  async function list() {
    const fecha = qs('#reservas-filtro-fecha').value;
    const edificio = qs('#reservas-filtro-edificio').value;
    const estado = qs('#reservas-filtro-estado').value;
    const params = new URLSearchParams();
    if (fecha) params.append('fecha', fecha);
    if (edificio) params.append('edificio', edificio);
    const url = `${apiBase}/reservas${params.toString() ? `?${params.toString()}` : ''}`;
    const data = await apiRequest('GET', url, null, qs('#reservas-msg'));
    const rows = (data || []).filter((r) => !estado || r.estado === estado);
    render(rows);
  }

  function render(items) {
    const tbody = qs('#reservas-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin reservas');
    tbody.innerHTML = '';
    items.forEach((r) => {
      const participantes = r.participantes ? r.participantes.split(',') : [];
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.id_reserva}</td>
        <td>${r.edificio} · ${r.nombre_sala}</td>
        <td>${r.fecha}</td>
        <td>${r.id_turno}</td>
        <td><span class="badge ${r.estado === 'activa' ? 'success' : ''}">${r.estado}</span></td>
        <td>${participantes.join(', ') || '—'}</td>
        <td>
          <div class="table-actions">
            <select data-reserva="${r.id_reserva}" class="estado-select">
              ${ALLOWED_ESTADOS
                .map((e) => `<option value="${e}" ${e === r.estado ? 'selected' : ''}>${e}</option>`)
                .join('')}
            </select>
            <button class="btn link" data-action="estado" data-id="${r.id_reserva}">Guardar estado</button>
          </div>
        </td>`;
      tbody.appendChild(tr);
    });
  }

  async function submit(evt) {
    evt.preventDefault();
    const payload = {
      fecha: qs('#res-fecha').value,
      edificio: qs('#res-edificio').value,
      nombre_sala: qs('#res-sala').value,
      id_turno: Number(qs('#res-turno').value),
      participantes: parseCiList(qs('#res-participantes').value),
      estado: normalizeEstado(qs('#res-estado').value),
    };
    if (!payload.fecha || !payload.edificio || !payload.nombre_sala || !payload.id_turno || !payload.participantes.length) {
      return setAlert(qs('#reservas-form-msg'), 'Completa todos los campos', 'error');
    }
    try {
      await apiRequest('POST', `${apiBase}/reservas`, payload, qs('#reservas-form-msg'));
      setAlert(qs('#reservas-form-msg'), 'Reserva creada', 'success');
      await list();
      qs('#reservas-form').reset();
    } catch (_) {}
  }

  async function updateEstado(evt) {
    const btn = evt.target.closest('button[data-action="estado"]');
    if (!btn) return;
    const id = btn.dataset.id;
    const select = btn.closest('tr').querySelector('.estado-select');
    const estado = select.value;
    try {
      await apiRequest('PATCH', `${apiBase}/reservas/${id}`, { estado }, qs('#reservas-msg'));
      await list();
    } catch (_) {}
  }

  async function registrarAsistencia(evt) {
    evt.preventDefault();
    const id = qs('#asis-id').value;
    const presentes = parseCiList(qs('#asis-presentes').value);
    if (!id) return;
    try {
      await apiRequest('POST', `${apiBase}/reservas/${id}/asistencia`, { presentes }, qs('#asistencia-msg'));
      setAlert(qs('#asistencia-msg'), 'Asistencia registrada', 'success');
      await list();
    } catch (_) {}
  }

  function init() {
    qs('#reservas-refresh').addEventListener('click', list);
    qs('#reservas-form').addEventListener('submit', submit);
    qs('#reservas-table').addEventListener('click', updateEstado);
    qs('#asistencia-form').addEventListener('submit', registrarAsistencia);
    qs('#res-edificio').addEventListener('change', (e) => combos.loadSalasFor(e.target.value, qs('#res-sala')));
    list();
  }

  return { init, list };
})();

const disponibilidadUI = (() => {
  async function consultar(evt) {
    evt.preventDefault();
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
    const params = ci ? `?ci=${encodeURIComponent(ci)}` : '';
    const data = await apiRequest('GET', `${apiBase}/sanciones${params}`, null, qs('#sanciones-msg'));
    render(data || []);
  }

  function render(items) {
    const tbody = qs('#sanciones-table');
    if (!items.length) return tablePlaceholder(tbody, 'Sin sanciones');
    tbody.innerHTML = '';
    items.forEach((s) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${s.ci_participante}</td>
        <td>${s.fecha_inicio}</td>
        <td>${s.fecha_fin}</td>
        <td>
          <div class="table-actions">
            <button class="btn link" data-action="edit" data-ci="${s.ci_participante}" data-inicio="${s.fecha_inicio}" data-fin="${s.fecha_fin}">Editar</button>
            <button class="btn link" data-action="delete" data-ci="${s.ci_participante}" data-inicio="${s.fecha_inicio}">Eliminar</button>
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
    if (!ci || !fecha_inicio || !fecha_fin) return;
    const msg = qs('#sanciones-form-msg');
    try {
      if (editing) {
        await apiRequest('PUT', `${apiBase}/sanciones/${encodeURIComponent(ci)}/${fecha_inicio}`, { fecha_fin }, msg);
        setAlert(msg, 'Sanción actualizada', 'success');
      } else {
        await apiRequest('POST', `${apiBase}/sanciones`, { ci_participante: ci, fecha_inicio, fecha_fin }, msg);
        setAlert(msg, 'Sanción creada', 'success');
      }
      await list();
      resetForm();
    } catch (_) {}
  }

  async function handleAction(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
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
      try {
        await apiRequest('DELETE', `${apiBase}/sanciones/${encodeURIComponent(ci)}/${inicio}`, null, qs('#sanciones-msg'));
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
  async function load() {
    const desde = qs('#reportes-desde').value;
    const hasta = qs('#reportes-hasta').value;
    const params = new URLSearchParams();
    if (desde) params.append('desde', desde);
    if (hasta) params.append('hasta', hasta);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    try {
      const [salas, ocupacion, rol] = await Promise.all([
        apiRequest('GET', `${apiBase}/reportes/salas-mas-usadas${suffix}`),
        apiRequest('GET', `${apiBase}/reportes/ocupacion-por-edificio${suffix}`),
        apiRequest('GET', `${apiBase}/reportes/uso-por-rol${suffix}`),
      ]);
      renderTable(qs('#reporte-salas'), salas, ['edificio', 'nombre_sala', 'total_reservas']);
      renderTable(qs('#reporte-ocupacion'), ocupacion, ['edificio', 'total_reservas', 'porcentaje_sobre_total']);
      renderTable(qs('#reporte-rol'), rol, ['rol', 'tipo_programa', 'total_reservas']);
      setAlert(qs('#reportes-msg'), '');
    } catch (err) {
      setAlert(qs('#reportes-msg'), err.message, 'error');
    }
  }

  function renderTable(tbody, data, keys) {
    if (!data || !data.length) return tablePlaceholder(tbody, 'Sin datos');
    tbody.innerHTML = '';
    data.forEach((row) => {
      const tr = document.createElement('tr');
      tr.innerHTML = keys.map((k) => `<td>${row[k]}</td>`).join('');
      tbody.appendChild(tr);
    });
  }

  function init() {
    qs('#reportes-refresh').addEventListener('click', load);
    load();
  }

  return { init };
})();

function setTodayDefaults() {
  const today = new Date().toISOString().split('T')[0];
  ['#res-fecha', '#disp-fecha', '#reservas-filtro-fecha'].forEach((sel) => {
    const el = qs(sel);
    if (el && !el.value) el.value = today;
  });
}

async function bootstrap() {
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
}

document.addEventListener('DOMContentLoaded', bootstrap);
