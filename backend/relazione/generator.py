"""
Fase 5: genera una bozza di Relazione Tecnica arricchita con dati reali, per
supportare la candidatura di Auxilium a un bando. Combina:

- Track record: commesse comparabili REALI (stesso cluster, stessa regione se
  indicata) da FactServiceRevenue (Fase 1) - non inventate.
- Stima di impatto macroeconomico (SAM): il budget del bando viene scomposto in
  spesa intermedia stimata e diretta usando i RAPPORTI REALI di Auxilium
  (bilancio 2025: quota di spesa intermedia sul valore della produzione, addetti
  per euro di produzione), poi passato al motore Tipo I/Tipo II (Fase 3). È una
  stima preliminare basata su rapporti aziendali medi, non un piano economico di
  progetto né un impegno occupazionale.
- Framework SROI/KPI di monitoraggio proposto per il cluster (Fase 4): quali
  indicatori si dovrebbero rilevare durante il progetto - nessun outcome sociale
  è stimato prima che il servizio parta.

Nessun numero di questa bozza sostituisce un'analisi economica di progetto vera e
propria: va sempre rivista prima dell'invio a un committente.
"""

from sqlalchemy.orm import Session

from database import month_key, DimDate, DimSite, DimService, FactFinanceMonthly, FactServiceRevenue
from sam.multipliers import compute_indirect_impact
from sam.auxilium_vectors import DIRECT_EMPLOYEES
from sroi.kpi_catalog import get_catalog
from sroi.benefits_catalog import get_cluster_benefits
from sroi.project_engine import get_project as get_sroi_project

# Branca ISTAT (NACE*63) usata per stimare l'impatto SAM di un nuovo progetto nel
# cluster. Coerente con `sam/auxilium_vectors.py`: tutti i cluster su "Assistenza
# sociale", eccetto la fornitura di personale sociosanitario (più vicina a
# "Attività dei servizi sanitari").
CLUSTER_ALLOCATION_BRANCH = {
    "ADI_SAD": "V87_88",
    "RSA_Residenziale": "V87_88",
    "Disabilita": "V87_88",
    "Minori_Famiglia": "V87_88",
    "Migranti_Accoglienza": "V87_88",
    "Prima_Infanzia": "V87_88",
    "Personale_Sociosanitario": "V86",
}

REFERENCE_ENTITY = "AUX"
REFERENCE_YEAR = 2025


def _reference_ratios(db: Session) -> dict:
    """Rapporti reali di Auxilium (bilancio 2025) usati come base per stimare la
    struttura di spesa e occupazionale di un nuovo progetto/bando."""
    def value(category):
        row = (
            db.query(FactFinanceMonthly)
            .filter(
                FactFinanceMonthly.EntityKey == REFERENCE_ENTITY,
                FactFinanceMonthly.MonthKey == month_key(REFERENCE_YEAR),
                FactFinanceMonthly.CostCategory == category,
            )
            .first()
        )
        if row is None:
            return None
        return row.RevenueEUR if row.RevenueEUR is not None else row.CostEUR

    valore_produzione = value("A_ValoreProduzione")
    intermediate = (value("B6_MateriePrime") or 0.0) + (value("B7_Servizi") or 0.0) + (value("B8_GodimentoBeniTerzi") or 0.0)
    employees = DIRECT_EMPLOYEES.get((REFERENCE_ENTITY, REFERENCE_YEAR))

    return {
        "referenceEntity": REFERENCE_ENTITY,
        "referenceYear": REFERENCE_YEAR,
        "intermediateConsumptionRatio": (intermediate / valore_produzione) if valore_produzione else None,
        "employeesPerEuroOutput": (employees / valore_produzione) if (valore_produzione and employees) else None,
    }


def _track_record(db: Session, cluster: str, regione: str = None, limit: int = 8) -> dict:
    q = (
        db.query(
            DimSite.SiteName, DimSite.Regione, DimSite.EnteCommittente,
            FactServiceRevenue.ContractName, FactServiceRevenue.RevenueEUR,
            FactServiceRevenue.ContractStatus, DimDate.Year,
        )
        .join(DimDate, FactServiceRevenue.MonthKey == DimDate.MonthKey)
        .join(DimSite, FactServiceRevenue.SiteKey == DimSite.SiteKey)
        .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
        .filter(DimService.ServiceCluster == cluster)
    )
    if regione:
        q = q.filter(DimSite.Regione == regione)
    rows = q.order_by(DimDate.Year.desc(), FactServiceRevenue.RevenueEUR.desc()).all()

    latest_per_site = {}
    for r in rows:
        key = (r.SiteName, r.ContractName)
        if key not in latest_per_site:
            latest_per_site[key] = r  # righe già ordinate per anno desc: prima occorrenza = più recente

    projects = sorted(latest_per_site.values(), key=lambda r: -r.RevenueEUR)[:limit]
    years = [r.Year for r in rows]

    return {
        "regioneFiltro": regione,
        "numeroCommesseComparabili": len(latest_per_site),
        "anniEsperienza": (max(years) - min(years) + 1) if years else 0,
        "progetti": [
            {
                "sito": r.SiteName, "regione": r.Regione, "enteCommittente": r.EnteCommittente,
                "servizio": r.ContractName, "valoreEUR": r.RevenueEUR, "stato": r.ContractStatus,
                "anno": r.Year,
            }
            for r in projects
        ],
    }


def generate_relazione(db: Session, cluster: str, budget_eur: float, durata_anni: float, regione: str = None,
                        sroi_project_id: int = None) -> dict:
    ratios = _reference_ratios(db)
    track_record = _track_record(db, cluster, regione)

    stima_impatto = None
    if ratios["intermediateConsumptionRatio"] is not None:
        intermediate_estimate = budget_eur * ratios["intermediateConsumptionRatio"]
        direct_output = budget_eur
        direct_value_added = budget_eur - intermediate_estimate
        direct_jobs_estimate = (
            budget_eur * ratios["employeesPerEuroOutput"] if ratios["employeesPerEuroOutput"] else None
        )

        branch = CLUSTER_ALLOCATION_BRANCH.get(cluster, "V87_88")
        impact = compute_indirect_impact(intermediate_estimate, branch_code=branch) if intermediate_estimate > 0 else None

        stima_impatto = {
            "budgetEUR": budget_eur,
            "durataAnni": durata_anni,
            "ipotesi": (
                f"Spesa intermedia stimata al {ratios['intermediateConsumptionRatio'] * 100:.1f}% del budget "
                f"(rapporto acquisti/valore della produzione di Auxilium, bilancio {ratios['referenceYear']}). "
                "Occupazione diretta stimata dal rapporto dipendenti/produzione di Auxilium. Stima preliminare "
                "basata su rapporti aziendali medi, non un piano economico di progetto né un impegno occupazionale."
            ),
            "direct": {
                "outputEUR": direct_output,
                "valueAddedEUR": direct_value_added,
                "jobsEstimate": direct_jobs_estimate,
            },
            "impact": impact,
            "total": {
                "type1_leontief": {
                    "outputEUR": direct_output + impact["type1_leontief"]["deltaOutputEUR"],
                    "valueAddedEUR": direct_value_added + impact["type1_leontief"]["deltaValueAddedEUR"],
                },
                "type2_sam": {
                    "outputEUR": direct_output + impact["type2_sam"]["deltaOutputEUR"],
                    "valueAddedEUR": direct_value_added + impact["type2_sam"]["deltaValueAddedEUR"],
                },
            } if impact else None,
        }

    progetto_sroi_collegato = get_sroi_project(db, sroi_project_id) if sroi_project_id else None

    if progetto_sroi_collegato and progetto_sroi_collegato.get("sroiRatio") is not None:
        sroi_status = (
            f"Stima SROI {progetto_sroi_collegato['sroiRatio']:.2f}x dal progetto collegato "
            f"'{progetto_sroi_collegato['name']}' (pagina 'Calcolo SROI') - stima ex-ante basata su "
            "quantità e ipotesi inserite per questo bando, da rivedere a consuntivo con i dati reali."
        )
    else:
        sroi_status = (
            "N/D - usa la pagina 'Calcolo SROI' per stimare il rapporto SROI di questo progetto a partire "
            "dai benefici allineati al cluster riportati qui sotto ('benefitsCatalog'), poi ricollega il "
            "progetto a questa Relazione (parametro sroi_project_id)."
        )

    return {
        "cluster": cluster,
        "budgetEUR": budget_eur,
        "durataAnni": durata_anni,
        "regione": regione,
        "trackRecord": track_record,
        "stimaImpattoMacroeconomico": stima_impatto,
        "kpiMonitoraggioProposto": get_catalog(cluster),
        "benefitsCatalog": get_cluster_benefits(cluster),
        "progettoSroiCollegato": progetto_sroi_collegato,
        "sroiStatus": sroi_status,
        "noteMetodologiche": (
            "Bozza generata automaticamente. Il track record riflette commesse storiche reali di Auxilium. "
            "La stima di impatto macroeconomico usa un modello Input-Output ISTAT nazionale (Tipo I e Tipo II, "
            "vedi Fase 3) applicato a un budget ipotizzato con i rapporti medi aziendali di Auxilium: non "
            "sostituisce un piano economico di progetto né una valutazione ex-post. I benefici SROI e le "
            "relative proxy finanziarie sono una metodologia di partenza per il cluster (vedi "
            "'benefitsCatalog'): il rapporto SROI del progetto va stimato con quantità reali nella pagina "
            "'Calcolo SROI', non inventato qui."
        ),
    }
