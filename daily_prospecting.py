"""Daily, review-only prospect preparation for MS Analytics.

This script reads a manually maintained CSV backlog, skips companies already
present in Google Sheets, prepares up to 10 outreach drafts, and writes them to
the "Master Prospects" and "Daily Prospects" tabs.

It never scrapes LinkedIn, sends email, or performs any LinkedIn action.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import textwrap
import traceback
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


try:
    # Optional for local use. GitHub Actions supplies environment variables
    # directly, so the script still works if python-dotenv is not imported yet.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from google.auth.exceptions import RefreshError
except ImportError:
    # Keep offline dry-runs available before Google dependencies are installed.
    class RefreshError(Exception):
        """Fallback used only when google-auth is not installed."""


MASTER_SHEET = "Master Prospects"
DAILY_SHEET = "Daily Prospects"
DEFAULT_SOURCE_FILE = "prospect_sources.csv"
DEFAULT_LIMIT = 10
MAX_DAILY_PROSPECTS = 10
DEFAULT_TIMEZONE = "Europe/Warsaw"

CASE_STUDY_URL = (
    "https://msanalytics.pl/projects/"
    "power-bi-b2b-crm-performance-dashboard"
)
WEBSITE_URL = "https://msanalytics.pl"

SOURCE_HEADERS = [
    "Company",
    "Industry",
    "Website",
    "SearchPhrase",
    "WhyItFits",
    "OfferIdea",
    "Priority",
    "ProspectType",
]

TRACKER_HEADERS = [
    "Company",
    "Industry",
    "Website",
    "SearchPhrase",
    "WhyItFits",
    "OfferIdea",
    "Priority",
    "ProspectType",
    "LinkedIn Connection Note",
    "Message After Acceptance",
    "Email Subject",
    "Email Body",
    "Follow Up 1",
    "Follow Up 2",
    "Status",
    "Date Added",
    "Next Action",
]

NEXT_ACTION = "Find decision maker on LinkedIn manually"
STATUS = "Do weryfikacji"
REDACTED_VALUE = "[REDACTED]"
SERVICE_ACCOUNT_FIELDS = {
    "auth_provider_x509_cert_url",
    "auth_uri",
    "client_email",
    "client_id",
    "client_x509_cert_url",
    "private_key",
    "private_key_id",
    "project_id",
    "token_uri",
    "type",
    "universe_domain",
}

MALE_VOCATIVE = {
    "Adam": "Adamie",
    "Andrzej": "Andrzeju",
    "Dariusz": "Dariuszu",
    "Dawid": "Dawidzie",
    "Dominik": "Dominiku",
    "Grzegorz": "Grzegorzu",
    "Jacek": "Jacku",
    "Jan": "Janie",
    "Marek": "Marku",
    "Markus": "Markusie",
    "Mateusz": "Mateuszu",
    "Michał": "Michale",
    "Paweł": "Pawle",
    "Piotr": "Piotrze",
    "Rafał": "Rafale",
    "Szymon": "Szymonie",
    "Wiktor": "Wiktorze",
}


class ConfigurationError(RuntimeError):
    """Raised when local or GitHub configuration is incomplete."""


class SheetStructureError(RuntimeError):
    """Raised when the Google Sheet does not match the documented structure."""


def clean_text(value: Any) -> str:
    """Return a safe, single-spaced string."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalized(value: Any) -> str:
    """Normalize text for case-insensitive comparisons."""
    return clean_text(value).casefold()


def shorten(value: Any, width: int) -> str:
    """Shorten text without cutting words in half."""
    text = clean_text(value)
    if not text:
        return ""
    return textwrap.shorten(text, width=width, placeholder="…")


def parse_bool(value: Any) -> bool:
    """Interpret common true/false environment variable values."""
    return normalized(value) in {"1", "true", "yes", "y", "on"}


def service_account_values_to_redact() -> set[str]:
    """Return credential values that must never appear in diagnostics."""
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    values = {raw_json} if raw_json else set()

    try:
        account_info = json.loads(raw_json) if raw_json else {}
    except (json.JSONDecodeError, TypeError):
        account_info = {}

    if isinstance(account_info, dict):
        for field in SERVICE_ACCOUNT_FIELDS:
            value = account_info.get(field)
            if isinstance(value, str) and len(value) >= 4:
                values.add(value)
                # Tracebacks may contain either decoded newlines or JSON escapes.
                values.add(json.dumps(value, ensure_ascii=False)[1:-1])

    return {value for value in values if value}


def redact_sensitive_diagnostics(value: Any) -> str:
    """Remove service-account content while preserving useful error details."""
    safe_text = str(value)

    # Redact exact environment and parsed credential values, longest first.
    for sensitive_value in sorted(
        service_account_values_to_redact(), key=len, reverse=True
    ):
        safe_text = safe_text.replace(sensitive_value, REDACTED_VALUE)

    # Defense in depth for messages that contain only part of a JSON credential.
    credential_fields = "|".join(sorted(SERVICE_ACCOUNT_FIELDS))
    safe_text = re.sub(
        rf'(?is)("(?:{credential_fields})"\s*:\s*")'
        rf'(?:\\.|[^"\\])*(")',
        rf"\1{REDACTED_VALUE}\2",
        safe_text,
    )
    safe_text = re.sub(
        r"(?is)-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----.*?"
        r"-----END(?: [A-Z]+)? PRIVATE KEY-----",
        REDACTED_VALUE,
        safe_text,
    )
    safe_text = re.sub(
        r"(?im)(GOOGLE_SERVICE_ACCOUNT_JSON\s*[:=]\s*).+$",
        rf"\1{REDACTED_VALUE}",
        safe_text,
    )
    return safe_text


def print_exception_diagnostics(error: BaseException) -> None:
    """Print a useful traceback without exposing service-account credentials."""
    exception_name = type(error).__name__
    message = redact_sensitive_diagnostics(str(error)) or "<empty message>"
    full_traceback = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    safe_traceback = redact_sensitive_diagnostics(full_traceback).rstrip()

    print(f"ERROR class: {exception_name}", file=sys.stderr)
    print(f"ERROR message: {message}", file=sys.stderr)
    print(
        "ERROR traceback (service-account values redacted):",
        file=sys.stderr,
    )
    print(safe_traceback, file=sys.stderr)


def normalize_company_name(company: Any) -> str:
    """Create a conservative company key for duplicate detection.

    Punctuation, accents, and common legal suffixes are ignored, so variants
    such as "Example Sp. z o.o." and "example" are treated as one company.
    """
    text = clean_text(company).translate(str.maketrans({"ł": "l", "Ł": "L"}))
    ascii_text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    ).casefold()
    words = re.findall(r"[a-z0-9]+", ascii_text)

    suffix_sequences = [
        ["sp", "z", "o", "o"],
        ["sp", "z", "oo"],
        ["spolka", "z", "ograniczona", "odpowiedzialnoscia"],
        ["s", "a"],
        ["sa"],
        ["ltd"],
        ["limited"],
        ["llc"],
        ["inc"],
        ["gmbh"],
        ["plc"],
    ]
    changed = True
    while changed and words:
        changed = False
        for suffix in suffix_sequences:
            if len(words) >= len(suffix) and words[-len(suffix) :] == suffix:
                words = words[: -len(suffix)]
                changed = True
                break

    return " ".join(words)


def build_salutation(contact_name: Any) -> str:
    """Create a polite Polish greeting with a neutral fallback."""
    contact = clean_text(contact_name)
    if not contact:
        return "Dzień dobry,"

    first_part = contact.split("/")[0].strip()
    words = [
        word.strip(".,")
        for word in first_part.split()
        if word.casefold() not in {"dr", "mgr", "inż.", "inz."}
    ]
    if not words:
        return "Dzień dobry,"

    first_name = words[0]
    role_words = {
        "ceo",
        "founder",
        "owner",
        "director",
        "operations",
        "prezes",
        "właściciel",
    }
    if first_name.casefold() in role_words:
        return "Dzień dobry,"
    if first_name in MALE_VOCATIVE:
        return f"Dzień dobry Panie {MALE_VOCATIVE[first_name]},"
    if first_name.endswith("a") and len(first_name) > 2:
        return f"Dzień dobry Pani {first_name[:-1]}o,"
    return "Dzień dobry,"


def choose_message_angle(industry: Any) -> tuple[str, str]:
    """Choose a restrained subject and reporting angle from the industry."""
    sector = normalized(industry)
    if any(word in sector for word in ("oze", "energi", "pv", "wiatr")):
        return (
            "Dashboard Power BI dla danych sprzedażowych",
            "pipeline ofert i projektów, sprzedaż oraz kluczowe KPI",
        )
    if any(
        word in sector
        for word in (
            "marketing",
            "reklam",
            "lead generation",
            "outbound",
            "event",
            "pr ",
        )
    ):
        return (
            "Krótkie pytanie o raportowanie KPI",
            "wyniki kampanii, leady, klienci i rentowność projektów",
        )
    if any(
        word in sector
        for word in (
            "handel",
            "hurtown",
            "import",
            "dystryb",
            "produkc",
            "żywno",
        )
    ):
        return (
            "Raportowanie sprzedaży i KPI",
            "sprzedaż, marże, klienci i wyniki handlowe",
        )
    if any(word in sector for word in ("szkol", "doradzt", "outsourcing")):
        return (
            "Pytanie o raporty i dane CRM",
            "leady, sprzedaż, realizacja usług i rentowność projektów",
        )
    if any(
        word in sector
        for word in ("crm", "sprzedaż", "automatyz", "information", "it ", "saas")
    ):
        return (
            "Pytanie o raporty i dane CRM",
            "pipeline sprzedaży, dane CRM, klienci i konwersja",
        )
    if any(word in sector for word in ("rekrut", "praca tymczasowa")):
        return (
            "Krótkie pytanie o raportowanie KPI",
            "projekty rekrutacyjne, klienci, kandydaci i marże",
        )
    return (
        "Krótkie pytanie o raportowanie KPI",
        "sprzedaż, klienci, projekty i kluczowe KPI",
    )


def build_linkedin_note(
    contact_name: Any, company: str, industry: Any
) -> str:
    """Generate a LinkedIn connection note below the 200-character limit."""
    salutation = build_salutation(contact_name)
    _, angle = choose_message_angle(industry)
    note = (
        f"{salutation} trafiłem na {company} przy temacie {angle}. "
        "Rozwijam MS Analytics: Power BI i raporty KPI. Chętnie dodam do sieci."
    )
    return textwrap.shorten(note, width=199, placeholder="…")


def build_message_after_acceptance(
    contact_name: Any, company: str, industry: Any
) -> str:
    """Generate a short message intended only for manual use after acceptance."""
    salutation = build_salutation(contact_name)
    _, angle = choose_message_angle(industry)
    return (
        f"{salutation}\n\n"
        "dziękuję za przyjęcie zaproszenia. Rozwijam MS Analytics — tworzę "
        "dashboardy Power BI, raporty KPI i porządkuję dane CRM.\n\n"
        f"Pomyślałem o {company}, bo często można uprościć {angle}.\n\n"
        "Czy mogę podesłać krótką, niezobowiązującą propozycję?"
    )


def build_email_body(
    contact_name: Any,
    company: str,
    industry: Any,
    what_to_offer: Any,
) -> str:
    """Generate a personalized Polish email body below 1200 characters."""
    salutation = build_salutation(contact_name)
    industry_short = shorten(industry, 95) or "Państwa branży"
    offer_short = shorten(what_to_offer, 155)
    _, angle = choose_message_angle(industry)

    if offer_short:
        context = (
            "Pomyślałem, że przydatne może być uporządkowanie obszaru: "
            f"{offer_short.rstrip('.')}."
        )
    else:
        context = (
            f"Pomyślałem, że można uprościć {angle}, jeśli dane są dziś "
            "rozproszone między Excelem, Google Sheets i innymi narzędziami."
        )

    body = (
        f"{salutation}\n\n"
        f"trafiłem na {company}, szukając firm z obszaru {industry_short}.\n\n"
        "Rozwijam MS Analytics — tworzę dashboardy Power BI, raporty KPI oraz "
        "pomagam porządkować dane CRM, sprzedażowe i marketingowe.\n\n"
        f"{context}\n\n"
        "Przykład takiego podejścia pokazuję w krótkim case study:\n"
        f"{CASE_STUDY_URL}\n\n"
        "Mogę bezpłatnie wskazać 2–3 miejsca, które da się uprościć w obecnym "
        "raportowaniu lub pracy z danymi. Czy mogę podesłać krótką propozycję?\n\n"
        "Pozdrawiam\n"
        "Mateusz Szczepański\n"
        "MS Analytics\n"
        f"{WEBSITE_URL}\n\n"
        "Jeśli to nie jest temat dla Państwa, proszę dać znać — nie będę "
        "ponawiać kontaktu."
    )
    if len(body) > 1200:
        raise ValueError(
            f"Email dla firmy {company} przekracza limit 1200 znaków."
        )
    return body


def build_follow_up_1(
    contact_name: Any, company: str, industry: Any
) -> str:
    """Generate a short follow-up for 3–4 days after the first message."""
    salutation = build_salutation(contact_name)
    _, angle = choose_message_angle(industry)
    company_in_sentence = company.rstrip(" .")
    return (
        f"{salutation}\n\n"
        f"wracam krótko do wiadomości o raportowaniu w {company_in_sentence}. "
        f"Jeśli temat taki jak {angle} jest aktualny, mogę bezpłatnie wskazać "
        "2–3 możliwe usprawnienia.\n\n"
        "Czy mogę podesłać krótką propozycję? Jeśli nie, proszę o informację — "
        "nie będę ponawiać kontaktu."
    )


def build_follow_up_2(
    contact_name: Any, company: str, industry: Any
) -> str:
    """Generate a clear final follow-up for 5–7 more days later."""
    salutation = build_salutation(contact_name)
    _, angle = choose_message_angle(industry)
    return (
        f"{salutation}\n\n"
        "to ostatni follow-up z mojej strony. Gdyby w "
        f"{company} pojawił się temat taki jak {angle}, zostawiam przykład:\n"
        f"{CASE_STUDY_URL}\n\n"
        "Jeśli temat nie jest aktualny, nie trzeba odpowiadać — nie będę już "
        "ponawiać kontaktu."
    )


def read_source_csv(path: Path) -> list[dict[str, str]]:
    """Read and validate the manually maintained prospect backlog."""
    if not path.is_file():
        raise FileNotFoundError(f"Nie znaleziono pliku źródłowego: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file)
        headers = [clean_text(header) for header in (reader.fieldnames or [])]
        if headers != SOURCE_HEADERS:
            raise ConfigurationError(
                "prospect_sources.csv musi mieć dokładnie te kolumny i w tej "
                "kolejności: " + ", ".join(SOURCE_HEADERS)
            )

        records: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=2):
            cleaned = {
                header: clean_text(row.get(header, "")) for header in SOURCE_HEADERS
            }
            if not cleaned["Company"] or cleaned["Company"].startswith("#"):
                continue

            missing_fields = [
                header for header in SOURCE_HEADERS if not cleaned[header]
            ]
            if missing_fields:
                raise ConfigurationError(
                    f"Wiersz {row_number} ({cleaned['Company']}) ma puste pola: "
                    + ", ".join(missing_fields)
                )

            if cleaned["Priority"] not in {"A", "B", "C"}:
                raise ConfigurationError(
                    f"Wiersz {row_number}: Priority musi mieć wartość A, B lub C."
                )
            if cleaned["ProspectType"] not in {"Klient", "Partner"}:
                raise ConfigurationError(
                    f"Wiersz {row_number}: ProspectType musi mieć wartość "
                    "Klient lub Partner."
                )
            if not re.match(r"^https?://", cleaned["Website"], re.IGNORECASE):
                raise ConfigurationError(
                    f"Wiersz {row_number}: Website musi być pełnym adresem "
                    "http:// lub https://."
                )
            if "linkedin.com" in normalized(cleaned["Website"]):
                raise ConfigurationError(
                    f"Wiersz {row_number}: Website nie może być adresem LinkedIn."
                )
            if (
                "linkedin" not in normalized(cleaned["SearchPhrase"])
                or "://" in cleaned["SearchPhrase"]
            ):
                raise ConfigurationError(
                    f"Wiersz {row_number}: SearchPhrase musi być zwykłą frazą "
                    "do ręcznego wyszukania na LinkedIn, a nie adresem URL."
                )
            records.append(cleaned)
    return records


def select_new_prospects(
    source_records: Iterable[dict[str, str]],
    existing_company_keys: set[str],
    limit: int,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Select the first unique companies in CSV order, up to the daily limit."""
    seen = set(existing_company_keys)
    eligible: list[dict[str, str]] = []
    duplicate_count = 0

    for record in source_records:
        company_key = normalize_company_name(record.get("Company"))
        if not company_key or company_key in seen:
            duplicate_count += 1
            continue
        seen.add(company_key)
        eligible.append(record)

    selected = eligible[:limit]
    return selected, {
        "duplicates_skipped": duplicate_count,
        "eligible_new": len(eligible),
        "waiting_after_run": max(0, len(eligible) - len(selected)),
    }


def build_tracker_record(
    source: dict[str, str], date_added: date
) -> dict[str, str]:
    """Combine source fields, generated drafts, and review-only status fields."""
    company = clean_text(source.get("Company"))
    industry = clean_text(source.get("Industry"))
    contact_name = ""
    subject, _ = choose_message_angle(industry)

    record = {
        header: clean_text(source.get(header, "")) for header in SOURCE_HEADERS
    }
    record.update(
        {
            "LinkedIn Connection Note": build_linkedin_note(
                contact_name, company, industry
            ),
            "Message After Acceptance": build_message_after_acceptance(
                contact_name, company, industry
            ),
            "Email Subject": subject,
            "Email Body": build_email_body(
                contact_name,
                company,
                industry,
                source.get("OfferIdea"),
            ),
            "Follow Up 1": build_follow_up_1(
                contact_name, company, industry
            ),
            "Follow Up 2": build_follow_up_2(
                contact_name, company, industry
            ),
            "Status": STATUS,
            "Date Added": date_added.isoformat(),
            "Next Action": NEXT_ACTION,
        }
    )
    return record


def column_letter(column_number: int) -> str:
    """Convert a one-based column number to Google Sheets A1 notation."""
    result = ""
    number = column_number
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def quote_sheet_name(sheet_name: str) -> str:
    """Quote a tab name for safe A1 notation."""
    return "'" + sheet_name.replace("'", "''") + "'"


def parse_service_account_json(raw_json: str) -> dict[str, Any]:
    """Parse the JSON secret without ever printing its contents."""
    try:
        account_info = json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise ConfigurationError(
            "GOOGLE_SERVICE_ACCOUNT_JSON nie jest poprawnym JSON-em."
        ) from error

    if not isinstance(account_info, dict):
        raise ConfigurationError(
            "GOOGLE_SERVICE_ACCOUNT_JSON musi zawierać obiekt JSON."
        )
    return account_info


class GoogleSheetsClient:
    """Small wrapper around the official Google Sheets API."""

    def __init__(
        self, spreadsheet_id: str, service_account_info: dict[str, Any]
    ) -> None:
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
        except ImportError as error:
            raise ConfigurationError(
                "Brak bibliotek Google API. Uruchom: "
                "python -m pip install -r requirements.txt"
            ) from error

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(
            service_account_info, scopes=scopes
        )
        self.spreadsheet_id = spreadsheet_id
        self.service = build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )

    def validate_required_tabs(self) -> None:
        """Fail clearly instead of creating or renaming tabs unexpectedly."""
        metadata = (
            self.service.spreadsheets()
            .get(
                spreadsheetId=self.spreadsheet_id,
                fields="sheets.properties.title",
            )
            .execute()
        )
        titles = {
            sheet["properties"]["title"] for sheet in metadata.get("sheets", [])
        }
        missing = {MASTER_SHEET, DAILY_SHEET} - titles
        if missing:
            raise SheetStructureError(
                "Brak wymaganych zakładek: " + ", ".join(sorted(missing))
            )

    def read_master_values(self) -> list[list[str]]:
        """Read the master tracker once for headers and duplicate detection."""
        range_name = f"{quote_sheet_name(MASTER_SHEET)}!A:ZZ"
        response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                majorDimension="ROWS",
            )
            .execute()
        )
        return response.get("values", [])

    def write_selected_prospects(
        self,
        master_values: list[list[str]],
        prepared_records: list[dict[str, str]],
    ) -> None:
        """Clear Daily Prospects and update both tabs using RAW cell values."""
        if master_values:
            master_headers = [clean_text(value) for value in master_values[0]]
            if len(master_headers) != len(set(master_headers)):
                raise SheetStructureError(
                    "Nagłówki Master Prospects zawierają duplikaty."
                )
            missing_headers = [
                header
                for header in TRACKER_HEADERS
                if header not in master_headers
            ]
            if missing_headers:
                raise SheetStructureError(
                    "Master Prospects nie zawiera kolumn: "
                    + ", ".join(missing_headers)
                )
        else:
            master_headers = TRACKER_HEADERS.copy()

        aligned_rows = [
            [record.get(header, "") for header in master_headers]
            for record in prepared_records
        ]
        last_column = column_letter(len(master_headers))

        # Clear values only; existing formatting and column sizing remain intact.
        (
            self.service.spreadsheets()
            .values()
            .batchClear(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "ranges": [
                        f"{quote_sheet_name(DAILY_SHEET)}!A:ZZ"
                    ]
                },
            )
            .execute()
        )

        updates: list[dict[str, Any]] = []
        if not master_values:
            master_rows = [master_headers] + aligned_rows
            updates.append(
                {
                    "range": (
                        f"{quote_sheet_name(MASTER_SHEET)}!"
                        f"A1:{last_column}{len(master_rows)}"
                    ),
                    "majorDimension": "ROWS",
                    "values": master_rows,
                }
            )
        elif aligned_rows:
            start_row = len(master_values) + 1
            end_row = start_row + len(aligned_rows) - 1
            updates.append(
                {
                    "range": (
                        f"{quote_sheet_name(MASTER_SHEET)}!"
                        f"A{start_row}:{last_column}{end_row}"
                    ),
                    "majorDimension": "ROWS",
                    "values": aligned_rows,
                }
            )

        daily_rows = [master_headers] + aligned_rows
        updates.append(
            {
                "range": (
                    f"{quote_sheet_name(DAILY_SHEET)}!"
                    f"A1:{last_column}{len(daily_rows)}"
                ),
                "majorDimension": "ROWS",
                "values": daily_rows,
            }
        )

        (
            self.service.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates,
                },
            )
            .execute()
        )


def existing_company_keys_from_master(
    master_values: list[list[str]],
) -> set[str]:
    """Extract normalized company names from the Master Prospects tab."""
    if not master_values:
        return set()

    headers = [clean_text(value) for value in master_values[0]]
    if len(headers) != len(set(headers)):
        raise SheetStructureError(
            "Nagłówki Master Prospects zawierają duplikaty."
        )
    if "Company" not in headers:
        raise SheetStructureError(
            "Master Prospects musi zawierać kolumnę Company."
        )
    missing_headers = [
        header for header in TRACKER_HEADERS if header not in headers
    ]
    if missing_headers:
        raise SheetStructureError(
            "Master Prospects nie zawiera kolumn: "
            + ", ".join(missing_headers)
        )
    company_index = headers.index("Company")

    result: set[str] = set()
    for row in master_values[1:]:
        if company_index >= len(row):
            continue
        key = normalize_company_name(row[company_index])
        if key:
            result.add(key)
    return result


def resolve_run_date(timezone_name: str) -> date:
    """Return today's date in the configured business timezone."""
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception as error:
        raise ConfigurationError(
            f"Nieprawidłowa strefa czasowa: {timezone_name}"
        ) from error
    return datetime.now(timezone).date()


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments used locally and by GitHub Actions."""
    parser = argparse.ArgumentParser(
        description=(
            "Prepare and add up to 10 prospects to Google Sheets for manual "
            "review. No email or LinkedIn action is performed."
        )
    )
    parser.add_argument(
        "--source",
        default=os.getenv("PROSPECT_SOURCE_FILE", DEFAULT_SOURCE_FILE),
        help="CSV backlog path (default: prospect_sources.csv).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("DAILY_PROSPECT_LIMIT", DEFAULT_LIMIT)),
        help="Number of prospects to select; allowed range: 1–10.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=parse_bool(os.getenv("DRY_RUN", "false")),
        help="Prepare and print a plan without changing Google Sheets.",
    )
    parser.add_argument(
        "--existing-company",
        action="append",
        default=[],
        help=(
            "Treat a company as already present during dry-run. "
            "May be repeated; useful for offline tests."
        ),
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Execute either a safe dry-run or the real Google Sheets update."""
    if not 1 <= args.limit <= MAX_DAILY_PROSPECTS:
        raise ConfigurationError("--limit musi być liczbą od 1 do 10.")

    source_path = Path(args.source).expanduser().resolve()
    source_records = read_source_csv(source_path)
    spreadsheet_id = clean_text(os.getenv("GOOGLE_SHEETS_ID"))
    account_json = clean_text(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))

    client: GoogleSheetsClient | None = None
    master_values: list[list[str]] = []

    if spreadsheet_id and account_json:
        client = GoogleSheetsClient(
            spreadsheet_id, parse_service_account_json(account_json)
        )
        client.validate_required_tabs()
        master_values = client.read_master_values()
    elif spreadsheet_id or account_json:
        raise ConfigurationError(
            "Ustaw oba sekrety: GOOGLE_SHEETS_ID i "
            "GOOGLE_SERVICE_ACCOUNT_JSON."
        )
    elif not args.dry_run:
        raise ConfigurationError(
            "Brak GOOGLE_SHEETS_ID i GOOGLE_SERVICE_ACCOUNT_JSON. "
            "Bez sekretów użyj --dry-run."
        )

    existing_keys = existing_company_keys_from_master(master_values)
    existing_keys.update(
        normalize_company_name(company)
        for company in args.existing_company
        if normalize_company_name(company)
    )

    selected, selection_stats = select_new_prospects(
        source_records, existing_keys, args.limit
    )
    timezone_name = clean_text(
        os.getenv("PROSPECTING_TIMEZONE", DEFAULT_TIMEZONE)
    )
    run_date = resolve_run_date(timezone_name)
    prepared = [
        build_tracker_record(record, run_date) for record in selected
    ]

    if not args.dry_run:
        assert client is not None
        client.write_selected_prospects(master_values, prepared)

    summary = {
        "mode": "DRY RUN" if args.dry_run else "LIVE",
        "source_rows": len(source_records),
        "existing_companies": len(existing_keys),
        "selected": len(prepared),
        **selection_stats,
        "date_added": run_date.isoformat(),
        "companies": [record["Company"] for record in prepared],
    }
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    """Print a compact audit trail without exposing credentials."""
    print(f"Mode: {summary['mode']}")
    print(f"Source rows: {summary['source_rows']}")
    print(f"Existing companies: {summary['existing_companies']}")
    print(f"Duplicates skipped: {summary['duplicates_skipped']}")
    print(f"Eligible new companies: {summary['eligible_new']}")
    print(f"Selected today: {summary['selected']}")
    print(f"Waiting after run: {summary['waiting_after_run']}")
    print(f"Date Added: {summary['date_added']}")
    if summary["companies"]:
        print("Selected companies:")
        for company in summary["companies"]:
            print(f"- {company}")
    else:
        print("Selected companies: none")
    if summary["mode"] == "DRY RUN":
        print("Dry-run complete: Google Sheets was not changed.")
    else:
        print(
            "Google Sheets updated. No email or LinkedIn action was performed."
        )


def main() -> int:
    """CLI entry point with detailed, secret-safe error handling."""
    try:
        summary = run(parse_arguments())
        print_summary(summary)
        return 0
    except RefreshError as error:
        print("ERROR: Google authentication refresh failed.", file=sys.stderr)
        print_exception_diagnostics(error)
        return 1
    except (
        ConfigurationError,
        FileNotFoundError,
        SheetStructureError,
        ValueError,
    ) as error:
        print_exception_diagnostics(error)
        return 1
    except Exception as error:
        print_exception_diagnostics(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
