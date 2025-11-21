-- MySQL 8.x, utf8mb4
CREATE DATABASE IF NOT EXISTS salas_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE salas_db;

CREATE TABLE facultad (
  id_facultad INT PRIMARY KEY,
  nombre      VARCHAR(120) NOT NULL
);

CREATE TABLE edificio (
  nombre_edificio VARCHAR(80) PRIMARY KEY,
  direccion       VARCHAR(200) NOT NULL,
  departamento    VARCHAR(80)  NOT NULL
);

CREATE TABLE programa_academico (
  nombre_programa VARCHAR(120) PRIMARY KEY,
  id_facultad     INT NOT NULL,
  tipo            ENUM('grado','posgrado') NOT NULL,
  FOREIGN KEY (id_facultad) REFERENCES facultad(id_facultad)
);

CREATE TABLE participante (
  ci                VARCHAR(20) PRIMARY KEY,
  nombre            VARCHAR(80) NOT NULL,
  apellido          VARCHAR(80) NOT NULL,
  email             VARCHAR(120) NOT NULL UNIQUE,
  tipo_participante ENUM('estudiante','docente','posgrado') NOT NULL DEFAULT 'estudiante',
  es_admin          TINYINT(1) NOT NULL DEFAULT 0
);

CREATE TABLE participante_programa_academico (
  id_alumno_programa INT PRIMARY KEY AUTO_INCREMENT,
  ci_participante    VARCHAR(20) NOT NULL,
  nombre_programa    VARCHAR(120) NOT NULL,
  rol                ENUM('alumno','docente') NOT NULL,
  FOREIGN KEY (ci_participante)  REFERENCES participante(ci),
  FOREIGN KEY (nombre_programa)  REFERENCES programa_academico(nombre_programa)
);

CREATE TABLE sala (
  nombre_sala  VARCHAR(80) NOT NULL,
  edificio     VARCHAR(80) NOT NULL,
  capacidad    INT NOT NULL CHECK (capacidad > 0),
  tipo_sala    ENUM('libre','posgrado','docente') NOT NULL,
  PRIMARY KEY (nombre_sala, edificio),
  FOREIGN KEY (edificio) REFERENCES edificio(nombre_edificio)
);

CREATE TABLE turno (
  id_turno    INT PRIMARY KEY,
  hora_inicio TIME NOT NULL,
  hora_fin    TIME NOT NULL,
  CONSTRAINT ck_turno CHECK (hora_fin > hora_inicio)
);

CREATE TABLE reserva (
  id_reserva   INT PRIMARY KEY AUTO_INCREMENT,
  nombre_sala  VARCHAR(80) NOT NULL,
  edificio     VARCHAR(80) NOT NULL,
  fecha        DATE NOT NULL,
  id_turno     INT NOT NULL,
  estado       ENUM('activa','cancelada','sin_asistencia','finalizada') NOT NULL DEFAULT 'activa',
  UNIQUE KEY uq_reserva_unica (nombre_sala, edificio, fecha, id_turno),
  FOREIGN KEY (nombre_sala, edificio) REFERENCES sala(nombre_sala, edificio),
  FOREIGN KEY (id_turno)              REFERENCES turno(id_turno)
);

CREATE TABLE reserva_participante (
  ci_participante          VARCHAR(20) NOT NULL,
  id_reserva               INT NOT NULL,
  fecha_solicitud_reserva  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  asistencia               BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (ci_participante, id_reserva),
  FOREIGN KEY (ci_participante) REFERENCES participante(ci),
  FOREIGN KEY (id_reserva)      REFERENCES reserva(id_reserva)
);

CREATE TABLE login (
  correo      VARCHAR(120) PRIMARY KEY,
  contrasena  VARCHAR(255) NOT NULL
);

CREATE TABLE sancion_participante (
  ci_participante VARCHAR(20) NOT NULL,
  fecha_inicio    DATE NOT NULL,
  fecha_fin       DATE NOT NULL,
  PRIMARY KEY (ci_participante, fecha_inicio),
  FOREIGN KEY (ci_participante) REFERENCES participante(ci),
  CHECK (fecha_fin > fecha_inicio)
);

