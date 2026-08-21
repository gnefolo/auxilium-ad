"""
Motore Fase 4 (rivisto): SROI delle commesse ATTIVE di Auxilium, per cluster di
servizio. Diverso dal calcolatore per NUOVI progetti (`project_engine.py`, pagina
"Calcolo SROI"): qui l'investimento è il valore REALE delle commesse del cluster
(da FactServiceRevenue) e i benefici sono quelli allineati al cluster con la
metodologia di monetizzazione (`sroi/benefits_catalog.py`).

Le quantità dei benefici (utenti con RSA evitata, ricoveri evitati, ore di
caregiver risparmiate, ecc.) non sono mai stimate da questo motore: vengono
inserite manualmente in dashboard e salvate in FactClusterOutcome. Se nessuna
quantità è stata inserita per un cluster/anno, il rapporto SROI resta N/D - non
viene mai riempito con un numero non dichiarato.

La "qualità degli indicatori" segnala, per il cluster selezionato, quanta parte
del catalogo KPI standardizzato è oggi calcolabile con dati reali e quanti dei
benefici della metodologia hanno già una quantità reale inserita: una misura di
completezza del monitoraggio, non del valore sociale in sé.
"""

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import month_key, DimSite, DimService, FactServiceRevenue, FactClusterOutcome
from sroi.kpi_catalog import get_catalog, KPI_STATUS_COMPUTABLE
from sroi.benefits_catalog import get_cluster_benefits
from sroi.project_engine import compute_benefit_net_value


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
        return {"usersServed": None, "hoursDelivered": None, "benefitQuantities": {}, "note": None}

    quantities = {}
    if row.BenefitQuantitiesJSON:
        try:
            quantities = json.loads(row.BenefitQuantitiesJSON)
        except (ValueError, TypeError):
            quantities = {}

    return {
        "usersServed": row.UsersServed,
        "hoursDelivered": row.HoursDelivered,
        "benefitQuantities": quantities,
        "note": row.Note,
    }


def save_cluster_outcome(db: Session, cluster: str, year: int, users_served, hours_delivered,
                          benefit_quantities: dict, note: str = None) -> dict:
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
    row.BenefitQuantitiesJSON = json.dumps(benefit_quantities or {})
    row.Note = note
    db.commit()
    return get_cluster_outcome(db, cluster, year)


def _compute_indicator_quality(catalog: dict, benefit_rows: list) -> dict:
    all_kpis = catalog["economicKPIs"] + catalog["processQualityKPIs"] + catalog["serviceVolumeKPIs"]
    kpi_total = len(all_kpis)
    kpi_computable = sum(1 for k in all_kpis if k["status"] == KPI_STATUS_COMPUTABLE)

    benefit_total = len(benefit_rows)
    benefit_with_data = sum(1 for b in benefit_rows if b["quantity"])

    return {
        "kpiCatalogTotal": kpi_total,
        "kpiCatalogComputable": kpi_computable,
        "kpiCatalogPct": (kpi_computable / kpi_total * 100) if kpi_total else 0.0,
        "benefitsTotal": benefit_total,
        "benefitsWithData": benefit_with_data,
        "benefitsPct": (benefit_with_data / benefit_total * 100) if benefit_total else 0.0,
    }


def compute_sroi_framework(db: Session, cluster: str, year: int) -> dict:
    economics = compute_cluster_economics(db, cluster, year)
    outcome = get_cluster_outcome(db, cluster, year)
    catalog = get_catalog(cluster)
    benefit_catalog = get_cluster_benefits(cluster)

    valore_commesse = economics["valoreCommesseEUR"]
    costo_per_utente = (
        valore_commesse / outcome["usersServed"]
        if outcome["usersServed"] else None
    )
    costo_per_ora = (
        valore_commesse / outcome["hoursDelivered"]
        if outcome["hoursDelivered"] else None
    )

    quantities = outcome["benefitQuantities"] or {}
    benefit_rows = []
    any_quantity_entered = False
    total_net_value = 0.0
    for idx, b in enumerate(benefit_catalog["benefits"]):
        qty = quantities.get(str(idx)) or 0.0
        if qty:
            any_quantity_entered = True
        net_value = compute_benefit_net_value(
            qty, b["proxyValueEUR"], 1, b["deadweightPct"], b["attributionPct"], b["dropoffPct"]
        )
        total_net_value += net_value
        benefit_rows.append({**b, "benefitIndex": idx, "quantity": qty, "netValueEUR": net_value})

    net_social_value = total_net_value if any_quantity_entered else None
    sroi_ratio = (total_net_value / valore_commesse) if (any_quantity_entered and valore_commesse) else None

    # Aggiorna lo stato dei due KPI economici collegati, solo su questa copia locale
    # del catalogo (non sugli oggetti globali - vedi fix in kpi_catalog.get_catalog).
    for item in catalog["economicKPIs"]:
        if item["id"] == "costo_per_utente" and costo_per_utente is not None:
            item["status"] = KPI_STATUS_COMPUTABLE
        if item["id"] == "costo_per_ora_erogata" and costo_per_ora is not None:
            item["status"] = KPI_STATUS_COMPUTABLE

    indicator_quality = _compute_indicator_quality(catalog, benefit_rows)

    if sroi_ratio is not None:
        sroi_status = (
            "Calcolato dalle quantità reali inserite per i benefici allineati al cluster, con proxy "
            "finanziarie di metodologia (vedi 'Metodologia di monetizzazione') - non un dato di bilancio."
        )
    else:
        sroi_status = "N/D - inserire almeno una quantità reale per i benefici del cluster per calcolarlo"

    return {
        "cluster": cluster,
        "year": year,
        "economics": economics,
        "outcome": outcome,
        "costoPerUtenteEUR": costo_per_utente,
        "costoPerOraErogataEUR": costo_per_ora,
        "kpiCatalog": catalog,
        "benefitsCatalog": benefit_catalog,
        "benefitRows": benefit_rows,
        "sroiRatio": sroi_ratio,
        "netSocialValueEUR": net_social_value,
        "sroiStatus": sroi_status,
        "indicatorQuality": indicator_quality,
        "methodologyNote": (
            "SROI delle commesse attive: il costo dell'investimento ('economics.valoreCommesseEUR') è "
            "reale, dal valore delle commesse del cluster. Il valore sociale netto si calcola con la "
            "stessa metodologia SROI Network usata per i nuovi progetti (deadweight/attribution/drop-off), "
            "applicata ai benefici allineati al cluster (vedi 'benefitsCatalog'), con le quantità reali "
            "inserite manualmente in dashboard. Nessuna quantità è mai stimata da questa dashboard."
        ),
    }
