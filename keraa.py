#!/usr/bin/env python3
"""Hakee suomalaisten medioiden RSS-virrat, suodattaa islam- ja maahanmuuttouutiset ja rakentaa index.html."""
import os, time, json, re, sys, urllib.request, urllib.parse, html
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

UA = "Mozilla/5.0 (compatible; uutisvahti/1.0; oma uutiskooste)"

SUORAT = [
    ("Yle", "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"),
    ("Helsingin Sanomat", "https://www.hs.fi/rss/tuoreimmat.xml"),
    ("Ilta-Sanomat", "https://www.is.fi/rss/tuoreimmat.xml"),
    ("Iltalehti", "https://www.iltalehti.fi/rss/uutiset.xml"),
    ("MTV Uutiset", "https://www.mtvuutiset.fi/api/feed/rss/uutiset_uusimmat"),
    ("Suomen Uutiset", "https://www.suomenuutiset.fi/feed/"),
    ("Kansalainen", "https://kansalainen.fi/feed/"),
]
HAUT = ["islam", "muslimi", "moskeija", "maahanmuutto", "turvapaikanhakija", "pakolainen", "ulkomaalaislaki", "kotouttaminen", "kansalaisuuslaki"]
GOOGLE = [("Google Uutiset", "https://news.google.com/rss/search?q=" + urllib.parse.quote(h + " when:7d") + "&hl=fi&gl=FI&ceid=FI:fi") for h in HAUT]

AIHEET = {
    "Islam": ["islam", "muslimi", "moskeija", "imaami", "šaria", "sharia", "jihad", "džihad", "hijab", "burka", "nikab", "kalifaatti", "koraani", "ramadan"],
    "Maahanmuutto": ["maahanmuut", "turvapaikka", "pakolai", "ulkomaalaislaki", "ulkomaalaisl", "kotoutu", "kotouttami", "kansalaisuuslaki", "oleskelulup", "karkotu", "maahantulo", "rajaturva", "vieraskielis", "monikulttuur"],
}
NIMET = {"HS.fi": "Helsingin Sanomat", "Hs.fi": "Helsingin Sanomat", "Yle Uutiset": "Yle", "yle.fi": "Yle", "Is.fi": "Ilta-Sanomat", "IS.fi": "Ilta-Sanomat"}
SAILYTYS_PV = 90
MAX = 3000

def hae(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    return urllib.request.urlopen(r, timeout=40).read()

def teksti(e, *nimet):
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
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").strip()

def parse(data, oletus_lahde):
    root = ET.fromstring(data)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    items = root.findall(".//item") or root.findall(".//a:entry", ns)
    for it in items:
        otsikko = puhdista(teksti(it, "title", "{http://www.w3.org/2005/Atom}title"))
        link = teksti(it, "link")
        if not link:
            l = it.find("{http://www.w3.org/2005/Atom}link")
            link = l.get("href") if l is not None else ""
        kuv = re.sub(r"\s*The post\s.*$", "", puhdista(teksti(it, "description", "{http://www.w3.org/2005/Atom}summary")), flags=re.S).strip()
        pvm = aika(teksti(it, "pubDate", "{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published"))
        lahde = oletus_lahde
        s = it.find("source")
        if s is not None and (s.text or "").strip():
            lahde = s.text.strip()
            if otsikko.endswith(" - " + lahde):
                otsikko = otsikko[: -len(lahde) - 3]
        lahde = NIMET.get(lahde, lahde)
        if kuv.lower().startswith(otsikko.lower()[:40]):
            kuv = ""
        if otsikko and link:
            out.append({"otsikko": otsikko, "linkki": link.strip(), "kuvaus": kuv[:300], "lahde": lahde, "aika": pvm.isoformat() if pvm else None})
    return out

def aiheet(it):
    t = (it["otsikko"] + " " + it["kuvaus"]).lower()
    res = {}
    for aihe, sanat in AIHEET.items():
        osumat = sorted({s for s in sanat if s in t})
        if osumat:
            res[aihe] = osumat
    return res

def main():
    try:
        vanha = json.load(open("data.json", encoding="utf-8"))
    except Exception:
        vanha = {"uutiset": {}}
    uutiset = vanha.get("uutiset", {})
    tila = []
    uusia = 0
    nyt = datetime.now(timezone.utc)
    # Google-haut kerran tunnissa (työnkulku asettaa OMA_GOOGLE), median omat virrat joka ajolla
    for nimi, url in SUORAT + (GOOGLE if os.environ.get("OMA_GOOGLE", "1") == "1" else []):
        try:
            lista = parse(hae(url), nimi)
            osumia = 0
            for it in lista:
                a = aiheet(it)
                if not a:
                    continue
                osumia += 1
                if it["linkki"] not in uutiset:
                    uusia += 1
                    it["aiheet"] = a
                    it["haettu"] = nyt.isoformat()
                    if not it["aika"]:
                        it["aika"] = nyt.isoformat()
                    uutiset[it["linkki"]] = it
            if "google" in url:
                time.sleep(1.5)
            tila.append([nimi if "google" not in url else "Google: " + urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0].replace(" when:7d", ""), len(lista), osumia, "ok"])
        except Exception as e:
            tila.append([nimi, 0, 0, "VIRHE " + str(e)[:80]])
    raja = (nyt - timedelta(days=SAILYTYS_PV)).isoformat()
    uutiset = {k: v for k, v in uutiset.items() if (v["aika"] or "") >= raja and "verkkouutiset" not in (v.get("lahde", "") + v.get("linkki", "")).lower()}
    for v in uutiset.values():   # julkaistaan vain hyvin lyhyt ote (lehtikustantajan oikeus)
        kv = (v.get("kuvaus") or "").strip()
        if len(kv) > 100:
            v["kuvaus"] = kv[:100].rsplit(" ", 1)[0].rstrip(" ,.;:–-") + "…"
    jarj = sorted(uutiset.values(), key=lambda v: v["aika"] or "", reverse=True)[:MAX]
    # deduplikoi sama otsikko+lähde
    # sama uutinen eri virroista: pidä yksi, suosi median omaa virtaa Googlen sijaan
    def avain(v):
        return re.sub(r"[^a-z0-9äöå]+", "", v["otsikko"].lower())
    jarj.sort(key=lambda v: (avain(v), "news.google" in v["linkki"], v["aika"] or ""))
    nahty, uniikit = set(), []
    for v in jarj:
        k = avain(v)
        if k in nahty:
            continue
        nahty.add(k)
        uniikit.append(v)
    uniikit.sort(key=lambda v: v["aika"] or "", reverse=True)
    out = {"paivitetty": nyt.isoformat(), "tila": tila, "uutiset": {v["linkki"]: v for v in uniikit}}
    json.dump(out, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sivu = open("pohja.html", encoding="utf-8").read().replace("__DATA__", json.dumps(
        {"paivitetty": out["paivitetty"], "tila": tila, "uutiset": uniikit}, ensure_ascii=False).replace("</", "<\\/"))
    open("index.html", "w", encoding="utf-8").write(sivu)
    for t in tila:
        print(t)
    print("uusia:", uusia, "yhteensä:", len(uniikit))

main()
