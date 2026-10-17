# Uutisvahti

Oma uutiskooste: hakee suomalaisten medioiden uutisvirrat tunnin välein, suodattaa islam- ja maahanmuuttouutiset ja rakentaa niistä yhden sivun (`index.html`, GitHub Pages).
Tallennetaan vain otsikko, linkki, lyhyt ingressi ja lähde. Hakusanat ovat tiedostossa `keraa.py`.

## Laaja kooste (`kooste/`)

Erillinen, laajempi versio: 8 pääaihetta ja 32 alaaihetta (politiikka → islam, maahanmuutto, …), vain suomalaiset (.fi) lähteet.
- Aiheet ja hakusanat: `kooste/aiheet.py`
- Keräin ja sivugeneraattori: `kooste/keraa.py` (ajetaan tunnin välein, `.github/workflows/kooste.yml`)
- Sivut: aihesivut (`/politiikka/islam/` jne.), `Oma syöte` (kävijä valitsee aiheet, tallentuu selaimeen ja jaettavaan linkkiin), `sitemap.xml`, `robots.txt`
- Oman verkkotunnuksen käyttöönotto: aseta GitHubin repo-asetuksissa (Settings → Secrets and variables → Actions → Variables) `KOOSTE_BASE_URL` (esim. `https://omadomain.fi`) ja `KOOSTE_NIMI` (sivuston nimi), aja työnkulku uudelleen.
