/* Composition d'une session : repliage du catalogue et raccourcis de selection.

   Le catalogue tient sur plusieurs ecrans : chapitres et modules se replient,
   et chaque en-tete replie affiche le compte de ses exercices coches, pour
   qu'un pli ne cache jamais une selection. L'etat des plis suit l'enseignant
   d'une visite a l'autre. */
(function () {
  "use strict";

  var form = document.querySelector("form[action$='/admin/sessions']");
  if (!form) return;

  var boxes = Array.prototype.slice.call(
    form.querySelectorAll("input[name=patterns]"));
  var groups = Array.prototype.slice.call(
    form.querySelectorAll("details.chapter, details.module"));
  var tally = document.getElementById("tally");

  var STORE = "atelier.catalogue.plis";

  function folded() {
    try { return JSON.parse(localStorage.getItem(STORE)) || {}; }
    catch (err) { return {}; }
  }

  function remember() {
    var state = {};
    groups.forEach(function (group) { state[key(group)] = group.open; });
    try { localStorage.setItem(STORE, JSON.stringify(state)); }
    catch (err) { /* navigation privee, mode sans stockage : tant pis */ }
  }

  function key(group) {
    return (group.classList.contains("chapter") ? "c:" : "m:")
      + (group.getAttribute("data-chapter") || group.getAttribute("data-module"));
  }

  function counts() {
    groups.forEach(function (group) {
      var slot = group.querySelector("[data-count]");
      if (!slot) return;
      var inner = Array.prototype.slice.call(
        group.querySelectorAll("input[name=patterns]"));
      var n = inner.filter(function (b) { return b.checked; }).length;
      slot.textContent = n + " / " + inner.length;
      slot.title = n + " exercice" + (n > 1 ? "s coches" : " coche")
        + " sur " + inner.length;
      slot.classList.toggle("none", n === 0);
    });
  }

  function refresh() {
    counts();
    var n = boxes.filter(function (b) { return b.checked; }).length;
    if (!tally) return;
    if (n === 0) {
      // Le formulaire arrive tout decoche, et le serveur refuse une session
      // vide : le dire ici evite un aller-retour pour rien.
      tally.textContent = "Aucun exercice sélectionné : cochez-en au moins un.";
      return;
    }
    tally.textContent = n + (n > 1 ? " exercices sélectionnés" : " exercice sélectionné")
      + " · " + (20 / n).toFixed(2).replace(".", ",") + " point"
      + (20 / n >= 2 ? "s" : "") + " chacun";
  }

  form.addEventListener("click", function (event) {
    var pick = event.target.getAttribute && event.target.getAttribute("data-pick");
    if (!pick) return;
    // Ces boutons vivent dans un <summary> : sans cela, cocher un module
    // le replierait dans le meme geste.
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

  var state = folded();
  groups.forEach(function (group) {
    var saved = state[key(group)];
    if (saved !== undefined) group.open = saved;
    group.addEventListener("toggle", remember);
  });

  refresh();
})();
