#!/usr/bin/env python3
"""Laaja uutiskooste: pääaiheet ja alaaiheet, vain suomalaiset (.fi) lähteet.
Hakee RSS-virrat ja Google Uutisten aihehaut, luokittelee uutiset, rakentaa staattiset aihesivut, Oma syöte -sivun, sitemapin ja robotsin."""
import os, sys, re, json, time, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aiheet import AIHEET

DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("BASE_URL", "https://miksu900.github.io/uutisvahti/kooste").rstrip("/")
SITE = os.environ.get("SITE_NAME", "Uutiskooste")
TESTI = os.environ.get("KOOSTE_TESTI") == "1"
UA = "Mozilla/5.0 (compatible; uutiskooste/1.0; oma uutiskooste)"
SAILYTYS_PV, MAX_ITEMS = 14, 3500
HKI = ZoneInfo("Europe/Helsinki")

SUORAT = [
    ("Yle", "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"),
    ("Yle Urheilu", "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_URHEILU"),
    ("Helsingin Sanomat", "https://www.hs.fi/rss/tuoreimmat.xml"),
    ("Ilta-Sanomat", "https://www.is.fi/rss/tuoreimmat.xml"),
    ("Iltalehti", "https://www.iltalehti.fi/rss/uutiset.xml"),
    ("MTV Uutiset", "https://www.mtvuutiset.fi/api/feed/rss/uutiset_uusimmat"),
    ("Verkkouutiset", "https://www.verkkouutiset.fi/feed/"),
    ("Suomen Uutiset", "https://www.suomenuutiset.fi/feed/"),
    ("Kauppalehti", "https://www.kauppalehti.fi/rss/uutiset"),
    ("Maaseudun Tulevaisuus", "https://www.mt.fi/rss/uusimmat"),
    ("Kaleva", "https://www.kaleva.fi/rss/"),
    ("Aamulehti", "https://www.aamulehti.fi/rss/"),
]
NIMET = {"HS.fi": "Helsingin Sanomat", "Hs.fi": "Helsingin Sanomat", "Yle Uutiset": "Yle", "yle.fi": "Yle", "Is.fi": "Ilta-Sanomat", "IS.fi": "Ilta-Sanomat"}

def hae(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    return urllib.request.urlopen(r, timeout=40).read()

def txt(e, *nimet):
    for n in nimet:
        x = e.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
    return ""

def aika(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def puhdista(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").replace("­", "").strip()

def parse(data, oletus):
    root = ET.fromstring(data)
    A = "{http://www.w3.org/2005/Atom}"
    out = []
    for it in (root.findall(".//item") or root.findall(".//" + A + "entry")):
        o = puhdista(txt(it, "title", A + "title"))
        link = txt(it, "link")
        if not link:
            l = it.find(A + "link")
            link = l.get("href") if l is not None else ""
        k = puhdista(txt(it, "description", A + "summary"))
        p = aika(txt(it, "pubDate", A + "updated", A + "published"))
        lahde, host = oletus, ""
        s = it.find("source")
        if s is not None:
            if (s.text or "").strip():
                lahde = s.text.strip()
            host = urllib.parse.urlparse(s.get("url", "")).hostname or ""
            if o.endswith(" - " + lahde):
                o = o[: -len(lahde) - 3]
        lahde = NIMET.get(lahde, lahde)
        if k.lower().startswith(o.lower()[:40]):
            k = ""
        if o and link:
            out.append({"o": o, "l": link.strip(), "s": lahde, "h": host, "a": p.isoformat() if p else None, "k": k[:220]})
    return out

def sana_re(sanat):
    return re.compile(r"(?<![a-zäöå0-9])(" + "|".join(re.escape(s) for s in sanat) + ")", re.I)
LUOK = {f"{p}/{a}": sana_re(v["sanat"]) for p, pv in AIHEET.items() for a, v in pv["ala"].items()}

def luokittele(it):
    t = []
    for k, rx in LUOK.items():
        otsikko_osumat = {m.lower() for m in rx.findall(it["o"])}
        kuv_osumat = {m.lower() for m in rx.findall(it["k"])}
        if otsikko_osumat or len(kuv_osumat) >= 2:
            t.append(k)
    return t

def suomalainen(it):
    h = it.get("h", "")
    return h.endswith(".fi") if h else False

def avain(v):
    return re.sub(r"[^a-z0-9äöå]+", "", v["o"].lower())

def esc(s):
    return html.escape(s or "", quote=True)

def hki(iso, muoto):
    return datetime.fromisoformat(iso).astimezone(HKI).strftime(muoto)

CSS = """:root{--bg:#14161a;--fg:#e8e6e1;--mute:#9aa0a8;--line:#2a2e35;--card:#1b1e23;--acc:#e0b04a;--chip:#232830}
@media (prefers-color-scheme:light){:root{--bg:#f6f4ef;--fg:#1d1f23;--mute:#6a707a;--line:#dedbd2;--card:#fff;--acc:#9a6b00;--chip:#ece9e0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 Georgia,"Times New Roman",serif}
main{max-width:760px;margin:0 auto;padding:16px}
header.top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.logo{font-size:1.4rem;font-weight:700;color:var(--fg);text-decoration:none}
nav.paa{display:flex;flex-wrap:wrap;gap:6px 14px;font:14px/1.3 system-ui,sans-serif;margin:8px 0 14px}
nav.paa a{color:var(--mute);text-decoration:none;padding:4px 0;border-bottom:2px solid transparent}
nav.paa a[aria-current],nav.paa a:hover{color:var(--fg);border-bottom-color:var(--acc)}
h1{font-size:1.6rem;line-height:1.2;margin:10px 0 6px}h2{font-size:1.15rem;margin:26px 0 8px}
.lead{color:var(--mute);font:14px/1.5 system-ui,sans-serif;margin:0 0 12px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px;font:14px/1.2 system-ui,sans-serif}
.chips a{background:var(--chip);color:var(--fg);text-decoration:none;border-radius:999px;padding:7px 12px}
.chips a[aria-current]{background:var(--acc);color:#14161a}
.item{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px}
.item a{color:var(--fg);text-decoration:none;font-size:1.05rem;font-weight:600;display:block}.item a:visited{color:var(--mute)}
.kuv{color:var(--mute);font-size:.93rem;margin-top:4px}
.meta{font:12.5px/1.4 system-ui,sans-serif;color:var(--mute);margin-top:6px}
.paiva{font:600 12.5px system-ui,sans-serif;color:var(--acc);margin:18px 0 8px}
footer{font:12px/1.6 system-ui,sans-serif;color:var(--mute);margin:30px 0 40px}
.btn,button{background:var(--acc);color:#14161a;border:0;border-radius:8px;padding:10px 14px;font:600 15px system-ui,sans-serif;cursor:pointer}
.sec{background:var(--chip);color:var(--fg)}
fieldset{border:1px solid var(--line);border-radius:10px;margin:0 0 10px;padding:8px 12px}
legend{font:600 15px system-ui,sans-serif;padding:0 6px}
label{display:flex;gap:8px;align-items:center;font:15px/1.3 system-ui,sans-serif;padding:6px 0}
input[type=checkbox]{width:20px;height:20px;accent-color:var(--acc)}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}"""

def rel(d):
    return "../" * d if d else "./"

def sivu(otsikko, kuvaus, polku, syvyys, runko, jsonld=None, aktiivinen=None):
    r = rel(syvyys)
    nav = "".join(f'<a href="{r}{p}/"{" aria-current=page" if p == aktiivinen else ""}>{esc(v["nimi"])}</a>' for p, v in AIHEET.items())
    kanon = f"{BASE}/{polku}" if polku else f"{BASE}/"
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")}</script>' if jsonld else ""
    return f"""<!doctype html>
<html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(otsikko)}</title>
<meta name="description" content="{esc(kuvaus)}">
<link rel="canonical" href="{kanon}">
<meta property="og:title" content="{esc(otsikko)}"><meta property="og:description" content="{esc(kuvaus)}"><meta property="og:type" content="website"><meta property="og:locale" content="fi_FI"><meta property="og:url" content="{kanon}">
<meta name="robots" content="index,follow,max-snippet:-1">
{ld}<style>{CSS}</style></head><body><main>
<header class="top"><a class="logo" href="{r}">{esc(SITE)}</a><a class="btn sec" href="{r}oma/">Oma syöte</a></header>
<nav class="paa" aria-label="Pääaiheet">{nav}</nav>
{runko}
<footer><p>{esc(SITE)} kokoaa suomalaisten medioiden uutisotsikot ja linkit yhteen paikkaan aiheittain. Sivusto näyttää vain otsikon, lyhyen ingressin ja lähteen. Jutut luetaan lähteen omalla sivulla. Aiheet tunnistetaan automaattisesti hakusanoista, joten osuma voi joskus olla epätarkka. Päivitetään tunnin välein.</p></footer>
</main></body></html>"""

def lista_html(items, ryhmittele=True):
    out, pv = [], ""
    for u in items:
        if ryhmittele:
            p = hki(u["a"], "%-d.%-m.%Y")
            if p != pv:
                out.append(f'<div class="paiva">{p}</div>')
                pv = p
        k = f'<div class="kuv">{esc(u["k"][:170])}{"…" if len(u["k"]) > 170 else ""}</div>' if u["k"] and u["k"] != u["o"] else ""
        out.append(f'<article class="item"><a href="{esc(u["l"])}" rel="noopener" target="_blank">{esc(u["o"])}</a>{k}<div class="meta">{esc(u["s"])} · {hki(u["a"], "%-d.%-m. klo %H.%M")}</div></article>')
    return "\n".join(out) or '<p class="lead">Ei uutisia vielä. Sivu päivittyy tunnin välein.</p>'

def itemlist_ld(nimi, items, polku):
    return {"@context": "https://schema.org", "@type": "CollectionPage", "name": nimi, "url": f"{BASE}/{polku}", "inLanguage": "fi",
            "mainEntity": {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": u["l"], "name": u["o"]} for i, u in enumerate(items[:20])]}}

def kirjoita(polku, sisalto):
    p = os.path.join(DIR, polku)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(sisalto)

def rakenna(items, paivitetty):
    por = {}
    for u in items:
        for t in u["t"]:
            por.setdefault(t, []).append(u)
    urls = [("", paivitetty)]
    # etusivu
    runko = f'<h1>Suomen uutiset aiheittain</h1><p class="lead">Valitse aihe tai rakenna oma syöte: <a href="oma/">Oma syöte</a>.</p>'
    for p, pv in AIHEET.items():
        yl = [u for u in items if any(t.startswith(p + "/") for t in u["t"])][:5]
        chips = "".join(f'<a href="{p}/{a}/">{esc(av["nimi"])}</a>' for a, av in pv["ala"].items())
        runko += f'<h2><a href="{p}/" style="color:inherit">{esc(pv["nimi"])}</a></h2><div class="chips">{chips}</div>{lista_html(yl, False)}'
    kirjoita("index.html", sivu(f"{SITE}: Suomen uutiset aiheittain", "Suomalaisten medioiden uutiset aiheittain: politiikka, talous, yhteiskunta, lifestyle, teknologia, urheilu, viihde ja liikenne. Valitse omat aiheesi.", "", 0, runko, {"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": BASE + "/", "inLanguage": "fi"}))
    for p, pv in AIHEET.items():
        yl = [u for u in items if any(t.startswith(p + "/") for t in u["t"])][:80]
        chips = "".join(f'<a href="{a}/">{esc(av["nimi"])}</a>' for a, av in pv["ala"].items())
        runko = f'<h1>{esc(pv["nimi"])}: uusimmat uutiset</h1><p class="lead">{esc(pv["kuvaus"])}</p><div class="chips">{chips}</div>{lista_html(yl)}'
        kirjoita(f"{p}/index.html", sivu(f"{pv['nimi']}: uusimmat uutiset | {SITE}", pv["kuvaus"], f"{p}/", 1, runko, itemlist_ld(pv["nimi"], yl, f"{p}/"), p))
        urls.append((f"{p}/", paivitetty))
        for a, av in pv["ala"].items():
            yl = por.get(f"{p}/{a}", [])[:80]
            chips = "".join(f'<a href="../{b}/"{" aria-current=page" if b == a else ""}>{esc(bv["nimi"])}</a>' for b, bv in pv["ala"].items())
            kuv = f'{av["nimi"]}: uusimmat suomalaiset uutiset yhdessä paikassa. {pv["nimi"]}.'
            runko = f'<h1>{esc(av["nimi"])}: uusimmat uutiset</h1><p class="lead">{esc(pv["nimi"])} · {len(yl)} uutista viimeisen {SAILYTYS_PV} päivän ajalta.</p><div class="chips">{chips}</div>{lista_html(yl)}'
            kirjoita(f"{p}/{a}/index.html", sivu(f"{av['nimi']}: uusimmat uutiset | {SITE}", kuv, f"{p}/{a}/", 2, runko, itemlist_ld(av["nimi"], yl, f"{p}/{a}/"), p))
            urls.append((f"{p}/{a}/", paivitetty))
    # Oma syöte
    puu = {p: {"nimi": pv["nimi"], "ala": {a: av["nimi"] for a, av in pv["ala"].items()}} for p, pv in AIHEET.items()}
    oma = f"""<h1>Oma syöte</h1><p class="lead">Valitse aiheet, joista haluat uutisia. Valinta tallentuu tähän selaimeen, ja voit jakaa sen linkkinä.</p>
<div id="valinta"></div>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px"><button type="button" id="kaikki" class="sec">Valitse kaikki</button><button type="button" id="tyhjenna" class="sec">Tyhjennä</button><button type="button" id="jaa">Kopioi linkki valintaan</button></div>
<p class="lead" id="tila"></p>
<div id="syote"></div>
<noscript><p>Oma syöte vaatii JavaScriptin. Aihesivut toimivat ilman: valitse aihe yläpalkista.</p></noscript>
<script>
const PUU={json.dumps(puu, ensure_ascii=False)};
const KEY="uutiskooste_valinnat";
const $=i=>document.getElementById(i);
const esc=s=>s.replace(/[&<>"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
function lue(){{
 const h=location.hash.replace(/^#a=/,"");if(location.hash.startsWith("#a=")&&h)return h.split(",").filter(Boolean);
 try{{return JSON.parse(localStorage.getItem(KEY)||"[]")}}catch(e){{return[]}}}}
function tallenna(v){{try{{localStorage.setItem(KEY,JSON.stringify(v))}}catch(e){{}}}}
let valitut=new Set(lue()),data=null;
function piirraValinta(){{
 $("valinta").innerHTML=Object.entries(PUU).map(([p,v])=>'<fieldset><legend>'+esc(v.nimi)+'</legend><label><input type="checkbox" data-paa="'+p+'"> Koko aihe</label>'+Object.entries(v.ala).map(([a,n])=>'<label><input type="checkbox" data-ala="'+p+'/'+a+'"> '+esc(n)+'</label>').join("")+'</fieldset>').join("");
 paivitaValinta();
 document.querySelectorAll("input[data-ala]").forEach(i=>i.addEventListener("change",()=>{{i.checked?valitut.add(i.dataset.ala):valitut.delete(i.dataset.ala);muutos()}}));
 document.querySelectorAll("input[data-paa]").forEach(i=>i.addEventListener("change",()=>{{Object.keys(PUU[i.dataset.paa].ala).forEach(a=>{{const k=i.dataset.paa+"/"+a;i.checked?valitut.add(k):valitut.delete(k)}});muutos()}}));
}}
function paivitaValinta(){{
 document.querySelectorAll("input[data-ala]").forEach(i=>i.checked=valitut.has(i.dataset.ala));
 document.querySelectorAll("input[data-paa]").forEach(i=>i.checked=Object.keys(PUU[i.dataset.paa].ala).every(a=>valitut.has(i.dataset.paa+"/"+a)));}}
function muutos(){{tallenna([...valitut]);paivitaValinta();piirraSyote()}}
function piirraSyote(){{
 if(!data){{return}}
 if(!valitut.size){{$("syote").innerHTML="";$("tila").textContent="Valitse vähintään yksi aihe, niin syöte ilmestyy tähän.";return}}
 const lista=data.filter(u=>u.t.some(t=>valitut.has(t))).slice(0,150);
 $("tila").textContent=lista.length+" uutista valituista aiheista";
 let out="",pv="";
 for(const u of lista){{
  const p=new Date(u.a).toLocaleDateString("fi-FI",{{timeZone:"Europe/Helsinki",day:"numeric",month:"numeric",year:"numeric"}});
  if(p!==pv){{out+='<div class="paiva">'+p+'</div>';pv=p}}
  const k=u.k&&u.k!==u.o?'<div class="kuv">'+esc(u.k.slice(0,170))+(u.k.length>170?"…":"")+'</div>':"";
  const t=new Date(u.a).toLocaleTimeString("fi-FI",{{timeZone:"Europe/Helsinki",hour:"2-digit",minute:"2-digit"}});
  out+='<article class="item"><a href="'+esc(u.l)+'" rel="noopener" target="_blank">'+esc(u.o)+'</a>'+k+'<div class="meta">'+esc(u.s)+' · '+t+'</div></article>';}}
 $("syote").innerHTML=out;}}
$("kaikki").onclick=()=>{{Object.entries(PUU).forEach(([p,v])=>Object.keys(v.ala).forEach(a=>valitut.add(p+"/"+a)));muutos()}};
$("tyhjenna").onclick=()=>{{valitut.clear();muutos()}};
$("jaa").onclick=()=>{{const u=location.href.split("#")[0]+"#a="+[...valitut].join(",");try{{navigator.clipboard.writeText(u);$("tila").textContent="Linkki kopioitu."}}catch(e){{$("tila").textContent=u}}}};
piirraValinta();
fetch("../feed.json").then(r=>r.json()).then(d=>{{data=d.u;piirraSyote()}}).catch(()=>{{$("tila").textContent="Uutisten lataus epäonnistui. Yritä hetken kuluttua uudelleen."}});
</script>"""
    kirjoita("oma/index.html", sivu(f"Oma syöte: valitse itse aiheet | {SITE}", "Rakenna oma uutissyöte: valitse politiikka-, talous-, lifestyle- ja muista aiheista ne alaaiheet, jotka kiinnostavat sinua.", "oma/", 1, oma))
    urls.append(("oma/", paivitetty))
    kirjoita("feed.json", json.dumps({"p": paivitetty, "u": [{"o": u["o"], "l": u["l"], "s": u["s"], "a": u["a"], "k": u["k"], "t": u["t"]} for u in items[:2500]]}, ensure_ascii=False, separators=(",", ":")))
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{BASE}/{p}</loc><lastmod>{m[:10]}</lastmod></url>\n" for p, m in urls) + "</urlset>\n"
    kirjoita("sitemap.xml", sm)
    kirjoita("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")

def main():
    nyt = datetime.now(timezone.utc)
    try:
        vanha = json.load(open(os.path.join(DIR, "data.json"), encoding="utf-8"))["u"]
    except Exception:
        vanha = {}
    uutiset = {u["l"]: u for u in (vanha.values() if isinstance(vanha, dict) else vanha)}
    tila = []
    if TESTI:
        for i in range(30):
            k = list(LUOK)[i % len(LUOK)]
            uutiset[f"https://example.fi/{i}"] = {"o": f"Testiuutinen {i} {k}", "l": f"https://example.fi/{i}", "s": "Testi", "h": "example.fi", "a": (nyt - timedelta(hours=i)).isoformat(), "k": "ingressi", "t": [k]}
    else:
        haut = [(n, u, None) for n, u in SUORAT]
        for p, pv in AIHEET.items():
            for a, av in pv["ala"].items():
                url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(f"({av['haku']}) when:3d") + "&hl=fi&gl=FI&ceid=FI:fi"
                haut.append((f"Google: {p}/{a}", url, f"{p}/{a}"))
        for nimi, url, kiinteä in haut:
            try:
                lista = parse(hae(url), nimi)
                lisatty = 0
                for it in lista:
                    if kiinteä and not suomalainen(it):
                        continue
                    it["a"] = it["a"] or nyt.isoformat()
                    t = [kiinteä] if kiinteä else luokittele(it)
                    if not t:
                        continue
                    vanha_it = uutiset.get(it["l"])
                    if vanha_it:
                        vanha_it["t"] = sorted(set(vanha_it["t"]) | set(t))
                        continue
                    it["t"] = sorted(t)
                    uutiset[it["l"]] = it
                    lisatty += 1
                tila.append([nimi, len(lista), lisatty, "ok"])
            except Exception as e:
                tila.append([nimi, 0, 0, "VIRHE " + str(e)[:80]])
            time.sleep(0.4)
    raja = (nyt - timedelta(days=SAILYTYS_PV)).isoformat()
    items = [u for u in uutiset.values() if (u["a"] or "") >= raja]
    # sama otsikko eri virroista: yhdistä aiheet, pidä yksi (suosi median omaa virtaa)
    items.sort(key=lambda v: (avain(v), "news.google" in v["l"], v["a"]))
    uniq, nahty = [], {}
    for u in items:
        k = avain(u)
        if k in nahty:
            nahty[k]["t"] = sorted(set(nahty[k]["t"]) | set(u["t"]))
            continue
        nahty[k] = u
        uniq.append(u)
    uniq.sort(key=lambda v: v["a"], reverse=True)
    uniq = uniq[:MAX_ITEMS]
    pv = nyt.isoformat()
    rakenna(uniq, pv)
    json.dump({"p": pv, "tila": tila, "u": uniq}, open(os.path.join(DIR, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for t in tila:
        print(t)
    print("uutisia yhteensä:", len(uniq))

main()
