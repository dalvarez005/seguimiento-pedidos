"use strict";

const ESTADOS = ["pendiente", "en_proceso", "revision", "listo"];
const NOMBRE = { pendiente: "Pendiente", en_proceso: "En proceso", revision: "Revisión", listo: "Listo" };
const SIGUIENTE = { pendiente: "en_proceso", en_proceso: "revision", revision: "listo" };
const MAX_UNIDADES = 100000;
const POR_COLUMNA = 24;
const MOVIL = window.matchMedia("(max-width: 719.98px)");
const ESCRITORIO = window.matchMedia("(min-width: 1100px)");
const SIN_MOVIMIENTO = window.matchMedia("(prefers-reduced-motion: reduce)");

const estado = {
  pedidos: [],
  detalle: null,
  ia: { disponible: false, modelo: null, proveedores: [] },
  filtro: "",
  abiertos: new Set(),   // paquetes con historial abierto
  rechazando: null,      // paquete con el formulario de rechazo abierto
  limite: {},            // paquetes visibles por casilla
  ocupado: new Set(),
  movidos: new Set(),    // paquetes que cambiaron y aún no se han visto
  calma: 0,              // hasta cuándo ignorar "visto" tras un movimiento
  activa: "pendiente",   // casilla visible en el celular
};

const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (n) => Number(n).toLocaleString("es-GT");
const pct = (n) => `${Number(n).toLocaleString("es-GT", { minimumFractionDigits: n % 1 ? 1 : 0, maximumFractionDigits: 1 })} %`;
const plural = (n, uno, varios) => `${fmt(n)} ${n === 1 ? uno : varios}`;
const icono = (id, extra = "") => `<svg class="i ${extra}" aria-hidden="true"><use href="#i-${id}"/></svg>`;
const NOMBRE_PROVEEDOR = { gemini: "Gemini", anthropic: "Claude" };

async function api(ruta, opciones = {}) {
  const r = await fetch(ruta, {
    ...opciones,
    headers: { "Content-Type": "application/json", ...(opciones.headers || {}) },
  });
  let datos = null;
  try { datos = await r.json(); } catch { /* sin cuerpo */ }
  if (!r.ok) {
    const err = new Error(datos?.detail || `Error ${r.status}`);
    err.status = r.status;
    throw err;
  }
  return datos;
}

function aviso(texto, tipo = "") {
  const t = document.createElement("div");
  t.className = `aviso ${tipo}`;
  t.textContent = texto;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), tipo === "error" ? 5500 : 3000);
}

function ocupar(boton, texto) {
  boton.disabled = true;
  boton.setAttribute("aria-busy", "true");
  if (texto) { boton.dataset.texto = boton.innerHTML; boton.textContent = texto; }
}
function liberar(boton) {
  boton.disabled = false;
  boton.removeAttribute("aria-busy");
  if (boton.dataset.texto) { boton.innerHTML = boton.dataset.texto; delete boton.dataset.texto; }
}

/* ---------- Tema: sistema → claro → oscuro ---------- */

const TEMAS = ["sistema", "claro", "oscuro"];
function temaGuardado() {
  try { const t = localStorage.getItem("tema"); return TEMAS.includes(t) ? t : "sistema"; } catch { return "sistema"; }
}
function aplicarTema(t) {
  const raiz = document.documentElement;
  if (t === "sistema") delete raiz.dataset.theme;
  else raiz.dataset.theme = t === "claro" ? "light" : "dark";
  const boton = $("#tema");
  boton.innerHTML = icono(t);
  boton.setAttribute("aria-label", `Tema: ${t}. Cambiar tema`);
  boton.title = `Tema: ${t}`;
}
$("#tema").addEventListener("click", () => {
  const t = TEMAS[(TEMAS.indexOf(temaGuardado()) + 1) % TEMAS.length];
  try { localStorage.setItem("tema", t); } catch { /* sin almacenamiento */ }
  aplicarTema(t);
});
aplicarTema(temaGuardado());

/* ---------- Partes reutilizables ---------- */

function unidadesPorEstado(paquetes) {
  const u = Object.fromEntries(ESTADOS.map((e) => [e, 0]));
  for (const p of paquetes) u[p.estado] += p.unidades;
  return u;
}

function barra(segmentos, total, etiqueta) {
  const partes = ESTADOS.filter((e) => segmentos[e] > 0)
    .map((e) => `<span class="seg ${e}" style="flex-grow:${segmentos[e]}" title="${NOMBRE[e]}: ${fmt(Math.round(segmentos[e]))} u"></span>`)
    .join("");
  return `<div class="barra" role="img" aria-label="${esc(etiqueta)}">${total ? partes : ""}</div>`;
}

// La lista no trae las unidades por estado; se aproxima con el conteo de
// paquetes salvo el de "listo", que sí se conoce exacto por el avance.
function segmentosLista(p) {
  const r = p.resumen;
  const listas = r.unidades_listas;
  const resto = r.unidades_totales - listas;
  const paqNoListos = r.total_paquetes - r.conteo.listo;
  const s = { listo: listas };
  for (const e of ["pendiente", "en_proceso", "revision"]) {
    s[e] = paqNoListos ? (resto * r.conteo[e]) / paqNoListos : 0;
  }
  return s;
}

function textoIA(t) {
  // Markdown mínimo: viñetas y negritas. Se escapa primero.
  const lineas = esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").split(/\n+/);
  let html = "", lista = false;
  for (const l of lineas) {
    const m = l.match(/^\s*[-•*]\s+(.*)/);
    if (m) {
      if (!lista) { html += "<ul>"; lista = true; }
      html += `<li>${m[1]}</li>`;
    } else if (l.trim()) {
      if (lista) { html += "</ul>"; lista = false; }
      html += `<p>${l}</p>`;
    }
  }
  return html + (lista ? "</ul>" : "");
}

function nombreModelo(modelo) {
  if (!modelo) return "IA";
  if (modelo.startsWith("gemini")) return "Gemini";
  if (modelo.startsWith("claude")) return "Claude";
  return modelo;
}

/* ---------- Encabezado ---------- */

function renderKpis() {
  const ps = estado.pedidos;
  const total = ps.reduce((a, p) => a + p.cantidad, 0);
  const listas = ps.reduce((a, p) => a + p.resumen.unidades_listas, 0);
  const revision = ps.reduce((a, p) => a + p.resumen.conteo.revision, 0);
  const completos = ps.filter((p) => p.resumen.avance === 100).length;
  $("#kpis").innerHTML = [
    ["Pedidos", fmt(ps.length)],
    ["Completos", `${fmt(completos)}<small> / ${fmt(ps.length)}</small>`],
    ["Unidades", fmt(total)],
    ["En revisión", `${fmt(revision)}<small> paq.</small>`],
    ["Avance global", total ? pct(Math.round((listas * 1000) / total) / 10) : "—"],
  ].map(([k, v]) => `<div><dt class="etq">${k}</dt><dd>${v}</dd></div>`).join("");
  $("#cuenta").textContent = ps.length ? `· ${fmt(ps.length)}` : "";
}

function renderIA() {
  const caja = $("#ia-estado");
  const ia = estado.ia;
  caja.hidden = false;
  caja.dataset.activa = String(ia.disponible);
  if (!ia.disponible) {
    $("#ia-estado-txt").textContent = "IA no configurada";
    caja.title = "Las funciones de IA no están configuradas en este servidor.";
    return;
  }
  const nombres = ia.proveedores.map((p) => NOMBRE_PROVEEDOR[p] || p);
  $("#ia-estado-txt").textContent = `IA · ${nombreModelo(ia.modelo)}`;
  caja.title = `IA activa. Orden: ${nombres.join(" → ")}. Si uno falla, responde el siguiente.`;
}

/* ---------- Lista ---------- */

function renderLista() {
  const f = estado.filtro.trim().toLowerCase();
  const ps = estado.pedidos.filter((p) => !f || p.numero.toLowerCase().includes(f) || p.cliente.toLowerCase().includes(f));
  const ul = $("#lista");
  ul.removeAttribute("aria-busy");
  if (!estado.pedidos.length) {
    ul.innerHTML = `<li class="vacio"><strong>Aún no hay pedidos</strong>Abre “Nuevo pedido”, escribe número, cliente y cantidad, y el sistema lo divide en paquetes.</li>`;
    return;
  }
  if (!ps.length) {
    ul.innerHTML = `<li class="vacio"><strong>Sin resultados</strong>Ningún pedido coincide con “${esc(estado.filtro)}”.</li>`;
    return;
  }
  const sel = estado.detalle?.numero;
  ul.innerHTML = ps.map((p) => {
    const r = p.resumen;
    const conteos = ESTADOS.map((e) => `<span><i class="pt ${e}"></i><b>${r.conteo[e]}</b> ${NOMBRE[e]}</span>`).join("");
    return `<li><button type="button" class="fila" data-numero="${esc(p.numero)}" ${p.numero === sel ? 'aria-current="true"' : ""}>
      <span class="id">
        <span class="numero">${esc(p.numero)}</span>
        <span class="cliente" title="${esc(p.cliente)}">${esc(p.cliente)}</span>
      </span>
      <span><span class="pct">${pct(r.avance)}</span><span class="unid">${fmt(p.cantidad)} u</span></span>
      ${barra(segmentosLista(p), r.unidades_totales, `Avance ${r.avance} %`)}
      <span class="conteos">${conteos}</span>
    </button></li>`;
  }).join("");
}

/* ---------- Detalle ---------- */

function fichaPaquete(p) {
  const ocupado = estado.ocupado.has(p.id) ? "disabled" : "";
  const busy = estado.ocupado.has(p.id) ? 'aria-busy="true"' : "";
  let botones = "";
  if (p.estado !== "listo") {
    botones = `<button class="btn btn-sm" data-avanzar="${p.id}" ${ocupado} ${busy}>${icono("avanzar")}A ${NOMBRE[SIGUIENTE[p.estado]].toLowerCase()}</button>`;
  }
  if (p.estado === "revision") {
    botones += `<button class="btn btn-sm btn-peligro" data-abrir-rechazo="${p.id}" ${ocupado}>${icono("rechazar")}Rechazar</button>`;
  }
  const rechazo = estado.rechazando === p.id ? `
    <form class="rechazo" data-rechazo="${p.id}">
      <label for="motivo-${p.id}">Motivo del rechazo <span style="font-weight:400">(opcional)</span></label>
      <input id="motivo-${p.id}" name="motivo" maxlength="300" placeholder="Ej.: etiqueta mal impresa" autocomplete="off">
      <div class="fila-btn">
        <button class="btn btn-sm btn-peligro lleno" type="submit">Confirmar rechazo</button>
        <button class="btn btn-sm" type="button" data-cancelar-rechazo>Cancelar</button>
      </div>
    </form>` : "";
  const abierto = estado.abiertos.has(p.id);
  const hist = abierto ? `<ul class="hist" data-hist="${p.id}"><li>Cargando…</li></ul>` : "";
  const movida = estado.movidos.has(p.id);
  return `<article class="ficha ${p.estado} ${movida ? "movida" : ""} ${ocupado ? "ocupada" : ""}" data-paquete="${p.id}" aria-label="Paquete ${p.indice}, ${p.unidades} unidades, ${NOMBRE[p.estado]}">
    ${movida ? `<span class="marca-movida etq">Movido</span>` : ""}
    <div class="linea"><span class="nom etq">Paquete ${String(p.indice).padStart(2, "0")}</span><span class="u">${fmt(p.unidades)}<small> u</small></span></div>
    ${botones ? `<div class="botones">${botones}</div>` : ""}
    ${rechazo}
    <button class="btn-txt" data-historial="${p.id}" aria-expanded="${abierto}">${icono("historial")}${abierto ? "Ocultar historial" : "Historial"}</button>
    ${hist}
  </article>`;
}

function casillaInicial(d) {
  return ESTADOS.find((e) => e !== "listo" && d.paquetes.some((p) => p.estado === e)) || "listo";
}

function renderDetalle() {
  const d = estado.detalle;
  const sec = $("#detalle");
  $("#inicio").hidden = Boolean(d);
  if (!d) { sec.hidden = true; return; }
  sec.hidden = false;
  const r = d.resumen;
  const u = unidadesPorEstado(d.paquetes);

  const pestanas = ESTADOS.map((e) => {
    const n = d.paquetes.filter((p) => p.estado === e).length;
    const nuevo = d.paquetes.some((p) => p.estado === e && estado.movidos.has(p.id) && e !== estado.activa);
    return `<button type="button" class="pestana ${e}" role="tab" id="tab-${e}" aria-controls="casilla-${e}" aria-selected="${e === estado.activa}" data-casilla="${e}">
      <span class="etq">${NOMBRE[e]}</span><b>${n}</b>
      ${nuevo ? `<span class="nuevo" aria-label="con cambios"></span>` : ""}
    </button>`;
  }).join("");

  const casillas = ESTADOS.map((e) => {
    const todos = d.paquetes.filter((p) => p.estado === e);
    const lim = estado.limite[e] || POR_COLUMNA;
    const visibles = todos.slice(0, lim);
    const mas = todos.length > lim ? `<button class="btn btn-sm mas" data-mas="${e}">Mostrar ${Math.min(POR_COLUMNA, todos.length - lim)} más (${todos.length - lim} ocultos)</button>` : "";
    return `<section class="casilla ${e} ${e === estado.activa ? "activa" : ""}" id="casilla-${e}" role="tabpanel" aria-labelledby="tab-${e}" aria-label="${NOMBRE[e]}">
      <h3 class="casilla-cab"><span class="etq"><i class="pt ${e}"></i>${NOMBRE[e]}</span><span class="cnt">${todos.length} · ${fmt(u[e])} u</span></h3>
      <div class="fichas">${visibles.map(fichaPaquete).join("") || `<div class="casilla-vacia">Sin paquetes</div>`}${mas}</div>
    </section>`;
  }).join("");

  const extra = [plural(d.cantidad, "unidad", "unidades"), plural(r.total_paquetes, "paquete", "paquetes")];
  if (d.rechazos) extra.push(plural(d.rechazos, "rechazo", "rechazos"));

  sec.innerHTML = `
    <div class="detalle-cab">
      <div>
        <h2>${esc(d.numero)}</h2>
        <p class="sub">${esc(d.cliente)} · ${extra.join(" · ")}</p>
      </div>
      <div class="acciones">
        ${estado.ia.disponible ? `<button class="btn btn-sm" data-resumen="${esc(d.numero)}">${icono("ia")}<span>Resumen<span class="txt-largo"> con IA</span></span></button>` : ""}
        <button class="btn-icono" data-cerrar aria-label="Cerrar pedido" title="Cerrar">${icono("cerrar")}</button>
      </div>
    </div>
    <div class="avance">
      ${barra(u, d.cantidad, `Avance ${r.avance} %`)}
      <div class="pct">${pct(r.avance)}</div>
      <div class="det">${fmt(r.unidades_listas)} de ${fmt(r.unidades_totales)} unidades listas</div>
    </div>
    <div class="ia-salida" data-salida="${esc(d.numero)}" aria-live="polite"></div>
    <div class="pestanas" role="tablist" aria-label="Estados">${pestanas}</div>
    <div class="tablero" data-activa="${estado.activa}">${casillas}</div>`;

  for (const id of estado.abiertos) cargarHistorial(id);
  const motivo = sec.querySelector("form.rechazo input");
  if (motivo) motivo.focus();
}

// Desliza cada ficha desde su posición anterior (FLIP).
function posiciones() {
  const m = new Map();
  for (const el of document.querySelectorAll("[data-paquete]")) m.set(el.dataset.paquete, el.getBoundingClientRect());
  return m;
}
function deslizar(antes) {
  if (SIN_MOVIMIENTO.matches || !antes.size) return;
  for (const el of document.querySelectorAll("[data-paquete]")) {
    const a = antes.get(el.dataset.paquete);
    if (!a) continue;
    const b = el.getBoundingClientRect();
    const dx = a.left - b.left, dy = a.top - b.top;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
    el.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
      { duration: 280, easing: "cubic-bezier(.2,.8,.2,1)" },
    );
  }
}

async function cargarHistorial(id) {
  try {
    const ev = await api(`/api/paquetes/${id}/historial`);
    const ul = document.querySelector(`[data-hist="${id}"]`);
    if (!ul) return;
    ul.innerHTML = ev.length ? ev.map((e) => {
      const f = new Date(e.creado_en).toLocaleString("es-GT", { dateStyle: "short", timeStyle: "short" });
      const accion = e.accion === "rechazar" ? "Rechazado" : "Avanzó";
      return `<li><span class="fecha">${f}</span> · ${accion}: ${NOMBRE[e.estado_origen]} → ${NOMBRE[e.estado_destino]}${e.motivo ? ` <span class="mot">“${esc(e.motivo)}”</span>` : ""}</li>`;
    }).join("") : `<li>Sin movimientos todavía.</li>`;
  } catch (e) {
    aviso(e.message, "error");
  }
}

/* ---------- Carga ---------- */

async function cargarPedidos() {
  estado.pedidos = await api("/api/pedidos");
  renderKpis();
  renderLista();
}

async function abrir(numero, { desplazar = true } = {}) {
  try {
    const d = await api(`/api/pedidos/${encodeURIComponent(numero)}`);
    if (estado.detalle?.numero !== d.numero) {
      estado.abiertos.clear();
      estado.movidos.clear();
      estado.rechazando = null;
      estado.limite = {};
      estado.activa = casillaInicial(d);
    }
    estado.detalle = d;
    history.replaceState(null, "", `#${encodeURIComponent(d.numero)}`);
    renderDetalle();
    renderLista();
    if (desplazar && !ESCRITORIO.matches) {
      $("#detalle").scrollIntoView({ behavior: SIN_MOVIMIENTO.matches ? "auto" : "smooth", block: "start" });
    }
    if (desplazar) $("#detalle").focus({ preventScroll: true });
  } catch (e) {
    if (e.status === 404) history.replaceState(null, "", location.pathname);
    aviso(e.message, "error");
  }
}

function cerrar() {
  const numero = estado.detalle?.numero;
  estado.detalle = null;
  history.replaceState(null, "", location.pathname);
  renderDetalle();
  renderLista();
  const fila = numero && document.querySelector(`.fila[data-numero="${CSS.escape(numero)}"]`);
  if (fila) fila.focus();
}

function aplicarMovimiento(mov) {
  const d = estado.detalle;
  if (d) {
    const i = d.paquetes.findIndex((p) => p.id === mov.paquete.id);
    if (i >= 0) d.paquetes[i] = mov.paquete;
    Object.assign(d, { resumen: mov.pedido.resumen, rechazos: mov.pedido.rechazos });
  }
  const j = estado.pedidos.findIndex((p) => p.id === mov.pedido.id);
  if (j >= 0) estado.pedidos[j] = mov.pedido;
  estado.movidos.add(mov.paquete.id);
  estado.calma = Date.now() + 900;
  const antes = posiciones();
  renderKpis();
  renderLista();
  renderDetalle();
  deslizar(antes);
}

async function mover(id, accion, cuerpo) {
  if (estado.ocupado.has(id)) return;
  estado.ocupado.add(id);
  renderDetalle();
  try {
    const mov = await api(`/api/paquetes/${id}/${accion}`, { method: "POST", body: cuerpo ? JSON.stringify(cuerpo) : undefined });
    estado.rechazando = null;
    estado.ocupado.delete(id);
    aplicarMovimiento(mov);
    const destino = NOMBRE[mov.paquete.estado];
    if (mov.pedido.resumen.avance === 100 && accion === "avanzar") aviso(`Pedido ${mov.pedido.numero} completo.`);
    else if (MOVIL.matches) aviso(`Paquete ${mov.paquete.indice} pasó a ${destino}.`);
    // En el celular el paquete sale de la casilla visible: se devuelve el foco a la casilla.
    const sigue = document.querySelector(`[data-paquete="${id}"] [data-avanzar]`);
    if (sigue && !MOVIL.matches) sigue.focus();
    else $(`#tab-${estado.activa}`)?.focus({ preventScroll: true });
  } catch (e) {
    estado.ocupado.delete(id);
    aviso(e.message, "error");
    if (estado.detalle) abrir(estado.detalle.numero, { desplazar: false });
  }
}

/* ---------- Formulario ---------- */

const form = $("#form-pedido");
const campos = { numero: $("#f-numero"), cliente: $("#f-cliente"), cantidad: $("#f-cantidad") };

function errorCampo(nombre, msg) {
  $(`#e-${nombre}`).textContent = msg || "";
  campos[nombre].setAttribute("aria-invalid", msg ? "true" : "false");
}

function validar() {
  const errores = {};
  if (!campos.numero.value.trim()) errores.numero = "Escribe el número de pedido.";
  if (!campos.cliente.value.trim()) errores.cliente = "Escribe el nombre del cliente.";
  const c = campos.cantidad.value.trim();
  if (!c) errores.cantidad = "Escribe la cantidad de unidades.";
  else if (!/^\d+$/.test(c)) errores.cantidad = "Debe ser un número entero, sin decimales ni signos.";
  else if (Number(c) <= 0) errores.cantidad = "Debe ser mayor que cero.";
  else if (Number(c) > MAX_UNIDADES) errores.cantidad = `El máximo es ${fmt(MAX_UNIDADES)} unidades.`;
  return errores;
}

function vistaPrevia() {
  const c = campos.cantidad.value.trim();
  const caja = $("#vista-previa");
  if (!/^\d+$/.test(c) || Number(c) <= 0 || Number(c) > MAX_UNIDADES) { caja.innerHTML = ""; return; }
  const n = Number(c), llenos = Math.floor(n / 100), resto = n % 100;
  const total = llenos + (resto ? 1 : 0);
  const chips = [];
  const mostrar = Math.min(llenos, 8);
  for (let i = 0; i < mostrar; i++) chips.push("100");
  if (llenos > mostrar) chips.push(`+${fmt(llenos - mostrar)} de 100`);
  if (resto) chips.push(String(resto));
  caja.innerHTML = `Se dividirá en <b>${plural(total, "paquete", "paquetes")}</b>:<div class="chips">${chips.map((x) => `<span>${x}</span>`).join("")}</div>`;
}

campos.cantidad.addEventListener("input", () => { vistaPrevia(); if ($("#e-cantidad").textContent) errorCampo("cantidad", validar().cantidad); });
for (const n of ["numero", "cliente"]) campos[n].addEventListener("input", () => { if ($(`#e-${n}`).textContent) errorCampo(n, validar()[n]); });

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("#e-form").textContent = "";
  const errores = validar();
  for (const n of Object.keys(campos)) errorCampo(n, errores[n]);
  const primero = Object.keys(campos).find((n) => errores[n]);
  if (primero) { campos[primero].focus(); return; }

  const btn = $("#btn-crear");
  ocupar(btn, "Registrando…");
  try {
    const p = await api("/api/pedidos", {
      method: "POST",
      body: JSON.stringify({ numero: campos.numero.value.trim(), cliente: campos.cliente.value.trim(), cantidad: Number(campos.cantidad.value.trim()) }),
    });
    form.reset();
    vistaPrevia();
    $("#ia-texto").value = "";
    $("#ia-nota").hidden = true;
    aviso(`Pedido ${p.numero} registrado en ${plural(p.resumen.total_paquetes, "paquete", "paquetes")}.`);
    $("#alta").open = false;
    await cargarPedidos();
    abrir(p.numero);
  } catch (e) {
    if (e.status === 409) { errorCampo("numero", e.message); campos.numero.focus(); }
    else $("#e-form").textContent = e.message;
  } finally {
    liberar(btn);
  }
});

/* ---------- IA ---------- */

$("#ia-interpretar").addEventListener("click", async () => {
  const texto = $("#ia-texto").value.trim();
  const nota = $("#ia-nota");
  if (texto.length < 3) { nota.hidden = false; nota.textContent = "Escribe el pedido primero."; $("#ia-texto").focus(); return; }
  const btn = $("#ia-interpretar");
  ocupar(btn, "Interpretando…");
  try {
    const b = await api("/api/ia/interpretar", { method: "POST", body: JSON.stringify({ texto }) });
    for (const n of ["numero", "cliente", "cantidad"]) {
      if (b[n] != null) { campos[n].value = b[n]; errorCampo(n, ""); }
    }
    vistaPrevia();
    const partes = [];
    if (b.faltantes.length) partes.push(`Completa: ${b.faltantes.map((f) => ({ numero: "número", cliente: "cliente", cantidad: "cantidad" })[f]).join(", ")}.`);
    if (b.nota) partes.push(b.nota);
    partes.push("Revisa los datos y pulsa Registrar pedido.");
    nota.hidden = false;
    nota.textContent = partes.join(" ");
    const falta = b.faltantes[0];
    (falta ? campos[falta] : $("#btn-crear")).focus();
  } catch (e) {
    nota.hidden = false;
    nota.textContent = e.message;
  } finally {
    liberar(btn);
  }
});

async function resumenIA(numero, boton) {
  const salida = document.querySelector(`[data-salida="${CSS.escape(numero)}"]`);
  ocupar(boton);
  salida.innerHTML = `<p class="cargando">Analizando ${numero ? "el pedido" : "los pedidos"}…</p>`;
  try {
    const r = await api("/api/ia/resumen", { method: "POST", body: JSON.stringify(numero ? { numero } : {}) });
    const quien = r.modelo ? ` con ${nombreModelo(r.modelo)}` : "";
    salida.innerHTML = textoIA(r.texto) + `<p class="pie">Generado${quien} a partir de los datos actuales.</p>`;
    if (r.modelo) { estado.ia.modelo = r.modelo; renderIA(); }
  } catch (e) {
    salida.innerHTML = `<p>${esc(e.message)}</p>`;
  } finally {
    liberar(boton);
  }
}

/* ---------- Eventos ---------- */

document.addEventListener("click", (ev) => {
  const t = ev.target.closest("button");
  if (!t) return;
  if (t.matches(".fila")) return abrir(t.dataset.numero);
  if (t.dataset.casilla) { estado.activa = t.dataset.casilla; return renderDetalle(); }
  if (t.dataset.avanzar) return mover(Number(t.dataset.avanzar), "avanzar");
  if (t.dataset.abrirRechazo) { estado.rechazando = Number(t.dataset.abrirRechazo); return renderDetalle(); }
  if (t.hasAttribute("data-cancelar-rechazo")) { estado.rechazando = null; return renderDetalle(); }
  if (t.dataset.historial) {
    const id = Number(t.dataset.historial);
    estado.abiertos.has(id) ? estado.abiertos.delete(id) : estado.abiertos.add(id);
    renderDetalle();
    return document.querySelector(`[data-historial="${id}"]`)?.focus();
  }
  if (t.dataset.mas) { estado.limite[t.dataset.mas] = (estado.limite[t.dataset.mas] || POR_COLUMNA) + POR_COLUMNA; return renderDetalle(); }
  if (t.hasAttribute("data-cerrar")) return cerrar();
  if (t.hasAttribute("data-resumen")) return resumenIA(t.dataset.resumen, t);
});

// La marca "Movido" se quita cuando la persona ve la ficha (puntero o foco).
function visto(ev) {
  if (Date.now() < estado.calma) return;
  const f = ev.target.closest?.(".ficha.movida");
  if (!f) return;
  estado.movidos.delete(Number(f.dataset.paquete));
  f.classList.remove("movida");
  f.querySelector(".marca-movida")?.remove();
}
document.addEventListener("pointerover", (ev) => { if (ev.pointerType === "mouse") visto(ev); });
document.addEventListener("focusin", visto);
document.addEventListener("touchstart", visto, { passive: true });

document.addEventListener("submit", (ev) => {
  const f = ev.target.closest("form.rechazo");
  if (!f) return;
  ev.preventDefault();
  const motivo = f.motivo.value.trim();
  mover(Number(f.dataset.rechazo), "rechazar", motivo ? { motivo } : {});
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && estado.rechazando) { estado.rechazando = null; renderDetalle(); return; }
  // Flechas entre pestañas de casilla (patrón de tabs accesibles).
  if (ev.target.matches?.(".pestana") && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) {
    const i = ESTADOS.indexOf(estado.activa) + (ev.key === "ArrowRight" ? 1 : -1);
    estado.activa = ESTADOS[(i + ESTADOS.length) % ESTADOS.length];
    renderDetalle();
    $(`#tab-${estado.activa}`).focus();
  }
});

$("#buscar").addEventListener("input", (ev) => { estado.filtro = ev.target.value; renderLista(); });

(async function iniciar() {
  try {
    estado.ia = await api("/api/ia/estado");
  } catch { /* sin IA */ }
  renderIA();
  $("#ia-caja").hidden = !estado.ia.disponible;
  $("#ia-resumen-global").hidden = !estado.ia.disponible;
  try {
    await cargarPedidos();
    // El alta se abre sola solo si no hay pedidos; si los hay, manda la lista.
    $("#alta").open = !estado.pedidos.length;
  } catch (e) {
    $("#lista").innerHTML = `<li class="vacio"><strong>No se pudieron cargar los pedidos</strong>${esc(e.message)}</li>`;
    aviso("No se pudieron cargar los pedidos.", "error");
  }
  const h = decodeURIComponent(location.hash.slice(1));
  if (h) abrir(h, { desplazar: false });
})();
