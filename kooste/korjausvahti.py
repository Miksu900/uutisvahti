"""Korjausvahti: huomaa, kun media muuttaa jo julkaistun uutisen otsikkoa, ja tallentaa ennen–jälkeen-parin.
Muutokset säilytetään tiedostossa muutokset.json (julkaistaan sivuston mukana, jotta seuraava ajo saa tilan).
Jokaisen päivän muutoslistasta lasketaan SHA-256-sormenjälki, joka sinetöidään lohkoketjuun (krypto-repon ajo).
Sormenjäljen voi tarkistaa kuka tahansa: sama laskutapa on kuvattu sivulla."""
import os, re, json, hashlib, difflib, html, urllib.request, urllib.parse, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DIR = os.path.dirname(os.path.abspath(__file__))
TIEDOSTO = os.path.join(DIR, "muutokset.json")
HKI = ZoneInfo("Europe/Helsinki")
SAILYTYS_PV, MAX_KPL, SEURANTA_H = 60, 5000, 72
SOPIMUS = os.environ.get("KORJAUSVAHTI_SOPIMUS", "").strip() or "0x7108BC5a24faBD5fB0f67dAFA4CBeAF06C50f7e5"

_m = []

def _norm(s):
    s = html.unescape(s or "").replace(" ", " ")
    s = re.sub(r"[“”„\"]", '"', s)
    s = re.sub(r"[’‘`´]", "'", s)
    s = re.sub(r"[–—]", "-", s)
    return re.sub(r"\s+", " ", s).strip()

def lataa():
    global _m
    try:
        _m = json.load(open(TIEDOSTO, encoding="utf-8")).get("m", [])
    except Exception:
        _m = []
    return _m

def tarkista(vanha_it, uusi_otsikko, nyt):
    """Kutsutaan, kun median oma syöte palauttaa jo tallessa olevan uutisen (sama linkki). Palauttaa True, jos otsikko muuttui."""
    vanha, uusi = vanha_it.get("o", ""), uusi_otsikko or ""
    if not uusi or _norm(vanha) == _norm(uusi):
        return False
    try:
        julk = datetime.fromisoformat(vanha_it.get("a") or "")
        if julk.tzinfo is None:
            julk = julk.replace(tzinfo=timezone.utc)
        if nyt - julk > timedelta(hours=SEURANTA_H):
            return False
    except Exception:
        pass
    _m.append({"l": vanha_it["l"], "s": vanha_it.get("s", ""), "a": vanha_it.get("a"), "vanha": vanha, "uusi": uusi,
               "t": nyt.replace(microsecond=0).isoformat(), "ark_ennen": vanha_it.get("ark")})
    vanha_it["o"] = uusi
    return True

# ---- Arkistokopiot (Internet Archive, Save Page Now) ----
# Arkistokopio tallentaa sivun sellaisena kuin se on tallennushetkellä. Siksi kopio otetaan
# 1) heti kun uutinen nähdään ensimmäistä kertaa (todiste alkuperäisestä otsikosta) ja
# 2) kun muutos havaitaan (todiste uudesta otsikosta). Ajoa kohden tehdään vain muutama tallennus.
ARK_MAX = int(os.environ.get("KORJAUSVAHTI_ARK_MAX", "2"))
ARK_TAUKO = 6

def _arkistoi(url):
    try:
        req = urllib.request.Request("https://web.archive.org/save/" + url, headers={"User-Agent": "Mozilla/5.0 (nytpuhutaan.fi korjausvahti)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            loppu = r.geturl()
            sijainti = r.headers.get("Content-Location") or ""
        for ehdokas in (loppu, "https://web.archive.org" + sijainti if sijainti.startswith("/web/") else ""):
            if "/web/" in ehdokas and "/save/" not in ehdokas:
                return ehdokas
        return "https://web.archive.org/web/" + time.strftime("%Y%m%d%H%M%S", time.gmtime()) + "/" + url
    except Exception as e:
        print("arkistointi epäonnistui:", url[:80], str(e)[:80])
        return None

def arkistoi(uutiset, nyt, painotus=("politiikka/", "yhteiskunta/")):
    if os.environ.get("KOOSTE_TESTI") == "1" or ARK_MAX <= 0:
        return 0
    jono = []
    raja2 = (nyt - timedelta(hours=2)).isoformat()
    for m in reversed(_m):            # 1) uusimmat muutokset: kopio nykyisestä versiosta
        if m["t"] >= raja2 and not m.get("ark_nyt") and int(m.get("ark_yritetty") or 0) < 3:
            jono.append(("muutos", m))
    raja1 = (nyt - timedelta(hours=1)).isoformat()
    tuoreet = [u for u in uutiset.values() if u.get("d") and not u.get("ark") and int(u.get("ark_yritetty") or 0) < 2 and (u.get("a") or "") >= raja1]
    tuoreet = sorted(tuoreet, key=lambda u: u.get("a") or "", reverse=True)
    tuoreet.sort(key=lambda u: not any(t.startswith(painotus) for t in u.get("t", [])))
    jono += [("uusi", u) for u in tuoreet]   # 2) uudet uutiset: kopio alkuperäisestä otsikosta
    tehty = 0
    for laji, x in jono[:ARK_MAX]:
        osoite = _arkistoi(x["l"])
        x["ark_yritetty"] = int(x.get("ark_yritetty") or 0) + 1
        if osoite:
            x["ark_nyt" if laji == "muutos" else "ark"] = osoite
        tehty += 1 if osoite else 0
        time.sleep(ARK_TAUKO)
    print(f"korjausvahti: arkistokopioita {tehty}/{min(len(jono), ARK_MAX)} (jonossa {len(jono)})")
    return tehty

def paiva(m):
    return datetime.fromisoformat(m["t"]).astimezone(HKI).date().isoformat()

def paivan_tiiviste(lista):
    """Sama laskutapa kuin sinetöinnissä: [linkki, vanha, uusi, aika] aikajärjestyksessä, tiivis JSON, SHA-256."""
    rivit = [[m["l"], m["vanha"], m["uusi"], m["t"]] for m in sorted(lista, key=lambda m: (m["t"], m["l"]))]
    return hashlib.sha256(json.dumps(rivit, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()

def tallenna(nyt):
    global _m
    raja = (nyt - timedelta(days=SAILYTYS_PV)).isoformat()
    _m = [m for m in _m if m["t"] >= raja][-MAX_KPL:]
    paivat = {}
    for m in _m:
        paivat.setdefault(paiva(m), []).append(m)
    tanaan = nyt.astimezone(HKI).date().isoformat()
    tiivisteet = {p: {"sha256": paivan_tiiviste(l), "kpl": len(l), "valmis": p < tanaan} for p, l in paivat.items()}
    json.dump({"p": nyt.isoformat(), "paivat": tiivisteet, "m": _m}, open(TIEDOSTO, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    return tiivisteet

def _erot(vanha, uusi, esc):
    a, b = vanha.split(), uusi.split()
    ulos_v, ulos_u = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op == "equal":
            ulos_v.append(esc(" ".join(a[i1:i2]))); ulos_u.append(esc(" ".join(b[j1:j2])))
        else:
            if i2 > i1: ulos_v.append(f'<del>{esc(" ".join(a[i1:i2]))}</del>')
            if j2 > j1: ulos_u.append(f'<ins>{esc(" ".join(b[j1:j2]))}</ins>')
    return " ".join(ulos_v), " ".join(ulos_u)


# ---------------------------------------------------------------------------
# Jakosivut, kuvat, nostot ja tilastot
# ---------------------------------------------------------------------------
FONTIT = os.path.join(os.path.dirname(DIR), "fontit")
KUVA_PV = 14   # jakokuva tehdään tuoreista muutoksista ja kaikista nostoista

def mid(m):
    return hashlib.sha1((m["l"] + "|" + m["t"]).encode("utf-8")).hexdigest()[:10]

_SANA = re.compile(r"[\wÅÄÖåäö'’:-]+", re.U)
HERKAT = re.compile(
    r"(suomalai|ulkomaalai|ulkomai|maahanmuutt|turvapaikan|pakolai|somali|afgaan|irakilai|syyrialai|venäläi|virolai|ukrainalai|romani|"
    r"marokkolai|eritrealai|nigerialai|ruotsalai|thaimaalai|kurdi|arabi|muslim|islam|kristit|juutalai|"
    r"sdp|kokoomu|perussuomalai|^ps:?n?$|keskust|kepu|vihreä|vihreide|vasemmistoliit|vasemmisto|rkp|kristillisdemo|^kd:?n?$|liike nyt|"
    r"pääministeri|ministeri|kansanedustaj|puolue|hallitu|oppositi|"
    r"isä|äiti|poika|tytär|puoliso|vaimo|aviomies|"
    r"raiskau|raiskas|puukot|ampu|ampui|murha|tappo|surma|pahoinpitel|ahdistel|"
    r"valehtel|myönsi|kiistää|kiisti|paljastu|kohu|skandaal|rasis|syrjin|nolo|tyly|lyttä|sätti|raivo)", re.I)
LIVE = re.compile(r"\b(live|suora lähetys|seuraa|seuraamme|hetki hetkeltä|katso suora|video:)\b", re.I)

def _sanat(s):
    return [w for w in _SANA.findall(_norm(s))]

def analyysi(m, tagit=()):
    """Palauttaa (pisteet 0–10, poistetut sanat, lisätyt sanat). Mitä suurempi, sitä merkittävämpi muutos."""
    a, b = _sanat(m["vanha"]), _sanat(m["uusi"])
    sm = difflib.SequenceMatcher(None, [w.lower() for w in a], [w.lower() for w in b])
    pois, lis, nimi_pois = [], [], False
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("delete", "replace"):
            pois.append(" ".join(a[i1:i2]))
            nimi_pois = nimi_pois or any(a[k][:1].isupper() for k in range(max(i1, 1), i2))
        if op in ("insert", "replace"): lis.append(" ".join(b[j1:j2]))
    r = sm.ratio()
    merkit = difflib.SequenceMatcher(None, _norm(m["vanha"]).lower(), _norm(m["uusi"]).lower()).ratio()
    if merkit > 0.93:                        # kirjoitusvirhe, välimerkki, iso kirjain
        return 0, pois, lis
    p = 2 if r > 0.6 else 3 if r > 0.3 else 1   # täysin eri otsikko = usein päivittyvä juttu
    pois_herkat = [w for w in " ".join(pois).split() if HERKAT.search(w.strip(",.:;!?”\"'"))]
    lis_herkat = [w for w in " ".join(lis).split() if HERKAT.search(w.strip(",.:;!?”\"'"))]
    p += min(4, 2 * len(pois_herkat)) + min(2, len(lis_herkat))
    # poistettu nimi (iso alkukirjain keskellä otsikkoa)
    if nimi_pois:
        p += 1
    if any(t.startswith(("politiikka", "yhteiskunta")) for t in tagit):
        p += 1
    if any(t.startswith(("urheilu", "viihde", "lifestyle")) for t in tagit):
        p -= 1
    if LIVE.search(m["vanha"]) or LIVE.search(m["uusi"]) or r < 0.15:
        p -= 2
    return max(0, min(10, p)), pois, lis

def _lyhenna(s, n):
    s = _norm(s)
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"

def x_teksti(m, pois=None, lis=None):
    """Neutraali jakoteksti X:ään. Linkki lasketaan X:ssä 23 merkiksi, joten tekstille jää noin 250 merkkiä."""
    vanha, uusi = _norm(m["vanha"]), _norm(m["uusi"])
    for n in (200, 110, 95, 80):
        t = f'{m["s"]} muutti otsikkoa julkaisun jälkeen.\n\nEnnen: ”{_lyhenna(vanha, n)}”\nNyt: ”{_lyhenna(uusi, n)}”'
        if len(t) <= 250:
            return t
    return t

def _rivita(draw, teksti, fontti, leveys, max_rivit):
    sanat, rivit, nyk = teksti.split(), [], ""
    for w in sanat:
        koe = (nyk + " " + w).strip()
        if draw.textlength(koe, font=fontti) <= leveys:
            nyk = koe
        else:
            rivit.append(nyk); nyk = w
    if nyk: rivit.append(nyk)
    if len(rivit) > max_rivit:
        rivit = rivit[:max_rivit]
        while draw.textlength(rivit[-1] + "…", font=fontti) > leveys and " " in rivit[-1]:
            rivit[-1] = rivit[-1].rsplit(" ", 1)[0]
        rivit[-1] += "…"
    return rivit

def tee_kuva(m, polku, site):
    """1200×630 jakokuva: vanha otsikko yliviivattuna, uusi alla."""
    from PIL import Image, ImageDraw, ImageFont
    W, H, X = 1200, 630, 64
    im = Image.new("RGB", (W, H), "#0d1117"); d = ImageDraw.Draw(im)
    f = lambda n, s: ImageFont.truetype(os.path.join(FONTIT, f"Inter-{n}.otf"), s)
    pieni, merkki, iso = f("SemiBold", 26), f("Bold", 24), f("Bold", 42)
    d.rectangle([0, 0, W, 8], fill="#ffc93c")
    d.text((X, 40), "OTSIKKO MUUTTUI", font=merkki, fill="#ffc93c")
    klo = datetime.fromisoformat(m["t"]).astimezone(HKI)
    d.text((W - X, 42), f'{m["s"]} · havaittu {klo.day}.{klo.month}. klo {klo:%H.%M}', font=pieni, fill="#8d99a8", anchor="ra")
    y = 100
    for laji, teksti, vari, tausta in (("ENNEN", m["vanha"], "#c9a3a3", "#3a1f24"), ("NYT", m["uusi"], "#ffffff", "#163527")):
        rivit = _rivita(d, _norm(teksti), iso, W - 2 * X - 40, 3)
        korkeus = 50 + len(rivit) * 54
        d.rounded_rectangle([X, y, W - X, y + korkeus], radius=18, fill=tausta)
        d.text((X + 22, y + 14), laji, font=merkki, fill="#ff8a8a" if laji == "ENNEN" else "#5fe3a1")
        ty = y + 46
        for r in rivit:
            d.text((X + 22, ty), r, font=iso, fill=vari)
            if laji == "ENNEN":
                lw = d.textlength(r, font=iso); d.line([X + 22, ty + 26, X + 22 + lw, ty + 26], fill="#ff5d5d", width=4)
            ty += 54
        y += korkeus + 18
    d.text((X, H - 56), f"{site} · Todiste: arkistokopio ja lohkoketjusinetti", font=pieni, fill="#8d99a8")
    os.makedirs(os.path.dirname(polku), exist_ok=True)
    im.save(polku, "PNG", optimize=True)

def rakenna_sivu(sivu, kirjoita, esc, lahde_html, tiivisteet, site, uutiset=None, base=""):
    uutiset = uutiset or []
    tagit = {u["l"]: u.get("t", []) for u in uutiset}
    nyt = datetime.now(timezone.utc)
    kuvadir = os.path.join(DIR, "muutokset", "k")
    try:
        import PIL  # noqa: F401
        kuvat_ok = os.path.exists(os.path.join(FONTIT, "Inter-Bold.otf"))
    except Exception:
        kuvat_ok = False
    tiedot = []
    for m in _m:
        p, pois, lis = analyysi(m, tagit.get(m["l"], ()))
        tiedot.append(dict(m=m, id=mid(m), p=p, pois=pois, lis=lis))
    # nostot: merkittävimmät 7 päivän ajalta, yksi per uutinen
    raja7 = (nyt - timedelta(days=7)).isoformat()
    paras = {}
    for x in tiedot:
        if x["m"]["t"] >= raja7 and x["p"] >= 5 and (x["m"]["l"] not in paras or x["p"] > paras[x["m"]["l"]]["p"]):
            paras[x["m"]["l"]] = x
    nostot = sorted(paras.values(), key=lambda x: (x["p"], x["m"]["t"]), reverse=True)[:10]
    nosto_idt = {x["id"] for x in nostot}
    # jakokuvat (välimuistissa edellisistä ajoista)
    rajak = (nyt - timedelta(days=KUVA_PV)).isoformat()
    voimassa, tehty = set(), 0
    for x in tiedot:
        if x["m"]["t"] >= rajak or x["id"] in nosto_idt or x["p"] >= 5:
            pk = os.path.join(kuvadir, x["id"] + ".png")
            if kuvat_ok and not os.path.exists(pk) and tehty < 400:
                try:
                    tee_kuva(x["m"], pk, site); tehty += 1
                except Exception as e:
                    print("kuva epäonnistui:", str(e)[:80])
            if os.path.exists(pk):
                voimassa.add(x["id"]); x["kuva"] = True
    if os.path.isdir(kuvadir):
        for f in os.listdir(kuvadir):
            if f[:-4] not in voimassa:
                os.remove(os.path.join(kuvadir, f))
    print(f"korjausvahti: jakokuvia uusia {tehty}, yhteensä {len(voimassa)}, nostoja {len(nostot)}")

    def jako(x, syv):
        url = f"{base}/muutokset/m/{x['id']}/"
        return (f'<button class="jaa" type="button" data-u="{esc(url)}" data-o="{esc(x_teksti(x["m"], x["pois"], x["lis"]))}" aria-label="Jaa muutos"></button>')

    def kortti(x, syv, iso=False):
        m = x["m"]; r = "../" * syv
        v, u = _erot(m["vanha"], m["uusi"], esc)
        klo = datetime.fromisoformat(m["t"]).astimezone(HKI)
        return (f'<li class="kv{" kv-iso" if iso else ""}"><div class="mt">{lahde_html(m["s"])}<span>havaittu {klo.day}.{klo.month}. klo {klo:%H.%M}</span>{jako(x, syv)}</div>'
                f'<div class="kv-v"><b>Ennen</b> {v}</div><div class="kv-u"><b>Nyt</b> {u}</div>'
                f'<div class="kv-ark"><a href="{r}muutokset/m/{x["id"]}/">Todiste ja jakaminen →</a></div></li>')

    CSS_KV = ('<style>.kv{padding:12px 14px;list-style:none}ul.rows{padding:0;margin:0}.kv+.kv{border-top:1px solid var(--line)}.kv-v{color:var(--mute);margin-top:6px}.kv-u{margin-top:4px;font-weight:600}'
              '.kv b{display:inline-block;min-width:44px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}'
              '.kv del{background:rgba(255,93,93,.2);text-decoration:line-through;text-decoration-color:#ff5d5d}'
              '.kv ins{background:rgba(61,220,151,.22);text-decoration:none}.kv-sha{font-size:12px;color:var(--mute);word-break:break-all}'
              '.kv-ark{font-size:13px;margin-top:6px}.kv-ark a{color:var(--acc)}.kv-info{margin:10px 0 18px;color:var(--mute)}.kv-info summary{cursor:pointer;color:var(--fg)}'
              '.kv-iso .kv-u{font-size:1.1em}.kv-nostot{border:1px solid var(--acc);border-radius:14px;padding:4px 0;margin:14px 0}'
              '.kv-nostot{padding:0 0 4px}.kv-nostot h2{padding:12px 14px 8px;margin:0}.kv-nav{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.kv-nav a{background:var(--chip);color:var(--fg);'
              'text-decoration:none;border-radius:999px;padding:7px 13px;font-weight:700;font-size:14px}.kv-nav a[aria-current]{background:var(--acc);color:#111}'
              '.kv-p{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:12px 0}.kv-p .kv-v,.kv-p .kv-u{font-size:1.15em;line-height:1.45}'
              '.kv-isonapit{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.kv-isonapit a,.kv-isonapit button{display:inline-flex;align-items:center;gap:6px;'
              'border:0;border-radius:12px;padding:12px 18px;font:700 16px system-ui,sans-serif;cursor:pointer;text-decoration:none}'
              '.kv-xnappi{background:#000;color:#fff;border:1px solid #444}.kv-muu{background:var(--chip);color:var(--fg)}.kv-kuva{width:100%;height:auto;border-radius:12px;border:1px solid var(--line);margin:8px 0}'
              '.kv-tilasto{width:100%;border-collapse:collapse;font-size:14px}.kv-tilasto th,.kv-tilasto td{padding:8px 6px;border-bottom:1px solid var(--line);text-align:right}'
              '.kv-tilasto th:first-child,.kv-tilasto td:first-child{text-align:left}.kv-palkki{display:block;height:6px;border-radius:3px;background:var(--acc);margin-top:4px}</style>')
    NAV = lambda r, akt: ('<nav class="kv-nav" aria-label="Korjausvahti">' + "".join(
        f'<a href="{r}{p}"{" aria-current=page" if akt == k else ""}>{n}</a>' for k, p, n in
        (("kaikki", "muutokset/", "Kaikki muutokset"), ("tilastot", "muutokset/tilastot/", "Tilastot"))) + "</nav>")
    sop = (f'<a href="https://sepolia.etherscan.io/address/{SOPIMUS}#readContract" rel="noopener" target="_blank">sopimuksesta</a> '
           'funktiolla <code>tarkista</code>') if SOPIMUS else ""
    INFO = (f'<details class="kv-info"><summary>Miten muutokset on todistettu?</summary><p>Jokaisen päivän muutoslistasta lasketaan sormenjälki '
            f'(SHA-256), joka tallennetaan lohkoketjuun. Sen jälkeen kenenkään, myöskään {esc(site)}:n, ei ole mahdollista muuttaa listaa '
            f'jälkikäteen huomaamatta. Laskutapa: päivän muutokset muodossa [linkki, ennen, nyt, havaintoaika] aikajärjestyksessä, '
            f'tiiviinä JSON-taulukkona, SHA-256. Lisäksi tuoreimmista muutoksista sinetöidään tilannekuva 5 minuutin välein aina, kun uusia muutoksia on tullut. '
            f'Sinetit voi tarkistaa {sop}. Data: <a href="/muutokset.json">muutokset.json</a>.</p>'
            f'<p>Arkistokopiot: osasta uutisista tallennetaan kopio <a href="https://web.archive.org" rel="noopener">Internet Archiveen</a> heti kun ne julkaistaan, '
            f'ja muuttuneesta uutisesta myös muutoksen jälkeen. Kopio on riippumattoman kolmannen osapuolen tallenne siitä, mitä sivulla luki.</p></details>')
    JOHDANTO = (f'<p class="lead">Media muuttaa joskus jo julkaistun uutisen otsikkoa. Tälle sivulle tallentuu, mitä otsikossa luki ennen ja mitä nyt. '
                f'Seurannassa ovat median omat syötteet (Yle, HS, IS, Iltalehti, MTV, Suomen Uutiset) {SEURANTA_H} tunnin ajan julkaisusta. '
                f'Otsikon muuttaminen on usein täysin tavallista, esimerkiksi tarkennus, uusi tieto tai korjaus.</p>')

    # ---- pääsivu ----
    paivat = {}
    for x in tiedot:
        paivat.setdefault(paiva(x["m"]), []).append(x)
    osat = []
    for p in sorted(paivat, reverse=True):
        lista = sorted(paivat[p], key=lambda x: x["m"]["t"], reverse=True)
        d = datetime.fromisoformat(p)
        t = tiivisteet.get(p, {})
        sinetti = (f'<p class="kv-sha">Päivän sormenjälki (SHA-256): <code>{t.get("sha256", "")}</code>'
                   + (" · sinetöity lohkoketjuun" if t.get("valmis") else " · päivä on kesken, tilannekuvat sinetöidään 5 minuutin välein") + "</p>")
        osat.append(f'<section><h2>{d.day}.{d.month}.{d.year} · {len(lista)} muutettua otsikkoa</h2>{sinetti}<ul class="rows">{"".join(kortti(x, 1) for x in lista)}</ul></section>')
    nosto_html = (f'<section class="kv-nostot"><h2>Viikon merkittävimmät muutokset</h2><ul class="rows">{"".join(kortti(x, 1, True) for x in nostot[:5])}</ul></section>'
                  if nostot else "")
    tyhja = '<p class="lead">Muutoksia ei ole vielä havaittu. Seuranta on käynnissä: jokainen median oma syöte tarkistetaan noin 10 minuutin välein.</p>'
    runko = f'<h1>Muutetut otsikot</h1>{JOHDANTO}{NAV("../", "kaikki")}{INFO}{nosto_html}{"".join(osat) or tyhja}{CSS_KV}'
    kirjoita("muutokset/index.html", sivu(f"Muutetut otsikot – näin media muuttaa uutisotsikoita | {site}",
             "Mitä uutisotsikossa luki ennen ja mitä nyt. Korjausvahti tallentaa median jälkikäteen muuttamat otsikot, todisteena arkistokopio ja lohkoketjusinetti.",
             "muutokset/", 1, runko, og_kuva=(f"{base}/muutokset/k/{nostot[0]['id']}.png" if nostot and nostot[0].get("kuva") else None)))

    # ---- jakosivut ----
    import shutil
    shutil.rmtree(os.path.join(DIR, "muutokset", "m"), ignore_errors=True)
    for x in tiedot:
        m = x["m"]
        v, u = _erot(m["vanha"], m["uusi"], esc)
        klo = datetime.fromisoformat(m["t"]).astimezone(HKI)
        julk = ""
        try:
            ja = datetime.fromisoformat(m["a"]).astimezone(HKI)
            julk = f"Julkaistu {ja.day}.{ja.month}. klo {ja:%H.%M} · "
        except Exception:
            pass
        url = f"{base}/muutokset/m/{x['id']}/"
        xt = x_teksti(m, x["pois"], x["lis"])
        e = urllib.parse.quote
        t = tiivisteet.get(paiva(m), {})
        ark = "".join(f'<li><a href="{esc(h)}" rel="noopener" target="_blank">{n}</a></li>' for n, h in
                      (("Arkistokopio ennen muutosta", m.get("ark_ennen")), ("Arkistokopio muutoksen jälkeen", m.get("ark_nyt"))) if h)
        mita = ""
        if x["pois"] or x["lis"]:
            mita = ('<p class="kv-mita">' + (f'<b>Poistettiin:</b> {esc(" … ".join(x["pois"]))}' if x["pois"] else "")
                    + ("<br>" if x["pois"] and x["lis"] else "") + (f'<b>Lisättiin:</b> {esc(" … ".join(x["lis"]))}' if x["lis"] else "") + "</p>")
        kuva = f'<img class="kv-kuva" src="../../k/{x["id"]}.png" alt="Ennen: {esc(m["vanha"])}. Nyt: {esc(m["uusi"])}" width="1200" height="630" loading="lazy">' if x.get("kuva") else ""
        runko = (f'<p class="kv-ark" style="margin-top:0"><a href="../../">← Kaikki muutetut otsikot</a></p>'
                 f'<h1>{esc(m["s"])} muutti otsikkoa</h1><p class="lead">{julk}muutos havaittu {klo.day}.{klo.month}.{klo.year} klo {klo:%H.%M}</p>'
                 f'<div class="kv-p kv"><div class="kv-v"><b>Ennen</b> {v}</div><div class="kv-u"><b>Nyt</b> {u}</div></div>{mita}'
                 f'<div class="kv-isonapit"><a class="kv-xnappi" href="https://x.com/intent/post?text={e(xt)}&url={e(url)}" target="_blank" rel="noopener">Jaa X:ssä</a>'
                 f'<button class="jaa kv-muu" type="button" data-u="{esc(url)}" data-o="{esc(xt)}" aria-label="Muut jakotavat"></button>'
                 f'<a class="kv-muu" href="{esc(m["l"])}" target="_blank" rel="noopener">Avaa alkuperäinen juttu</a></div>{kuva}'
                 f'<section class="kv-p"><h2>Todiste</h2><ul>{ark}<li>Päivän muutoslistan sormenjälki (SHA-256): <code style="word-break:break-all">{t.get("sha256", "")}</code></li>'
                 f'<li>Sormenjälki on tallennettu lohkoketjuun. Kenenkään, myöskään {esc(site)}:n, ei ole mahdollista muuttaa tätä tietoa jälkikäteen huomaamatta.</li></ul>{INFO}</section>'
                 f'<p class="kv-sha">Otsikon muuttaminen on usein tavallista: tarkennus, uusi tieto tai korjaus. Sivu näyttää vain, mitä otsikossa luki ennen ja mitä nyt.</p>{CSS_KV}')
        kirjoita(f"muutokset/m/{x['id']}/index.html", sivu(f"{m['s']} muutti otsikkoa: ”{_lyhenna(m['uusi'], 70)}” | {site}",
                 f"Ennen: ”{_lyhenna(m['vanha'], 120)}” Nyt: ”{_lyhenna(m['uusi'], 120)}”", f"muutokset/m/{x['id']}/", 3, runko,
                 og_kuva=(f"{base}/muutokset/k/{x['id']}.png" if x.get("kuva") else None), noindex=x["p"] < 5))

    # ---- tilastot ----
    raja30 = (nyt - timedelta(days=30)).isoformat()
    # seuranta alkoi, kun ensimmäinen suoran syötteen uutinen merkittiin (d); nimittäjänä kaikki saman median uutiset siitä lähtien
    alku = min([u["a"] for u in uutiset if u.get("d") and u.get("a")] or [None]) if uutiset else None
    alku = max(alku, raja30) if alku else None
    seuratut_lahteet = {u["s"] for u in uutiset if u.get("d")} | {x["m"]["s"] for x in tiedot}
    seuratut = {}
    for u in uutiset:
        if alku and u.get("s") in seuratut_lahteet and (u.get("a") or "") >= alku:
            seuratut[u["s"]] = seuratut.get(u["s"], 0) + 1
    muut = {}
    viive = {}
    for x in tiedot:
        m = x["m"]
        if alku and m["t"] >= alku:
            muut[m["s"]] = muut.get(m["s"], 0) + 1
            try:
                viive.setdefault(m["s"], []).append((datetime.fromisoformat(m["t"]) - datetime.fromisoformat(m["a"])).total_seconds() / 3600)
            except Exception:
                pass
    rivit = []
    lahteet = sorted(set(seuratut) | set(muut), key=lambda s: -(muut.get(s, 0) / max(1, seuratut.get(s, 0))))
    maxo = max([muut.get(s, 0) / max(1, seuratut.get(s, 0)) for s in lahteet] or [1]) or 1
    for s in lahteet:
        n, k = seuratut.get(s, 0), muut.get(s, 0)
        if n < 20:
            continue
        osuus = k / n
        vv = sorted(viive.get(s, []))
        med = f"{vv[len(vv)//2]:.1f} h" if vv else "–"
        rivit.append(f'<tr><td>{lahde_html(s)}<span class="kv-palkki" style="width:{max(2, round(100 * osuus / maxo))}%"></span></td><td>{n}</td><td>{k}</td><td><b>{osuus*100:.1f} %</b></td><td>{med}</td></tr>')
    if alku:
        ad = datetime.fromisoformat(alku).astimezone(HKI)
        jakso = f"{ad.day}.{ad.month}.–{nyt.astimezone(HKI).day}.{nyt.astimezone(HKI).month}.{nyt.astimezone(HKI).year}"
    else:
        jakso = "viimeiset 30 päivää"
    paivia = (nyt - datetime.fromisoformat(alku)).total_seconds() / 86400 if alku else 0
    if paivia < 3:
        rivit = [f'<tr><td colspan="5" style="text-align:left;padding:16px 6px">Tilastot karttuvat. Vertailu julkaistaan, kun seurantaa on kertynyt vähintään kolmelta päivältä'
                 + (f' (noin {(datetime.fromisoformat(alku) + timedelta(days=3)).astimezone(HKI):%-d.%-m.})' if alku else '') + '.</td></tr>']
    runko = (f'<h1>Kuka muuttaa otsikoitaan eniten?</h1><p class="lead">Osuus kertoo, kuinka suuren osan median omassa syötteessä julkaisemista uutisista '
             f'otsikko muuttui {SEURANTA_H} tunnin sisällä julkaisusta. Jakso: {jakso}. Mediat, joilta on alle 20 seurattua uutista, eivät ole mukana.</p>{NAV("../../", "tilastot")}'
             f'<div style="overflow-x:auto"><table class="kv-tilasto"><tr><th>Media</th><th>Uutisia</th><th>Muutettuja</th><th>Osuus</th><th>Mediaaniaika</th></tr>{"".join(rivit)}</table></div>'
             f'<p class="kv-sha">Mediaaniaika = tyypillinen aika julkaisusta otsikon muutokseen. Muutos voi olla tarkennus, uusi tieto, korjaus tai otsikon muotoilu. '
             f'Erot medioiden välillä kertovat myös erilaisista toimitustavoista, esimerkiksi päivittyvistä jutuista. Lähtödata: <a href="/muutokset.json">muutokset.json</a>.</p>{CSS_KV}')
    kirjoita("muutokset/tilastot/index.html", sivu(f"Kuka muuttaa otsikoitaan eniten? Medioiden vertailu | {site}",
             "Kuinka suuren osan uutisotsikoistaan kukin suomalainen media muuttaa julkaisun jälkeen. Päivittyvä vertailu.", "muutokset/tilastot/", 2, runko))

    # ---- nostot.json viikkokoostetta varten ----
    json.dump({"p": nyt.isoformat(), "nostot": [{"url": f"{base}/muutokset/m/{x['id']}/", "kuva": f"{base}/muutokset/k/{x['id']}.png" if x.get("kuva") else None,
               "media": x["m"]["s"], "ennen": x["m"]["vanha"], "nyt": x["m"]["uusi"], "havaittu": x["m"]["t"], "pisteet": x["p"],
               "poistettiin": x["pois"], "lisattiin": x["lis"], "x_teksti": x_teksti(x["m"], x["pois"], x["lis"]), "juttu": x["m"]["l"]} for x in nostot]},
              open(os.path.join(DIR, "muutokset", "nostot.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return ["muutokset/", "muutokset/tilastot/"] + [f"muutokset/m/{x['id']}/" for x in tiedot if x["p"] >= 5]
