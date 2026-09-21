/* Fiche d'un exercice, cote enseignant.

   Un clic sur le titre d'un exercice — dans le formulaire de composition,
   dans le recapitulatif d'une session ou dans l'en-tete du suivi direct —
   ouvre la fiche : enonce, rappel de cours, sortie attendue, code complete
   et reponse de reference. Rien n'est cache ici : la route est derriere
   l'authentification enseignant. */
(function () {
  "use strict";

  var sheet = document.getElementById("exo-sheet");
  if (!sheet) return;

  var el = {
    path: document.getElementById("sheet-path"),
    name: document.getElementById("sheet-name"),
    level: document.getElementById("sheet-level"),
    brief: document.getElementById("sheet-brief"),
    body: document.getElementById("sheet-body"),
  };

  var DOTS = ["", "●○○○", "●●○○", "●●●○", "●●●●"];
  var cache = {};
  var opener = null;

  // Les intitules acceptent `du code` et **du gras**, rien de plus : le
  // texte vient du serveur, on le pose en textContent et on n'insere que
  // des balises fabriquees ici.
  function richText(node, text) {
    var re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
    var last = 0, m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) {
        node.appendChild(document.createTextNode(text.slice(last, m.index)));
      }
      var tick = m[0][0] === "`";
      var tag = document.createElement(tick ? "code" : "strong");
      tag.textContent = m[0].slice(tick ? 1 : 2, tick ? -1 : -2);
      node.appendChild(tag);
      last = m.index + m[0].length;
    }
    if (last < text.length) {
      node.appendChild(document.createTextNode(text.slice(last)));
    }
  }

  function make(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function section(title) {
    var box = make("section", "sheet-section");
    box.appendChild(make("h3", null, title));
    return box;
  }

  function lines(rows) {
    // Les lignes sont posees une par une : une sortie vide ne doit pas
    // faire disparaitre le bloc, et un \n de plus doublerait l'interligne.
    var pre = make("pre", "ascii");
    (rows || []).forEach(function (line) {
      pre.appendChild(make("span", "good", line === null ? " " : line));
    });
    return pre;
  }

  function renderBlanks(data) {
    if (!data.blanks.length) return null;
    var box = section(data.mode === "debug" ? "Le diagnostic attendu"
                    : data.mode === "qcm" ? "Les propositions"
                                          : "Les réponses attendues");
    data.blanks.forEach(function (blank) {
      box.appendChild(make("p", "sheet-label", blank.label));
      var list = make("ul", "answers");
      blank.options.forEach(function (opt) {
        var li = make("li", opt.ok ? "answer ok-answer" : "answer");
        li.appendChild(make("span", "answer-mark", opt.ok ? "✓" : "·"));
        var text = make("span", "answer-text");
        text.appendChild(make("code", null, opt.c));
        if (opt.note) text.appendChild(make("em", null, opt.note));
        li.appendChild(text);
        list.appendChild(li);
      });
      box.appendChild(list);
    });
    return box;
  }

  function render(data) {
    el.path.textContent = data.chapter + " · " + data.module;
    el.name.textContent = data.name;
    el.level.className = "level-badge lvl" + data.level;
    el.level.textContent = "";
    el.level.appendChild(make("span", "level-dots", DOTS[data.level]));
    el.level.appendChild(document.createTextNode(" " + data.level_name));
    el.brief.textContent = data.brief;

    el.body.textContent = "";

    if (data.teacher_note) {
      var note = make("p", "note sheet-teacher-note");
      note.appendChild(make("strong", null, "Pour vous seul — "));
      richText(note, data.teacher_note);
      el.body.appendChild(note);
    }

    if (data.why) {
      var why = section("Ce que l'exercice travaille");
      why.appendChild(make("p", null, data.why));
      el.body.appendChild(why);
    }

    if (data.lesson.length) {
      var lesson = section("Ce qu'il faut savoir, rappelé à l'élève");
      var list = make("ul");
      data.lesson.forEach(function (line) {
        var li = make("li");
        richText(li, line);
        list.appendChild(li);
      });
      lesson.appendChild(list);
      el.body.appendChild(lesson);
    }

    // Une question de QCM n'a ni sortie ni code : la fiche saute ces deux
    // sections plutôt que de montrer des cadres vides.
    if (data.target && data.target.length) {
      var sorties = make("div", "sheet-outputs");
      var attendu = section(data.mode === "predict"
        ? "La sortie que l'élève doit écrire"
        : data.mode === "debug" ? "La sortie attendue du programme"
                                : "Le motif à reproduire");
      attendu.appendChild(lines(data.target));
      sorties.appendChild(attendu);
      if (data.actual) {
        var obtenu = section("Ce que le code fautif produit");
        obtenu.appendChild(lines(data.actual));
        sorties.appendChild(obtenu);
      }
      el.body.appendChild(sorties);
    }

    if (data.code) {
      var code = section(data.mode === "complete"
        ? "Le code, trous remplis par la réponse de référence"
        : "Le code tel que l'élève le lit");
      code.appendChild(make("pre", "code", data.code));
      el.body.appendChild(code);
    }

    var blanks = renderBlanks(data);
    if (blanks) el.body.appendChild(blanks);
  }

  function open(key, source) {
    opener = source;
    el.path.textContent = "";
    el.name.textContent = "…";
    el.level.textContent = "";
    el.brief.textContent = "";
    el.body.textContent = "";
    el.body.appendChild(make("p", "muted", "Chargement de la fiche…"));
    if (sheet.showModal) sheet.showModal(); else sheet.setAttribute("open", "");

    if (cache[key]) { render(cache[key]); return; }
    fetch("/admin/api/patterns/" + encodeURIComponent(key),
          { credentials: "same-origin" })
      .then(function (r) {
        if (r.status === 401) { window.location.href = "/admin/login"; return null; }
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (!data) {
          el.name.textContent = "Fiche indisponible";
          el.body.textContent = "";
          el.body.appendChild(make("p", "muted",
            "Impossible de charger les attendus de cet exercice."));
          return;
        }
        cache[key] = data;
        render(data);
      })
      .catch(function () {
        el.name.textContent = "Fiche indisponible";
      });
  }

  function close() {
    if (sheet.close) sheet.close(); else sheet.removeAttribute("open");
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest && event.target.closest("[data-detail]");
    if (trigger) {
      event.preventDefault();
      open(trigger.getAttribute("data-detail"), trigger);
      return;
    }
    // Clic sur le fond : la boite occupe son propre rectangle, tout ce qui
    // arrive au <dialog> lui-meme vient donc de l'exterieur.
    if (event.target === sheet) close();
  });

  document.getElementById("sheet-close").addEventListener("click", close);
  sheet.addEventListener("close", function () {
    if (opener && document.contains(opener)) opener.focus();
    opener = null;
  });
})();
