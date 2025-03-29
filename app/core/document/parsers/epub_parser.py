"""
EPUB-Parser für SciLit
-------------------
Parser für E-Book-Dokumente im EPUB-Format.
"""

import logging
from typing import Dict, Tuple, Any

# EPUB-Verarbeitung
try:
    import epub2txt
except ImportError:
    epub2txt = None

from app.core.document.parsers.base_parser import DocumentParser, DocumentParsingError

# Logger konfigurieren
logger = logging.getLogger("scilit.document.parsers.epub")

class EPUBParser(DocumentParser):
    """
    Parser für EPUB-Dokumente.
    
    Dieser Parser extrahiert Text und Metadaten aus EPUB-Dateien
    mit dem epub2txt Paket.
    """
    
    def parse(self, filepath: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parst ein EPUB-Dokument und extrahiert Text und Metadaten.
        
        Args:
            filepath: Pfad zum EPUB
            
        Returns:
            Tuple aus (extrahierter Text, Dictionary mit Metadaten)
            
        Raises:
            DocumentParsingError: Bei Problemen mit dem Parsing
        """
        if not epub2txt:
            raise DocumentParsingError("epub2txt ist nicht installiert")
        
        try:
            # Metadaten aus Dateiinformationen
            metadata = self._extract_basic_metadata(filepath)
            
            # EPUBs verarbeiten
            text = epub2txt.epub2txt(filepath)
            
            # Extrahiere Metadaten, wenn vorhanden
            # (Anmerkung: epub2txt extrahiert nicht direkt Metadaten, wir bräuchten ebooklib für eine detailliertere Extraktion)
            
            # Schätze die Seitenzahl basierend auf der Textlänge
            # (eine Buchseite enthält ca. 2000 Zeichen)
            self.page_count = max(1, len(text) // 2000)
            metadata["page_count"] = self.page_count
            
            return self._clean_text(text), metadata
            
        except Exception as e:
            raise DocumentParsingError(f"Fehler beim EPUB-Parsing: {str(e)}")