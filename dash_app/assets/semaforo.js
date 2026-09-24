/*
 * Sincroniza el semáforo HTML del Resumen con la animación del tanque (Plotly).
 *
 * La figura del tanque trae en layout.meta.zonas la zona (0 normal, 1 precaución, 2 alerta)
 * de cada cuadro. Mientras se reproduce o se arrastra el deslizador, este script escribe
 * data-anim="<zona>" en el .semaforo-caja de la misma tarjeta y el CSS enciende la luz.
 * No toca clases ni texto que administre React: al recalcular la simulación, Dash crea un
 * semáforo nuevo (con otra key) sin data-anim y vuelve a mostrar la zona final.
 */
(function () {
  "use strict";

  function cajaDe(gd) {
    var tarjeta = gd.closest(".tanque-y-semaforo");
    return tarjeta ? tarjeta.querySelector(".semaforo-caja") : null;
  }

  function mostrar(gd, nombreCuadro) {
    var zonas = gd.layout && gd.layout.meta && gd.layout.meta.zonas;
    var caja = cajaDe(gd);
    var k = Number(nombreCuadro);
    if (!zonas || !caja || !isFinite(k) || zonas[k] === undefined) return;
    caja.setAttribute("data-anim", String(zonas[k]));
  }

  function enganchar(gd) {
    if (gd.__semaforo || typeof gd.on !== "function") return;
    gd.__semaforo = true;
    gd.on("plotly_animatingframe", function (ev) { mostrar(gd, ev && ev.name); });
    gd.on("plotly_sliderchange", function (ev) {
      var args = ev && ev.step && ev.step.args;
      if (args && args[0] && args[0][0] !== undefined) mostrar(gd, args[0][0]);
    });
  }

  var pendiente = false;
  function revisar() {
    pendiente = false;
    document.querySelectorAll(".grafico-tanque .js-plotly-plot").forEach(enganchar);
  }

  function iniciar() {
    new MutationObserver(function () {
      if (!pendiente) { pendiente = true; requestAnimationFrame(revisar); }
    }).observe(document.body, { childList: true, subtree: true });
    revisar();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
