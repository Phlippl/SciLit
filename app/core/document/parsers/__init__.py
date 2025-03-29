"""
Parser-Paket für SciLit
---------------------
Importiert Parser für verschiedene Dokumenttypen und bietet eine einheitliche Schnittstelle.
"""

import os
import logging
from typing import Optional

# Importiere die Basis- und Fehlerklassen
from app.core.document.parsers.base_parser import DocumentParser, DocumentParsingError

# Importiere alle spezifischen Parser
from app.core.document.parsers.pdf_parser import PDFParser
from app.core.document.parsers.docx_parser import DOCXParser
from app.core.document.parsers.epub_parser import EPUBParser
from app.core.document.parsers.pptx_parser import PPTXParser
from app.core.document.parsers.txt_parser import TXTParser

# Logger konfigurieren
logger = logging.getLogger("scilit.document.parsers")

def determine_parser_for_file(filepath: str, ocr_if_needed: bool = True, language: str = "auto") -> Optional[DocumentParser]:
    """
    Bestimmt den passenden Parser für eine Datei basierend auf der Dateiendung.
    
    Args:
        filepath: Pfad zur Datei
        ocr_if_needed: Ob OCR bei Bedarf angewendet werden soll
        language: Sprache für OCR und Textanalyse
        
    Returns:
        Eine Instanz des passenden Parsers oder None, wenn kein passender Parser gefunden wurde
    """
    # Dateiendung extrahieren und normalisieren
    file_ext = os.path.splitext(filepath)[1].lower()
    
    if file_ext == '.pdf':
        return PDFParser(ocr_if_needed=ocr_if_needed, ocr_language=language)
    elif file_ext == '.docx':
        return DOCXParser()
    elif file_ext == '.epub':
        return EPUBParser()
    elif file_ext == '.pptx':
        return PPTXParser()
    elif file_ext in ['.txt', '.md', '.csv']:
        return TXTParser()
    else:
        logger.warning(f"Kein Parser für Dateityp {file_ext} verfügbar")
        return None

__all__ = [
    'DocumentParser',
    'DocumentParsingError',
    'determine_parser_for_file',
    'PDFParser',
    'DOCXParser',
    'EPUBParser',
    'PPTXParser',
    'TXTParser'
]