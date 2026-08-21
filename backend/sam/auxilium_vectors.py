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

from sqlalchemy.orm import Session

from database import month_key, FactFinanceMonthly
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
