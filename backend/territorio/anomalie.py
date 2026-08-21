"""
Rilevamento anomalie: confronta il valore dell'ultimo anno di ciascuna commessa con la
media degli anni precedenti (dati REALI, FactServiceRevenue) e segnala deviazioni
superiori a una soglia. Non stima outcome/valore sociale (non disponibili per
commessa): rileva solo deviazioni economiche reali, con azioni suggerite generiche
(template), non un'analisi di causa specifica che questo progetto non può conoscere.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import DimDate, DimSite, DimService, FactServiceRevenue

SOGLIA_ATTENZIONE = 0.20   # 20%
SOGLIA_CRITICO = 0.45      # 45%


def _severity(deviation_pct: float) -> str:
    if abs(deviation_pct) >= SOGLIA_CRITICO:
        return "CRITICO"
    if abs(deviation_pct) >= SOGLIA_ATTENZIONE:
        return "ATTENZIONE"
    return "OK"


def _suggested_actions(deviation_pct: float) -> list:
    if deviation_pct <= -SOGLIA_ATTENZIONE:
        return [
            "Verificare se la commessa è stata rinegoziata, ridotta o è in fase di chiusura.",
            "Controllare se manca una fattura/rendicontazione dell'ultimo anno (possibile errore di trascrizione).",
        ]
    if deviation_pct >= SOGLIA_ATTENZIONE:
        return [
            "Verificare se l'aumento deriva da un ampliamento del servizio o da un nuovo affidamento aggiuntivo.",
            "Controllare che l'importo non includa arretrati di anni precedenti contabilizzati nell'ultimo anno.",
        ]
    return []


def detect_revenue_anomalies(db: Session) -> dict:
    rows = (
        db.query(
            FactServiceRevenue.SiteKey, FactServiceRevenue.ServiceKey,
            DimSite.SiteName, DimSite.Regione, DimService.ServiceName, DimService.ServiceCluster,
            DimDate.Year, FactServiceRevenue.RevenueEUR, FactServiceRevenue.ContractStatus,
        )
        .join(DimDate, FactServiceRevenue.MonthKey == DimDate.MonthKey)
        .join(DimSite, FactServiceRevenue.SiteKey == DimSite.SiteKey)
        .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
        .order_by(FactServiceRevenue.SiteKey, FactServiceRevenue.ServiceKey, DimDate.Year)
        .all()
    )

    by_contract = {}
    for r in rows:
        key = (r.SiteKey, r.ServiceKey)
        by_contract.setdefault(key, []).append(r)

    anomalies = []
    for (site_key, service_key), contract_rows in by_contract.items():
        if len(contract_rows) < 3:
            continue  # serve storico sufficiente per una media significativa
        contract_rows.sort(key=lambda r: r.Year)
        *history, last = contract_rows
        avg_history = sum(r.RevenueEUR for r in history) / len(history)
        if avg_history == 0:
            continue
        deviation_pct = (last.RevenueEUR - avg_history) / avg_history
        severity = _severity(deviation_pct)
        if severity == "OK":
            continue

        anomalies.append({
            "siteKey": site_key,
            "siteName": last.SiteName,
            "regione": last.Regione,
            "serviceName": last.ServiceName,
            "cluster": last.ServiceCluster,
            "year": last.Year,
            "actualEUR": last.RevenueEUR,
            "historicalAverageEUR": avg_history,
            "deviationPct": deviation_pct,
            "severity": severity,
            "status": last.ContractStatus,
            "suggestedActions": _suggested_actions(deviation_pct),
        })

    anomalies.sort(key=lambda a: -abs(a["deviationPct"]))
    return {
        "anomalies": anomalies,
        "thresholds": {"attenzione": SOGLIA_ATTENZIONE, "critico": SOGLIA_CRITICO},
        "sourceNote": (
            "Analisi statistica su dati REALI (FactServiceRevenue, Elenco Servizi): confronta "
            "l'ultimo anno di ciascuna commessa con la media degli anni precedenti. Non misura "
            "outcome o valore sociale (non disponibili per commessa in questo progetto). Le azioni "
            "suggerite sono generiche: questo strumento non conosce la causa reale della variazione."
        ),
    }
