/* Page étudiant : navigation entre motifs, menus a compléter, correction.
   Aucune reponse attendue ne transite ici : le serveur seul sait si la
   selection reproduit la cible. */
(function () {
  "use strict";

  var el = {
    gate: document.getElementById("gate"),
    gateHint: document.getElementById("gate-hint"),
    start: document.getElementById("start-btn"),
    app: document.getElementById("app"),
    nav: document.getElementById("tasknav"),
    name: document.getElementById("task-name"),
    brief: document.getElementById("task-brief"),
    state: document.getElementById("task-state"),
    target: document.getElementById("target"),
    output: document.getElementById("output"),
    code: document.getElementById("code"),
    blanks: document.getElementById("blanks"),
    check: document.getElementById("check-btn"),
    feedback: document.getElementById("feedback"),
    finish: document.getElementById("finish-btn"),
    finishHint: document.getElementById("finish-hint"),
    progressPill: document.getElementById("progress-pill"),
    penaltyPill: document.getElementById("penalty-pill")
  };

  var tasks = [];
  var current = null;      // donnees de l'exercice affiché
  var selection = {};

  function esc(text) {
    return String(text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function api(url, options) {
    return fetch(url, Object.assign({ credentials: "same-origin" }, options))
      .then(function (r) {
        if (r.status === 401) { window.location.href = "/"; throw new Error("auth"); }
        if (!r.ok) throw new Error("http " + r.status);
        return r.json();
      });
  }

  function postJSON(url, body) {
    return api(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
  }

  // --- Affichage ----------------------------------------------------------

  function showProgress(p) {
    el.progressPill.textContent = p.solved + " / " + p.total + " motifs";
    if (p.penalty > 0) {
      el.penaltyPill.hidden = false;
      el.penaltyPill.textContent = String.fromCharCode(8722)
        + p.penalty.toFixed(0) + " pts · " + p.exits + " sortie"
        + (p.exits > 1 ? "s" : "");
    }
    el.finishHint.textContent = "Note actuelle : " + p.score.toFixed(2)
      + " / 20. La remise est définitive.";
  }

  function renderNav() {
    el.nav.textContent = "";
    tasks.forEach(function (task) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = (task.solved ? "✓ " : "") + task.name;
      btn.className = task.solved ? "done" : "";
      if (current && current.key === task.key) btn.setAttribute("aria-current", "true");
      btn.addEventListener("click", function () { loadTask(task.key); });
      el.nav.appendChild(btn);
    });
  }

  function renderCode() {
    var html = esc(current.code_template);
    current.blanks.forEach(function (blank) {
      var chosen = selection[blank.id];
      var replacement;
      if (chosen) {
        var opt = blank.options.filter(function (o) { return o.id === chosen; })[0];
        replacement = '<span class="fill">' + esc(opt.c) + "</span>";
      } else {
        replacement = '<span class="empty">__________</span>';
      }
      html = html.split("@" + blank.id + "@").join(replacement);
    });
    el.code.innerHTML = html;
  }

  function renderBlanks() {
    el.blanks.textContent = "";
    current.blanks.forEach(function (blank) {
      var label = document.createElement("label");
      label.textContent = blank.label;

      var select = document.createElement("select");
      var placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "— choisir —";
      select.appendChild(placeholder);

      blank.options.forEach(function (opt) {
        var option = document.createElement("option");
        option.value = opt.id;
        option.textContent = opt.c;
        if (selection[blank.id] === opt.id) option.selected = true;
        select.appendChild(option);
      });

      select.addEventListener("change", function () {
        if (select.value) selection[blank.id] = select.value;
        else delete selection[blank.id];
        renderCode();
        el.feedback.textContent = "";
        el.feedback.className = "feedback";
      });

      label.appendChild(select);
      el.blanks.appendChild(label);
    });
  }

  function renderLines(node, lines, marks) {
    node.textContent = "";
    lines.forEach(function (line, idx) {
      var span = document.createElement("span");
      span.className = marks && marks[idx] === false ? "bad" : "good";
      // Les spans sont en display:block : un \n en plus doublerait l'interligne
      // et le motif ne se lirait plus comme une forme.
      span.textContent = (line === null || line === undefined) ? " " : line;
      node.appendChild(span);
    });
  }

  function loadTask(key) {
    return api("/api/task/" + encodeURIComponent(key)).then(function (data) {
      current = data;
      selection = Object.assign({}, data.selection);
      el.name.textContent = data.name;
      el.brief.textContent = data.brief + " — " + data.why;
      el.state.textContent = data.solved
        ? "✓ réussi" : "en cours · " + data.attempts + " tentative"
          + (data.attempts > 1 ? "s" : "");
      el.state.className = data.solved ? "pill ok" : "pill";
      renderLines(el.target, data.target);
      el.output.textContent = "Complétez les menus puis compilez.";
      el.feedback.textContent = "";
      el.feedback.className = "feedback";
      renderBlanks();
      renderCode();
      renderNav();
    });
  }

  // --- Actions ------------------------------------------------------------

  el.check.addEventListener("click", function () {
    if (!current) return;
    el.check.disabled = true;
    postJSON("/api/task/" + encodeURIComponent(current.key) + "/check",
             { selection: selection })
      .then(function (res) {
        if (!res.complete) {
          el.feedback.textContent = res.message;
          el.feedback.className = "feedback ko";
          return;
        }
        var marks = res.diff.map(function (d) { return d.ok; });
        renderLines(el.output, res.diff.map(function (d) { return d.got; }), marks);
        if (res.ok) {
          el.feedback.textContent = res.first_time
            ? "Exact. Motif validé."
            : "Exact (motif déjà validé).";
          el.feedback.className = "feedback ok";
          el.state.textContent = "✓ réussi";
          el.state.className = "pill ok";
          tasks.forEach(function (t) { if (t.key === current.key) t.solved = true; });
          renderNav();
        } else {
          current.attempts += 1;
          el.state.textContent = "en cours · " + current.attempts + " tentative"
            + (current.attempts > 1 ? "s" : "");
          var wrong = res.diff.filter(function (d) { return !d.ok; }).length;
          el.feedback.textContent = wrong + " ligne" + (wrong > 1 ? "s" : "")
            + " différente" + (wrong > 1 ? "s" : "") + " de la cible.";
          el.feedback.className = "feedback ko";
        }
        showProgress(res.progress);
      })
      .catch(function () {
        el.feedback.textContent = "Erreur réseau. Réessayez.";
        el.feedback.className = "feedback ko";
      })
      .then(function () { el.check.disabled = false; });
  });

  el.finish.addEventListener("click", function () {
    if (!window.confirm("Remettre votre copie ? Vous ne pourrez plus répondre.")) return;
    el.finish.disabled = true;
    postJSON("/api/finish").then(function (res) {
      if (window.Proctor) window.Proctor.stop();
      window.location.href = res.redirect;
    }).catch(function () { el.finish.disabled = false; });
  });

  el.start.addEventListener("click", function () {
    el.start.disabled = true;
    window.Proctor.start({
      onPenalty: function (data) { showProgress(data.progress); }
    }).then(function (fullscreen) {
      if (!fullscreen) {
        el.gateHint.textContent = "Le plein écran a ete refusé par le "
          + "navigateur : la surveillance se limite au changement d'onglet.";
      }
      return api("/api/me");
    }).then(function (me) {
      if (me.finished || me.session_status !== "open") {
        window.location.href = "/terminé";
        return;
      }
      tasks = me.tasks;
      showProgress(me.progress);
      el.gate.hidden = true;
      el.app.hidden = false;
      return loadTask(tasks[0].key);
    }).catch(function () {
      el.start.disabled = false;
      el.gateHint.textContent = "Impossible de charger les exercices. Réessayez.";
    });
  });

  // Battement de coeur : alimente la colonne « dernière activité » cote
  // enseignant et detecte la cloture de la session.
  setInterval(function () {
    if (el.app.hidden) return;
    postJSON("/api/heartbeat").then(function (p) {
      showProgress(p);
    }).catch(function () {});
  }, 10000);

  setInterval(function () {
    if (el.app.hidden) return;
    api("/api/me").then(function (me) {
      if (me.session_status === "closed") {
        if (window.Proctor) window.Proctor.stop();
        window.location.href = "/terminé";
      }
    }).catch(function () {});
  }, 15000);
})();
