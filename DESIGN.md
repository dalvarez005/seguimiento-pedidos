# Design

Sistema visual de la interfaz (`src/pedidos/static`). Estilo **nítido**: neutros limpios,
negro como color principal y el color reservado a los cuatro estados del paquete. Pantalla
de trabajo: controles web estándar, jerarquía por peso y tamaño, nada decorativo.

## Color
Una paleta, dos temas. Los tokens viven en `:root`; el tema oscuro los redefine
(`prefers-color-scheme` o `data-theme` en `<html>`, guardado en `localStorage` como `tema`).

| Rol | Claro | Oscuro | Uso |
|---|---|---|---|
| `--fondo` / `--superficie` | `#fafafa` / `#ffffff` | `#0a0a0a` / `#111111` | Página y paneles |
| `--superficie-2` / `--hundido` | `#f4f4f5` | `#1a1a1a` / `#161616` | Columnas, hover, cajas de IA |
| `--borde` | `#e5e5e5` | `#262626` | Bordes de 1 px |
| `--texto` / `-2` / `-3` | `#0a0a0a` / `#525252` / `#666` | `#fafafa` / `#a3a3a3` / `#8f8f8f` | Texto |
| `--primario` | `#0a0a0a` | `#fafafa` | Botón principal y "Avanzar"; se invierte en oscuro |
| Estados | `#a3a3a3` `#f59e0b` `#8b5cf6` `#22c55e` | `#8a8a8a` `#fbbf24` `#a78bfa` `#4ade80` | Pendiente, En proceso, Revisión, Listo |
| `--peligro` | `#dc2626` | `#f87171` | Rechazo y errores |

El violeta de Revisión marca también lo relacionado con la IA (ícono y viñetas).
Contraste de texto ≥ 4.5:1 en ambos temas.

## Tipografía
**Geist** para la interfaz y **Geist Mono** para datos: porcentajes, unidades, número de
paquete, fechas y la etiqueta de IA. Cifras tabulares en todo el documento. Escala fija en
rem (11–24 px), tracking negativo en títulos.

## Espacio y forma
Escala de 4 px (`--e1`…`--e7`). Radios de 12 / 10 / 7 px (panel / ficha / control).
Bordes de 1 px y sombras mínimas; la sombra grande solo en avisos y en la ficha movida.

## Componentes
- **Barra superior** fija con desenfoque: marca, estado de la IA y botón de tema.
- **Métricas:** una tarjeta dividida en 5 celdas (3 + 2 en el celular).
- **Fila de pedido:** número, cliente, % y unidades en mono, barra segmentada y conteos.
- **Columna por estado:** fondo hundido, cabecera con punto de color y conteo en mono.
- **Ficha de paquete:** "A {siguiente}" en negro y "Rechazar" con borde rojo. En Listo,
  una sola línea con el historial como ícono. `.movida` = anillo del color de texto y la
  etiqueta "Movido" hasta que la persona la ve.
- **Pestañas de estado** (< 720 px): una columna visible a la vez.

## Movimiento
La ficha se desliza a su nueva columna (FLIP, 280 ms, ease-out); el resto son transiciones de
150–200 ms. Todo se apaga con `prefers-reduced-motion`.

## Distribución
Mobile-first: una columna. Desde 720 px, 4 columnas de estado y 5 métricas en fila. Desde
1100 px, lista lateral fija y detalle a la derecha. Sin scroll horizontal desde 320 px.
