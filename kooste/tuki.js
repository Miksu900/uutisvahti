// Jaettu apu: keskustelun päälläolo, kommenttimäärät listoille, Supabase-kirjaston lataus.
(function () {
  var C = window.KOOSTE_CONF || {};
  var ON = !!(C.url && C.key);
  var K = (window.KOOSTE = { on: ON, conf: C });
  function rpc(fn, args) {
    return fetch(C.url + "/rest/v1/rpc/" + fn, {
      method: "POST",
      headers: { apikey: C.key, Authorization: "Bearer " + C.key, "Content-Type": "application/json" },
      body: JSON.stringify(args)
    }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }
  K.maarat = function () {
    if (!ON) return;
    var els = Array.prototype.slice.call(document.querySelectorAll("a.kesk[data-id]"));
    if (!els.length) return;
    var ids = []; els.forEach(function (e) { if (ids.indexOf(e.dataset.id) < 0) ids.push(e.dataset.id); });
    rpc("kommenttimaarat", { ids: ids }).then(function (rows) {
      var m = {}; rows.forEach(function (r) { m[r.uutinen] = r.n; });
      els.forEach(function (e) { var n = m[e.dataset.id] || 0; e.textContent = n ? "Keskustele (" + n + ")" : "Keskustele"; });
    }).catch(function () {});
  };
  K.lataaKirjasto = function () {
    return new Promise(function (res, rej) {
      if (window.supabase) return res(window.supabase);
      var s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js";
      s.onload = function () { res(window.supabase); };
      s.onerror = rej;
      document.head.appendChild(s);
    });
  };
  K.el = function (t, c, x) { var e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  K.aika = function (iso) {
    return new Date(iso).toLocaleString("fi-FI", { timeZone: "Europe/Helsinki", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
  };
  K.turvallinenLinkki = function (u) { return /^https?:\/\//i.test(u || "") ? u : "#"; };
  document.addEventListener("DOMContentLoaded", K.maarat);
})();
