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
    module: document.getElementById("task-module"),
    level: document.getElementById("task-level"),
    brief: document.getElementById("task-brief"),
    panel: document.querySelector(".panel"),
    state: document.getElementById("task-state"),
    stakes: document.getElementById("task-stakes"),
    target: document.getElementById("target"),
    output: document.getElementById("output"),
    code: document.getElementById("code"),
    blanks: document.getElementById("blanks"),
    panes: document.getElementById("panes"),
    targetPane: document.getElementById("target-pane"),
    codeTitle: document.getElementById("code-title"),
    predictBox: document.getElementById("predict-box"),
    predictInput: document.getElementById("predict-input"),
    targetTitle: document.getElementById("target-title"),
    outputTitle: document.getElementById("output-title"),
    diagBox: document.getElementById("diag-box"),
    diagLegend: document.getElementById("diag-legend"),
    diagList: document.getElementById("diag-list"),
    diagNote: document.getElementById("diag-note"),
    lesson: document.getElementById("lesson"),
    lessonList: document.getElementById("lesson-list"),
    lessonFormat: document.getElementById("lesson-format"),
    lessonFormatLines: document.getElementById("lesson-format-lines"),
    traceBox: document.getElementById("trace-box"),
    traceBody: document.getElementById("trace-body"),
    check: document.getElementById("check-btn"),
    feedback: document.getElementById("feedback"),
    finish: document.getElementById("finish-btn"),
    confirmBox: document.getElementById("confirm-overlay"),
    confirmRecap: document.getElementById("confirm-recap"),
    confirmYes: document.getElementById("confirm-yes"),
    confirmNo: document.getElementById("confirm-no"),
    finishHint: document.getElementById("finish-hint"),
    progressPill: document.getElementById("progress-pill"),
    penaltyPill: document.getElementById("penalty-pill")
  };

  // Mode examen : ni note, ni verdict, ni vert. Le serveur ne les envoie
  // pas non plus (cf. `in_exam` dans student.py) ; ce drapeau ne commande
  // que l'habillage — les libellés, et la liste du bandeau supérieur.
  var EXAM = !!(window.ATELIER && window.ATELIER.exam);

  var tasks = [];
  var progress = null;     // dernier état renvoyé par le serveur
  var modules = [];        // intitulés des modules couverts par la session
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

  // Les points s'ecrivent a la francaise, virgule comprise : ce sont des
  // notes, l'eleve doit les relire sans traduire.
  function points(value) {
    return value.toFixed(2).replace(".", ",") + " pt" + (value >= 2 ? "s" : "");
  }

  // Nombre de tentatives, en mots : sert d'etat d'exercice en mode examen,
  // la ou le mode ordinaire annonce « reussi ».
  function attemptLabel(attempts) {
    return attempts
      ? "répondu · " + attempts + " tentative" + (attempts > 1 ? "s" : "")
      : "pas encore répondu";
  }

  function showProgress(p) {
    progress = p;
    // En examen, le compteur dit combien de questions sont traitees. Le
    // nombre de reussites, lui, ne sort pas du serveur.
    el.progressPill.textContent = p.exam
      ? p.answered + " / " + p.total + " traités"
      : p.solved + " / " + p.total + " motifs";
    // Les penalites restent affichees dans les deux modes : une sanction
    // annoncee avant l'epreuve doit se voir pendant.
    if (p.penalty > 0) {
      el.penaltyPill.hidden = false;
      el.penaltyPill.textContent = String.fromCharCode(8722)
        + p.penalty.toFixed(0) + " pts · " + p.exits + " sortie"
        + (p.exits > 1 ? "s" : "");
    }
    el.finishHint.textContent = p.exam
      ? "Questions traitées : " + p.answered + " / " + p.total
        + ". La remise est définitive."
      : "Note actuelle : " + p.score.toFixed(2) + " / 20"
        + (p.lost > 0 ? " · " + points(p.lost) + " laissés en essais manqués"
                      : "")
        + ". La remise est définitive.";
  }

  // Cout reel de l'essai qui vient d'etre fait : l'ecart entre ce que
  // l'exercice valait et ce qu'il vaut. Un motif deja valide ne perd rien,
  // et un motif deja tombe a zero ne peut plus tomber plus bas.
  function lossNote(before, after, wasSolved) {
    if (wasSolved) return " Ce motif est déjà validé : rien ne vous est retiré.";
    var lost = before ? Math.max(0, before.worth - after.worth) : after.cost;
    return lost > 0
      ? " Cet essai manqué coûte " + points(lost) + "."
      : " Ce motif ne rapporte plus de points.";
  }

  function showStakes(stakes, solved) {
    if (!stakes) { el.stakes.hidden = true; return; }
    el.stakes.hidden = false;
    if (solved) {
      el.stakes.className = "pill ok";
      el.stakes.textContent = "acquis : " + points(stakes.worth)
        + " sur " + points(stakes.value);
    } else if (stakes.worth <= 0) {
      el.stakes.className = "pill warn";
      el.stakes.textContent = "ne rapporte plus de points";
    } else if (stakes.wrong > 0) {
      el.stakes.className = "pill warn";
      el.stakes.textContent = "vaut encore " + points(stakes.worth)
        + " sur " + points(stakes.value);
    } else {
      el.stakes.className = "pill";
      el.stakes.textContent = "vaut " + points(stakes.value);
    }
    el.stakes.title = "Chaque essai manqué coûte " + points(stakes.cost)
      + " ; " + stakes.tries + " essais manqués ramènent cet exercice à zéro."
      + (stakes.wrong ? " Essais manqués : " + stakes.wrong + "." : "");
  }

  function levelDots(level) {
    // Mêmes repères que côté enseignant : des points autant qu'une couleur,
    // pour que la difficulté reste lisible en niveaux de gris.
    var dots = document.createElement("span");
    dots.className = "level-dots lvl" + level;
    dots.setAttribute("aria-hidden", "true");
    dots.textContent = "●".repeat(level) + "○".repeat(4 - level);
    return dots;
  }

  function navButton(task) {
    var btn = document.createElement("button");
    btn.type = "button";
    // En examen, la case cochee dit « traite », pas « juste » : d'ou une
    // teinte neutre et une case a cocher, et non le vert du mode ordinaire.
    btn.className = EXAM ? (task.answered ? "answered" : "")
                         : (task.solved ? "done" : "");
    btn.title = "Difficulté : " + task.level_name
      + (EXAM ? " · " + (task.answered ? "question traitée"
                                       : "pas encore traitée") : "");
    btn.appendChild(levelDots(task.level));
    btn.appendChild(document.createTextNode(
      (EXAM ? (task.answered ? "☑ " : "☐ ") : (task.solved ? "✓ " : ""))
      + task.name));
    if (current && current.key === task.key) {
      btn.setAttribute("aria-current", "true");
    }
    btn.addEventListener("click", function () { loadTask(task.key); });
    return btn;
  }

  function renderNav() {
    el.nav.textContent = "";

    // Un seul module : les boutons suffisent. Plusieurs : on les sépare par
    // module, sinon l'élève ne sait plus de quel sujet relève un exercice.
    if (modules.length < 2) {
      tasks.forEach(function (task) { el.nav.appendChild(navButton(task)); });
      return;
    }
    modules.forEach(function (title) {
      var group = document.createElement("div");
      group.className = "nav-module";
      var label = document.createElement("span");
      label.className = "nav-module-title";
      label.textContent = title;
      group.appendChild(label);
      tasks.filter(function (t) { return t.module === title; })
           .forEach(function (task) { group.appendChild(navButton(task)); });
      el.nav.appendChild(group);
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

  // Les rappels de cours acceptent `du code` et **du gras**, rien de plus :
  // le texte vient du serveur, on le pose en textContent et on n'insere que
  // des balises que l'on fabrique soi-meme.
  function richText(node, text) {
    var re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
    var last = 0, m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) {
        node.appendChild(document.createTextNode(text.slice(last, m.index)));
      }
      var inner = m[0].slice(m[0][0] === "`" ? 1 : 2,
                             m[0][0] === "`" ? -1 : -2);
      var tag = document.createElement(m[0][0] === "`" ? "code" : "strong");
      tag.textContent = inner;
      node.appendChild(tag);
      last = m.index + m[0].length;
    }
    if (last < text.length) {
      node.appendChild(document.createTextNode(text.slice(last)));
    }
  }

  function renderLesson(lines, format) {
    lines = lines || [];
    format = format || [];
    el.lessonList.textContent = "";
    lines.forEach(function (line) {
      var li = document.createElement("li");
      richText(li, line);
      el.lessonList.appendChild(li);
    });
    el.lessonList.hidden = !lines.length;
    el.lessonFormatLines.textContent = format.join("\n");
    el.lessonFormat.hidden = !format.length;
    el.lesson.hidden = !lines.length && !format.length;
  }

  function renderTrace(steps) {
    el.traceBody.textContent = "";
    if (!steps || !steps.length) { el.traceBox.hidden = true; return; }
    steps.forEach(function (step) {
      var tr = document.createElement("tr");
      if (!step.vrai) tr.className = "exit";

      [String(step.tour === null ? "—" : step.tour),
       String(step.j),
       step.test].forEach(function (value, idx) {
        var td = document.createElement("td");
        td.textContent = value;
        td.className = idx === 2 ? "mono" : "num";
        tr.appendChild(td);
      });

      var verdict = document.createElement("td");
      // Glyphe et mot : le statut ne repose jamais sur la couleur seule.
      verdict.className = step.vrai ? "ok" : "ko";
      verdict.textContent = step.vrai ? "\u2713 vrai" : "\u2717 faux";
      tr.appendChild(verdict);

      var action = document.createElement("td");
      action.textContent = step.action;
      tr.appendChild(action);

      var out = document.createElement("td");
      out.className = "mono";
      out.textContent = step.sortie === "" ? "(vide)" : step.sortie;
      tr.appendChild(out);

      el.traceBody.appendChild(tr);
    });
    el.traceBox.hidden = false;
  }

  function renderDiagnoses(blank) {
    el.diagList.textContent = "";
    el.diagLegend.textContent = "";
    richText(el.diagLegend, blank.label);   // une question cite du code
    blank.options.forEach(function (opt) {
      var label = document.createElement("label");
      label.className = "diagnosis";

      var input = document.createElement("input");
      input.type = "radio";
      input.name = blank.id;
      input.value = opt.id;
      input.checked = selection[blank.id] === opt.id;
      input.addEventListener("change", function () {
        selection = {};
        selection[blank.id] = opt.id;
        el.diagNote.hidden = true;
        el.feedback.textContent = "";
        el.feedback.className = "feedback";
      });

      var text = document.createElement("span");
      richText(text, opt.c);        // les diagnostics citent du code

      label.appendChild(input);
      label.appendChild(text);
      el.diagList.appendChild(label);
    });
  }

  function applyMode(data) {
    var predict = data.mode === "predict";
    var debug = data.mode === "debug";
    var qcm = data.mode === "qcm";

    // Le mode est posé sur le panneau : le CSS s'en sert pour donner à
    // l'énoncé d'un QCM la place d'une vraie question.
    el.panel.className = "panel mode-" + data.mode;
    el.predictBox.hidden = !predict;
    el.diagBox.hidden = !(debug || qcm);
    el.blanks.hidden = predict || debug || qcm;
    el.diagNote.hidden = true;

    // Une question de QCM n'a ni code ni sortie : tout le volet
    // « programme » disparaît, il ne reste que l'énoncé et les propositions.
    el.panes.hidden = qcm;
    el.codeTitle.hidden = qcm;
    el.code.hidden = qcm;

    // La cible EST la réponse en mode prédiction : son volet ne réapparaît
    // qu'une fois l'exercice trouvé.
    el.targetPane.hidden = predict && !data.target;
    el.panes.classList.toggle("single", predict && !data.target);

    el.codeTitle.textContent = (predict || debug) ? "Code à lire"
                                                  : "Code à compléter";
    // Le libellé du geste vient du chapitre : on compile un programme,
    // on exécute une commande.
    el.check.textContent = predict ? "Vérifier ma prédiction"
                         : debug   ? "Valider mon diagnostic"
                         : qcm     ? "Valider ma réponse"
                                   : (data.action || "Compiler et exécuter");
    el.targetTitle.textContent = debug ? "Ce que le code devrait produire"
                                       : "Motif à reproduire";
    el.outputTitle.textContent = debug ? "Ce qu'il produit réellement"
                                       : "Votre sortie";
    el.output.textContent = predict
      ? "Écrivez votre prédiction puis vérifiez."
      : "Complétez les menus puis lancez l'exécution.";

    if (predict) {
      el.predictInput.value = data.answer || "";
      el.predictInput.readOnly = !!data.solved;
      el.code.textContent = data.code;
    }
    if (debug) {
      el.code.textContent = data.code;
      // L'écart est visible d'emblée : c'est l'expliquer qui fait l'exercice.
      renderLines(el.output, data.actual,
                  data.actual.map(function () { return false; }));
    }
    if (debug || qcm) renderDiagnoses(data.blanks[0]);
  }

  function loadTask(key) {
    return api("/api/task/" + encodeURIComponent(key)).then(function (data) {
      current = data;
      selection = Object.assign({}, data.selection || {});
      el.name.textContent = data.name;
      el.module.textContent = data.module;
      el.level.className = "level-badge lvl" + data.level;
      el.level.title = "Difficulté : " + data.level_name;
      el.level.textContent = "";
      el.level.appendChild(levelDots(data.level));
      el.level.appendChild(document.createTextNode(" " + data.level_name));
      // Le « pourquoi » n'existe pas partout : une question de QCM n'a que
      // son énoncé, et un tiret orphelin se verrait.
      el.brief.textContent = data.mode === "qcm" ? ""
        : [data.brief, data.why].filter(Boolean).join(" — ");
      el.state.textContent = EXAM ? attemptLabel(data.attempts)
        : data.solved ? "✓ réussi"
        : "en cours · " + data.attempts + " tentative"
          + (data.attempts > 1 ? "s" : "");
      el.state.className = (!EXAM && data.solved) ? "pill ok" : "pill";
      showStakes(data.stakes, data.solved);
      el.feedback.textContent = "";
      el.feedback.className = "feedback";

      applyMode(data);
      if (data.target) renderLines(el.target, data.target);
      renderLesson(data.lesson, data.output_format);
      renderTrace(null);
      if (data.mode === "complete") {
        renderBlanks();
        renderCode();
      }
      renderNav();
    });
  }

  // Mode examen : la reponse est enregistree, et l'ecran n'en dit pas plus.
  // Pas de verdict, pas de diff coloree, pas de mise en jeu — rien que
  // l'eleve pourrait lire comme « juste » ou « faux ».
  function showExamResult(res) {
    current.attempts = res.attempts;
    current.answered = true;
    tasks.forEach(function (t) {
      if (t.key === current.key) t.answered = true;
    });
    el.state.textContent = attemptLabel(res.attempts);
    el.state.className = "pill";

    if (current.mode === "complete") {
      if (res.infinite) {
        // Un fait sur son propre code, pas une correction : sans arret, il
        // n'y a aucune sortie a afficher.
        el.output.textContent = "Cette boucle ne s'arrête jamais : "
          + "aucune sortie à afficher.";
      } else {
        // Sans marques : les lignes s'affichent toutes de la meme facon.
        renderLines(el.output, res.rows || []);
      }
      renderTrace(res.trace);
    }

    // Ce message est exact au mot : en examen la copie est jugee sur la
    // reponse qu'elle porte, et revenir dessus ne coute rien.
    el.feedback.textContent = "Réponse enregistrée. Vous pouvez la modifier "
      + "jusqu'à la remise : c'est la dernière qui compte.";
    el.feedback.className = "feedback";
    renderNav();
    showProgress(res.progress);
  }

  // --- Actions ------------------------------------------------------------

  // En prédiction, Ctrl+Entrée valide sans quitter la zone de saisie.
  el.predictInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      el.check.click();
    }
  });

  el.check.addEventListener("click", function () {
    if (!current) return;
    el.check.disabled = true;
    var body = current.mode === "predict"
      ? { answer: el.predictInput.value }
      : { selection: selection };
    var radio = current.mode === "debug" || current.mode === "qcm";
    if (radio && !Object.keys(selection).length) {
      el.feedback.textContent = current.mode === "qcm"
        ? "Choisissez une réponse." : "Choisissez une cause.";
      el.feedback.className = "feedback ko";
      el.check.disabled = false;
      return;
    }
    postJSON("/api/task/" + encodeURIComponent(current.key) + "/check", body)
      .then(function (res) {
        var before = current.stakes;
        var wasSolved = !!current.solved;
        if (!res.complete) {
          renderTrace(null);
          el.feedback.textContent = res.message;
          el.feedback.className = "feedback ko";
          return;
        }
        if (res.exam) { showExamResult(res); return; }
        if (radio) {
          // Un QCM ne commente pas les mauvaises réponses : le bandeau
          // reste fermé tant que l'élève n'a pas trouvé.
          el.diagNote.textContent = res.note || "";
          el.diagNote.className = res.ok ? "note ok-note" : "note ko-note";
          el.diagNote.hidden = !res.note;
          if (res.ok) {
            el.feedback.textContent = current.mode === "qcm"
              ? (res.first_time ? "Bonne réponse." : "Bonne réponse (déjà validée).")
              : (res.first_time ? "Diagnostic exact." : "Diagnostic exact (déjà validé).");
            el.feedback.className = "feedback ok";
            el.state.textContent = "\u2713 réussi";
            el.state.className = "pill ok";
            current.solved = true;
            tasks.forEach(function (t) {
              if (t.key === current.key) t.solved = true;
            });
            renderNav();
          } else {
            current.attempts += 1;
            el.feedback.textContent = (current.mode === "qcm"
              ? "Ce n'est pas la bonne réponse." : "Ce n'est pas la cause.")
              + lossNote(before, res.stakes, wasSolved);
            el.feedback.className = "feedback ko";
          }
          current.stakes = res.stakes;
          showStakes(res.stakes, res.ok || wasSolved);
          showProgress(res.progress);
          return;
        }

        if (res.infinite) {
          el.output.textContent = "Cette boucle ne s'arrête jamais : "
            + "aucune sortie à comparer.";
          renderTrace(res.trace);
          el.feedback.textContent = "Boucle infinie. Regardez le tableau : "
            + "le test reste vrai tour après tour."
            + lossNote(before, res.stakes, wasSolved);
          el.feedback.className = "feedback ko";
          current.stakes = res.stakes;
          showStakes(res.stakes, false);
          showProgress(res.progress);
          return;
        }

        var marks = res.diff.map(function (d) { return d.ok; });
        renderLines(el.output, res.diff.map(function (d) { return d.got; }), marks);
        renderTrace(res.trace);
        if (res.target) {          // prédiction trouvée : la cible se dévoile
          el.targetPane.hidden = false;
          el.panes.classList.remove("single");
          renderLines(el.target, res.target);
        }
        if (res.ok) {
          el.feedback.textContent = res.first_time
            ? "Exact. Motif validé."
            : "Exact (motif déjà validé).";
          el.feedback.className = "feedback ok";
          el.state.textContent = "✓ réussi";
          el.state.className = "pill ok";
          if (current.mode === "predict") el.predictInput.readOnly = true;
          current.solved = true;
          tasks.forEach(function (t) { if (t.key === current.key) t.solved = true; });
          renderNav();
        } else {
          current.attempts += 1;
          el.state.textContent = "en cours · " + current.attempts + " tentative"
            + (current.attempts > 1 ? "s" : "");
          var wrong = res.diff.filter(function (d) { return !d.ok; }).length;
          var message = wrong + " ligne" + (wrong > 1 ? "s" : "")
            + " différente" + (wrong > 1 ? "s" : "") + " de la cible.";
          if (res.count_mismatch) {
            message += " Le nombre de lignes ne correspond pas non plus.";
          }
          message += lossNote(before, res.stakes, wasSolved);
          el.feedback.textContent = message;
          el.feedback.className = "feedback ko";
        }
        current.stakes = res.stakes;
        showStakes(res.stakes, res.ok || wasSolved);
        showProgress(res.progress);
      })
      .catch(function () {
        el.feedback.textContent = "Erreur réseau. Réessayez.";
        el.feedback.className = "feedback ko";
      })
      .then(function () { el.check.disabled = false; });
  });

  // Un window.confirm() natif fait perdre le focus à la page : la
  // surveillance le comptait comme une sortie, et l'élève était pénalisé
  // pour avoir cliqué sur « Remettre ma copie ». D'où cette boîte en page.
  el.finish.addEventListener("click", function () {
    if (progress) {
      el.confirmRecap.textContent = progress.exam
        ? progress.answered + " question" + (progress.answered > 1 ? "s" : "")
          + " traitée" + (progress.answered > 1 ? "s" : "")
          + " sur " + progress.total
        : progress.solved + " exercice"
          + (progress.solved > 1 ? "s" : "") + " sur " + progress.total
          + " · note actuelle " + progress.score.toFixed(2) + " / 20";
    }
    el.confirmBox.hidden = false;
    el.confirmNo.focus();
  });

  el.confirmNo.addEventListener("click", function () {
    el.confirmBox.hidden = true;
    el.finish.focus();
  });

  el.confirmYes.addEventListener("click", function () {
    el.confirmYes.disabled = true;
    postJSON("/api/finish").then(function (res) {
      // On arrête la surveillance avant de quitter le plein écran, sinon
      // cette sortie-là serait comptée comme une infraction.
      if (window.Proctor) window.Proctor.stop();
      window.location.href = res.redirect;
    }).catch(function () {
      el.confirmYes.disabled = false;
      el.confirmBox.hidden = true;
    });
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
        window.location.href = "/termine";
        return;
      }
      tasks = me.tasks;
      modules = me.modules || [];
      showProgress(me.progress);
      el.gate.hidden = true;
      el.app.hidden = false;
      return loadTask(tasks[0].key);
    }).catch(function () {
      el.start.disabled = false;
      el.gateHint.textContent = "Impossible de charger les exercices. Réessayez.";
    });
  });

  // Battement de coeur, seul sondage de la page : il alimente la colonne
  // « dernière activité » cote enseignant, rafraichit l'avancement, et
  // detecte la cloture de la session.
  //
  // Il tournait a 10 secondes, double d'un second sondage a 15 secondes
  // qui ne lisait qu'un etat de session. Trente eleves faisaient ainsi
  // trois cents requetes par minute, dont cent quatre-vingts ecritures
  // en base : sur l'hebergement, ou le disque est monte par le reseau,
  // c'est la que partait la latence. Une seule requete par demi-minute
  // porte la meme information.
  setInterval(function () {
    if (el.app.hidden) return;
    postJSON("/api/heartbeat").then(function (p) {
      if (p.session_status === "closed") {
        if (window.Proctor) window.Proctor.stop();
        window.location.href = "/termine";
        return;
      }
      showProgress(p);
    }).catch(function () {});
  }, 30000);
})();
