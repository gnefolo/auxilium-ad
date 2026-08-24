from typing import Optional

from fastapi import FastAPI, Depends, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import (
    engine, SessionLocal, init_db, month_key,
    DimDate, DimEntity, DimSite, DimService, DimScope, DimRiskType,
    FactFinanceMonthly, FactServiceRevenue, FactImpactMonthly,
)
from sam.auxilium_vectors import compute_entity_footprint
from sam.benchmark import compute_sector_benchmark
from sam.multipliers import compute_indirect_impact
from sroi.engine import compute_sroi_framework, save_cluster_outcome
from sroi.kpi_catalog import get_catalog as get_sroi_catalog
from sroi import project_engine as sroi_projects
from relazione.generator import generate_relazione
from territorio.map_data import get_sites_map_data
from territorio.anomalie import detect_revenue_anomalies
from auth import create_token, verify_token, check_credentials
import settings as app_settings

app = FastAPI(title="Auxilium Cruscotto Strategico API")

# Initialize SQLite database
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Percorsi accessibili senza token (login stesso + endpoint di servizio/documentazione).
PUBLIC_PATHS = {"/", "/api/auth/login", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def require_auth(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path in PUBLIC_PATHS or not path.startswith("/api/"):
        return await call_next(request)
    authz = request.headers.get("authorization", "")
    token = authz.split(" ", 1)[1] if authz.lower().startswith("bearer ") else None
    if not token or not verify_token(token):
        return JSONResponse(status_code=401, content={"error": "Non autenticato"})
    return await call_next(request)


@app.post("/api/auth/login")
def login(payload: dict = Body(...)):
    username = payload.get("username", "")
    password = payload.get("password", "")
    if check_credentials(username, password):
        return {"token": create_token(username)}
    return JSONResponse(status_code=401, content={"error": "Credenziali non valide"})


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def latest_year_with_revenue(db: Session) -> Optional[int]:
    row = db.query(func.max(DimDate.Year)).join(
        FactServiceRevenue, FactServiceRevenue.MonthKey == DimDate.MonthKey
    ).first()
    return row[0] if row else None


@app.get("/")
def read_root():
    return {"message": "Auxilium Strategic Backend is running. DB is ready."}


@app.get("/api/entities")
def get_entities(db: Session = Depends(get_db)):
    return db.query(DimEntity).all()


@app.get("/api/sites")
def get_sites(db: Session = Depends(get_db)):
    return db.query(DimSite).all()


@app.get("/api/services")
def get_services(db: Session = Depends(get_db)):
    return db.query(DimService).all()


@app.get("/api/service-revenue")
def get_service_revenue(
    year: Optional[int] = Query(None),
    cluster: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = (
        db.query(
            FactServiceRevenue.id,
            DimDate.Year,
            DimSite.SiteName,
            DimSite.Comune,
            DimSite.Regione,
            DimSite.EnteCommittente,
            DimService.ServiceName,
            DimService.ServiceCluster,
            FactServiceRevenue.ContractName,
            FactServiceRevenue.RevenueEUR,
            FactServiceRevenue.ContractStatus,
        )
        .join(DimDate, FactServiceRevenue.MonthKey == DimDate.MonthKey)
        .join(DimSite, FactServiceRevenue.SiteKey == DimSite.SiteKey)
        .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
    )
    if year is not None:
        q = q.filter(DimDate.Year == year)
    if cluster:
        q = q.filter(DimService.ServiceCluster == cluster)

    rows = q.order_by(DimSite.SiteName).all()
    return [
        {
            "id": r.id,
            "year": r.Year,
            "site": r.SiteName,
            "comune": r.Comune,
            "regione": r.Regione,
            "enteCommittente": r.EnteCommittente,
            "service": r.ServiceName,
            "cluster": r.ServiceCluster,
            "contractName": r.ContractName,
            "revenueEUR": r.RevenueEUR,
            "status": r.ContractStatus,
        }
        for r in rows
    ]


@app.get("/api/finance")
def get_finance(
    year: Optional[int] = Query(None),
    entity_key: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Costi di bilancio per entità/categoria. Vuota finché la Fase 2 (innesto dati di
    bilancio) non è completata: il frontend deve gestire una lista vuota mostrando
    'N/D' invece di inventare numeri."""
    q = db.query(
        DimDate.Year,
        FactFinanceMonthly.EntityKey,
        FactFinanceMonthly.CostCategory,
        FactFinanceMonthly.CostEUR,
        FactFinanceMonthly.BudgetCostEUR,
        FactFinanceMonthly.RevenueEUR,
    ).join(DimDate, FactFinanceMonthly.MonthKey == DimDate.MonthKey)

    if year is not None:
        q = q.filter(DimDate.Year == year)
    if entity_key:
        q = q.filter(FactFinanceMonthly.EntityKey == entity_key)

    rows = q.all()
    return [
        {
            "year": r.Year,
            "entityKey": r.EntityKey,
            "costCategory": r.CostCategory,
            "costEUR": r.CostEUR,
            "budgetCostEUR": r.BudgetCostEUR,
            "revenueEUR": r.RevenueEUR,
        }
        for r in rows
    ]


@app.get("/api/impact")
def get_impact(
    cluster: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Aggregazione per cluster di servizio del valore delle commesse (proxy 'Investment
    Cost'), sull'anno più recente disponibile. NetSocialValueEUR/OutcomeAchievedRate
    (SROI vero e proprio) non sono ancora calcolati: il framework è in Fase 4."""
    year = latest_year_with_revenue(db)
    if year is None:
        return {"year": None, "clusters": []}

    q = (
        db.query(
            DimService.ServiceCluster,
            func.sum(FactServiceRevenue.RevenueEUR).label("total"),
            func.count(func.distinct(FactServiceRevenue.SiteKey)).label("nSites"),
        )
        .join(DimDate, FactServiceRevenue.MonthKey == DimDate.MonthKey)
        .join(DimService, FactServiceRevenue.ServiceKey == DimService.ServiceKey)
        .filter(DimDate.Year == year)
    )
    if cluster:
        q = q.filter(DimService.ServiceCluster == cluster)
    q = q.group_by(DimService.ServiceCluster).order_by(func.sum(FactServiceRevenue.RevenueEUR).desc())

    return {
        "year": year,
        "methodologyNote": "Valore commesse (proxy 'Investment Cost'). SROI/valore sociale netto: framework in validazione (Fase 4), non ancora mostrato.",
        "clusters": [
            {"cluster": r.ServiceCluster, "investmentCostEUR": r.total, "sitesCount": r.nSites}
            for r in q.all()
        ],
    }


@app.get("/api/kpis")
def get_kpis(db: Session = Depends(get_db)):
    year = latest_year_with_revenue(db)
    if year is None:
        return {"year": None}

    def revenue_for_year(y: int) -> float:
        total = (
            db.query(func.sum(FactServiceRevenue.RevenueEUR))
            .filter(FactServiceRevenue.MonthKey == month_key(y))
            .scalar()
        )
        return total or 0.0

    current_revenue = revenue_for_year(year)
    previous_revenue = revenue_for_year(year - 1)
    yoy = (
        (current_revenue - previous_revenue) / previous_revenue
        if previous_revenue
        else None
    )

    active_contracts = (
        db.query(func.count(FactServiceRevenue.id))
        .filter(
            FactServiceRevenue.MonthKey == month_key(year),
            FactServiceRevenue.ContractStatus == "In essere",
        )
        .scalar()
    )

    committenti = (
        db.query(func.count(func.distinct(DimSite.EnteCommittente)))
        .join(FactServiceRevenue, FactServiceRevenue.SiteKey == DimSite.SiteKey)
        .filter(FactServiceRevenue.MonthKey == month_key(year))
        .scalar()
    )

    def fact_finance_value(entity_key: str, fin_year: int, category: str) -> Optional[float]:
        row = (
            db.query(FactFinanceMonthly)
            .filter(
                FactFinanceMonthly.EntityKey == entity_key,
                FactFinanceMonthly.MonthKey == month_key(fin_year),
                FactFinanceMonthly.CostCategory == category,
            )
            .first()
        )
        if row is None:
            return None
        return row.RevenueEUR if row.RevenueEUR is not None else row.CostEUR

    # Margine operativo capogruppo (AUX): calcolato solo sull'anno con bilancio
    # civilistico completo (2025) - il Bilancio Sociale 2024 non scorpora i costi B.
    finance_year = 2025
    aux_revenue = fact_finance_value("AUX", finance_year, "A_ValoreProduzione")
    aux_costs_b = fact_finance_value("AUX", finance_year, "Totale_CostiProduzione_B")
    if aux_revenue and aux_costs_b is not None:
        operating_margin_pct = (aux_revenue - aux_costs_b) / aux_revenue * 100
        operating_margin = {
            "value": f"{operating_margin_pct:.1f}%",
            "trend": f"bilancio {finance_year} - solo Auxilium capogruppo",
            "status": "good" if operating_margin_pct >= 0 else "neutral",
        }
    else:
        operating_margin = {
            "value": "N/D",
            "trend": "N/D",
            "status": "neutral",
            "note": "In attesa dell'innesto dei dati di bilancio (Fase 2)",
        }

    return {
        "year": year,
        "totalServiceRevenue": {
            "value": f"€ {current_revenue / 1_000_000:.1f}M",
            "trend": f"{yoy * 100:+.1f}%" if yoy is not None else "N/D",
            "status": "good" if (yoy is not None and yoy >= 0) else "neutral",
        },
        "activeContracts": {
            "value": str(active_contracts or 0),
            "trend": "n/a",
            "status": "neutral",
        },
        "committenti": {
            "value": str(committenti or 0),
            "trend": "n/a",
            "status": "neutral",
        },
        "operatingMargin": operating_margin,
    }


@app.get("/api/sam/benchmark")
def get_sam_benchmark(
    entity_key: str = Query("AUX"),
    year: int = Query(2025),
    db: Session = Depends(get_db),
):
    """Confronto Auxilium vs media di settore (NACE Q), calcolato dalle stesse tavole
    ISTAT del modello SAM - nessun dato di benchmark proprietario/inventato."""
    return compute_sector_benchmark(db, entity_key, year)


@app.get("/api/sam/simulate")
def get_sam_simulate(
    amount_eur: float = Query(...),
    branch_code: str = Query("V87_88"),
):
    """Simulatore di scenario: impatto Tipo I/Tipo II di una spesa/investimento
    aggiuntivo ipotizzato, allocato secondo il mix di acquisti della branca indicata."""
    return compute_indirect_impact(amount_eur, branch_code=branch_code)


@app.get("/api/sam/footprint")
def get_sam_footprint(
    entity_key: str = Query(...),
    year: int = Query(2025),
    db: Session = Depends(get_db),
):
    """Footprint macroeconomico (Fase 3): effetto diretto (dati di bilancio) + effetto
    indiretto (modello Input-Output ISTAT, 'tipo I') di un'entità del gruppo Auxilium."""
    return compute_entity_footprint(db, entity_key, year)


@app.get("/api/sroi/catalog")
def get_sroi_kpi_catalog(cluster: Optional[str] = Query(None)):
    """Catalogo KPI standardizzato per cluster (Fase 4) - riferimento metodologico,
    non richiede dati dal database."""
    return get_sroi_catalog(cluster)


@app.get("/api/sroi/framework")
def get_sroi_framework(
    cluster: str = Query(...),
    year: int = Query(2024),
    db: Session = Depends(get_db),
):
    """Framework SROI semplificato (Fase 4) per un cluster di servizio: KPI economici
    reali + catalogo KPI di outcome/qualità + stato del rapporto SROI (N/D finché non
    vengono inseriti dati di outcome, vedi /api/sroi/outcome)."""
    return compute_sroi_framework(db, cluster, year)


@app.post("/api/sroi/outcome")
def post_sroi_outcome(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    """Salva i dati di outcome inseriti manualmente per le commesse attive di un
    cluster/anno: utenti in carico, ore erogate, e le quantità reali dei benefici
    allineati al cluster (`benefitQuantities`, chiave = indice del beneficio nel
    catalogo). Il valore sociale netto e il rapporto SROI si ricalcolano sempre da
    queste quantità con la metodologia SROI Network - non vengono mai inseriti
    come numero isolato."""
    cluster = payload.get("cluster")
    year = payload.get("year")
    if not cluster or not year:
        return {"error": "cluster e year sono obbligatori"}

    save_cluster_outcome(
        db, cluster, int(year),
        users_served=payload.get("usersServed"),
        hours_delivered=payload.get("hoursDelivered"),
        benefit_quantities=payload.get("benefitQuantities"),
        note=payload.get("note"),
    )
    return compute_sroi_framework(db, cluster, int(year))


@app.get("/api/relazione/genera")
def get_relazione_generata(
    cluster: str = Query(...),
    budget_eur: float = Query(...),
    durata_anni: float = Query(1.0),
    regione: Optional[str] = Query(None),
    sroi_project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Fase 5: bozza di Relazione Tecnica con track record reale, stima di impatto
    SAM (Tipo I/II) e benefici/metodologia SROI allineati al cluster. Se
    `sroi_project_id` è indicato (un progetto creato in 'Calcolo SROI' per questo
    bando), la stima SROI del progetto viene inclusa nella bozza."""
    return generate_relazione(db, cluster, budget_eur, durata_anni, regione, sroi_project_id)


@app.get("/api/sroi/benefits-catalog")
def get_benefits_catalog(cluster: Optional[str] = Query(None)):
    """Libreria di benefici allineata al cluster di servizio, con proxy finanziarie
    e metodologia di monetizzazione (vedi sroi/benefits_catalog.py), per il
    calcolatore SROI di nuovi progetti ('Calcolo SROI') e per la pagina 'SROI'
    (commesse attive). Se `cluster` non è indicato, restituisce l'intera libreria
    raggruppata per cluster."""
    return sroi_projects.get_benefit_library(cluster)


@app.get("/api/sroi/projects")
def get_sroi_projects(db: Session = Depends(get_db)):
    return sroi_projects.list_projects(db)


@app.post("/api/sroi/projects")
def post_sroi_project(payload: dict = Body(...), db: Session = Depends(get_db)):
    return sroi_projects.create_project(db, payload)


@app.get("/api/sroi/projects/{project_id}")
def get_sroi_project(project_id: int, db: Session = Depends(get_db)):
    result = sroi_projects.get_project(db, project_id)
    return result if result else {"error": "Progetto non trovato"}


@app.put("/api/sroi/projects/{project_id}")
def put_sroi_project(project_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    result = sroi_projects.update_project(db, project_id, payload)
    return result if result else {"error": "Progetto non trovato"}


@app.delete("/api/sroi/projects/{project_id}")
def delete_sroi_project(project_id: int, db: Session = Depends(get_db)):
    sroi_projects.delete_project(db, project_id)
    return {"ok": True}


@app.post("/api/sroi/projects/{project_id}/costs")
def post_sroi_cost(project_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    return sroi_projects.add_cost(db, project_id, payload)


@app.put("/api/sroi/projects/{project_id}/costs/{cost_id}")
def put_sroi_cost(project_id: int, cost_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    return sroi_projects.update_cost(db, project_id, cost_id, payload)


@app.delete("/api/sroi/projects/{project_id}/costs/{cost_id}")
def delete_sroi_cost(project_id: int, cost_id: int, db: Session = Depends(get_db)):
    return sroi_projects.delete_cost(db, project_id, cost_id)


@app.post("/api/sroi/projects/{project_id}/benefits")
def post_sroi_benefit(project_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    return sroi_projects.add_benefit(db, project_id, payload)


@app.put("/api/sroi/projects/{project_id}/benefits/{benefit_id}")
def put_sroi_benefit(project_id: int, benefit_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    return sroi_projects.update_benefit(db, project_id, benefit_id, payload)


@app.delete("/api/sroi/projects/{project_id}/benefits/{benefit_id}")
def delete_sroi_benefit(project_id: int, benefit_id: int, db: Session = Depends(get_db)):
    return sroi_projects.delete_benefit(db, project_id, benefit_id)


@app.get("/api/territorio/mappa")
def get_territorio_mappa(year: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """Dati mappa territoriale: valore commesse reale per sito (Fase 1), non un
    valore sociale stimato che non esiste a livello di sito."""
    return get_sites_map_data(db, year)


@app.get("/api/territorio/anomalie")
def get_territorio_anomalie(db: Session = Depends(get_db)):
    """Rilevamento anomalie su deviazioni reali dei ricavi delle commesse rispetto
    alla media storica (non un'analisi di outcome/valore sociale). Le soglie sono
    configurabili nella pagina Impostazioni (vedi /api/settings)."""
    s = app_settings.get_settings(db)
    return detect_revenue_anomalies(db, s["anomalia_soglia_attenzione"], s["anomalia_soglia_critico"])


@app.get("/api/settings")
def get_app_settings(db: Session = Depends(get_db)):
    """Preferenze del cruscotto (soglie di anomalia, intervallo di auto-refresh)."""
    return app_settings.get_settings(db)


@app.put("/api/settings")
def put_app_settings(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Salva le preferenze del cruscotto."""
    return app_settings.save_settings(db, payload)


if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8005)))
