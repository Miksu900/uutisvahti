# Pääaiheet ja alaaiheet. Avain = url-polku. "sanat" = osumat otsikossa/ingressissä, "haku" = Google Uutisten hakulauseke.
AIHEET = {
  "politiikka": {"nimi": "Politiikka", "kuvaus": "Suomen politiikan uutiset: eduskunta, hallitus, vaalit, maahanmuutto ja ulkopolitiikka.", "ala": {
    "eduskunta-ja-hallitus": {"nimi": "Eduskunta ja hallitus", "sanat": ["eduskunta", "kansanedustaj", "hallitus", "ministeri", "pääministeri", "orpo", "purra", "lindtman", "puoluejohtaj", "oppositio"], "haku": "eduskunta OR hallitus OR ministeri"},
    "maahanmuutto": {"nimi": "Maahanmuutto", "sanat": ["maahanmuut", "turvapaikka", "pakolai", "ulkomaalaislaki", "kotoutu", "kotouttami", "kansalaisuuslaki", "oleskelulup", "karkotu", "rajaturva", "monikulttuur"], "haku": "maahanmuutto OR turvapaikanhakija OR ulkomaalaislaki"},
    "islam": {"nimi": "Islam", "sanat": ["islam", "muslimi", "moskeija", "imaami", "šaria", "sharia", "jihad", "džihad", "hijab", "burka", "nikab", "kalifaatti", "koraani", "ramadan"], "haku": "islam OR muslimi OR moskeija"},
    "vaalit-ja-puolueet": {"nimi": "Vaalit ja puolueet", "sanat": ["vaali", "ehdokas", "puolueen kannatus", "kannatuskysely", "puoluekokous", "puoluesihteer", "kokoomus", "sdp", "perussuomalai", "keskusta", "vihreät", "vasemmistoliitto"], "haku": "vaalit OR puolueet OR kannatuskysely"},
    "ulkopolitiikka": {"nimi": "Ulkopolitiikka ja turvallisuus", "sanat": ["ukraina", "venäjä", "nato", "putin", "zelensk", "puolustusvoim", "eu-", "ulkoministeri", "trump", "kiina"], "haku": "Ukraina OR Venäjä OR Nato OR ulkopolitiikka"},
    "verot-ja-budjetti": {"nimi": "Verot ja budjetti", "sanat": ["vero", "budjetti", "julkinen talous", "leikkaus", "velka", "indeksi", "valtiovarainministeri", "talousarvio"], "haku": "verotus OR budjetti OR valtion velka"},
  }},
  "talous": {"nimi": "Talous", "kuvaus": "Talouden, työn, asumisen ja sijoittamisen uutiset Suomesta.", "ala": {
    "tyo-ja-tyollisyys": {"nimi": "Työ ja työllisyys", "sanat": ["työttömyys", "työllisyys", "irtisano", "muutosneuvottelu", "lakko", "palkka", "työmarkkina", "ay-liike", "työpaikka"], "haku": "työttömyys OR irtisanomiset OR työmarkkinat"},
    "asuminen": {"nimi": "Asuminen ja korot", "sanat": ["asunto", "vuokra", "asuntolaina", "euribor", "korko", "kiinteistö", "omakotitalo", "kerrostalo"], "haku": "asuntomarkkinat OR vuokrat OR euribor"},
    "porssi-ja-sijoittaminen": {"nimi": "Pörssi ja sijoittaminen", "sanat": ["pörssi", "osake", "sijoittaj", "osinko", "rahasto", "bitcoin", "krypto", "ethereum", "kurssi"], "haku": "pörssi OR sijoittaminen OR bitcoin OR osakkeet"},
    "energia": {"nimi": "Energia ja sähkö", "sanat": ["sähkö", "energia", "ydinvoima", "tuulivoima", "sähkön hinta", "fingrid", "polttoaine", "bensiini"], "haku": "sähkön hinta OR energia OR ydinvoima"},
    "yritykset": {"nimi": "Yritykset", "sanat": ["konkurssi", "yritys", "yrittäjä", "liikevaihto", "osakeyhtiö", "start-up", "startup"], "haku": "yritykset OR yrittäjät OR konkurssit"},
  }},
  "yhteiskunta": {"nimi": "Yhteiskunta", "kuvaus": "Rikokset, terveys, koulutus ja sosiaaliturva: yhteiskunnan uutiset Suomesta.", "ala": {
    "rikokset-ja-oikeus": {"nimi": "Rikokset ja oikeus", "sanat": ["poliisi", "tuomio", "oikeus", "syyte", "murha", "pahoinpitely", "huume", "vankila", "rikos", "epäilty", "käräjä"], "haku": "poliisi OR oikeudenkäynti OR rikos"},
    "terveys-ja-sote": {"nimi": "Terveys ja sote", "sanat": ["sairaala", "hoitaja", "lääkäri", "terveyskeskus", "sote", "hyvinvointialue", "päivystys", "hoitojono", "sairaus"], "haku": "terveydenhuolto OR sairaala OR hyvinvointialue"},
    "koulutus": {"nimi": "Koulutus", "sanat": ["koulu", "opettaj", "oppilas", "yliopisto", "opiskelija", "ammattikoulu", "oppivelvollisuus", "pisa"], "haku": "koulut OR opettajat OR yliopisto"},
    "sosiaaliturva": {"nimi": "Sosiaaliturva ja Kela", "sanat": ["kela", "eläke", "toimeentulotuki", "työttömyysturva", "asumistuki", "sosiaaliturva", "lapsilisä", "perustulo"], "haku": "Kela OR eläke OR sosiaaliturva OR toimeentulotuki"},
  }},
  "lifestyle": {"nimi": "Lifestyle", "kuvaus": "Ruoka, matkailu, hyvinvointi, koti ja ihmissuhteet: arjen uutiset ja vinkit Suomesta.", "ala": {
    "ruoka": {"nimi": "Ruoka ja juoma", "sanat": ["resepti", "ruoka", "ravintola", "leivonta", "kahvi", "viini", "olut", "ruokakauppa"], "haku": "ruoka OR resepti OR ravintola"},
    "matkailu": {"nimi": "Matkailu", "sanat": ["matka", "lento", "loma", "hotelli", "lentoyhtiö", "turisti", "risteily", "finnair"], "haku": "matkailu OR lomamatka OR Finnair"},
    "hyvinvointi": {"nimi": "Hyvinvointi ja liikunta", "sanat": ["liikunta", "ravinto", "laihdu", "kuntosali", "juoksu", "stressi", "mielenterveys", "jaksaminen"], "haku": "hyvinvointi OR liikunta OR uni"},
    "koti-ja-puutarha": {"nimi": "Koti ja puutarha", "sanat": ["sisustus", "remontti", "puutarha", "piha", "keittiö", "kylpyhuone", "mökki"], "haku": "sisustus OR remontti OR puutarha"},
    "perhe-ja-suhteet": {"nimi": "Perhe ja suhteet", "sanat": ["parisuhde", "avioero", "vanhemmuus", "lapsiperhe", "häät", "deittai", "naimisiin"], "haku": "parisuhde OR vanhemmuus OR lapsiperhe"},
  }},
  "teknologia": {"nimi": "Teknologia", "kuvaus": "Tekoäly, tietoturva, puhelimet ja sovellukset: tekniikan uutiset Suomesta.", "ala": {
    "tekoaly": {"nimi": "Tekoäly", "sanat": ["tekoäly", "chatgpt", "openai", "anthropic", "kielimalli", "robotti", "koneoppi"], "haku": "tekoäly OR ChatGPT OR OpenAI"},
    "tietoturva": {"nimi": "Tietoturva", "sanat": ["tietomurto", "kyber", "huijaus", "kalastelu", "haittaohjelma", "tietoturva", "tunnistautumi", "verkkopetos"], "haku": "tietoturva OR kyberhyökkäys OR huijaus"},
    "puhelimet-ja-sovellukset": {"nimi": "Puhelimet ja sovellukset", "sanat": ["iphone", "android", "samsung", "sovellus", "älypuhelin", "tiktok", "instagram", "facebook", "somejätti"], "haku": "älypuhelin OR sovellus OR TikTok"},
  }},
  "urheilu": {"nimi": "Urheilu", "kuvaus": "Jääkiekko, jalkapallo, formulat ja muu urheilu Suomesta.", "ala": {
    "jaakiekko": {"nimi": "Jääkiekko", "sanat": ["jääkiekko", "liiga", "leijonat", "nhl", "kiekko"], "haku": "jääkiekko OR Liiga OR Leijonat"},
    "jalkapallo": {"nimi": "Jalkapallo", "sanat": ["jalkapallo", "veikkausliiga", "huuhkajat", "valioliiga", "mestarien liiga"], "haku": "jalkapallo OR Huuhkajat OR Veikkausliiga"},
    "moottoriurheilu": {"nimi": "Moottoriurheilu", "sanat": ["formula", "ralli", "bottas", "moottoriurheilu", "f1"], "haku": "formula 1 OR ralli OR moottoriurheilu"},
  }},
  "viihde": {"nimi": "Viihde", "kuvaus": "Julkkikset, elokuvat, sarjat ja musiikki Suomesta.", "ala": {
    "julkkikset": {"nimi": "Julkkikset", "sanat": ["julkkis", "tähti", "seurustel", "esiintyj", "juontaj", "kuuluisa"], "haku": "julkkis OR viihdetähti"},
    "tv-ja-elokuvat": {"nimi": "TV ja elokuvat", "sanat": ["elokuva", "sarja", "netflix", "ohjelma", "elokuvateatteri", "jakso", "ensi-ilta"], "haku": "elokuva OR sarja OR Netflix"},
    "musiikki": {"nimi": "Musiikki", "sanat": ["musiikki", "keikka", "albumi", "bändi", "artisti", "festivaali", "laulaja", "single"], "haku": "musiikki OR keikka OR albumi"},
  }},
  "liikenne": {"nimi": "Liikenne ja autot", "kuvaus": "Autot, taksit, joukkoliikenne ja liikenneuutiset Suomesta.", "ala": {
    "taksi": {"nimi": "Taksi", "sanat": ["taksi", "taksiyrittäjä", "kuljettaja", "uber", "bolt"], "haku": "taksi OR taksiala OR taksiyrittäjä"},
    "autot": {"nimi": "Autot ja sähköautot", "sanat": ["auto", "sähköauto", "autovero", "katsastus", "tesla", "renkaat", "ajoneuvo"], "haku": "autot OR sähköauto OR autovero"},
    "joukkoliikenne": {"nimi": "Joukkoliikenne", "sanat": ["juna", "vr", "hsl", "raitiovaunu", "bussi", "metro", "lentokenttä", "joukkoliikenne"], "haku": "joukkoliikenne OR VR OR HSL"},
  }},
}
