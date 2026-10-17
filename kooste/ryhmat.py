"""Saman tapahtuman uutisten ryhmittely eri medioista ("Nyt puhutaan").

Otsikot pilkotaan sanoiksi, sanat lyhennetään vartaloiksi (suomen taivutus), ja
kaksi uutista kuuluu samaan ryhmään, kun niiden otsikoissa on riittävästi yhteisiä
merkitseviä sanoja ja ne on julkaistu lähekkäin. Ryhmät muodostetaan union-findilla.
"""
import re
from datetime import datetime

STOP = set("""ja tai mutta että kun jos kuin on ovat oli olivat ei eivät en et hän he se ne tämä nämä tuo nuo
joka jotka mikä mitkä miten miksi missä mitä kuka ketkä nyt jo vielä myös vain sekä eli siis koska vaikka
kanssa mukaan jälkeen ennen aikana yli alle ilman kautta luona vuoksi takia saa sai voi voivat pitää pitäisi
tulee tuli olla ollut on uusi uuden uudet suuri iso pieni hyvä paljon vähän kaikki kaikkien moni monet
sitten taas tänään eilen huomenna vuonna vuoden viikon päivän kertoo kertoi sanoo sanoi mielestä näin tässä
tästä siitä siihen sinne täällä sieltä mitä mukana noin jopa ainakin enää lähes heti juuri aivan todella
katso lue video kuvat kuvagalleria live seuranta suora lähetys analyysi kolumni pääkirjoitus mielipide
suomi suomen suomessa suomeen suomalainen suomalaiset suomalaisten""".split())

RX = re.compile(r"[a-zäöåé0-9]+(?:-[a-zäöå0-9]+)*", re.I)

def vartalot(otsikko):
    out = set()
    for w in RX.findall(otsikko.lower()):
        if w in STOP or len(w) < 3:
            continue
        if w.isdigit():
            if len(w) >= 2:          # luvut (esim. 20 000, 15) ovat hyviä tunnisteita
                out.add(w)
            continue
        out.add(w[:5] if len(w) > 5 else w)
    return out

def _aika(u):
    return datetime.fromisoformat(u["a"]).timestamp()

def puhdas_otsikko(o):
    """HS: "Osasto | Otsikko", Uutissuomalainen: "Otsikko | Uutissuomalainen" -> pisin osa."""
    osat = [x.strip() for x in re.split(r"\s+\|\s+|\s+-\s+(?=[A-ZÄÖ][a-zäö]+(\s\|\s|$))", o) if x and x.strip()]
    return max(osat, key=len) if osat else o

OSUUS = 0.3

def ryhmittele(items, ikkuna_h=36, kynnys=0.34):
    """Palauttaa listan ryhmiä (lista uutisia, uusin ensin). Jokainen uutinen on täsmälleen yhdessä ryhmässä."""
    import math
    n = len(items)
    V = [vartalot(puhdas_otsikko(u["o"])) for u in items]
    T = [_aika(u) for u in items]
    df = {}
    for v in V:
        for x in v:
            df[x] = df.get(x, 0) + 1
    idf = {x: math.log((n + 1) / c) for x, c in df.items()}
    W = [sum(idf[x] for x in v) for v in V]
    ind = {}
    for i, v in enumerate(V):
        for x in v:
            ind.setdefault(x, []).append(i)
    # parien samankaltaisuus (painotettu päällekkäisyys, harvinaiset sanat painavat enemmän)
    linkit = {}
    for i in range(n):
        if len(V[i]) < 2:
            continue
        ehd = set()
        for x in V[i]:
            if df[x] <= 60:
                ehd.update(j for j in ind[x] if j > i)
        for j in ehd:
            if abs(T[i] - T[j]) > ikkuna_h * 3600:
                continue
            yht = V[i] & V[j]
            if len(yht) < 2:
                continue
            sim = sum(idf[x] for x in yht) / max(1e-9, min(W[i], W[j]))
            if sim >= kynnys:
                linkit[(i, j)] = sim
    # keskiarvolinkitys: ryhmät yhdistetään vain, jos riittävä osa jäsenpareista on linkitetty (estää ketjuuntumisen)
    ryhma = {i: {i} for i in range(n)}
    jakso = {i: (T[i], T[i]) for i in range(n)}   # ryhmän vanhin ja uusin julkaisuaika
    kuuluu = list(range(n))
    for (i, j), sim in sorted(linkit.items(), key=lambda kv: -kv[1]):
        a, b = kuuluu[i], kuuluu[j]
        if a == b:
            continue
        A, B = ryhma[a], ryhma[b]
        lk = sum(1 for x in A for y in B if (min(x, y), max(x, y)) in linkit)
        if lk < OSUUS * len(A) * len(B):
            continue
        alku, loppu = min(jakso[a][0], jakso[b][0]), max(jakso[a][1], jakso[b][1])
        if loppu - alku > ikkuna_h * 3600:   # koko ryhmän aikajänne rajattu
            continue
        if len(A) < len(B):
            a, b, A, B = b, a, B, A
        A |= B
        jakso[a] = (alku, loppu)
        for y in B:
            kuuluu[y] = a
        del ryhma[b]
    out = []
    for g in ryhma.values():
        lista = sorted((items[i] for i in g), key=lambda u: u["a"], reverse=True)
        out.append(lista)
    return out

def mediat(g):
    nahty, out = set(), []
    for u in sorted(g, key=lambda u: u["a"]):
        if u["s"] not in nahty:
            nahty.add(u["s"]); out.append(u["s"])
    return out

def muissa_medioissa(items, ikkuna_h=36, kynnys=0.22):
    """Tunnukset uutisille, joille löytyy edes löyhästi samankaltainen uutinen toisesta mediasta.
    Käytetään 'Vain yksi media kertoi' -osiossa, jotta sinne päätyy vain aidosti yhden median uutisia."""
    import math
    n = len(items)
    V = [vartalot(puhdas_otsikko(u["o"])) for u in items]
    T = [_aika(u) for u in items]
    df = {}
    for v in V:
        for x in v:
            df[x] = df.get(x, 0) + 1
    idf = {x: math.log((n + 1) / c) for x, c in df.items()}
    W = [sum(idf[x] for x in v) for v in V]
    ind = {}
    for i, v in enumerate(V):
        for x in v:
            ind.setdefault(x, []).append(i)
    out = set()
    for i in range(n):
        for x in V[i]:
            if df[x] > 80:
                continue
            for j in ind[x]:
                if j == i or items[j]["s"] == items[i]["s"] or abs(T[i] - T[j]) > ikkuna_h * 3600:
                    continue
                yht = V[i] & V[j]
                if len(yht) >= 2 and sum(idf[y] for y in yht) / max(1e-9, min(W[i], W[j])) >= kynnys:
                    out.add(items[i].get("i") or items[i]["l"])
                    break
            else:
                continue
            break
    return out
