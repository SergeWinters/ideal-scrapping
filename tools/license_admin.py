"""Herramienta de administración y generación de licencias (Compatible con certificados).

Uso:
  python tools\\license_admin.py issue --hwid XXXX-XXXX-XXXX-XXXX --days 365 [--name "Cliente"]
  python tools\\license_admin.py verify CLAVE
"""
import argparse
import base64
import csv
import struct
import sys
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from idealista import licensing as L

PRIV = ROOT / "tools" / "_private" / "license_private.pem"
# Si no existe localmente en tools/_private, buscar en la carpeta de certificados
CERT_PRIV = Path(r"C:\proyectos\proyectos-composers\certificados\tools\_private\license_private.pem")


def get_private_key_path() -> Path:
    if PRIV.exists():
        return PRIV
    if CERT_PRIV.exists():
        return CERT_PRIV
    return PRIV


def cmd_issue(args):
    priv_path = get_private_key_path()
    if not priv_path.exists():
        sys.exit(f"Falta la clave privada en {priv_path}. Asegúrate de tener license_private.pem.")
    
    hw = L.parse_hwid(args.hwid)
    issued = date.fromisoformat(args.issued) if args.issued else date.today()
    when = datetime.combine(issued, dtime(12)) if args.issued else datetime.now()
    payload = struct.pack(L.PAYLOAD_FMT, 1, hw, int((when - L.EPOCH_DT).total_seconds()), args.days, args.max_items)
    
    key = serialization.load_pem_private_key(priv_path.read_bytes(), None)
    token = L.group(base64.b32encode(payload + key.sign(payload)).decode().rstrip("="), 5)
    expires = issued + timedelta(days=args.days)
    
    print(f"Cliente: {args.name or '-'} | HWID {L.hwid_text(hw)} | {args.days} días | Caduca: {expires:%d/%m/%Y}\n")
    print("CLAVE DE LICENCIA:")
    print(token)


def cmd_verify(args):
    info = L.decode_key(args.key)
    print("Clave válida y auténtica:")
    print(f"  HWID:        {L.hwid_text(info['hwid'])}")
    print(f"  Emitida:     {info['issued']:%d/%m/%Y}")
    print(f"  Caduca:      {info['expires']:%d/%m/%Y} ({info['days']} días)")


def main():
    p = argparse.ArgumentParser(description="Administración de Licencias Idealista")
    sub = p.add_subparsers(dest="cmd")
    
    p_issue = sub.add_parser("issue", help="Emitir una nueva clave")
    p_issue.add_argument("--hwid", required=True, help="Hardware ID del equipo destino")
    p_issue.add_argument("--days", type=int, default=365, help="Días de validez")
    p_issue.add_argument("--name", default="", help="Nombre del cliente")
    p_issue.add_argument("--max-items", type=int, default=0, help="0 para ilimitado")
    p_issue.add_argument("--issued", default="", help="Fecha de emisión AAAA-MM-DD")
    
    p_verify = sub.add_parser("verify", help="Verificar una clave")
    p_verify.add_argument("key", help="Clave a comprobar")
    
    args = p.parse_args()
    if args.cmd == "issue":
        cmd_issue(args)
    elif args.cmd == "verify":
        cmd_verify(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
