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
SOPIMUS = os.environ.get("KORJAUSVAHTI_SOPIMUS", "").strip() or "0x21d667A0dDC3376764c2a0884EE44dCb7728e30B"

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
        if m["t"] >= raja2 and not m.get("ark_nyt") and not m.get("ark_yritetty"):
            jono.append(("muutos", m))
    raja1 = (nyt - timedelta(hours=1)).isoformat()
    tuoreet = [u for u in uutiset.values() if u.get("d") and not u.get("ark") and not u.get("ark_yritetty") and (u.get("a") or "") >= raja1]
    tuoreet = sorted(tuoreet, key=lambda u: u.get("a") or "", reverse=True)
    tuoreet.sort(key=lambda u: not any(t.startswith(painotus) for t in u.get("t", [])))
    jono += [("uusi", u) for u in tuoreet]   # 2) uudet uutiset: kopio alkuperäisestä otsikosta
    tehty = 0
    for laji, x in jono[:ARK_MAX]:
        osoite = _arkistoi(x["l"])
        if laji == "muutos":
            x["ark_yritetty"] = 1
            if osoite: x["ark_nyt"] = osoite
        else:
            x["ark_yritetty"] = 1
            if osoite: x["ark"] = osoite
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

def rakenna_sivu(sivu, kirjoita, esc, lahde_html, tiivisteet, site):
    paivat = {}
    for m in _m:
        paivat.setdefault(paiva(m), []).append(m)
    osat = []
    for p in sorted(paivat, reverse=True):
        lista = sorted(paivat[p], key=lambda m: m["t"], reverse=True)
        d = datetime.fromisoformat(p)
        rivit = []
        for m in lista:
            v, u = _erot(m["vanha"], m["uusi"], esc)
            klo = datetime.fromisoformat(m["t"]).astimezone(HKI).strftime("klo %H.%M")
            ark = " · ".join(x for x in (
                f'<a href="{esc(m["ark_ennen"])}" rel="noopener" target="_blank">arkistokopio ennen</a>' if m.get("ark_ennen") else "",
                f'<a href="{esc(m["ark_nyt"])}" rel="noopener" target="_blank">arkistokopio nyt</a>' if m.get("ark_nyt") else "") if x)
            rivit.append(f'<li class="kv"><div class="mt">{lahde_html(m["s"])}<span>havaittu {klo}</span></div>'
                         f'<div class="kv-v"><b>Ennen</b> {v}</div><div class="kv-u"><b>Nyt</b> <a href="{esc(m["l"])}" rel="noopener" target="_blank">{u}</a></div>'
                         + (f'<div class="kv-ark">{ark}</div>' if ark else "") + '</li>')
        t = tiivisteet.get(p, {})
        sinetti = (f'<p class="kv-sha">Päivän sormenjälki (SHA-256): <code>{t.get("sha256", "")}</code>'
                   + (" · sinetöidään lohkoketjuun seuraavana yönä" if t.get("valmis") else " · päivä on kesken") + "</p>")
        osat.append(f'<section><h2>{d.day}.{d.month}.{d.year} · {len(lista)} muutettua otsikkoa</h2>{sinetti}<ul class="rows">{"".join(rivit)}</ul></section>')
    tyhja = '<p class="lead">Muutoksia ei ole vielä havaittu. Seuranta on käynnissä: jokainen median oma syöte tarkistetaan noin 10 minuutin välein.</p>'
    sop = (f' Sinetit voi tarkistaa <a href="https://sepolia.etherscan.io/address/{SOPIMUS}#readContract" rel="noopener" target="_blank">sopimuksesta</a> '
           'funktiolla <code>tarkista</code>.') if SOPIMUS else ""
    runko = (f'<h1>Muutetut otsikot</h1><p class="lead">Media muuttaa joskus jo julkaistun uutisen otsikkoa. Tälle sivulle tallentuu, '
             f'mitä otsikossa luki ennen ja mitä nyt. Seurannassa ovat median omat syötteet (Yle, HS, IS, Iltalehti, MTV, Suomen Uutiset) '
             f'{SEURANTA_H} tunnin ajan julkaisusta. Otsikon muuttaminen on usein täysin tavallista, esimerkiksi tarkennus tai korjaus.</p>'
             f'<details class="kv-info"><summary>Miten muutokset on todistettu?</summary><p>Jokaisen päivän muutoslistasta lasketaan sormenjälki '
             f'(SHA-256), joka tallennetaan lohkoketjuun. Sen jälkeen kenenkään, myöskään {esc(site)}:n, ei ole mahdollista muuttaa listaa '
             f'jälkikäteen huomaamatta. Laskutapa: päivän muutokset muodossa [linkki, ennen, nyt, havaintoaika] aikajärjestyksessä, '
             f'tiiviinä JSON-taulukkona, SHA-256. Lisäksi tuoreimmista muutoksista sinetöidään tilannekuva muutaman minuutin välein '
             f'(muutokset, jotka on havaittu 48 tunnin sisällä ennen sinetöintiä; rajat näkyvät sinetin selitteessä). Data: <a href="../muutokset.json">muutokset.json</a>.{sop}</p>'
             f'<p>Arkistokopiot: osasta uutisista tallennetaan kopio <a href="https://web.archive.org" rel="noopener">Internet Archiveen</a> heti kun ne julkaistaan, '
             f'ja muuttuneesta uutisesta myös muutoksen jälkeen. Kopio on riippumattoman kolmannen osapuolen tallenne siitä, mitä sivulla luki.</p></details>'
             + ("".join(osat) or tyhja)
             + '<style>.kv{padding:12px 14px}.kv-v{color:var(--mute);margin-top:4px}.kv-u{margin-top:4px}.kv del{background:rgba(255,93,93,.18);'
               'text-decoration:line-through}.kv ins{background:rgba(61,220,151,.22);text-decoration:none}.kv-sha{font-size:12px;color:var(--mute);'
               'word-break:break-all}.kv-ark{font-size:12px;margin-top:4px}.kv-info{margin:10px 0 18px;color:var(--mute)}.kv-info summary{cursor:pointer}</style>')
    kirjoita("muutokset/index.html", sivu(f"Muutetut otsikot | {site}", "Uutisotsikot, joita media on muuttanut julkaisun jälkeen.",
                                         "muutokset/", 1, runko, noindex=True))
