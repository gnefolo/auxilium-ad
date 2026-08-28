from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Per migrare a Supabase (PostgreSQL), basta cambiare questo URL
# es. SQLALCHEMY_DATABASE_URL = "postgresql://user:password@db.supabase.co:5432/postgres"
SQLALCHEMY_DATABASE_URL = "sqlite:///./auxilium.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def month_key(year: int, month: int = 12) -> int:
    """Chiave DimDate nel formato YYYYMM (es. dicembre 2024 -> 202412)."""
    return year * 100 + month


# ---------------------------------------------------------------------------
# Dimensioni (schema a stella, vedi README.txt in radice del progetto)
# ---------------------------------------------------------------------------

class DimDate(Base):
    __tablename__ = "dim_date"

    MonthKey = Column(Integer, primary_key=True)
    Year = Column(Integer, index=True)
    Month = Column(Integer)
    MonthLabel = Column(String)
    Quarter = Column(Integer)


class DimEntity(Base):
    """Le società/cooperative del gruppo Auxilium (fonte: bilanci)."""
    __tablename__ = "dim_entity"

    EntityKey = Column(String, primary_key=True)
    EntityName = Column(String, index=True)
    LegalForm = Column(String)


class DimSite(Base):
    """Sede/struttura/territorio dove il servizio viene erogato (fonte: Elenco Servizi)."""
    __tablename__ = "dim_site"

    SiteKey = Column(String, primary_key=True)
    SiteName = Column(String, index=True)
    Comune = Column(String)
    Provincia = Column(String)
    Regione = Column(String)
    EnteCommittente = Column(String)


class DimService(Base):
    """Tipologia di servizio erogato, con cluster per l'aggregazione SROI (fonte: Elenco Servizi)."""
    __tablename__ = "dim_service"

    ServiceKey = Column(String, primary_key=True)
    ServiceName = Column(String, index=True)
    ServiceCluster = Column(String, index=True)


class DimScope(Base):
    """Scope emissivo (GHG Protocol). Nessuna fonte dati di carbon footprint oggi: dimensione
    di riferimento pronta, FactCarbonMonthly resta vuota finché non emerge una fonte reale."""
    __tablename__ = "dim_scope"

    ScopeKey = Column(String, primary_key=True)
    ScopeLabel = Column(String)


class DimRiskType(Base):
    """Tipologia di rischio. Nessun registro rischi reale oggi disponibile: dimensione di
    riferimento pronta, FactRiskActions resta vuota finché non emerge una fonte reale."""
    __tablename__ = "dim_risk_type"

    RiskTypeKey = Column(String, primary_key=True)
    RiskLabel = Column(String)


# ---------------------------------------------------------------------------
# Fatti
# ---------------------------------------------------------------------------

class FactFinanceMonthly(Base):
    """Costi/ricavi di bilancio per entità e categoria economica (fonte: bilanci d'esercizio).
    Grana reale: annuale (MonthKey = dicembre dell'anno di bilancio). Popolata in Fase 2:
    è anche la base dei vettori di spesa per il modello SAM (Fase 3)."""
    __tablename__ = "fact_finance_monthly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    MonthKey = Column(Integer, index=True)
    EntityKey = Column(String, index=True)
    CostCategory = Column(String, index=True)
    CostEUR = Column(Float)
    BudgetCostEUR = Column(Float, nullable=True)
    RevenueEUR = Column(Float, nullable=True)


class FactServiceRevenue(Base):
    """Valore delle commesse/servizi per sito e cluster di servizio (fonte: Elenco Servizi
    Auxilium). Grana reale: annuale. Base "Investment Cost" per l'SROI di Fase 4."""
    __tablename__ = "fact_service_revenue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    MonthKey = Column(Integer, index=True)
    SiteKey = Column(String, index=True)
    ServiceKey = Column(String, index=True)
    EntityKey = Column(String, index=True)
    ContractName = Column(String)
    RevenueEUR = Column(Float)
    ContractStatus = Column(String)


class FactImpactMonthly(Base):
    """Indicatori di impatto/SROI per sito e servizio. NetSocialValueEUR/OutcomeAchievedRate
    restano NULL finché il framework SROI (Fase 4) non è validato: non si mostrano numeri di
    valore sociale stimati senza etichettarli esplicitamente come tali."""
    __tablename__ = "fact_impact_monthly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    MonthKey = Column(Integer, index=True)
    SiteKey = Column(String, index=True)
    ServiceKey = Column(String, index=True)
    NetSocialValueEUR = Column(Float, nullable=True)
    InvestmentCostEUR = Column(Float, nullable=True)
    OutcomeAchievedRate = Column(Float, nullable=True)
    UsersServed = Column(Integer, nullable=True)


class FactCarbonMonthly(Base):
    """Emissioni di CO2e per sito/servizio/scope. Tabella creata per compatibilità con lo
    schema del README ma oggi senza alcuna riga: non esiste ancora una fonte dati di
    footprint carbonico in questa cartella."""
    __tablename__ = "fact_carbon_monthly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    MonthKey = Column(Integer, index=True)
    SiteKey = Column(String, index=True)
    ServiceKey = Column(String, index=True)
    ScopeKey = Column(String, index=True)
    Emissions_tCO2e = Column(Float)


class FactRiskActions(Base):
    """Azioni di rischio aperte/scadute per tipologia. Tabella creata per compatibilità con lo
    schema del README ma oggi senza alcuna riga: non esiste ancora un registro rischi reale
    in questa cartella."""
    __tablename__ = "fact_risk_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    MonthKey = Column(Integer, index=True)
    RiskTypeKey = Column(String, index=True)
    ActionsOpen = Column(Integer)
    ActionsOverdue = Column(Integer)


class FactClusterOutcome(Base):
    """Dati di outcome delle commesse ATTIVE inseriti manualmente per cluster/anno
    (Fase 4+): utenti in carico, ore erogate, e le quantità dei benefici monetizzati
    allineati al cluster (`sroi/benefits_catalog.py`), salvate come JSON in
    BenefitQuantitiesJSON ({"<indice beneficio>": quantità}). Il valore sociale netto
    non è mai inventato: viene sempre ricalcolato da queste quantità con la stessa
    metodologia SROI Network usata per i nuovi progetti (`sroi/project_engine.py`),
    non stimato o inserito a mano come numero isolato."""
    __tablename__ = "fact_cluster_outcome"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ServiceCluster = Column(String, index=True)
    Year = Column(Integer, index=True)
    UsersServed = Column(Integer, nullable=True)
    HoursDelivered = Column(Float, nullable=True)
    NetSocialValueEUR = Column(Float, nullable=True)
    BenefitQuantitiesJSON = Column(String, nullable=True)
    Note = Column(String, nullable=True)


# ---------------------------------------------------------------------------
# Calcolo SROI rigoroso (metodologia SROI Network: deadweight/attribution/
# drop-off per singolo beneficio) - progetti creati e gestiti dall'utente in
# dashboard, indipendenti dal framework semplificato per cluster della Fase 4.
# ---------------------------------------------------------------------------

class SroiProject(Base):
    __tablename__ = "sroi_project"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String)
    ServiceCluster = Column(String, nullable=True)
    Status = Column(String, default="In corso")
    Year = Column(Integer)
    DirectBeneficiaries = Column(Integer, nullable=True)
    Description = Column(String, nullable=True)
    Purpose = Column(String, nullable=True)


class SroiProjectCost(Base):
    """Voce di costo diretto del progetto (Personale/Materiali/Spazi e sedi/Altro)."""
    __tablename__ = "sroi_project_cost"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ProjectId = Column(Integer, index=True)
    Category = Column(String)
    AmountEUR = Column(Float)


class SroiBenefit(Base):
    """Beneficio del progetto secondo la metodologia SROI Network: valore netto =
    Quantità x Proxy finanziaria x (1-Deadweight) x Attribution x (1-DropOff)^(anno-1),
    sommato per gli anni di durata."""
    __tablename__ = "sroi_benefit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ProjectId = Column(Integer, index=True)
    Category = Column(String)
    Title = Column(String)
    Stakeholder = Column(String, nullable=True)
    Quantity = Column(Float)
    ProxyValueEUR = Column(Float)
    DurationYears = Column(Integer, default=1)
    DeadweightPct = Column(Float, default=0.0)
    AttributionPct = Column(Float, default=100.0)
    DropoffPct = Column(Float, default=0.0)
    Note = Column(String, nullable=True)


class AppSetting(Base):
    """Preferenze del cruscotto configurabili dall'utente (chiave/valore), es. soglie di
    anomalia e intervallo di auto-refresh - non dati aziendali, solo impostazioni UI/soglie
    applicate a calcoli che restano su dati reali."""
    __tablename__ = "app_setting"

    Key = Column(String, primary_key=True)
    Value = Column(String)


class Tender(Base):
    """Bando/opportunità di gara ATTIVA su cui candidarsi, inserita e aggiornata
    manualmente dall'ufficio gare (o importata da CeBas Basilicata, vedi
    cebas_import.py, sempre da verificare). Distinta da FactServiceRevenue
    (commesse già vinte/storico). EmPULIA non è integrabile: il portale non è
    raggiungibile da richieste automatiche (verificato). CeBas Basilicata non
    ha un filtro per settore/CPV nè espone scadenza/importo via API pubblica -
    vedi nota in DEPLOY.md."""
    __tablename__ = "tender"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Cig = Column(String, nullable=True)
    Ref = Column(String, nullable=True)
    Nome = Column(String)
    StazioneAppaltante = Column(String, nullable=True)
    Settore = Column(String, nullable=True)
    ImportoEUR = Column(Float, nullable=True)
    Scadenza = Column(String, nullable=True)
    Stato = Column(String, default="prep")
    Urgenza = Column(Integer, default=0)
    Note = Column(String, nullable=True)
    DocsJSON = Column(String, nullable=True)
    Responsabile = Column(String, nullable=True)
    FonteUrl = Column(String, nullable=True)


class TenderStatusHistory(Base):
    """Log delle transizioni di stato di una gara (Tender), scritto automaticamente
    da tenders.update_tender() quando il campo Stato cambia - mai inserito a mano."""
    __tablename__ = "tender_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    TenderId = Column(Integer, index=True)
    OldStato = Column(String, nullable=True)
    NewStato = Column(String)
    ChangedAt = Column(String)
    Note = Column(String, nullable=True)


class ClusterKpiValue(Base):
    """Valore di un indicatore di processo/qualità o di volume di servizio
    (kpi_catalog.py) inserito manualmente per cluster/anno, quando il dato di
    monitoraggio operativo non è altrimenti disponibile in questo progetto.
    Non tocca il calcolo SROI (sroi/engine.py): è un dato informativo separato,
    mostrato accanto ai KPI economici reali con una fonte chiaramente distinta."""
    __tablename__ = "cluster_kpi_value"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ServiceCluster = Column(String, index=True)
    Year = Column(Integer, index=True)
    IndicatorId = Column(String, index=True)
    Value = Column(String)
    Note = Column(String, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from seed_data import run_seed
        run_seed(db)
    finally:
        db.close()
