# Tareas — Spec 001

Se implementan en orden. Cada tarea cita los requisitos que cubre.

- [x] **T01** Estructura del proyecto: `pyproject.toml`, dependencias, `config.py`, `.env.example`, `.gitignore`.
- [x] **T02** Pruebas del dominio (división, transiciones, rechazo, avance). — RF-02, RF-05, RF-06, RF-07
- [x] **T03** Implementar `domain.py` hasta que T02 pase.
- [x] **T04** Modelos SQLAlchemy y `db.py` (UNIQUE de `numero_clave`, CHECKs). — RF-04, RF-08
- [x] **T05** Esquemas Pydantic estrictos y servicios (crear, avanzar, rechazar, historial, resumen). — RF-01, RF-03, RF-04, RF-09
- [x] **T06** Rutas de la API, manejo de errores en español, `/health`.
- [x] **T07** Pruebas de API: creación, validación, duplicados, flujo completo, rechazo, persistencia. — RF-01..RF-09
- [x] **T08** Módulo IA (`interpretar`, `resumen`, `estado`) + pruebas con cliente falso. — RF-10, RF-11, RF-12
- [x] **T09** Interfaz web (alta, lista, tablero por estados, historial, IA). — HU-1..HU-5, RNF-01
- [x] **T10** Docker, compose y script de despliegue. — RNF-04
- [x] **T11** CI en GitHub Actions. — RNF-05
- [ ] **T12** README (instalación, pruebas, SDD, error del agente y su corrección, pendientes).
- [ ] **T13** Despliegue en la Orange Pi + hostname en Cloudflare + verificación pública.
