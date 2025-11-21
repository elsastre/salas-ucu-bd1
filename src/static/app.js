const apiBase = '';

const qs = (selector) => document.querySelector(selector);

const renderList = (element, items, formatter) => {
  element.innerHTML = '';
  if (!items || items.length === 0) {
    element.innerHTML = '<li class="empty">Sin datos</li>';
    return;
  }
  for (const item of items) {
    const li = document.createElement('li');
    li.innerHTML = formatter(item);
    element.appendChild(li);
  }
};

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  const text = await res.text();
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const data = text ? JSON.parse(text) : null;
      if (data?.detail) msg += `: ${data.detail}`;
    } catch (err) {
      // ignore
    }
    if (!text && res.statusText) msg += `: ${res.statusText}`;
    throw new Error(msg);
  }
  return text ? JSON.parse(text) : null;
}

const parseLista = (value) =>
  value
    .split(',')
    .map((p) => p.trim())
    .filter(Boolean);

const setMessage = (selector, message, isError = false) => {
  const el = qs(selector);
  el.textContent = message;
  el.className = isError ? 'error' : '';
};

async function cargarEdificios() {
  try {
    const datos = await fetchJSON(`${apiBase}/edificios`);
    renderList(qs('#lista-edificios'), datos, (d) => `${d.edificio}`);
  } catch (err) {
    qs('#lista-edificios').innerHTML = `<li class="error">${err.message}</li>`;
  }
}

async function cargarSalas() {
  try {
    const datos = await fetchJSON(`${apiBase}/salas`);
    renderList(
      qs('#lista-salas'),
      datos,
      (d) => `${d.edificio} · ${d.nombre_sala} (capacidad ${d.capacidad}, tipo ${d.tipo_sala})`
    );
  } catch (err) {
    qs('#lista-salas').innerHTML = `<li class="error">${err.message}</li>`;
  }
}

async function cargarReservas() {
  try {
    const datos = await fetchJSON(`${apiBase}/reservas`);
    renderList(
      qs('#lista-reservas'),
      datos,
      (d) => `${d.id_reserva}: ${d.edificio} ${d.nombre_sala} · ${d.fecha} · turno ${d.id_turno} · estado ${d.estado}`
    );
  } catch (err) {
    qs('#lista-reservas').innerHTML = `<li class="error">${err.message}</li>`;
  }
}

async function cargarTurnos() {
  try {
    const datos = await fetchJSON(`${apiBase}/turnos`);
    renderList(
      qs('#lista-turnos'),
      datos,
      (d) => `${d.id_turno}: ${d.hora_inicio} - ${d.hora_fin}`
    );
  } catch (err) {
    qs('#lista-turnos').innerHTML = `<li class="error">${err.message}</li>`;
  }
}

async function buscarTurno(event) {
  event.preventDefault();
  const id = qs('#turno-id').value;
  if (!id) return;
  setMessage('#turno-detalle', 'Buscando...');
  try {
    const dato = await fetchJSON(`${apiBase}/turnos/${encodeURIComponent(id)}`);
    setMessage(
      '#turno-detalle',
      `Turno ${dato.id_turno}: ${dato.hora_inicio} - ${dato.hora_fin}`
    );
  } catch (err) {
    setMessage('#turno-detalle', err.message, true);
  }
}

async function cargarParticipantes() {
  try {
    const datos = await fetchJSON(`${apiBase}/participantes`);
    renderList(
      qs('#lista-participantes'),
      datos,
      (d) => `${d.ci}: ${d.apellido}, ${d.nombre} (${d.email})`
    );
  } catch (err) {
    qs('#lista-participantes').innerHTML = `<li class="error">${err.message}</li>`;
  }
}

async function buscarParticipante(event) {
  event.preventDefault();
  const ci = qs('#participante-ci').value.trim();
  if (!ci) return;
  setMessage('#participante-detalle', 'Buscando...');
  try {
    const dato = await fetchJSON(`${apiBase}/participantes/${encodeURIComponent(ci)}`);
    setMessage(
      '#participante-detalle',
      `${dato.ci}: ${dato.apellido}, ${dato.nombre} (${dato.email})`
    );
  } catch (err) {
    setMessage('#participante-detalle', err.message, true);
  }
}

async function crearParticipante(event) {
  event.preventDefault();
  const payload = {
    ci: qs('#nuevo-ci').value.trim(),
    nombre: qs('#nuevo-nombre').value.trim(),
    apellido: qs('#nuevo-apellido').value.trim(),
    email: qs('#nuevo-email').value.trim(),
  };
  if (!payload.ci || !payload.nombre || !payload.apellido || !payload.email) return;
  setMessage('#participante-msg', 'Enviando...');
  try {
    await fetchJSON(`${apiBase}/participantes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    setMessage('#participante-msg', 'Participante creado.');
    cargarParticipantes();
    qs('#form-participante').reset();
  } catch (err) {
    setMessage('#participante-msg', err.message, true);
  }
}

async function crearReserva(event) {
  event.preventDefault();
  const payload = {
    edificio: qs('#reserva-edificio').value.trim(),
    nombre_sala: qs('#reserva-sala').value.trim(),
    fecha: qs('#reserva-fecha').value,
    id_turno: Number(qs('#reserva-turno').value),
    participantes: parseLista(qs('#reserva-participantes').value),
  };
  const estado = qs('#reserva-estado').value.trim();
  if (estado) payload.estado = estado;
  if (!payload.edificio || !payload.nombre_sala || !payload.fecha || !payload.id_turno) {
    return;
  }
  setMessage('#reserva-msg', 'Enviando...');
  try {
    await fetchJSON(`${apiBase}/reservas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    setMessage('#reserva-msg', 'Reserva creada.');
    cargarReservas();
    qs('#form-reserva').reset();
  } catch (err) {
    setMessage('#reserva-msg', err.message, true);
  }
}

async function registrarAsistencia(event) {
  event.preventDefault();
  const id = qs('#asistencia-id').value;
  if (!id) return;
  const payload = {
    presentes: parseLista(qs('#asistencia-presentes').value || ''),
  };
  setMessage('#asistencia-msg', 'Enviando...');
  try {
    await fetchJSON(`${apiBase}/reservas/${encodeURIComponent(id)}/asistencia`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    setMessage('#asistencia-msg', 'Asistencia registrada.');
    cargarReservas();
    qs('#form-asistencia').reset();
  } catch (err) {
    setMessage('#asistencia-msg', err.message, true);
  }
}

async function consultarDisponibilidad(event) {
  event.preventDefault();
  const fecha = qs('#fecha').value;
  const edificio = qs('#edificio').value;
  const sala = qs('#sala').value;
  if (!fecha || !edificio || !sala) return;
  const contenedor = qs('#disponibilidad');
  contenedor.textContent = 'Consultando...';
  try {
    const datos = await fetchJSON(
      `${apiBase}/disponibilidad?fecha=${encodeURIComponent(fecha)}&edificio=${encodeURIComponent(
        edificio
      )}&nombre_sala=${encodeURIComponent(sala)}`
    );
    if (datos.length === 0) {
      contenedor.textContent = 'Sin turnos para mostrar';
      return;
    }
    const lista = document.createElement('ul');
    datos.forEach((d) => {
      const li = document.createElement('li');
      li.textContent = `${d.hora_inicio} - ${d.hora_fin}: ${d.reservado ? 'Reservado' : 'Libre'}${
        d.estado_reserva ? ` (${d.estado_reserva})` : ''
      }`;
      if (d.reservado) li.classList.add('reservado');
      lista.appendChild(li);
    });
    contenedor.innerHTML = '';
    contenedor.appendChild(lista);
  } catch (err) {
    contenedor.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

function setDefaultFecha() {
  const hoy = new Date().toISOString().split('T')[0];
  qs('#fecha').value = hoy;
  const fechaReserva = qs('#reserva-fecha');
  if (fechaReserva) fechaReserva.value = hoy;
}

document.addEventListener('DOMContentLoaded', () => {
  setDefaultFecha();
  cargarEdificios();
  cargarSalas();
  cargarReservas();
  qs('#btn-edificios').addEventListener('click', cargarEdificios);
  qs('#btn-salas').addEventListener('click', cargarSalas);
  qs('#btn-reservas').addEventListener('click', cargarReservas);
  qs('#form-disponibilidad').addEventListener('submit', consultarDisponibilidad);

  qs('#btn-turnos').addEventListener('click', cargarTurnos);
  qs('#btn-turno-detalle').addEventListener('click', buscarTurno);

  qs('#btn-participantes').addEventListener('click', cargarParticipantes);
  qs('#btn-participante-detalle').addEventListener('click', buscarParticipante);
  qs('#form-participante').addEventListener('submit', crearParticipante);

  qs('#form-reserva').addEventListener('submit', crearReserva);
  qs('#form-asistencia').addEventListener('submit', registrarAsistencia);
});
