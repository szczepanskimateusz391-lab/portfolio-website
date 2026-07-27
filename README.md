# Mateusz Szczepanski Portfolio Website

Statyczna strona portfolio dla freelancera Data Analytics & Business Automation, przygotowana pod pozyskiwanie klientow B2B.

## Zakres strony

- krotki hero section z jasnym CTA,
- prawdziwy screenshot projektu w hero,
- 4 karty uslug: Dashboard Development, CRM Data Cleanup, Business Automation, KPI Reporting,
- case studies opisane jako projekty portfolio,
- klikalne screenshoty projektow z modalem/lightboxem,
- sekcja "O mnie" ze zdjeciem profilowym,
- favicon `MS`,
- ciemny profesjonalny styl, hover effects i responsywnosc mobile,
- SEO: title, description, Open Graph, canonical i JSON-LD.

## Technologie pokazane na stronie

- Google Sheets
- Microsoft Excel
- Power Query
- Google Apps Script

## Przed publikacja

1. W `index.html` podmien:
   - `twoj-email@example.com` na wlasciwy adres e-mail,
   - `LINKEDIN_URL` w `script.js` na profil LinkedIn,
   - `https://twojadomena.pl/` na docelowa domene.
2. Screenshoty i zdjecie profilowe sa w folderze `assets`.
3. Strone mozna opublikowac na GitHub Pages, Netlify, Vercel albo klasycznym hostingu statycznym.

## Lokalny podglad

Projekt jest statyczna strona HTML/CSS/JS. Nie wymaga Vite ani instalowania zaleznosci.

```bash
npm run dev
```

Domyslny adres lokalny:

```text
https://msanalytics.pl
```

Dostepne skrypty:

- `npm run dev` - uruchamia lokalny serwer developerski na porcie `5173`.
- `npm run build` - kopiuje pliki strony do folderu `dist`.
- `npm run preview` - uruchamia podglad folderu `dist` na porcie `5174`.

## Daily prospecting automation

Repozytorium zawiera również bezpieczny workflow CSV → Google Sheets do
codziennego przygotowywania maksymalnie 10 prospektów:

- `daily_prospecting.py` — skrypt Python,
- `prospect_sources.csv` — ręcznie zweryfikowana baza kandydatów,
- `requirements.txt` — zależności Pythona,
- `.env.example` — przykładowa konfiguracja bez sekretów,
- `.github/workflows/daily-prospecting.yml` — harmonogram GitHub Actions.

Workflow nie wysyła e-maili ani wiadomości LinkedIn i nie wykonuje żadnych
automatycznych działań na LinkedIn. Generuje teksty wyłącznie do ręcznej
weryfikacji.

### Działanie

Podczas każdego uruchomienia skrypt:

1. czyta `prospect_sources.csv`,
2. pobiera istniejące firmy z zakładki `Master Prospects`,
3. pomija duplikaty,
4. wybiera maksymalnie 10 kolejnych firm według kolejności w CSV,
5. przygotowuje polskie teksty outreach do ręcznej weryfikacji,
6. dopisuje rekordy do `Master Prospects`,
7. odświeża zakładkę `Daily Prospects`.

Status nowych rekordów to `Do weryfikacji`, a następna czynność to
`Find decision maker on LinkedIn manually`.

### Konfiguracja Google Sheets

Arkusz musi zawierać dwie zakładki o dokładnych nazwach:

- `Master Prospects`
- `Daily Prospects`

Jeśli `Master Prospects` zawiera już dane, pierwszy wiersz musi zawierać
następujące unikalne nagłówki:

```text
Company
Industry
Website
SearchPhrase
WhyItFits
OfferIdea
Priority
ProspectType
LinkedIn Connection Note
Message After Acceptance
Email Subject
Email Body
Follow Up 1
Follow Up 2
Status
Date Added
Next Action
```

W Google Cloud należy włączyć Google Sheets API i utworzyć konto serwisowe.
Arkusz trzeba udostępnić adresowi `client_email` tego konta z rolą edytora.

W ustawieniach GitHub Actions należy dodać dwa sekrety:

- `GOOGLE_SHEETS_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

Nie należy commitować pliku `.env` ani klucza JSON konta serwisowego.

### Format `prospect_sources.csv`

Plik musi zachować dokładnie tę kolejność kolumn:

```csv
Company,Industry,Website,SearchPhrase,WhyItFits,OfferIdea,Priority,ProspectType
```

`Priority` przyjmuje wartości `A`, `B` lub `C`, a `ProspectType` — `Klient`
lub `Partner`. `Website` musi być zwykłym adresem strony firmy. `SearchPhrase`
jest tekstową frazą do ręcznego wyszukania i nie może być adresem LinkedIn.

### Test lokalny

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --requirement requirements.txt
python daily_prospecting.py --dry-run
```

Dry-run bez sekretów działa całkowicie lokalnie i niczego nie zapisuje do
Google Sheets.

### GitHub Actions

Workflow uruchamia się codziennie o `06:15 UTC` oraz może być uruchomiony
ręcznie przez `Actions → Daily Prospecting → Run workflow`. Przed pierwszym
uruchomieniem produkcyjnym warto zaznaczyć opcję `dry_run`.
