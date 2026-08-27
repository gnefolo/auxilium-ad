"""
CRUD per i bandi di gara ATTIVI (`Tender`, vedi database.py) - inseriti e aggiornati
manualmente dall'ufficio gare. Nessuna fonte open data italiana offre oggi un feed
affidabile di bandi attivi filtrabile per settore/regione: automazione non ancora
implementata, vedi DEPLOY.md.
"""

import json

from sqlalchemy.orm import Session

from database import Tender

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
    )
    db.add(t)
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
    ]:
        if field in payload:
            setattr(t, attr, payload[field])
    if "stato" in payload and payload["stato"] in STATI_VALIDI:
        t.Stato = payload["stato"]
    if "docs" in payload:
        t.DocsJSON = json.dumps(payload["docs"] or [])
    db.commit()
    return get_tender(db, tender_id)


def delete_tender(db: Session, tender_id: int) -> None:
    db.query(Tender).filter(Tender.id == tender_id).delete()
    db.commit()
