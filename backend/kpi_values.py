"""
CRUD per i valori di KPI di processo/qualità e di volume di servizio inseriti
manualmente per cluster/anno (vedi database.py::ClusterKpiValue), quando il
kpi_catalog.py li segna come "richiede_dati_monitoraggio". Un valore inserito
qui è mostrato nel frontend con una pillola distinta ("Inserito manualmente")
da quelli calcolati da FactServiceRevenue: non viene mai presentato come se
fosse calcolato automaticamente.
"""

from sqlalchemy.orm import Session

from database import ClusterKpiValue


def _value_dict(v: ClusterKpiValue) -> dict:
    return {
        "id": v.id,
        "cluster": v.ServiceCluster,
        "year": v.Year,
        "indicatorId": v.IndicatorId,
        "value": v.Value,
        "note": v.Note,
    }


def list_values(db: Session, cluster: str, year: int) -> list:
    rows = (
        db.query(ClusterKpiValue)
        .filter(ClusterKpiValue.ServiceCluster == cluster, ClusterKpiValue.Year == year)
        .all()
    )
    return [_value_dict(v) for v in rows]


def upsert_value(db: Session, cluster: str, year: int, indicator_id: str, value: str, note: str = None) -> dict:
    row = (
        db.query(ClusterKpiValue)
        .filter(
            ClusterKpiValue.ServiceCluster == cluster,
            ClusterKpiValue.Year == year,
            ClusterKpiValue.IndicatorId == indicator_id,
        )
        .first()
    )
    if row is None:
        row = ClusterKpiValue(ServiceCluster=cluster, Year=year, IndicatorId=indicator_id)
        db.add(row)
    row.Value = value
    row.Note = note
    db.commit()
    return _value_dict(row)
