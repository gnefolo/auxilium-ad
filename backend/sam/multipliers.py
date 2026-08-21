"""
Motore di calcolo dei moltiplicatori economici, basato sulla cache costruita da
`build_io_cache.py` a partire dalle tavole ufficiali ISTAT. Due modelli, entrambi
disponibili e restituiti insieme perché il secondo si ottiene "spegnendo" il conto
famiglie del primo:

TIPO I (Leontief, solo produzione):
  A  = matrice dei coefficienti tecnici DOMESTICI (63x63): A[i][j] = quota di input
       dalla branca i acquistata dalla branca j per unità di produzione di j.
  L  = (I - A)^-1
  Dato un vettore di spesa finale f (per branca, milioni di euro - unità ISTAT):
      Δx = L @ f                    (output aggiuntivo per branca)
      ΔVA = va_coeff * Δx           (valore aggiunto aggiuntivo per branca)
      Δore = hours_coeff * Δx       (ore lavorate aggiuntive per branca)
  Non include il giro indotto dei consumi delle famiglie.

TIPO II (SAM, con conto famiglie endogeno - giro indotto):
  Si aggiunge una 64-esima riga/colonna "famiglie" alla matrice A:
    - riga famiglie:    A*[63][j] = redditi da lavoro dipendente generati dalla
                         branca j per unità di produzione di j (quanto reddito
                         "esce" dalla produzione ed entra nelle famiglie)
    - colonna famiglie: A*[i][63] = quota del reddito aggiuntivo delle famiglie che
                         torna in economia come nuova spesa per consumi sulla branca i,
                         già netta di cuneo fiscale/contributivo e risparmio (quanto
                         "rientra" in produzione come domanda aggiuntiva)
  L* = (I - A*)^-1  (64x64)
  Il differenziale Tipo II meno Tipo I isola il puro "effetto indotto" (il giro dei
  consumi delle famiglie che il Tipo I non vede).

Limiti espliciti (dichiarati anche nell'output, non solo qui):
- Tavola nazionale italiana: la propagazione stimata è sull'intera economia italiana,
  non è confinata ai territori dove opera Auxilium (Basilicata/Puglia/Lazio).
- L'allocazione della spesa di Auxilium tra le 63 branche fornitrici non è nota per
  singola fattura: si usa come proxy il mix di acquisti tipico della branca
  fornita (default "Assistenza sociale", V87_88) osservato nella tavola ISTAT stessa -
  un'ipotesi di "tecnologia media di settore", non i fornitori reali di Auxilium.
- Il coefficiente famiglie (cuneo fiscale + propensione al risparmio) usa medie
  nazionali come proxy delle propensioni MARGINALI - prassi standard nei modelli SAM
  semplici, ma resta un'approssimazione (vedi `build_io_cache.py` per le fonti).
- La conversione ore -> posti di lavoro equivalenti usa la media ore/anno per addetto
  osservata nel Bilancio Sociale 2024 di Auxilium (2.426.584,91 ore / 1.597 lavoratori
  = 1.519,5 ore/anno), come proxy applicata all'intera economia: è un'ipotesi dichiarata,
  non una statistica occupazionale nazionale.
"""

import json
from pathlib import Path
from functools import lru_cache

import numpy as np

DATA_DIR = Path(__file__).parent / "data"

# Fonte: Auxilium, Bilancio Sociale 2024 (letto in Fase 2) - 2.426.584,91 ore lavorate
# nel 2024 per 1.597 lavoratori con contratto subordinato al 31/12/2024.
AVG_HOURS_PER_WORKER = 2_426_584.91 / 1597


@lru_cache(maxsize=1)
def load_io_cache(year: int = 2022) -> dict:
    path = DATA_DIR / f"istat_io_{year}.json"
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def leontief_inverse(year: int = 2022) -> np.ndarray:
    cache = load_io_cache(year)
    A = np.array(cache["technical_coefficients_domestic"])
    n = A.shape[0]
    return np.linalg.inv(np.eye(n) - A)


@lru_cache(maxsize=1)
def leontief_inverse_sam(year: int = 2022) -> np.ndarray:
    """Inversa di Leontief della matrice 64x64 (63 branche + conto famiglie)."""
    cache = load_io_cache(year)
    A = np.array(cache["technical_coefficients_domestic"])
    n = A.shape[0]

    A_star = np.zeros((n + 1, n + 1))
    A_star[:n, :n] = A
    A_star[n, :n] = cache["household_income_coefficients"]
    A_star[:n, n] = cache["household_spending_coefficients"]
    # A_star[n, n] = 0: le famiglie non pagano sé stesse.

    return np.linalg.inv(np.eye(n + 1) - A_star)


def sector_average_purchase_mix(branch_code: str, year: int = 2022) -> np.ndarray:
    """Quote (che sommano a 1) del mix di acquisti intermedi tipico della branca
    `branch_code`, desunte dalla sua colonna nella tavola ISTAT (proxy 'tecnologia
    media di settore', vedi limiti nel docstring del modulo)."""
    cache = load_io_cache(year)
    A = np.array(cache["technical_coefficients_domestic"])
    idx = cache["branch_codes"].index(branch_code)
    column = A[:, idx]
    total = column.sum()
    if total == 0:
        raise ValueError(f"Branca {branch_code}: nessun coefficiente di acquisto intermedio in tavola")
    return column / total


def _top_branches(delta_output: np.ndarray, codes: list, names: list, limit: int = 10) -> list:
    return sorted(
        (
            {"code": codes[i], "name": names[i].strip(), "deltaOutputEUR": float(delta_output[i]) * 1_000_000.0}
            for i in range(len(codes))
            if delta_output[i] > 1e-9
        ),
        key=lambda r: -r["deltaOutputEUR"],
    )[:limit]


def compute_indirect_impact(expenditure_eur: float, branch_code: str = "V87_88", year: int = 2022) -> dict:
    """Impatto indiretto (Tipo I) e indotto (Tipo II) generato da una spesa intermedia
    di `expenditure_eur` euro, allocata secondo il mix di acquisti tipico di
    `branch_code`. Restituisce entrambi i modelli così l'"effetto indotto puro" è
    leggibile come differenza tra i due, non nascosto in un solo numero."""
    cache = load_io_cache(year)
    codes = cache["branch_codes"]
    names = cache["branch_names"]
    va_coeff = np.array(cache["value_added_coefficients"])
    hours_coeff = np.array(cache["hours_worked_coefficients_thousands_per_million_eur"])
    n = len(codes)

    mix = sector_average_purchase_mix(branch_code, year)
    # Le tavole ISTAT sono in milioni di euro; la spesa di Auxilium è in euro.
    f = mix * (expenditure_eur / 1_000_000.0)

    # --- Tipo I ---
    L = leontief_inverse(year)
    delta_output_t1 = L @ f
    delta_va_t1 = delta_output_t1 * va_coeff
    delta_hours_t1 = delta_output_t1 * hours_coeff  # migliaia di ore

    # --- Tipo II (SAM, con giro indotto dei consumi delle famiglie) ---
    L_star = leontief_inverse_sam(year)
    f_star = np.concatenate([f, [0.0]])
    delta_x_star = L_star @ f_star
    delta_output_t2 = delta_x_star[:n]
    delta_household_income_induced = float(delta_x_star[n]) * 1_000_000.0
    delta_va_t2 = delta_output_t2 * va_coeff
    delta_hours_t2 = delta_output_t2 * hours_coeff

    def summarize(delta_output, delta_va, delta_hours):
        total_output = float(delta_output.sum()) * 1_000_000.0
        total_va = float(delta_va.sum()) * 1_000_000.0
        total_hours = float(delta_hours.sum()) * 1000.0  # da migliaia a unità
        return {
            "deltaOutputEUR": total_output,
            "deltaValueAddedEUR": total_va,
            "deltaHoursWorked": total_hours,
            "deltaJobsEquivalent": total_hours / AVG_HOURS_PER_WORKER,
            "outputMultiplier": total_output / expenditure_eur if expenditure_eur else None,
        }

    type1 = summarize(delta_output_t1, delta_va_t1, delta_hours_t1)
    type2 = summarize(delta_output_t2, delta_va_t2, delta_hours_t2)

    return {
        "expenditureEUR": expenditure_eur,
        "allocationBranch": branch_code,
        "istatYear": year,
        "type1_leontief": {
            **type1,
            "topSupplierBranches": _top_branches(delta_output_t1, codes, names),
            "note": "Nessun giro indotto dei consumi delle famiglie.",
        },
        "type2_sam": {
            **type2,
            "topSupplierBranches": _top_branches(delta_output_t2, codes, names),
            "inducedHouseholdIncomeEUR": delta_household_income_induced,
            "note": "Include il giro indotto: reddito da lavoro generato -> nuova spesa delle "
                    "famiglie -> ulteriore produzione. Usa cuneo fiscale e propensione al "
                    "risparmio medi nazionali come proxy delle propensioni marginali.",
        },
        "inducedEffectOnly": {
            "deltaOutputEUR": type2["deltaOutputEUR"] - type1["deltaOutputEUR"],
            "deltaValueAddedEUR": type2["deltaValueAddedEUR"] - type1["deltaValueAddedEUR"],
            "deltaJobsEquivalent": type2["deltaJobsEquivalent"] - type1["deltaJobsEquivalent"],
        },
        "methodologyNote": (
            "Modello Input-Output ISTAT nazionale 2022, 63 branche. Tipo I = solo effetto a monte "
            "sui fornitori (Leontief). Tipo II = Tipo I + giro indotto dei consumi delle famiglie "
            "(SAM con conto famiglie endogeno). Allocazione della spesa tra branche fornitrici "
            "stimata con il mix di acquisti medio della branca "
            f"'{names[codes.index(branch_code)].strip()}' - non i fornitori reali di Auxilium. "
            "Conversione ore->posti di lavoro equivalenti basata sulla media ore/anno per addetto "
            "di Auxilium (Bilancio Sociale 2024), applicata come proxy all'intera economia."
        ),
    }
