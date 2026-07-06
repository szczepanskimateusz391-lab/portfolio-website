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
http://127.0.0.1:5173/
```

Dostepne skrypty:

- `npm run dev` - uruchamia lokalny serwer developerski na porcie `5173`.
- `npm run build` - kopiuje pliki strony do folderu `dist`.
- `npm run preview` - uruchamia podglad folderu `dist` na porcie `5174`.
