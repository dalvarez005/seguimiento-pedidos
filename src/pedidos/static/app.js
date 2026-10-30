"use strict";

const ESTADOS = ["pendiente", "en_proceso", "revision", "listo"];
const NOMBRE = { pendiente: "Pendiente", en_proceso: "En proceso", revision: "Revisión", listo: "Listo" };
const SIGUIENTE = { pendiente: "en_proceso", en_proceso: "revision", revision: "listo" };
const MAX_UNIDADES = 100000;
const POR_COLUMNA = 24;

const estado = {
  pedidos: [],
  detalle: null,
  ia: false,
  filtro: "",
  abiertos: new Set(),   // paquetes con historial abierto
  rechazando: null,      // paquete con el formulario de rechazo abierto
  limite: {},            // paquetes visibles por columna
  ocupado: new Set(),
};

const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (n) => Number(n).toLocaleString("es-GT");
const pct = (n) => `${Number(n).toLocaleString("es-GT", { minimumFractionDigits: n % 1 ? 1 : 0, maximumFractionDigits: 1 })} %`;

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
  t.className = `toast ${tipo}`;
  t.textContent = texto;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), tipo === "error" ? 5000 : 2800);
}

/* ---------- Partes reutilizables ---------- */

function unidadesPorEstado(paquetes) {
  const u = Object.fromEntries(ESTADOS.map((e) => [e, 0]));
  for (const p of paquetes) u[p.estado] += p.unidades;
  return u;
}

function barra(segmentos, total, etiqueta) {
  const partes = ESTADOS.filter((e) => segmentos[e] > 0)
    .map((e) => `<span class="seg ${e}" style="flex-grow:${segmentos[e]}" title="${NOMBRE[e]}: ${fmt(segmentos[e])}"></span>`)
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

/* ---------- Encabezado ---------- */

function renderKpis() {
  const ps = estado.pedidos;
  const total = ps.reduce((a, p) => a + p.cantidad, 0);
  const listas = ps.reduce((a, p) => a + p.resumen.unidades_listas, 0);
  const revision = ps.reduce((a, p) => a + p.resumen.conteo.revision, 0);
  const completos = ps.filter((p) => p.resumen.avance === 100).length;
  $("#kpis").innerHTML = [
    ["Pedidos", fmt(ps.length)],
    ["Completos", fmt(completos)],
    ["Unidades", fmt(total)],
    ["En revisión", fmt(revision)],
    ["Avance global", total ? pct(Math.round((listas * 1000) / total) / 10) : "—"],
  ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
}

/* ---------- Lista ---------- */

function renderLista() {
  const f = estado.filtro.trim().toLowerCase();
  const ps = estado.pedidos.filter((p) => !f || p.numero.toLowerCase().includes(f) || p.cliente.toLowerCase().includes(f));
  const ul = $("#lista");
  if (!estado.pedidos.length) {
    ul.innerHTML = `<li class="vacio"><strong>Aún no hay pedidos</strong>Registra el primero con el formulario.</li>`;
    return;
  }
  if (!ps.length) {
    ul.innerHTML = `<li class="vacio">Ningún pedido coincide con “${esc(estado.filtro)}”.</li>`;
    return;
  }
  const sel = estado.detalle?.numero;
  ul.innerHTML = ps.map((p) => {
    const r = p.resumen;
    const conteos = ESTADOS.map((e) => `<span><i class="pt ${e}"></i><b>${r.conteo[e]}</b> ${NOMBRE[e]}</span>`).join("");
    return `<li class="fila" tabindex="0" data-numero="${esc(p.numero)}" ${p.numero === sel ? 'aria-current="true"' : ""}>
      <div class="id">
        <div class="numero">${esc(p.numero)}</div>
        <div class="cliente" title="${esc(p.cliente)}">${esc(p.cliente)}</div>
      </div>
      <div class="barra-wrap">
        ${barra(segmentosLista(p), r.unidades_totales, `Avance ${r.avance} %`)}
        <div class="conteos">${conteos}</div>
      </div>
      <div><div class="pct">${pct(r.avance)}</div><div class="unid num" style="text-align:right">${fmt(p.cantidad)} u</div></div>
    </li>`;
  }).join("");
}

/* ---------- Detalle ---------- */

function tarjetaPaquete(p) {
  const ocupado = estado.ocupado.has(p.id) ? "disabled" : "";
  let botones = "";
  if (p.estado !== "listo") {
    botones = `<button class="btn btn-sec btn-sm" data-avanzar="${p.id}" ${ocupado}>→ ${NOMBRE[SIGUIENTE[p.estado]]}</button>`;
  }
  if (p.estado === "revision") {
    botones += `<button class="btn btn-peligro btn-sm" data-abrir-rechazo="${p.id}" ${ocupado}>Rechazar</button>`;
  }
  const rechazo = estado.rechazando === p.id ? `
    <form class="rechazo" data-rechazo="${p.id}">
      <input name="motivo" maxlength="300" placeholder="Motivo (opcional)" aria-label="Motivo del rechazo" autocomplete="off">
      <div class="fila-btn">
        <button class="btn btn-peligro btn-sm" type="submit">Confirmar rechazo</button>
        <button class="btn btn-sec btn-sm" type="button" data-cancelar-rechazo>Cancelar</button>
      </div>
    </form>` : "";
  const hist = estado.abiertos.has(p.id) ? `<ul class="hist" data-hist="${p.id}"><li class="cargando">Cargando…</li></ul>` : "";
  return `<article class="paq ${p.estado}" data-paquete="${p.id}">
    <div class="linea"><span class="nom">Paquete ${p.indice}</span><span class="u">${fmt(p.unidades)} u</span></div>
    ${botones ? `<div class="botones">${botones}</div>` : ""}
    ${rechazo}
    <button class="btn-txt" data-historial="${p.id}" aria-expanded="${estado.abiertos.has(p.id)}">${estado.abiertos.has(p.id) ? "Ocultar historial" : "Historial"}</button>
    ${hist}
  </article>`;
}

function renderDetalle() {
  const d = estado.detalle;
  const sec = $("#detalle");
  if (!d) { sec.hidden = true; return; }
  sec.hidden = false;
  const r = d.resumen;
  const u = unidadesPorEstado(d.paquetes);
  const columnas = ESTADOS.map((e) => {
    const todos = d.paquetes.filter((p) => p.estado === e);
    const lim = estado.limite[e] || POR_COLUMNA;
    const visibles = todos.slice(0, lim);
    const mas = todos.length > lim ? `<button class="btn btn-sec btn-sm mas" data-mas="${e}">Mostrar ${Math.min(POR_COLUMNA, todos.length - lim)} más (${todos.length - lim} ocultos)</button>` : "";
    return `<section class="columna" aria-label="${NOMBRE[e]}">
      <h3><span><i class="pt ${e}"></i>${NOMBRE[e]}</span><span class="cnt">${todos.length} · ${fmt(u[e])} u</span></h3>
      <div class="paquetes">${visibles.map(tarjetaPaquete).join("") || `<div class="col-vacia">Sin paquetes</div>`}${mas}</div>
    </section>`;
  }).join("");

  sec.innerHTML = `
    <div class="detalle-cab">
      <div>
        <h2>${esc(d.numero)}</h2>
        <div class="sub">${esc(d.cliente)} · ${fmt(d.cantidad)} unidades en ${r.total_paquetes} paquete${r.total_paquetes === 1 ? "" : "s"}${d.rechazos ? ` · ${d.rechazos} rechazo${d.rechazos === 1 ? "" : "s"}` : ""}</div>
      </div>
      <div class="acciones">
        ${estado.ia ? `<button class="btn btn-sec btn-sm" data-resumen="${esc(d.numero)}">Resumen con IA</button>` : ""}
        <button class="btn btn-sec btn-sm" data-cerrar>Cerrar</button>
      </div>
    </div>
    <div class="avance-grande">
      ${barra(u, d.cantidad, `Avance ${r.avance} %`)}
      <div><div class="pct">${pct(r.avance)}</div><div class="det num">${fmt(r.unidades_listas)} / ${fmt(r.unidades_totales)} u listas</div></div>
    </div>
    <div class="tablero">${columnas}</div>
    <div class="ia-panel ia-texto-salida" data-salida="${esc(d.numero)}"></div>`;

  for (const id of estado.abiertos) cargarHistorial(id);
  const form = sec.querySelector("form.rechazo input");
  if (form) form.focus();
}

async function cargarHistorial(id) {
  try {
    const ev = await api(`/api/paquetes/${id}/historial`);
    const ul = document.querySelector(`[data-hist="${id}"]`);
    if (!ul) return;
    ul.innerHTML = ev.length ? ev.map((e) => {
      const f = new Date(e.creado_en).toLocaleString("es-GT", { dateStyle: "short", timeStyle: "short" });
      const accion = e.accion === "rechazar" ? "Rechazado" : "Avanzó";
      return `<li><span class="num">${f}</span> · ${accion}: ${NOMBRE[e.estado_origen]} → ${NOMBRE[e.estado_destino]}${e.motivo ? ` <span class="mot">“${esc(e.motivo)}”</span>` : ""}</li>`;
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
      estado.rechazando = null;
      estado.limite = {};
    }
    estado.detalle = d;
    history.replaceState(null, "", `#${encodeURIComponent(d.numero)}`);
    renderDetalle();
    renderLista();
    if (desplazar) $("#detalle").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    if (e.status === 404) history.replaceState(null, "", location.pathname);
    aviso(e.message, "error");
  }
}

function cerrar() {
  estado.detalle = null;
  history.replaceState(null, "", location.pathname);
  renderDetalle();
  renderLista();
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
  renderKpis();
  renderLista();
  renderDetalle();
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
    if (mov.pedido.resumen.avance === 100 && accion === "avanzar") aviso(`Pedido ${mov.pedido.numero} completo.`);
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
  if (llenos > mostrar) chips.push(`… ${llenos - mostrar} más de 100`);
  if (resto) chips.push(String(resto));
  caja.innerHTML = `Se dividirá en <b>${fmt(total)}</b> paquete${total === 1 ? "" : "s"}:<div class="chips">${chips.map((x) => `<span>${x}</span>`).join("")}</div>`;
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
  btn.disabled = true;
  btn.textContent = "Registrando…";
  try {
    const p = await api("/api/pedidos", {
      method: "POST",
      body: JSON.stringify({ numero: campos.numero.value.trim(), cliente: campos.cliente.value.trim(), cantidad: Number(campos.cantidad.value.trim()) }),
    });
    form.reset();
    vistaPrevia();
    $("#ia-texto").value = "";
    $("#ia-nota").hidden = true;
    aviso(`Pedido ${p.numero} registrado en ${p.resumen.total_paquetes} paquete${p.resumen.total_paquetes === 1 ? "" : "s"}.`);
    await cargarPedidos();
    abrir(p.numero);
  } catch (e) {
    if (e.status === 409) { errorCampo("numero", e.message); campos.numero.focus(); }
    else $("#e-form").textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Registrar pedido";
  }
});

/* ---------- IA ---------- */

$("#ia-interpretar").addEventListener("click", async () => {
  const texto = $("#ia-texto").value.trim();
  const nota = $("#ia-nota");
  if (texto.length < 3) { nota.hidden = false; nota.textContent = "Escribe el pedido primero."; return; }
  const btn = $("#ia-interpretar");
  btn.disabled = true;
  btn.textContent = "Interpretando…";
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
    btn.disabled = false;
    btn.textContent = "Llenar formulario";
  }
});

async function resumenIA(numero, boton) {
  const salida = document.querySelector(`[data-salida="${CSS.escape(numero)}"]`);
  boton.disabled = true;
  salida.innerHTML = `<p class="cargando">Analizando ${numero ? "el pedido" : "los pedidos"}…</p>`;
  try {
    const r = await api("/api/ia/resumen", { method: "POST", body: JSON.stringify(numero ? { numero } : {}) });
    salida.innerHTML = textoIA(r.texto) + `<p class="pie">Generado con IA a partir de los datos actuales.</p>`;
  } catch (e) {
    salida.innerHTML = `<p>${esc(e.message)}</p>`;
  } finally {
    boton.disabled = false;
  }
}

/* ---------- Eventos ---------- */

document.addEventListener("click", (ev) => {
  const t = ev.target.closest("button, .fila");
  if (!t) return;
  if (t.matches(".fila")) return abrir(t.dataset.numero);
  if (t.dataset.avanzar) return mover(Number(t.dataset.avanzar), "avanzar");
  if (t.dataset.abrirRechazo) { estado.rechazando = Number(t.dataset.abrirRechazo); return renderDetalle(); }
  if (t.hasAttribute("data-cancelar-rechazo")) { estado.rechazando = null; return renderDetalle(); }
  if (t.dataset.historial) {
    const id = Number(t.dataset.historial);
    estado.abiertos.has(id) ? estado.abiertos.delete(id) : estado.abiertos.add(id);
    return renderDetalle();
  }
  if (t.dataset.mas) { estado.limite[t.dataset.mas] = (estado.limite[t.dataset.mas] || POR_COLUMNA) + POR_COLUMNA; return renderDetalle(); }
  if (t.hasAttribute("data-cerrar")) return cerrar();
  if (t.hasAttribute("data-resumen")) return resumenIA(t.dataset.resumen, t);
});

document.addEventListener("submit", (ev) => {
  const f = ev.target.closest("form.rechazo");
  if (!f) return;
  ev.preventDefault();
  const motivo = f.motivo.value.trim();
  mover(Number(f.dataset.rechazo), "rechazar", motivo ? { motivo } : {});
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && ev.target.matches(".fila")) abrir(ev.target.dataset.numero);
  if (ev.key === "Escape" && estado.rechazando) { estado.rechazando = null; renderDetalle(); }
});

$("#buscar").addEventListener("input", (ev) => { estado.filtro = ev.target.value; renderLista(); });

(async function iniciar() {
  try {
    const ia = await api("/api/ia/estado");
    estado.ia = ia.disponible;
  } catch { estado.ia = false; }
  $("#ia-caja").hidden = !estado.ia;
  $("#ia-resumen-global").hidden = !estado.ia;
  try {
    await cargarPedidos();
  } catch (e) {
    aviso("No se pudieron cargar los pedidos: " + e.message, "error");
  }
  const h = decodeURIComponent(location.hash.slice(1));
  if (h) abrir(h, { desplazar: false });
})();
