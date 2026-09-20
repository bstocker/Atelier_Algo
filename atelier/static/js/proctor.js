/* Surveillance de la fenêtre d'examen.
 *
 * Une « sortie » est un passage de l'état surveillé (plein écran + onglet
 * visible + fenêtre au premier plan) vers n'importe quel autre etat. Les
 * evenements du navigateur se chevauchent (changer d'onglet declenche a la
 * fois blur et visibilitychange), d'ou le drapeau `outside` : un episode
 * compte pour une sortie, quel que soit le nombre d'evenements recus.
 *
 * La pénalité est enregistrée des la sortie, par le serveur, selon son rang.
 * Le decompte est un rappel a l'ordre : il ne change pas la sanction, mais
 * le delai de retour est consigne pour l'enseignant.
 */
(function (global) {
  "use strict";

  var DELAY = (global.ATELIER && global.ATELIER.returnDelay) || 3;

  var el = {
    overlay: document.getElementById("overlay"),
    count: document.getElementById("ov-count"),
    msg: document.getElementById("ov-msg"),
    tally: document.getElementById("ov-tally"),
    resume: document.getElementById("resume-btn")
  };

  var active = false;         // l'épreuve a demarre
  var outside = false;        // episode de sortie en cours
  var fullscreenRequired = true;
  var exitAt = 0;
  var incidentId = null;
  var returnReported = false;
  var timer = null;
  var onPenalty = function () {};

  function isFullscreen() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement);
  }

  function requestFullscreen() {
    var node = document.documentElement;
    var fn = node.requestFullscreen || node.webkitRequestFullscreen;
    if (!fn) return Promise.reject(new Error("unsupported"));
    try {
      return Promise.resolve(fn.call(node));
    } catch (err) {
      return Promise.reject(err);
    }
  }

  function inside() {
    return document.visibilityState === "visible"
      && document.hasFocus()
      && (!fullscreenRequired || isFullscreen());
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
      credentials: "same-origin"
    }).then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function wording(ordinal, penalty) {
    if (penalty <= 0) {
      return "Première sortie : avertissement. Aucun point retiré cette fois, "
           + "mais la prochaine sortie coûtera 2 points.";
    }
    return "Sortie n" + String.fromCharCode(176) + " " + ordinal + " : "
         + penalty + " point" + (penalty > 1 ? "s" : "") + " retiré"
         + (penalty > 1 ? "s" : "") + " de votre note.";
  }

  function startCountdown() {
    var left = DELAY;
    el.count.textContent = left;
    el.count.removeAttribute("data-expired");
    clearInterval(timer);
    timer = setInterval(function () {
      left -= 1;
      if (left > 0) {
        el.count.textContent = left;
        return;
      }
      clearInterval(timer);
      timer = null;
      el.count.textContent = "0";
      el.count.setAttribute("data-expired", "true");
    }, 1000);
  }

  function handleExit(kind) {
    if (!active || outside) return;
    outside = true;
    returnReported = false;
    incidentId = null;
    exitAt = Date.now();

    el.msg.textContent = "Sortie détectée. Revenez immediatement.";
    el.tally.textContent = "";
    el.overlay.hidden = false;
    startCountdown();

    post("/api/incident", { kind: kind }).then(function (data) {
      if (!data || data.ignored) return;
      incidentId = data.incident_id;
      el.msg.textContent = wording(data.ordinal, data.penalty);
      el.tally.textContent = "Sorties : " + data.ordinal + " · "
        + (data.total_penalty > 0
            ? "Pénalité cumulée : " + String.fromCharCode(8722)
              + data.total_penalty.toFixed(0) + " points"
            : "aucune pénalité pour l'instant");
      onPenalty(data);
    });
  }

  function reportReturn() {
    if (returnReported || !incidentId) return;
    returnReported = true;
    post("/api/incident/" + incidentId + "/return", { ms: Date.now() - exitAt });
  }

  function settle() {
    if (!active || !outside) return;
    if (document.visibilityState === "visible" && document.hasFocus()) {
      reportReturn();   // l'étudiant est revenu, même si le plein écran manque
    }
    if (!inside()) return;
    outside = false;
    clearInterval(timer);
    timer = null;
    el.overlay.hidden = true;
  }

  // --- Branchement des evenements -----------------------------------------

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") handleExit("hidden");
    else settle();
  });

  global.addEventListener("blur", function () { handleExit("blur"); });
  global.addEventListener("focus", settle);

  ["fullscreenchange", "webkitfullscreenchange"].forEach(function (evt) {
    document.addEventListener(evt, function () {
      if (!active || !fullscreenRequired) return;
      if (!isFullscreen()) handleExit("fullscreen");
      else settle();
    });
  });

  if (el.resume) {
    el.resume.addEventListener("click", function () {
      if (!fullscreenRequired || isFullscreen()) { settle(); return; }
      requestFullscreen().then(settle, function () {
        // Plein écran refusé : on retombe sur la surveillance du focus seul.
        fullscreenRequired = false;
        settle();
      });
    });
  }

  global.Proctor = {
    /* Demarre la surveillance. Doit etre appele depuis un clic : le plein
       écran exige un geste utilisateur. Résout avec true si le plein écran
       a ete obtenu, false si l'on se rabat sur le focus seul. */
    start: function (options) {
      onPenalty = (options && options.onPenalty) || onPenalty;
      return requestFullscreen().then(function () {
        active = true;
        return true;
      }, function () {
        fullscreenRequired = false;
        active = true;
        return false;
      });
    },
    /* Arrête la surveillance (remise de copie) et quitte le plein écran. */
    stop: function () {
      active = false;
      outside = false;
      clearInterval(timer);
      el.overlay.hidden = true;
      if (isFullscreen() && document.exitFullscreen) {
        document.exitFullscreen().catch(function () {});
      }
    }
  };
})(window);
