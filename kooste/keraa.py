#!/usr/bin/env python3
"""Laaja uutiskooste: pääaiheet ja alaaiheet, vain suomalaiset (.fi) lähteet.
Hakee RSS-virrat ja Google Uutisten aihehaut, luokittelee uutiset, rakentaa staattiset aihesivut, Oma syöte -sivun, sitemapin ja robotsin."""
import os, sys, re, json, time, html, hashlib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aiheet import AIHEET
from ryhmat import ryhmittele, mediat, puhdas_otsikko, muissa_medioissa

DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("BASE_URL", "https://nytpuhutaan.fi").rstrip("/")
SITE = os.environ.get("SITE_NAME", "Nytpuhutaan.fi")
TESTI = os.environ.get("KOOSTE_TESTI") == "1"
UA = "Mozilla/5.0 (compatible; uutiskooste/1.0; oma uutiskooste)"
SAILYTYS_PV, MAX_ITEMS = 14, 3500
SB_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SB_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
KESKUSTELU = bool(SB_URL and SB_KEY)
YLLAPITAJA = os.environ.get("KOOSTE_YLLAPITAJA", "").strip() or "[täydennä: ylläpitäjän nimi tai yritys]"
YHTEYS = os.environ.get("KOOSTE_YHTEYS", "").strip() or "[täydennä: sähköpostiosoite]"

def tunnus(link):
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
HKI = ZoneInfo("Europe/Helsinki")

SUORAT = [
    ("Yle", "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"),
    ("Yle Urheilu", "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_URHEILU"),
    ("Helsingin Sanomat", "https://www.hs.fi/rss/tuoreimmat.xml"),
    ("Ilta-Sanomat", "https://www.is.fi/rss/tuoreimmat.xml"),
    ("Iltalehti", "https://www.iltalehti.fi/rss/uutiset.xml"),
    ("MTV Uutiset", "https://www.mtvuutiset.fi/api/feed/rss/uutiset_uusimmat"),
    ("Suomen Uutiset", "https://www.suomenuutiset.fi/feed/"),
]
NIMET = {"HS.fi": "Helsingin Sanomat", "Hs.fi": "Helsingin Sanomat", "Yle Uutiset": "Yle", "yle.fi": "Yle", "Is.fi": "Ilta-Sanomat", "IS.fi": "Ilta-Sanomat", "mtvuutiset.fi": "MTV Uutiset", "Mtvuutiset.fi": "MTV Uutiset"}

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

# WordPress-syötteiden ja muiden lähteiden lisäämä roskateksti ingressin perässä
ROSKA = [re.compile(r"\s*The post\s.*$", re.S), re.compile(r"\s*(Continue reading|Lue lisää|Lue koko juttu)\b.*$", re.S | re.I),
         re.compile(r"\s*\[(…|\.\.\.|&#8230;)\]\s*$")]
INGRESSI_MAX = 100   # lehtikustantajan oikeus: vain hyvin lyhyt ote julkaistaan
def lyhyt(k, n=INGRESSI_MAX):
    k = (k or "").strip()
    if len(k) <= n:
        return k
    return k[:n].rsplit(" ", 1)[0].rstrip(" ,.;:–-") + "…"

def siivoa(k):
    for rx in ROSKA:
        k = rx.sub("", k or "")
    return re.sub(r"\s{2,}", " ", k).strip()

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
        k = siivoa(puhdista(txt(it, "description", A + "summary")))
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
LEHDET = {f"{p}/{a}": set(v.get("lehdet", ())) for p, pv in AIHEET.items() for a, v in pv["ala"].items()}

# Sanat, jotka alkavat hakusanalla mutta tarkoittavat muuta (esim. "tilanne sähköistyy" ei ole energiauutinen)
POIS = ("sähköist", "sähköinen", "sähköise", "sähköpost", "automaat", "autoritaar", "autenti", "matkalla", "matkaan",
        "oikeusvaltio", "tähtää", "tähtäi", "kurssil", "sarjamurha", "vrt")
SANA_LOPPU = re.compile(r"[a-zäöå0-9-]*", re.I)
def osumat(rx, teksti):
    out = set()
    for m in rx.finditer(teksti or ""):
        koko = (m.group(0) + SANA_LOPPU.match(teksti, m.end()).group(0)).lower()
        if not koko.startswith(POIS):
            out.add(m.group(0).lower())
    return out

def luokittele(it):
    t = []
    for k, rx in LUOK.items():
        otsikko_osumat = osumat(rx, it["o"])
        kuv_osumat = osumat(rx, it["k"])
        if otsikko_osumat or len(kuv_osumat) >= 2:
            t.append(k)
    # Viihde ei ole oikea paikka kovalle uutiselle: jos juttu on myös politiikkaa, taloutta tai rikosuutinen, viihdetunniste pois.
    if any(x.startswith(("politiikka/", "talous/", "yhteiskunta/rikokset")) for x in t):
        t = [x for x in t if not x.startswith("viihde/")]
    return t

def maakuntalehden_oma(it):
    """Maakuntalehti julkaisee myös valtakunnallisia STT-/Uutissuomalainen-juttuja: ne eivät ole paikallisia."""
    if "Uutissuomalainen" in it["o"] or "STT" in it.get("k", "")[:40]:
        return False
    return not any(x.startswith(("politiikka/", "talous/", "teknologia/")) for x in luokittele(it))

# Lähteet, joiden käyttöehdot kieltävät automaattisen keräyksen: ei koskaan mukaan (myöskään Googlen kautta)
ESTETYT = ("verkkouutiset",)
def estetty(it):
    return any(e in (it.get("s", "") + " " + it.get("h", "") + " " + it.get("l", "")).lower() for e in ESTETYT)

def suomalainen(it):
    h = it.get("h", "")
    return h.endswith((".fi", ".ax")) if h else False

def avain(v):
    return re.sub(r"[^a-z0-9äöå]+", "", v["o"].lower())

def esc(s):
    return html.escape(s or "", quote=True)

def hki(iso, muoto):
    return datetime.fromisoformat(iso).astimezone(HKI).strftime(muoto)

CSS = """:root{--bg:#0d1117;--card:#151b24;--fg:#e8edf3;--mute:#8d99a8;--line:#232c38;--acc:#ffc93c;--acct:#ffc93c;--hot:#ff5d5d;--chip:#1d2531}
@media (prefers-color-scheme:light){:root{--bg:#f3f4f6;--card:#fff;--fg:#11161d;--mute:#59636f;--line:#e0e4ea;--acc:#ffc93c;--acct:#8a5d00;--hot:#d63434;--chip:#eceff3}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif}
a{color:inherit}
.hd{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--line)}
@supports (backdrop-filter:blur(8px)){.hd{background:color-mix(in srgb,var(--bg) 86%,transparent);backdrop-filter:saturate(1.5) blur(14px);-webkit-backdrop-filter:saturate(1.5) blur(14px)}}
.hd-in{max-width:820px;margin:0 auto;display:flex;align-items:center;gap:8px;padding:10px 16px 4px}
.logo{display:flex;align-items:center;gap:8px;font-weight:800;font-size:1.15rem;letter-spacing:-.02em;text-decoration:none}
.pulse{width:9px;height:9px;border-radius:50%;background:var(--hot);animation:pl 2.2s infinite}
@keyframes pl{0%{box-shadow:0 0 0 0 rgba(255,93,93,.55)}70%{box-shadow:0 0 0 9px rgba(255,93,93,0)}100%{box-shadow:0 0 0 0 rgba(255,93,93,0)}}
@media (prefers-reduced-motion:reduce){.pulse{animation:none}}
.upd{font-size:12px;color:var(--mute);margin-right:auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ico{display:grid;place-items:center;flex:none;width:40px;height:40px;border-radius:12px;background:var(--chip);color:var(--fg);border:0;padding:0;cursor:pointer;text-decoration:none}
.ico svg{width:19px;height:19px}
.tabs{max-width:820px;margin:0 auto;display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;padding:0 10px}
.tabs::-webkit-scrollbar,.chips::-webkit-scrollbar{display:none}
.tabs,.chips{-webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 28px),transparent);mask-image:linear-gradient(90deg,#000 calc(100% - 28px),transparent)}
.tabs a{flex:none;padding:9px 9px 10px;font-size:14px;font-weight:650;color:var(--mute);text-decoration:none;border-bottom:3px solid transparent;white-space:nowrap}
.tabs a[aria-current]{color:var(--fg);border-bottom-color:var(--acc)}
main{max-width:820px;margin:0 auto;padding:4px 16px 0}
h1{font-size:1.45rem;line-height:1.15;letter-spacing:-.02em;margin:18px 0 4px}
h2{font-size:1.05rem;letter-spacing:-.01em;margin:26px 0 10px}
.sec-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin:28px 0 10px}
.sec-h h2{margin:0;display:flex;align-items:center;gap:8px}
.sec-h .sm{font-size:12.5px;color:var(--mute);text-align:right}
.sec-h .sm a{color:var(--acct);font-weight:700;text-decoration:none}
.lead{color:var(--mute);font-size:14px;margin:0 0 12px}
.stats{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 0;font-size:12.5px;color:var(--mute)}
.stats b{color:var(--fg)}
.stats span{background:var(--chip);border-radius:999px;padding:5px 10px}
.chips{display:flex;gap:8px;margin:6px -16px 14px;padding:0 16px;overflow-x:auto;scrollbar-width:none}
.chips a{flex:none;background:var(--chip);text-decoration:none;border-radius:999px;padding:8px 13px;font-size:13.5px;font-weight:650;white-space:nowrap}
.chips a[aria-current]{background:var(--acc);color:#111}
.story{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 14px 2px;margin:0 0 12px}
.story.iso{border-color:color-mix(in srgb,var(--hot) 45%,var(--line))}
.st-top{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--mute);margin-bottom:7px}
.hot{background:var(--hot);color:#fff;font-weight:800;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;border-radius:6px;padding:3px 7px}
.story .ot{display:block;font-size:1.13rem;line-height:1.28;font-weight:750;text-decoration:none;letter-spacing:-.01em}
.story.iso .ot{font-size:1.3rem}
.srcs{display:flex;flex-wrap:wrap;gap:6px;margin:11px 0 4px}
.src{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:650;white-space:nowrap}
.src::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--c,#888);flex:none}
.srcs .src{background:var(--chip);padding:4px 9px;border-radius:999px}
.srcs .plus{font-size:12px;color:var(--mute);padding:4px 2px;font-weight:650}
details.vrt{border-top:1px solid var(--line);margin-top:9px}
details.vrt summary{list-style:none;cursor:pointer;padding:11px 0;font-size:13.5px;font-weight:750;color:var(--acct);display:flex;justify-content:space-between;align-items:center}
details.vrt summary::-webkit-details-marker{display:none}
details.vrt summary::after{content:"";width:8px;height:8px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(45deg);margin:0 4px 4px 0;transition:transform .2s}
details.vrt[open] summary::after{transform:rotate(225deg);margin-bottom:-2px}
.vrt ol{list-style:none;margin:0;padding:0 0 10px}
.vrt li{padding:9px 0;border-top:1px dashed var(--line)}
.vrt li .mt{margin:0 0 3px}
.vrt li a{display:block;text-decoration:none;font-size:14.5px;line-height:1.35}
.ensin{font-size:10.5px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#111;background:var(--acc);border-radius:5px;padding:2px 6px}
.rows{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.row{display:grid;grid-template-columns:44px 1fr;gap:10px;padding:11px 14px;border-top:1px solid var(--line)}
.row:first-child{border-top:0}
.row>time{font-size:12.5px;font-weight:750;color:var(--mute);font-variant-numeric:tabular-nums;padding-top:2px;white-space:nowrap}
.row.uusi>time{color:var(--acct)}
.row.uusi>time::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--acc);margin-right:3px;vertical-align:2px}
.row .ot{display:block;text-decoration:none;font-weight:650;line-height:1.32}
.row .ot:visited,.story .ot:visited,.vrt a:visited{color:var(--mute)}
.row .kuv{font-size:13.5px;color:var(--mute);margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.mt{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;margin-top:5px;font-size:12px;color:var(--mute)}
.mm{font-weight:750;color:var(--acct)}
a.kesk{font-weight:750;color:var(--acct);text-decoration:none}
.paiva{font-size:11.5px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--mute);margin:22px 0 8px}
.jaa{flex:none;display:inline-flex;align-items:center;gap:5px;margin:-4px 0 -4px auto;padding:5px 11px 5px 9px;border:0;border-radius:999px;background:var(--chip);color:var(--fg);cursor:pointer;font:700 12.5px system-ui,sans-serif}
.jaa::after{content:"Jaa"}
.jaa::before{content:"";width:15px;height:15px;background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3v12'/%3E%3Cpath d='m7 8 5-5 5 5'/%3E%3Cpath d='M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3v12'/%3E%3Cpath d='m7 8 5-5 5 5'/%3E%3Cpath d='M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6'/%3E%3C/svg%3E") center/contain no-repeat}
.jaa:hover,.jaa:focus-visible{background:var(--acc);color:#111}
.st-top .jaa{margin:-4px 0 -4px auto}
#jako{position:fixed;inset:0;z-index:60;background:rgba(0,0,0,.5);display:flex;align-items:flex-end;justify-content:center}
#jako[hidden]{display:none}
.jako-in{background:var(--card);width:100%;max-width:520px;border-radius:18px 18px 0 0;padding:16px 16px calc(16px + env(safe-area-inset-bottom));border:1px solid var(--line)}
.jako-in p{margin:0 0 12px;font-weight:700;font-size:14.5px;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.jako-g{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.jako-g a,.jako-g button{display:flex;align-items:center;justify-content:center;gap:6px;background:var(--chip);color:var(--fg);border:0;border-radius:12px;padding:12px 6px;font:650 14px system-ui,sans-serif;text-decoration:none;cursor:pointer}
.jako-x{width:100%;margin-top:10px}
.jako-g .j-x{background:#000;color:#fff;border:1px solid #333}.jako-g .j-fb{background:#1877f2;color:#fff}.jako-g .j-wa{background:#25d366;color:#06321a}.jako-g .j-tg{background:#2aabee;color:#fff}.jako-g .j-li{background:#0a66c2;color:#fff}
.jako-g a,.jako-g button{font-weight:800}
.jako-kop{display:block;width:100%;margin:0 0 8px;padding:14px;font-size:15.5px}
.tile.laaja{grid-column:1/-1;min-height:0;border-color:color-mix(in srgb,var(--acc) 45%,var(--line))}
.oma-alue{display:block;text-align:center;margin:4px 0 6px}.oma-alue[hidden]{display:none}
.asenna{display:block;width:100%;margin:14px 0 0}.asenna[hidden],.asenna-ios[hidden]{display:none}.asenna-ios{margin:12px 0 0}
.more{display:block;text-align:center;padding:13px;font-weight:750;font-size:14px;color:var(--acct);text-decoration:none;border-top:1px solid var(--line)}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;text-decoration:none;display:flex;flex-direction:column;gap:4px;min-height:120px}
.tile b{font-size:15px;letter-spacing:-.01em}
.tile .tc{font-size:12px;color:var(--acct);font-weight:750}
.tile .th{font-size:13px;color:var(--mute);line-height:1.3;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
@media (min-width:700px){.tiles{grid-template-columns:repeat(4,1fr)}}
#haku{position:fixed;inset:0;z-index:50;background:var(--bg);overflow:auto}
#haku[hidden]{display:none}
.haku-in{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line)}
.haku-in div{display:flex;gap:8px;padding:12px 16px;max-width:820px;margin:0 auto}
.haku-in input{flex:1;min-width:0;font:16px system-ui,sans-serif;padding:11px 14px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
#hakuTulos{max-width:820px;margin:0 auto;padding:12px 16px 40px}
footer{max-width:820px;margin:0 auto;padding:34px 16px 60px;font-size:12px;line-height:1.6;color:var(--mute)}
footer a{color:var(--mute)}
.item{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:0 0 10px}
.item a{text-decoration:none;font-weight:650;display:block}
.kuv{color:var(--mute);font-size:.93rem;margin-top:4px}
.meta{font-size:12.5px;color:var(--mute);margin-top:6px}
.btn,button{background:var(--acc);color:#111;border:0;border-radius:10px;padding:10px 14px;font:650 15px system-ui,sans-serif;cursor:pointer;text-decoration:none}
button.pieni{padding:3px 9px;font-size:12px;margin-left:4px}
.sec{background:var(--chip);color:var(--fg)}
textarea,input[type=email]{font-family:inherit}
fieldset{border:1px solid var(--line);border-radius:12px;margin:0 0 10px;padding:8px 12px}
legend{font-weight:700;font-size:15px;padding:0 6px}
label{display:flex;gap:8px;align-items:center;font-size:15px;line-height:1.3;padding:6px 0}
input[type=checkbox]{width:20px;height:20px;accent-color:var(--acc)}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}"""

# Sivun yhteinen skripti: suhteelliset ajat, UUSI-merkit (edellisestä käynnistä), haku. Ei f-merkkijono.
JS = r"""<script>
(function(){
var K="uv_viime",nyt=Date.now(),viime=0;try{viime=+localStorage.getItem(K)||0}catch(e){}
function rel(iso){var s=(nyt-Date.parse(iso))/1000;if(s<90)return"juuri nyt";if(s<3600)return Math.round(s/60)+" min sitten";if(s<86400)return Math.floor(s/3600)+" t sitten";var d=new Date(iso);return d.getDate()+"."+(d.getMonth()+1)+".";}
document.querySelectorAll("[data-rel]").forEach(function(e){e.textContent=(e.dataset.pre||"")+rel(e.dataset.rel)});
if(viime)document.querySelectorAll(".row[data-a]").forEach(function(e){if(Date.parse(e.dataset.a)>viime)e.classList.add("uusi")});
setTimeout(function(){try{localStorage.setItem(K,String(nyt))}catch(e){}},5000);
function vari(s){var h=0;for(var i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))%360;return"hsl("+h+" 70% 55%)"}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
var H=document.getElementById("haku"),I=document.getElementById("hakuIn"),T=document.getElementById("hakuTulos"),data=null;
try{var OA=JSON.parse(localStorage.getItem("uv_alue")||"null");if(OA){var pt=document.getElementById("paikTile");if(pt){pt.href=pt.dataset.base+OA[0]+"/";document.getElementById("paikTc").textContent="Oma alueesi: "+OA[1]+" →"}
 var oa=document.getElementById("omaAlue");if(oa){oa.href=OA[0]+"/";oa.textContent="Oma alueesi: "+OA[1]+" →";oa.hidden=false}}}catch(e){}
var CC=document.querySelector(".chips a[aria-current]");if(CC){var CP=CC.parentNode;CP.scrollLeft=CC.offsetLeft-CP.clientWidth/2+CC.clientWidth/2}
function kopioi(u,b){function ok(){b.textContent="Linkki kopioitu ✓"}
 function vara(){var t=document.createElement("textarea");t.value=u;t.setAttribute("readonly","");t.style.position="fixed";t.style.opacity="0";document.body.appendChild(t);t.select();t.setSelectionRange(0,u.length);var r=false;try{r=document.execCommand("copy")}catch(x){}document.body.removeChild(t);if(r)ok();else b.textContent=u}
 try{if(navigator.clipboard&&window.isSecureContext)navigator.clipboard.writeText(u).then(ok,vara);else vara()}catch(x){vara()}}
function jaa(u,o){
 u=String(u).replace(/[?&](origin|utm_[a-z]+)=[^&#]*/g,"").replace(/&$/,"");
 var J=document.getElementById("jako");
 if(!J){J=document.createElement("div");J.id="jako";J.hidden=true;document.body.appendChild(J);J.addEventListener("click",function(e){if(e.target===J||e.target.classList.contains("jako-x"))J.hidden=true})}
 var e=encodeURIComponent,uu=e(u),oo=e(o);
 J.innerHTML='<div class="jako-in" role="dialog" aria-label="Jaa uutinen"><p>'+esc(o)+'</p>'
  +'<button type="button" class="jako-kop" id="jakoKop">Kopioi linkki</button><div class="jako-g">'
  +'<a class="j-x" target="_blank" rel="noopener" href="https://x.com/intent/post?text='+oo+'&url='+uu+'">X</a>'
  +'<a class="j-fb" target="_blank" rel="noopener" href="https://www.facebook.com/sharer/sharer.php?u='+uu+'">Facebook</a>'
  +'<a class="j-wa" target="_blank" rel="noopener" href="https://wa.me/?text='+e(o+" "+u)+'">WhatsApp</a>'
  +'<a class="j-tg" target="_blank" rel="noopener" href="https://t.me/share/url?url='+uu+'&text='+oo+'">Telegram</a>'
  +'<a class="j-li" target="_blank" rel="noopener" href="https://www.linkedin.com/sharing/share-offsite/?url='+uu+'">LinkedIn</a>'
  +(navigator.share?'<button type="button" id="jakoMuu">Muut sovellukset…</button>':'<a href="mailto:?subject='+oo+'&body='+e(o+"\n"+u)+'">Sähköposti</a>')
  +'</div><button type="button" class="sec jako-x">Sulje</button></div>';
 J.hidden=false;
 document.getElementById("jakoKop").onclick=function(){kopioi(u,this)};
 var m=document.getElementById("jakoMuu");if(m)m.onclick=function(){navigator.share({title:o,text:o,url:u}).then(function(){J.hidden=true}).catch(function(){})};
}
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".jaa");if(b){e.preventDefault();jaa(b.dataset.u,b.dataset.o)}});
document.addEventListener("keydown",function(e){var J=document.getElementById("jako");if(e.key==="Escape"&&J&&!J.hidden)J.hidden=true});
var M=document.querySelector('link[rel=manifest]');
if(M&&"serviceWorker" in navigator){try{navigator.serviceWorker.register(M.href.replace("manifest.webmanifest","sw.js"))}catch(e){}}
var A=document.getElementById("asenna"),ip=null;
window.addEventListener("beforeinstallprompt",function(e){e.preventDefault();ip=e;if(A)A.hidden=false});
if(A)A.onclick=function(){if(!ip)return;ip.prompt();ip.userChoice.then(function(){A.hidden=true;ip=null})};var AI=document.getElementById("asennaIos");if(AI&&/iphone|ipad|ipod/i.test(navigator.userAgent)&&!navigator.standalone)AI.hidden=false;
if(!H)return;
function hae(){if(!data)return;var q=I.value.toLowerCase().trim();
 if(q.length<2){T.innerHTML='<p class="lead">Hae kaikista uutisista kahden viikon ajalta. Esim. <b>kokoomus maahanmuutto</b> tai <b>sähkön hinta</b>.</p>';return}
 var w=q.split(/\s+/),r=[];for(var i=0;i<data.length&&r.length<120;i++){var u=data[i],t=(u.o+" "+u.k+" "+u.s).toLowerCase();if(w.every(function(x){return t.indexOf(x)>=0}))r.push(u)}
 T.innerHTML='<p class="lead">'+(r.length>=120?"Yli 120":r.length)+' osumaa</p>'+(r.length?'<div class="rows">'+r.map(function(u){var d=new Date(u.a);return'<article class="row"><time>'+d.getDate()+"."+(d.getMonth()+1)+'.</time><div><a class="ot" href="'+esc(u.l)+'" target="_blank" rel="noopener">'+esc(u.o)+'</a><div class="mt"><span class="src" style="--c:'+vari(u.s)+'">'+esc(u.s)+'</span><button class="jaa" type="button" data-u="'+esc(u.l)+'" data-o="'+esc(u.o)+'" aria-label="Jaa uutinen"></button></div></div></article>'}).join("")+'</div>':"")}
function avaa(){H.hidden=false;document.body.style.overflow="hidden";setTimeout(function(){I.focus()},30);
 if(!data){T.innerHTML='<p class="lead">Ladataan…</p>';fetch(H.dataset.feed).then(function(r){return r.json()}).then(function(d){data=d.u;hae()}).catch(function(){T.innerHTML='<p class="lead">Haku ei juuri nyt toimi. Yritä hetken päästä uudelleen.</p>'})}}
function sulje(){H.hidden=true;document.body.style.overflow=""}
document.getElementById("hakuBtn").onclick=avaa;document.getElementById("hakuX").onclick=sulje;
document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!H.hidden)sulje();if(e.key==="/"&&H.hidden&&!/INPUT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();avaa()}});
var tm;I.addEventListener("input",function(){clearTimeout(tm);tm=setTimeout(hae,120)});
})();
</script>"""

IKONI_HAKU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'
IKONI_OMA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z"/></svg>'
PAIVITETTY = ""

def vari(s):
    h = 0
    for c in s:
        h = (h * 31 + ord(c)) % 360
    return f"hsl({h} 70% 55%)"

def lahde(s):
    return f'<span class="src" style="--c:{vari(s)}">{esc(s)}</span>'

def rel(d):
    return "../" * d if d else "./"

def sivu(otsikko, kuvaus, polku, syvyys, runko, jsonld=None, aktiivinen=None, noindex=False):
    r = rel(syvyys)
    nav = f'<a href="{r}"{" aria-current=page" if aktiivinen == "etusivu" else ""}>Etusivu</a>'
    nav += "".join(f'<a href="{r}{p}/"{" aria-current=page" if p == aktiivinen else ""}>{esc(v["nimi"])}</a>' for p, v in AIHEET.items())
    nav += f'<a href="{r}oma/"{" aria-current=page" if aktiivinen == "oma" else ""}>Oma syöte</a>'
    kanon = f"{BASE}/{polku}" if polku else f"{BASE}/"
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")}</script>' if jsonld else ""
    upd = f'<span class="upd" data-rel="{PAIVITETTY}" data-pre="Päivitetty ">Päivitetty {hki(PAIVITETTY, "klo %H.%M")}</span>' if PAIVITETTY else '<span class="upd"></span>'
    return f"""<!doctype html>
<html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(otsikko)}</title>
<meta name="description" content="{esc(kuvaus)}">
<meta name="theme-color" content="#0d1117" media="(prefers-color-scheme: dark)"><meta name="theme-color" content="#f3f4f6" media="(prefers-color-scheme: light)">
<link rel="canonical" href="{kanon}">
<link rel="manifest" href="{r}manifest.webmanifest"><link rel="icon" type="image/png" href="{r}favicon.png"><link rel="apple-touch-icon" href="{r}apple-touch-icon.png"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="{esc(SITE)}">
<meta property="og:title" content="{esc(otsikko)}"><meta property="og:description" content="{esc(kuvaus)}"><meta property="og:type" content="website"><meta property="og:locale" content="fi_FI"><meta property="og:url" content="{kanon}">
<meta name="robots" content="{"noindex,nofollow" if noindex else "index,follow,max-snippet:-1"}">
{ld}<style>{CSS}</style><script src="{r}config.js"></script><script src="{r}tuki.js"></script></head><body>
<header class="hd"><div class="hd-in"><a class="logo" href="{r}"><span class="pulse" aria-hidden="true"></span>{esc(SITE)}</a>{upd}<button class="ico" id="hakuBtn" type="button" aria-label="Hae uutisia">{IKONI_HAKU}</button><a class="ico" href="{r}oma/" aria-label="Oma syöte">{IKONI_OMA}</a></div>
<nav class="tabs" aria-label="Aiheet">{nav}</nav></header>
<div id="haku" hidden data-feed="{r}feed.json"><div class="haku-in"><div><input id="hakuIn" type="search" placeholder="Hae uutisia…" aria-label="Hakusana" autocomplete="off"><button class="sec" id="hakuX" type="button">Sulje</button></div></div><div id="hakuTulos"></div></div>
<main>
{runko}
</main>
<footer><p>{esc(SITE)} kokoaa suomalaisten medioiden uutisotsikot yhteen paikkaan noin 10 minuutin välein. Saman tapahtuman uutiset eri medioista ryhmitellään automaattisesti, jotta näet yhdellä silmäyksellä, mistä puhutaan ja miten eri mediat asian otsikoivat. Sivusto näyttää vain otsikon, lyhyen ingressin ja lähteen; jutut luetaan lähteen omalla sivulla. Aiheet ja ryhmät tunnistetaan automaattisesti, joten ne voivat joskus olla epätarkkoja.</p><p><a href="https://eduskuntaseuranta.fi/" rel="noopener">Eduskuntaseuranta</a> · <a href="{r}saannot/">Keskustelusäännöt</a> · <a href="{r}tietosuoja/">Tietosuoja</a></p></footer>
{JS}
<!-- Cloudflare Web Analytics (evästeetön) --><script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "6b71f4e21fa24282bc0932cdcb3c1b51"}}'></script>
</body></html>"""

def kesk(u, r):
    if not KESKUSTELU:
        return ""
    return f'<a class="kesk" data-id="{u["i"]}" href="{r}keskustelu/?i={u["i"]}">Keskustele</a>'

EDUSKUNTA_LAATIKKO = ('<a class="tile laaja" href="https://eduskuntaseuranta.fi/aanestykset/" rel="noopener" style="margin:0 0 14px">'
    '<b>Miten kansanedustajat äänestivät?</b><span class="th">Jokainen eduskunnan äänestys, edustaja ja puolue avoimesta datasta: eduskuntaseuranta.fi</span></a>')

RYHMA_N = {}     # uutisen tunnus -> montako mediaa samassa ryhmässä
TANAAN = ""

def jaa_nappi(u):
    return f'<button class="jaa" type="button" data-u="{esc(u["l"])}" data-o="{esc(u["o"])}" aria-label="Jaa uutinen"></button>'

def rivi(u, r, kuv=True):
    t = hki(u["a"], "%H.%M") if hki(u["a"], "%Y-%m-%d") == TANAAN else hki(u["a"], "%-d.%-m.")
    k = f'<div class="kuv">{esc(lyhyt(u["k"]))}</div>' if kuv and u["k"] and u["k"] != u["o"] else ""
    n = RYHMA_N.get(u.get("i"), 1)
    mm = f'<span class="mm">{n} mediaa</span>' if n > 1 else ""
    return (f'<article class="row" data-a="{u["a"]}"><time datetime="{u["a"]}">{t}</time><div>'
            f'<a class="ot" href="{esc(u["l"])}" rel="noopener" target="_blank">{esc(u["o"])}</a>{k}'
            f'<div class="mt">{lahde(u["s"])}{mm}{kesk(u, r)}{jaa_nappi(u)}</div></div></article>')

def lista_html(items, ryhmittele=True, r="./", kuv=True):
    if not items:
        return '<p class="lead">Ei uutisia juuri nyt. Sivu päivittyy noin 10 minuutin välein.</p>'
    if not ryhmittele:
        return '<div class="rows">' + "".join(rivi(u, r, kuv) for u in items) + '</div>'
    out, pv, auki = [], "", False
    for u in items:
        p = hki(u["a"], "%Y-%m-%d")
        if p != pv:
            if auki:
                out.append("</div>")
            nimi = "Tänään" if p == TANAAN else hki(u["a"], "%A %-d.%-m.").replace("Monday", "Maanantai").replace("Tuesday", "Tiistai").replace("Wednesday", "Keskiviikko").replace("Thursday", "Torstai").replace("Friday", "Perjantai").replace("Saturday", "Lauantai").replace("Sunday", "Sunnuntai")
            out.append(f'<div class="paiva">{nimi}</div><div class="rows">')
            pv, auki = p, True
        out.append(rivi(u, r, kuv))
    if auki:
        out.append("</div>")
    return "\n".join(out)

ENSISIJAISET = ["Yle", "STT Info", "Helsingin Sanomat", "MTV Uutiset", "Ilta-Sanomat", "Iltalehti"]

def tarina_html(g, r, iso=False):
    """Yksi 'Nyt puhutaan' -kortti: sama tapahtuma monesta mediasta + vertailu otsikoista."""
    md = mediat(g)
    paa = next((u for s_ in ENSISIJAISET for u in sorted(g, key=lambda x: x["a"]) if u["s"] == s_), sorted(g, key=lambda x: x["a"])[0])
    uusin = max(u["a"] for u in g)
    chips = "".join(lahde(x) for x in md[:6]) + (f'<span class="plus">+{len(md) - 6}</span>' if len(md) > 6 else "")
    nahty, rivit = set(), []
    for i, u in enumerate(sorted(g, key=lambda x: x["a"])):
        if u["l"] in nahty:
            continue
        nahty.add(u["l"])
        ens = '<span class="ensin">Ensin</span>' if not rivit else ""
        rivit.append(f'<li><div class="mt">{lahde(u["s"])}<span>{hki(u["a"], "%-d.%-m. klo %H.%M")}</span>{ens}</div><a href="{esc(u["l"])}" rel="noopener" target="_blank">{esc(u["o"])}</a></li>')
    return (f'<article class="story{" iso" if iso else ""}"><div class="st-top"><span class="hot">{len(md)} mediaa</span>'
            f'<span data-rel="{uusin}">{hki(uusin, "klo %H.%M")}</span>{jaa_nappi(dict(paa, o=puhdas_otsikko(paa["o"])))}</div>'
            f'<a class="ot" href="{esc(paa["l"])}" rel="noopener" target="_blank">{esc(puhdas_otsikko(paa["o"]))}</a>'
            f'<div class="srcs">{chips}</div>'
            f'<details class="vrt"><summary>Näin mediat otsikoivat ({len(rivit)})</summary><ol>{"".join(rivit)}</ol></details></article>')

def itemlist_ld(nimi, items, polku):
    return {"@context": "https://schema.org", "@type": "CollectionPage", "name": nimi, "url": f"{BASE}/{polku}", "inLanguage": "fi",
            "mainEntity": {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": u["l"], "name": u["o"]} for i, u in enumerate(items[:20])]}}

def kirjoita(polku, sisalto):
    p = os.path.join(DIR, polku)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(sisalto)

def rakenna(items, paivitetty):
    for u in items:
        u["i"] = tunnus(u["l"])
    por = {}
    for u in items:
        for t in u["t"]:
            por.setdefault(t, []).append(u)
    urls = [("", paivitetty)]
    global PAIVITETTY, TANAAN
    PAIVITETTY = paivitetty
    TANAAN = hki(paivitetty, "%Y-%m-%d")
    nyt = datetime.fromisoformat(paivitetty)
    def ika_h(iso):
        return (nyt - datetime.fromisoformat(iso)).total_seconds() / 3600
    # saman tapahtuman ryhmät (vain viimeiset 3 vrk, nopeus)
    tuore = [u for u in items if ika_h(u["a"]) <= 72]
    ryhmat = ryhmittele(tuore)
    RYHMA_N.clear()
    for g in ryhmat:
        n = len(mediat(g))
        for u in g:
            RYHMA_N[u["i"]] = n
    ryhma_of = {u["i"]: g for g in ryhmat for u in g}
    def kuumat(ehto=lambda g: True, max_h=24, kpl=7):
        ehd = [g for g in ryhmat if len(mediat(g)) >= 2 and ika_h(max(u["a"] for u in g)) <= max_h and ehto(g)]
        ehd.sort(key=lambda g: -len(mediat(g)) / (1 + ika_h(max(u["a"] for u in g)) / 8))
        return ehd[:kpl]
    def tuoreimmat(lista, kpl):
        out, nahty = [], set()
        for u in lista:
            g = ryhma_of.get(u["i"])
            gid = id(g) if g else u["i"]
            if gid in nahty:
                continue
            nahty.add(gid)
            out.append(u)
            if len(out) >= kpl:
                break
        return out

    # ---- etusivu ----
    vrk = [u for u in items if ika_h(u["a"]) <= 24]
    hot = kuumat()
    runko = (f'<h1>Suomen uutiset yhdessä paikassa</h1>'
             f'<div class="stats"><span><b>{len(vrk)}</b> uutista vuorokaudessa</span><span><b>{len({u["s"] for u in vrk})}</b> mediaa</span><span>päivittyy <b>10 min</b> välein</span></div>'
             '<button class="btn asenna" id="asenna" type="button" hidden>Asenna sovellukseksi puhelimeen</button>'
             '<p class="sm asenna-ios" id="asennaIos" hidden>📱 Sovellukseksi iPhoneen: paina Safarin <b>Jaa</b>-painiketta ja valitse <b>Lisää Koti-valikkoon</b>.</p>')
    if hot:
        runko += '<div class="sec-h"><h2><span class="pulse" aria-hidden="true"></span>Nyt puhutaan</h2><span class="sm">Sama uutinen monessa mediassa</span></div>'
        runko += "".join(tarina_html(g, "./", iso=(i == 0)) for i, g in enumerate(hot))
    runko += '<div class="sec-h"><h2>Tuoreimmat</h2><span class="sm"><a href="#aiheet">Aiheittain ↓</a></span></div>'
    runko += lista_html(tuoreimmat(items, 30), False, "./", kuv=False)
    muualla = muissa_medioissa(tuore)
    yksi = [u for u in vrk if RYHMA_N.get(u["i"], 1) == 1 and u["i"] not in muualla and any(t.startswith(("politiikka/", "yhteiskunta/")) for t in u["t"])][:8]
    if yksi:
        runko += '<div class="sec-h"><h2>Vain yksi media kertoi</h2><span class="sm">Politiikka ja yhteiskunta, 24 h</span></div>'
        runko += '<p class="lead">Uutisia, joista vain yksi media on kirjoittanut viimeisen vuorokauden aikana. Täältä löytyy se, mikä muualla jää huomaamatta.</p>'
        runko += lista_html(yksi, False, "./")
    tiles = ""
    for p, pv in AIHEET.items():
        yl = [u for u in items if any(t.startswith(p + "/") for t in u["t"])]
        n24 = sum(1 for u in yl if ika_h(u["a"]) <= 24)
        th = esc(yl[0]["o"]) if yl else ""
        if p == "paikalliset":
            tiles = (f'<a class="tile laaja" id="paikTile" href="{p}/" data-base="{p}/"><b>Paikalliset uutiset</b>'
                     f'<span class="tc" id="paikTc">{len(pv["ala"])} maakuntaa · valitse oma alueesi</span><span class="th">{th}</span></a>') + tiles
            continue
        tiles += f'<a class="tile" href="{p}/"><b>{esc(pv["nimi"])}</b><span class="tc">{n24} uutista tänään</span><span class="th">{th}</span></a>'
    tiles += ('<a class="tile laaja" href="https://eduskuntaseuranta.fi/" rel="noopener"><b>Eduskuntaseuranta: miten päättäjät äänestivät?</b>'
              '<span class="th">Äänestykset, viranomaisten tiedotteet ja hankinnat. Tilaa ilmainen hälytys omasta aiheestasi sähköpostiin.</span></a>')
    runko += f'<div class="sec-h" id="aiheet"><h2>Aiheet</h2><span class="sm"><a href="oma/">Rakenna oma syöte →</a></span></div><div class="tiles">{tiles}</div>'
    kirjoita("index.html", sivu(f"{SITE}: Suomen uutiset yhdessä paikassa", "Suomalaisten medioiden uutiset yhdessä paikassa: näe mistä nyt puhutaan, miten eri mediat otsikoivat saman uutisen ja mitkä uutiset vain yksi media kertoi. Päivittyy 10 minuutin välein.", "", 0, runko, {"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": BASE + "/", "inLanguage": "fi"}, "etusivu"))

    # ---- aihe- ja alaaihesivut ----
    for p, pv in AIHEET.items():
        yl = [u for u in items if any(t.startswith(p + "/") for t in u["t"])][:120]
        chips = "".join(f'<a href="{a}/">{esc(av["nimi"])}</a>' for a, av in pv["ala"].items())
        h = kuumat(lambda g: any(t.startswith(p + "/") for u in g for t in u["t"]), 48, 3)
        runko = f'<h1>{esc(pv["nimi"])}</h1><p class="lead">{esc(pv["kuvaus"])}</p><div class="chips">{chips}</div>'
        if p == "politiikka":
            runko += EDUSKUNTA_LAATIKKO
        if p == "paikalliset":
            runko += '<a class="btn oma-alue" id="omaAlue" data-base="" href="#" hidden></a>'
        if h:
            runko += f'<div class="sec-h"><h2><span class="pulse" aria-hidden="true"></span>Nyt puhutaan</h2><span class="sm">{esc(pv["nimi"])}</span></div>' + "".join(tarina_html(g, "../") for g in h)
            runko += '<div class="sec-h"><h2>Kaikki uutiset</h2></div>'
        runko += lista_html(yl, True, "../")
        kirjoita(f"{p}/index.html", sivu(f"{pv['nimi']}: uusimmat uutiset | {SITE}", pv["kuvaus"], f"{p}/", 1, runko, itemlist_ld(pv["nimi"], yl, f"{p}/"), p))
        urls.append((f"{p}/", paivitetty))
        for a, av in pv["ala"].items():
            yl = por.get(f"{p}/{a}", [])[:120]
            chips = "".join(f'<a href="../{b}/"{" aria-current=page" if b == a else ""}>{esc(bv["nimi"])}</a>' for b, bv in pv["ala"].items())
            kuv = f'{av["nimi"]}: uusimmat suomalaiset uutiset yhdessä paikassa. {pv["nimi"]}.'
            h = kuumat(lambda g: any(t == f"{p}/{a}" for u in g for t in u["t"]), 48, 3)
            runko = f'<h1>{esc(av["nimi"])}</h1><p class="lead">{esc(pv["nimi"])} · {len(yl)} uutista viimeisen {SAILYTYS_PV} päivän ajalta</p><div class="chips">{chips}</div>'
            if p == "paikalliset":
                runko += f'<script>try{{localStorage.setItem("uv_alue",JSON.stringify(["{a}",{json.dumps(av["nimi"], ensure_ascii=False)}]))}}catch(e){{}}</script>'
            if h:
                runko += '<div class="sec-h"><h2><span class="pulse" aria-hidden="true"></span>Nyt puhutaan</h2></div>' + "".join(tarina_html(g, "../../") for g in h)
                runko += '<div class="sec-h"><h2>Kaikki uutiset</h2></div>'
            runko += lista_html(yl, True, "../../")
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
const vari=s=>{{let h=0;for(let i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))%360;return "hsl("+h+" 70% 55%)"}};
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
  if(p!==pv){{out+=(pv?'</div>':'')+'<div class="paiva">'+p+'</div><div class="rows">';pv=p}}
  const k=u.k&&u.k!==u.o?'<div class="kuv">'+esc(u.k)+'</div>':"";
  const t=new Date(u.a).toLocaleTimeString("fi-FI",{{timeZone:"Europe/Helsinki",hour:"2-digit",minute:"2-digit"}});
  out+='<article class="row" data-a="'+u.a+'"><time>'+t+'</time><div><a class="ot" href="'+esc(u.l)+'" rel="noopener" target="_blank">'+esc(u.o)+'</a>'+k+'<div class="mt"><span class="src" style="--c:'+vari(u.s)+'">'+esc(u.s)+'</span>'+(window.KOOSTE&&KOOSTE.on&&u.i?'<a class="kesk" data-id="'+u.i+'" href="../keskustelu/?i='+u.i+'">Keskustele</a>':'')+'<button class="jaa" type="button" data-u="'+esc(u.l)+'" data-o="'+esc(u.o)+'" aria-label="Jaa uutinen"></button></div></div></article>';}}
 $("syote").innerHTML=out+(pv?'</div>':'');if(window.KOOSTE)KOOSTE.maarat();}}
$("kaikki").onclick=()=>{{Object.entries(PUU).forEach(([p,v])=>Object.keys(v.ala).forEach(a=>valitut.add(p+"/"+a)));muutos()}};
$("tyhjenna").onclick=()=>{{valitut.clear();muutos()}};
$("jaa").onclick=()=>{{const u=location.href.split("#")[0]+"#a="+[...valitut].join(",");try{{navigator.clipboard.writeText(u);$("tila").textContent="Linkki kopioitu."}}catch(e){{$("tila").textContent=u}}}};
piirraValinta();
fetch("../feed.json").then(r=>r.json()).then(d=>{{data=d.u;piirraSyote()}}).catch(()=>{{$("tila").textContent="Uutisten lataus epäonnistui. Yritä hetken kuluttua uudelleen."}});
</script>"""
    kirjoita("oma/index.html", sivu(f"Oma syöte: valitse itse aiheet | {SITE}", "Rakenna oma uutissyöte: valitse politiikka-, talous-, lifestyle- ja muista aiheista ne alaaiheet, jotka kiinnostavat sinua.", "oma/", 1, oma, None, "oma"))
    urls.append(("oma/", paivitetty))
    # Keskustelu: config, keskustelu- ja moderointisivu, säännöt, tietosuoja
    kirjoita("config.js", "window.KOOSTE_CONF=" + (json.dumps({"url": SB_URL, "key": SB_KEY}) if KESKUSTELU else "{}") + ";\n")
    kirjoita("keskustelu/index.html", sivu(f"Keskustelu | {SITE}", "Keskustele uutisesta.", "keskustelu/", 1, '<div id="app"><p class="lead">Ladataan…</p></div><script src="../keskustelu.js"></script>', noindex=True))
    kirjoita("moderointi/index.html", sivu(f"Moderointi | {SITE}", "Ylläpitäjän näkymä.", "moderointi/", 1, '<h1>Moderointi</h1><div id="app"><p class="lead">Ladataan…</p></div><script src="../moderointi.js"></script>', noindex=True))
    saannot = f"""<h1>Keskustelusäännöt</h1>
<p class="lead">Nämä säännöt koskevat kaikkia {esc(SITE)}-palvelun kommentteja.</p>
<h2>Perusasiat</h2>
<p>Kommentit voi lukea ilman kirjautumista. Kommentointi vaatii kirjautumisen sähköpostilinkillä ja nimimerkin. Kommentit julkaistaan heti ilman etukäteistarkastusta. Jokainen vastaa itse kirjoittamastaan.</p>
<h2>Mitä ei saa kirjoittaa</h2>
<p>Kommentteja, jotka ovat selvästi laittomia, poistetaan. Tällaisia ovat esimerkiksi kunnianloukkaus, uhkaukset, kiihottaminen kansanryhmää vastaan, toisen henkilötietojen paljastaminen ja rikoksiin yllyttäminen. Myös roskaposti ja mainonta poistetaan.</p>
<h2>Ilmianna kommentti</h2>
<p>Jokaisen kommentin vieressä on Ilmianna-nappi. Ilmoitukset menevät ylläpitäjälle, joka tarkistaa ne ja poistaa selvästi laittomat kommentit. Mielipide, josta olet eri mieltä, ei ole sellaisenaan syy poistoon.</p>
<h2>Oma kommentti</h2>
<p>Voit poistaa oman kommenttisi milloin tahansa. Kommenttia ei voi muokata, mutta sen voi poistaa ja kirjoittaa uudelleen.</p>
<h2>Ylläpito</h2>
<p>{esc(YLLAPITAJA)}. Yhteys: {esc(YHTEYS)}</p>"""
    kirjoita("saannot/index.html", sivu(f"Keskustelusäännöt | {SITE}", "Keskustelun säännöt, kommenttien poisto ja ilmiannot.", "saannot/", 1, saannot))
    tieto = f"""<h1>Tietosuojaseloste</h1>
<p class="lead">Luonnos. Täydennä ylläpitäjän tiedot ja tarkistuta tarvittaessa asiantuntijalla ennen julkaisua.</p>
<h2>Rekisterinpitäjä</h2><p>{esc(YLLAPITAJA)}. Yhteys: {esc(YHTEYS)}</p>
<h2>Mitä tietoja kerätään</h2>
<p>Uutisten lukeminen ei vaadi kirjautumista, eikä silloin kerätä henkilötietoja. Kun kirjaudut keskustelemaan, tallennamme sähköpostiosoitteesi (kirjautumista varten), valitsemasi nimimerkin ja kirjoittamasi kommentit aikaleimoineen. Ilmiannoista tallennetaan ilmiantajan tunniste ja kirjoittamasi syy.</p>
<h2>Mihin tietoja käytetään</h2>
<p>Sähköpostiosoitetta käytetään vain kirjautumiseen ja palvelun turvallisuuteen. Nimimerkki ja kommentit näkyvät julkisesti. Sähköpostiosoitettasi ei näytetä muille eikä luovuteta eteenpäin.</p>
<h2>Käsittelyn peruste ja säilytys</h2>
<p>Käsittely perustuu suostumukseesi, kun kirjaudut palveluun. Tietoja säilytetään, kunnes poistat kommenttisi tai pyydät tilisi poistamista. Voit pyytää tietojesi tarkastamista tai poistamista ottamalla yhteyttä ylläpitäjään.</p>
<h2>Tietojen sijainti</h2>
<p>Käyttäjätiedot ja kommentit tallennetaan Supabase-palveluun. Sivusto on julkaistu GitHub Pagesissa. Palveluntarjoajat voivat käsitellä tietoja EU:n ulkopuolella, mikä perustuu niiden omiin sopimusehtoihin.</p>
<h2>Evästeet ja selaimen tallennus</h2>
<p>Palvelu tallentaa selaimeesi kirjautumistiedon ja Oma syöte -valinnat. Mainos- tai seurantaevästeitä ei käytetä.</p>"""
    kirjoita("tietosuoja/index.html", sivu(f"Tietosuojaseloste | {SITE}", "Mitä tietoja palvelu kerää ja miten niitä käytetään.", "tietosuoja/", 1, tieto))
    urls.append(("saannot/", paivitetty)); urls.append(("tietosuoja/", paivitetty))
    kirjoita("feed.json", json.dumps({"p": paivitetty, "u": [{"i": u["i"], "o": u["o"], "l": u["l"], "s": u["s"], "a": u["a"], "k": u["k"], "t": u["t"]} for u in items[:2500]]}, ensure_ascii=False, separators=(",", ":")))
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{BASE}/{p}</loc><lastmod>{m[:10]}</lastmod></url>\n" for p, m in urls) + "</urlset>\n"
    kirjoita("sitemap.xml", sm)
    kirjoita("manifest.webmanifest", json.dumps({"name": SITE, "short_name": "Nyt puhutaan", "description": "Suomen uutiset yhdessä paikassa: mistä nyt puhutaan ja miten eri mediat sen otsikoivat.",
        "lang": "fi", "start_url": "./", "scope": "./", "display": "standalone", "background_color": "#0d1117", "theme_color": "#0d1117",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, ensure_ascii=False, indent=1))
    kirjoita("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /vahti/\nDisallow: /tila/\n\nSitemap: {BASE}/sitemap.xml\n")
    # vanhat osoitteet (miksu900.github.io/uutisvahti/kooste/...) ohjautuvat uuteen polkuun
    kirjoita("404.html", '<!doctype html><html lang="fi"><head><meta charset="utf-8"><title>Sivua ei löytynyt</title><meta name="robots" content="noindex">'
        '<script>var p=location.pathname;if(/^\\/(uutisvahti\\/)?kooste(\\/|$)/.test(p)){location.replace(p.replace(/^\\/(uutisvahti\\/)?kooste/,"")||"/")}</script></head>'
        '<body style="font-family:system-ui;background:#0d1117;color:#e8edf3;text-align:center;padding:60px 16px"><h1>Sivua ei löytynyt</h1><p><a style="color:#ffc93c" href="/">Etusivulle</a></p></body></html>')

def main():
    nyt = datetime.now(timezone.utc)
    try:
        vanha = json.load(open(os.path.join(DIR, "data.json"), encoding="utf-8"))["u"]
    except Exception:
        vanha = {}
    uutiset = {u["l"]: u for u in (vanha.values() if isinstance(vanha, dict) else vanha)}
    for u in uutiset.values():
        u["k"] = siivoa(u.get("k", ""))
        # uudet aiheet (esim. Paikalliset) myös jo kerätyille uutisille
        # Aiheet lasketaan joka ajolla uudelleen nykyisillä säännöillä, jotta vanhat virheluokitukset korjautuvat.
        # Paikallislehden oma juttu säilyttää paikallistunnisteensa (se ei aina näy otsikon sanoista).
        vanhat_paik = {x for x in u.get("t", []) if x.startswith("paikalliset/")}
        u["t"] = sorted(set(luokittele(u)) | vanhat_paik | ({f"paikalliset/{a}" for a in AIHEET["paikalliset"]["ala"] if u["s"] in LEHDET[f"paikalliset/{a}"] and maakuntalehden_oma(u)}))
    tila = []
    if TESTI:
        for i in range(30):
            k = list(LUOK)[i % len(LUOK)]
            uutiset[f"https://example.fi/{i}"] = {"o": f"Testiuutinen {i} {k}", "l": f"https://example.fi/{i}", "s": "Testi", "h": "example.fi", "a": (nyt - timedelta(hours=i)).isoformat(), "k": "ingressi", "t": [k]}
    else:
        haut = [(n, u, None) for n, u in SUORAT]
        # Googlen aihehaut jaetaan kuuteen osaan: jokainen 10 min ajo tekee yhden osan, joten jokainen haku
        # ajetaan kerran tunnissa eikä Googlea kuormiteta kerralla (muuten se vastaa 503).
        osa = os.environ.get("KOOSTE_GOOGLE_OSA", "").strip()
        gi = 0
        for p, pv in AIHEET.items():
            if os.environ.get("KOOSTE_GOOGLE", "1") != "1":
                break
            for a, av in pv["ala"].items():
                if not osa or gi % 6 == int(osa) % 6:
                    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(f"({av['haku']}) when:7d") + "&hl=fi&gl=FI&ceid=FI:fi"
                    haut.append((f"Google: {p}/{a}", url, f"{p}/{a}"))
                gi += 1
        google_esto = False
        for nimi, url, kiinteä in haut:
            if kiinteä and google_esto:
                tila.append([nimi, 0, 0, "ohitettu: Google rajoitti"])
                continue
            try:
                lista = parse(hae(url), nimi)
                lisatty = 0
                for it in lista:
                    if kiinteä and not suomalainen(it):
                        continue
                    it["a"] = it["a"] or nyt.isoformat()
                    if kiinteä:
                        # Googlen haku on löyhä: aiheen hakusanan on löydyttävä otsikosta
                        oma_lehti = it["s"] in LEHDET.get(kiinteä, ()) and maakuntalehden_oma(it)
                        t = [kiinteä] if (LUOK[kiinteä].search(it["o"]) or oma_lehti) else []
                        t = sorted(set(t) | set(luokittele(it)))
                    else:
                        t = luokittele(it)
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
                if kiinteä and ("503" in str(e) or "429" in str(e)):
                    google_esto = True   # Google rajoittaa: ei jatketa tällä ajolla
            time.sleep(1.5 if kiinteä else 0.3)
    raja = (nyt - timedelta(days=SAILYTYS_PV)).isoformat()
    uutiset = {k: u for k, u in uutiset.items() if not estetty(u)}
    for u in uutiset.values():   # luokittelu tehty koko ingressillä, julkaistaan vain lyhyt ote
        u["k"] = lyhyt(u.get("k", ""))
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
    # lähteiden tila -sivu (ei hakukoneisiin)
    rivit = "".join(f'<tr><td>{esc(n)}</td><td>{h}</td><td>{l}</td><td>{"✓" if st == "ok" else esc(st)}</td></tr>' for n, h, l, st in tila)
    okt = sum(1 for t in tila if t[3] == "ok")
    kirjoita("tila/index.html", sivu(f"Lähteiden tila | {SITE}", "Uutislähteiden hakutilanne.", "tila/", 1,
        f'<h1>Lähteiden tila</h1><p class="lead">Viimeisin ajo {hki(pv, "%-d.%-m. klo %H.%M")} · {okt}/{len(tila)} lähdettä ok · {len(uniq)} uutista tallessa</p>'
        f'<div class="rows" style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px">'
        f'<tr style="text-align:left;color:var(--mute)"><th>Lähde</th><th>Haettu</th><th>Uusia</th><th>Tila</th></tr>{rivit}</table></div>', noindex=True))
    json.dump({"p": pv, "tila": tila, "u": uniq}, open(os.path.join(DIR, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for t in tila:
        print(t)
    print("uutisia yhteensä:", len(uniq))

main()
