USE salas_db;

INSERT INTO facultad (id_facultad, nombre) VALUES
  (1, 'Ingeniería y Tecnologías'),
  (2, 'Ciencias Empresariales');

INSERT INTO edificio (nombre_edificio, direccion, departamento) VALUES
  ('Sede Central', 'Av. 8 de Octubre 2738', 'Montevideo'),
  ('Campus Pocitos', 'Av. Brasil 2697', 'Montevideo');

INSERT INTO programa_academico (nombre_programa, id_facultad, tipo) VALUES
  ('Ing. en IA y Datos', 1, 'grado'),
  ('MBA', 2, 'posgrado');

INSERT INTO participante (ci, nombre, apellido, email) VALUES
  ('4.123.456-7', 'Matihas', 'Sastre', 'matihas.sastre@ucu.edu.uy'),
  ('5.987.654-3', 'Ada', 'Lovelace', 'ada@ucu.edu.uy');

INSERT INTO participante_programa_academico (ci_participante, nombre_programa, rol) VALUES
  ('4.123.456-7', 'Ing. en IA y Datos', 'alumno'),
  ('5.987.654-3', 'MBA', 'docente');

INSERT INTO sala (nombre_sala, edificio, capacidad, tipo_sala) VALUES
  ('Sala 101', 'Sede Central', 6, 'libre'),
  ('Sala 102', 'Sede Central', 10, 'libre'),
  ('Sala P1',  'Campus Pocitos', 8, 'posgrado');

INSERT INTO turno (id_turno, hora_inicio, hora_fin) VALUES
  (8,  '08:00:00', '09:00:00'),
  (9,  '09:00:00', '10:00:00'),
  (10, '10:00:00', '11:00:00'),
  (11, '11:00:00', '12:00:00'),
  (12, '12:00:00', '13:00:00'),
  (13, '13:00:00', '14:00:00'),
  (14, '14:00:00', '15:00:00'),
  (15, '15:00:00', '16:00:00'),
  (16, '16:00:00', '17:00:00'),
  (17, '17:00:00', '18:00:00'),
  (18, '18:00:00', '19:00:00'),
  (19, '19:00:00', '20:00:00'),
  (20, '20:00:00', '21:00:00'),
  (21, '21:00:00', '22:00:00'),
  (22, '22:00:00', '23:00:00');
