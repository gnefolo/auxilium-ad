"""
Preferenze del cruscotto: soglie e comportamenti configurabili dall'utente, persistiti
come chiave/valore (AppSetting). Non introduce nuovi dati aziendali: le soglie qui
configurate vengono applicate a calcoli che restano sempre su dati reali (es. le
soglie di anomalia di territorio/anomalie.py).
"""

from sqlalchemy.orm import Session

from database import AppSetting

DEFAULTS = {
    "anomalia_soglia_attenzione": 0.20,
    "anomalia_soglia_critico": 0.45,
    "overview_refresh_seconds": 30,
}

# Impostazioni numeriche: cast del valore salvato (stringa) al tipo giusto.
_CASTERS = {
    "anomalia_soglia_attenzione": float,
    "anomalia_soglia_critico": float,
    "overview_refresh_seconds": int,
}


def get_settings(db: Session) -> dict:
    rows = db.query(AppSetting).all()
    stored = {r.Key: r.Value for r in rows}
    result = dict(DEFAULTS)
    for key, caster in _CASTERS.items():
        if key in stored:
            try:
                result[key] = caster(stored[key])
            except (TypeError, ValueError):
                pass
    return result


def save_settings(db: Session, payload: dict) -> dict:
    for key in DEFAULTS:
        if key not in payload:
            continue
        value = payload[key]
        row = db.query(AppSetting).filter(AppSetting.Key == key).first()
        if row is None:
            row = AppSetting(Key=key, Value=str(value))
            db.add(row)
        else:
            row.Value = str(value)
    db.commit()
    return get_settings(db)
