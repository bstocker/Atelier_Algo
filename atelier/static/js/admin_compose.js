/* Composition d'une session : raccourcis de selection et poids par exercice. */
(function () {
  "use strict";

  var form = document.querySelector("form[action$='/admin/sessions']");
  if (!form) return;

  var boxes = Array.prototype.slice.call(
    form.querySelectorAll("input[name=patterns]"));
  var tally = document.getElementById("tally");

  function refresh() {
    var n = boxes.filter(function (b) { return b.checked; }).length;
    if (!tally) return;
    if (n === 0) {
      tally.textContent = "Aucun exercice sélectionné : la session en prendra "
        + boxes.length + " par défaut.";
      return;
    }
    tally.textContent = n + (n > 1 ? " exercices sélectionnés" : " exercice sélectionné")
      + " · " + (20 / n).toFixed(2).replace(".", ",") + " point"
      + (20 / n >= 2 ? "s" : "") + " chacun";
  }

  form.addEventListener("click", function (event) {
    var pick = event.target.getAttribute && event.target.getAttribute("data-pick");
    if (!pick) return;
    event.preventDefault();
    if (pick === "level" || pick === "module" || pick === "chapter") {
      var scope = event.target.closest("." + (pick === "level" ? "level-group"
                                            : pick === "module" ? "module"
                                            : "chapter"));
      var inScope = Array.prototype.slice.call(
        scope.querySelectorAll("input[name=patterns]"));
      // Bascule : si tout est deja coche, on decoche.
      var allOn = inScope.every(function (b) { return b.checked; });
      inScope.forEach(function (b) { b.checked = !allOn; });
    } else {
      boxes.forEach(function (b) { b.checked = pick === "all"; });
    }
    refresh();
  });

  boxes.forEach(function (b) { b.addEventListener("change", refresh); });
  refresh();
})();
