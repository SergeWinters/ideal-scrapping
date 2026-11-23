"""Licencia anti-copia con clave firmada (Ed25519) ligada al Hardware ID.
100% compatible con el sistema de licencias de 'certificados'.
"""
from __future__ import annotations

import base64
import email.utils
import hashlib
import json
import os
import struct
import threading
import time
import urllib.request
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .licensing_pub import PUBLIC_KEY_B64

EPOCH = date(2026, 1, 1)
EPOCH_DT = datetime(2026, 1, 1)
HW_SALT = b"DEHuMonitor/hwid/v1"
PAYLOAD_FMT = ">B10sIHH"  # version, hwid(10 bytes), emitida(SEGUNDOS desde EPOCH), dias de validez, max unidades
PAYLOAD_LEN = struct.calcsize(PAYLOAD_FMT)  # 19
SIG_LEN = 64
CLOCK_TOLERANCE = 24 * 3600

LICENSE_STORAGE = Path(__file__).resolve().parent.parent / "data" / "license.json"


class LicenseError(Exception):
    pass


# ------------------------------------------------------------------ storage local
def _load_storage() -> dict:
    try:
        if LICENSE_STORAGE.exists():
            return json.loads(LICENSE_STORAGE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_storage(data: dict) -> None:
    try:
        LICENSE_STORAGE.parent.mkdir(parents=True, exist_ok=True)
        LICENSE_STORAGE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


class LocalStore:
    """Almacén clave-valor para settings y licencia."""
    def get(self, key: str, default=None):
        data = _load_storage()
        return data.get(key, default)

    def set(self, key: str, val) -> None:
        data = _load_storage()
        data[key] = val
        _save_storage(data)


# ------------------------------------------------------------------ hardware id
def machine_guid() -> str:
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        return str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:
        return str(uuid.getnode())


def hwid_bytes() -> bytes:
    return hashlib.sha256(HW_SALT + machine_guid().encode()).digest()[:10]


def group(text: str, n: int) -> str:
    return "-".join(text[i:i + n] for i in range(0, len(text), n))


def hwid_text(raw: bytes | None = None) -> str:
    return group(base64.b32encode(raw or hwid_bytes()).decode().rstrip("="), 4)


def _clean(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalnum())


def parse_hwid(text: str) -> bytes:
    try:
        raw = base64.b32decode(_clean(text))
    except Exception as e:
        raise LicenseError("Hardware ID no válido") from e
    if len(raw) != 10:
        raise LicenseError("Hardware ID no válido (longitud)")
    return raw


# ------------------------------------------------------------------ decode key
def decode_key(text: str) -> dict:
    """Valida firma y devuelve datos. NO comprueba equipo ni caducidad."""
    c = _clean(text)
    try:
        raw = base64.b32decode(c + "=" * (-len(c) % 8))
    except Exception as e:
        raise LicenseError("La clave no tiene un formato válido") from e
    if len(raw) != PAYLOAD_LEN + SIG_LEN:
        raise LicenseError("La clave no tiene un formato válido")
    payload, sig = raw[:PAYLOAD_LEN], raw[PAYLOAD_LEN:]
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64)).verify(sig, payload)
    except InvalidSignature as e:
        raise LicenseError("Clave no auténtica (firma incorrecta)") from e
    ver, hw, issued_ts, days, max_items = struct.unpack(PAYLOAD_FMT, payload)
    if ver != 1:
        raise LicenseError("Versión de clave no soportada")
    issued_d = (EPOCH_DT + timedelta(seconds=issued_ts)).date()
    return {
        "hwid": hw,
        "issued": issued_d,
        "issued_ts": issued_ts,
        "days": days,
        "expires": issued_d + timedelta(days=days),
        "max_items": max_items or None,
    }


# ------------------------------------------------------------------ fecha internet y reloj
NET_CLOCK_URL = "https://descargas.forgenex.com/certs/latest.json"
NET_FRESH_S = 12 * 3600
NET_REFRESH_S = 6 * 3600
NET_RETRY_S = 600
_net = {"server": None, "mono": 0.0, "dirty": False, "try": 0.0, "ok": 0.0, "running": False}


def _fetch_net_time() -> None:
    try:
        req = urllib.request.Request(NET_CLOCK_URL, method="HEAD", headers={"User-Agent": "DEHuMonitor-clock"})
        with urllib.request.urlopen(req, timeout=8) as r:
            hdr = r.headers.get("Date")
        server = email.utils.parsedate_to_datetime(hdr).timestamp()
        _net.update(server=server, mono=time.monotonic(), dirty=True, ok=time.time())
    except Exception:
        pass
    finally:
        _net["running"] = False


def kick_net_sync(force: bool = False) -> None:
    if _net["running"]:
        return
    gap = NET_REFRESH_S if _net["server"] is not None else NET_RETRY_S
    if not force and time.time() - _net["try"] < gap:
        return
    _net["try"] = time.time()
    _net["running"] = True
    threading.Thread(target=_fetch_net_time, daemon=True, name="net-clock").start()


def net_epoch() -> float | None:
    if _net["server"] is None or time.monotonic() - _net["mono"] > NET_FRESH_S:
        return None
    return _net["server"] + (time.monotonic() - _net["mono"])


def _now() -> float:
    n = net_epoch()
    return n if n is not None else time.time()


def today() -> date:
    return date.fromtimestamp(_now())


def license_setting() -> str:
    return "license:" + hwid_text().replace("-", "")


def status(db: LocalStore | None = None) -> dict:
    if db is None:
        db = LocalStore()
    kick_net_sync()
    key = db.get(license_setting())
    if not key:
        return {"plan": "free", "expires": None, "days_left": None, "reason": "No registrada"}
    try:
        info = decode_key(key)
    except LicenseError as e:
        return {"plan": "free", "expires": None, "days_left": None, "reason": str(e)}

    if info["hwid"] != hwid_bytes():
        return {"plan": "free", "expires": None, "days_left": None, "reason": "La licencia es de otro equipo"}

    today_ = today()
    if info["issued"] > today_ + timedelta(days=1):
        return {"plan": "free", "expires": None, "days_left": None, "reason": "Fecha de emisión futura"}

    days_left = (info["expires"] - today_).days
    if days_left < 0:
        return {
            "plan": "free",
            "expires": info["expires"],
            "days_left": days_left,
            "reason": f"Licencia caducada el {info['expires']:%d/%m/%Y}",
        }

    return {
        "plan": "pro",
        "expires": info["expires"],
        "days_left": days_left,
        "reason": "",
    }


def activate(db: LocalStore, key_text: str) -> dict:
    info = decode_key(key_text)
    if info["hwid"] != hwid_bytes():
        raise LicenseError("Esta clave es de otro equipo (el Hardware ID no coincide)")
    if info["expires"] < today():
        raise LicenseError(f"Esta clave caducó el {info['expires']:%d/%m/%Y}")
    db.set(license_setting(), _clean(key_text))
    return status(db)


def remove(db: LocalStore) -> None:
    db.set(license_setting(), "")


def describe(st: dict) -> str:
    if st["plan"] == "pro":
        return f"Licencia Pro Activa · Caduca {st['expires']:%d/%m/%Y} ({st['days_left']} días restantes)"
    return f"Versión Gratuita" + (f" — {st['reason']}" if st.get("reason") else "")
