/* Suivi direct cote enseignant.
   PythonAnywhere n'offre pas de WebSocket : on interroge le serveur toutes
   les 3 secondes. La charge reste faible (une requete par enseignant). */
(function () {
  "use strict";

  var POLL_MS = 3000;
  var STALE_MS = 30000;   // au-dela, l'étudiant est considere inactif

  var stamp = document.getElementById("live-stamp");
  var stats = document.getElementById("stats");
  var head = document.getElementById("live-head");
  var body = document.getElementById("live-body");

  function tile(label, value, unit, hero) {
    var box = document.createElement("div");
    box.className = hero ? "tile hero" : "tile";
    var lab = document.createElement("span");
    lab.className = "tile-label";
    lab.textContent = label;
    var val = document.createElement("div");
    val.className = value === "\u2014" ? "tile-value empty" : "tile-value";
    val.textContent = value;
    if (unit) {
      var u = document.createElement("span");
      u.className = "tile-unit";
      u.textContent = " " + unit;
      val.appendChild(u);
    }
    box.appendChild(lab);
    box.appendChild(val);
    return box;
  }

  function renderStats(data) {
    stats.textContent = "";
    stats.appendChild(tile(
      "Moyenne de la classe",
      data.stats.average === null ? "—" : data.stats.average.toFixed(2),
      "/ 20", true));
    stats.appendChild(tile("Étudiants connectés", data.stats.count));
    stats.appendChild(tile("Copies remises",
      data.stats.finished + " / " + data.stats.count));
    stats.appendChild(tile("Sorties de fenêtre", data.stats.exits));
    stats.appendChild(tile("Essais manqués", data.stats.wrong));
  }

  function th(text, cls) {
    var node = document.createElement("th");
    node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  function td(text, cls) {
    var node = document.createElement("td");
    node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  function renderHead(data) {
    head.textContent = "";
    var row = document.createElement("tr");
    row.appendChild(th("Étudiant"));
    // Les sorties passent en deuxième : c'est ce que l'enseignant surveille
    // en priorité pendant l'épreuve.
    row.appendChild(th("Sorties"));
    // Le titre ouvre la fiche de l'exercice (cf. admin_preview.js).
    data.patterns.forEach(function (p) {
      var cell = th("", "rotate");
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = p.name;
      button.setAttribute("data-detail", p.key);
      button.setAttribute("aria-haspopup", "dialog");
      button.title = "Voir les attendus de l'exercice";
      cell.appendChild(button);
      row.appendChild(cell);
    });
    row.appendChild(th("Réussis"));
    row.appendChild(th("Essais manqués"));
    row.appendChild(th("Pénalité"));
    row.appendChild(th("Note /20"));
    row.appendChild(th("\u00c9tat"));
    head.appendChild(row);
  }

  function renderBody(data, now) {
    body.textContent = "";
    if (!data.students.length) {
      var empty = document.createElement("tr");
      var cell = document.createElement("td");
      cell.colSpan = data.patterns.length + 7;
      cell.className = "muted";
      cell.textContent = data.status === "open"
        ? "En attente des étudiants…"
        : "Aucun étudiant n'a rejoint cette session.";
      empty.appendChild(cell);
      body.appendChild(empty);
      return;
    }

    data.students.forEach(function (s) {
      var row = document.createElement("tr");
      var seen = s.last_seen ? Date.parse(s.last_seen) : 0;
      if (!s.finished && now - seen > STALE_MS) row.className = "stale";

      var nom = td(s.name);
      // La couleur alerte au premier coup d'œil ; le compte, juste à côté,
      // porte l'information pour ne jamais dépendre de la seule teinte.
      if (s.exits >= 2) {
        nom.className = "name-alert";
        nom.title = s.exits + " sorties de fenêtre";
      } else if (s.exits === 1) {
        nom.className = "name-warn";
        nom.title = "1 sortie de fenêtre";
      }
      row.appendChild(nom);
      row.appendChild(td(String(s.exits), "num"));

      s.cells.forEach(function (c) {
        var cell = document.createElement("td");
        cell.className = "cell";
        var dot = document.createElement("span");
        // Glyphe + title : le statut ne repose jamais sur la couleur seule.
        if (c.solved) {
          // Un exercice trouve apres des essais manques ne vaut plus le
          // meme nombre de points : la pastille le dit.
          dot.className = c.wrong ? "dot done costly" : "dot done";
          dot.textContent = "✓";
          dot.title = "Reussi en " + c.attempts + " tentative(s)"
            + (c.wrong ? ", dont " + c.wrong + " essai(s) manqué(s)" : "");
        } else if (c.attempts > 0) {
          dot.className = "dot tried";
          dot.textContent = c.attempts;
          dot.title = c.attempts + " tentative(s), pas encore réussi";
        } else {
          dot.className = "dot";
          dot.textContent = "·";
          dot.title = "Pas encore aborde";
        }
        cell.appendChild(dot);
        row.appendChild(cell);
      });

      row.appendChild(td(s.solved + " / " + s.total, "num"));
      var wrong = td(s.wrong ? String(s.wrong) : "—", "num");
      if (s.lost > 0) {
        wrong.className = "num name-warn";
        wrong.title = s.lost.toFixed(2).replace(".", ",")
          + " point(s) laissé(s) en essais manqués";
      }
      row.appendChild(wrong);
      row.appendChild(td(s.penalty ? "−" + s.penalty.toFixed(0) : "—", "num"));
      row.appendChild(td(s.score.toFixed(2), "num strong"));

      var state = document.createElement("td");
      var pill = document.createElement("span");
      pill.className = "pill" + (s.finished ? " ok" : "");
      pill.textContent = s.finished ? "remise"
        : (now - seen > STALE_MS ? "inactif" : "en cours");
      state.appendChild(pill);
      row.appendChild(state);

      body.appendChild(row);
    });
  }

  var lastSignature = "";

  function tick() {
    fetch(window.LIVE_URL, { credentials: "same-origin" })
      .then(function (r) {
        if (r.status === 401) { window.location.href = "/admin/login"; return null; }
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (!data) { stamp.textContent = "hors ligne"; return; }
        var now = Date.now();
        renderStats(data);
        var signature = JSON.stringify(data.patterns);
        if (signature !== lastSignature) { renderHead(data); lastSignature = signature; }
        renderBody(data, now);
        stamp.textContent = data.status === "open"
          ? "en direct · " + new Date().toLocaleTimeString("fr-FR")
          : "session " + (data.status === "closed" ? "clôturée" : "en brouillon");
      })
      .catch(function () { stamp.textContent = "hors ligne"; });
  }

  tick();
  setInterval(tick, POLL_MS);
})();
