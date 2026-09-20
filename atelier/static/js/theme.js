// Bascule claire/sombre. Le reglage systeme fait foi tant qu'on n'a pas choisi.
(function () {
  var KEY = "atelier-theme";
  var root = document.documentElement;
  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) { /* mode prive : on reste sur le reglage systeme */ }

  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", function () {
    var dark = root.getAttribute("data-theme") === "dark"
      || (!root.hasAttribute("data-theme")
          && window.matchMedia("(prefers-color-scheme: dark)").matches);
    var next = dark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem(KEY, next); } catch (e) { /* ignore */ }
  });
})();
