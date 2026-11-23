"""Exportadores de datos de inmuebles a CSV y Excel (.xlsx).
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import List

from .models import Listing


def export_to_csv(filepath: str | Path, listings: List[Listing], delimiter: str = ";") -> Path:
    """Exporta los inmuebles a CSV con codificación UTF-8-SIG y separador configurable."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    headers = [
        "Score", "Banda (Deal)", "Precio (€)", "€/m²", "vs Área (%)", 
        "Habitaciones", "Superficie (m²)", "Planta", "Ascensor", 
        "Barrio", "Distrito", "Ciudad", "Cuota Hipoteca (€)", 
        "Terraza", "Piscina", "Garaje", "Aire Acondicionado", 
        "Título", "URL", "ID Anuncio"
    ]
    
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(headers)
        for item in listings:
            writer.writerow([
                f"{item.score:.2f}" if item.score is not None else "",
                item.band or "",
                item.price if item.price is not None else "",
                f"{item.price_m2:.1f}" if item.price_m2 is not None else "",
                f"{item.discount_pct:+.1f}%" if item.discount_pct is not None else "",
                item.rooms if item.rooms is not None else "",
                item.size_m2 if item.size_m2 is not None else "",
                item.floor or "",
                "Sí" if item.elevator is True else ("No" if item.elevator is False else "?"),
                item.neighborhood or "",
                item.district or "",
                item.city or "",
                f"{item.monthly_payment:.0f}" if item.monthly_payment is not None else "",
                "Sí" if item.terrace is True else ("No" if item.terrace is False else ""),
                "Sí" if item.pool is True else ("No" if item.pool is False else ""),
                "Sí" if item.garage is True else ("No" if item.garage is False else ""),
                "Sí" if item.air_conditioning is True else ("No" if item.air_conditioning is False else ""),
                item.title or "",
                item.url or "",
                item.ad_id or "",
            ])
    return path


def export_to_excel(filepath: str | Path, listings: List[Listing]) -> Path:
    """Exporta los inmuebles a formato Excel (.xlsx) con estilos Fluent y enlaces activos."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inmuebles Idealista"
    ws.views.sheetView[0].showGridLines = True

    headers = [
        "Score", "Oportunidad", "Precio", "€/m²", "vs Área", 
        "Hab.", "m²", "Planta", "Ascensor", "Barrio", 
        "Distrito", "Cuota Est.", "Terraza", "Garaje", 
        "Título", "Enlace"
    ]

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0078D4", end_color="0078D4", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    thin_border = Border(
        left=Side(style="thin", color="E0E0E0"),
        right=Side(style="thin", color="E0E0E0"),
        top=Side(style="thin", color="E0E0E0"),
        bottom=Side(style="thin", color="E0E0E0"),
    )

    ws.row_dimensions[1].height = 26
    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Estilos de oportunidad
    deal_colors = {
        "great deal": PatternFill(start_color="DFF6DD", end_color="DFF6DD", fill_type="solid"),
        "good deal": PatternFill(start_color="EBF9EB", end_color="EBF9EB", fill_type="solid"),
        "fair": PatternFill(start_color="FFF4CE", end_color="FFF4CE", fill_type="solid"),
        "overpriced": PatternFill(start_color="FDE7E9", end_color="FDE7E9", fill_type="solid"),
    }
    deal_fonts = {
        "great deal": Font(name="Segoe UI", size=10, bold=True, color="0E700E"),
        "good deal": Font(name="Segoe UI", size=10, bold=True, color="107C10"),
        "fair": Font(name="Segoe UI", size=10, bold=True, color="8A6D00"),
        "overpriced": Font(name="Segoe UI", size=10, bold=True, color="A80000"),
    }
    regular_font = Font(name="Segoe UI", size=10)
    link_font = Font(name="Segoe UI", size=10, color="0078D4", underline="single")

    for r_idx, item in enumerate(listings, start=2):
        ws.row_dimensions[r_idx].height = 20
        row_values = [
            round(item.score, 2) if item.score is not None else "",
            item.band.title() if item.band else "",
            item.price or "",
            round(item.price_m2, 1) if item.price_m2 is not None else "",
            f"{item.discount_pct:+.1f}%" if item.discount_pct is not None else "",
            item.rooms or "",
            item.size_m2 or "",
            item.floor or "",
            "Sí" if item.elevator is True else ("No" if item.elevator is False else ""),
            item.neighborhood or "",
            item.district or "",
            f"{item.monthly_payment:,.0f} €" if item.monthly_payment is not None else "",
            "Sí" if item.terrace is True else ("No" if item.terrace is False else ""),
            "Sí" if item.garage is True else ("No" if item.garage is False else ""),
            item.title or "",
            "Ver en Idealista" if item.url else "",
        ]
        ws.append(row_values)

        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            cell.border = thin_border
            cell.font = regular_font

            # Alineaciones específicas
            if c_idx in (1, 6, 7, 8, 9, 13, 14):
                cell.alignment = center_align
            elif c_idx in (3, 4, 5, 12):
                cell.alignment = right_align
            else:
                cell.alignment = left_align

            # Formato de celda de oportunidad
            if c_idx == 2 and item.band in deal_colors:
                cell.fill = deal_colors[item.band]
                cell.font = deal_fonts[item.band]

            # Enlace activo
            if c_idx == len(headers) and item.url:
                cell.hyperlink = item.url
                cell.font = link_font
                cell.alignment = center_align

            # Formato numérico en precio
            if c_idx == 3 and isinstance(cell.value, (int, float)):
                cell.number_format = "#,##0 €"
            elif c_idx == 4 and isinstance(cell.value, (int, float)):
                cell.number_format = "#,##0.0 €"

    # Ajuste automático del ancho de columnas
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)

    wb.save(path)
    return path
