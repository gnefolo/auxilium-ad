"""
Confronto Auxilium vs media di settore (NACE Q - Sanità e Assistenza Sociale, branche
ISTAT V86 "Attività dei servizi sanitari" + V87_88 "Assistenza sociale" combinate) e
simulatore di scenario per una spesa/investimento aggiuntivo ipotizzato.

A differenza di benchmark tipo "ISTAT/Cerved" (dati di settore proprietari che non sono
disponibili in questo progetto), qui i rapporti di settore sono calcolati DIRETTAMENTE
dalle stesse tavole ISTAT Input-Output già usate per il modello SAM (Fase 3): nessun
numero di settore è inventato. Il limite dichiarato: l'occupazione di settore non è un
dato ISTAT diretto ma una stima (ore lavorate del settore / ore-anno per addetto di
Auxilium, la stessa proxy già usata altrove in questo progetto).
"""

from sqlalchemy.orm import Session

from database import month_key, FactFinanceMonthly
from sam.multipliers import load_io_cache, AVG_HOURS_PER_WORKER
from sam.auxilium_vectors import DIRECT_EMPLOYEES

SECTOR_BRANCHES = ["V86", "V87_88"]  # NACE Q: Sanità e Assistenza Sociale


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


def compute_sector_benchmark(db: Session, entity_key: str = "AUX", year: int = 2025) -> dict:
    cache = load_io_cache()
    codes = cache["branch_codes"]

    output_q = 0.0
    va_q = 0.0
    rlg_q = 0.0
    redditi_lavoro_q = 0.0
    hours_q_thousands = 0.0
    for code in SECTOR_BRANCHES:
        idx = codes.index(code)
        out = cache["output_eur"][idx]
        output_q += out
        va_q += cache["value_added_eur"][idx]
        rlg_q += cache["gross_operating_surplus_eur"][idx]
        redditi_lavoro_q += cache["household_income_coefficients"][idx] * out
        hours_q_thousands += cache["hours_worked_coefficients_thousands_per_million_eur"][idx] * out

    fte_q_estimate = (hours_q_thousands * 1000) / AVG_HOURS_PER_WORKER if hours_q_thousands else None
    output_q_eur = output_q * 1_000_000  # le tavole ISTAT sono in milioni di euro

    sector = {
        "outputEUR": output_q_eur,
        "valueAddedEUR": va_q * 1_000_000,
        "grossOperatingSurplusEUR": rlg_q * 1_000_000,
        "fteEstimate": fte_q_estimate,
        "ricaviPerFTE": (output_q_eur / fte_q_estimate) if fte_q_estimate else None,
        "costoPersonalePctRicavi": (redditi_lavoro_q / output_q) if output_q else None,
        "margineEbitdaPctRicavi": (rlg_q / output_q) if output_q else None,
        "valoreAggiuntoPctRicavi": (va_q / output_q) if output_q else None,
        "ftePerMilioneRicavi": (fte_q_estimate / output_q) if (fte_q_estimate and output_q) else None,
    }

    valore_produzione = _finance_value(db, entity_key, year, "A_ValoreProduzione")
    totale_costi_b = _finance_value(db, entity_key, year, "Totale_CostiProduzione_B")
    ammortamenti = _finance_value(db, entity_key, year, "B10_Ammortamenti") or 0.0
    personale = sum(
        _finance_value(db, entity_key, year, cat) or 0.0
        for cat in ["B9_Personale_Salari", "B9_Personale_OneriSociali", "B9_Personale_TFR",
                    "B9_Personale_TFR_Altri", "B9_Personale_Altri", "B9_Personale_Totale"]
    )
    intermediate = sum(
        _finance_value(db, entity_key, year, cat) or 0.0
        for cat in ["B6_MateriePrime", "B7_Servizi", "B8_GodimentoBeniTerzi"]
    )
    employees = DIRECT_EMPLOYEES.get((entity_key, year))

    ebitda_proxy = (valore_produzione - totale_costi_b + ammortamenti) if (valore_produzione and totale_costi_b is not None) else None
    value_added = (valore_produzione - intermediate) if valore_produzione else None

    auxilium = {
        "outputEUR": valore_produzione,
        "valueAddedEUR": value_added,
        "grossOperatingSurplusEUR": ebitda_proxy,
        "fte": employees,
        "ricaviPerFTE": (valore_produzione / employees) if (valore_produzione and employees) else None,
        "costoPersonalePctRicavi": (personale / valore_produzione) if valore_produzione else None,
        "margineEbitdaPctRicavi": (ebitda_proxy / valore_produzione) if (ebitda_proxy is not None and valore_produzione) else None,
        "valoreAggiuntoPctRicavi": (value_added / valore_produzione) if (value_added is not None and valore_produzione) else None,
        "ftePerMilioneRicavi": (employees / (valore_produzione / 1_000_000)) if (employees and valore_produzione) else None,
    }

    return {
        "entityKey": entity_key,
        "year": year,
        "auxilium": auxilium,
        "sector": sector,
        "sourceNote": (
            "Settore = branche ISTAT V86 'Attività dei servizi sanitari' + V87_88 'Assistenza "
            "sociale' (NACE Q), Sistema di tavole Input-Output ISTAT 2022. L'occupazione di "
            "settore è una stima (ore lavorate del settore / ore-anno per addetto di Auxilium, "
            "Bilancio Sociale 2024), non un dato ISTAT diretto. 'Margine EBITDA' è un proxy "
            "(risultato lordo di gestione per il settore; valore prod. - costi B + ammortamenti "
            "per Auxilium), non un dato di bilancio certificato per il confronto settoriale. "
            "Nessun dato Cerved o di benchmark proprietario è usato: tutto deriva dalle stesse "
            "tavole ISTAT del modello SAM."
        ),
    }
