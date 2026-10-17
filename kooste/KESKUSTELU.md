# Keskustelun käyttöönotto (Supabase)

Keskustelu on valmiina koodissa, mutta se on pois päältä, kunnes alla olevat vaiheet on tehty. Sivu toimii ilman sitä normaalisti.

1. Luo uusi, erillinen Supabase-projekti (ilmainen) osoitteessa supabase.com. Älä käytä Eduskuntaseurannan projektia.
2. Avaa projektissa **SQL Editor**, liitä sinne koko tiedosto `kooste/supabase.sql` ja **vaihda ennen ajamista** viimeisen rivin `SINUN@SAHKOPOSTI` omaksi sähköpostiosoitteeksesi. Paina Run.
3. **Authentication → URL Configuration**: aseta Site URL ja Redirect URLs -listaan osoite `https://miksu900.github.io/uutisvahti/kooste/**` (ja myöhemmin oma verkkotunnus).
4. **Project Settings → API**: kopioi Project URL ja julkinen (anon / publishable) avain.
5. GitHubissa repossa uutisvahti: **Settings → Secrets and variables → Actions → Variables** (ei Secrets!). Lisää muuttujat:
   - `SUPABASE_URL` = projektin URL
   - `SUPABASE_ANON_KEY` = julkinen avain
   - `KOOSTE_YLLAPITAJA` = nimesi tai yrityksesi (näkyy säännöissä ja tietosuojaselosteessa)
   - `KOOSTE_YHTEYS` = sähköpostiosoite, johon käyttäjät voivat ottaa yhteyttä
6. Aja työnkulku "Kerää laaja kooste" käsin (Actions-välilehti → Run workflow). Listoihin ilmestyy "Keskustele"-linkit.
7. Ylläpitonäkymä: `/kooste/moderointi/` (kirjaudu ylläpitäjän sähköpostilla).

Huomioita:
- Supabasen oletuksena sähköpostin lähetys on hyvin rajoitettu (muutama linkki tunnissa). Kun käyttäjiä tulee, lisää oma SMTP (Authentication → SMTP Settings).
- Tietosuojaseloste on luonnos. Tarkistuta se ennen kuin avaat keskustelun yleisölle.
