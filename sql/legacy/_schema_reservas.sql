USE salas_db;

CREATE TABLE IF NOT EXISTS facultad (
  id_facultad INT PRIMARY KEY,
  nombre      VARCHAR(120) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS edificio (
  id_edificio INT PRIMARY KEY,
  facultad_id INT NOT NULL,
  nombre      VARCHAR(120) NOT NULL,
  CONSTRAINT fk_edificio_facultad
    FOREIGN KEY (facultad_id) REFERENCES facultad(id_facultad)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sala (
  id_sala     INT PRIMARY KEY,
  edificio_id INT NOT NULL,
  nombre      VARCHAR(120) NOT NULL,
  capacidad   INT NOT NULL,
  CONSTRAINT fk_sala_edificio
    FOREIGN KEY (edificio_id) REFERENCES edificio(id_edificio)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS usuario (
  id_usuario INT PRIMARY KEY,
  nombre     VARCHAR(120) NOT NULL
) ENGINE=InnoDB;

/* La tabla turno ya existe (id_turno, hora_inicio, hora_fin) */

CREATE TABLE IF NOT EXISTS reserva (
  id_reserva INT PRIMARY KEY AUTO_INCREMENT,
  sala_id    INT NOT NULL,
  usuario_id INT NOT NULL,
  fecha      DATE NOT NULL,
  turno_id   INT NOT NULL,
  estado     ENUM('activa','cancelada') NOT NULL DEFAULT 'activa',
  UNIQUE KEY uq_reserva (sala_id, fecha, turno_id),
  CONSTRAINT fk_reserva_sala    FOREIGN KEY (sala_id)    REFERENCES sala(id_sala),
  CONSTRAINT fk_reserva_usuario FOREIGN KEY (usuario_id) REFERENCES usuario(id_usuario),
  CONSTRAINT fk_reserva_turno   FOREIGN KEY (turno_id)   REFERENCES turno(id_turno)
) ENGINE=InnoDB;
