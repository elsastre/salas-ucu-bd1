USE salas_db;
#Salas más reservadas
SELECT s.nombre_sala, s.edificio, COUNT(r.id_reserva) AS total_reservas
FROM reserva r
JOIN sala s ON r.nombre_sala = s.nombre_sala AND r.edificio = s.edificio
GROUP BY s.nombre_sala, s.edificio
ORDER BY total_reservas DESC;

#Turnos mas demandados
SELECT t.id_turno, t.hora_inicio, t.hora_fin, COUNT(r.id_reserva) AS total_reservas
FROM reserva r
JOIN turno t ON r.id_turno = t.id_turno
GROUP BY t.id_turno, t.hora_inicio, t.hora_fin
ORDER BY total_reservas DESC;

#Promedio de participantes por sala
SELECT s.nombre_sala, s.edificio,
       AVG(num_participantes) AS promedio_participantes
FROM (
    SELECT r.id_reserva, r.nombre_sala, r.edificio, COUNT(rp.ci_participante) AS num_participantes
    FROM reserva r
    JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva
    GROUP BY r.id_reserva, r.nombre_sala, r.edificio
) AS sub
JOIN sala s ON s.nombre_sala = sub.nombre_sala AND s.edificio = sub.edificio
GROUP BY s.nombre_sala, s.edificio;

#Cantidad de reservas por carrera (programa académico) y facultad
SELECT f.nombre AS facultad, p.nombre_programa AS programa, COUNT(DISTINCT rp.id_reserva) AS total_reservas
FROM reserva_participante rp
JOIN participante_programa_academico ppa ON rp.ci_participante = ppa.ci_participante
JOIN programa_academico p ON ppa.nombre_programa = p.nombre_programa
JOIN facultad f ON p.id_facultad = f.id_facultad
GROUP BY f.nombre, p.nombre_programa
ORDER BY total_reservas DESC;

#Porcentaje de ocupación de salas por edificio, (Comparando capacidad total con cantidad promedio de asistentes)
SELECT sub.edificio,
       ROUND(SUM(sub.ocupacion) / SUM(sub.capacidad_total) * 100, 2) AS porcentaje_ocupacion
FROM (
    SELECT r.id_reserva, r.nombre_sala, r.edificio,
           COUNT(rp.ci_participante) AS ocupacion,
           s.capacidad AS capacidad_total
    FROM reserva r
    JOIN sala s ON r.nombre_sala = s.nombre_sala AND r.edificio = s.edificio
    LEFT JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva AND rp.asistencia = TRUE
    GROUP BY r.id_reserva, r.nombre_sala, r.edificio, s.capacidad
) AS sub
GROUP BY sub.edificio;

#Cantidad de reservas y asistencias de profesores y alumnos (grado y posgrado)
SELECT ppa.rol, pa.tipo,
       COUNT(DISTINCT rp.id_reserva) AS reservas,
       SUM(rp.asistencia) AS asistencias
FROM reserva_participante rp
JOIN participante_programa_academico ppa ON rp.ci_participante = ppa.ci_participante
JOIN programa_academico pa ON ppa.nombre_programa = pa.nombre_programa
GROUP BY ppa.rol, pa.tipo;

#Cantidad de sanciones para profesores y alumnos (grado y posgrado)
SELECT ppa.rol, pa.tipo, COUNT(sp.ci_participante) AS total_sanciones
FROM sancion_participante sp
JOIN participante_programa_academico ppa ON sp.ci_participante = ppa.ci_participante
JOIN programa_academico pa ON ppa.nombre_programa = pa.nombre_programa
GROUP BY ppa.rol, pa.tipo;

#Porcentaje de reservas efectivamente utilizadas vs canceladas/no asistidas
SELECT
  SUM(CASE WHEN r.estado = 'finalizada' THEN 1 ELSE 0 END) / COUNT(*) * 100 AS porcentaje_utilizadas,
  SUM(CASE WHEN r.estado IN ('cancelada','sin_asistencia') THEN 1 ELSE 0 END) / COUNT(*) * 100 AS porcentaje_no_utilizadas
FROM reserva r;

#ADICIONAL 1 Salas con más cancelaciones
SELECT s.nombre_sala, s.edificio, COUNT(*) AS cancelaciones
FROM reserva r
JOIN sala s ON r.nombre_sala = s.nombre_sala AND r.edificio = s.edificio
WHERE r.estado = 'cancelada'
GROUP BY s.nombre_sala, s.edificio
ORDER BY cancelaciones DESC;

#ADICIONAL 2 Participantes con mayor puntualidad (asistencia promedio)
SELECT
  p.nombre,
  p.apellido,
  ROUND(AVG(rp.asistencia) * 100, 2) AS porcentaje_asistencia
FROM reserva_participante rp
JOIN participante p ON rp.ci_participante = p.ci
GROUP BY p.ci
ORDER BY porcentaje_asistencia DESC;

#ADICIONAL 3 Porcentaje de utilización por tipo de sala
#Evalúa qué tipo de sala (libre, posgrado o docente) se usa más en proporción a sus reservas efectivas.
SELECT
  s.tipo_sala,
  ROUND(SUM(CASE WHEN r.estado = 'finalizada' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS porcentaje_uso
FROM reserva r
JOIN sala s ON r.nombre_sala = s.nombre_sala AND r.edificio = s.edificio
GROUP BY s.tipo_sala
ORDER BY porcentaje_uso DESC;