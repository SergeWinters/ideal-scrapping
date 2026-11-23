"""Genera assets/app_icon.ico (círculo azul Fluent con una I) para el exe de Idealista Scraper Pro."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

app = QGuiApplication([])
out = Path(__file__).resolve().parent.parent / "assets"
out.mkdir(exist_ok=True)

img = QImage(256, 256, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
p.setBrush(QColor("#0078D4"))
p.setPen(Qt.NoPen)
p.drawEllipse(12, 12, 232, 232)
p.setPen(QColor("white"))
p.setFont(QFont("Segoe UI", 120, QFont.Bold))
p.drawText(img.rect(), Qt.AlignCenter, "I")
p.end()

ok = img.save(str(out / "app_icon.ico"))
img.save(str(out / "app_icon.png"))
print("Icono generado en:", out / "app_icon.ico", "OK" if ok else "ERROR")
sys.exit(0 if ok else 1)
