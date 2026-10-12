// Rend les graphes Vega-Lite de la page. Les couleurs "@nom" des specs sont
// remplacees par les variables CSS du theme : un changement de theme
// redessine les graphes avec la palette correspondante.
(function () {
  var TOKENS = {
    "@series1": "--series-1", "@ink": "--ink", "@ink2": "--ink-2", "@ink3": "--ink-3",
    "@surface": "--surface", "@rule": "--rule", "@seqlo": "--seq-lo", "@seqhi": "--seq-hi"
  };
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function resolve(v) {
    if (typeof v === "string" && TOKENS[v]) return css(TOKENS[v]);
    if (Array.isArray(v)) return v.map(resolve);
    if (v && typeof v === "object") {
      var o = {};
      for (var k in v) o[k] = resolve(v[k]);
      return o;
    }
    return v;
  }
  function config() {
    var ink2 = css("--ink-2"), rule = css("--rule"), font = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    return {
      font: font, view: { stroke: null },
      axis: { labelColor: ink2, titleColor: ink2, gridColor: rule, domainColor: rule, tickColor: rule,
              labelFontSize: 11, titleFontSize: 11, titleFontWeight: 500 },
      axisX: { grid: false }, legend: { labelColor: ink2, titleColor: ink2, labelFontSize: 11 }
    };
  }
  var FR = document.documentElement.lang === "fr";
  var LOCALE = FR ? {
    formatLocale: { decimal: ",", thousands: "\u202f", grouping: [3], currency: ["", "\u00a0€"] },
    timeFormatLocale: {
      dateTime: "%A %e %B %Y à %X", date: "%d/%m/%Y", time: "%H:%M:%S", periods: ["AM", "PM"],
      days: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"],
      shortDays: ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."],
      months: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
      shortMonths: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    }
  } : {};
  function draw() {
    if (!window.vegaEmbed) return;
    document.querySelectorAll("script[data-chart]").forEach(function (node) {
      var spec = resolve(JSON.parse(node.textContent));
      spec.config = config();
      vegaEmbed("#" + node.dataset.chart, spec, Object.assign({ actions: false, renderer: "svg" }, LOCALE));
    });
  }
  draw();
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (mq.addEventListener) mq.addEventListener("change", draw);
  }
  new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
