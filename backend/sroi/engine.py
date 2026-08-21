"""
Motore Fase 4: calcola i KPI economici realmente disponibili per cluster di servizio
(da FactServiceRevenue, dati reali dell'Elenco Servizi) e li affianca al catalogo KPI
standardizzato (`kpi_catalog.py`).

I dati di outcome (utenti in carico, ore erogate, valore sociale netto) non esistono
in questo progetto: possono essere inseriti manualmente dall'utente in dashboard
(FactClusterOutcome) - una volta inseriti, costo per utente, costo per ora erogata e
il rapporto SROI si calcolano automaticamente. Il valore sociale netto non è mai
stimato da questo motore: se non viene inserito a mano, il rapporto SROI resta N/D.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import month_key, DimSite, DimService, FactServiceRevenue, FactClusterOutcome
from sroi.kpi_catalog import get_catalog, KPI_STATUS_COMPUTABLE


def compute_cluster_economics(db: Session, cluster: str, year: int) -> dict:
    def revenue_for_year(y: int) -> float:
        total = (
            db.query(func.sum(FactServiceRevenue.RevenueEUR))
            .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
            .filter(DimService.ServiceCluster == cluster, FactServiceRevenue.MonthKey == month_key(y))
            .scalar()
        )
        return total or 0.0

    def count_by_status(status: str) -> int:
        return (
            db.query(func.count(FactServiceRevenue.id))
            .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
            .filter(
                DimService.ServiceCluster == cluster,
                FactServiceRevenue.MonthKey == month_key(year),
                FactServiceRevenue.ContractStatus == status,
            )
            .scalar()
        ) or 0

    current_revenue = revenue_for_year(year)
    previous_revenue = revenue_for_year(year - 1)
    yoy = (current_revenue - previous_revenue) / previous_revenue if previous_revenue else None

    n_active = count_by_status("In essere")
    n_concluded = count_by_status("Concluso")
    n_contracts = n_active + n_concluded

    n_committenti = (
        db.query(func.count(func.distinct(DimSite.EnteCommittente)))
        .join(FactServiceRevenue, FactServiceRevenue.SiteKey == DimSite.SiteKey)
        .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
        .filter(DimService.ServiceCluster == cluster, FactServiceRevenue.MonthKey == month_key(year))
        .scalar()
    ) or 0

    return {
        "cluster": cluster,
        "year": year,
        "valoreCommesseEUR": current_revenue,
        "crescitaYoY": yoy,
        "numeroCommesseAttive": n_active,
        "numeroCommesseConcluse": n_concluded,
        "numeroEntiCommittenti": n_committenti,
        "valoreMedioCommessaEUR": (current_revenue / n_contracts) if n_contracts else None,
    }


def get_cluster_outcome(db: Session, cluster: str, year: int) -> dict:
    row = (
        db.query(FactClusterOutcome)
        .filter(FactClusterOutcome.ServiceCluster == cluster, FactClusterOutcome.Year == year)
        .first()
    )
    if row is None:
        return {"usersServed": None, "hoursDelivered": None, "netSocialValueEUR": None, "note": None}
    return {
        "usersServed": row.UsersServed,
        "hoursDelivered": row.HoursDelivered,
        "netSocialValueEUR": row.NetSocialValueEUR,
        "note": row.Note,
    }


def save_cluster_outcome(db: Session, cluster: str, year: int, users_served, hours_delivered,
                          net_social_value_eur, note: str = None) -> dict:
    row = (
        db.query(FactClusterOutcome)
        .filter(FactClusterOutcome.ServiceCluster == cluster, FactClusterOutcome.Year == year)
        .first()
    )
    if row is None:
        row = FactClusterOutcome(ServiceCluster=cluster, Year=year)
        db.add(row)

    row.UsersServed = users_served
    row.HoursDelivered = hours_delivered
    row.NetSocialValueEUR = net_social_value_eur
    row.Note = note
    db.commit()
    return get_cluster_outcome(db, cluster, year)


def compute_sroi_framework(db: Session, cluster: str, year: int) -> dict:
    economics = compute_cluster_economics(db, cluster, year)
    outcome = get_cluster_outcome(db, cluster, year)
    catalog = get_catalog(cluster)

    valore_commesse = economics["valoreCommesseEUR"]
    costo_per_utente = (
        valore_commesse / outcome["usersServed"]
        if outcome["usersServed"] else None
    )
    costo_per_ora = (
        valore_commesse / outcome["hoursDelivered"]
        if outcome["hoursDelivered"] else None
    )
    sroi_ratio = (
        outcome["netSocialValueEUR"] / valore_commesse
        if (outcome["netSocialValueEUR"] is not None and valore_commesse)
        else None
    )

    # Aggiorna lo stato dei due KPI economici collegati, se l'utente ha inserito i dati.
    for item in catalog["economicKPIs"]:
        if item["id"] == "costo_per_utente" and costo_per_utente is not None:
            item["status"] = KPI_STATUS_COMPUTABLE
        if item["id"] == "costo_per_ora_erogata" and costo_per_ora is not None:
            item["status"] = KPI_STATUS_COMPUTABLE

    if sroi_ratio is not None:
        sroi_status = "Calcolato dal valore sociale netto inserito manualmente - verificarne la fonte prima di pubblicarlo."
    else:
        sroi_status = "N/D - inserire il valore sociale netto per calcolarlo automaticamente"

    return {
        "cluster": cluster,
        "year": year,
        "economics": economics,
        "outcome": outcome,
        "costoPerUtenteEUR": costo_per_utente,
        "costoPerOraErogataEUR": costo_per_ora,
        "kpiCatalog": catalog,
        "sroiRatio": sroi_ratio,
        "netSocialValueEUR": outcome["netSocialValueEUR"],
        "sroiStatus": sroi_status,
        "methodologyNote": (
            "Fase 4 - framework semplificato: il costo dell'investimento (valore commesse, "
            "'economics.valoreCommesseEUR') è reale. Costo/utente, costo/ora erogata e il rapporto "
            "SROI si calcolano automaticamente se gli utenti in carico, le ore erogate o il valore "
            "sociale netto vengono inseriti manualmente (pagina SROI). Il valore sociale netto non è "
            "mai stimato da questa dashboard: chi lo inserisce ne è responsabile."
        ),
    }
