# -*- coding: utf-8 -*-
"""
====================================================================
 CONTROL DE NIVEL DE AGUA — PROTOTIPO DE PREVENCIÓN DE INUNDACIONES
 Aplicación web en Dash (Python)
====================================================================
El sistema tiene DOS bombas:
  - Bomba superior (entrada): echa agua al tanque de forma aleatoria (simula la lluvia).
    Es la perturbación que el control debe rechazar.
  - Bomba inferior (drenaje): la maneja el controlador P/PI/PD/PID para mantener el nivel
    bajo y evitar la inundación. Solo puede sacar agua, entre 0 % y su potencia máxima.

Ejecución (desde la carpeta controlapp):
    python dash_app/app.py
y abrir http://127.0.0.1:8050 en el navegador.

Estructura:
    modelo.py        → modelo matemático, simulación con las dos bombas y análisis
    graficos.py      → figuras Plotly (se adaptan al tema claro/oscuro)
    datos_reales.py  → lectura del CSV del ESP32 y comparación real vs. simulación
    app.py           → interfaz: contenido + panel de parámetros (derecha, intercambiable)
    assets/          → estilos, iconos (Lucide), números animados y semáforo; Dash los carga solo

Dependencias:
    pip install -r dash_app/requirements.txt
====================================================================
"""

import os

import numpy as np
import pandas as pd
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update
from dash.dash_table.Format import Format, Scheme
from dash.exceptions import PreventUpdate

import datos_reales as dr
import graficos as gr
from modelo import (DEFAULTS, ESTADO_ZONA, NOMBRE_ZONA, COLOR_ZONA,
                    limpiar_parametros, resumen_para_comparar, simular, texto_ganancias, zona_de)

app = Dash(__name__, title="Control de Nivel · Prevención de inundaciones",
           suppress_callback_exceptions=True)
server = app.server

# Orden de los parámetros del panel (id del componente → clave en modelo.DEFAULTS)
PARAMS = list(DEFAULTS.keys())


# ====================================================================
# COMPONENTES REUTILIZABLES
# ====================================================================
def ico(nombre, clase=""):
    """Icono de línea (Lucide) que toma el color del texto que lo rodea."""
    return html.Span(className=f"ico ico-{nombre} {clase}".strip(), **{"aria-hidden": "true"})


def punto_zona(z):
    """Punto de color del semáforo; siempre va junto al nombre de la zona."""
    return html.Span(className=f"punto punto-{ESTADO_ZONA[z]}")


def semaforo(z, clave=None, texto=None):
    """
    Semáforo físico (tres focos). z = zona encendida (None = apagado).
    En el Resumen, assets/semaforo.js lo sincroniza con la animación del tanque.
    """
    etiqueta = texto if texto is not None else (NOMBRE_ZONA[z] if z is not None else "Sin datos")
    return html.Div(className="semaforo-caja", key=clave, children=[
        html.Div(className=f"semaforo-fisico{'' if z is None else f' sem-z{z}'}", children=[
            html.Span(className="luz luz-roja"), html.Span(className="luz luz-amarilla"),
            html.Span(className="luz luz-verde")]),
        html.Div(html.Span(etiqueta, className="sem-etq-real"), className="sem-etq"),
    ])


def campo_slider(id_, etiqueta, minimo, maximo, paso, ayuda=None):
    return html.Div(className="campo", id=f"fila-{id_}", children=[
        html.Label(etiqueta, htmlFor=id_, title=ayuda),
        dcc.Slider(id=id_, min=minimo, max=maximo, step=paso, value=DEFAULTS[id_], marks=None,
                   updatemode="mouseup", allow_direct_input=True),
    ])


def campo_numero(id_, etiqueta, paso, minimo=None, maximo=None, ayuda=None):
    return html.Div(className="campo", id=f"fila-{id_}", children=[
        html.Label(etiqueta, htmlFor=id_, title=ayuda),
        # Se actualiza al dejar de escribir 0,5 s (no hace falta pulsar Enter ni salir del campo)
        dcc.Input(id=id_, type="number", value=DEFAULTS[id_], step=paso, min=minimo, max=maximo,
                  debounce=0.5, className="entrada"),
    ])


def segmentado(id_, opciones, etiqueta=None, ayuda=None):
    """Botones de opción única con aspecto de control segmentado."""
    return html.Div(className="campo", children=[
        html.Label(etiqueta, title=ayuda) if etiqueta else None,
        dcc.RadioItems(id=id_, value=DEFAULTS[id_], inline=True, className="segmentado",
                       options=[{"label": l, "value": v} for l, v in opciones]),
    ])


def grupo(icono, titulo, hijos, abierto=True):
    return html.Details(className="grupo", open=abierto, children=[
        html.Summary([html.Span(ico(icono), className="grupo-ico"), titulo]),
        html.Div(hijos, className="grupo-cuerpo"),
    ])


def kpi(etiqueta, valor, unidad="", sub="", estado="info", icono="gauge"):
    # El valor real lo pinta React; el script assets/numeros.js lo anima en un span aparte
    # (kpi-anim) para no tocar nodos que React administra.
    return html.Div(className=f"kpi kpi-{estado}", children=[
        html.Div([html.Span(ico(icono), className="kpi-ico"), etiqueta], className="kpi-etiqueta"),
        html.Div([html.Span([html.Span(valor, className="kpi-real"),
                             html.Span(className="kpi-anim", **{"aria-hidden": "true"})],
                            className="kpi-num", **{"data-clave": etiqueta}),
                  html.Span(unidad, className="kpi-unidad") if unidad else None], className="kpi-valor"),
        html.Div(sub, className="kpi-sub") if sub else None,
    ])


def tarjeta(icono, titulo, hijos, sub=None, clase=""):
    return html.Section(className=f"tarjeta {clase}", children=[
        html.Div([html.H3([html.Span(ico(icono), className="tarjeta-ico"), titulo]),
                  html.P(sub) if sub else None], className="tarjeta-cabecera"),
        *hijos,
    ])


def aviso(estado, contenido, icono=None):
    iconos = {"ok": "circle-check", "warn": "triangle-alert", "bad": "siren", "info": "info"}
    return html.Div([html.Span(ico(icono or iconos[estado]), className="aviso-icono"), html.Div(contenido)],
                    className=f"aviso aviso-{estado}")


def como_leer(texto):
    return html.Details(className="como-leer", children=[
        html.Summary([ico("lightbulb"), "¿Cómo leer esto?"]), dcc.Markdown(texto),
    ])


def grafico(fig, clase=""):
    # Altura explícita: sin ella Dash ajusta el gráfico a la altura del contenedor
    return dcc.Graph(figure=fig, config=gr.CONFIG, className=f"grafico {clase}".strip(),
                     style={"height": f"{fig.layout.height}px"})


def leyenda_semaforo(q):
    rangos = [f"< {q['u-am']:g} cm", f"{q['u-am']:g} – {q['u-rojo']:g} cm", f"≥ {q['u-rojo']:g} cm"]
    return html.Div(className="leyenda-semaforo", children=[
        html.Span([punto_zona(k), f"{NOMBRE_ZONA[k]} · {rangos[k]}"], className="leyenda-item") for k in range(3)
    ])


def zona_subida(id_, grande=False):
    """Área para arrastrar o elegir el CSV con las mediciones del ESP32."""
    return dcc.Upload(id=id_, accept=".csv,.txt", multiple=False,
                      className=f"subida{' subida-grande' if grande else ''}",
                      children=html.Div([ico("upload"), html.Span([html.B("Arrastra el CSV del ESP32"),
                                                                   " o haz clic para elegirlo"])]))


def estilo_tabla(tema):
    oscuro = tema == "oscuro"
    return dict(
        style_as_list_view=True,
        style_table={"overflowX": "auto", "borderRadius": "12px"},
        style_header={"backgroundColor": "#15325a" if oscuro else "#1a4f8f",
                      "color": "#e3ecf7" if oscuro else "#ffffff", "fontWeight": "700",
                      "border": "none", "fontSize": "11.5px", "textTransform": "uppercase", "letterSpacing": ".05em"},
        style_cell={"backgroundColor": "#0e1b2f" if oscuro else "#ffffff",
                    "color": "#e3ecf7" if oscuro else "#0b1a2e", "fontFamily": "Inter, sans-serif",
                    "fontSize": "13px", "padding": "9px 12px", "textAlign": "right",
                    "fontVariantNumeric": "tabular-nums",
                    "borderBottom": f"1px solid {'#1c2e48' if oscuro else '#e3ebf5'}"},
        style_data_conditional=[{"if": {"row_index": "odd"},
                                 "backgroundColor": "#0c1829" if oscuro else "#f4f8fd"}],
        style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "left"}
                                for c in ("Simulación", "Zona máx.", "Alerta", "Señal", "Estado", "")],
    )


def tabla(datos, columnas, tema, **extra):
    """DataTable con el estilo de la app; combina el rayado con los colores condicionales."""
    estilo = estilo_tabla(tema)
    condicional = estilo.pop("style_data_conditional") + extra.pop("style_data_conditional", [])
    return dash_table.DataTable(data=datos, columns=columnas, style_data_conditional=condicional, **estilo, **extra)


# ----- Formato y estados -----
def fmt_ess(x):
    return "0" if x == 0 else (f"{x:.3f}" if np.isfinite(x) else "∞")


def fmt_mg(gm_db):
    return "∞" if np.isinf(gm_db) else (f"{gm_db:.1f}" if np.isfinite(gm_db) else "—")


def estado_mf(pm):
    if not np.isfinite(pm):
        return "info"
    return "ok" if pm >= 45 else ("warn" if pm >= 30 else "bad")


def estado_mg(gm_db):
    if np.isinf(gm_db):
        return "ok"
    if not np.isfinite(gm_db):
        return "info"
    return "ok" if gm_db >= 6 else ("warn" if gm_db >= 3 else "bad")


def estado_mp(mp):
    if mp is None:
        return "info"
    return "ok" if mp <= 10 else ("warn" if mp <= 25 else "bad")


def insignia(texto, estado):
    return html.Span(texto, className=f"insignia insignia-{estado}")


# ====================================================================
# PANEL DE PARÁMETROS
# ====================================================================
panel = html.Aside(className="panel", children=[
    html.Div(className="marca", children=[
        html.Div(ico("waves"), className="marca-logo"),
        html.Div([html.Div("Control de Nivel", className="marca-titulo"),
                  html.Div("Prevención de inundaciones", className="marca-sub")]),
        html.Div(className="marca-acciones", children=[
            html.Button(ico("arrow-left-right"), id="btn-lado", className="btn-icono",
                        title="Mover el panel al otro lado", **{"aria-label": "Mover el panel al otro lado"}),
            html.Button(ico("moon"), id="btn-tema", className="btn-icono",
                        title="Cambiar tema claro / oscuro", **{"aria-label": "Cambiar tema claro u oscuro"}),
        ]),
    ]),
    html.P("Ajusta los parámetros: la simulación se actualiza al instante.", className="panel-ayuda"),

    grupo("triangle-alert", "Modo de simulación", [
        segmentado("modo", [("Normal", "normal"), ("Fallo del drenaje", "fallo")], "Qué simular",
                   "Normal: el controlador maneja la bomba de drenaje. Fallo: la bomba de drenaje se detiene "
                   "en un instante y la de entrada sigue echando agua (se ve en el tanque del Resumen)."),
        html.Div(id="fila-fallo-esc", children=[
            segmentado("fallo", [("Precaución", "precaucion"), ("Alerta de inundación", "alerta")], "Escenario",
                       "Precaución: alguien repara la bomba cuando el nivel llega al umbral amarillo. "
                       "Alerta: la bomba no se recupera y el agua sigue subiendo."),
        ]),
        campo_numero("t-fallo", "El drenaje falla en t = [s]", 1, 0,
                     ayuda="Instante en que la bomba de drenaje se detiene."),
    ]),
    grupo("cloud-rain", "Entrada de agua · bomba superior", [
        segmentado("entrada", [("Aleatoria", "aleatoria"), ("Constante", "constante"), ("Ninguna", "ninguna")],
                   "Cómo entra el agua",
                   "Aleatoria: simula lluvia que se intensifica y amaina. Constante: caudal fijo. "
                   "Ninguna: solo se prueba la respuesta a la consigna."),
        campo_slider("q-media", "Caudal medio de entrada [cm³/s]", 0, 30, 0.1),
        campo_slider("q-var", "Variabilidad de la lluvia [%]", 0, 100, 5),
        campo_slider("q-cambio", "Cambia de intensidad cada [s]", 1, 30, 0.5),
        html.Div(className="fila-semilla", id="fila-lluvia", children=[
            campo_numero("semilla", "Lluvia nº (semilla)", 1, 0, 99999,
                         "El mismo número reproduce exactamente la misma lluvia."),
            html.Button([ico("shuffle"), "Nueva lluvia"], id="btn-lluvia", className="btn btn-auto"),
        ]),
    ]),
    grupo("arrow-down-to-line", "Bomba de drenaje · bomba inferior", [
        campo_slider("kb", "Caudal máximo Kb [cm³/s]", 0.1, 100, 0.1,
                     "Caudal que saca la bomba de drenaje a PWM 100 %."),
        campo_slider("v-max", "Potencia máxima permitida [%]", 10, 100, 5,
                     "Límite de PWM de la bomba de drenaje. Si la entrada supera este caudal, el tanque se llena."),
        campo_slider("tau", "Constante de tiempo τ [s]", 0.01, 5, 0.01,
                     "La bomba no cambia su caudal al instante: dinámica de 1er orden."),
        html.Div(className="campo", children=[
            segmentado("modo-ganancia", [("Kb (bomba)", "kb"), ("K (planta)", "k-planta")],
                       "Definir ganancia con"),
        ]),
        campo_slider("k-planta", "Ganancia de la planta K = Kb/A", 0.01, 10, 0.01),
    ]),
    grupo("cylinder", "Tanque", [
        campo_slider("area", "Área del tanque A [cm²]", 1, 1000, 0.5,
                     "Área transversal del tanque rectangular (largo × ancho)."),
        segmentado("inicio", [("Reposo en h₀", "reposo"), ("Tanque vacío", "vacio")], "Condición inicial",
                   "Reposo en h₀: el tanque está en h₀ y la bomba de drenaje ya compensa la entrada (caso real). "
                   "Tanque vacío: parte en 0 cm con la bomba apagada."),
        campo_numero("h0", "Nivel inicial h₀ [cm]", 0.1, 0, 100),
    ]),
    grupo("sliders-horizontal", "Controlador", [
        segmentado("ctrl", [("P", "P"), ("PI", "PI"), ("PD", "PD"), ("PID", "PID")], "Tipo de controlador"),
        campo_slider("kp", "Kp · proporcional", 0, 50, 0.1),
        campo_slider("ki", "Ki · integral", 0, 20, 0.05),
        campo_slider("kd", "Kd · derivativa", 0, 10, 0.01),
        campo_slider("n", "N · filtro derivativo", 1, 100, 1,
                     "La derivada usa Kd·N·s/(s+N). N alto se acerca a la derivada ideal pero amplifica el ruido."),
    ]),
    grupo("target", "Nivel objetivo (consigna)", [
        segmentado("consigna", [("Escalón", "Escalón"), ("Rampa", "Rampa")], "Forma de la consigna"),
        html.Div(className="fila-doble", children=[
            campo_numero("amp", "Cambio Δh [cm]", 0.1, -50, 50),
            campo_numero("t-esc", "En el instante [s]", 1, 0),
        ]),
        campo_numero("pendiente", "Pendiente de la rampa [cm/s]", 0.05, -10, 10),
    ], abierto=False),
    grupo("siren", "Semáforo de alerta", [
        html.Div(className="fila-doble", children=[
            campo_numero("u-am", "Precaución desde [cm]", 0.5, 0.1, 200),
            campo_numero("u-rojo", "Alerta desde [cm]", 0.5, 0.2, 300),
        ]),
    ], abierto=False),
    grupo("radio-tower", "Datos reales (ESP32)", [
        zona_subida("subir-real"),
        html.Div(className="fila-doble", children=[
            html.Button([ico("file-spreadsheet"), "Datos de ejemplo"], id="btn-ejemplo", className="btn",
                        title="Genera mediciones SINTÉTICAS para probar la vista combinada"),
            html.Button([ico("x"), "Quitar datos"], id="btn-quitar-real", className="btn"),
        ]),
        dcc.Checklist(id="ver-real", className="interruptor", value=[],
                      options=[{"label": "Ver real y simulación juntos", "value": "si"}]),
        html.Div(id="estado-real", className="aviso-guardado", **{"aria-live": "polite"}),
    ]),
    grupo("clock", "Simulación", [
        campo_numero("t-final", "Tiempo final [s]", 1, 1, 600),
        campo_slider("n-puntos", "Resolución (nº de puntos)", 200, 5000, 100),
    ], abierto=False),
    grupo("git-compare", "Comparar sintonías", [
        html.Div(className="campo", children=[
            html.Label("Nombre (opcional)", htmlFor="nombre-corrida"),
            dcc.Input(id="nombre-corrida", type="text", placeholder="p. ej. PID suave", className="entrada"),
        ]),
        html.Button([ico("bookmark-plus"), "Guardar esta simulación"], id="btn-guardar", className="btn btn-primario"),
        html.Div(className="fila-doble", children=[
            html.Button([ico("undo-2"), "Quitar última"], id="btn-quitar", className="btn"),
            html.Button([ico("trash-2"), "Borrar todas"], id="btn-borrar", className="btn"),
        ]),
        html.Div(id="aviso-guardado", className="aviso-guardado", **{"aria-live": "polite"}),
    ], abierto=False),
])

# (valor, etiqueta) — el icono de cada pestaña se pone por CSS (clase pestana-<valor>)
PESTANAS = [("resumen", "Resumen"), ("respuesta", "Respuesta temporal"), ("reales", "Real vs. simulación"),
            ("comparar", "Comparar"), ("estabilidad", "Estabilidad"), ("frecuencia", "Frecuencia"),
            ("modelo", "Modelo"), ("datos", "Datos")]

app.layout = html.Div(id="raiz", className="app", children=[
    dcc.Store(id="tema", storage_type="local", data="claro"),
    dcc.Store(id="lado", storage_type="local", data="derecha"),
    dcc.Store(id="corridas", storage_type="session", data=[]),
    dcc.Store(id="datos-reales", storage_type="session", data=None),
    dcc.Download(id="descarga-csv"),
    html.Main(className="principal", children=[
        html.Header(id="cabecera", className="cabecera"),
        dcc.Tabs(id="pestanas", value="resumen", className="pestanas", parent_className="pestanas-contenedor",
                 children=[dcc.Tab(label=l, value=v, className=f"pestana pestana-{v}",
                                   selected_className="pestana-activa") for v, l in PESTANAS]),
        dcc.Loading(html.Div(id="contenido", className="contenido"), type="dot", delay_show=500,
                    color="#2a78d6"),
        html.Footer("Prototipo de prevención de inundaciones · Modelo: balance de masa del tanque con bomba de "
                    "entrada (perturbación) y bomba de drenaje controlada · Dash · python-control · Plotly · "
                    "Iconos Lucide", className="pie"),
    ]),
    panel,
])


# ====================================================================
# CALLBACKS DE LA INTERFAZ
# ====================================================================
@app.callback(Output("tema", "data"), Input("btn-tema", "n_clicks"), State("tema", "data"),
              prevent_initial_call=True)
def cambiar_tema(_, tema):
    return "claro" if tema == "oscuro" else "oscuro"


@app.callback(Output("lado", "data"), Input("btn-lado", "n_clicks"), State("lado", "data"),
              prevent_initial_call=True)
def cambiar_lado(_, lado):
    return "izquierda" if lado == "derecha" else "derecha"


@app.callback(Output("raiz", "className"), Output("btn-tema", "children"),
              Input("tema", "data"), Input("lado", "data"))
def aplicar_apariencia(tema, lado):
    clases = ["app", "tema-oscuro" if tema == "oscuro" else "", "panel-izquierda" if lado == "izquierda" else ""]
    return " ".join(c for c in clases if c), ico("sun" if tema == "oscuro" else "moon")


OCULTO, VISIBLE = {"display": "none"}, {}


@app.callback(Output("fila-ki", "style"), Output("fila-kd", "style"), Output("fila-n", "style"),
              Input("ctrl", "value"))
def mostrar_ganancias(ctrl):
    ki = VISIBLE if ctrl in ("PI", "PID") else OCULTO
    kd = VISIBLE if ctrl in ("PD", "PID") else OCULTO
    return ki, kd, kd


@app.callback(Output("fila-kb", "style"), Output("fila-k-planta", "style"), Input("modo-ganancia", "value"))
def mostrar_modo_ganancia(modo):
    return (VISIBLE, OCULTO) if modo == "kb" else (OCULTO, VISIBLE)


@app.callback(Output("fila-amp", "style"), Output("fila-pendiente", "style"), Input("consigna", "value"))
def mostrar_consigna(consigna):
    return (VISIBLE, OCULTO) if consigna == "Escalón" else (OCULTO, VISIBLE)


@app.callback(Output("fila-q-media", "style"), Output("fila-q-var", "style"), Output("fila-q-cambio", "style"),
              Output("fila-lluvia", "style"), Input("entrada", "value"))
def mostrar_entrada(entrada):
    media = OCULTO if entrada == "ninguna" else VISIBLE
    aleatoria = VISIBLE if entrada == "aleatoria" else OCULTO
    return media, aleatoria, aleatoria, aleatoria


@app.callback(Output("fila-fallo-esc", "style"), Output("fila-t-fallo", "style"), Input("modo", "value"))
def mostrar_modo(modo):
    return (VISIBLE, VISIBLE) if modo == "fallo" else (OCULTO, OCULTO)


@app.callback(Output("semilla", "value"), Input("btn-lluvia", "n_clicks"), prevent_initial_call=True)
def nueva_lluvia(_):
    return int(np.random.default_rng().integers(1, 99999))


def _leer_subida(contenido, nombre):
    if not contenido:
        raise PreventUpdate
    try:
        datos = dr.leer_csv(contenido, nombre)
    except Exception as exc:
        return no_update, [ico("triangle-alert"), f" No pude leer «{nombre}»: {exc}"], no_update
    return datos, [ico("circle-check"), f" «{nombre}»: {len(datos['t'])} mediciones cargadas."], ["si"]


# El área grande de la pestaña «Real vs. simulación» solo existe cuando esa pestaña está abierta,
# por eso tiene su propio callback (escribe en las mismas salidas con allow_duplicate).
@app.callback(Output("datos-reales", "data", allow_duplicate=True), Output("estado-real", "children", allow_duplicate=True),
              Output("ver-real", "value", allow_duplicate=True),
              Input("subir-real-grande", "contents"), State("subir-real-grande", "filename"), prevent_initial_call=True)
def cargar_desde_pestana(contenido, nombre):
    return _leer_subida(contenido, nombre)


@app.callback(Output("datos-reales", "data"), Output("estado-real", "children"), Output("ver-real", "value"),
              Input("subir-real", "contents"), Input("btn-ejemplo", "n_clicks"), Input("btn-quitar-real", "n_clicks"),
              State("subir-real", "filename"), *[State(p, "value") for p in PARAMS], prevent_initial_call=True)
def cargar_datos_reales(contenido, _ej, _quitar, nombre, *valores):
    disparo = ctx.triggered_id
    if disparo == "btn-quitar-real":
        return None, "Sin datos reales cargados.", []
    if disparo == "btn-ejemplo":
        q, errores = limpiar_parametros(dict(zip(PARAMS, valores)))
        if errores:
            return no_update, "Corrige los parámetros antes de generar el ejemplo.", no_update
        datos = dr.generar_ejemplo(simular(q))
        return datos, [ico("circle-check"), " Datos de ejemplo SINTÉTICOS cargados (no son mediciones)."], ["si"]
    return _leer_subida(contenido, nombre)


@app.callback(Output("corridas", "data"), Output("aviso-guardado", "children"),
              Input("btn-guardar", "n_clicks"), Input("btn-quitar", "n_clicks"), Input("btn-borrar", "n_clicks"),
              State("nombre-corrida", "value"), State("corridas", "data"),
              *[State(p, "value") for p in PARAMS], prevent_initial_call=True)
def gestionar_corridas(_g, _q, _b, nombre, corridas, *valores):
    corridas = list(corridas or [])
    if ctx.triggered_id == "btn-borrar":
        return [], "Se borraron las simulaciones guardadas."
    if ctx.triggered_id == "btn-quitar":
        if not corridas:
            raise PreventUpdate
        quitada = corridas.pop()
        return corridas, f"Se quitó «{quitada['nombre']}»."
    q, errores = limpiar_parametros(dict(zip(PARAMS, valores)))
    if errores:
        return no_update, "Corrige los parámetros antes de guardar."
    n = (max([c["n"] for c in corridas]) if corridas else 0) + 1
    base = (nombre or "").strip() or f"{q['ctrl']} ({texto_ganancias(q)})"
    nueva = resumen_para_comparar(simular(q), f"#{n} {base}", None)
    nueva["n"] = n
    corridas = (corridas + [nueva])[-6:]
    return corridas, [ico("circle-check"), f" Guardada «#{n} {base}». Mírala en Comparar."]


@app.callback(Output("descarga-csv", "data"), Input("btn-csv", "n_clicks"),
              *[State(p, "value") for p in PARAMS], prevent_initial_call=True)
def descargar_csv(n_clicks, *valores):
    if not n_clicks:
        raise PreventUpdate
    q, errores = limpiar_parametros(dict(zip(PARAMS, valores)))
    if errores:
        raise PreventUpdate
    df = tabla_datos(simular(q))
    return dcc.send_data_frame(df.to_csv, f"simulacion_{q['ctrl']}_{q['entrada']}.csv", index=False)


# ====================================================================
# CALLBACK PRINCIPAL: simula y dibuja la pestaña activa
# ====================================================================
@app.callback(Output("cabecera", "children"), Output("contenido", "children"),
              *[Input(p, "value") for p in PARAMS],
              Input("pestanas", "value"), Input("tema", "data"), Input("corridas", "data"),
              Input("datos-reales", "data"), Input("ver-real", "value"))
def actualizar(*args):
    valores, (pestana, tema, corridas, real, ver_real) = args[:len(PARAMS)], args[len(PARAMS):]
    tema = "oscuro" if tema == "oscuro" else "claro"
    q, errores = limpiar_parametros(dict(zip(PARAMS, valores)))
    tk = gr.TEMAS[tema]

    if errores:
        return cabecera(q, None, None), html.Div([aviso("bad", e) for e in errores])
    try:
        res = simular(q)
    except Exception as exc:
        return cabecera(q, None, None), aviso("bad", f"No fue posible simular el sistema: {exc}")

    # Lo que comparten todas las vistas
    x = dict(tk=tk, tema=tema, corridas=corridas or [], real=real,
             superponer=bool(real) and "si" in (ver_real or []))
    x["comp"] = dr.comparar(res, real) if real else None
    vistas = {"resumen": vista_resumen, "respuesta": vista_respuesta, "reales": vista_reales,
              "comparar": vista_comparar, "estabilidad": vista_estabilidad, "frecuencia": vista_frecuencia,
              "modelo": vista_modelo, "datos": vista_datos}
    return cabecera(q, res, x), vistas.get(pestana, vista_resumen)(res, x)


# ====================================================================
# VISTAS
# ====================================================================
def cabecera(q, res, x):
    chips = []
    if res is not None:
        z = res["zona_final"]
        chips.append(html.Span([punto_zona(z), f"Nivel final: {NOMBRE_ZONA[z]}"], className=f"chip chip-{ESTADO_ZONA[z]}"))
        chips.append(html.Span([ico("shield-check" if res["estable"] else "shield-alert"),
                                "Estable" if res["estable"] else "Inestable"],
                               className=f"chip chip-{'ok' if res['estable'] else 'bad'}"))
    entrada = {"aleatoria": f"lluvia aleatoria ~{q['q-media']:g} cm³/s",
               "constante": f"entrada constante {q['q-media']:g} cm³/s", "ninguna": "sin entrada"}[q["entrada"]]
    chips += [
        html.Span([ico("cloud-rain"), entrada], className="chip"),
        html.Span([ico("sliders-horizontal"), f"{q['ctrl']} · {texto_ganancias(q)}"], className="chip"),
        html.Span([ico("arrow-down-to-line"), f"Drenaje máx. {q['Kb'] * q['v-max'] / 100:.3g} cm³/s"], className="chip"),
    ]
    if q["modo"] == "fallo":
        chips.append(html.Span([ico("triangle-alert"), f"Fallo del drenaje en t = {q['t-fallo']:g} s"],
                               className="chip chip-warn"))
    if x and x["superponer"]:
        chips.append(html.Span([ico("radio-tower"), "Real + simulación" + (" (ejemplo)" if x["real"].get("ejemplo") else "")],
                               className="chip chip-real"))
    return [
        html.Div(className="cabecera-titulo", children=[
            html.Div("Prototipo a escala · Prevención de inundaciones", className="cabecera-antetitulo"),
            html.H1("Control de Nivel de Agua"),
        ]),
        html.Div(chips, className="chips"),
    ]


def aviso_semaforo(res):
    """Mensaje principal para la presentación: ¿hay riesgo de inundación?"""
    zf, zm, h_max, tz, h = res["zona_final"], res["zona_max"], res["h_max"], res["t_zonas"], res["h"]
    q = res["q"]
    nombre = lambda k: html.B([punto_zona(k), NOMBRE_ZONA[k].lower()], className="zona-en-texto")
    saturada = res["t_saturada"]
    nota_sat = ([" La bomba de drenaje estuvo al máximo durante ", html.B(f"{saturada:.1f} s"),
                 ": la entrada de agua supera lo que puede sacar."] if saturada > 0.5 else [])
    if zm > zf:
        return aviso(ESTADO_ZONA[zm], [
            "Aunque el nivel final queda en zona ", nombre(zf), ", en algún momento llega hasta ",
            html.B(f"{h_max:.2f} cm"), " (zona ", nombre(zm), ") durante ", html.B(f"{sum(tz[zf + 1:]):.1f} s"),
            ". Más Kp o más potencia de drenaje reducen ese pico."] + nota_sat)
    if zf == 2:
        return aviso("bad", ["El nivel termina en zona ", nombre(2), f" ({h[-1]:.2f} cm): "
                             "hay condición de inundación."] + nota_sat)
    if zf == 1:
        return aviso("warn", ["El nivel se mantiene en zona ", nombre(1), f" (máximo {h_max:.2f} cm). "
                              "No hay alerta roja, pero conviene vigilar."] + nota_sat)
    return aviso("ok", ["La bomba de drenaje mantiene el nivel en zona ", nombre(0), " durante toda la simulación "
                        f"(máximo {h_max:.2f} cm, por debajo de {q['u-am']:g} cm)."] + nota_sat)


def aviso_fallo(res):
    """Modo fallo: explica qué falló, cuándo, y si el nivel llegó a la zona del escenario elegido."""
    q, f, zm = res["q"], res["fallo"], res["zona_max"]
    esperada = 1 if q["fallo"] == "precaucion" else 2
    if f["t_caida"] is None:
        return aviso("info", [f"El fallo estaba programado en t = {q['t-fallo']:g} s, después del tiempo final "
                              f"({q['t-final']:g} s): no llega a ocurrir. Adelántalo para verlo."])
    texto = [html.B("Falla la bomba de drenaje"), f" en t = {f['t_caida']:.1f} s: se detiene mientras la bomba de "
             "entrada sigue echando agua, así que el nivel sube."]
    if f["t_reparada"] is not None:
        texto += [f" Se repara en t = {f['t_reparada']:.1f} s, cuando el nivel llega a {q['u-am']:g} cm, "
                  "y el controlador vuelve a drenar."]
    else:
        texto += [" La bomba no se recupera durante la simulación."]
    if zm < esperada:
        return aviso("info", texto + [f" Con esta entrada el nivel máximo fue {res['h_max']:.2f} cm y no llegó a la zona ",
                                      html.B(NOMBRE_ZONA[esperada].lower()),
                                      ": sube el caudal de entrada o adelanta el fallo."])
    return aviso(ESTADO_ZONA[zm], texto + [f" Nivel máximo: {res['h_max']:.2f} cm (", html.B(NOMBRE_ZONA[zm].lower()), ")."])


def kpis_principales(res, x):
    met, zf, zm = res["met"], res["zona_final"], res["zona_max"]
    pm, h, q = res["pm"], res["h"], res["q"]
    tarjetas = [
        kpi("Nivel final", f"{h[-1]:.2f}", "cm", NOMBRE_ZONA[zf], ESTADO_ZONA[zf], "droplet"),
        kpi("Nivel máx.", f"{res['h_max']:.2f}", "cm", NOMBRE_ZONA[zm], ESTADO_ZONA[zm], "waves"),
        kpi("Entrada", f"{np.mean(res['q_l']):.2f}", "cm³/s",
            {"aleatoria": "lluvia aleatoria", "constante": "caudal constante", "ninguna": "sin entrada"}[q["entrada"]],
            "info", "cloud-rain"),
        kpi("Drenaje", f"{res['uso_drenaje']:.0f}", "%",
            f"media · al máximo {res['t_saturada']:.1f} s" if res["t_saturada"] > 0.5 else "uso medio de la bomba",
            "warn" if res["t_saturada"] > 0.5 else "info", "arrow-down-to-line"),
    ]
    if q["entrada"] != "ninguna":
        zx = int(zona_de(res["r"][-1] + met["exceso"], q["u-am"], q["u-rojo"]))
        tarjetas.append(kpi("Exceso máx.", f"{met['exceso']:.2f}", "cm", "por encima del objetivo",
                            "ok" if met["exceso"] < 0.5 else ESTADO_ZONA[max(zx, 1)], "trending-up"))
    elif q["consigna"] == "Escalón" and q["amp"] != 0:
        mp, ts = met["mp"], met["ts"]
        tarjetas += [
            kpi("Sobreimpulso", f"{mp:.1f}" if mp is not None else "—", "%",
                f"pico en t = {met['tp']:.2f} s" if met["tp"] is not None else "sin pico", estado_mp(mp), "trending-up"),
            kpi("Asentamiento", f"{ts:.2f}" if ts is not None else "—", "s" if ts is not None else "",
                "banda del 2 %" if ts is not None else "no se asienta", "info" if ts is not None else "warn", "timer"),
        ]
    else:
        tarjetas.append(kpi("IAE", f"{met['iae']:.2f}", "cm·s", "∫|r − h| dt", "info", "sigma"))
    if x["superponer"] and x["comp"]:
        tarjetas.append(kpi("Modelo vs real", f"{x['comp']['rmse']:.2f}", "cm", "error RMS", "info", "radio-tower"))
    tarjetas += [
        kpi("Margen fase", f"{pm:.1f}" if np.isfinite(pm) else "—", "°", "recomendado ≥ 45°", estado_mf(pm), "compass"),
        kpi("Estabilidad", "Estable" if res["estable"] else "Inestable", "",
            f"{len(res['polos'])} polos en lazo cerrado", "ok" if res["estable"] else "bad",
            "shield-check" if res["estable"] else "shield-alert"),
    ]
    return html.Div(tarjetas, className="kpis")


def tabla_resumen(res):
    met, info, tz = res["met"], res["info_step"], res["t_zonas"]
    pm, gm_db = res["pm"], res["gm_db"]
    filas = [("grp", "Semáforo de alerta"),
             (html.Span([punto_zona(0), "Tiempo en normal"]), f"{tz[0]:.1f} s"),
             (html.Span([punto_zona(1), "Tiempo en precaución"]), f"{tz[1]:.1f} s"),
             (html.Span([punto_zona(2), "Tiempo en alerta"]), f"{tz[2]:.1f} s"),
             ("grp", "Bombas"),
             ("Entrada media / máxima", f"{np.mean(res['q_l']):.2f} / {np.max(res['q_l']):.2f} cm³/s"),
             ("Drenaje medio / máximo", f"{np.mean(res['q_b']):.2f} / {np.max(res['q_b']):.2f} cm³/s"),
             ("Drenaje al 100 % de su límite", f"{res['t_saturada']:.1f} s"),
             ("grp", "Estabilidad"),
             ("Lazo cerrado", insignia("Estable", "ok") if res["estable"] else insignia("Inestable", "bad")),
             ("Margen de fase", insignia(f"{pm:.1f}°", estado_mf(pm)) if np.isfinite(pm) else "—"),
             ("Margen de ganancia", insignia(f"{fmt_mg(gm_db)} dB", estado_mg(gm_db))),
             ("grp", "Error en estado estacionario"),
             ("Tipo de sistema", f"Tipo {res['n_int']}"),
             ("ess escalón", fmt_ess(res["ess"][0])),
             ("ess rampa", fmt_ess(res["ess"][1])),
             ("grp", "Desempeño (simulación)"),
             ("IAE  ∫|e| dt", f"{met['iae']:.3f}"),
             ("ISE  ∫e² dt", f"{met['ise']:.3f}"),
             ("ITAE  ∫t|e| dt", f"{met['itae']:.3f}")]
    if info is not None:
        filas += [("grp", "Escalón unitario teórico T(s)"),
                  ("Sobreimpulso Mp", f"{info['Overshoot']:.1f} %"),
                  ("Tiempo de pico tp", f"{info['PeakTime']:.3f} s"),
                  ("Tiempo asent. ts (2 %)", f"{info['SettlingTime']:.3f} s")]
    return html.Table(className="tabla-resumen", children=[html.Tbody([
        html.Tr(html.Td(b, colSpan=2), className="grp") if isinstance(a, str) and a == "grp"
        else html.Tr([html.Td(a), html.Td(b)]) for a, b in filas
    ])])


def _clave_simulacion(res):
    """Identificador de la simulación: al cambiar, React crea un semáforo nuevo (sin estado de animación)."""
    return "sem-" + str(abs(hash((tuple(np.round(res["h"][::50], 4)), res["q"]["u-am"], res["q"]["u-rojo"]))))


def vista_resumen(res, x):
    tk = x["tk"]
    real = x["real"] if x["superponer"] else None
    fallo = res["fallo"] is not None
    return html.Div([
        aviso_fallo(res) if fallo else aviso_semaforo(res),
        kpis_principales(res, x),
        html.Div(className="rejilla rejilla-principal", children=[
            tarjeta("chart-line", "Respuesta del sistema", [grafico(gr.fig_respuesta(res, tk, 560, real=real))],
                    "Nivel sobre las zonas del semáforo" + (" (real y simulado)" if real else "")
                    + ", franja de alerta, error y caudales de las dos bombas."),
            tarjeta("cylinder", "Tanque en movimiento", [
                html.Div(className="tanque-y-semaforo", children=[
                    grafico(gr.fig_tanque(res, tk, 520, fallo=fallo), "grafico-tanque"),
                    semaforo(res["zona_final"], clave=_clave_simulacion(res)),
                ])],
                "Pulsa ▶: la bomba superior echa agua, la inferior falla y el semáforo sigue el nivel." if fallo
                else "Pulsa ▶: la bomba superior echa agua, la inferior drena y el semáforo sigue el nivel."),
        ]),
        como_leer(
            "- **Curva azul**: nivel del agua h(t). **Línea discontinua**: el nivel objetivo (consigna)."
            + (" **Curva naranja**: el nivel medido por el sensor real." if real else "") + "\n"
            "- **Fondo de colores**: zonas del semáforo. Si el nivel entra en precaución o alerta, "
            "hay riesgo de inundación aunque sea por poco tiempo.\n"
            "- **Panel de caudales**: en verde lo que echa la bomba superior (la «lluvia»); en azul lo que "
            "saca la bomba de drenaje. Si el verde supera la línea punteada de drenaje máximo, el tanque se "
            "llena inevitablemente.\n"
            "- **Error**: diferencia entre el objetivo y el nivel; el controlador ajusta la bomba de drenaje "
            "para llevarla a 0."),
        html.Div(className="rejilla rejilla-tres", children=[
            tarjeta("audio-waveform", "Bode (lazo abierto)", [grafico(gr.fig_bode(res, tk, 330, compacto=True))]),
            tarjeta("orbit", "Lugar de raíces", [grafico(gr.fig_root_locus(res, tk, 330))]),
            tarjeta("clipboard-list", "Resumen de desempeño", [html.Div(tabla_resumen(res), className="desplazable")]),
        ]),
    ])


def vista_respuesta(res, x):
    met, h, e, v = res["met"], res["h"], res["e"], res["v"]
    zf = res["zona_final"]
    real = x["real"] if x["superponer"] else None
    na = lambda val, f: (f.format(val), True) if val is not None else ("n/a", False)
    mp, hay_mp = na(met["mp"], "{:.1f}")
    ts, hay_ts = na(met["ts"], "{:.2f}")
    return html.Div([
        tarjeta("chart-line", "Nivel, alerta, error y caudales", [
            leyenda_semaforo(res["q"]), grafico(gr.fig_respuesta(res, x["tk"], 720, real=real))],
            "Arrastra para hacer zoom (se aplica a todos los paneles); doble clic para restablecer."),
        como_leer(
            "- La **bomba superior** (verde) echa agua al azar: es la perturbación, como una lluvia.\n"
            "- La **bomba inferior** (azul) la maneja el controlador: drena más cuando el nivel supera el "
            "objetivo y se apaga cuando está por debajo. **No puede llenar el tanque**: si el objetivo sube, "
            "el nivel solo sube gracias a la entrada de agua.\n"
            "- Si la entrada supera el **drenaje máximo** (línea punteada), la bomba se satura al 100 % y el "
            "nivel sube sin remedio: es la situación de inundación que el sistema debe alertar."),
        html.H2([ico("ruler"), "Indicadores de la respuesta"], className="subtitulo"),
        html.Div(className="kpis", children=[
            kpi("Nivel final", f"{h[-1]:.3f}", "cm", NOMBRE_ZONA[zf], ESTADO_ZONA[zf], "droplet"),
            kpi("Error final", f"{e[-1]:+.3f}", "cm", "objetivo − nivel", "info", "crosshair"),
            kpi("Sobreimpulso", mp, "%" if hay_mp else "", "del escalón" if hay_mp else "solo sin entrada de agua",
                estado_mp(met["mp"]), "trending-up"),
            kpi("Asentamiento", ts, "s" if hay_ts else "", "banda del 2 %" if hay_ts else "solo sin entrada de agua",
                "info", "timer"),
            kpi("Exceso máx.", f"{met['exceso']:.2f}", "cm", "por encima del objetivo", "info", "waves"),
            kpi("Drenaje máx.", f"{np.max(v) * 100:.0f}", "%", "de la potencia de la bomba", "info", "arrow-down-to-line"),
        ]),
        html.Div(className="kpis", children=[
            kpi("IAE", f"{met['iae']:.3f}", "", "∫|e(t)| dt", "info", "sigma"),
            kpi("ISE", f"{met['ise']:.3f}", "", "∫e(t)² dt", "info", "sigma"),
            kpi("ITAE", f"{met['itae']:.3f}", "", "∫t·|e(t)| dt", "info", "sigma"),
            kpi("Drenaje saturado", f"{res['t_saturada']:.1f}", "s", "bomba al máximo",
                "warn" if res["t_saturada"] > 0.5 else "ok", "siren"),
        ]),
    ])


def vista_reales(res, x):
    """Real y simulación al mismo tiempo: carga de datos, semáforo real y comparación."""
    real, comp, q, tk = x["real"], x["comp"], res["q"], x["tk"]
    conexion = html.Span([html.Span(className="punto-pulso"), ico("radio-tower"), "ESP32 no conectado en vivo"],
                         className="estado-conexion")
    if not real:
        return html.Div([
            conexion,
            aviso("info", ["Para ver lo real y lo simulado al mismo tiempo, carga un ", html.B("CSV con las mediciones"),
                           " del ESP32 (arrástralo aquí abajo o en el panel, sección «Datos reales»). Si todavía no "
                           "tienes mediciones, pulsa ", html.B("Datos de ejemplo"), " para probar la vista con datos "
                           "sintéticos."], icono="radio-tower"),
            zona_subida("subir-real-grande", grande=True),
            html.Div(className="rejilla rejilla-reales", children=[
                tarjeta("siren", "Semáforo real", [semaforo(None)], clase="centrada"),
                tarjeta("file-spreadsheet", "Formato del archivo", [
                    dcc.Markdown("Una fila por medición. Columnas **t** (tiempo en s) y **h** (nivel en cm); "
                                 "opcional **v** (PWM de la bomba de drenaje en %). Acepta `,` o `;` como "
                                 "separador y decimales con punto o coma."),
                    html.Pre("t,h,v\n0.0,2.01,35\n0.5,2.04,36\n1.0,2.10,41\n...", className="codigo-ejemplo"),
                    dcc.Markdown("En el ESP32 basta con imprimir por el puerto serie `t,h,v` cada medio segundo "
                                 "y guardar esa salida como `.csv`.")]),
            ]),
        ])

    zr = int(zona_de(real["h"][-1], q["u-am"], q["u-rojo"]))
    zs = res["zona_final"]
    fuente = real.get("fuente", "archivo")
    kpis = [
        kpi("Muestras", f"{len(real['t'])}", "", f"durante {real['t'][-1]:.1f} s", "info", "file-spreadsheet"),
        kpi("Nivel real final", f"{real['h'][-1]:.2f}", "cm", NOMBRE_ZONA[zr], ESTADO_ZONA[zr], "radio-tower"),
        kpi("Nivel simulado", f"{res['h'][-1]:.2f}", "cm", NOMBRE_ZONA[zs], ESTADO_ZONA[zs], "droplet"),
    ]
    if comp:
        kpis += [kpi("Error RMS", f"{comp['rmse']:.3f}", "cm", "real − simulado", "info", "sigma"),
                 kpi("Diferencia máx.", f"{comp['max']:.3f}", "cm", f"media {comp['media']:+.3f} cm", "info", "ruler")]
    return html.Div([
        conexion,
        aviso("warn" if real.get("ejemplo") else "info",
              ([html.B("Datos de ejemplo sintéticos: "), "no son mediciones reales, solo sirven para probar esta vista. "]
               if real.get("ejemplo") else [html.B("Datos cargados: "), f"{fuente}. "])
              + ["Activa «Ver real y simulación juntos» en el panel para superponer la curva real también en el "
                 "Resumen y en la Respuesta temporal."], icono="file-spreadsheet"),
        html.Div(className="kpis", children=kpis),
        html.Div(className="rejilla rejilla-reales-datos", children=[
            tarjeta("chart-line", "Nivel real frente al simulado",
                    [grafico(gr.fig_real_vs_sim(res, real, comp, tk, 520))],
                    "Arriba ambas curvas sobre el semáforo; abajo la diferencia (real − simulado)."),
            tarjeta("siren", "Semáforos", [html.Div(className="par-semaforos", children=[
                html.Div([html.Div("Real", className="par-titulo"), semaforo(zr)]),
                html.Div([html.Div("Simulado", className="par-titulo"), semaforo(zs)]),
            ])], "Según el último nivel de cada uno.", clase="centrada"),
        ]),
        como_leer(
            "- Si las dos curvas casi coinciden, el **modelo representa bien** el tanque real.\n"
            "- Un **error RMS** de pocos milímetros es excelente: está al nivel del ruido del sensor ultrasónico.\n"
            "- Si la curva real queda sistemáticamente por encima, la bomba real drena menos que la nominal: "
            "ajusta **Kb** o **τ** en el panel hasta que coincidan (identificación del modelo).\n"
            "- Para comparar bien, usa en la simulación la misma consigna y una entrada de agua parecida a la "
            "del experimento."),
        zona_subida("subir-real-grande", grande=True),
    ])


def vista_comparar(res, x):
    q, tk = res["q"], x["tk"]
    corridas = x["corridas"]
    actual = resumen_para_comparar(res, f"Actual · {q['ctrl']} ({texto_ganancias(q)})", None)
    todas = corridas + [actual]
    mejor = min(range(len(todas)), key=lambda k: todas[k]["iae"])
    filas = [{
        "": "★" if k == mejor else "", "Simulación": c["nombre"],
        "Sobreimpulso [%]": None if c["mp"] is None else round(c["mp"], 1),
        "T. asentamiento [s]": None if c["ts"] is None else round(c["ts"], 2),
        "IAE": round(c["iae"], 3), "Nivel máx. [cm]": round(c["h_max"], 2),
        "Zona máx.": NOMBRE_ZONA[c["zona_max"]],
        "Margen de fase [°]": None if c["pm"] is None else round(c["pm"], 1),
        "Estable": "Sí" if c["estable"] else "No",
    } for k, c in enumerate(todas)]
    colores_zona = [{"if": {"filter_query": f'{{Zona máx.}} = "{NOMBRE_ZONA[k]}"', "column_id": "Zona máx."},
                     "color": COLOR_ZONA[k], "fontWeight": "700"} for k in range(3)]
    vacio = None if corridas else aviso("info", [
        "Aún no hay simulaciones guardadas. En el panel de parámetros (sección «Comparar sintonías») pulsa ",
        html.B("Guardar esta simulación"), ", cambia la sintonía (por ejemplo, de PI a PID) y compara ambas "
        "curvas aquí. Consejo: deja la misma «Lluvia nº» para que todas enfrenten la misma lluvia."],
        icono="git-compare")
    return html.Div([
        vacio,
        tarjeta("waves", "Nivel h(t) de cada sintonía",
                [grafico(gr.fig_comparacion(corridas, actual, q["u-am"], q["u-rojo"], tk))],
                "Sobre las zonas del semáforo: la mejor sintonía mantiene el nivel bajo sin invadir zonas de riesgo."),
        tarjeta("clipboard-list", "Tabla comparativa", [tabla(
            filas, [{"name": c, "id": c} for c in filas[0]], x["tema"], style_data_conditional=colores_zona)],
            "★ marca la sintonía con menor error acumulado (IAE)."),
        como_leer(
            "- **IAE** (integral del error absoluto) resume en un número cuánto se alejó el nivel del objetivo "
            "durante toda la simulación: **menor es mejor**.\n"
            "- Para prevenir inundaciones conviene priorizar un **nivel máximo bajo** y un buen **margen de fase**."),
    ])


def vista_estabilidad(res, x):
    polos, ess = res["polos"], res["ess"]
    filas_polos = [{"Parte real σ": round(p.real, 4), "Parte imaginaria ω": round(p.imag, 4),
                    "|p|": round(abs(p), 4),
                    "ζ (amortiguamiento)": round(-p.real / abs(p), 3) if abs(p) > 1e-12 else None,
                    "Estado": "estable" if p.real < 0 else "inestable"} for p in polos]
    estado = (aviso("ok", ["El sistema en lazo cerrado es ", html.B("estable"),
                           ": todos los polos tienen parte real negativa."])
              if res["estable"] else
              aviso("bad", ["El sistema en lazo cerrado ", html.B("NO es estable"),
                            " con estos parámetros: al menos un polo tiene parte real ≥ 0."]))
    return html.Div([
        estado,
        html.Div(className="rejilla rejilla-dos", children=[
            tarjeta("orbit", "Lugar geométrico de las raíces", [grafico(gr.fig_root_locus(res, x["tk"], 460))],
                    "La estrella marca los polos de lazo cerrado actuales (K = 1). Zona sombreada: semiplano inestable."),
            tarjeta("crosshair", "Polos y ceros en lazo cerrado", [grafico(gr.fig_pzmap(res, x["tk"], 460))],
                    "Pasa el cursor sobre cada punto para ver su valor."),
        ]),
        como_leer(
            "- El análisis de estabilidad usa el **modelo lineal** del lazo (sin los límites de la bomba). "
            "La simulación temporal sí incluye esos límites.\n"
            "- Un sistema es **estable** si todos sus polos de lazo cerrado están a la **izquierda** del eje "
            "vertical (fuera de la zona sombreada).\n"
            "- Cuanto más a la izquierda están los polos, más **rápida** es la respuesta; si tienen parte "
            "imaginaria grande, la respuesta **oscila** más."),
        html.Div(className="rejilla rejilla-dos-uno", children=[
            tarjeta("table-2", "Polos del sistema en lazo cerrado", [tabla(
                filas_polos, [{"name": c, "id": c} for c in filas_polos[0]] if filas_polos else [], x["tema"])]),
            tarjeta("square-function", "Tipo de sistema y errores ess", [html.Div(className="kpis kpis-2", children=[
                kpi("Tipo", f"{res['n_int']}", "", "integradores en L(s)", "info", "square-function"),
                kpi("ess escalón", fmt_ess(ess[0]), "", "", "ok" if ess[0] == 0 else "warn", "move-up-right"),
                kpi("ess rampa", fmt_ess(ess[1]), "", "", "ok" if ess[1] == 0 else "warn", "trending-up"),
                kpi("ess parábola", fmt_ess(ess[2]), "", "", "ok" if ess[2] == 0 else "warn", "spline"),
            ])]),
        ]),
    ])


def vista_frecuencia(res, x):
    pm, gm_db, wg, wp = res["pm"], res["gm_db"], res["wg"], res["wp"]
    return html.Div([
        html.Div(className="kpis", children=[
            kpi("Margen gan.", fmt_mg(gm_db), "dB", "recomendado ≥ 6 dB", estado_mg(gm_db), "signal"),
            kpi("Margen fase", f"{pm:.1f}" if np.isfinite(pm) else "—", "°", "recomendado ≥ 45°",
                estado_mf(pm), "compass"),
            kpi("ω cruce gan.", f"{wp:.3g}" if np.isfinite(wp) else "—", "rad/s", "|L(jω)| = 0 dB", "info", "activity"),
            kpi("ω cruce fase", f"{wg:.3g}" if np.isfinite(wg) else "—", "rad/s", "∠L(jω) = −180°", "info", "activity"),
        ]),
        tarjeta("audio-waveform", "Diagrama de Bode de L(s) = C(s)·Gp(s)", [grafico(gr.fig_bode(res, x["tk"], 600))]),
        como_leer(
            "- Los **márgenes** indican cuánto «colchón» tiene el sistema antes de volverse inestable.\n"
            "- **Margen de fase ≥ 45°** suele dar una respuesta con poco sobreimpulso; valores bajos implican "
            "oscilaciones (y más riesgo de que el nivel suba de más).\n"
            "- **Margen de ganancia ∞** significa que la fase nunca cruza −180°."),
    ])


def _polinomio_latex(coef):
    """Coeficientes [0.5, 6, 11.11] → texto LaTeX del polinomio en s."""
    coef = np.atleast_1d(np.asarray(coef, dtype=float))
    n = len(coef) - 1
    terminos = []
    for i, c in enumerate(coef):
        if abs(c) < 1e-12:
            continue
        p = n - i
        num = f"{abs(c):.4g}"
        potencia = "" if p == 0 else ("s" if p == 1 else f"s^{{{p}}}")
        if potencia and num == "1":
            num = ""
        signo = "-" if c < 0 else "+"
        terminos.append((signo, rf"{num}\,{potencia}" if num and potencia else (num or potencia)))
    if not terminos:
        return "0"
    texto = ("-" if terminos[0][0] == "-" else "") + terminos[0][1]
    return texto + "".join(f" {sg} {t}" for sg, t in terminos[1:])


def tf_latex(nombre, sistema):
    num, den = sistema.num[0][0], sistema.den[0][0]
    return rf"$${nombre} = \dfrac{{{_polinomio_latex(num)}}}{{{_polinomio_latex(den)}}}$$"


def _matriz_latex(M):
    return r"\begin{bmatrix}" + r" \\ ".join(" & ".join(f"{v:.4g}" for v in fila) for fila in M) + r"\end{bmatrix}"


def vista_modelo(res, x):
    q = res["q"]
    Ass, Bss, Css, Dss = res["ss"]
    mat = lambda txt: dcc.Markdown(txt, mathjax=True, className="formula")
    return html.Div([
        tarjeta("cylinder", "Balance de masa con dos bombas", [
            mat(r"$$A\,\dfrac{dh}{dt} = Q_{entrada}(t) - Q_{drenaje}(t), \qquad "
                r"\tau\,\dfrac{dQ_{drenaje}}{dt} + Q_{drenaje} = K_b\,v(t), \quad 0 \le v \le v_{max}$$"),
            html.P("La bomba superior (Q_entrada) es la perturbación; la bomba inferior (Q_drenaje) es el "
                   "actuador. El controlador actúa sobre la bomba de drenaje con v = C(s)·(h − r): drena más "
                   "cuando el nivel supera el objetivo.", className="nota")]),
        html.Div(className="rejilla rejilla-dos", children=[
            tarjeta("arrow-down-to-line", "Planta (bomba de drenaje → nivel)", [
                mat(r"$$G_p(s) = \dfrac{K}{\tau s^2 + s}, \qquad K = \dfrac{K_b}{A}$$"),
                mat(tf_latex("G_p(s)", res["Gp"])),
                html.P(f"Valores actuales → K = {res['K']:.4f}, τ = {q['tau']:.4f} s", className="nota")]),
            tarjeta("sliders-horizontal", f"Controlador ({q['ctrl']})", [
                mat(r"$$C(s) = K_p + \dfrac{K_i}{s} + \dfrac{K_d N s}{s + N}$$"),
                mat(tf_latex("C(s)", res["C"])),
                html.P("Valores numéricos con los parámetros actuales.", className="nota")]),
        ]),
        html.Div(className="rejilla rejilla-dos", children=[
            tarjeta("route", "Seguimiento del objetivo T(s) = H(s)/R(s)", [
                mat(r"$$T(s) = \dfrac{C(s)\,G_p(s)}{1 + C(s)\,G_p(s)}$$"),
                mat(tf_latex("T(s)", res["T"]))]),
            tarjeta("cloud-rain", "Rechazo de la lluvia H(s)/Q_entrada(s)", [
                mat(r"$$\dfrac{H(s)}{Q_{entrada}(s)} = \dfrac{1/(A\,s)}{1 + C(s)\,G_p(s)}$$"),
                mat(tf_latex(r"\dfrac{H}{Q_e}", res["T_pert"])),
                html.P("Mientras más pequeña sea esta función, menos sube el nivel con la lluvia.", className="nota")]),
        ]),
        tarjeta("sigma", "Representación en espacio de estados de la planta", [
            mat(r"$$\dot{x} = A\,x + B\,v, \qquad h = C\,x + D\,v$$"),
            html.Div(className="rejilla rejilla-cuatro", children=[
                mat(f"$$A = {_matriz_latex(Ass)}$$"), mat(f"$$B = {_matriz_latex(Bss)}$$"),
                mat(f"$$C = {_matriz_latex(Css)}$$"), mat(f"$$D = {_matriz_latex(Dss)}$$")]),
            html.P("Estados: x₁ = h (nivel), x₂ = Q_drenaje/A. Entrada: v (mando de la bomba de drenaje; "
                   "el signo negativo de B indica que drenar baja el nivel). Salida: h (nivel medido).",
                   className="nota")]),
        como_leer(
            "- La **planta** es integradora (polo en s = 0): toda el agua que entra y no se drena se acumula.\n"
            "- Por eso la bomba de drenaje necesita el controlador: con acción **integral** (PI/PID) compensa "
            "exactamente la lluvia media y el nivel vuelve al objetivo.\n"
            f"- Condición inicial usada: **{'reposo en h₀' if q['inicio'] == 'reposo' else 'tanque vacío'}**."),
    ])


def tabla_datos(res):
    q = res["q"]
    z = zona_de(res["h"], q["u-am"], q["u-rojo"])
    return pd.DataFrame({"t [s]": res["t"], "r(t) [cm]": res["r"], "h(t) [cm]": res["h"],
                         "e(t) [cm]": res["e"], "Entrada [cm³/s]": res["q_l"], "Drenaje [cm³/s]": res["q_b"],
                         "PWM drenaje [%]": res["v"] * 100, "Alerta": [NOMBRE_ZONA[k] for k in z]})


def vista_datos(res, x):
    df = tabla_datos(res)
    tz = res["t_zonas"]
    total = max(sum(tz), 1e-9)
    columnas = [{"name": c, "id": c, "type": "numeric" if c != "Alerta" else "text",
                 "format": Format(precision=3, scheme=Scheme.fixed) if c != "Alerta" else None} for c in df.columns]
    colores_alerta = [{"if": {"filter_query": f'{{Alerta}} = "{NOMBRE_ZONA[k]}"', "column_id": "Alerta"},
                       "color": COLOR_ZONA[k], "fontWeight": "700"} for k in range(3)]
    est = df[["h(t) [cm]", "e(t) [cm]", "Entrada [cm³/s]", "Drenaje [cm³/s]"]].agg(["mean", "std", "min", "max"]).T.round(3)
    est.insert(0, "Señal", est.index)
    est.columns = ["Señal", "Media", "Desv. est.", "Mínimo", "Máximo"]
    return html.Div(className="rejilla rejilla-dos-uno", children=[
        tarjeta("table-2", "Muestras de la simulación", [
            html.Button([ico("download"), "Descargar CSV completo"], id="btn-csv", className="btn btn-primario btn-derecha"),
            tabla(df.round(4).to_dict("records"), columnas, x["tema"], page_size=14, sort_action="native",
                  style_data_conditional=colores_alerta)],
            f"{len(df)} muestras · ordena haciendo clic en los encabezados · 14 filas por página."),
        html.Div([
            tarjeta("siren", "Tiempo en cada zona", [html.Div(className="kpis kpis-1", children=[
                kpi(NOMBRE_ZONA[k].split()[0], f"{tz[k]:.1f}", "s", f"{100 * tz[k] / total:.0f} % del tiempo",
                    ESTADO_ZONA[k], ["circle-check", "triangle-alert", "siren"][k]) for k in range(3)])]),
            tarjeta("ruler", "Estadísticas", [tabla(
                est.to_dict("records"), [{"name": c, "id": c} for c in est.columns], x["tema"])]),
        ]),
    ])


if __name__ == "__main__":
    # En producción (Hugging Face, etc.) la plataforma define PORT y la app escucha en todas las interfaces;
    # en el computador sigue en http://127.0.0.1:8050.
    puerto = os.environ.get("PORT")
    app.run(debug=False, host="0.0.0.0" if puerto else "127.0.0.1", port=int(puerto or 8050))
