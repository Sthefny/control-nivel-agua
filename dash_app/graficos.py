# -*- coding: utf-8 -*-
"""
Figuras Plotly de la aplicación. Cada función recibe `tk`, los colores del tema activo.

Criterios de color:
- Una curva por panel usa la escala de azules de la interfaz; la consigna es tinta neutra
  discontinua (es una referencia, no una serie).
- Varias series en un mismo gráfico (Comparar) usan una paleta categórica validada para
  daltonismo, en orden fijo: la simulación actual siempre ocupa el primer lugar (azul).
- El semáforo usa colores de estado reservados, siempre acompañados de su nombre.
- Nunca dos ejes Y en un mismo panel: magnitud y fase van en paneles separados.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from modelo import COLOR_ZONA, NOMBRE_ZONA, zona_de

TEMAS = {
    "claro": dict(
        texto="#3d5170", titulo="#0b1a2e", grid="#e6ecf3", eje="#c5d1df", superficie="#ffffff",
        hover="#ffffff", slider="#dde5ef",
        nivel="#2a78d6", nivel_relleno="rgba(42,120,214,0.12)", consigna="#1c2f4a", entrada="#1baf7a",
        error="#6b83a3", error_relleno="rgba(107,131,163,0.14)", control="#1c5cab",
        fase="#1c5cab", marca="#0b1a2e", destacado="#eb6834",
        agua_fondo="#0d4f96", agua_sup="#5aa5ee", vidrio="#8aa6c4",
        categorica=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"],
    ),
    "oscuro": dict(
        texto="#aebfd6", titulo="#e3ecf7", grid="#16263d", eje="#2b4262", superficie="#0e1b2f",
        hover="#0e1b2f", slider="#1c2e48",
        nivel="#3987e5", nivel_relleno="rgba(57,135,229,0.16)", consigna="#c9d6e6", entrada="#199e70",
        error="#8aa1bf", error_relleno="rgba(138,161,191,0.14)", control="#6da7ec",
        fase="#6da7ec", marca="#e3ecf7", destacado="#d95926",
        agua_fondo="#0b3f7a", agua_sup="#4a95e0", vidrio="#4f6b8f",
        categorica=["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9"],
    ),
}
CONFIG = {"displaylogo": False,
          "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def color_comparacion(tk, n):
    """Color fijo de la simulación guardada nº n (el primer lugar es de la simulación actual)."""
    paleta = tk["categorica"]
    return paleta[1 + (n - 1) % (len(paleta) - 1)]


def _base(fig, tk, altura, xtitle=None, ytitle=None, leyenda=True):
    fig.update_layout(
        height=altura, template="none",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color=tk["texto"]),
        margin=dict(l=58, r=18, t=36 if leyenda else 16, b=44),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=tk["texto"])),
        showlegend=leyenda, hovermode="x unified",
        hoverlabel=dict(bgcolor=tk["hover"], bordercolor=tk["eje"],
                        font=dict(size=12, color=tk["titulo"])),
    )
    fig.update_xaxes(gridcolor=tk["grid"], linecolor=tk["eje"], zeroline=False,
                     ticks="outside", tickcolor=tk["eje"], showline=True)
    fig.update_yaxes(gridcolor=tk["grid"], linecolor=tk["eje"], zeroline=False,
                     ticks="outside", tickcolor=tk["eje"], showline=True)
    if xtitle:
        fig.update_xaxes(title_text=xtitle)
    if ytitle:
        fig.update_yaxes(title_text=ytitle)
    return fig


def _zonas_semaforo(fig, y_tope, u_am, u_rojo, row=None, col=None):
    """Bandas del semáforo como fondo del eje de nivel, con el nombre de cada umbral."""
    kw = dict(row=row, col=col) if row else {}
    for k, (y0, y1) in enumerate([(-1e3, u_am), (u_am, u_rojo), (u_rojo, max(y_tope, u_rojo) + 1e3)]):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=COLOR_ZONA[k], opacity=0.06 if k == 0 else 0.09,
                      line_width=0, layer="below", **kw)
    for k, u in ((1, u_am), (2, u_rojo)):
        if u <= y_tope:
            fig.add_hline(y=u, line_color=COLOR_ZONA[k], line_width=1, line_dash="dot",
                          annotation_text=f"{NOMBRE_ZONA[k].split()[0]} · {u:g} cm",
                          annotation_position="top left",
                          annotation_font=dict(size=10, color=COLOR_ZONA[k]), **kw)


# ====================================================================
# RESPUESTA TEMPORAL
# ====================================================================
def fig_respuesta(res, tk, altura=560, real=None):
    """
    Cuatro paneles con el mismo eje de tiempo: nivel (sobre el semáforo, y opcionalmente el
    nivel real medido), franja de alerta, error y caudales de las dos bombas.
    """
    t, r, h, e, met = res["t"], res["r"], res["h"], res["e"], res["met"]
    q = res["q"]
    u_am, u_rojo = q["u-am"], q["u-rojo"]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[0.5, 0.05, 0.18, 0.27])

    alturas = [np.max(h), np.max(r)] + ([max(real["h"])] if real else [])
    y_tope = max(float(max(alturas)) * 1.15, u_am * 1.15)
    y_min = float(min(np.min(h), np.min(r), 0.0))
    _zonas_semaforo(fig, y_tope, u_am, u_rojo, row=1, col=1)
    if met["banda"] is not None:
        fig.add_hrect(y0=met["r_final"] - met["banda"], y1=met["r_final"] + met["banda"],
                      fillcolor=tk["nivel"], opacity=0.12, line_width=0, row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=h, name="Nivel simulado" if real else "Nivel h(t)", fill="tozeroy",
                             fillcolor=tk["nivel_relleno"], line=dict(color=tk["nivel"], width=2.5),
                             hovertemplate="%{y:.3f} cm"), row=1, col=1)
    if real:
        fig.add_trace(go.Scatter(x=real["t"], y=real["h"],
                                 name="Nivel real" + (" (ejemplo)" if real.get("ejemplo") else ""),
                                 mode="lines", line=dict(color=tk["destacado"], width=2),
                                 hovertemplate="%{y:.3f} cm"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=r, name="Consigna r(t)", line=dict(color=tk["consigna"], width=1.6, dash="dash"),
                             hovertemplate="%{y:.3f} cm"), row=1, col=1)
    if met["mp"] and met["h_pico"] is not None:
        fig.add_trace(go.Scatter(
            x=[met["tp"] + q["t-esc"]], y=[met["h_pico"]], mode="markers+text",
            marker=dict(size=9, color=tk["nivel"], line=dict(width=2, color=tk["superficie"])),
            text=[f"  Mp {met['mp']:.1f} %"], textposition="middle right",
            textfont=dict(size=11, color=tk["titulo"]), hoverinfo="skip", showlegend=False), row=1, col=1)
    if met["ts"] is not None and met["ts"] > 0:
        fig.add_vline(x=met["ts"] + q["t-esc"], line_color=tk["texto"], line_dash="dot", line_width=1.2,
                      row=1, col=1, annotation_text=f"ts = {met['ts']:.2f} s",
                      annotation_position="bottom right", annotation_font=dict(size=11, color=tk["texto"]))

    escala = [[0, COLOR_ZONA[0]], [0.333, COLOR_ZONA[0]], [0.334, COLOR_ZONA[1]],
              [0.666, COLOR_ZONA[1]], [0.667, COLOR_ZONA[2]], [1, COLOR_ZONA[2]]]
    fig.add_trace(go.Heatmap(x=t, y=[0], z=[zona_de(h, u_am, u_rojo)], zmin=0, zmax=2, colorscale=escala,
                             showscale=False, hoverinfo="skip", name="Alerta"), row=2, col=1)

    fig.add_trace(go.Scatter(x=t, y=e, name="Error e(t)", fill="tozeroy", fillcolor=tk["error_relleno"],
                             line=dict(color=tk["error"], width=2), hovertemplate="%{y:.3f} cm",
                             showlegend=False), row=3, col=1)
    fig.add_hline(y=0, line_color=tk["eje"], line_width=1, row=3, col=1)

    # Caudales de las dos bombas, con su propia leyenda junto al panel
    fig.add_trace(go.Scatter(x=t, y=res["q_l"], name="Entrada (bomba superior)", legend="legend2",
                             line=dict(color=tk["entrada"], width=2), hovertemplate="%{y:.2f} cm³/s"), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=res["q_b"], name="Drenaje (bomba inferior, controlada)", legend="legend2",
                             line=dict(color=tk["control"], width=2), hovertemplate="%{y:.2f} cm³/s"), row=4, col=1)
    q_max = q["Kb"] * q["v-max"] / 100
    fig.add_hline(y=q_max, line_color=tk["texto"], line_width=1, line_dash="dot", row=4, col=1,
                  annotation_text=f"máx. drenaje {q_max:.3g} cm³/s", annotation_position="top left",
                  annotation_font=dict(size=10, color=tk["texto"]))

    _base(fig, tk, altura)
    dominio_4 = fig.layout.yaxis4.domain
    fig.update_layout(hoversubplots="axis", margin=dict(l=62, r=18, t=36, b=44),
                      legend2=dict(orientation="h", x=0.995, xanchor="right", y=dominio_4[1] - 0.005, yanchor="top",
                                   bgcolor=tk["superficie"], bordercolor=tk["eje"], borderwidth=1,
                                   font=dict(size=10.5, color=tk["texto"])))
    fig.update_yaxes(title_text="Nivel [cm]", range=[y_min, y_tope], row=1, col=1)
    fig.update_yaxes(title_text="Alerta", showticklabels=False, showgrid=False, ticks="", showline=False,
                     title_font=dict(size=10), row=2, col=1)
    fig.update_yaxes(title_text="Error [cm]", row=3, col=1)
    fig.update_yaxes(title_text="Caudal [cm³/s]", rangemode="tozero", row=4, col=1)
    fig.update_xaxes(title_text="Tiempo [s]", row=4, col=1)
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1,
                     spikecolor=tk["texto"], spikedash="dot")
    return fig


# ====================================================================
# TANQUE ANIMADO: vidrio, agua con oleaje, dos bombas y sensor
# (el semáforo va aparte, en HTML, y assets/semaforo.js lo sincroniza con la animación)
# ====================================================================
def _marcas_hasta(tope, max_marcas=7):
    """Marcas «redondas» del eje entre 0 y tope (1, 2, 5, 10, 20…)."""
    for paso in (0.5, 1, 2, 5, 10, 20, 50, 100, 200):
        if tope / paso <= max_marcas:
            return list(np.arange(0, tope + 1e-9, paso))
    return None


PX_X, PX_H = 300, 340          # píxeles por unidad de X y por altura del tanque (proporción del dibujo)
RELACION_TANQUE = 1.05         # ancho / alto del gráfico del tanque (incluye márgenes y controles); lo usa app.py


def _en_ruta(puntos, s, H):
    """Puntos repartidos a lo largo de una tubería (polilínea); s = fracciones 0–1 del recorrido."""
    p = np.asarray(puntos, float)
    seg = np.hypot(np.diff(p[:, 0]) * PX_X, np.diff(p[:, 1]) / H * PX_H)   # longitud aproximada en píxeles
    acum = np.concatenate([[0.0], np.cumsum(seg)])
    d = np.asarray(s, float) * acum[-1]
    return np.interp(d, acum, p[:, 0]), np.interp(d, acum, p[:, 1])


def _rgba(color, alfa):
    """Color #rrggbb con transparencia (los tonos de alerta salen de COLOR_ZONA)."""
    c = color.lstrip("#")
    return f"rgba({int(c[0:2], 16)},{int(c[2:4], 16)},{int(c[4:6], 16)},{alfa})"


def fig_tanque(res, tk, altura=500, n_cuadros=90, fallo=False):
    """Tanque animado. Con fallo=True el agua y el borde toman el tono de la zona del semáforo
    (ámbar en precaución, rojo en alerta) y se agrega un botón para reiniciar la animación."""
    t, r, h, q_l, q_b = res["t"], res["r"], res["h"], res["q_l"], res["q_b"]
    u_am, u_rojo = res["q"]["u-am"], res["q"]["u-rojo"]
    H = max(float(np.max(r)), float(np.max(h)), u_rojo) * 1.18       # altura del tanque
    idxs = np.unique(np.linspace(0, len(t) - 1, n_cuadros).astype(int))
    q_ref = max(float(np.max(q_l)), float(np.max(q_b)), 1e-6)         # para escalar los chorros
    xs = np.linspace(-0.5, 0.5, 60)
    X_ENT, Y_ENT = -0.3, 1.1 * H                                       # boca de la tubería de entrada
    Y_DREN = 0.05 * H                                                  # altura del desagüe
    Y_SENS, X_SENS = 1.10 * H, 0.18                                    # base del sensor y eje del haz
    X_PE, X_PD = -0.84, 0.70                                           # centro de la voluta de cada bomba
    PUNTOS = 7                                                         # puntos de flujo por tubería
    ruta_dren = [(0.52, Y_DREN), (0.93, Y_DREN), (0.93, -0.05 * H)]
    zonas = [int(zona_de(h[i], u_am, u_rojo)) for i in idxs]

    # Estado de las bombas en cada cuadro: el giro y el avance del flujo se acumulan solo mientras
    # hay caudal, así que apagada queda quieta.
    f_ent = q_l[idxs] / q_ref
    f_dren = q_b[idxs] / q_ref
    fase_e = np.cumsum(np.where(f_ent > 0.02, 0.012 + 0.06 * f_ent, 0.0)) % 1.0
    fase_d = np.cumsum(np.where(f_dren > 0.02, 0.012 + 0.06 * f_dren, 0.0)) % 1.0
    giro_e = np.cumsum(np.where(f_ent > 0.02, 14 + 50 * f_ent, 0.0))
    giro_d = np.cumsum(np.where(f_dren > 0.02, 14 + 50 * f_dren, 0.0))

    def bomba(k, activa, color, xv, yv, motor, giro, flecha):
        """Motor + voluta + impulsor giratorio + flecha del sentido del flujo (una sola traza)."""
        c = color if activa else tk["error"]                          # apagada: gris
        return go.Scatter(
            x=[motor[0], xv, xv, flecha[0]], y=[motor[1], yv, yv, flecha[1]], mode="markers",
            hoverinfo="skip", showlegend=False,
            marker=dict(symbol=["square", "circle", "cross", "triangle-right"], size=[22, 44, 17, 9],
                        angle=[0, 0, float(giro[k]) % 360, 0], color=[tk["superficie"], tk["superficie"], c, c],
                        line=dict(width=[2, 2.5, 0, 0], color=[c, c, c, c])))

    def trazas(k, i):
        nivel = max(float(h[i]), 0.0)
        fe, fd = float(f_ent[k]), float(f_dren[k])
        act_e, act_d = fe > 0.02, fd > 0.02
        # oleaje: más agitado cuanto más agua entra
        amp = H * (0.005 + 0.014 * min(fe, 1.0))
        sup = nivel + amp * np.sin(2 * np.pi * (1.3 * xs) + 0.55 * k) if nivel > 0 else np.zeros_like(xs)
        poligono = (np.concatenate([[-0.5], xs, [0.5]]), np.concatenate([[0.0], sup, [0.0]]))
        tr = [go.Scatter(x=poligono[0], y=poligono[1], fill="toself", mode="lines", line=dict(width=0),
                         fillgradient=dict(type="vertical", colorscale=[[0, tk["agua_fondo"]], [1, tk["agua_sup"]]]),
                         hoverinfo="skip", showlegend=False)]
        if fallo:
            # tono de alerta sobre el agua y el borde del tanque (transparente en zona normal)
            z = zonas[k]
            tr.append(go.Scatter(x=poligono[0], y=poligono[1], fill="toself", mode="lines", line=dict(width=0),
                                 fillcolor=_rgba(COLOR_ZONA[z], 0.55) if z else "rgba(0,0,0,0)", uid="tintagua",
                                 hoverinfo="skip", showlegend=False))
            tr.append(go.Scatter(x=[-0.52, -0.52, 0.52, 0.52], y=[H, -0.02, -0.02, H], mode="lines", uid="tintborde",
                                 line=dict(color=COLOR_ZONA[z] if z else "rgba(0,0,0,0)", width=7),
                                 hoverinfo="skip", showlegend=False))
        tr.append(go.Scatter(x=xs, y=sup, mode="lines", line=dict(color="rgba(255,255,255,0.55)", width=2),
                             hoverinfo="skip", showlegend=False))
        tr.append(go.Scatter(x=[-0.5, 0.5], y=[r[i], r[i]], mode="lines",
                             line=dict(color=tk["consigna"], width=1.6, dash="dash"), hoverinfo="skip",
                             showlegend=False))
        # bomba superior (lluvia): tubería + chorro hasta el agua, con grosor según el caudal
        ruta_ent = [(-0.75, Y_ENT), (X_ENT, Y_ENT), (X_ENT, nivel)]
        tr.append(go.Scatter(x=[p[0] for p in ruta_ent], y=[p[1] for p in ruta_ent], mode="lines",
                             line=dict(color=tk["agua_sup"], width=1.5 + 4.5 * min(fe, 1.0)),
                             opacity=0.85 if act_e else 0.0, hoverinfo="skip", showlegend=False))
        px, py = _en_ruta(ruta_ent, (np.arange(PUNTOS) / PUNTOS + fase_e[k]) % 1.0, H) if act_e else ([None], [None])
        tr.append(go.Scatter(x=px, y=py, mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(size=4 + 3 * min(fe, 1.0), color="rgba(255,255,255,0.85)")))
        # agua que sale por el desagüe, pasa por la bomba inferior y se descarga
        tr.append(go.Scatter(x=[p[0] for p in ruta_dren], y=[p[1] for p in ruta_dren], mode="lines",
                             line=dict(color=tk["agua_sup"], width=1.5 + 4.5 * min(fd, 1.0)),
                             opacity=0.9 if act_d else 0.0, hoverinfo="skip", showlegend=False))
        px, py = _en_ruta(ruta_dren, (np.arange(PUNTOS) / PUNTOS + fase_d[k]) % 1.0, H) if act_d else ([None], [None])
        tr.append(go.Scatter(x=px, y=py, mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(size=4 + 3 * min(fd, 1.0), color="rgba(255,255,255,0.85)")))
        # sensor ultrasónico: haz hasta la superficie y pulsos de sonido que bajan y rebotan
        y_agua = nivel + amp
        tr.append(go.Scatter(x=[X_SENS, X_SENS], y=[Y_SENS, y_agua], mode="lines",
                             line=dict(color=tk["texto"], width=1, dash="dot"), hoverinfo="skip", showlegend=False))
        ax, ay = [], []
        ang = np.linspace(-1.05, 1.05, 9)
        for u in ((0.075 * k) % 1.0, (0.075 * k + 0.5) % 1.0):
            baja = u < 0.5                                             # primera mitad: onda emitida; segunda: eco
            s = (2 * u) % 1.0
            yc = Y_SENS - s * (Y_SENS - y_agua) if baja else y_agua + s * (Y_SENS - y_agua)
            sag = 0.022 * H
            ax += list(X_SENS + 0.075 * np.sin(ang)) + [None]
            ay += list(yc - sag * np.cos(ang) if baja else yc + sag * np.cos(ang)) + [None]
        tr.append(go.Scatter(x=ax, y=ay, mode="lines", line=dict(color=tk["destacado"], width=2),
                             hoverinfo="skip", showlegend=False))
        # bombas (encima de las tuberías)
        tr.append(bomba(k, act_e, tk["entrada"], X_PE, Y_ENT, (-0.985, Y_ENT), giro_e, (-0.56, Y_ENT)))
        tr.append(bomba(k, act_d, tk["control"], X_PD, Y_DREN, (X_PD, Y_DREN + 0.13 * H), giro_d, (0.86, Y_DREN)))
        return tr

    def anotaciones(i):
        nivel = max(float(h[i]), 0.0)
        return [
            dict(x=-0.53, y=r[i], xref="x", yref="y", text=f"r {r[i]:.1f}", showarrow=False,
                 xanchor="right", font=dict(color=tk["consigna"], size=11)),
            dict(x=0.0, y=min(0.1 * H, max(float(h[i]), 0) * 0.5) + 0.05 * H, xref="x", yref="y",
                 text=f"<b>{h[i]:.2f} cm</b>", showarrow=False, font=dict(color="white", size=15)),
            dict(x=0.5, y=1, xref="paper", yref="paper", yanchor="bottom", yshift=48, showarrow=False,
                 text=f"<b>t = {t[i]:.1f} s</b>", font=dict(size=12, color=tk["titulo"])),
            dict(x=0.5, y=1, xref="paper", yref="paper", yanchor="bottom", yshift=28, showarrow=False,
                 text=(f"<span style='color:{tk['entrada']}'>▼ entra {q_l[i]:.1f}</span>   ·   "
                       f"<span style='color:{tk['control']}'>▲ drena {q_b[i]:.1f}</span>   cm³/s"),
                 font=dict(size=11, color=tk["texto"])),
            # distancia que mide el sensor: altura del sensor − nivel
            dict(x=X_SENS - 0.09, y=(Y_SENS + nivel) / 2, xref="x", yref="y", xanchor="right",
                 text=f"d = {Y_SENS - nivel:.1f} cm", showarrow=False, bgcolor=tk["superficie"], opacity=0.9,
                 bordercolor=tk["eje"], borderpad=2, font=dict(size=10, color=tk["texto"])),
        ] + fijas

    fijas = [dict(x=0.47, y=u, xref="x", yref="y", text=f"{u:g} cm", showarrow=False, xanchor="right",
                  yanchor="bottom", font=dict(size=10, color=COLOR_ZONA[k])) for k, u in ((1, u_am), (2, u_rojo))]
    fijas += [dict(x=X_PE, y=Y_ENT, xref="x", yref="y", yanchor="bottom", yshift=30, text="Bomba de entrada", showarrow=False,
                   font=dict(size=10, color=tk["entrada"])),
              dict(x=X_SENS, y=1.17 * H, xref="x", yref="y", yanchor="bottom", yshift=16, text="Sensor ultrasónico", showarrow=False,
                   font=dict(size=10, color=tk["texto"])),
              dict(x=0.90, y=Y_DREN, xref="x", yref="y", yanchor="bottom", yshift=30, text="Bomba de<br>drenaje", showarrow=False,
                   font=dict(size=10, color=tk["control"]))]
    formas = [dict(type="rect", x0=-0.5, x1=0.5, y0=y0, y1=y1, fillcolor=COLOR_ZONA[k], opacity=0.07,
                   line_width=0, layer="below")
              for k, (y0, y1) in enumerate([(0, u_am), (u_am, u_rojo), (u_rojo, H)])]
    formas += [dict(type="line", x0=-0.5, x1=0.5, y0=u, y1=u, line=dict(color=COLOR_ZONA[k], width=1, dash="dot"))
               for k, u in ((1, u_am), (2, u_rojo))]
    # tanque de vidrio con reflejo (en modo fallo va debajo de las trazas para que el borde de alerta se vea encima)
    formas.append(dict(type="path", path=f"M -0.52 {H} L -0.52 -0.02 L 0.52 -0.02 L 0.52 {H}",
                       line=dict(color=tk["vidrio"], width=4), layer="below" if fallo else "above"))
    formas.append(dict(type="rect", x0=-0.45, x1=-0.42, y0=0.04 * H, y1=0.96 * H, fillcolor="white",
                       opacity=0.18, line_width=0))
    # tuberías (debajo de los chorros para que el agua se vea correr)
    formas.append(dict(type="path", path=f"M -0.75 {Y_ENT} L {X_ENT} {Y_ENT} L {X_ENT} {1.02 * H}",
                       line=dict(color=tk["vidrio"], width=6), layer="below"))
    formas.append(dict(type="path", path=f"M 0.52 {Y_DREN} L 0.93 {Y_DREN} L 0.93 {-0.05 * H}",
                       line=dict(color=tk["vidrio"], width=8), layer="below"))
    # bridas de las bombas y ejes que unen el motor con la voluta
    for xb, yb, alto in ((-0.76, Y_ENT, 0.07), (0.61, Y_DREN, 0.08), (0.785, Y_DREN, 0.08)):
        formas.append(dict(type="rect", x0=xb, x1=xb + 0.02, y0=yb - alto / 2 * H, y1=yb + alto / 2 * H,
                           fillcolor=tk["vidrio"], line_width=0, layer="below"))
    formas.append(dict(type="line", x0=-0.95, x1=-0.91, y0=Y_ENT, y1=Y_ENT, line=dict(color=tk["vidrio"], width=4),
                       layer="below"))
    formas.append(dict(type="line", x0=X_PD, x1=X_PD, y0=Y_DREN + 0.06 * H, y1=Y_DREN + 0.10 * H,
                       line=dict(color=tk["vidrio"], width=4), layer="below"))
    # sensor ultrasónico tipo HC-SR04: cuerpo y soporte anclado al tanque (los transductores van como trazas fijas)
    formas.append(dict(type="path", path=f"M 0.34 {1.135 * H} L 0.52 {1.135 * H} L 0.52 {H}",
                       line=dict(color=tk["vidrio"], width=3), layer="below"))
    formas.append(dict(type="rect", x0=0.02, x1=0.34, y0=Y_SENS, y1=1.17 * H, fillcolor=tk["superficie"],
                       line=dict(color=tk["vidrio"], width=2), layer="below"))

    i0 = idxs[-1]
    fig = go.Figure(data=trazas(len(idxs) - 1, i0))
    # transductores del sensor (emisor y receptor): fijos, al final (los cuadros solo actualizan las primeras trazas)
    for x in (0.10, 0.26):
        fig.add_trace(go.Scatter(x=[x], y=[1.135 * H], mode="markers", hoverinfo="skip", showlegend=False,
                                 marker=dict(symbol="circle", size=19, color=tk["superficie"],
                                             line=dict(width=2.5, color=tk["texto"]))))
        fig.add_trace(go.Scatter(x=[x], y=[1.135 * H], mode="markers", hoverinfo="skip", showlegend=False,
                                 marker=dict(symbol="circle", size=7, color=tk["texto"])))
    fig.frames = [go.Frame(data=trazas(k, i), layout=dict(annotations=anotaciones(i)), name=str(k))
                  for k, i in enumerate(idxs)]
    _base(fig, tk, altura, leyenda=False)
    botones = [dict(label="▶ Reproducir", method="animate",
                    args=[None, dict(frame=dict(duration=70, redraw=True), transition=dict(duration=0),
                                     fromcurrent=False, mode="immediate")]),
               dict(label="❚❚", method="animate",
                    args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])]
    if fallo:
        botones.append(dict(label="⏮ Reiniciar", method="animate",
                            args=[["0"], dict(frame=dict(duration=0, redraw=True), transition=dict(duration=0),
                                              mode="immediate")]))
    fig.update_layout(
        # zona del semáforo en cada cuadro: la lee assets/semaforo.js para encender el semáforo HTML
        meta={"zonas": zonas},
        margin=dict(l=46, r=6, t=84, b=10), hovermode=False,
        # Tamaño: lo da el CSS (aspect-ratio del contenedor); el dibujo mantiene siempre su proporción
        autosize=True, height=None,
        xaxis=dict(range=[-1.08, 1.05], visible=False, fixedrange=True, constrain="domain"),
        # 1 unidad de X ≈ PX_X píxeles y la altura H ≈ PX_H píxeles: el tanque nunca se estira ni se aplasta
        yaxis=dict(range=[-0.07 * H, 1.32 * H], title="Nivel [cm]", fixedrange=True, showgrid=False,
                   tickvals=_marcas_hasta(H),   # sin números por encima del tanque (ahí van bomba y sensor)
                   scaleanchor="x", scaleratio=(PX_H / H) / PX_X, constrain="domain"),
        annotations=anotaciones(i0), shapes=formas,
        updatemenus=[dict(
            type="buttons", direction="left", x=0, y=-0.02, xanchor="left", yanchor="top",
            pad=dict(t=6, r=6), showactive=False, bgcolor=tk["superficie"], bordercolor=tk["eje"],
            font=dict(color=tk["titulo"]), buttons=botones,
        )],
        sliders=[dict(
            active=len(idxs) - 1, x=0.5 if fallo else 0.36, len=0.5 if fallo else 0.64, y=-0.02,
            yanchor="top", pad=dict(t=6),
            currentvalue=dict(visible=False), ticklen=0, tickcolor="rgba(0,0,0,0)",
            font=dict(size=1, color="rgba(0,0,0,0)"), bgcolor=tk["slider"],
            activebgcolor=tk["nivel"], bordercolor=tk["eje"],
            steps=[dict(method="animate", label="", args=[[str(k)], dict(
                mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))])
                for k in range(len(idxs))],
        )],
    )
    return fig


# ====================================================================
# DATOS REALES FRENTE A LA SIMULACIÓN
# ====================================================================
def fig_real_vs_sim(res, real, comp, tk, altura=520):
    """Nivel real y simulado superpuestos, y abajo la diferencia real − simulado."""
    u_am, u_rojo = res["q"]["u-am"], res["q"]["u-rojo"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.07, row_heights=[0.68, 0.32])
    y_tope = max(float(max(np.max(res["h"]), max(real["h"]))) * 1.15, u_am * 1.15)
    _zonas_semaforo(fig, y_tope, u_am, u_rojo, row=1, col=1)
    fig.add_trace(go.Scatter(x=res["t"], y=res["h"], name="Nivel simulado", line=dict(color=tk["nivel"], width=2.5),
                             hovertemplate="%{y:.3f} cm"), row=1, col=1)
    fig.add_trace(go.Scatter(x=real["t"], y=real["h"],
                             name="Nivel real" + (" (ejemplo)" if real.get("ejemplo") else ""),
                             line=dict(color=tk["destacado"], width=2), hovertemplate="%{y:.3f} cm"), row=1, col=1)
    fig.add_trace(go.Scatter(x=res["t"], y=res["r"], name="Consigna",
                             line=dict(color=tk["consigna"], width=1.4, dash="dash"),
                             hovertemplate="%{y:.3f} cm"), row=1, col=1)
    if comp is not None:
        fig.add_trace(go.Scatter(x=comp["t"], y=comp["dif"], name="Real − simulado", fill="tozeroy",
                                 fillcolor=tk["error_relleno"], line=dict(color=tk["error"], width=1.6),
                                 hovertemplate="%{y:+.3f} cm", showlegend=False), row=2, col=1)
        fig.add_hline(y=0, line_color=tk["eje"], line_width=1, row=2, col=1)
    _base(fig, tk, altura)
    fig.update_yaxes(title_text="Nivel [cm]", range=[min(0.0, float(np.min(res["h"]))), y_tope], row=1, col=1)
    fig.update_yaxes(title_text="Diferencia [cm]", row=2, col=1)
    fig.update_xaxes(title_text="Tiempo [s]", row=2, col=1)
    fig.update_layout(hoversubplots="axis")
    return fig


# ====================================================================
# COMPARACIÓN DE SINTONÍAS
# ====================================================================
def fig_comparacion(corridas, actual, u_am, u_rojo, tk, altura=460):
    todas = corridas + [actual]
    y_max = max(max(max(c["h"]), max(c["r"])) for c in todas)
    y_min = min(min(min(c["h"]), 0.0) for c in todas)
    y_tope = max(y_max * 1.15, u_am * 1.15)
    fig = go.Figure()
    _zonas_semaforo(fig, y_tope, u_am, u_rojo)
    for c in corridas:
        fig.add_trace(go.Scatter(x=c["t"], y=c["h"], name=c["nombre"],
                                 line=dict(color=color_comparacion(tk, c["n"]), width=2),
                                 hovertemplate="%{y:.3f} cm"))
    fig.add_trace(go.Scatter(x=actual["t"], y=actual["h"], name=actual["nombre"],
                             line=dict(color=tk["categorica"][0], width=3.2), hovertemplate="%{y:.3f} cm"))
    fig.add_trace(go.Scatter(x=actual["t"], y=actual["r"], name="Consigna actual",
                             line=dict(color=tk["consigna"], width=1.6, dash="dash"), hovertemplate="%{y:.3f} cm"))
    _base(fig, tk, altura, "Tiempo [s]", "Nivel [cm]")
    fig.update_yaxes(range=[y_min, y_tope])
    return fig


# ====================================================================
# ESTABILIDAD Y FRECUENCIA
# ====================================================================
def _rango_plano_s(*grupos):
    """Rango centrado en polos/ceros relevantes, para que las ramas al infinito no aplasten la vista."""
    pts = np.concatenate([np.atleast_1d(np.asarray(g, dtype=complex)) for g in grupos if g is not None]
                         + [np.array([0j])])
    x_min, x_max = float(np.min(pts.real)), max(float(np.max(pts.real)), 0.0)
    span = max(x_max - x_min, 1.0)
    y_max = max(float(np.max(np.abs(pts.imag))) * 1.4, span * 0.4)
    return [x_min - 0.2 * span, x_max + 0.2 * span], [-y_max, y_max]


def _plano_s(fig, tk, altura, xr, yr):
    fig.add_vrect(x0=0, x1=xr[1], fillcolor=COLOR_ZONA[2], opacity=0.06, line_width=0,
                  annotation_text="inestable", annotation_position="top right",
                  annotation_font=dict(size=10, color=COLOR_ZONA[2]))
    fig.add_vline(x=0, line_color=tk["eje"], line_width=1)
    fig.add_hline(y=0, line_color=tk["eje"], line_width=1)
    _base(fig, tk, altura, "Eje real (σ)", "Eje imaginario (jω)")
    fig.update_xaxes(range=xr)
    fig.update_yaxes(range=yr)
    fig.update_layout(hovermode="closest")
    return fig


def fig_root_locus(res, tk, altura=380):
    fig = go.Figure()
    rl, polos = res["rl"], res["polos"]
    if rl is not None:
        loci, polos_ol, ceros_ol = rl
        for i in range(loci.shape[1]):
            fig.add_trace(go.Scatter(x=np.real(loci[:, i]), y=np.imag(loci[:, i]), mode="lines",
                                     line=dict(color=tk["nivel"], width=2), showlegend=(i == 0),
                                     name="Lugar de raíces", hoverinfo="skip"))
        if len(polos_ol):
            fig.add_trace(go.Scatter(x=np.real(polos_ol), y=np.imag(polos_ol), mode="markers", name="Polos LA",
                                     marker=dict(symbol="x", size=10, color=tk["marca"], line=dict(width=2))))
        if len(ceros_ol):
            fig.add_trace(go.Scatter(x=np.real(ceros_ol), y=np.imag(ceros_ol), mode="markers", name="Ceros LA",
                                     marker=dict(symbol="circle-open", size=10, color=tk["marca"], line=dict(width=2))))
    if len(polos):
        fig.add_trace(go.Scatter(x=np.real(polos), y=np.imag(polos), mode="markers", name="Operación actual",
                                 marker=dict(symbol="star", size=15, color=tk["destacado"],
                                             line=dict(width=1.5, color=tk["superficie"]))))
    xr, yr = _rango_plano_s(*(rl[1:] if rl is not None else ()), polos)
    return _plano_s(fig, tk, altura, xr, yr)


def fig_pzmap(res, tk, altura=380):
    polos, ceros = res["polos"], res["ceros"]
    fig = go.Figure()
    if len(polos):
        fig.add_trace(go.Scatter(x=np.real(polos), y=np.imag(polos), mode="markers", name="Polos LC",
                                 marker=dict(symbol="x", size=13, color=tk["marca"], line=dict(width=2.4)),
                                 hovertemplate="σ = %{x:.4f}<br>jω = %{y:.4f}<extra>Polo</extra>"))
    if len(ceros):
        fig.add_trace(go.Scatter(x=np.real(ceros), y=np.imag(ceros), mode="markers", name="Ceros LC",
                                 marker=dict(symbol="circle-open", size=13, color=tk["nivel"], line=dict(width=2.4)),
                                 hovertemplate="σ = %{x:.4f}<br>jω = %{y:.4f}<extra>Cero</extra>"))
    xr, yr = _rango_plano_s(polos, ceros)
    return _plano_s(fig, tk, altura, xr, yr)


def fig_bode(res, tk, altura=430, compacto=False):
    """Magnitud y fase en paneles apilados con el mismo eje de frecuencia (nunca doble eje Y)."""
    w, mag_db, phase_deg = res["w"], res["mag_db"], res["phase_deg"]
    gm_db, pm, wg, wp = res["gm_db"], res["pm"], res["wg"], res["wp"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08 if not compacto else 0.1,
                        subplot_titles=None if compacto else ("Magnitud", "Fase"))
    fig.add_trace(go.Scatter(x=w, y=mag_db, name="Magnitud", fill="tozeroy", fillcolor=tk["nivel_relleno"],
                             line=dict(color=tk["nivel"], width=2.2), hovertemplate="%{y:.1f} dB"), row=1, col=1)
    fig.add_hline(y=0, line_color=tk["eje"], line_width=1, row=1, col=1)
    fig.add_trace(go.Scatter(x=w, y=phase_deg, name="Fase", line=dict(color=tk["fase"], width=2.2),
                             hovertemplate="%{y:.1f}°"), row=2, col=1)
    fig.add_hline(y=-180, line_color=tk["eje"], line_width=1, row=2, col=1)
    fuente = dict(size=10 if compacto else 11, color=tk["titulo"])
    if np.isfinite(wp):
        fig.add_vline(x=wp, line_color=tk["texto"], line_width=1.2, line_dash="dot", row=1, col=1)
        fig.add_vline(x=wp, line_color=tk["texto"], line_width=1.2, line_dash="dot", row=2, col=1,
                      annotation_text=f"MF = {pm:.1f}°" if compacto else f"ωgc={wp:.3g} rad/s · MF={pm:.1f}°",
                      annotation_position="bottom right", annotation_font=fuente)
    if np.isfinite(wg):
        texto = f"ωpc={wg:.3g} rad/s · MG={gm_db:.1f} dB" if np.isfinite(gm_db) else f"ωpc={wg:.3g} rad/s"
        fig.add_vline(x=wg, line_color=tk["destacado"], line_width=1.2, line_dash="dot", row=1, col=1,
                      annotation_text=texto, annotation_position="top right", annotation_font=fuente)
        fig.add_vline(x=wg, line_color=tk["destacado"], line_width=1.2, line_dash="dot", row=2, col=1)
    _base(fig, tk, altura, leyenda=False)
    fig.update_xaxes(type="log")
    fig.update_xaxes(title_text="Frecuencia ω [rad/s]", row=2, col=1)
    fig.update_yaxes(title_text="|L| [dB]" if compacto else "Magnitud [dB]", row=1, col=1)
    fig.update_yaxes(title_text="∠L [°]" if compacto else "Fase [°]", row=2, col=1)
    fig.update_annotations(selector=dict(text="Magnitud"), font_color=tk["titulo"])
    fig.update_annotations(selector=dict(text="Fase"), font_color=tk["titulo"])
    fig.update_layout(margin=dict(l=62, r=18, t=16 if compacto else 34, b=44))
    return fig
