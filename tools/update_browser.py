"""Descarga y actualiza el Chromium portable (browser\\chrome-win64) para empaquetarlo junto al ejecutable.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "browser" / "chrome-win64"
REF_BROWSER = Path(r"C:\proyectos\proyectos-composers\certificados\browser\chrome-win64")


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Si ya existe en certificados, copiar directamente para ahorrar tiempo y ancho de banda
    if REF_BROWSER.exists() and (REF_BROWSER / "chrome.exe").exists() and not (DEST / "chrome.exe").exists():
        print(f"Copiando Chromium portable desde {REF_BROWSER}...")
        if DEST.exists():
            shutil.rmtree(DEST)
        shutil.copytree(REF_BROWSER, DEST)
        print("Chromium portable copiado con éxito.")
        return

    # 2. Si no, instalar mediante Playwright
    print("Instalando Chromium mediante Playwright...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    
    code = (
        "from playwright.sync_api import sync_playwright\n"
        "p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()"
    )
    exe_str = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
    exe = Path(exe_str)
    if not exe.exists():
        sys.exit(f"No se encontró el ejecutable de Chromium en: {exe}")
    
    src = exe.parent
    print(f"Copiando {src} -> {DEST}...")
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(src, DEST)
    print("Chromium portable instalado correctamente en:", DEST)


if __name__ == "__main__":
    main()
