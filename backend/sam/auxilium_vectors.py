"""
Costruisce il vettore di spesa di un'entità del gruppo Auxilium a partire da
FactFinanceMonthly (dati di bilancio, Fase 2) e lo passa al motore di moltiplicatori
(`multipliers.py`) per stimare il footprint macroeconomico (Fase 3), sia Tipo I
(solo fornitori) sia Tipo II (con giro indotto dei consumi delle famiglie).

Effetto diretto: la produzione, il valore aggiunto e l'occupazione della stessa
entità Auxilium (dati di bilancio reali, nessuna stima - "employees" è un conteggio
esatto da bilancio, non un equivalente stimato).
Effetto indiretto/indotto: prodotto dal motore IO/SAM su una spesa per acquisti
intermedi (B6+B7+B8); l'occupazione indiretta è una stima in "posti di lavoro
equivalenti" (vedi `multipliers.py` per il metodo di conversione ore->posti), non
un conteggio - va sempre presentata come tale.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import month_key, FactFinanceMonthly, FactServiceRevenue, DimService
from sam.multipliers import compute_indirect_impact

# Occupati (numero medio dichiarato a bilancio, Fase 2) - effetto diretto noto con
# certezza, non richiede il motore IO. "N/D" quando il bilancio letto non riporta il dato
# (es. bozza senza Nota Integrativa).
DIRECT_EMPLOYEES = {
    ("AUX", 2025): 825,
    ("AUX", 2024): 1597,  # Bilancio Sociale 2024: lavoratori con contratto subordinato al 31.12, non "numero medio"
    ("PHY", 2025): 8,
    ("CARE", 2025): 116,
    ("SRV", 2025): None,  # bozza senza Nota Integrativa: dato non disponibile
}

# Branca ISTAT (NACE*63) usata come proxy del mix di acquisti di ciascuna entità.
# Tutte le entità del gruppo operano in servizi socio-assistenziali/sociosanitari:
# si usa "Assistenza sociale" (V87_88) per tutte finché non emerga una ragione per
# differenziare (es. Physioclinic, fisioterapia, potrebbe in futuro usare V86).
ALLOCATION_BRANCH = {
    "AUX": "V87_88",
    "PHY": "V87_88",
    "CARE": "V87_88",
    "SRV": "V87_88",
}

# Branca ISTAT per cluster di servizio (usata sia qui per il footprint reale di
# cluster, sia in relazione/generator.py per la stima di impatto di un nuovo bando -
# unica fonte per evitare che le due mappature divergano nel tempo).
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


def _finance_value(db: Session, entity_key: str, year: int, category: str):
    row = (
        db.query(FactFinanceMonthly)
        .filter(
            FactFinanceMonthly.EntityKey == entity_key,
            FactFinanceMonthly.MonthKey == month_key(year),
            FactFinanceMonthly.CostCategory == category,
        )
        .first()
    )
    if row is None:
        return None
    return row.RevenueEUR if row.RevenueEUR is not None else row.CostEUR


def compute_entity_footprint(db: Session, entity_key: str, year: int) -> dict:
    direct_output = _finance_value(db, entity_key, year, "A_ValoreProduzione")
    b6 = _finance_value(db, entity_key, year, "B6_MateriePrime") or 0.0
    b7 = _finance_value(db, entity_key, year, "B7_Servizi") or 0.0
    b8 = _finance_value(db, entity_key, year, "B8_GodimentoBeniTerzi") or 0.0
    intermediate_consumption = b6 + b7 + b8

    if direct_output is None:
        return {
            "entityKey": entity_key,
            "year": year,
            "error": "Nessun dato di bilancio (FactFinanceMonthly) per questa entità/anno",
        }

    direct_value_added = direct_output - intermediate_consumption
    direct_employees = DIRECT_EMPLOYEES.get((entity_key, year))

    result = {
        "entityKey": entity_key,
        "year": year,
        "direct": {
            "outputEUR": direct_output,
            "valueAddedEUR": direct_value_added,
            "employees": direct_employees,
            "employeesNote": "Conteggio esatto da bilancio, non una stima.",
            "intermediateConsumptionEUR": intermediate_consumption,
        },
        "impact": None,
        "total": None,
    }

    if intermediate_consumption > 0:
        branch = ALLOCATION_BRANCH.get(entity_key, "V87_88")
        impact = compute_indirect_impact(intermediate_consumption, branch_code=branch)
        result["impact"] = impact
        result["total"] = {
            "type1_leontief": {
                "outputEUR": direct_output + impact["type1_leontief"]["deltaOutputEUR"],
                "valueAddedEUR": direct_value_added + impact["type1_leontief"]["deltaValueAddedEUR"],
                "jobsEquivalent_indirectOnly": impact["type1_leontief"]["deltaJobsEquivalent"],
            },
            "type2_sam": {
                "outputEUR": direct_output + impact["type2_sam"]["deltaOutputEUR"],
                "valueAddedEUR": direct_value_added + impact["type2_sam"]["deltaValueAddedEUR"],
                "jobsEquivalent_indirectPlusInduced": impact["type2_sam"]["deltaJobsEquivalent"],
            },
            "note": "'jobsEquivalent' è una stima in posti di lavoro equivalenti (vedi metodologia "
                    "in multipliers.py), da non confondere con 'employees' (conteggio esatto diretto).",
        }

    return result


def _reference_ratios(db: Session) -> dict:
    """Rapporti reali di Auxilium (bilancio capogruppo) usati come proxy della struttura
    di spesa/occupazionale quando non abbiamo un bilancio separato per cluster di
    servizio (i bilanci sono per entità legale, non per cluster)."""
    valore_produzione = _finance_value(db, REFERENCE_ENTITY, REFERENCE_YEAR, "A_ValoreProduzione")
    intermediate = (
        (_finance_value(db, REFERENCE_ENTITY, REFERENCE_YEAR, "B6_MateriePrime") or 0.0)
        + (_finance_value(db, REFERENCE_ENTITY, REFERENCE_YEAR, "B7_Servizi") or 0.0)
        + (_finance_value(db, REFERENCE_ENTITY, REFERENCE_YEAR, "B8_GodimentoBeniTerzi") or 0.0)
    )
    employees = DIRECT_EMPLOYEES.get((REFERENCE_ENTITY, REFERENCE_YEAR))
    return {
        "intermediateConsumptionRatio": (intermediate / valore_produzione) if valore_produzione else None,
        "employeesPerEuroOutput": (employees / valore_produzione) if (valore_produzione and employees) else None,
    }


def compute_cluster_footprint(db: Session, cluster: str, year: int) -> dict:
    """Impatto macroeconomico di un cluster di servizio, usando il valore REALE delle
    commesse del cluster nell'anno (FactServiceRevenue) come base - a differenza di
    relazione/generator.py, che stima l'impatto di un budget IPOTETICO per un nuovo
    bando non ancora vinto. Stessa metodologia: spesa intermedia stimata dai rapporti
    aziendali medi di Auxilium capogruppo (i bilanci non sono disponibili per singolo
    cluster), poi passata al motore Input-Output ISTAT (Tipo I/Tipo II, Fase 3)."""
    revenue = (
        db.query(func.sum(FactServiceRevenue.RevenueEUR))
        .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
        .filter(DimService.ServiceCluster == cluster, FactServiceRevenue.MonthKey == month_key(year))
        .scalar()
    ) or 0.0

    result = {"cluster": cluster, "year": year, "valoreCommesseEUR": revenue, "impact": None, "total": None}
    ratios = _reference_ratios(db)
    if not revenue or ratios["intermediateConsumptionRatio"] is None:
        return result

    intermediate_estimate = revenue * ratios["intermediateConsumptionRatio"]
    direct_value_added = revenue - intermediate_estimate
    direct_jobs_estimate = (
        revenue * ratios["employeesPerEuroOutput"] if ratios["employeesPerEuroOutput"] else None
    )

    branch = CLUSTER_ALLOCATION_BRANCH.get(cluster, "V87_88")
    impact = compute_indirect_impact(intermediate_estimate, branch_code=branch) if intermediate_estimate > 0 else None

    result["ipotesi"] = (
        f"Spesa intermedia stimata al {ratios['intermediateConsumptionRatio'] * 100:.1f}% del valore delle "
        f"commesse del cluster (rapporto acquisti/valore della produzione di Auxilium capogruppo, bilancio "
        f"{REFERENCE_YEAR}). Occupazione diretta stimata dallo stesso rapporto dipendenti/produzione - una "
        "stima sui rapporti aziendali medi, non un conteggio reale per questo specifico cluster."
    )
    result["direct"] = {
        "outputEUR": revenue, "valueAddedEUR": direct_value_added, "jobsEstimate": direct_jobs_estimate,
    }
    result["impact"] = impact
    if impact:
        result["total"] = {
            "type1_leontief": {
                "outputEUR": revenue + impact["type1_leontief"]["deltaOutputEUR"],
                "valueAddedEUR": direct_value_added + impact["type1_leontief"]["deltaValueAddedEUR"],
            },
            "type2_sam": {
                "outputEUR": revenue + impact["type2_sam"]["deltaOutputEUR"],
                "valueAddedEUR": direct_value_added + impact["type2_sam"]["deltaValueAddedEUR"],
            },
        }
    return result
