# Spec 001 — Seguimiento de pedidos por paquetes

- **Estado:** aprobada
- **Fecha:** 2026-10-29
- **Origen:** prueba técnica "Seguimiento de pedidos" (Inteligencia Organizacional)

## 1. Objetivo
Aplicación web para registrar pedidos y dar seguimiento a su avance por
paquetes de hasta 100 unidades.

## 2. Glosario
| Término | Definición |
|---|---|
| Pedido | Solicitud con número único, cliente y cantidad de unidades. |
| Paquete | Parte de un pedido con 1 a 100 unidades. Tiene un estado. |
| Estado | Uno de: `Pendiente`, `En proceso`, `Revisión`, `Listo`. |
| Avance | Porcentaje de unidades del pedido que están en paquetes `Listo`. |

## 3. Historias de usuario
- **HU-1.** Como encargado, quiero registrar un pedido con número, cliente y
  cantidad para que el sistema lo divida en paquetes automáticamente.
- **HU-2.** Como operario, quiero avanzar cada paquete por los estados en orden
  para reflejar el trabajo real.
- **HU-3.** Como revisor, quiero rechazar un paquete en revisión para que
  vuelva a proceso.
- **HU-4.** Como encargado, quiero ver por pedido cuántos paquetes hay en cada
  estado y su porcentaje de avance.
- **HU-5 (extra IA).** Como encargado, quiero escribir el pedido en lenguaje
  natural y obtener un resumen del avance redactado por IA.

## 4. Requisitos funcionales

### RF-01 Crear pedido
El pedido tiene `numero` (texto, 1–40 caracteres, sin espacios al inicio o
final), `cliente` (texto, 1–120 caracteres) y `cantidad` (entero).

### RF-02 División automática en paquetes
Al guardar, el pedido se divide en `⌊cantidad / 100⌋` paquetes de 100
unidades más un paquete con el residuo si es mayor que 0. Los paquetes se
numeran 1..n en ese orden y todos inician en `Pendiente`.

| Given cantidad | Then paquetes |
|---|---|
| 250 | 100, 100, 50 |
| 100 | 100 |
| 1 | 1 |
| 99 | 99 |
| 1000 | 100 × 10 |
| 101 | 100, 1 |

### RF-03 Validación de cantidad
`cantidad` debe ser un número entero mayor que 0. Se rechazan: 0, negativos,
decimales (`2.5`), texto (`"abc"`, `"10"`), booleanos y vacío. Límite superior
operativo: 100 000 unidades (1 000 paquetes) para proteger el servidor.
Respuesta: HTTP 422 con mensaje en español.

### RF-04 Número de pedido único
No pueden existir dos pedidos con el mismo `numero` (comparación sin espacios
alrededor y sin distinguir mayúsculas). Se garantiza también con una
restricción `UNIQUE` en la base de datos. Respuesta: HTTP 409.

### RF-05 Avanzar paquete
Un paquete avanza solo al estado siguiente:
`Pendiente → En proceso → Revisión → Listo`. No se puede saltar estados ni
regresar con "avanzar". Un paquete `Listo` no avanza más.
Respuesta ante transición inválida: HTTP 409.

### RF-06 Rechazar en revisión
Solo un paquete en `Revisión` puede rechazarse; vuelve a `En proceso`. Se
puede registrar un motivo opcional (hasta 300 caracteres). Rechazar en otro
estado: HTTP 409.

### RF-07 Resumen por pedido
Por cada pedido se muestra la cantidad de paquetes en cada uno de los 4
estados (incluidos los que tienen 0) y el avance:
`avance = unidades en paquetes Listo / cantidad total × 100`, redondeado a
1 decimal.

Ejemplo: pedido de 250 (100, 100, 50) con el paquete de 50 en `Listo` →
avance 20.0 %, no 33.3 % (se calcula por unidades, no por paquetes).

### RF-08 Persistencia
Pedidos, paquetes e historial se guardan en una base de datos relacional
(PostgreSQL en producción, SQLite en desarrollo y pruebas). Los datos
sobreviven a reinicios.

### RF-09 Historial de movimientos (extra)
Cada avance o rechazo registra un evento con estado origen, destino, acción,
motivo y fecha. Se consulta por paquete.

### RF-10 Crear pedido con IA (extra)
El usuario escribe texto libre (p. ej. *"pedido PED-1001 para Ferretería
López, 250 unidades"*). Claude devuelve un **borrador** `{numero, cliente,
cantidad}`. El borrador se muestra en el formulario y el usuario lo confirma;
la IA nunca guarda nada. Si falta un dato, el campo queda vacío y se avisa.

### RF-11 Resumen del avance con IA (extra)
Botón que pide a Claude un informe breve en español del estado de un pedido o
de todos los pedidos: avance, paquetes atascados, rechazos frecuentes y
siguiente acción sugerida. Se basa solo en los datos enviados.

### RF-12 IA opcional
Si no hay `ANTHROPIC_API_KEY`, `GET /api/ia/estado` responde
`{"disponible": false}`, la interfaz oculta las funciones de IA y el resto de
la aplicación funciona igual. Errores de la IA → HTTP 503 con mensaje claro.

## 5. Requisitos no funcionales
- **RNF-01** Interfaz en español, responsive (desde 360 px de ancho).
- **RNF-02** Las reglas de negocio se validan en el servidor.
- **RNF-03** Operaciones concurrentes: avanzar/rechazar usa bloqueo de fila
  (o equivalente) para no saltar estados con dos clics simultáneos.
- **RNF-04** Contenedor único liviano (≤ 200 MB de RAM) para la Orange Pi.
- **RNF-05** Pruebas automatizadas de dominio y API en CI.

## 6. Fuera de alcance
Autenticación de usuarios, edición o borrado de pedidos, cambio de cantidad
de un pedido ya creado.
