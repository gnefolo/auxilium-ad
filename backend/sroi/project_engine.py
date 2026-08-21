"""
Calcolo SROI rigoroso (metodologia SROI Network - "A Guide to Social Return on
Investment", Nicholls et al.) per progetti creati dall'utente in dashboard.

Per ciascun beneficio, il valore netto attribuibile al progetto è:

    valore_netto = Σ (per anno t = 1..durata) [
        Quantità x Proxy finanziaria x (1 - Deadweight%) x Attribution% x (1 - DropOff%)^(t-1)
    ]

- Deadweight%: quota del risultato che si sarebbe verificata comunque, senza il progetto.
- Attribution%: quota del risultato attribuibile al progetto (e non ad altri attori/fattori).
- Drop-off%: riduzione annua del beneficio negli anni successivi al primo (il beneficio
  tende a scemare nel tempo).

Il rapporto SROI del progetto è: Σ valore_netto dei benefici / Totale investimento
(somma delle voci di costo diretto). Nessun valore di proxy finanziaria è incluso in
questo motore in modo silenzioso: ogni beneficio richiede che l'utente inserisca la
propria proxy (eventualmente partendo dalla libreria di esempio, chiaramente etichettata
come indicativa e da validare).
"""

from sqlalchemy.orm import Session

from database import SroiProject, SroiProjectCost, SroiBenefit
from sroi.benefits_catalog import get_cluster_benefits, CLUSTER_BENEFITS


def compute_benefit_net_value(quantity: float, proxy_eur: float, duration_years: int,
                               deadweight_pct: float, attribution_pct: float, dropoff_pct: float) -> float:
    deadweight = (deadweight_pct or 0.0) / 100.0
    attribution = (attribution_pct if attribution_pct is not None else 100.0) / 100.0
    dropoff = (dropoff_pct or 0.0) / 100.0
    duration = max(int(duration_years or 1), 1)

    base = (quantity or 0.0) * (proxy_eur or 0.0) * (1 - deadweight) * attribution
    return sum(base * ((1 - dropoff) ** t) for t in range(duration))


def _project_dict(p: SroiProject) -> dict:
    return {
        "id": p.id,
        "name": p.Name,
        "serviceCluster": p.ServiceCluster,
        "status": p.Status,
        "year": p.Year,
        "directBeneficiaries": p.DirectBeneficiaries,
        "description": p.Description,
    }


def _cost_dict(c: SroiProjectCost) -> dict:
    return {"id": c.id, "category": c.Category, "amountEUR": c.AmountEUR}


def _benefit_dict(b: SroiBenefit) -> dict:
    net_value = compute_benefit_net_value(
        b.Quantity, b.ProxyValueEUR, b.DurationYears, b.DeadweightPct, b.AttributionPct, b.DropoffPct
    )
    return {
        "id": b.id,
        "category": b.Category,
        "title": b.Title,
        "stakeholder": b.Stakeholder,
        "quantity": b.Quantity,
        "proxyValueEUR": b.ProxyValueEUR,
        "durationYears": b.DurationYears,
        "deadweightPct": b.DeadweightPct,
        "attributionPct": b.AttributionPct,
        "dropoffPct": b.DropoffPct,
        "note": b.Note,
        "netValueEUR": net_value,
    }


def list_projects(db: Session) -> list:
    projects = db.query(SroiProject).order_by(SroiProject.id.desc()).all()
    result = []
    for p in projects:
        costs = db.query(SroiProjectCost).filter(SroiProjectCost.ProjectId == p.id).all()
        benefits = db.query(SroiBenefit).filter(SroiBenefit.ProjectId == p.id).all()
        total_investment = sum(c.AmountEUR or 0.0 for c in costs)
        total_net_value = sum(
            compute_benefit_net_value(b.Quantity, b.ProxyValueEUR, b.DurationYears,
                                       b.DeadweightPct, b.AttributionPct, b.DropoffPct)
            for b in benefits
        )
        row = _project_dict(p)
        row["sroiRatio"] = (total_net_value / total_investment) if total_investment else None
        result.append(row)
    return result


def get_project(db: Session, project_id: int) -> dict:
    p = db.query(SroiProject).filter(SroiProject.id == project_id).first()
    if p is None:
        return None
    costs = db.query(SroiProjectCost).filter(SroiProjectCost.ProjectId == project_id).all()
    benefits = db.query(SroiBenefit).filter(SroiBenefit.ProjectId == project_id).all()

    total_investment = sum(c.AmountEUR or 0.0 for c in costs)
    benefit_rows = [_benefit_dict(b) for b in benefits]
    total_net_value = sum(b["netValueEUR"] for b in benefit_rows)

    result = _project_dict(p)
    result["costs"] = [_cost_dict(c) for c in costs]
    result["totalInvestmentEUR"] = total_investment
    result["benefits"] = benefit_rows
    result["totalNetValueEUR"] = total_net_value
    result["sroiRatio"] = (total_net_value / total_investment) if total_investment else None
    return result


def create_project(db: Session, payload: dict) -> dict:
    p = SroiProject(
        Name=payload.get("name") or "Nuovo progetto",
        ServiceCluster=payload.get("serviceCluster"),
        Status=payload.get("status") or "In corso",
        Year=payload.get("year"),
        DirectBeneficiaries=payload.get("directBeneficiaries"),
        Description=payload.get("description"),
    )
    db.add(p)
    db.commit()
    return get_project(db, p.id)


def update_project(db: Session, project_id: int, payload: dict) -> dict:
    p = db.query(SroiProject).filter(SroiProject.id == project_id).first()
    if p is None:
        return None
    for field, attr in [("name", "Name"), ("serviceCluster", "ServiceCluster"), ("status", "Status"),
                         ("year", "Year"), ("directBeneficiaries", "DirectBeneficiaries"),
                         ("description", "Description")]:
        if field in payload:
            setattr(p, attr, payload[field])
    db.commit()
    return get_project(db, project_id)


def delete_project(db: Session, project_id: int) -> None:
    db.query(SroiBenefit).filter(SroiBenefit.ProjectId == project_id).delete()
    db.query(SroiProjectCost).filter(SroiProjectCost.ProjectId == project_id).delete()
    db.query(SroiProject).filter(SroiProject.id == project_id).delete()
    db.commit()


def add_cost(db: Session, project_id: int, payload: dict) -> dict:
    c = SroiProjectCost(ProjectId=project_id, Category=payload.get("category") or "Altro",
                         AmountEUR=payload.get("amountEUR") or 0.0)
    db.add(c)
    db.commit()
    return get_project(db, project_id)


def update_cost(db: Session, project_id: int, cost_id: int, payload: dict) -> dict:
    c = db.query(SroiProjectCost).filter(SroiProjectCost.id == cost_id, SroiProjectCost.ProjectId == project_id).first()
    if c is None:
        return None
    if "category" in payload:
        c.Category = payload["category"]
    if "amountEUR" in payload:
        c.AmountEUR = payload["amountEUR"]
    db.commit()
    return get_project(db, project_id)


def delete_cost(db: Session, project_id: int, cost_id: int) -> dict:
    db.query(SroiProjectCost).filter(SroiProjectCost.id == cost_id, SroiProjectCost.ProjectId == project_id).delete()
    db.commit()
    return get_project(db, project_id)


def add_benefit(db: Session, project_id: int, payload: dict) -> dict:
    b = SroiBenefit(
        ProjectId=project_id,
        Category=payload.get("category") or "Custom",
        Title=payload.get("title") or "Nuovo beneficio",
        Stakeholder=payload.get("stakeholder"),
        Quantity=payload.get("quantity") or 0.0,
        ProxyValueEUR=payload.get("proxyValueEUR") or 0.0,
        DurationYears=payload.get("durationYears") or 1,
        DeadweightPct=payload.get("deadweightPct") or 0.0,
        AttributionPct=payload.get("attributionPct") if payload.get("attributionPct") is not None else 100.0,
        DropoffPct=payload.get("dropoffPct") or 0.0,
        Note=payload.get("note"),
    )
    db.add(b)
    db.commit()
    return get_project(db, project_id)


def update_benefit(db: Session, project_id: int, benefit_id: int, payload: dict) -> dict:
    b = db.query(SroiBenefit).filter(SroiBenefit.id == benefit_id, SroiBenefit.ProjectId == project_id).first()
    if b is None:
        return None
    field_map = {
        "category": "Category", "title": "Title", "stakeholder": "Stakeholder",
        "quantity": "Quantity", "proxyValueEUR": "ProxyValueEUR", "durationYears": "DurationYears",
        "deadweightPct": "DeadweightPct", "attributionPct": "AttributionPct",
        "dropoffPct": "DropoffPct", "note": "Note",
    }
    for field, attr in field_map.items():
        if field in payload:
            setattr(b, attr, payload[field])
    db.commit()
    return get_project(db, project_id)


def delete_benefit(db: Session, project_id: int, benefit_id: int) -> dict:
    db.query(SroiBenefit).filter(SroiBenefit.id == benefit_id, SroiBenefit.ProjectId == project_id).delete()
    db.commit()
    return get_project(db, project_id)


# Libreria di beneficio per il calcolatore SROI di NUOVI progetti (pagina "Calcolo
# SROI"): a differenza della vecchia libreria generica, è allineata al cluster di
# servizio del progetto e porta proxy finanziarie reali con fonte dichiarata (vedi
# sroi/benefits_catalog.py per la metodologia completa). Restano comunque valori
# di partenza da adattare al progetto specifico, non un dato Auxilium.

def get_benefit_library(cluster: str = None) -> dict:
    """Libreria di benefici per il calcolatore. Se `cluster` è indicato, restituisce
    solo i benefici allineati a quel cluster (con la metodologia relativa); altrimenti
    restituisce l'intera libreria raggruppata per cluster, per un progetto non ancora
    associato a un'area di servizio."""
    if cluster:
        return get_cluster_benefits(cluster)
    return {
        "cluster": None,
        "methodologyNote": (
            "Nessun cluster selezionato per il progetto: qui sotto l'intera libreria "
            "raggruppata per area di servizio. Seleziona un'area di servizio nel progetto "
            "per vedere solo i benefici allineati a quel cluster."
        ),
        "byCluster": {c: get_cluster_benefits(c) for c in CLUSTER_BENEFITS},
    }
