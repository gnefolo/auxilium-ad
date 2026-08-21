"""
Coordinate geografiche (lat, lon) dei comuni dove Auxilium opera, secondo l'Elenco
Servizi. Sono fatti geografici pubblici (non dati statistici), usati solo per
posizionare i siti sulla mappa - precisione a livello di comune, non catastale.
"""

COMUNE_COORDS = {
    "Roma": (41.9028, 12.4964),
    "Milano": (45.4642, 9.1900),
    "Bari": (41.1171, 16.8719),
    "Potenza": (40.6404, 15.8054),
    "Matera": (40.6664, 16.6043),
    "Lecce": (40.3519, 18.1720),
    "Taranto": (40.4738, 17.2403),
    "Bitonto": (41.1080, 16.6928),
    "Andria": (41.2306, 16.2971),
    "Minervino Murge": (41.0908, 16.0774),
    "Copertino": (40.2649, 18.0499),
    "Gallipoli": (40.0557, 17.9922),
    "Galatina": (40.1741, 18.1720),
    "Martano": (40.2333, 18.3167),
    "Lequile": (40.2833, 18.1333),
    "Genzano di Lucania": (40.8664, 16.0964),
    "Maratea": (39.9944, 15.7139),
    "Lagonegro": (40.1167, 15.7167),
    "Chiaromonte": (40.0167, 16.2667),
    "Ferrandina": (40.4931, 16.4592),
    "Scanzano Jonico": (40.2500, 16.7333),
    "Irsina": (40.7500, 16.2333),
    "Tivoli": (41.9633, 12.7981),
    "Latronico": (40.0833, 15.9667),
    "Crispiano": (40.6019, 17.2308),
    "Gorgoglione": (40.4833, 16.1667),
}


def coords_for_comune(comune: str):
    return COMUNE_COORDS.get(comune)
