// Ylläpitäjän näkymä: ilmoitetut kommentit ja uusimmat kommentit, poisto ja ilmoituksen hylkäys.
(function () {
  var K = window.KOOSTE, app = document.getElementById("app"), el = K.el, sb;
  if (!K.on) { app.textContent = "Keskustelu ei ole vielä käytössä."; return; }

  async function nayta() {
    app.textContent = "";
    var s = await sb.auth.getSession();
    var user = s.data && s.data.session ? s.data.session.user : null;
    if (!user) { kirjaudu(); return; }
    var ad = await sb.rpc("is_admin");
    if (!ad.data) {
      app.appendChild(el("p", "lead", "Tällä tilillä (" + user.email + ") ei ole ylläpito-oikeuksia."));
      var u = el("button", "sec", "Kirjaudu ulos"); u.type = "button"; u.onclick = async function () { await sb.auth.signOut(); nayta(); };
      app.appendChild(u); return;
    }
    app.appendChild(el("h2", "", "Ilmoitetut kommentit"));
    var il = await sb.from("ilmiannot").select("id,syy,luotu,kommentti_id,kommentit(id,teksti,nimimerkki,otsikko,uutinen,poistettu,luotu)").order("luotu", { ascending: false }).limit(100);
    var rivit = (il.data || []).filter(function (r) { return r.kommentit; });
    if (!rivit.length) app.appendChild(el("p", "lead", "Ei avoimia ilmoituksia."));
    rivit.forEach(function (r) {
      var k = r.kommentit, c = el("article", "item");
      c.appendChild(el("div", "kuv", k.teksti)); c.lastChild.style.whiteSpace = "pre-wrap"; c.lastChild.style.color = "var(--fg)";
      c.appendChild(el("div", "meta", k.nimimerkki + " · uutinen: " + k.otsikko + (k.poistettu ? " · POISTETTU" : "")));
      c.appendChild(el("div", "meta", "Ilmoituksen syy: " + (r.syy || "(ei kerrottu)") + " · " + K.aika(r.luotu)));
      var p = el("div", "meta");
      var pois = el("button", "", "Poista kommentti"); pois.type = "button";
      pois.onclick = async function () { var x = await sb.from("kommentit").update({ poistettu: true }).eq("id", k.id); if (x.error) alert(x.error.message); else nayta(); };
      var hylkaa = el("button", "sec", "Hylkää ilmoitus"); hylkaa.type = "button";
      hylkaa.onclick = async function () { var x = await sb.from("ilmiannot").delete().eq("id", r.id); if (x.error) alert(x.error.message); else nayta(); };
      var l = el("a", "", "Avaa keskustelu"); l.href = "../keskustelu/?i=" + encodeURIComponent(k.uutinen); l.style.cssText = "font:14px system-ui;color:var(--acc);margin-left:8px";
      p.appendChild(pois); p.appendChild(document.createTextNode(" ")); p.appendChild(hylkaa); p.appendChild(l);
      c.appendChild(p); app.appendChild(c);
    });
    app.appendChild(el("h2", "", "Uusimmat kommentit"));
    var uu = await sb.from("kommentit").select("id,teksti,nimimerkki,otsikko,uutinen,poistettu,luotu").order("luotu", { ascending: false }).limit(50);
    (uu.data || []).forEach(function (k) {
      var c = el("article", "item");
      c.appendChild(el("div", "kuv", k.teksti)); c.lastChild.style.whiteSpace = "pre-wrap"; c.lastChild.style.color = "var(--fg)";
      c.appendChild(el("div", "meta", k.nimimerkki + " · " + k.otsikko + " · " + K.aika(k.luotu) + (k.poistettu ? " · POISTETTU" : "")));
      if (!k.poistettu) {
        var pois = el("button", "", "Poista"); pois.type = "button";
        pois.onclick = async function () { var x = await sb.from("kommentit").update({ poistettu: true }).eq("id", k.id); if (x.error) alert(x.error.message); else nayta(); };
        c.appendChild(pois);
      }
      app.appendChild(c);
    });
    var u2 = el("button", "sec", "Kirjaudu ulos"); u2.type = "button"; u2.style.marginTop = "16px"; u2.onclick = async function () { await sb.auth.signOut(); nayta(); };
    app.appendChild(u2);
  }

  function kirjaudu() {
    app.appendChild(el("p", "lead", "Kirjaudu ylläpitäjän sähköpostilla. Lähetämme kertakäyttöisen linkin."));
    var em = el("input"); em.type = "email"; em.placeholder = "sähköpostiosoite";
    em.style.cssText = "width:100%;margin:0 0 8px;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:16px";
    var nap = el("button", "", "Lähetä linkki"); nap.type = "button"; var t = el("p", "lead", "");
    nap.onclick = async function () {
      var r = await sb.auth.signInWithOtp({ email: em.value.trim(), options: { emailRedirectTo: location.href } });
      t.textContent = r.error ? r.error.message : "Linkki lähetetty. Avaa se sähköpostistasi.";
    };
    [em, nap, t].forEach(function (x) { app.appendChild(x); });
  }

  K.lataaKirjasto().then(function (lib) {
    sb = lib.createClient(K.conf.url, K.conf.key, { auth: { persistSession: true, detectSessionInUrl: true } });
    sb.auth.onAuthStateChange(function (ev) { if (ev === "SIGNED_IN" || ev === "SIGNED_OUT") nayta(); });
    nayta();
  }).catch(function () { app.textContent = "Lataus epäonnistui."; });
})();
