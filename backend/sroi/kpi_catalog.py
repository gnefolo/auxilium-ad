"""
Catalogo KPI standardizzato per cluster di servizio (Fase 4).

Fonte per gli indicatori di processo/qualità e per gli indicatori di volume di
servizio: "Relazione Tecnica" (gara PNRR M5C2, Auxilium/Iskra, 23.05.2025, letta in
questo progetto), sezioni "Sistema di monitoraggio e valutazione" e "Modalità di
valutazione del grado di soddisfazione dell'utenza" - sono indicatori che Auxilium
GIÀ usa operativamente nel proprio Sistema di Gestione Qualità (UNI EN ISO 9001),
qui standardizzati per cluster di servizio invece che descritti come testo libero
per singola gara.

Nessun valore di questi indicatori è popolato per le singole commesse: i dati di
monitoraggio (ore erogate, piani individuali attivi, turnover, ecc. per sito/anno)
non sono disponibili in questo progetto - vivono nel sistema di gestione operativa
di Auxilium. Il catalogo serve a: 1) standardizzare cosa tracciare per costruire in
futuro un SROI robusto, comune a tutti i cluster; 2) rendere visibile subito cosa si
può calcolare oggi (KPI economici, da FactServiceRevenue) e cosa manca (KPI di
outcome) - senza mai riempire il vuoto con un numero stimato non dichiarato.
"""

import copy

KPI_STATUS_COMPUTABLE = "calcolabile_oggi"
KPI_STATUS_PENDING = "richiede_dati_monitoraggio"

ALL_CLUSTERS = [
    "ADI_SAD", "RSA_Residenziale", "Disabilita", "Minori_Famiglia",
    "Migranti_Accoglienza", "Prima_Infanzia", "Personale_Sociosanitario",
]

# Il "piano individuale" è l'unità di misura del volume di servizio nella Relazione
# Tecnica, con nomenclatura diversa per area (PAI per assistenza, PEI per l'area
# minori/educativa). Per i cluster non coperti dalla Relazione Tecnica letta, la
# nomenclatura è segnata "da adattare": è un'ipotesi di lavoro, non un dato Auxilium.
INDIVIDUAL_PLAN_LABEL = {
    "ADI_SAD": "PAI (Piano Assistenziale Individualizzato)",
    "RSA_Residenziale": "PAI (Piano Assistenziale Individualizzato)",
    "Disabilita": "PAI (Piano Assistenziale Individualizzato)",
    "Minori_Famiglia": "PEI (Piano Educativo Individualizzato)",
    "Migranti_Accoglienza": "Piano di accoglienza individuale (da adattare)",
    "Prima_Infanzia": "Piano educativo del nido (da adattare)",
    "Personale_Sociosanitario": "Non applicabile - fornitura di personale, non presa in carico individuale",
}

ECONOMIC_KPIS = [
    dict(id="valore_commesse_anno", nome="Valore commesse (anno)", unita="EUR",
         definizione="Somma del valore delle commesse del cluster nell'anno",
         fonte="FactServiceRevenue", status=KPI_STATUS_COMPUTABLE),
    dict(id="numero_commesse_attive", nome="Numero commesse attive", unita="n.",
         definizione="Commesse con stato 'In essere' nell'anno",
         fonte="FactServiceRevenue", status=KPI_STATUS_COMPUTABLE),
    dict(id="numero_commesse_concluse", nome="Numero commesse concluse", unita="n.",
         definizione="Commesse con stato 'Concluso' nell'anno",
         fonte="FactServiceRevenue", status=KPI_STATUS_COMPUTABLE),
    dict(id="numero_enti_committenti", nome="Numero enti committenti", unita="n.",
         definizione="Enti committenti distinti nel cluster",
         fonte="FactServiceRevenue / DimSite", status=KPI_STATUS_COMPUTABLE),
    dict(id="valore_medio_commessa", nome="Valore medio commessa", unita="EUR",
         definizione="Valore commesse anno / numero commesse anno",
         fonte="FactServiceRevenue", status=KPI_STATUS_COMPUTABLE),
    dict(id="crescita_yoy", nome="Crescita valore commesse YoY", unita="%",
         definizione="Variazione % del valore commesse rispetto all'anno precedente",
         fonte="FactServiceRevenue", status=KPI_STATUS_COMPUTABLE),
    dict(id="costo_per_utente", nome="Costo per utente", unita="EUR/utente",
         definizione="Valore commessa / utenti in carico",
         fonte="FactServiceRevenue + monitoraggio", status=KPI_STATUS_PENDING),
    dict(id="costo_per_ora_erogata", nome="Costo per ora erogata", unita="EUR/ora",
         definizione="Valore commessa / ore erogate",
         fonte="FactServiceRevenue + monitoraggio", status=KPI_STATUS_PENDING),
]

# Le 5 fasi del percorso di presa in carico individuale (valutazione iniziale -> piano
# -> erogazione -> verifica -> outcome), usate per raggruppare visivamente il catalogo
# KPI in una pipeline (pagina SROI). Non è un dato Auxilium: è una lettura del
# ciclo di presa in carico già implicito nella Relazione Tecnica (PAI/PEI, VMD,
# monitoraggio, verifica obiettivi), qui resa esplicita per organizzare il catalogo.
FASE_VALUTAZIONE = "valutazione_iniziale"
FASE_PIANIFICAZIONE = "pianificazione"
FASE_EROGAZIONE = "erogazione"
FASE_VERIFICA = "verifica"

FASE_LABELS = {
    FASE_VALUTAZIONE: "Valutazione iniziale",
    FASE_PIANIFICAZIONE: "Pianificazione (PAI/PEI)",
    FASE_EROGAZIONE: "Erogazione",
    FASE_VERIFICA: "Verifica obiettivi",
}
FASE_ORDER = [FASE_VALUTAZIONE, FASE_PIANIFICAZIONE, FASE_EROGAZIONE, FASE_VERIFICA]

# Fonte: Relazione Tecnica, tabella "Qualità organizzativa e gestionale" (indicatori
# di processo comuni a tutti i cluster, non specifici di un servizio).
PROCESS_QUALITY_KPIS = [
    dict(id="puntualita_turni", nome="Puntualità invio turni di servizio", unita="%",
         definizione="Quota di prospetti turno inviati con più di 2 giorni di ritardo",
         targetRiferimento="< 10%", status=KPI_STATUS_PENDING, fase=FASE_EROGAZIONE),
    dict(id="puntualita_report", nome="Puntualità invio report mensili", unita="%",
         definizione="Quota di report mensili pervenuti entro il 5 del mese successivo",
         targetRiferimento="1° anno > 95%, poi 100%", status=KPI_STATUS_PENDING, fase=FASE_VERIFICA),
    dict(id="tempi_presa_in_carico", nome="Tempi di presa in carico", unita="ore",
         definizione="Tempo tra formalizzazione del piano individuale e avvio effettivo",
         targetRiferimento="< 24h urgenze, < 72h standard", status=KPI_STATUS_PENDING, fase=FASE_VALUTAZIONE),
    dict(id="assenteismo", nome="Assenteismo operatori", unita="%",
         definizione="Ore di assenza sulle ore teoriche programmate",
         targetRiferimento="< 10%", status=KPI_STATUS_PENDING, fase=FASE_EROGAZIONE),
    dict(id="turnover_operatori", nome="Turnover operatori", unita="%",
         definizione="Operatori usciti nel periodo su organico a inizio periodo",
         targetRiferimento="< 15% primo anno, < 10% successivi", status=KPI_STATUS_PENDING, fase=FASE_EROGAZIONE),
    dict(id="formazione", nome="Formazione operatori", unita="%",
         definizione="Operatori con formazione prevista completata sul totale operatori",
         targetRiferimento="> 90%", status=KPI_STATUS_PENDING, fase=FASE_EROGAZIONE),
    dict(id="customer_satisfaction", nome="Customer satisfaction", unita="indice",
         definizione="Questionario di soddisfazione utenza/committente (qualità percepita vs attesa)",
         status=KPI_STATUS_PENDING, fase=FASE_VERIFICA),
]

# Fonte: Relazione Tecnica, tabella "Indicatori quantitativi" (volume di servizio).
SERVICE_VOLUME_KPIS = [
    dict(id="piani_individuali_attivi", nome="Piani individuali attivi", unita="n.",
         definizione="Numero di piani individuali attivi - volume del servizio reso",
         status=KPI_STATUS_PENDING, fase=FASE_PIANIFICAZIONE),
    dict(id="tasso_copertura_utenza", nome="Tasso di copertura utenza", unita="%",
         definizione="Piani attivi rispetto all'utenza potenziale del territorio",
         status=KPI_STATUS_PENDING, fase=FASE_PIANIFICAZIONE),
    dict(id="durata_media_piano", nome="Durata media del piano individuale", unita="giorni",
         definizione="Periodo medio di assistenza assicurato per utente",
         status=KPI_STATUS_PENDING, fase=FASE_PIANIFICAZIONE),
    dict(id="ore_erogate", nome="Ore erogate", unita="ore",
         definizione="Ore di servizio erogate, totali e per tipologia di attività",
         status=KPI_STATUS_PENDING, fase=FASE_EROGAZIONE),
    dict(id="tempo_attesa_avvio", nome="Tempo medio di attesa per l'avvio del servizio", unita="giorni",
         definizione="Tempo tra richiesta e avvio effettivo dell'intervento",
         status=KPI_STATUS_PENDING, fase=FASE_VALUTAZIONE),
    dict(id="collaborazioni_rete_territoriale", nome="Collaborazioni con la rete territoriale", unita="n.",
         definizione="Numero di collaborazioni attive con associazioni/enti del territorio",
         status=KPI_STATUS_PENDING, fase=FASE_VERIFICA),
]


def get_catalog(cluster: str = None) -> dict:
    # Copie profonde: chi consuma questo catalogo (es. sroi/engine.py) aggiorna lo
    # stato "calcolabile_oggi" dei singoli KPI in base ai dati disponibili per una
    # specifica richiesta cluster/anno - senza copiare, quella mutazione si
    # propagherebbe permanentemente a tutte le richieste successive (bug corretto).
    return {
        "cluster": cluster,
        "individualPlanLabel": INDIVIDUAL_PLAN_LABEL.get(cluster) if cluster else None,
        "economicKPIs": copy.deepcopy(ECONOMIC_KPIS),
        "processQualityKPIs": copy.deepcopy(PROCESS_QUALITY_KPIS),
        "serviceVolumeKPIs": copy.deepcopy(SERVICE_VOLUME_KPIS),
        "faseOrder": FASE_ORDER,
        "faseLabels": FASE_LABELS,
        "sourceNote": (
            "Indicatori di processo/qualità e di volume di servizio ripresi dal sistema di "
            "monitoraggio già in uso da Auxilium (Relazione Tecnica, gara PNRR M5C2, 23.05.2025), "
            "qui standardizzati per cluster invece che descritti per singola gara. Nessun valore è "
            "popolato: i dati di monitoraggio operativo reali (ore erogate, piani attivi, turnover "
            "per sito/anno) non sono disponibili in questo progetto."
        ),
    }
