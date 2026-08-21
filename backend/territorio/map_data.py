"""
Dati per la mappa territoriale: valore commesse REALE per sito (da FactServiceRevenue,
Fase 1) - non un "valore sociale netto" stimato, che non esiste a livello di sito in
questo progetto. La dimensione dei cerchi sulla mappa riflette il valore economico
reale delle commesse, non un impatto sociale inventato.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import month_key, DimSite, DimService, FactServiceRevenue
from territorio.geo import coords_for_comune


def get_sites_map_data(db: Session, year: int = None) -> dict:
    if year is None:
        year = (
            db.query(func.max(FactServiceRevenue.MonthKey)).scalar()
        )
        year = year // 100 if year else None
    else:
        year = int(year)

    rows = (
        db.query(
            DimSite.SiteKey, DimSite.SiteName, DimSite.Comune, DimSite.Provincia,
            DimSite.Regione, DimSite.EnteCommittente,
            func.sum(FactServiceRevenue.RevenueEUR).label("total"),
            func.count(func.distinct(DimService.ServiceCluster)).label("nClusters"),
        )
        .join(FactServiceRevenue, FactServiceRevenue.SiteKey == DimSite.SiteKey)
        .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
        .filter(FactServiceRevenue.MonthKey == month_key(year))
        .group_by(DimSite.SiteKey)
        .all()
    )

    sites = []
    for r in rows:
        coords = coords_for_comune(r.Comune)
        sites.append({
            "siteKey": r.SiteKey,
            "siteName": r.SiteName,
            "comune": r.Comune,
            "provincia": r.Provincia,
            "regione": r.Regione,
            "enteCommittente": r.EnteCommittente,
            "valoreCommesseEUR": r.total,
            "numeroCluster": r.nClusters,
            "lat": coords[0] if coords else None,
            "lon": coords[1] if coords else None,
        })

    sites.sort(key=lambda s: -s["valoreCommesseEUR"])
    return {
        "year": year,
        "sites": sites,
        "sourceNote": (
            "Dimensione dei cerchi = valore commesse reale per sito nell'anno (FactServiceRevenue, "
            "Elenco Servizi). Non è un valore sociale netto: quel dato non esiste a livello di "
            "singolo sito in questo progetto. Coordinate a livello di comune, non catastali."
        ),
    }
