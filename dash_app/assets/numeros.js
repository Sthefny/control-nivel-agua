/*
 * Números animados en las tarjetas KPI.
 *
 * Cada tarjeta tiene <span class="kpi-num" data-clave="…">
 *   <span class="kpi-real">3.25</span>          ← lo escribe React (Dash)
 *   <span class="kpi-anim" aria-hidden></span>  ← lo escribe este script
 * </span>
 * Cuando cambia el valor real, el número visible "cuenta" desde el valor anterior
 * hasta el nuevo. Nunca se modifica kpi-real, así React sigue siendo el dueño del dato.
 * Con "reducir movimiento" activado en el sistema, el valor cambia sin animación.
 */
(function () {
  "use strict";
  var DURACION = 380;                                    // ms: corto, es una indicación de cambio
  var anteriores = new Map();                            // clave de la tarjeta → último valor mostrado
  var reducir = window.matchMedia("(prefers-reduced-motion: reduce)");
  var salida = function (t) { return 1 - Math.pow(1 - t, 3); };   // ease-out cúbico

  function leer(texto) {
    var m = texto.trim().match(/^([+-]?)(\d+(?:\.(\d+))?)$/);
    if (!m) return null;
    return { v: parseFloat(texto), dec: m[3] ? m[3].length : 0, signo: m[1] === "+" };
  }

  function formato(v, p) {
    var s = v.toFixed(p.dec);
    return p.signo && v >= 0 ? "+" + s : s;
  }

  function actualizar(el) {
    var real = el.querySelector(".kpi-real");
    var anim = el.querySelector(".kpi-anim");
    if (!real || !anim) return;
    var texto = real.textContent;
    if (el.dataset.mostrado === texto) return;           // sin cambios
    el.dataset.mostrado = texto;

    var clave = el.dataset.clave;
    var nuevo = leer(texto);
    var antes = anteriores.get(clave);
    anteriores.set(clave, nuevo ? nuevo.v : null);
    if (el._raf) cancelAnimationFrame(el._raf);

    if (!nuevo || antes == null || antes === nuevo.v || reducir.matches) {
      anim.textContent = texto;
      return;
    }
    var t0 = performance.now();
    function paso(ahora) {
      var k = Math.min(1, (ahora - t0) / DURACION);
      anim.textContent = k < 1 ? formato(antes + (nuevo.v - antes) * salida(k), nuevo) : texto;
      if (k < 1) el._raf = requestAnimationFrame(paso);
    }
    anim.textContent = formato(antes, nuevo);
    el._raf = requestAnimationFrame(paso);
  }

  var pendiente = false;
  function revisar() {
    pendiente = false;
    document.querySelectorAll(".kpi-num").forEach(actualizar);
  }

  function iniciar() {
    document.documentElement.classList.add("js-numeros");
    new MutationObserver(function () {
      if (!pendiente) { pendiente = true; requestAnimationFrame(revisar); }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
    revisar();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
