"""
document_processors/excel_processor.py
--------------------------------------
Text extraction module for Microsoft Excel spreadsheets:
- .xlsx (Excel 2007+ OpenXML) using pandas with openpyxl
- .xls (Excel 97-2003 Binary) using pandas with xlrd
"""

import io
import pandas as pd


def extract_xlsx_text(file) -> str:
    """
    Extract text content from all sheets of an Excel .xlsx workbook.
    """
    if hasattr(file, "seek"):
        file.seek(0)

    try:
        excel = pd.ExcelFile(file, engine="openpyxl")
    except Exception:
        # Fallback without specifying engine
        if hasattr(file, "seek"):
            file.seek(0)
        excel = pd.ExcelFile(file)

    text_parts = []
    for sheet_name in excel.sheet_names:
        df = pd.read_excel(excel, sheet_name=sheet_name)
        sheet_str = f"--- Sheet: {sheet_name} ---\n"
        sheet_str += df.to_string(index=False)
        text_parts.append(sheet_str)

    if hasattr(file, "seek"):
        file.seek(0)

    return "\n\n".join(text_parts).strip()


def extract_xls_text(file) -> str:
    """
    Extract text content from all sheets of a legacy Excel .xls workbook.
    """
    if hasattr(file, "seek"):
        file.seek(0)

    try:
        excel = pd.ExcelFile(file, engine="xlrd")
    except Exception:
        if hasattr(file, "seek"):
            file.seek(0)
        excel = pd.ExcelFile(file)

    text_parts = []
    for sheet_name in excel.sheet_names:
        df = pd.read_excel(excel, sheet_name=sheet_name)
        sheet_str = f"--- Sheet: {sheet_name} ---\n"
        sheet_str += df.to_string(index=False)
        text_parts.append(sheet_str)

    if hasattr(file, "seek"):
        file.seek(0)

    return "\n\n".join(text_parts).strip()
