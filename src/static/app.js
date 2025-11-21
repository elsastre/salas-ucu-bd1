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

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

async function cargarEdificios() {
  try {
    const datos = await fetchJSON(`${apiBase}/edificios`);
    renderList(
      qs('#lista-edificios'),
      datos,
      (d) => `${d.edificio}`
    );
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
});
