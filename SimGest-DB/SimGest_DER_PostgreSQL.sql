-- =========================================================
-- SimGest - Script de creación de base de datos (PostgreSQL 16)
-- =========================================================

-- Ejecutar conectado a la base de datos del proyecto, por ejemplo:
-- CREATE DATABASE simgest_db;
-- \c simgest_db

-- ---------------------------------------------------------
-- Tabla: rol
-- ---------------------------------------------------------
CREATE TABLE rol (
    id_rol      SERIAL PRIMARY KEY,
    nombre      VARCHAR(50) NOT NULL UNIQUE
);

-- ---------------------------------------------------------
-- Tabla: usuario
-- ---------------------------------------------------------
CREATE TABLE usuario (
    id_usuario      SERIAL PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    id_rol          INT NOT NULL REFERENCES rol(id_rol),
    estado          VARCHAR(20) NOT NULL DEFAULT 'activo',
    fecha_creacion  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Tabla: bitacora (auditoría de acciones)
-- ---------------------------------------------------------
CREATE TABLE bitacora (
    id_bitacora     SERIAL PRIMARY KEY,
    id_usuario      INT NOT NULL REFERENCES usuario(id_usuario),
    fecha           DATE NOT NULL DEFAULT CURRENT_DATE,
    hora            TIME NOT NULL DEFAULT CURRENT_TIME,
    accion          VARCHAR(150) NOT NULL,
    resultado       VARCHAR(50) NOT NULL,
    ip_origen       VARCHAR(45)
);

-- ---------------------------------------------------------
-- Tabla: historial_accesos
-- ---------------------------------------------------------
CREATE TABLE historial_accesos (
    id_historial    SERIAL PRIMARY KEY,
    id_usuario      INT NOT NULL REFERENCES usuario(id_usuario),
    fecha           DATE NOT NULL DEFAULT CURRENT_DATE,
    hora            TIME NOT NULL DEFAULT CURRENT_TIME,
    resultado       VARCHAR(50) NOT NULL,
    ip_origen       VARCHAR(45)
);

-- ---------------------------------------------------------
-- Tabla: notificacion
-- ---------------------------------------------------------
CREATE TABLE notificacion (
    id_notificacion SERIAL PRIMARY KEY,
    id_usuario      INT NOT NULL REFERENCES usuario(id_usuario),
    mensaje         VARCHAR(255) NOT NULL,
    fecha           TIMESTAMP NOT NULL DEFAULT NOW(),
    leido           BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------
-- Tabla: categoria (de escenarios)
-- ---------------------------------------------------------
CREATE TABLE categoria (
    id_categoria    SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL UNIQUE
);

-- ---------------------------------------------------------
-- Tabla: escenario (guiones de simulación)
-- ---------------------------------------------------------
CREATE TABLE escenario (
    id_escenario    SERIAL PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    descripcion     TEXT,
    id_categoria    INT NOT NULL REFERENCES categoria(id_categoria)
);

-- ---------------------------------------------------------
-- Tabla: solicitud
-- ---------------------------------------------------------
CREATE TABLE solicitud (
    id_solicitud    SERIAL PRIMARY KEY,
    id_cliente      INT NOT NULL REFERENCES usuario(id_usuario),
    id_escenario    INT NOT NULL REFERENCES escenario(id_escenario),
    estado          VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    fecha_solicitud TIMESTAMP NOT NULL DEFAULT NOW(),
    fecha_evento    DATE NOT NULL
);

-- ---------------------------------------------------------
-- Tabla: actor (extiende usuario)
-- ---------------------------------------------------------
CREATE TABLE actor (
    id_actor        SERIAL PRIMARY KEY,
    id_usuario      INT NOT NULL UNIQUE REFERENCES usuario(id_usuario),
    edad            INT,
    genero          VARCHAR(20),
    habilidades     TEXT,
    tarifa          NUMERIC(10,2),
    tipo_tarifa     VARCHAR(30)
);

-- ---------------------------------------------------------
-- Tabla: disponibilidad
-- ---------------------------------------------------------
CREATE TABLE disponibilidad (
    id_disponibilidad SERIAL PRIMARY KEY,
    id_actor          INT NOT NULL REFERENCES actor(id_actor),
    fecha             DATE NOT NULL,
    hora_inicio       TIME NOT NULL,
    hora_fin          TIME NOT NULL
);

-- ---------------------------------------------------------
-- Tabla: asignacion (actor asignado a una solicitud)
-- ---------------------------------------------------------
CREATE TABLE asignacion (
    id_asignacion   SERIAL PRIMARY KEY,
    id_solicitud    INT NOT NULL REFERENCES solicitud(id_solicitud),
    id_actor        INT NOT NULL REFERENCES actor(id_actor),
    estado          VARCHAR(30) NOT NULL DEFAULT 'asignado'
);

-- ---------------------------------------------------------
-- Tabla: pago
-- ---------------------------------------------------------
CREATE TABLE pago (
    id_pago         SERIAL PRIMARY KEY,
    id_solicitud    INT NOT NULL REFERENCES solicitud(id_solicitud),
    id_actor        INT NOT NULL REFERENCES actor(id_actor),
    monto           NUMERIC(10,2) NOT NULL,
    fecha_pago      DATE,
    estado          VARCHAR(30) NOT NULL DEFAULT 'pendiente'
);

-- =========================================================
-- Datos de prueba mínimos (dummy data para evidencia local)
-- =========================================================
INSERT INTO rol (nombre) VALUES ('Cliente'), ('Administrador'), ('Actor');

INSERT INTO usuario (nombre, email, password_hash, id_rol)
VALUES
('Cliente de Prueba', 'cliente@prueba.com', 'hash_temporal_1', 1),
('Admin de Prueba', 'admin@prueba.com', 'hash_temporal_2', 2),
('Actor de Prueba', 'actor@prueba.com', 'hash_temporal_3', 3);

INSERT INTO categoria (nombre) VALUES ('Emergencias'), ('Atención primaria');

INSERT INTO escenario (nombre, descripcion, id_categoria)
VALUES ('Paro cardíaco simulado', 'Escenario de práctica clínica', 1);

INSERT INTO actor (id_usuario, edad, genero, habilidades, tarifa, tipo_tarifa)
VALUES (3, 30, 'No especificado', 'Actuación clínica', 15000.00, 'por hora');

-- =========================================================
-- Consultas de prueba (para la evidencia del entregable)
-- =========================================================

-- Verificar que las tablas se crearon correctamente
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Verificar los datos de prueba insertados
SELECT u.nombre, u.email, r.nombre AS rol
FROM usuario u
JOIN rol r ON u.id_rol = r.id_rol;
