# Design

Sistema visual de la interfaz (`src/pedidos/static`). Dirección: **casillero de clasificación**.
Cada estado es una casilla hundida y cada paquete es una ficha que se desliza a la casilla
siguiente al avanzar. Pantalla de trabajo (modo *operate*): controles web estándar y la
identidad solo en tipografía, paleta, densidad y un gesto propio.

## Color
Una paleta, dos luminosidades. Los tokens viven en `:root` y el tema oscuro los redefine
(`prefers-color-scheme` o `data-theme` en `<html>`, guardado en `localStorage` como `tema`).

| Rol | Claro | Oscuro | Uso |
|---|---|---|---|
| `--shell` | `#1f3d33` | `#16302a` | Verde máquina: encabezado y avisos |
| `--fondo` / `--superficie` | `#e7ebe8` / `#f8f9f7` | `#0e1512` / `#151e1a` | Acero: fondo y paneles |
| `--casilla` | `#dde3df` | `#101814` | Interior hundido de casillas, barras y chips |
| `--primario` | `#2f5f4d` | `#4a8c72` | Acción principal |
| `--laton` | `#9c7a2f` | `#c9a14a` | Selección, foco, cambio reciente, IA |
| Estados | `#6f7a85` `#c98a0c` `#7556c2` `#2c8a55` | `#94a0ab` `#eeb13a` `#a58ce9` `#4fc185` | Pendiente, En proceso, Revisión, Listo |
| `--peligro` | `#b0392a` | `#f0806e` | Rechazo y errores |

Pares de texto verificados con WCAG AA (≥ 4.5:1) en ambos temas.

## Tipografía
Una familia, **Archivo** (Google Fonts, ejes de ancho y peso). Etiquetas de porta-etiquetas
(`.etq`): ancho 75 %, mayúsculas, 12 px, tracking .06em. Números de pedido y porcentajes
condensados al 80–85 %. Cifras tabulares en todo el documento. Escala fija en rem (12–28 px).

## Espacio y forma
Escala de 4 px (`--e1`…`--e7`). Radio de 8 px en paneles y de 5 px en controles. Profundidad
con sombras suaves desplazadas en paneles y fichas, e `inset` en casillas y campos.

## Componentes
- **Ficha de paquete:** franja superior de 3 px con el color del estado, etiqueta condensada,
  unidades grandes y botones "A {siguiente}" y "Rechazar". `.movida` = borde de latón con la
  etiqueta "Movido" hasta que la persona la ve (puntero, foco o toque).
- **Casilla:** cabecera tipo porta-etiqueta (estado, cantidad de paquetes y unidades).
- **Pestañas de casilla** (< 720 px): una casilla visible a la vez, conteo grande, barra de
  color y punto de latón si hubo cambios.
- **Fila de pedido:** botón con número, cliente, % y barra segmentada por estado.
  Seleccionada = fondo y borde de latón.
- Botones: primario, secundario, peligro y de texto; estados hover, foco, deshabilitado y
  ocupado (`aria-busy`).

## Movimiento
Un solo gesto: la ficha se desliza (FLIP, 280 ms, ease-out) a su nueva casilla. Lo demás son
transiciones de 150–200 ms. Todo se apaga con `prefers-reduced-motion`.

## Distribución
Mobile-first: una columna (alta plegable, lista y detalle). Desde 720 px, 4 casillas en fila.
Desde 1100 px, lista lateral fija y detalle a la derecha. Sin scroll horizontal desde 320 px.
