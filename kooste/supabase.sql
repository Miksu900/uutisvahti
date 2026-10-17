-- Uutiskoosteen keskustelu: aja tämä kokonaan Supabasen SQL Editorissa (uusi, erillinen projekti).
-- ENNEN AJAMISTA: vaihda alimmalla rivillä oleva SINUN@SAHKOPOSTI omaksi sähköpostiosoitteeksesi (ylläpitäjä).

create table if not exists profiilit (
  id uuid primary key references auth.users(id) on delete cascade,
  nimimerkki text not null unique
    check (char_length(nimimerkki) between 3 and 24 and nimimerkki ~ '^[A-Za-z0-9ÅÄÖåäö_.-]+$'),
  luotu timestamptz not null default now()
);

create table if not exists yllapitajat (email text primary key);

create table if not exists kommentit (
  id bigint generated always as identity primary key,
  uutinen text not null check (uutinen ~ '^[a-f0-9]{16}$'),
  otsikko text not null check (char_length(otsikko) between 1 and 400),
  linkki text not null check (linkki ~ '^https?://' and char_length(linkki) <= 1000),
  kayttaja uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nimimerkki text not null,
  teksti text not null check (char_length(teksti) between 1 and 2000),
  luotu timestamptz not null default now(),
  poistettu boolean not null default false
);
create index if not exists kommentit_uutinen_idx on kommentit (uutinen, luotu);
create index if not exists kommentit_luotu_idx on kommentit (luotu desc);

create table if not exists ilmiannot (
  id bigint generated always as identity primary key,
  kommentti_id bigint not null references kommentit(id) on delete cascade,
  kayttaja uuid not null default auth.uid() references auth.users(id) on delete cascade,
  syy text check (char_length(syy) <= 500),
  luotu timestamptz not null default now(),
  unique (kommentti_id, kayttaja)
);

-- Ylläpitäjän tunnistus: kirjautuneen käyttäjän vahvistettu sähköposti löytyy ylläpitäjälistalta.
create or replace function is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from yllapitajat where lower(email) = lower(coalesce(auth.jwt() ->> 'email', '')));
$$;
grant execute on function is_admin() to anon, authenticated;

-- Kommenttimäärät uutislistoille (ei paljasta poistettuja)
create or replace function kommenttimaarat(ids text[]) returns table (uutinen text, n bigint)
language sql stable security definer set search_path = public as $$
  select k.uutinen, count(*) from kommentit k
  where k.uutinen = any(ids) and not k.poistettu group by k.uutinen;
$$;
grant execute on function kommenttimaarat(text[]) to anon, authenticated;

-- Nopeusrajoitus: enintään 10 kommenttia 10 minuutissa per käyttäjä
create or replace function kommentti_rajoitus() returns trigger
language plpgsql as $$
begin
  if (select count(*) from kommentit where kayttaja = new.kayttaja and luotu > now() - interval '10 minutes') >= 10 then
    raise exception 'Liian monta kommenttia lyhyessä ajassa. Odota hetki.';
  end if;
  return new;
end $$;
drop trigger if exists kommentti_rajoitus_trg on kommentit;
create trigger kommentti_rajoitus_trg before insert on kommentit for each row execute function kommentti_rajoitus();

-- Rivitason suojaus
alter table profiilit enable row level security;
alter table yllapitajat enable row level security;
alter table kommentit enable row level security;
alter table ilmiannot enable row level security;

drop policy if exists profiilit_luku on profiilit;
create policy profiilit_luku on profiilit for select using (true);
drop policy if exists profiilit_lisays on profiilit;
create policy profiilit_lisays on profiilit for insert to authenticated with check (id = auth.uid());

-- yllapitajat: ei yhtään käytäntöä, joten sitä ei voi lukea suoraan (vain is_admin() käyttää)

drop policy if exists kommentit_luku on kommentit;
create policy kommentit_luku on kommentit for select using (not poistettu or is_admin());
drop policy if exists kommentit_lisays on kommentit;
create policy kommentit_lisays on kommentit for insert to authenticated
  with check (kayttaja = auth.uid() and not poistettu
              and nimimerkki = (select p.nimimerkki from profiilit p where p.id = auth.uid()));
drop policy if exists kommentit_paivitys on kommentit;
create policy kommentit_paivitys on kommentit for update to authenticated using (is_admin()) with check (is_admin());
drop policy if exists kommentit_poisto on kommentit;
create policy kommentit_poisto on kommentit for delete to authenticated using (kayttaja = auth.uid() or is_admin());

drop policy if exists ilmiannot_lisays on ilmiannot;
create policy ilmiannot_lisays on ilmiannot for insert to authenticated with check (kayttaja = auth.uid());
drop policy if exists ilmiannot_luku on ilmiannot;
create policy ilmiannot_luku on ilmiannot for select to authenticated using (is_admin());
drop policy if exists ilmiannot_poisto on ilmiannot;
create policy ilmiannot_poisto on ilmiannot for delete to authenticated using (is_admin());

-- VIIMEISENÄ: lisää itsesi ylläpitäjäksi (vaihda sähköposti!)
insert into yllapitajat (email) values ('SINUN@SAHKOPOSTI') on conflict do nothing;
