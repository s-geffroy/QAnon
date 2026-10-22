/* Menus de l'en-tete. Sans JavaScript, les quatre rubriques restent des <details> utilisables et
   la barre passe a la ligne si besoin. Avec : un seul menu ouvert a la fois ; et des que le titre,
   les menus et la langue ne tiennent plus sur une ligne (quelle que soit la raison : largeur, zoom,
   police), barre compacte avec un bouton "Menu". */
(function () {
  var head = document.querySelector(".site-head"), nav = document.getElementById("site-nav"),
      btn = document.querySelector(".menu-btn"), brand = document.querySelector(".brand"),
      lang = document.querySelector(".head-row .lang");
  if (!head || !nav || !btn || !brand) return;
  var groups = [].slice.call(nav.querySelectorAll(".nav-group"));
  nav.setAttribute("data-js", "");
  function compact() { return head.classList.contains("compact"); }
  function closeAll(keep) { groups.forEach(function (g) { if (g !== keep) g.open = false; }); }
  function setOpen(v) { btn.setAttribute("aria-expanded", v ? "true" : "false"); nav.classList.toggle("open", v); }
  function fitsOnOneLine() {
    var row = brand.parentNode, top = brand.getBoundingClientRect(), mid = top.top + top.height / 2;
    var items = [nav].concat(lang ? [lang] : []);
    var aligned = items.every(function (e) { var r = e.getBoundingClientRect(); return r.top <= mid && r.bottom >= mid; });
    return aligned && row.scrollWidth <= row.clientWidth + 1;
  }
  function layout() {
    var was = compact();
    head.classList.remove("compact"); btn.hidden = true; nav.classList.remove("open");
    var fits = fitsOnOneLine();
    head.classList.toggle("compact", !fits); btn.hidden = fits;
    if (!fits) {
      setOpen(false);
      if (!was) groups.forEach(function (g) { g.open = g.hasAttribute("data-current"); });
    } else if (was) {
      closeAll(null);
    }
  }
  groups.forEach(function (g) {
    g.addEventListener("toggle", function () { if (g.open && !compact()) closeAll(g); });
  });
  document.addEventListener("click", function (e) { if (!compact() && !nav.contains(e.target)) closeAll(null); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (compact()) { if (nav.classList.contains("open")) { setOpen(false); btn.focus(); } return; }
    var open = groups.filter(function (g) { return g.open; })[0];
    if (open) { open.open = false; open.querySelector("summary").focus(); }
  });
  btn.addEventListener("click", function () { setOpen(btn.getAttribute("aria-expanded") !== "true"); });
  var frame = 0;
  window.addEventListener("resize", function () { cancelAnimationFrame(frame); frame = requestAnimationFrame(layout); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(layout);
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
