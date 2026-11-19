// Explorateur du corpus : filtre cote client de data/corpus.json.
(function () {
  var L = JSON.parse(document.getElementById("c-labels").textContent);
  var $ = function (id) { return document.getElementById(id); };
  var q = $("c-q"), year = $("c-year"), board = $("c-board"), actor = $("c-actor"), verdict = $("c-verdict"),
      list = $("c-list"), more = $("c-more"), count = $("c-n"), single = $("c-single");
  var data, rows = [], shown = 0, PAGE = 50;
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function render(d) {
    var li = el("li", "drop"); li.id = "d" + d[0];
    var head = el("p", "tags");
    var a = el("a", "topic", L.drop + d[0]); a.href = "#d" + d[0]; head.appendChild(a);
    head.appendChild(document.createTextNode(" "));
    head.appendChild(el("span", "topic", d[1] + " (New York) · " + d[2]));
    if (d[5]) { head.appendChild(document.createTextNode(" ")); head.appendChild(el("span", "tag", L.pred + " " + d[5])); }
    d[6].forEach(function (v) { head.appendChild(document.createTextNode(" ")); head.appendChild(el("span", "tag vd vd-" + v, L.verdicts[v])); });
    if (d[7]) { head.appendChild(document.createTextNode(" ")); head.appendChild(el("span", "topic", L.images + " " + d[7])); }
    li.appendChild(head);
    li.appendChild(el("pre", "drop-text", d[3] || "—"));
    if (d[4].length) li.appendChild(el("p", "note", d[4].map(function (i) { return data.actors[i]; }).join(" · ")));
    return li;
  }
  function filter() {
    var words = q.value.toLowerCase().split(/\s+/).filter(Boolean), ai = actor.value === "" ? -1 : +actor.value;
    rows = data.drops.filter(function (d) {
      if (year.value && d[1].slice(0, 4) !== year.value) return false;
      if (board.value && d[2] !== board.value) return false;
      if (ai >= 0 && d[4].indexOf(ai) < 0) return false;
      if (verdict.value === "pred" && !d[5]) return false;
      if (verdict.value && verdict.value !== "pred" && d[6].indexOf(verdict.value) < 0) return false;
      if (words.length) { var t = d[3].toLowerCase(); for (var i = 0; i < words.length; i++) if (t.indexOf(words[i]) < 0) return false; }
      return true;
    });
    list.textContent = ""; shown = 0; page();
    count.textContent = rows.length.toLocaleString(L.lang);
  }
  function page() {
    var end = Math.min(rows.length, shown + PAGE);
    for (; shown < end; shown++) list.appendChild(render(rows[shown]));
    more.hidden = shown >= rows.length;
    if (!rows.length) list.appendChild(el("li", "note", L.empty));
  }
  function fromHash() {
    var m = location.hash.match(/^#d(\d+)$/);
    if (!m || !data) return false;
    var d = data.drops.filter(function (x) { return x[0] === +m[1]; })[0];
    if (!d) return false;
    list.textContent = ""; list.appendChild(render(d)); more.hidden = true; single.hidden = false;
    count.textContent = "1"; return true;
  }
  fetch("../data/corpus.json").then(function (r) { return r.json(); }).then(function (js) {
    data = js;
    Array.from(new Set(js.drops.map(function (d) { return d[2]; }))).sort().forEach(function (b) {
      var o = el("option", null, b); o.value = b; board.appendChild(o);
    });
    js.actors.map(function (n, i) { return [n, i]; }).sort(function (a, b) { return a[0].localeCompare(b[0]); })
      .forEach(function (x) { var o = el("option", null, x[0]); o.value = x[1]; actor.appendChild(o); });
    if (!fromHash()) filter();
  });
  [q, year, board, actor, verdict].forEach(function (e) { e.addEventListener("input", function () { single.hidden = true; filter(); }); });
  more.addEventListener("click", page);
  $("c-all").addEventListener("click", function (e) { e.preventDefault(); history.replaceState(null, "", location.pathname); single.hidden = true; filter(); });
  window.addEventListener("hashchange", function () { if (!fromHash()) filter(); });
})();
