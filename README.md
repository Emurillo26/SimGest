# SimGest

Sistema web de gestión de simulaciones desarrollado para **Escénica la Semilla S.A. / Simulactores**, empresa dedicada a la producción de simulaciones clínicas y corporativas con actores profesionales.

Proyecto desarrollado en el marco del curso **SC-702 Diseño y Desarrollo de Sistemas**, Universidad Fidélitas, III Cuatrimestre 2026 (continuación del proyecto iniciado en SC-603 Análisis y Modelado de Requerimientos).

---

## 🧑‍💻 Equipo de Desarrollo — Grupo 2

| Nombre | Rol |
|---|---|
| Engel García Murillo | Project Manager / QA |
| Allison González Aguilar | UI/UX Designer |
| Jefry Goleath Arrieta | Full-Stack Lead |
| Dayana Castillo Villalobos | Business Analyst |

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3 / Django |
| Frontend | Bootstrap 5 |
| Base de datos | PostgreSQL 16 |
| Entorno de desarrollo | pgAdmin 4 / VS Code |
| Control de versiones | Git / GitHub |
| Gestión de proyecto | Azure DevOps (Boards, Backlogs, Sprints) |

---

## 📄 Documentación

### SC-603 — Análisis y Modelado de Requerimientos
| Documento | Descripción |
|---|---|
| IN01 | Documento de Alcance y Aceptación |
| IN02 | Estudio de Factibilidad |
| AN01 | Especificación de Requerimientos |
| AN02 | Historias de Usuario (migradas a Azure DevOps) |
| DN01 | Documento de Arquitectura de Software |

### SC-702 — Diseño y Desarrollo de Sistemas
| Documento | Descripción |
|---|---|
| PL01 | Planificación y Preparación de Ambientes |
| Bitácora Sprint 1 | Objetivo, backlog e historias planificadas para el Sprint 1 |
| Checklist Ambiente | Verificación de instalación por integrante (Python, Django, PostgreSQL, Git, VS Code) |

---

## 👩‍🏫 Docente

MSc. Kimberly Quirós Quirós — SC-702 Diseño y Desarrollo de Sistemas

---

## 📁 Estructura del Repositorio

```
SimGest/
├── simgest/                  # Proyecto Django (configuración, apps, settings)
├── SimGest-DB/                # Script de creación de la base de datos (PostgreSQL)
├── SimGest-Mockup/             # Diseño visual / mockup de la aplicación
├── .env.example                # Plantilla de variables de entorno (copiar a .env)
├── .gitignore                  # Archivos y carpetas excluidos del control de versiones
├── manage.py                   # Utilidad de administración de Django
├── requirements.txt            # Dependencias del proyecto (Django, psycopg2-binary, python-decouple)
└── README.md                   # Este archivo
```
