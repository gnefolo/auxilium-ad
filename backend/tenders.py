"""
CRUD per i bandi di gara ATTIVI (`Tender`, vedi database.py) - inseriti e aggiornati
manualmente dall'ufficio gare, o importati da CeBas Basilicata (vedi
cebas_import.py, sempre da verificare). Ogni cambio di Stato viene loggato in
TenderStatusHistory per avere uno storico reale delle transizioni.
"""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database import Tender, TenderStatusHistory

STATI_VALIDI = {"pubbl", "aggiu", "prep", "annul", "sospe"}


def _tender_dict(t: Tender) -> dict:
    try:
        docs = json.loads(t.DocsJSON) if t.DocsJSON else []
    except (TypeError, ValueError):
        docs = []
    return {
        "id": t.id,
        "cig": t.Cig,
        "ref": t.Ref,
        "nome": t.Nome,
        "stazioneAppaltante": t.StazioneAppaltante,
        "settore": t.Settore,
        "importoEUR": t.ImportoEUR,
        "scadenza": t.Scadenza,
        "stato": t.Stato,
        "urgenza": t.Urgenza,
        "note": t.Note,
        "docs": docs,
        "responsabile": t.Responsabile,
        "fonteUrl": t.FonteUrl,
    }


def list_tenders(db: Session) -> list:
    tenders = db.query(Tender).order_by(Tender.id.desc()).all()
    return [_tender_dict(t) for t in tenders]


def get_tender(db: Session, tender_id: int) -> dict:
    t = db.query(Tender).filter(Tender.id == tender_id).first()
    return _tender_dict(t) if t is not None else None


def create_tender(db: Session, payload: dict) -> dict:
    stato = payload.get("stato") or "prep"
    t = Tender(
        Cig=payload.get("cig"),
        Ref=payload.get("ref"),
        Nome=payload.get("nome") or "Nuovo bando",
        StazioneAppaltante=payload.get("stazioneAppaltante"),
        Settore=payload.get("settore"),
        ImportoEUR=payload.get("importoEUR"),
        Scadenza=payload.get("scadenza"),
        Stato=stato if stato in STATI_VALIDI else "prep",
        Urgenza=payload.get("urgenza") or 0,
        Note=payload.get("note"),
        DocsJSON=json.dumps(payload.get("docs") or []),
        Responsabile=payload.get("responsabile"),
        FonteUrl=payload.get("fonteUrl"),
    )
    db.add(t)
    db.commit()
    db.add(TenderStatusHistory(
        TenderId=t.id, OldStato=None, NewStato=t.Stato,
        ChangedAt=datetime.now(timezone.utc).isoformat(), Note="Creazione",
    ))
    db.commit()
    return get_tender(db, t.id)


def update_tender(db: Session, tender_id: int, payload: dict) -> dict:
    t = db.query(Tender).filter(Tender.id == tender_id).first()
    if t is None:
        return None
    for field, attr in [
        ("cig", "Cig"), ("ref", "Ref"), ("nome", "Nome"),
        ("stazioneAppaltante", "StazioneAppaltante"), ("settore", "Settore"),
        ("importoEUR", "ImportoEUR"), ("scadenza", "Scadenza"),
        ("urgenza", "Urgenza"), ("note", "Note"),
        ("responsabile", "Responsabile"), ("fonteUrl", "FonteUrl"),
    ]:
        if field in payload:
            setattr(t, attr, payload[field])
    if "stato" in payload and payload["stato"] in STATI_VALIDI and payload["stato"] != t.Stato:
        old_stato = t.Stato
        t.Stato = payload["stato"]
        db.add(TenderStatusHistory(
            TenderId=t.id, OldStato=old_stato, NewStato=t.Stato,
            ChangedAt=datetime.now(timezone.utc).isoformat(), Note=None,
        ))
    if "docs" in payload:
        t.DocsJSON = json.dumps(payload["docs"] or [])
    db.commit()
    return get_tender(db, tender_id)


def delete_tender(db: Session, tender_id: int) -> None:
    db.query(Tender).filter(Tender.id == tender_id).delete()
    db.query(TenderStatusHistory).filter(TenderStatusHistory.TenderId == tender_id).delete()
    db.commit()


def get_tender_history(db: Session, tender_id: int) -> list:
    rows = (
        db.query(TenderStatusHistory)
        .filter(TenderStatusHistory.TenderId == tender_id)
        .order_by(TenderStatusHistory.id.asc())
        .all()
    )
    return [
        {"id": r.id, "oldStato": r.OldStato, "newStato": r.NewStato, "changedAt": r.ChangedAt, "note": r.Note}
        for r in rows
    ]
