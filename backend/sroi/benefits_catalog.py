"""
Metodologia di monetizzazione SROI per cluster di servizio (metodologia SROI Network:
deadweight/attribution/drop-off, vedi `project_engine.py`).

Per ciascun cluster sono identificati 2-3 benefici materiali e più defendibili (non un
elenco esaustivo: è un punto di partenza curato, estendibile con "+ Custom" nel
calcolatore). Ogni beneficio ha una proxy finanziaria con fonte dichiarata e un livello
di confidenza:

  ALTA    = costo standard/tariffario verificabile (RSA, DRG ospedalieri, comunità
            minori, spesa per studente, costo orario assistenza familiare)
  MEDIA   = stima da letteratura economica consolidata ma da tarare sul contesto
            specifico (es. reddito da occupazione abilitata dal nido)
  BASSA   = proxy internazionali di benessere (es. banche di proxy UK come HACT/Social
            Value UK) usati in assenza di un databank italiano equivalente - da
            validare con particolare cautela prima di presentarli come dato consolidato

Nessun valore qui è un dato Auxilium: sono proxy di letteratura/tariffario nazionale,
punto di partenza per il calcolo - le quantità (utenti, ricoveri evitati, ore, ecc.)
vanno sempre inserite con dati reali o stime esplicitamente dichiarate come tali.
"""

CONFIDENCE_HIGH = "ALTA"
CONFIDENCE_MEDIUM = "MEDIA"
CONFIDENCE_LOW = "BASSA"


def _benefit(category, title, stakeholder, unit, proxy_eur, source, confidence,
             deadweight=20.0, attribution=60.0, dropoff=5.0):
    return dict(
        category=category, title=title, stakeholder=stakeholder, unit=unit,
        proxyValueEUR=proxy_eur, source=source, confidence=confidence,
        deadweightPct=deadweight, attributionPct=attribution, dropoffPct=dropoff,
    )


CLUSTER_BENEFITS = {

    "ADI_SAD": {
        "methodologyNote": (
            "L'assistenza domiciliare integrata/sociale genera valore principalmente "
            "evitando o ritardando l'istituzionalizzazione e i ricoveri, e riducendo il "
            "carico dei caregiver familiari. I primi due benefici hanno proxy ad alta "
            "confidenza (tariffari); il terzo è ben documentato ma richiede una stima "
            "delle ore di cura risparmiate."
        ),
        "benefits": [
            _benefit("Istituzionalizzazione evitata", "Ritardo/evitamento del ricovero in RSA",
                     "Utente / SSR", "mesi di permanenza a domicilio evitando la RSA", 3000.0,
                     "Tariffe regionali RSA (quota sanitaria+sociale), ordine di grandezza "
                     "nazionale ~€90-110/die; valore mensile indicativo da tarare sul territorio",
                     CONFIDENCE_HIGH, deadweight=20, attribution=65, dropoff=5),
            _benefit("Salute", "Riduzione dei ricoveri ospedalieri evitabili",
                     "Utente / SSN", "n. ricoveri evitati", 4000.0,
                     "Tariffario nazionale prestazioni di assistenza ospedaliera (DM 18/10/2012 "
                     "e succ. agg.), costo medio indicativo ricovero ordinario per acuti",
                     CONFIDENCE_HIGH, deadweight=15, attribution=55, dropoff=0),
            _benefit("Caregiver", "Riduzione del carico assistenziale dei caregiver familiari",
                     "Famiglia/Caregiver", "ore di assistenza informale risparmiate/anno", 10.0,
                     "Costo di sostituzione (assistenza familiare/badante), CCNL lavoro "
                     "domestico e stime correnti del costo orario in Italia",
                     CONFIDENCE_HIGH, deadweight=10, attribution=80, dropoff=10),
        ],
    },

    "RSA_Residenziale": {
        "methodologyNote": (
            "Per le strutture residenziali (RSA, case alloggio, hospice) il valore "
            "principale è il sollievo del carico familiare (la famiglia non deve più "
            "fornire assistenza continuativa) e la prevenzione di complicanze/ricoveri "
            "grazie alla presenza professionale continua."
        ),
        "benefits": [
            _benefit("Caregiver", "Sollievo dal carico di cura familiare",
                     "Famiglia/Caregiver", "ore di assistenza informale risparmiate/anno", 10.0,
                     "Costo di sostituzione (assistenza familiare/badante), stessa proxy di ADI_SAD",
                     CONFIDENCE_HIGH, deadweight=10, attribution=85, dropoff=5),
            _benefit("Salute", "Prevenzione di complicanze e ricoveri ospedalieri",
                     "Utente / SSN", "n. ricoveri evitati", 4000.0,
                     "Tariffario nazionale prestazioni di assistenza ospedaliera, costo medio "
                     "indicativo ricovero ordinario",
                     CONFIDENCE_HIGH, deadweight=15, attribution=60, dropoff=0),
            _benefit("Salute mentale", "Riduzione di ricoveri/TSO psichiatrici (case alloggio)",
                     "Utente / SSN", "n. ricoveri psichiatrici evitati", 4500.0,
                     "Tariffario DRG psichiatrici, costo medio giornata SPDC indicativo x "
                     "durata media ricovero; applicabile solo a strutture per salute mentale",
                     CONFIDENCE_MEDIUM, deadweight=20, attribution=55, dropoff=0),
        ],
    },

    "Disabilita": {
        "methodologyNote": (
            "Per i servizi rivolti a persone con disabilità, i benefici più solidi sono "
            "la continuità della partecipazione sociale/scolastica e la riduzione del "
            "carico dei caregiver. Il valore della continuità scolastica usa come proxy "
            "la spesa pubblica evitata per anno scolastico non perso, un limite "
            "riconosciuto della metodologia (non misura il beneficio educativo in sé)."
        ),
        "benefits": [
            _benefit("Educazione/Inclusione", "Continuità dell'inclusione scolastica",
                     "Persona con disabilità / Famiglia", "anni scolastici supportati", 7500.0,
                     "OCSE, Education at a Glance - spesa pubblica indicativa per studente in "
                     "Italia; proxy del valore preservato, non del beneficio educativo diretto",
                     CONFIDENCE_MEDIUM, deadweight=20, attribution=60, dropoff=5),
            _benefit("Caregiver", "Riduzione del carico assistenziale dei caregiver familiari",
                     "Famiglia/Caregiver", "ore di assistenza informale risparmiate/anno", 10.0,
                     "Costo di sostituzione (assistenza familiare/badante), stessa proxy di ADI_SAD",
                     CONFIDENCE_HIGH, deadweight=10, attribution=80, dropoff=10),
            _benefit("Inclusione sociale", "Partecipazione sociale e autonomia",
                     "Persona con disabilità", "beneficiario/anno", 2000.0,
                     "Proxy internazionale di benessere (banche di proxy tipo HACT/Social "
                     "Value UK), in assenza di un databank italiano equivalente - da validare",
                     CONFIDENCE_LOW, deadweight=25, attribution=50, dropoff=15),
        ],
    },

    "Minori_Famiglia": {
        "methodologyNote": (
            "Per i servizi per minori e famiglia, il beneficio più materiale è la "
            "prevenzione dell'allontanamento familiare (collocamento in comunità, molto "
            "più costoso dell'intervento domiciliare/diurno), seguito dagli esiti "
            "scolastici. Il beneficio sul benessere familiare resta il più incerto."
        ),
        "benefits": [
            _benefit("Prevenzione allontanamento", "Prevenzione del collocamento in comunità per minori",
                     "Minore / Famiglia / Ente locale", "mesi di permanenza in famiglia evitando la comunità", 3300.0,
                     "Tariffari regionali servizi sociali per minori, costo medio indicativo "
                     "~€80-110/die per comunità educativa; valore mensile da tarare sul territorio",
                     CONFIDENCE_HIGH, deadweight=25, attribution=55, dropoff=5),
            _benefit("Educazione", "Miglioramento degli esiti scolastici / riduzione dispersione",
                     "Minore", "anni scolastici recuperati/protetti", 7500.0,
                     "OCSE, Education at a Glance - spesa pubblica indicativa per studente in Italia",
                     CONFIDENCE_MEDIUM, deadweight=20, attribution=55, dropoff=5),
            _benefit("Benessere familiare", "Riduzione dello stress e migliore funzionamento familiare",
                     "Famiglia", "nucleo familiare/anno", 1800.0,
                     "Proxy internazionale di benessere (banche di proxy tipo HACT/Social "
                     "Value UK) - da validare con cautela nel contesto italiano",
                     CONFIDENCE_LOW, deadweight=30, attribution=45, dropoff=15),
        ],
    },

    "Migranti_Accoglienza": {
        "methodologyNote": (
            "Cluster con la monetizzazione più incerta del set: i benefici principali "
            "(integrazione, occupazione, salute) dipendono da percorsi individuali "
            "difficili da attribuire con precisione al singolo servizio di accoglienza. "
            "Le proxy qui sono indicative e vanno usate con grande cautela, dichiarando "
            "sempre l'alta incertezza in qualsiasi documento che le riporti."
        ),
        "benefits": [
            _benefit("Occupazione/Integrazione", "Percorso di integrazione con avvio a formazione/lavoro",
                     "Beneficiario", "inserimenti lavorativi/formativi avviati", 14000.0,
                     "Stima su retribuzione medio-bassa da primo inserimento lavorativo in "
                     "Italia; valore fortemente indicativo, alta incertezza sull'attribuzione",
                     CONFIDENCE_LOW, deadweight=30, attribution=40, dropoff=10),
            _benefit("Salute", "Accesso a cure sanitarie di base / prevenzione emergenze",
                     "Beneficiario / SSN", "accessi al Pronto Soccorso evitati", 200.0,
                     "Tariffario prestazioni di Pronto Soccorso, valore medio indicativo",
                     CONFIDENCE_MEDIUM, deadweight=20, attribution=50, dropoff=0),
        ],
    },

    "Prima_Infanzia": {
        "methodologyNote": (
            "Per i servizi di prima infanzia (asili nido) il beneficio più solido e "
            "misurabile in letteratura economica è l'abilitazione della partecipazione "
            "al lavoro dei genitori (soprattutto madri). Lo sviluppo cognitivo del "
            "bambino, pur rilevante, ha proxy internazionali (es. Perry Preschool) non "
            "direttamente trasferibili al contesto italiano con affidabilità: è "
            "intenzionalmente escluso da questa prima versione, non azzerato per scelta "
            "arbitraria ma per assenza di una proxy italiana defendibile."
        ),
        "benefits": [
            _benefit("Occupazione", "Abilitazione della partecipazione al lavoro dei genitori",
                     "Famiglia", "genitori occupati grazie al nido/anno", 20000.0,
                     "ISTAT, retribuzione netta media annua indicativa; letteratura OCSE/UE su "
                     "servizi ECEC e partecipazione femminile al lavoro",
                     CONFIDENCE_MEDIUM, deadweight=15, attribution=70, dropoff=0),
        ],
    },

    "Personale_Sociosanitario": {
        "methodologyNote": (
            "Questo cluster (fornitura di personale socio-sanitario in appalto, es. "
            "presso l'Ospedale Bambino Gesù) non si presta bene a un framework SROI "
            "classico per beneficiario diretto: il committente è la struttura "
            "ospedaliera, non un singolo utente finale identificabile da Auxilium. "
            "Il beneficio riportato è un proxy debole e va usato con cautela; il "
            "contributo economico di questo cluster è meglio rappresentato dal footprint "
            "macroeconomico (Fase 3 - pagina Footprint SAM) piuttosto che da un rapporto SROI."
        ),
        "benefits": [
            _benefit("Continuità assistenziale", "Continuità e qualità dell'assistenza ospedaliera",
                     "Struttura ospedaliera / Pazienti", "mesi di servizio continuativo garantito", 1000.0,
                     "Proxy indicativa e debole: valore assegnato alla continuità del "
                     "servizio, non a un esito misurato sui pazienti - da rivedere",
                     CONFIDENCE_LOW, deadweight=30, attribution=40, dropoff=10),
        ],
    },
}


def get_cluster_benefits(cluster: str) -> dict:
    data = CLUSTER_BENEFITS.get(cluster)
    if data is None:
        return {"cluster": cluster, "methodologyNote": "Nessuna metodologia definita per questo cluster.", "benefits": []}
    return {"cluster": cluster, **data}
