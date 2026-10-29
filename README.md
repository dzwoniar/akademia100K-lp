# Akademia100K-lp — dokumentacja koncepcji

Repozytorium ma historyczny opis prototypu landing page, ale jego bieżąca zawartość obejmuje dokument planistyczny **Discovery PL Creators v1** oraz pusty plik `TRASH`. Nie zawiera obecnie kodu strony ani aplikacji do uruchomienia.

## Zawartość

| Plik | Rola |
| --- | --- |
| [docs/discovery-pl-creators-v1.md](docs/discovery-pl-creators-v1.md) | Zachowany w całości wcześniejszy README: PRD procesu wyszukiwania twórców |
| [TRASH](TRASH) | Pusty plik pozostały po zmianie nazwy dawnego `index.html` |
| [README.md](README.md) | Przegląd aktualnego stanu repozytorium |

## Zakres dokumentu projektowego

PRD opisuje plan pozyskania profili z Instagrama i TikToka: discovery, uzupełnienie danych, deduplikację, filtrowanie i eksport wyników do dwóch plików XLSX. Wskazuje proponowane usługi Apify i dalsze przetwarzanie w Pythonie.

```text
Plan: dane z Apify → deduplikacja i filtry w Pythonie → eksport XLSX → ręczny przegląd
```

To opis zamierzonego procesu. Repozytorium nie zawiera skryptów pobierania, konfiguracji actorów, implementacji filtrów, eksportera ani wynikowych arkuszy. Nazwy usług, schematy danych, kryteria i szacunki kosztów w PRD są historycznymi założeniami do weryfikacji przed implementacją.

## Jak przeglądać

Otwórz [dokument PRD](docs/discovery-pl-creators-v1.md) bezpośrednio na GitHubie albo sklonuj repozytorium:

```sh
git clone https://github.com/dzwoniar/akademia100K-lp.git
cd akademia100K-lp
```

Wystarczy edytor Markdown. Nie ma zależności do instalacji, zmiennych środowiskowych ani komendy startowej. Uruchomienie serwera HTTP nie odtworzy wcześniejszej strony: w aktualnej wersji nie ma `index.html`.

## Dalsza praca

Przed implementacją trzeba wybrać zakres: przywrócenie landing page albo rozwój procesu discovery opisanego w PRD. Dopiero dodanie kodu pozwoli określić wymagania środowiska i instrukcję uruchomienia. W repozytorium nie ma obecnie testów automatycznych ani procesu budowania.
