"""
Basis-Parser für SciLit
----------------------
Enthält die Basisklasse für alle Dokumentenparser und gemeinsame Funktionalitäten.
"""

import re
import logging
from typing import Dict, Tuple, Any
from pathlib import Path

# Logger konfigurieren
logger = logging.getLogger("scilit.document.parsers.base")

class DocumentParsingError(Exception):
    """Fehlerklasse für Probleme beim Parsen von Dokumenten."""
    pass

class DocumentParser:
    """
    Basisklasse für alle Dokumentenparser.
    
    Diese Klasse definiert die gemeinsame Schnittstelle für alle Parser
    und enthält Hilfsmethoden für gemeinsame Funktionalitäten.
    
    Attributes:
        page_count (int): Anzahl der Seiten im Dokument
        language (str): Erkannte Sprache des Dokuments
    """
    
    def __init__(self):
        """Initialisiert den Dokumentparser."""
        self.page_count = 0
        self.language = "auto"
    
    def parse(self, filepath: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parst ein Dokument und extrahiert Text und Metadaten.
        
        Args:
            filepath: Pfad zur zu parsenden Datei
            
        Returns:
            Tuple aus (extrahierter Text, Dictionary mit Metadaten)
            
        Raises:
            NotImplementedError: Wenn die Unterklasse diese Methode nicht implementiert
        """
        raise NotImplementedError("Unterklassen müssen diese Methode implementieren")
    
    def _clean_text(self, text: str) -> str:
        """
        Bereinigt den extrahierten Text.
        
        Diese Methode entfernt übermäßige Leerzeichen, Seitenumbrüche und andere
        unerwünschte Artefakte aus dem extrahierten Text.
        
        Args:
            text: Der zu bereinigende Text
            
        Returns:
            Bereinigter Text
        """
        if not text:
            return ""
        
        # Ersetze mehrere Leerzeilen durch eine
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Ersetze mehrere Leerzeichen durch eines (außer am Zeilenende)
        text = re.sub(r' {2,}(?!\n)', ' ', text)
        
        # Entferne Leerzeichen am Zeilenbeginn und -ende
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)
        
        return text.strip()
    
    def _extract_basic_metadata(self, filepath: str) -> Dict[str, Any]:
        """
        Extrahiert grundlegende Metadaten aus dem Dateipfad.
        
        Args:
            filepath: Pfad zur Datei
            
        Returns:
            Dictionary mit grundlegenden Metadaten
        """
        file_path = Path(filepath)
        
        metadata = {
            "filename": file_path.name,
            "file_extension": file_path.suffix.lower(),
            "file_size": file_path.stat().st_size
        }
        
        return metadata