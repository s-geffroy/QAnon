/* Menus de l'en-tete. Sans JavaScript, les quatre rubriques restent des <details> utilisables ;
   avec, un seul menu ouvert a la fois sur grand ecran, et un bouton "Menu" sur petit ecran. */
(function () {
  var nav = document.getElementById("site-nav"), btn = document.querySelector(".menu-btn");
  if (!nav || !btn) return;
  var groups = [].slice.call(nav.querySelectorAll(".nav-group"));
  var narrow = window.matchMedia("(max-width: 64rem)");
  nav.setAttribute("data-js", "");
  function closeAll(keep) { groups.forEach(function (g) { if (g !== keep) g.open = false; }); }
  function setOpen(v) { btn.setAttribute("aria-expanded", v ? "true" : "false"); nav.classList.toggle("open", v); }
  groups.forEach(function (g) {
    g.addEventListener("toggle", function () { if (g.open && !narrow.matches) closeAll(g); });
  });
  document.addEventListener("click", function (e) { if (!narrow.matches && !nav.contains(e.target)) closeAll(null); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (narrow.matches) { if (nav.classList.contains("open")) { setOpen(false); btn.focus(); } return; }
    var open = groups.filter(function (g) { return g.open; })[0];
    if (open) { open.open = false; open.querySelector("summary").focus(); }
  });
  btn.addEventListener("click", function () { setOpen(btn.getAttribute("aria-expanded") !== "true"); });
  function layout() {
    if (narrow.matches) {
      btn.hidden = false; setOpen(false);
      groups.forEach(function (g) { g.open = g.hasAttribute("data-current"); });
    } else {
      btn.hidden = true; nav.classList.remove("open"); closeAll(null);
    }
  }
  (narrow.addEventListener ? narrow.addEventListener("change", layout) : narrow.addListener(layout));
  layout();
})();

/* Sommaire des pages longues : la section en cours de lecture est mise en evidence. */
(function () {
  var links = [].slice.call(document.querySelectorAll(".toc a[href^='#']"));
  if (!links.length || !window.IntersectionObserver) return;
  var byId = {};
  links.forEach(function (a) { byId[decodeURIComponent(a.hash.slice(1))] = a; });
  var targets = Object.keys(byId).map(function (id) { return document.getElementById(id); }).filter(Boolean);
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      links.forEach(function (a) { a.classList.remove("here"); });
      byId[e.target.id].classList.add("here");
    });
  }, { rootMargin: "0px 0px -70% 0px" });
  targets.forEach(function (t) { obs.observe(t); });
})();
