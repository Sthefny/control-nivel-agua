# -*- coding: utf-8 -*-
"""
Modelo matemático y análisis del sistema de control de nivel.

Planta (tanque + bomba de 1er orden):
    A * dh/dt = Q_l(t) - Q_b(t)
    tau * dQ_b/dt + Q_b(t) = Kb * v(t)
    Gp(s) = K / (tau*s^2 + s),   K = Kb / A

Todo el cálculo pesado se hace aquí; la interfaz (app.py) solo lo muestra.
"""

import numpy as np
import control as ct

# ----- Semáforo de alerta de inundación -----
NOMBRE_ZONA = ["Normal", "Precaución", "Alerta de inundación"]
# Colores de estado reservados (bueno / advertencia / crítico): nunca se reutilizan para series,
# y siempre van acompañados del nombre de la zona para no depender solo del color.
COLOR_ZONA = ["#0ca30c", "#fab219", "#d03b3b"]
ESTADO_ZONA = ["ok", "warn", "bad"]

# Valores por defecto de la interfaz (también sirven de respaldo si un campo queda vacío)
DEFAULTS = {
    "area": 27.0, "modo-ganancia": "kb", "kb": 10.0, "k-planta": 0.37, "tau": 0.5,
    "ctrl": "PID", "kp": 2.0, "ki": 0.5, "kd": 0.1, "n": 10.0,
    "consigna": "Escalón", "inicio": "reposo", "h0": 2.0, "amp": 1.0, "pendiente": 0.2,
    "t-esc": 0.0, "u-am": 5.0, "u-rojo": 10.0, "t-final": 60.0, "n-puntos": 2000,
    # Bomba superior (entrada de agua / "lluvia"): es la perturbación
    "entrada": "aleatoria", "q-media": 4.0, "q-var": 60.0, "q-cambio": 6.0, "semilla": 7,
    # Bomba inferior (drenaje): es el actuador del controlador; potencia máxima en %
    "v-max": 100.0,
    # Modo de la simulación: "normal" o "fallo" (la bomba de drenaje se detiene en t-fallo)
    "modo": "normal", "fallo": "alerta", "t-fallo": 10.0,
}


# Tolerancia al comparar con los umbrales: si el nivel se asienta justo en uno (p. ej. 10 cm),
# el ruido numérico de la simulación (~1e-7 cm) haría parpadear el semáforo entre dos zonas.
TOL_UMBRAL = 1e-4   # cm, muy por debajo de la resolución de cualquier sensor real


def zona_de(h, u_am, u_rojo):
    """0 = normal, 1 = precaución, 2 = alerta (acepta escalares o arreglos)."""
    return np.where(h >= u_rojo - TOL_UMBRAL, 2, np.where(h >= u_am - TOL_UMBRAL, 1, 0))


def tiempo_en_zonas(t, h, u_am, u_rojo):
    """Segundos que el nivel permanece en cada zona del semáforo."""
    dt = np.diff(t, append=t[-1])
    z = zona_de(h, u_am, u_rojo)
    return [float(dt[z == k].sum()) for k in range(3)]


# ====================================================================
# CONSTRUCCIÓN DEL MODELO
# ====================================================================
def construir_planta(A_tanque, Kb, tau):
    """Gp(s) = K/(tau*s^2 + s) y su representación en espacio de estados."""
    K = Kb / A_tanque
    Gp = ct.tf([K], [tau, 1, 0])
    Ass = np.array([[0.0, 1.0], [0.0, -1.0 / tau]])
    Bss = np.array([[0.0], [-K / tau]])
    Css = np.array([[1.0, 0.0]])
    Dss = np.array([[0.0]])
    return Gp, K, (Ass, Bss, Css, Dss)


def construir_controlador(tipo, Kp, Ki, Kd, N=10.0):
    """C(s) para P / PI / PD / PID; la derivada usa el filtro Kd*N*s/(s+N)."""
    if tipo not in ("P", "PI", "PD", "PID"):
        raise ValueError(f"Tipo de controlador desconocido: {tipo}")
    C = ct.tf([Kp], [1])
    if tipo in ("PI", "PID"):
        C = C + ct.tf([Ki], [1, 0])
    if tipo in ("PD", "PID"):
        C = C + ct.tf([Kd * N, 0], [1, N])
    return C


def generar_consigna(tipo, t, h0, amp_escalon, m_rampa, t_escalon=0.0):
    """Señal de referencia r(t): escalón o rampa a partir de t_escalon."""
    if tipo == "Escalón":
        return np.where(t >= t_escalon, h0 + amp_escalon, h0)
    if tipo == "Rampa":
        return h0 + m_rampa * np.clip(t - t_escalon, a_min=0, a_max=None)
    raise ValueError(f"Tipo de consigna desconocido: {tipo}")


# ====================================================================
# ANÁLISIS
# ====================================================================
def calcular_margenes(L):
    try:
        gm, pm, sm, wg, wp, ws = ct.stability_margins(L)
        return gm, pm, wg, wp
    except Exception:
        return (np.nan,) * 4


def calcular_tipo_y_errores(L):
    """Tipo de sistema (integradores en L) y errores ess ante escalón, rampa y parábola."""
    try:
        n_int = int(np.sum(np.abs(ct.poles(L)) < 1e-6))
    except Exception:
        n_int = 0
    s0 = 1e-6
    try:
        g = abs(np.real(ct.evalfr(L, s0) * (s0 ** n_int)))
    except Exception:
        g = np.nan
    ok = np.isfinite(g) and g > 0
    if n_int == 0:
        return n_int, (1.0 / (1.0 + g) if np.isfinite(g) else np.nan), np.inf, np.inf
    if n_int == 1:
        return n_int, 0.0, (1.0 / g if ok else np.inf), np.inf
    if n_int == 2:
        return n_int, 0.0, 0.0, (1.0 / g if ok else np.inf)
    return n_int, 0.0, 0.0, 0.0


def calcular_lugar_raices(L):
    try:
        rl_map = ct.root_locus_map(L)
        return rl_map.loci, ct.poles(L), ct.zeros(L)
    except Exception:
        return None


def metricas_simulacion(t, r, h, v, tipo_consigna, t_escalon):
    """IAE, ISE, ITAE, esfuerzo de control y (en escalón) Mp, tp y ts (banda 2 %)."""
    e = r - h
    integrar = getattr(np, "trapezoid", None) or np.trapz
    m = dict(iae=float(integrar(np.abs(e), t)), ise=float(integrar(e ** 2, t)),
             itae=float(integrar(t * np.abs(e), t)), v_max=float(np.max(np.abs(v))),
             mp=None, tp=None, h_pico=None, ts=None, banda=None, r_final=float(r[-1]))
    if tipo_consigna != "Escalón":
        return m
    mascara = t >= t_escalon
    if not np.any(mascara):
        return m
    t_m, h_m = t[mascara], h[mascara]
    r_final = r[-1]
    delta = r_final - h_m[0]
    if abs(delta) < 1e-9:
        return m
    m["banda"] = banda = 0.02 * abs(delta)
    fuera = np.where(np.abs(h_m - r_final) > banda)[0]
    if len(fuera) == 0:
        m["ts"] = 0.0
    elif fuera[-1] < len(t_m) - 1:
        m["ts"] = float(t_m[fuera[-1] + 1] - t_escalon)
    desviacion = np.sign(delta) * (h_m - r_final)
    idx = int(np.argmax(desviacion))
    if desviacion[idx] > 0:
        m["mp"] = float(100 * desviacion[idx] / abs(delta))
        m["tp"] = float(t_m[idx] - t_escalon)
        m["h_pico"] = float(h_m[idx])
    else:
        m["mp"] = 0.0
    return m


def limpiar_parametros(p):
    """Rellena campos vacíos con sus valores por defecto y valida rangos.
    Devuelve (parametros, lista_de_errores)."""
    q = {k: (DEFAULTS[k] if p.get(k) in (None, "") else p[k]) for k in DEFAULTS}
    errores = []
    Kb = q["kb"] if q["modo-ganancia"] == "kb" else q["k-planta"] * q["area"]
    q["Kb"] = Kb
    if q["area"] <= 0:
        errores.append("El área del tanque debe ser mayor que cero.")
    if Kb <= 0:
        errores.append("La ganancia de la bomba debe ser mayor que cero.")
    if q["tau"] <= 0:
        errores.append("La constante de tiempo τ debe ser mayor que cero.")
    if q["t-final"] <= 0:
        errores.append("El tiempo final de simulación debe ser mayor que cero.")
    if q["u-rojo"] <= q["u-am"]:
        errores.append("El umbral rojo del semáforo debe ser mayor que el amarillo.")
    if q["q-media"] < 0:
        errores.append("El caudal medio de entrada no puede ser negativo.")
    if q["v-max"] <= 0:
        errores.append("La potencia máxima de la bomba de drenaje debe ser mayor que cero.")
    if q["modo"] == "fallo" and q["t-fallo"] < 0:
        errores.append("El instante del fallo no puede ser negativo.")
    return q, errores


def texto_ganancias(q):
    txt = f"Kp={q['kp']:g}"
    if q["ctrl"] in ("PI", "PID"):
        txt += f" · Ki={q['ki']:g}"
    if q["ctrl"] in ("PD", "PID"):
        txt += f" · Kd={q['kd']:g}"
    return txt


# ====================================================================
# BOMBA SUPERIOR: ENTRADA DE AGUA (PERTURBACIÓN)
# ====================================================================
def generar_entrada(q, t):
    """
    Caudal de la bomba superior Q_l(t) [cm³/s]:
    - "aleatoria": cambia a un valor al azar cada `q-cambio` s dentro de media ± variabilidad,
      con transiciones suaves (como una lluvia que se intensifica y amaina). La `semilla`
      hace que la misma configuración produzca siempre la misma lluvia (reproducible).
    - "constante": caudal fijo igual a la media.
    - "ninguna": sin entrada (solo la respuesta a la consigna).
    """
    media = max(float(q["q-media"]), 0.0)
    if q["entrada"] == "ninguna" or media == 0:
        return np.zeros_like(t)
    if q["entrada"] == "constante":
        return np.full_like(t, media)
    rng = np.random.default_rng(int(q["semilla"]))
    var = np.clip(float(q["q-var"]), 0, 100) / 100.0
    periodo = max(float(q["q-cambio"]), 0.5)
    n_tramos = int(np.ceil(t[-1] / periodo)) + 2
    niveles = media * (1 + var * rng.uniform(-1, 1, n_tramos))
    escalones = niveles[np.minimum((t / periodo).astype(int), n_tramos - 1)]
    # suavizado de 1er orden (constante de tiempo = 1/4 del periodo)
    dt = t[1] - t[0] if len(t) > 1 else 1.0
    a = 1 - np.exp(-dt / (0.25 * periodo))
    q_l = np.empty_like(escalones)
    q_l[0] = escalones[0]
    for i in range(1, len(t)):
        q_l[i] = q_l[i - 1] + a * (escalones[i] - q_l[i - 1])
    return np.clip(q_l, 0, None)


# ====================================================================
# SIMULACIÓN TEMPORAL NO LINEAL (dos bombas, saturación, tanque ≥ 0)
# ====================================================================
def simular_tiempo(q, t, r, q_l, Ki, Kd, info=None):
    """
    Integra el sistema real paso a paso:
        A·dh/dt = Q_l(t) − Q_b(t)                       (tanque)
        τ·dQ_b/dt + Q_b = Kb·v(t)                        (bomba de drenaje, 1er orden)
        v = sat[0, v_max]( Kp·ε + Ki∫ε + Kd·N·s/(s+N)·ε ),   ε = h − r
    La bomba de drenaje solo puede SACAR agua (v ≥ 0) y tiene potencia máxima v_max.
    El integrador usa anti-windup (se congela cuando la bomba está saturada) para que no
    acumule error mientras la bomba no puede responder.
    Devuelve h, v (fracción 0–1) y el caudal realmente drenado.

    Modo "fallo" (opcional): desde t-fallo la bomba de drenaje se detiene (v = 0, el integrador
    se congela) mientras la de entrada sigue funcionando.
      - escenario "alerta": la bomba no se recupera.
      - escenario "precaucion": se repara cuando el nivel alcanza u-am (alguien reacciona al aviso).
    Si se pasa `info` (dict), se rellena con t_caida y t_reparada (None si no ocurrió).
    """
    A, Kb, tau, Kp, N = q["area"], q["Kb"], q["tau"], q["kp"], q["n"]
    v_max = float(q["v-max"]) / 100.0
    n = len(t)
    dt_out = t[1] - t[0] if n > 1 else 0.01
    # sub-pasos para que la integración sea estable aun con τ o 1/N pequeños
    paso_max = min(tau / 4, (1 / (2 * N)) if Kd > 0 else np.inf, 0.05)
    nsub = max(1, int(np.ceil(dt_out / paso_max)))
    dts = dt_out / nsub
    a_bomba = 1 - np.exp(-dts / tau)
    a_filtro = 1 - np.exp(-N * dts)

    if q["inicio"] == "reposo":
        # En reposo a h0: la bomba de drenaje ya compensa la entrada inicial (sin golpe al arrancar)
        h = float(q["h0"])
        qb = float(np.clip(q_l[0], 0, Kb * v_max))
        integ = qb / Kb if Ki > 0 else 0.0
    else:
        h, qb, integ = 0.0, 0.0, 0.0
    filtro = h - r[0]                       # estado del filtro derivativo (derivada inicial nula)

    # Fallo de la bomba de drenaje (solo si el modo es "fallo")
    con_fallo = q.get("modo") == "fallo"
    t_fallo, u_am = float(q["t-fallo"]), float(q["u-am"])
    repara = q.get("fallo") == "precaucion"
    caida, reparada, t_caida, t_reparada = False, False, None, None

    def estado_bomba(tiempo, nivel):
        """Actualiza si el drenaje está caído en este instante (lo deja en `caida`)."""
        nonlocal caida, reparada, t_caida, t_reparada
        if not caida and not reparada and tiempo >= t_fallo:
            caida, t_caida = True, tiempo
        elif caida and repara and nivel >= u_am:
            caida, reparada, t_reparada = False, True, tiempo

    H, V, QB = np.empty(n), np.empty(n), np.empty(n)
    for i in range(n):
        if con_fallo:
            estado_bomba(t[i], h)
        eps = h - r[i]
        d = Kd * N * (eps - filtro) if Kd > 0 else 0.0
        H[i], QB[i] = h, qb
        V[i] = 0.0 if caida else min(max(Kp * eps + integ + d, 0.0), v_max)
        if i == n - 1:
            break
        ql = q_l[i]
        for k in range(nsub):
            if con_fallo:
                estado_bomba(t[i] + k * dts, h)
            eps = h - r[i]
            d = Kd * N * (eps - filtro) if Kd > 0 else 0.0
            sin_sat = Kp * eps + integ + d
            v = 0.0 if caida else min(max(sin_sat, 0.0), v_max)
            if Ki > 0 and not caida and not ((sin_sat > v_max and eps > 0) or (sin_sat < 0 and eps < 0)):
                integ += Ki * eps * dts
            filtro += (eps - filtro) * a_filtro
            qb += (Kb * v - qb) * a_bomba
            h += (ql - qb) / A * dts
            if h < 0:                        # tanque vacío: la bomba no puede sacar más agua
                h = 0.0
    if info is not None:
        info.update(t_caida=t_caida, t_reparada=t_reparada)
    return H, V, QB


# ====================================================================
# SIMULACIÓN COMPLETA
# ====================================================================
def simular(q):
    """Construye el lazo, simula y calcula todos los análisis. Devuelve un dict."""
    ctrl = q["ctrl"]
    Ki = q["ki"] if ctrl in ("PI", "PID") else 0.0
    Kd = q["kd"] if ctrl in ("PD", "PID") else 0.0
    Gp, K, ss = construir_planta(q["area"], q["Kb"], q["tau"])
    C = construir_controlador(ctrl, q["kp"], Ki, Kd, q["n"])
    L = C * Gp
    T_lc = ct.feedback(L, 1)
    # Efecto de la entrada de agua sobre el nivel con el lazo cerrado: H/Q_l = (1/(A·s)) / (1 + L)
    Gd = ct.tf([1.0 / q["area"]], [1, 0])
    T_pert = ct.minreal(Gd / (1 + L), verbose=False)

    t = np.linspace(0, q["t-final"], int(q["n-puntos"]))
    amp = q["amp"] if q["consigna"] == "Escalón" else 0.0
    pend = q["pendiente"] if q["consigna"] == "Rampa" else 0.0
    r = generar_consigna(q["consigna"], t, q["h0"], amp, pend, q["t-esc"])
    q_l = generar_entrada(q, t)
    info_fallo = {}
    h, v, q_b = simular_tiempo(q, t, r, q_l, Ki, Kd, info_fallo)
    e = r - h

    w = np.logspace(-3, 3, 1200)
    resp = ct.frequency_response(L, w)
    mag_db = 20 * np.log10(np.clip(resp.magnitude, 1e-12, None))
    phase_deg = np.degrees(resp.phase)
    gm, pm, wg, wp = calcular_margenes(L)
    gm_db = 20 * np.log10(gm) if np.isfinite(gm) and gm > 0 else np.inf

    polos = ct.poles(T_lc)
    ceros = ct.zeros(T_lc)
    estable = bool(np.all(np.real(polos) < 0)) if len(polos) else False
    n_int, ess_step, ess_ramp, ess_parab = calcular_tipo_y_errores(L)
    try:
        info_step = ct.step_info(T_lc)
    except Exception:
        info_step = None
    met = metricas_simulacion(t, r, h, v, q["consigna"], q["t-esc"])
    if q["entrada"] != "ninguna":
        # Con lluvia el nivel no responde solo a la consigna: sobreimpulso y asentamiento del
        # escalón pierden sentido, así que no se informan (se usa el exceso sobre el objetivo).
        met.update(mp=None, tp=None, h_pico=None, ts=None, banda=None)
    met["exceso"] = float(max(np.max(h - r), 0.0))

    u_am, u_rojo = q["u-am"], q["u-rojo"]
    h_max = float(np.max(h))
    v_max = float(q["v-max"]) / 100.0
    return dict(
        q=q, Gp=Gp, C=C, L=L, T=T_lc, T_pert=T_pert, K=K, ss=ss,
        t=t, r=r, h=h, e=e, v=v, q_l=q_l, q_b=q_b, fallo=info_fallo if q["modo"] == "fallo" else None,
        uso_drenaje=float(np.mean(v) / v_max * 100) if v_max > 0 else 0.0,
        t_saturada=float(np.sum(np.diff(t, append=t[-1])[v >= v_max - 1e-9])),
        w=w, mag_db=mag_db, phase_deg=phase_deg, gm_db=gm_db, pm=pm, wg=wg, wp=wp,
        polos=polos, ceros=ceros, estable=estable, rl=calcular_lugar_raices(L),
        n_int=n_int, ess=(ess_step, ess_ramp, ess_parab), info_step=info_step, met=met,
        h_max=h_max, zona_final=int(zona_de(h[-1], u_am, u_rojo)),
        zona_max=int(zona_de(h_max, u_am, u_rojo)), t_zonas=tiempo_en_zonas(t, h, u_am, u_rojo),
    )


def resumen_para_comparar(res, nombre, color, max_puntos=400):
    """Versión liviana (serializable a JSON) de una simulación, para guardarla."""
    paso = max(1, len(res["t"]) // max_puntos)
    pm = res["pm"]
    return dict(
        nombre=nombre, color=color,
        t=res["t"][::paso].tolist(), h=res["h"][::paso].tolist(), r=res["r"][::paso].tolist(),
        mp=res["met"]["mp"], ts=res["met"]["ts"], iae=res["met"]["iae"],
        h_max=res["h_max"], zona_max=res["zona_max"], estable=res["estable"],
        pm=float(pm) if np.isfinite(pm) else None,
    )
