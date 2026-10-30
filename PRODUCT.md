# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Encargado** (sobre todo en PC): registra pedidos y sigue el avance por pedido.
- **Operario** (sobre todo en celular, en planta o bodega): avanza paquetes al siguiente estado.
- **Revisor** (celular o PC): rechaza paquetes en revisión, que vuelven a proceso.
- **Evaluador de la prueba técnica**: abre la app en cualquier pantalla para juzgar calidad.

## Product Purpose
Registrar pedidos y seguir su avance por paquetes de hasta 100 unidades. Cada paquete pasa
por Pendiente → En proceso → Revisión → Listo, sin saltar ni regresar estados (salvo el rechazo
en Revisión). El avance se mide por unidades listas. Éxito: saber de un vistazo cómo va cada
pedido y mover un paquete en un toque.

## Positioning
El pedido se divide solo en paquetes y su avance se mide por unidades, no por tareas. Una IA
opcional (Gemini con respaldo de Claude) llena el alta a partir de texto libre y redacta un
resumen del avance; nunca guarda nada por su cuenta.

## Operating Context
Uso diario, mezcla de PC y celular. Datos reales del negocio: número de pedido, cliente,
cantidad, paquetes, historial de movimientos y rechazos con motivo.

## Capabilities and Constraints
- FastAPI sirve una página única con HTML/CSS/JS sin framework ni paso de build (`src/pedidos/static`).
- Endpoints: `/api/pedidos`, `/api/paquetes/{id}/avanzar|rechazar|historial`, `/api/ia/estado|interpretar|resumen`.
- Las reglas se validan en el servidor; la interfaz solo ayuda.
- Textos en español. Se despliega en una Orange Pi (recursos limitados).

## Brand Commitments
Ninguna identidad previa obligatoria. La persona pidió una identidad nueva, con modo claro y
oscuro de la misma paleta y un botón para cambiar de tema. Rechaza lo genérico/plano y lo desordenado.

## Evidence on Hand
Sin logos, testimonios ni imágenes. No inventar clientes ni cifras.

## Product Principles
1. Claridad primero: dónde se acumulan los paquetes y qué hacer después debe leerse al instante.
2. Una acción, un toque: avanzar o rechazar no exige navegar.
3. El servidor manda; la interfaz explica los errores en español.
4. La IA propone, la persona confirma.

## Accessibility & Inclusion
WCAG 2.1 AA en ambos temas, operable con teclado, `prefers-reduced-motion`, usable desde 320 px.
