// Keskustelusivu: yksi uutinen, kommentit, kirjautuminen (sähköpostilinkki), nimimerkki, ilmianna.
(function () {
  var K = window.KOOSTE, app = document.getElementById("app"), el = K.el;
  if (!K.on) { app.textContent = "Keskustelu ei ole vielä käytössä."; return; }
  var ID = (new URLSearchParams(location.search).get("i") || "").toLowerCase();
  if (!/^[a-f0-9]{16}$/.test(ID)) { app.textContent = "Uutista ei löytynyt."; return; }
  var sb, user = null, profiili = null, uutinen = null, kommentit = [];

  function virhe(e, oletus) { return (e && e.message) ? e.message : oletus; }

  async function lataa() {
    var r = await sb.from("kommentit").select("id,nimimerkki,teksti,luotu,kayttaja,otsikko,linkki").eq("uutinen", ID).eq("poistettu", false).order("luotu", { ascending: true }).limit(500);
    kommentit = r.data || [];
    var s = await sb.auth.getSession();
    user = s.data && s.data.session ? s.data.session.user : null;
    profiili = null;
    if (user) {
      var p = await sb.from("profiilit").select("nimimerkki").eq("id", user.id).maybeSingle();
      profiili = p.data ? p.data.nimimerkki : null;
    }
    piirra();
  }

  function otsikkoJaLinkki() {
    if (uutinen) return { o: uutinen.o, l: uutinen.l };
    if (kommentit.length) return { o: kommentit[0].otsikko, l: kommentit[0].linkki };
    return null;
  }

  function piirra() {
    app.textContent = "";
    var ot = otsikkoJaLinkki();
    var h = el("h1", "", ot ? ot.o : "Keskustelu");
    app.appendChild(h);
    if (ot) {
      var a = el("a", "", "Lue uutinen lähteessä");
      a.href = K.turvallinenLinkki(ot.l); a.target = "_blank"; a.rel = "noopener nofollow ugc";
      var p = el("p", "lead"); p.appendChild(a); app.appendChild(p);
    } else {
      app.appendChild(el("p", "lead", "Tämä uutinen ei ole enää listalla, eikä siitä ole vielä kommentteja."));
    }
    app.appendChild(el("h2", "", kommentit.length ? "Kommentit (" + kommentit.length + ")" : "Ei vielä kommentteja"));
    kommentit.forEach(function (k) {
      var c = el("article", "item");
      c.appendChild(el("div", "kuv", k.teksti));
      c.lastChild.style.whiteSpace = "pre-wrap"; c.lastChild.style.color = "var(--fg)";
      var m = el("div", "meta", k.nimimerkki + " · " + K.aika(k.luotu));
      var ilm = el("button", "sec pieni", "Ilmianna");
      ilm.type = "button";
      ilm.onclick = function () { ilmianna(k, ilm); };
      m.appendChild(document.createTextNode(" "));
      m.appendChild(ilm);
      if (user && user.id === k.kayttaja) {
        var pois = el("button", "sec pieni", "Poista oma");
        pois.type = "button";
        pois.onclick = async function () {
          if (!confirm("Poistetaanko kommentti?")) return;
          var r = await sb.from("kommentit").delete().eq("id", k.id);
          if (r.error) alert(virhe(r.error, "Poisto epäonnistui")); else lataa();
        };
        m.appendChild(document.createTextNode(" ")); m.appendChild(pois);
      }
      c.appendChild(m);
      app.appendChild(c);
    });
    app.appendChild(lomake(ot));
  }

  async function ilmianna(k, nappi) {
    if (!user) { alert("Kirjaudu ensin sisään, niin voit ilmiantaa kommentin."); return; }
    var syy = prompt("Miksi kommentti pitäisi poistaa? (valinnainen)");
    if (syy === null) return;
    var r = await sb.from("ilmiannot").insert({ kommentti_id: k.id, syy: (syy || "").slice(0, 500) });
    if (r.error) alert(r.error.code === "23505" ? "Olet jo ilmiantanut tämän kommentin." : virhe(r.error, "Ilmianto epäonnistui"));
    else { nappi.textContent = "Ilmiannettu"; nappi.disabled = true; }
  }

  function lomake(ot) {
    var box = el("section", "");
    box.style.marginTop = "22px";
    if (!user) {
      box.appendChild(el("h2", "", "Kirjaudu keskustelemaan"));
      box.appendChild(el("p", "lead", "Kommentit voi lukea ilman kirjautumista. Kommentointiin tarvitaan sähköpostiosoite: lähetämme sinulle kertakäyttöisen kirjautumislinkin, salasanaa ei tarvita."));
      var em = el("input"); em.type = "email"; em.placeholder = "sähköpostiosoite"; em.autocomplete = "email";
      em.style.cssText = "width:100%;margin:0 0 8px;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:16px";
      var nap = el("button", "", "Lähetä kirjautumislinkki"); nap.type = "button";
      var tila = el("p", "lead", "");
      nap.onclick = async function () {
        if (!em.value || em.value.indexOf("@") < 1) { tila.textContent = "Kirjoita sähköpostiosoite."; return; }
        nap.disabled = true; tila.textContent = "Lähetetään…";
        var r = await sb.auth.signInWithOtp({ email: em.value.trim(), options: { emailRedirectTo: location.href } });
        if (r.error) { tila.textContent = virhe(r.error, "Lähetys epäonnistui. Yritä hetken kuluttua uudelleen."); nap.disabled = false; }
        else tila.textContent = "Linkki lähetetty. Avaa sähköpostisi ja paina linkkiä, niin palaat tänne kirjautuneena.";
      };
      var sv = el("p", "lead"); sv.innerHTML = "Kirjautumalla hyväksyt <a href='../saannot/'>keskustelusäännöt</a> ja <a href='../tietosuoja/'>tietosuojaselosteen</a>.";
      [em, nap, tila, sv].forEach(function (x) { box.appendChild(x); });
      return box;
    }
    if (!profiili) {
      box.appendChild(el("h2", "", "Valitse nimimerkki"));
      box.appendChild(el("p", "lead", "Nimimerkki näkyy kommenttiesi vieressä. 3–24 merkkiä: kirjaimia, numeroita, _ . -. Käytä muuta kuin oikeaa nimeäsi, jos haluat pysyä nimettömänä. Sitä ei voi vaihtaa myöhemmin."));
      var ni = el("input"); ni.placeholder = "nimimerkki"; ni.maxLength = 24;
      ni.style.cssText = "width:100%;margin:0 0 8px;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:16px";
      var tl = el("p", "lead", "");
      var tall = el("button", "", "Tallenna nimimerkki"); tall.type = "button";
      tall.onclick = async function () {
        var v = ni.value.trim();
        if (!/^[A-Za-z0-9ÅÄÖåäö_.-]{3,24}$/.test(v)) { tl.textContent = "Nimimerkissä saa olla 3–24 merkkiä: kirjaimia, numeroita, _ . -"; return; }
        var r = await sb.from("profiilit").insert({ id: user.id, nimimerkki: v });
        if (r.error) tl.textContent = r.error.code === "23505" ? "Nimimerkki on jo käytössä. Kokeile toista." : virhe(r.error, "Tallennus epäonnistui");
        else lataa();
      };
      [ni, tall, tl].forEach(function (x) { box.appendChild(x); });
      return box;
    }
    box.appendChild(el("h2", "", "Kirjoita kommentti"));
    box.appendChild(el("p", "lead", "Kirjautuneena nimimerkillä " + profiili + ". Kommentit julkaistaan heti. Laittomat kommentit poistetaan ilmoituksen perusteella."));
    if (!ot) { box.appendChild(el("p", "lead", "Tähän uutiseen ei voi enää lisätä kommentteja, koska se ei ole listalla.")); return box; }
    var ta = el("textarea"); ta.rows = 5; ta.maxLength = 2000; ta.placeholder = "Mitä mieltä olet?";
    ta.style.cssText = "width:100%;margin:0 0 8px;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font:16px/1.4 Georgia,serif";
    var lh = el("button", "", "Julkaise kommentti"); lh.type = "button";
    var t2 = el("p", "lead", "");
    lh.onclick = async function () {
      var v = ta.value.trim();
      if (!v) { t2.textContent = "Kirjoita ensin kommentti."; return; }
      lh.disabled = true;
      var r = await sb.from("kommentit").insert({ uutinen: ID, otsikko: ot.o.slice(0, 400), linkki: ot.l, nimimerkki: profiili, teksti: v });
      lh.disabled = false;
      if (r.error) t2.textContent = virhe(r.error, "Julkaisu epäonnistui");
      else lataa();
    };
    var ulos = el("button", "sec pieni", "Kirjaudu ulos"); ulos.type = "button";
    ulos.onclick = async function () { await sb.auth.signOut(); lataa(); };
    [ta, lh, t2, ulos].forEach(function (x) { box.appendChild(x); });
    return box;
  }

  K.lataaKirjasto().then(async function (lib) {
    sb = lib.createClient(K.conf.url, K.conf.key, { auth: { persistSession: true, detectSessionInUrl: true } });
    try { var f = await (await fetch("../feed.json")).json(); uutinen = (f.u || []).find(function (u) { return u.i === ID; }) || null; } catch (e) {}
    sb.auth.onAuthStateChange(function (ev) { if (ev === "SIGNED_IN" || ev === "SIGNED_OUT") lataa(); });
    lataa();
  }).catch(function () { app.textContent = "Keskustelun lataus epäonnistui. Yritä hetken kuluttua uudelleen."; });
})();
