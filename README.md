# PRD: Discovery PL Creators v1

**Projekt:** JANUSZEKRÓL / Akademia 100k – outbound rekrutacja Short-Form Copywriter
**Iteracja:** 1 (MVP – pierwsza lista do ręcznego review)
**Data:** 2026-05-11
**Owner:** Janek

---

## 1. Cel iteracji

Wypuścić **2 pliki XLSX** (jeden IG, jeden TikTok), każdy zawierający **30–50 wierszy** polskich twórców spełniających podstawowe kryteria z SOP, do ręcznego review przez Janka.

To jest **MVP discovery** – jednorazowy run, najmniejsza możliwa logika. Powtarzalność, scoring, klasyfikacja typu, integracja z n8n – wszystko parkujemy.

---

## 2. Out of scope (świadomie parkowane)

- LLM klasyfikacja typu twórcy (EDU/story/UGC/art) – Janek oznacza ręcznie w Excelu po review
- Writing/Hunger/Professionalism scoring – wymaga LLM, podbija koszt i kompleksność
- Detekcja wieku (20–30) – niemożliwe automatycznie, ręczny review po zdjęciu
- Detekcja "głodu kasy" i braku monetyzacji – sygnał słaby, ręczny review po bio
- Integracja z n8n / DataTables – jednorazowy run, nie potrzeba pipeline'u
- Auto-discovery przez lookalike / komentujących pod top twórcami
- Wysyłka DM – zupełnie osobny etap

---

## 3. Architektura (najprostsza możliwa)

```
[Apify hashtag scraper] → [Apify profile scraper] → [Python: dedup + filter + export]
        IG/TT                    IG/TT                     2 × XLSX
```

**Dlaczego nie n8n w tej iteracji:** n8n ma sens dopiero gdy puszczasz cron co tydzień. Dla jednorazowego batcha 60–100 profili to overkill. Logikę filtracji zachowujemy w skrypcie Python – jeśli kiedyś chcemy ją przenieść do n8n, port jest trywialny (Code node v2).

**Gdzie odpalamy skrypt Python:**
- Najszybsza opcja: Claude w przeglądarce (code execution sandbox) – ja uruchamiam w trakcie kolejnej iteracji, Ty dostajesz gotowe XLSX przez `present_files`
- Apify dataset → pobranie JSON → ten sam skrypt lokalnie też zadziała

---

## 4. Pipeline – 5 kroków

### Krok 1: Discovery (hashtag scraping)

**Instagram** – actor `apify/instagram-hashtag-scraper`:
- Input: lista hashtagów PL (sekcja 7), `resultsLimit: 100` per hashtag
- Output: ~500–800 postów (zależnie od liczby hashtagów)

**TikTok** – actor `clockworks/tiktok-scraper` lub `apify/tiktok-scraper`:
- KONIECZNOŚĆ WERYFIKACJI: który actor TT daje aktualnie najlepsze rezultaty i koszt
- Input: lista hashtagów PL, `resultsPerPage: 100` per hashtag
- Output: ~500–800 wideo

### Krok 2: Deduplikacja autorów

Z listy postów wyciągamy unikalne `username` / `authorMeta.uniqueId`. Spodziewane: ~300–500 unikalnych autorów per platforma (sporo overlapu między hashtagami).

### Krok 3: Enrichment (profile data)

**Instagram** – actor `apify/instagram-profile-scraper`:
- Input: lista usernames z kroku 2
- Output per profil: `followersCount`, `followsCount`, `biography`, `isVerified`, lista ostatnich 12 postów z timestampami i typem (`Reel` / `Image` / `Sidecar`)

**TikTok** – actor `clockworks/tiktok-profile-scraper`:
- Input: lista usernames
- Output per profil: `fans` (followers), `following`, `signature` (bio), ostatnie wideo z timestampami i view countami

KONIECZNOŚĆ WERYFIKACJI: dokładny schemat zwracany przez aktualną wersję actorów (Apify aktualizuje, schematy się zmieniają).

### Krok 4: Filtracja (heurystyka, prosta)

Filtry stosowane w Pythonie na pobranych profilach:

| Filtr                       | Reguła                                                                                                  | Twardość |
|-----------------------------|---------------------------------------------------------------------------------------------------------|----------|
| Followers                   | 1 000 ≤ x ≤ 10 000                                                                                      | Twardy   |
| Aktywność short-form        | ≥ 5 rolek/videos w ostatnich 30 dniach (liczone z timestampów ostatnich postów)                         | Twardy   |
| Język PL                    | Bio zawiera ≥1 polski znak diakrytyczny (ąęćłńóśźż) LUB ≥2 polskie stopwords (się, jest, nie, jak, że) | Twardy   |
| Nie zweryfikowany           | `isVerified == false` (eliminuje duże marki i celebrytów)                                               | Twardy   |
| Blacklist bio (sygnał korpo)| Bio nie zawiera: "B2B", "SaaS", "HR tech", "automation dla firm", "agencja marketingowa", "marketing manager" | Miękki   |

**Podważam jeden punkt:** "min 5 rolek/30 dni" – Apify profile scraper zwraca domyślnie 12 ostatnich postów. Jeśli twórca posta bardzo gęsto (np. 2/dzień), 12 ostatnich pokryje tylko ~6 dni i nie zobaczymy pełnego okna 30 dni. Mitygacja: podbić `resultsLimit` w profile scraperze do 30 (kosztuje więcej, ale wciąż grosze) i liczyć rolki z czasem stamp `> now - 30 dni`.

### Krok 5: Eksport XLSX

Dwa pliki: `discovery_ig_v1_YYYY-MM-DD.xlsx`, `discovery_tt_v1_YYYY-MM-DD.xlsx`.

Po filtrach spodziewamy się 30–80 wierszy per platforma. Jeśli więcej niż 50 – sortujemy po liczbie rolek/30d malejąco i bierzemy top 50.

Jeśli mniej niż 30 po filtrach – rozszerzamy listę hashtagów i powtarzamy (świadomy trade-off jakość/ilość, do ustalenia z Jankiem).

---

## 5. Schemat XLSX (kolumny)

Spójny z arkuszem trackingowym z SOP §5, ale na tym etapie tylko **dane wyciągnięte automatycznie** – pola scoringowe (Writing/Hunger/Professionalism) zostawiamy puste, do wypełnienia ręcznie:

| # | Kolumna                  | Źródło                                  | Przykład                     |
|---|--------------------------|------------------------------------------|------------------------------|
| 1 | Data scrape              | now()                                    | 2026-05-11                   |
| 2 | Nick wyświetlany         | Apify (`fullName` / `nickname`)          | Anna Kowalska                |
| 3 | Handle                   | Apify (`username`)                       | anna.kowalska                |
| 4 | Link do profilu          | konstruowany                             | instagram.com/anna.kowalska  |
| 5 | Platforma                | "IG" / "TT"                              | IG                           |
| 6 | Followers                | Apify                                    | 4 320                        |
| 7 | Following                | Apify                                    | 312                          |
| 8 | Reels/Videos w 30d       | obliczone z timestampów                  | 11                           |
| 9 | Bio (raw)                | Apify (`biography` / `signature`)        | Trenerka mindset…            |
| 10| Link do top postu        | Apify (post z największą liczbą views)   | instagram.com/p/CxYz…        |
| 11| Avg views (ost. rolki)   | mean z ostatnich rolek (jeśli dostępne)  | 8 500                        |
| 12| Writing Score (1–5)      | puste – do wypełnienia ręcznie           | _                            |
| 13| Hunger Score (1–5)       | puste – do wypełnienia ręcznie           | _                            |
| 14| Professionalism (1–5)    | puste – do wypełnienia ręcznie           | _                            |
| 15| Ocena końcowa (Z/Ż/C)    | puste                                    | _                            |
| 16| Status                   | "nowy"                                   | nowy                         |
| 17| Notatki                  | puste                                    | _                            |

---

## 6. Hashtagi seedowe

**Instagram (z SOP + propozycje rozszerzeń):**
- Z SOP: `#biznesonline`, `#marketing`, `#treneronline`, `#edukacja`, `#rozwojosobisty`
- Propozycje rozszerzeń: `#przedsiebiorca`, `#onlinebiznes`, `#produktywnosc`, `#finanseosobiste`, `#mentalhealthpl`, `#nauka`, `#jezykangielski`, `#fitnesspl`

**TikTok (z SOP + propozycje rozszerzeń):**
- Z SOP: `#biznes`, `#marketing`, `#copywriting`, `#edutok`, `#nauka`, `#rozwojosobisty`
- Propozycje rozszerzeń: `#edukacjapl`, `#storytime`, `#opowiadania`, `#produktywnosc`, `#motywacja`, `#fitnesspolska`

**Decyzja do potwierdzenia z Jankiem:** czy startujemy tylko z hashtagami z SOP (mniejszy zasięg, większa precyzja), czy z poszerzoną listą (większy zasięg, więcej szumu do odsiania)?

---

## 7. Szacunek kosztów Apify

TRZEBA SPRAWDZIĆ aktualne ceny – Apify zmienia cennik. Orientacyjnie:

| Krok                    | Wyniki   | Stawka (orient.) | Koszt orient. |
|-------------------------|----------|------------------|---------------|
| IG hashtag (10×100)     | ~1000    | ~$2 / 1000       | ~$2           |
| IG profile enrichment   | ~400     | ~$5 / 1000       | ~$2           |
| TT hashtag (10×100)     | ~1000    | ~$2 / 1000       | ~$2           |
| TT profile enrichment   | ~400     | ~$5 / 1000       | ~$2           |
| **Suma**                |          |                  | **~$8–15**    |

To jest mało. Nie ma sensu się nad tym pochylać – odpalamy.

---

## 8. Ryzyka i mitygacje

| Ryzyko                                                                 | Prawdop. | Mitygacja                                                          |
|------------------------------------------------------------------------|----------|--------------------------------------------------------------------|
| Apify zwraca niekompletne dane (np. brak bio w części profili)         | Średnia  | Skrypt loguje brakujące pola, profile bez bio → odfiltrowane       |
| TikTok actor mniej stabilny niż IG, czasem rate-limity                 | Wysoka   | Mniejszy `resultsLimit`, retry, akceptujemy mniejszy batch dla TT |
| Heurystyka PL odrzuca pogranicze (np. dwujęzyczne bio)                 | Średnia  | Janek może podać feedback po review, rozluźnimy w v2              |
| "12 ostatnich postów" nie pokrywa 30 dni dla bardzo aktywnych twórców  | Średnia  | Podbicie `resultsLimit` profili do 30                              |
| Apify hashtag scraper zwraca głównie viral posty (≠ mali twórcy)       | Wysoka   | NIE WIEM jak silny ten bias – sprawdzimy po pierwszym runie, ewentualnie zmiana strategii (np. scraping komentujących pod małymi viralami) |
| ToS violation IG/TT                                                    | Znana    | Świadomie akceptowane, single batch, niska skala                  |

---

## 9. Definition of Done

- [ ] 2 pliki XLSX zapisane (`discovery_ig_v1_<data>.xlsx`, `discovery_tt_v1_<data>.xlsx`)
- [ ] Każdy zawiera 30–50 wierszy (jeśli mniej – udokumentowany powód i propozycja rozszerzenia hashtagów)
- [ ] Wszystkie wiersze przechodzą twarde filtry z §4
- [ ] Kolumny zgodne ze schematem z §5
- [ ] Janek otrzymuje pliki przez `present_files` / download w chacie
- [ ] Total czas: <45 min od startu do dostarczenia plików

---

## 10. Kolejne kroki (po review batcha v1 przez Janka)

1. Janek przegląda oba Excele, oznacza 5–10 "trafionych" i 5–10 "spudłowanych" wzorów
2. Na bazie feedbacku doprecyzowujemy filtry (np. blacklist bio, ranges followersów, hashtagi)
3. Decyzja: czy v2 to ten sam jednorazowy skrypt z lepszymi filtrami, czy już port do n8n z cronem tygodniowym
4. Dopiero w v3+ dodajemy LLM scoring i klasyfikację typu

---

## 11. Otwarte pytania do Janka (przed startem v1)

1. Czy hashtagi rozszerzamy poza listę z SOP, czy zaczynamy ściśle z SOP?
2. Czy w `username` jest OK żeby pojawili się też twórcy z bio po angielsku, ale captionami po polsku? (Dziś filtr patrzy tylko na bio – może być zbyt agresywny.)
3. Czy chcesz dostać w XLSX dodatkowo link do **najnowszej** rolki (oprócz top), żebyś od razu mógł sprawdzić aktualną jakość?
4. Czy 50 to twardy cap per platforma, czy jeśli przejdzie 70 dobrych, masz pojemność żeby przejrzeć więcej?
