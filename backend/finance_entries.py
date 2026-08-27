"""
CRUD per le voci di FactFinanceMonthly (vedi database.py) inserite manualmente
dall'ufficio amministrativo quando arrivano nuovi dati di bilancio (grana annuale,
MonthKey = dicembre dell'anno). Prima di questo modulo la tabella era scrivibile
solo modificando seed_data.py e rifacendo il deploy - qui si chiude quel gap.
"""

from sqlalchemy.orm import Session

from database import FactFinanceMonthly, month_key


def _entry_dict(f: FactFinanceMonthly) -> dict:
    return {
        "id": f.id,
        "year": f.MonthKey // 100,
        "entityKey": f.EntityKey,
        "costCategory": f.CostCategory,
        "costEUR": f.CostEUR,
        "budgetCostEUR": f.BudgetCostEUR,
        "revenueEUR": f.RevenueEUR,
    }


def list_finance_entries(db: Session, year: int = None, entity_key: str = None) -> list:
    query = db.query(FactFinanceMonthly)
    if year is not None:
        query = query.filter(FactFinanceMonthly.MonthKey == month_key(year))
    if entity_key is not None:
        query = query.filter(FactFinanceMonthly.EntityKey == entity_key)
    rows = query.order_by(FactFinanceMonthly.id.desc()).all()
    return [_entry_dict(f) for f in rows]


def get_finance_entry(db: Session, entry_id: int) -> dict:
    f = db.query(FactFinanceMonthly).filter(FactFinanceMonthly.id == entry_id).first()
    return _entry_dict(f) if f is not None else None


def create_finance_entry(db: Session, payload: dict) -> dict:
    year = payload.get("year")
    f = FactFinanceMonthly(
        MonthKey=month_key(int(year)) if year else None,
        EntityKey=payload.get("entityKey"),
        CostCategory=payload.get("costCategory"),
        CostEUR=payload.get("costEUR"),
        BudgetCostEUR=payload.get("budgetCostEUR"),
        RevenueEUR=payload.get("revenueEUR"),
    )
    db.add(f)
    db.commit()
    return get_finance_entry(db, f.id)


def update_finance_entry(db: Session, entry_id: int, payload: dict) -> dict:
    f = db.query(FactFinanceMonthly).filter(FactFinanceMonthly.id == entry_id).first()
    if f is None:
        return None
    if "year" in payload and payload["year"]:
        f.MonthKey = month_key(int(payload["year"]))
    for field, attr in [
        ("entityKey", "EntityKey"), ("costCategory", "CostCategory"),
        ("costEUR", "CostEUR"), ("budgetCostEUR", "BudgetCostEUR"),
        ("revenueEUR", "RevenueEUR"),
    ]:
        if field in payload:
            setattr(f, attr, payload[field])
    db.commit()
    return get_finance_entry(db, entry_id)


def delete_finance_entry(db: Session, entry_id: int) -> None:
    db.query(FactFinanceMonthly).filter(FactFinanceMonthly.id == entry_id).delete()
    db.commit()
