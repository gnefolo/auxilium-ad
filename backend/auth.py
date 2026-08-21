"""
Autenticazione minimale per l'accesso alla dashboard: un solo account amministratore
(username/password da variabili d'ambiente), token firmato con scadenza (HMAC-SHA256,
senza dipendenze esterne tipo PyJWT). Adeguata per uno strumento interno a un utente
(l'Amministratore Delegato), non per un sistema multi-utente con ruoli.

IMPORTANTE PER IL DEPLOY: le variabili d'ambiente ADMIN_USERNAME, ADMIN_PASSWORD e
AUTH_SECRET_KEY vanno impostate su Render (o dovunque il backend sia eseguito) con
valori reali e segreti. I valori di default qui sotto valgono SOLO per lo sviluppo
locale e non sono sicuri per la produzione.
"""

import base64
import hashlib
import hmac
import json
import os
import time

SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "dev-insecure-secret-change-me-before-deploy")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "auxilium2026")
TOKEN_TTL_SECONDS = 12 * 60 * 60  # 12 ore


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _sign(payload_b64: str) -> str:
    sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).digest()
    return _b64encode(sig)


def create_token(username: str) -> str:
    payload = {"u": username, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload_b64 = _b64encode(json.dumps(payload).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> bool:
    try:
        payload_b64, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(payload_b64)):
            return False
        payload = json.loads(_b64decode(payload_b64))
        return payload.get("exp", 0) > time.time()
    except Exception:
        return False


def check_credentials(username: str, password: str) -> bool:
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
