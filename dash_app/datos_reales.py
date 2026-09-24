# -*- coding: utf-8 -*-
"""
Lectura de mediciones reales (CSV exportado del ESP32) y comparación con la simulación.

Formato esperado del CSV (encabezados flexibles, separador , o ; y decimales con . o ,):
    t,h            ← tiempo [s] y nivel medido [cm]  (obligatorias)
    t,h,v          ← opcional: señal de la bomba de drenaje [%]
Nombres aceptados: t/tiempo/time/segundos  ·  h/nivel/level/altura  ·  v/pwm/bomba/control
"""

import base64
import io

import numpy as np
import pandas as pd

NOMBRES_T = ("t", "tiempo", "time", "segundos", "seg", "s")
NOMBRES_H = ("h", "nivel", "level", "altura", "distancia_nivel")
NOMBRES_V = ("v", "pwm", "bomba", "control", "u")


def _columna(df, candidatos):
    limpios = {c: c.strip().lower().split("[")[0].split("(")[0].strip() for c in df.columns}
    for c, base in limpios.items():
        if base in candidatos:
            return c
    for c, base in limpios.items():
        if any(base.startswith(k) for k in candidatos if len(k) > 1):
            return c
    return None


def leer_csv(contenido_base64, nombre_archivo):
    """Convierte el archivo subido con dcc.Upload en {t, h, v?, fuente}. Lanza ValueError con
    un mensaje claro si el formato no sirve."""
    _, datos = contenido_base64.split(",", 1)
    crudo = base64.b64decode(datos)
    texto = None
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            texto = crudo.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    df = pd.read_csv(io.StringIO(texto), sep=None, engine="python")
    col_t, col_h, col_v = _columna(df, NOMBRES_T), _columna(df, NOMBRES_H), _columna(df, NOMBRES_V)
    if col_t is None or col_h is None:
        raise ValueError(f"No encontré columnas de tiempo y nivel. Columnas del archivo: {', '.join(df.columns)}. "
                         "Usa encabezados como «t» y «h».")

    def numerica(serie):
        if serie.dtype == object:
            serie = serie.astype(str).str.replace(",", ".", regex=False)
        return pd.to_numeric(serie, errors="coerce")

    tabla = pd.DataFrame({"t": numerica(df[col_t]), "h": numerica(df[col_h])})
    if col_v is not None:
        tabla["v"] = numerica(df[col_v])
    tabla = tabla.dropna(subset=["t", "h"]).sort_values("t")
    if len(tabla) < 2:
        raise ValueError("El archivo tiene menos de 2 mediciones válidas.")
    tabla["t"] = tabla["t"] - tabla["t"].iloc[0]           # el registro empieza en t = 0
    salida = {"t": tabla["t"].round(4).tolist(), "h": tabla["h"].round(4).tolist(),
              "fuente": nombre_archivo, "ejemplo": False}
    if "v" in tabla:
        salida["v"] = tabla["v"].round(3).tolist()
    return salida


def generar_ejemplo(res, semilla=11):
    """
    Datos de EJEMPLO SINTÉTICOS (no son mediciones): la simulación actual con las
    imperfecciones típicas de un montaje real — ruido del sensor ultrasónico (±1.5 mm),
    muestreo cada 0.5 s y una bomba ~8 % más débil que la nominal. Sirven para probar la
    vista combinada antes de tener el ESP32 conectado.
    """
    rng = np.random.default_rng(semilla)
    t = res["t"]
    paso = max(1, int(round(0.5 / (t[1] - t[0]))))
    idx = np.arange(0, len(t), paso)
    # respuesta algo más lenta al drenar: el nivel real se queda un poco por encima
    exceso = np.clip(res["h"] - res["r"], 0, None) * 0.08
    h = res["h"][idx] + exceso[idx] + rng.normal(0, 0.15, len(idx))   # ruido del sensor: σ = 1.5 mm
    return {"t": t[idx].round(3).tolist(), "h": np.clip(h, 0, None).round(3).tolist(),
            "v": (res["v"][idx] * 100).round(1).tolist(),
            "fuente": "Ejemplo sintético (no son mediciones reales)", "ejemplo": True}


def comparar(res, real):
    """Error entre el nivel real y el simulado en el tramo de tiempo común."""
    t_r, h_r = np.asarray(real["t"]), np.asarray(real["h"])
    mascara = (t_r >= res["t"][0]) & (t_r <= res["t"][-1])
    if mascara.sum() < 2:
        return None
    h_sim = np.interp(t_r[mascara], res["t"], res["h"])
    dif = h_r[mascara] - h_sim
    return {"rmse": float(np.sqrt(np.mean(dif ** 2))), "max": float(np.max(np.abs(dif))),
            "media": float(np.mean(dif)), "n": int(mascara.sum()),
            "t": t_r[mascara], "dif": dif, "h_real_final": float(h_r[mascara][-1])}
