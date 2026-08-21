"""
Seed dei dati reali disponibili oggi nella cartella del progetto.

Fonti:
- "Elenco servizi Auxilium.pdf" (root del progetto): storico commesse 2015-2024 di
  Auxilium Società Cooperativa Sociale. Trascritto a mano riga per riga (il PDF è una
  tabella non affidabile da parsare automaticamente) — prima versione, da validare.
- Bilanci d'esercizio (root del progetto): conto economico 2025 (2024 per Auxilium
  capogruppo, da Bilancio Sociale) delle 4 entità, letti e verificati riga per riga in
  Fase 2. Vedi FINANCE_DATA più sotto per le fonti e i limiti di ciascun documento.

Ogni "site" è il luogo/struttura dove il servizio è erogato; "ente_committente" è il
soggetto che affida/paga il servizio (spesso coincidono, non sempre: es. le RSA gestite
per conto della ex ASL n.3 Lagonegro sono a Chiaromonte/Maratea, non a Lagonegro).
Tutte le righe di FactServiceRevenue sono attribuite all'entità "AUX" (Auxilium
capogruppo): l'Elenco Servizi riguarda solo Auxilium, non le altre entità della rete
(Physioclinic/Care/Servizi), che non hanno un elenco equivalente in questa cartella.

Nota sul perimetro: "rete Auxilium" qui indica un ambito di analisi scelto (le 4 entità
coinvolte nei bilanci presenti in cartella), non un gruppo societario in senso tecnico.
Dai bilanci letti in Fase 2: solo Physioclinic S.r.l. dichiara esplicitamente di essere
posseduta al 100% da Auxilium; Auxilium Care e Auxilium Servizi dichiarano entrambe
"Appartenenza a un gruppo: no" nei propri bilanci — sono cooperative giuridicamente
indipendenti che condividono marchio/rete con Auxilium, non società controllate.
"""

from sqlalchemy.orm import Session

from database import (
    month_key,
    DimDate,
    DimEntity,
    DimSite,
    DimService,
    DimScope,
    DimRiskType,
    FactServiceRevenue,
    FactFinanceMonthly,
)

ENTITIES = [
    # EntityKey, EntityName, LegalForm (confermati leggendo i frontespizi dei bilanci in Fase 2)
    ("AUX", "Auxilium Società Cooperativa Sociale", "Cooperativa sociale di tipo A (capogruppo/rete)"),
    ("PHY", "Physioclinic S.r.l.", "S.r.l. a socio unico - controllata al 100% da Auxilium"),
    ("CARE", "Auxilium Care Società Cooperativa Sociale",
     "Cooperativa sociale a mutualità prevalente, tipo A - indipendente, stessa rete Auxilium"),
    ("SRV", "Auxilium Servizi Società Cooperativa",
     "Cooperativa - indipendente, stessa rete Auxilium"),
]

# ---------------------------------------------------------------------------
# Dati di bilancio (Fase 2) - fonte: lettura diretta dei bilanci in root del progetto,
# verificata riga per riga il 21/08/2026.
#
# Per ciascuna entità/anno le categorie seguono (dove disponibile) la voce B del conto
# economico ex art. 2425 c.c.; "Totale_CostiProduzione_B" è il totale così come riportato
# nel bilancio stesso (non un ricalcolo). Per Auxilium 2024 la fonte è il Bilancio
# Sociale 2024 (non il bilancio civilistico): non scorpora B6/B7/B8/B14 - riporta solo
# l'aggregato "Costi Esterni" - quindi niente "Totale_CostiProduzione_B" per quell'anno;
# si usa invece il "Risultato Operativo" così come dichiarato nel documento.
# ---------------------------------------------------------------------------

FINANCE_DATA = [
    # --- Auxilium (AUX) - bilancio civilistico 2025 ---
    dict(entity="AUX", year=2025, category="A_ValoreProduzione", revenue=63855328),
    dict(entity="AUX", year=2025, category="B6_MateriePrime", cost=883340),
    dict(entity="AUX", year=2025, category="B7_Servizi", cost=11068294),
    dict(entity="AUX", year=2025, category="B8_GodimentoBeniTerzi", cost=1256925),
    dict(entity="AUX", year=2025, category="B9_Personale_Salari", cost=38470178),
    dict(entity="AUX", year=2025, category="B9_Personale_OneriSociali", cost=8188474),
    dict(entity="AUX", year=2025, category="B9_Personale_TFR", cost=2227529),
    dict(entity="AUX", year=2025, category="B9_Personale_Altri", cost=129610),
    dict(entity="AUX", year=2025, category="B10_Ammortamenti", cost=284137),
    dict(entity="AUX", year=2025, category="B14_OneriDiversi", cost=413476),
    dict(entity="AUX", year=2025, category="Totale_CostiProduzione_B", cost=62960061),
    dict(entity="AUX", year=2025, category="Imposte_Reddito", cost=426770),
    dict(entity="AUX", year=2025, category="Risultato_Esercizio", cost=55624),

    # --- Auxilium (AUX) - Bilancio Sociale 2024 (aggregato, non civilistico) ---
    dict(entity="AUX", year=2024, category="A_ValoreProduzione", revenue=58595859),
    dict(entity="AUX", year=2024, category="B9_Personale_Totale", cost=44096831),
    dict(entity="AUX", year=2024, category="CostiEsterni_Aggregato", cost=12523794),
    dict(entity="AUX", year=2024, category="B10_Ammortamenti", cost=986340),
    dict(entity="AUX", year=2024, category="Risultato_Operativo", cost=720508),
    dict(entity="AUX", year=2024, category="Imposte_Reddito", cost=324298),
    dict(entity="AUX", year=2024, category="Risultato_Esercizio", cost=167894),

    # --- Physioclinic S.r.l. (PHY) - bilancio 2025 ---
    dict(entity="PHY", year=2025, category="A_ValoreProduzione", revenue=4424316),
    dict(entity="PHY", year=2025, category="B6_MateriePrime", cost=300593),
    dict(entity="PHY", year=2025, category="B7_Servizi", cost=2704097),
    dict(entity="PHY", year=2025, category="B8_GodimentoBeniTerzi", cost=422347),
    dict(entity="PHY", year=2025, category="B9_Personale_Salari", cost=645458),
    dict(entity="PHY", year=2025, category="B9_Personale_OneriSociali", cost=148906),
    dict(entity="PHY", year=2025, category="B9_Personale_TFR", cost=47999),
    dict(entity="PHY", year=2025, category="B10_Ammortamenti", cost=74590),
    dict(entity="PHY", year=2025, category="B14_OneriDiversi", cost=62229),
    dict(entity="PHY", year=2025, category="Totale_CostiProduzione_B", cost=4397436),
    dict(entity="PHY", year=2025, category="Imposte_Reddito", cost=14608),
    dict(entity="PHY", year=2025, category="Risultato_Esercizio", cost=5888),

    # --- Auxilium Care (CARE) - bilancio 2025 ---
    dict(entity="CARE", year=2025, category="A_ValoreProduzione", revenue=14834764),
    dict(entity="CARE", year=2025, category="B6_MateriePrime", cost=25003),
    dict(entity="CARE", year=2025, category="B7_Servizi", cost=7038477),
    dict(entity="CARE", year=2025, category="B8_GodimentoBeniTerzi", cost=76017),
    dict(entity="CARE", year=2025, category="B9_Personale_Salari", cost=5801114),
    dict(entity="CARE", year=2025, category="B9_Personale_OneriSociali", cost=1278389),
    dict(entity="CARE", year=2025, category="B9_Personale_TFR", cost=366900),
    dict(entity="CARE", year=2025, category="B10_Ammortamenti", cost=1401),
    dict(entity="CARE", year=2025, category="B14_OneriDiversi", cost=65793),
    dict(entity="CARE", year=2025, category="Totale_CostiProduzione_B", cost=14653094),
    dict(entity="CARE", year=2025, category="Imposte_Reddito", cost=2458),
    dict(entity="CARE", year=2025, category="Risultato_Esercizio", cost=91311),

    # --- Auxilium Servizi (SRV) - bozza bilancio 2025 (senza Nota Integrativa) ---
    dict(entity="SRV", year=2025, category="A_ValoreProduzione", revenue=9049290),
    dict(entity="SRV", year=2025, category="B6_MateriePrime", cost=646393),
    dict(entity="SRV", year=2025, category="B7_Servizi", cost=835516),
    dict(entity="SRV", year=2025, category="B8_GodimentoBeniTerzi", cost=70877),
    dict(entity="SRV", year=2025, category="B9_Personale_Salari", cost=5788533),
    dict(entity="SRV", year=2025, category="B9_Personale_OneriSociali", cost=1322179),
    dict(entity="SRV", year=2025, category="B9_Personale_TFR_Altri", cost=15302),
    dict(entity="SRV", year=2025, category="B10_Ammortamenti", cost=27748),
    dict(entity="SRV", year=2025, category="B14_OneriDiversi", cost=14952),
    dict(entity="SRV", year=2025, category="Totale_CostiProduzione_B", cost=8721500),
    dict(entity="SRV", year=2025, category="Imposte_Reddito", cost=0),
    dict(entity="SRV", year=2025, category="Risultato_Esercizio", cost=275885),
]

SCOPES = [
    ("SCOPE1", "Scope 1 - Emissioni dirette"),
    ("SCOPE2", "Scope 2 - Energia elettrica acquistata"),
    ("SCOPE3", "Scope 3 - Catena del valore"),
]

RISK_TYPES = [
    ("OPERATIVO", "Rischio operativo"),
    ("FINANZIARIO", "Rischio finanziario"),
    ("COMPLIANCE", "Rischio di compliance/normativo"),
    ("REPUTAZIONALE", "Rischio reputazionale"),
]

# Cluster di servizio standard, usati anche come base per la standardizzazione KPI/SROI
# di Fase 4:
#   ADI_SAD               - assistenza domiciliare integrata/sociosanitaria (anziani, generalista)
#   RSA_Residenziale      - RSA, case alloggio, hospice, strutture residenziali
#   Disabilita            - servizi dedicati a persone con disabilità
#   Minori_Famiglia       - minori, famiglia, centri diurni, case famiglia
#   Migranti_Accoglienza  - accoglienza richiedenti asilo/rifugiati (CAS, SPRAR/SIPROIMI)
#   Prima_Infanzia        - asili nido
#   Personale_Sociosanitario - fornitura di personale socio-sanitario in appalto (es. Bambino Gesù)

SERVICES = [
    dict(site="Ospedale Pediatrico Bambino Gesù", comune="Roma", provincia="RM", regione="Lazio",
         ente="Ospedale Pediatrico Bambino Gesù",
         service="Servizi infermieristici, OSS e personale tecnico-sanitario",
         cluster="Personale_Sociosanitario",
         amounts={2022: 17828669.22, 2023: 15637044.26, 2024: 16090743.46},
         period="Dal 01.01.2022 a tutt'oggi in essere", status="In essere"),
    dict(site="RSA Chiaromonte", comune="Chiaromonte", provincia="PZ", regione="Basilicata",
         ente="Ex Azienda Sanitaria ASL n.3 Lagonegro (PZ)",
         service="Gestione RSA Chiaromonte", cluster="RSA_Residenziale",
         amounts={2015: 558074.48, 2016: 558073.87, 2017: 558662.62, 2018: 584429.01, 2019: 662597.48,
                  2020: 620639.39, 2021: 667278.51, 2022: 676332.64, 2023: 732153.24, 2024: 738128.76},
         period="Dal 01.12.2006 a tutt'oggi in essere", status="In essere"),
    dict(site="RSA Maratea", comune="Maratea", provincia="PZ", regione="Basilicata",
         ente="Ex Azienda Sanitaria ASL n.3 Lagonegro (PZ)",
         service="Gestione RSA Maratea", cluster="RSA_Residenziale",
         amounts={2015: 550206.39, 2016: 559347.13, 2017: 550211.01, 2018: 603368.12, 2019: 707635.35,
                  2020: 701373.38, 2021: 681114.73, 2022: 726240.58, 2023: 809867.88, 2024: 807961.42},
         period="Dal 01.01.2007 a tutt'oggi in essere", status="In essere"),
    dict(site="Casa Alloggio Vallina", comune="Lagonegro", provincia="PZ", regione="Basilicata",
         ente="Ex Azienda Sanitaria ASL n.3 Lagonegro (PZ)",
         service="Casa Alloggio Vallina per malati psichiatrici", cluster="RSA_Residenziale",
         amounts={2015: 559109.05, 2016: 552493.78, 2017: 562755.92, 2018: 537707.54, 2019: 572167.72,
                  2020: 580235.52, 2021: 575524.70, 2022: 579581.07, 2023: 633737.25, 2024: 634065.21},
         period="Dal 15.07.1999 a tutt'oggi in essere", status="In essere"),
    dict(site="Case Alloggio Genzano 1-2-3", comune="Genzano di Lucania", provincia="PZ", regione="Basilicata",
         ente="Ex Azienda Sanitaria ASL n.1 Venosa (PZ)",
         service="Case Alloggio Genzano 1, 2 e 3 per malati psichiatrici", cluster="RSA_Residenziale",
         amounts={2015: 1098094.64, 2016: 1086850.14, 2017: 1119346.75, 2018: 1091857.31, 2019: 1173325.97,
                  2020: 1157968.21, 2021: 1117687.46, 2022: 1174632.00, 2023: 1220563.89, 2024: 1258848.49},
         period="Dal 15.07.1999 a tutt'oggi in essere (in proroga)", status="In essere"),
    dict(site="ASP Potenza - ADI", comune="Potenza", provincia="PZ", regione="Basilicata",
         ente="ASP Potenza",
         service="Assistenza Domiciliare Sanitaria, Farmacologica, Infermieristica, Riabilitativa, Medica e Psicologica",
         cluster="ADI_SAD",
         amounts={2016: 3671128.00, 2017: 6630239.74, 2018: 6901203.26, 2019: 7243115.31, 2020: 7019506.20,
                  2021: 7587096.95, 2022: 7824203.51, 2023: 8524841.25, 2024: 7498807.09},
         period="Dal 1° maggio 2016 a tutt'oggi in essere", status="In essere"),
    dict(site="RSA Copertino", comune="Copertino", provincia="LE", regione="Puglia",
         ente="Istituto Servizi alla Persona per l'Europa (ISPE) di Lecce",
         service="Gestione RSA di Copertino", cluster="RSA_Residenziale",
         amounts={2015: 1228534.28, 2016: 1127217.87, 2017: 1017137.03, 2018: 1020045.73, 2019: 1010073.77,
                  2020: 761274.88, 2021: 712522.66, 2022: 784434.80, 2023: 776474.96, 2024: 879638.04},
         period="Dal mese di marzo 2012 a tutt'oggi in essere", status="In essere"),
    dict(site="ASL Taranto - ADI/SLA", comune="Taranto", provincia="TA", regione="Puglia",
         ente="ASL Taranto",
         service="Supporto assistenza sociosanitaria domiciliare integrata (ambito distrettuale/riabilitativo e rete SLA)",
         cluster="ADI_SAD",
         amounts={2020: 1038979.15, 2021: 2068267.84, 2022: 2086354.18, 2023: 2195755.67, 2024: 2343363.78},
         period="Dal mese di luglio 2020 a tutt'oggi in essere", status="In essere"),
    dict(site="Casa di Riposo Mater Amabilis", comune="Roma", provincia="RM", regione="Lazio",
         ente="Provincia Romana Sacro Cuore di Gesù - Ist. Suore Passioniste San Paolo della Croce",
         service="Casa di Riposo \"Mater Amabilis\" per anziani (affitto di ramo d'azienda, Auxilium conduttore)",
         cluster="RSA_Residenziale",
         amounts={2015: 424833.49, 2016: 558906.04, 2017: 552503.93, 2018: 565765.08, 2019: 562776.74,
                  2020: 522374.86, 2021: 529456.14, 2022: 541922.68, 2023: 545944.59, 2024: 591597.34},
         period="Dal 01.04.2015 a tutt'oggi in essere (2025 fine gestione)", status="In essere"),
    dict(site="Comune di Irsina - ADI", comune="Irsina", provincia="MT", regione="Basilicata",
         ente="Comune di Irsina",
         service="Assistenza domiciliare anziani in difficoltà", cluster="ADI_SAD",
         amounts={2022: 252138.72, 2023: 305312.16, 2024: 331053.25},
         period="Da aprile 2022 a tutt'oggi in essere", status="In essere"),
    dict(site="Ambito Lagonegrese (ex Maratea) - Disabili", comune="Maratea", provincia="PZ", regione="Basilicata",
         ente="Comune di Viggianello (PZ) - Ente capofila ex Ambito Lagonegrese",
         service="Assistenza Domiciliare per Disabili", cluster="Disabilita",
         amounts={2015: 242795.04, 2016: 239476.00, 2017: 225699.28, 2018: 217284.86, 2019: 197485.30,
                  2020: 146242.76, 2021: 188776.30, 2022: 190344.12, 2023: 194602.53, 2024: 194749.42},
         period="Dal 14.04.2004 a tutt'oggi in essere", status="In essere"),
    dict(site="Ambito Basso Sinni - Disabili", comune="Scanzano Jonico", provincia="MT", regione="Basilicata",
         ente="Comune Capofila Scanzano Jonico (MT) - Ambito Basso Sinni",
         service="Assistenza Domiciliare per Disabili", cluster="Disabilita",
         amounts={2015: 222226.45, 2016: 196900.00, 2017: 195977.31, 2018: 198396.39, 2019: 175269.70,
                  2020: 168854.07, 2021: 185347.60, 2022: 204872.77, 2023: 134636.77},
         period="Dal febbraio 2005, concluso il 31.07.2023", status="Concluso"),
    dict(site="Comune di Ferrandina - Anziani", comune="Ferrandina", provincia="MT", regione="Basilicata",
         ente="Comune di Ferrandina (MT)",
         service="Sostegno a domicilio per persone anziane e in difficoltà", cluster="ADI_SAD",
         amounts={2015: 218809.76, 2016: 178979.45, 2017: 171823.34, 2018: 182055.12, 2019: 163070.21,
                  2020: 123370.44, 2021: 193744.76, 2022: 48019.84, 2024: 20201.85},
         period="Dal 05.11.2005, concluso marzo 2022; 2024 affidamenti diretti", status="Concluso"),
    dict(site="Comune di Bitonto - ADI/ADS", comune="Bitonto", provincia="BA", regione="Puglia",
         ente="Comune di Bitonto",
         service="Assistenza Domiciliare Integrata (ADI) e Assistenza Domiciliare Sociale (ADS)",
         cluster="ADI_SAD",
         amounts={2015: 690023.00, 2016: 845612.43, 2017: 623038.15, 2018: 631936.96, 2019: 487514.49,
                  2020: 138330.95, 2021: 321121.08, 2022: 265537.51, 2023: 192515.49, 2024: 186409.30},
         period="Dal 16.12.2009 a tutt'oggi in essere", status="In essere"),
    dict(site="Ambito Lagonegrese (ex Latronico) - Minori", comune="Latronico", provincia="PZ", regione="Basilicata",
         ente="Comune di Viggianello (PZ) - Ente capofila ex Ambito Lagonegrese",
         service="Centro diurno e sostegno domiciliare area minori - infanzia e famiglia",
         cluster="Minori_Famiglia",
         amounts={2016: 247503.00, 2017: 262952.92, 2018: 273390.78, 2019: 270940.94, 2020: 197611.87,
                  2021: 291417.15, 2022: 300286.97, 2023: 340311.54, 2024: 352179.82},
         period="Dal settembre 2003 a tutt'oggi in essere (in proroga)", status="In essere"),
    dict(site="Fondazione Protettorato S. Giuseppe", comune="Roma", provincia="RM", regione="Lazio",
         ente="Fondazione Protettorato di S. Giuseppe",
         service="Servizi socio-assistenziali ed educativi (Case Famiglia minori, Casa Famiglia madre/bambino, Micronido)",
         cluster="Minori_Famiglia",
         amounts={2015: 228057.80, 2016: 1132777.23, 2017: 1166303.92, 2018: 1188000.00, 2019: 1193148.00,
                  2020: 1316443.57, 2021: 1438936.65, 2022: 1405496.25, 2023: 1476160.95, 2024: 1613759.58},
         period="Dal 26.05.2006 a tutt'oggi in essere", status="In essere"),
    dict(site="Asilo Nido Comunale Tivoli", comune="Tivoli", provincia="RM", regione="Lazio",
         ente="Comune di Tivoli",
         service="Gestione dell'Asilo Nido Comunale", cluster="Prima_Infanzia",
         amounts={2015: 223994.61, 2016: 259561.91, 2017: 300309.03, 2018: 269474.37, 2019: 319908.71,
                  2020: 173489.54, 2021: 279624.00, 2022: 174232.56},
         period="Da ottobre 2012, in ATI con Coop. SS. Pietro e Paolo Patroni di Roma; concluso luglio 2022",
         status="Concluso"),
    dict(site="CAS Bari Palese", comune="Bari", provincia="BA", regione="Puglia",
         ente="Prefettura di Bari",
         service="Gestione del Centro di Accoglienza per Richiedenti Asilo di Bari Palese",
         cluster="Migranti_Accoglienza",
         amounts={2015: 14448759.62, 2016: 13948326.66, 2017: 12266885.77, 2018: 5747290.67, 2019: 1599323.09,
                  2020: 1475072.13, 2021: 1881159.65, 2022: 1981759.50, 2023: 3444244.53, 2024: 394201.59},
         period="Dal 28.04.2008, concluso a gennaio 2024", status="Concluso"),
    dict(site="Comune di Bitonto - SPRAR", comune="Bitonto", provincia="BA", regione="Puglia",
         ente="Comune di Bitonto",
         service="Accoglienza, integrazione e tutela Richiedenti Asilo, Rifugiati e Umanitari (RARU/SPRAR)",
         cluster="Migranti_Accoglienza",
         amounts={2015: 705651.66, 2016: 615996.20, 2017: 623038.15, 2018: 840000.00, 2019: 696000.00,
                  2020: 656573.29, 2021: 792650.00, 2022: 806600.00, 2023: 751800.00, 2024: 891500.00},
         period="Dal 01.01.2011 a tutt'oggi in essere", status="In essere"),
    dict(site="ASM Matera - ADI", comune="Matera", provincia="MT", regione="Basilicata",
         ente="ASM Matera",
         service="Assistenza domiciliare sanitaria, farmacologica, infermieristica, riabilitativa, medica e psicologica",
         cluster="ADI_SAD",
         amounts={2016: 3003683.70, 2017: 3267699.20, 2018: 3357469.70, 2019: 3537808.75, 2020: 3216683.90,
                  2021: 3445307.32, 2022: 3451457.87, 2023: 3678411.25, 2024: 4176771.49},
         period="Da novembre 2015 a tutt'oggi in essere (in proroga)", status="In essere"),
    dict(site="Asilo Nido Ambito Martano", comune="Martano", provincia="LE", regione="Puglia",
         ente="Ambito di Martano",
         service="Asilo Nido", cluster="Prima_Infanzia",
         amounts={2019: 178002.57, 2020: 70572.77, 2021: 98505.91, 2022: 101083.10, 2023: 161101.65,
                  2024: 209519.75},
         period="Dal 1° ottobre 2017 a tutt'oggi in essere", status="In essere"),
    dict(site="RSA Crispiano", comune="Crispiano", provincia="TA", regione="Puglia",
         ente="ASL Taranto",
         service="Gestione RSA di Crispiano", cluster="RSA_Residenziale",
         amounts={2015: 84038.02, 2016: 911027.66, 2017: 1302042.96, 2018: 902503.54, 2019: 1240158.14,
                  2020: 1185997.91, 2021: 915805.57, 2022: 1006085.45, 2023: 1226182.69, 2024: 1292345.98},
         period="Dal 12.11.2015 a tutt'oggi in essere", status="In essere"),
    dict(site="Centro Giaccone", comune="Roma", provincia="RM", regione="Lazio",
         ente="Comune di Roma",
         service="Centro di accoglienza notturna e primo intervento per donne e nuclei madre-minori in "
                 "condizioni di vulnerabilità (\"Giaccone\", via Cassia 471)",
         cluster="Minori_Famiglia",
         amounts={2018: 369513.90, 2019: 899239.59, 2020: 893339.19, 2021: 898741.56, 2022: 879624.87,
                  2023: 513329.01},
         period="Dal 01.08.2018 al 28.02.2021", status="Concluso"),
    dict(site="Centro Volare Alto", comune="Lecce", provincia="LE", regione="Puglia",
         ente="Comune di Lecce",
         service="Centro Socioeducativo diurno \"Volare Alto\"", cluster="Minori_Famiglia",
         amounts={2018: 38139.62, 2019: 239432.02, 2020: 238272.67, 2021: 255791.53, 2022: 249118.72,
                  2023: 244517.78, 2024: 228507.63},
         period="Dal 12.11.2018 al 10.11.2019, concluso il 31.01.2025", status="Concluso"),
    dict(site="ASL BAT - ADI", comune="Andria", provincia="BT", regione="Puglia",
         ente="ASL BAT",
         service="Assistenza Domiciliare Integrata", cluster="ADI_SAD",
         amounts={2018: 724321.63, 2019: 3424143.27, 2020: 3608055.29, 2021: 3902354.51, 2022: 3803586.88,
                  2023: 4001825.86, 2024: 4591539.09},
         period="Dal 01.08.2018 a tutt'oggi in essere", status="In essere"),
    dict(site="Hospice Minervino Murge", comune="Minervino Murge", provincia="BT", regione="Puglia",
         ente="ASL BAT",
         service="Gestione dell'Hospice di Minervino Murge", cluster="RSA_Residenziale",
         amounts={2019: 101046.32, 2020: 754480.98, 2021: 792509.86, 2022: 666859.50, 2023: 782315.82,
                  2024: 841709.88},
         period="Avvio 17.10.2019, durata contratto 5 anni", status="In essere"),
    dict(site="Centro C'entro anch'io", comune="Lequile", provincia="LE", regione="Puglia",
         ente="Comune di Lequile",
         service="Centro Socioeducativo diurno \"C'entro anch'io\"", cluster="Minori_Famiglia",
         amounts={2019: 65828.40, 2020: 133405.20, 2021: 137431.20, 2022: 151031.28, 2023: 85584.40},
         period="Dal 01.07.2019, durata 10 mesi + eventuale proroga, concluso", status="Concluso"),
    dict(site="Comune di Matera - Disabili scuole", comune="Matera", provincia="MT", regione="Basilicata",
         ente="Comune di Matera",
         service="Assistenza personalizzata per alunni disabili nelle scuole cittadine",
         cluster="Disabilita",
         amounts={2019: 464258.61, 2020: 338680.67, 2021: 514090.88, 2022: 456260.28, 2023: 457853.69},
         period="Dal 07.01.2019, concluso giugno 2024", status="Concluso"),
    dict(site="Comune di Matera - Home Care", comune="Matera", provincia="MT", regione="Basilicata",
         ente="Comune di Matera",
         service="Home Care: assistenza domiciliare per parenti di dipendenti pubblici",
         cluster="ADI_SAD",
         amounts={2021: 7090.24, 2022: 30381.46, 2023: 50158.50, 2024: 72021.91},
         period="Dal 2021 a tutt'oggi in essere", status="In essere"),
    dict(site="Comune di Galatina - Educativa domiciliare", comune="Galatina", provincia="LE", regione="Puglia",
         ente="Comune di Galatina",
         service="Servizio di Educativa domiciliare", cluster="Minori_Famiglia",
         amounts={2022: 24399.55, 2023: 24467.17, 2024: 36759.73},
         period="Da gennaio 2022 a tutt'oggi in essere", status="In essere"),
    dict(site="Comune di Gorgoglione - Minori stranieri", comune="Gorgoglione", provincia="MT", regione="Basilicata",
         ente="Comune di Gorgoglione (MT)",
         service="Accoglienza, integrazione e tutela minori stranieri non accompagnati (SPRAR/SIPROIMI)",
         cluster="Migranti_Accoglienza",
         amounts={2021: 300541.70, 2022: 381639.16, 2023: 356561.10, 2024: 357980.06},
         period="Dal 1° febbraio 2021 a tutt'oggi in essere", status="In essere"),
    dict(site="ASL BA - Personale sociosanitario", comune="Bari", provincia="BA", regione="Puglia",
         ente="ASL Bari",
         service="Prestazioni di assistenza tutelare OSS, infermieristiche, riabilitative, logoterapiche e psicologiche",
         cluster="Personale_Sociosanitario",
         amounts={2021: 4607493.47, 2022: 6705810.94, 2023: 8592336.97, 2024: 10317018.66},
         period="Da marzo 2021 a tutt'oggi in essere", status="In essere"),
    dict(site="Ambito di Gallipoli - ADI/SAD", comune="Gallipoli", provincia="LE", regione="Puglia",
         ente="Ambito di Gallipoli",
         service="Assistenza Domiciliare Socio-Assistenziale integrata con servizi sanitari per disabili gravi",
         cluster="ADI_SAD",
         amounts={2021: 161366.39, 2023: 161598.89, 2024: 285884.77},
         period="Da settembre 2016, in ATI con Egle Soc. Coop. sociale, terminato 01.07.2021; "
                "da maggio 2023 a tutt'oggi in essere", status="In essere"),
    dict(site="Ambito di Galatina - SAD/ADI", comune="Galatina", provincia="LE", regione="Puglia",
         ente="Ambito di Galatina",
         service="Servizio SAD e ADI anziani e disabili", cluster="ADI_SAD",
         amounts={2021: 6558.70, 2022: 165597.58, 2023: 204604.93, 2024: 228100.61},
         period="Dal dicembre 2021 a tutt'oggi in essere", status="In essere"),
    dict(site="ASL Roma B - Struttura via Osimo", comune="Roma", provincia="RM", regione="Lazio",
         ente="ASL Roma B",
         service="Gestione struttura residenziale socio-riabilitativa (via Osimo 3)",
         cluster="RSA_Residenziale",
         amounts={2019: 268898.16, 2020: 310562.22, 2021: 299194.82, 2022: 283491.04, 2023: 299231.11,
                  2024: 312072.78},
         period="Dal 15.01.2015 a tutt'oggi in essere (in proroga)", status="In essere"),
]


def run_seed(db: Session) -> None:
    if db.query(DimEntity).count() > 0:
        return  # già seedato

    for key, name, legal_form in ENTITIES:
        db.add(DimEntity(EntityKey=key, EntityName=name, LegalForm=legal_form))

    for key, label in SCOPES:
        db.add(DimScope(ScopeKey=key, ScopeLabel=label))

    for key, label in RISK_TYPES:
        db.add(DimRiskType(RiskTypeKey=key, RiskLabel=label))

    for year in range(2015, 2026):
        db.add(DimDate(
            MonthKey=month_key(year, 12),
            Year=year,
            Month=12,
            MonthLabel=f"Dicembre {year}",
            Quarter=4,
        ))

    db.flush()

    for i, row in enumerate(SERVICES, start=1):
        site_key = f"S{i:02d}"
        service_key = f"SV{i:02d}"

        db.add(DimSite(
            SiteKey=site_key,
            SiteName=row["site"],
            Comune=row["comune"],
            Provincia=row["provincia"],
            Regione=row["regione"],
            EnteCommittente=row["ente"],
        ))
        db.add(DimService(
            ServiceKey=service_key,
            ServiceName=row["service"],
            ServiceCluster=row["cluster"],
        ))

        for year, amount in row["amounts"].items():
            db.add(FactServiceRevenue(
                MonthKey=month_key(year, 12),
                SiteKey=site_key,
                ServiceKey=service_key,
                EntityKey="AUX",
                ContractName=row["service"],
                RevenueEUR=amount,
                ContractStatus=row["status"],
            ))

    for row in FINANCE_DATA:
        db.add(FactFinanceMonthly(
            MonthKey=month_key(row["year"], 12),
            EntityKey=row["entity"],
            CostCategory=row["category"],
            CostEUR=row.get("cost"),
            RevenueEUR=row.get("revenue"),
        ))

    db.commit()
