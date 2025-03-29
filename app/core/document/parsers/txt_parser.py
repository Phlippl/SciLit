"""
TXT-Parser für SciLit
------------------
Parser für einfache Textdateien.
"""

import logging
import sys
import os
from typing import Dict, Tuple, Any
from pathlib import Path

from ....core.document.parsers.base_parser import DocumentParser, DocumentParsingError

# Logger konfigurieren
logger = logging.getLogger("scilit.document.parsers.txt")

class TXTParser(DocumentParser):
    """
    Parser für einfache Textdateien.
    
    Dieser Parser extrahiert Text und minimale Metadaten aus reinen Textdateien.
    """
    
    def parse(self, filepath: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parst eine Textdatei und extrahiert Text und Metadaten.
        
        Args:
            filepath: Pfad zur Textdatei
            
        Returns:
            Tuple aus (extrahierter Text, Dictionary mit Metadaten)
            
        Raises:
            DocumentParsingError: Bei Problemen mit dem Parsing
        """
        try:
            # Metadaten aus Dateiinformationen
            metadata = self._extract_basic_metadata(filepath)
            
            # Versuche verschiedene Codierungen, falls utf-8 fehlschlägt
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            text = None
            
            for encoding in encodings:
                try:
                    with open(filepath, 'r', encoding=encoding) as file:
                        text = file.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                raise DocumentParsingError("Konnte die Datei mit keiner bekannten Codierung öffnen")
            
            # Schätze die Seitenzahl basierend auf der Textlänge
            # (eine Seite enthält ca. 2000 Zeichen)
            self.page_count = max(1, len(text) // 2000)
            metadata["page_count"] = self.page_count
            
            # Basistitel aus Dateiname
            metadata["title"] = Path(filepath).stem
            
            return self._clean_text(text), metadata
            
        except Exception as e:
            if isinstance(e, DocumentParsingError):
                raise
            else:
                raise DocumentParsingError(f"Fehler beim TXT-Parsing: {str(e)}")