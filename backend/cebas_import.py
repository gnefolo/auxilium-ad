"""
Import assistito di bandi da CeBas (Portale Bandi della Regione Basilicata) verso
il registro Tender. EmPULIA NON è integrabile: il portale non è raggiungibile da
richieste automatiche (verificato manualmente: connessione rifiutata/timeout sia
con una richiesta diretta sia con un fetch dedicato).

CeBas espone una REST API pubblica di sola lettura (è un sito WordPress) con
titolo/link/date in JSON pulito, ma NON con scadenza/importo (campi JetEngine non
esposti in REST; un'API di gestione interna esiste ma richiede autenticazione).
Scadenza e importo vengono quindi estratti con un parsing testuale mirato della
pagina di dettaglio pubblica (HTML renderizzato lato server, verificato con una
richiesta diretta - non serve un browser headless). Nessun filtro per settore/CPV
esiste sul portale: il filtro qui è per parola chiave nel titolo, impreciso per
natura - ogni bando importato va sempre verificato sulla fonte originale
(campo fonteUrl) prima di considerarlo affidabile.
"""

import html
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import tenders as tenders_engine

CEBAS_API_BASE = "https://portalebandi.regione.basilicata.it/wp-json/wp/v2/avvisi-e-bandi"
CEBAS_MAX_AGE_DAYS = 180

KEYWORDS = [
    "sociale", "sociosanitari", "domiciliare", "disabilit", "minori", "famiglia",
    "anzian", "rsa", "accoglienza", "migrant", "infanzia", "assistenz",
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AuxiliumCruscotto/1.0)"}


def _http_get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_recent_items(max_pages: int = 5) -> list:
    """Scarica gli avvisi CeBas più recenti (per data di modifica), fermandosi a
    max_pages o al primo item più vecchio di CEBAS_MAX_AGE_DAYS - evita di
    scaricare l'intero archivio (~9700 avvisi) a ogni esecuzione."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=CEBAS_MAX_AGE_DAYS)
    items = []
    for page in range(1, max_pages + 1):
        url = f"{CEBAS_API_BASE}?per_page=50&orderby=modified&order=desc&page={page}"
        try:
            raw = _http_get(url)
            batch = json.loads(raw)
        except Exception:
            break
        if not isinstance(batch, list) or not batch:
            break
        stop = False
        for item in batch:
            modified = item.get("modified")
            modified_dt = None
            if modified:
                try:
                    modified_dt = datetime.fromisoformat(modified).replace(tzinfo=timezone.utc)
                except ValueError:
                    modified_dt = None
            if modified_dt and modified_dt < cutoff:
                stop = True
                break
            items.append(item)
        if stop:
            break
    return items


def filter_by_keywords(items: list) -> list:
    """Filtro impreciso per natura: nessun filtro per settore/CPV esiste sul
    portale, quindi si cerca una parola chiave del dominio Auxilium nel titolo."""
    out = []
    for item in items:
        title = (item.get("title") or {}).get("rendered") or ""
        if any(k in title.lower() for k in KEYWORDS):
            out.append(item)
    return out


def parse_detail(url: str) -> dict:
    """Estrae scadenza e importo dalla pagina di dettaglio pubblica (HTML
    server-renderizzato). Se un pattern non trova corrispondenza il campo resta
    vuoto - non si inventa mai un valore.

    Ogni pagina include in fondo un blocco "Avvisi e bandi correlati" con le
    date/importi di ALTRI bandi: senza tagliarlo via, la regex può prendere per
    errore un valore che appartiene a un bando diverso (bug verificato
    direttamente su una pagina reale). Si cerca quindi solo nella parte della
    pagina PRIMA di quel blocco."""
    result = {"scadenza": None, "importoEUR": None}
    try:
        page_html = _http_get(url)
    except Exception:
        return result

    marker = re.search(r"[Aa]vvisi e bandi correlati|data-listing-source=[\"']posts[\"']", page_html)
    if marker:
        page_html = page_html[:marker.start()]

    m = re.search(r"[Dd]ata di scadenza[^0-9]{0,10}(\d{2}/\d{2}/\d{4})", page_html)
    if not m:
        m = re.search(r"[Ss]cadenza[^0-9]{0,10}(\d{2}/\d{2}/\d{4})", page_html)
    if m:
        try:
            result["scadenza"] = datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    m2 = re.search(r"[Ii]mporto[^€]{0,40}€\s*([\d.,]+)", page_html)
    if m2:
        try:
            result["importoEUR"] = float(m2.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return result


def import_new_tenders(db: Session, max_pages: int = 5) -> dict:
    items = fetch_recent_items(max_pages=max_pages)
    candidates = filter_by_keywords(items)
    existing_refs = {t["ref"] for t in tenders_engine.list_tenders(db) if t["ref"]}

    controllati = len(candidates)
    nuovi = 0
    gia_presenti = 0
    for item in candidates:
        ref = f"CEBAS-{item.get('id')}"
        if ref in existing_refs:
            gia_presenti += 1
            continue
        title = html.unescape((item.get("title") or {}).get("rendered") or "Avviso CeBas senza titolo")
        link = item.get("link") or ""
        detail = parse_detail(link) if link else {"scadenza": None, "importoEUR": None}
        tenders_engine.create_tender(db, {
            "nome": title,
            "ref": ref,
            "stazioneAppaltante": "Regione Basilicata",
            "stato": "prep",
            "scadenza": detail["scadenza"],
            "importoEUR": detail["importoEUR"],
            "fonteUrl": link,
            "note": "Importato da CeBas (Basilicata) - verificare sempre sulla fonte originale prima di procedere.",
        })
        existing_refs.add(ref)
        nuovi += 1

    return {"controllati": controllati, "nuovi": nuovi, "giaPresenti": gia_presenti}
