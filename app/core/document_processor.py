"""
Dokumentenverarbeitung für SciLit
---------------------------------
Hauptklasse für die Koordination der Dokumentenverarbeitung.
"""

import os
import logging
import shutil
import hashlib
from typing import Dict, List, Optional, Tuple, Any

from .document_parsers import determine_parser_for_file, DocumentParsingError
from .metadata_extraction import extract_title_from_text, extract_authors_from_text
from .metadata_api_client import MetadataAPIClient
from .text_analysis import TextAnalyzer

# Logger konfigurieren
logger = logging.getLogger("scilit.document_processor")

class DocumentProcessor:
    """Hauptklasse für die Verarbeitung von Dokumenten."""
    
    def __init__(
        self, 
        upload_dir: str, 
        processed_dir: str,
        ocr_if_needed: bool = True,
        language: str = "auto",
        metadata_sources: Dict[str, bool] = None
    ):
        """
        Initialisiert den Dokumentenprozessor.
        
        Args:
            upload_dir: Verzeichnis für hochgeladene Dateien
            processed_dir: Verzeichnis für verarbeitete Dateien
            ocr_if_needed: Ob OCR bei Bedarf angewendet werden soll
            language: Hauptsprache der Dokumente ('de', 'en', 'auto', 'mixed')
            metadata_sources: Welche Metadaten-APIs verwendet werden sollen
        """
        self.upload_dir = upload_dir
        self.processed_dir = processed_dir
        self.ocr_if_needed = ocr_if_needed
        self.language = language
        
        # Standardwerte für Metadatenquellen, wenn nicht angegeben
        self.metadata_sources = metadata_sources or {
            "use_crossref": True,
            "use_openlib": True,
            "use_k10plus": True,
            "use_googlebooks": True,
            "use_openalex": True,
        }
        
        # Verzeichnisse sicherstellen
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        
        # Hilfsobjekte initialisieren
        self.text_analyzer = TextAnalyzer()
        self.api_client = MetadataAPIClient(self.metadata_sources)
    
    def process_document(self, filename: str) -> Dict[str, Any]:
        """
        Verarbeitet ein Dokument vollständig.
        
        Args:
            filename: Name der zu verarbeitenden Datei im Upload-Verzeichnis
            
        Returns:
            Dict mit Metadaten und Verarbeitungsergebnissen
        """
        filepath = os.path.join(self.upload_dir, filename)
        logger.info(f"Verarbeite Dokument: {filepath}")
        
        # Eindeutige ID für das Dokument erzeugen
        doc_id = self._generate_document_id(filepath)
        
        # Metadaten-Verzeichnis erstellen
        doc_dir = os.path.join(self.processed_dir, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        
        # Datei ins verarbeitete Verzeichnis kopieren
        target_filepath = os.path.join(doc_dir, filename)
        shutil.copy2(filepath, target_filepath)
        
        # Extrahiere Text und Basis-Metadaten aus dem Dokument
        text, basic_metadata = self.extract_content_and_metadata(filepath)
        
        # Erweiterte Metadaten über APIs abrufen
        metadata = self.api_client.enhance_metadata(basic_metadata)
        
        # Text in Chunks aufteilen
        chunks = self.text_analyzer.split_text_into_chunks(text, metadata.get("language", self.language))
        
        # Ergebnisse speichern
        self._save_processing_results(doc_dir, text, metadata, chunks)
        
        # Rückgabe-Dictionary erstellen
        result = {
            "id": doc_id,
            "filename": filename,
            "filepath": target_filepath,
            "metadata": metadata,
            "chunks_count": len(chunks),
            "status": "processed"
        }
        
        logger.info(f"Dokument erfolgreich verarbeitet: {doc_id}")
        return result
    
    def _generate_document_id(self, filepath: str) -> str:
        """Erzeugt eine eindeutige ID für ein Dokument basierend auf Inhalt und Name."""
        filename = os.path.basename(filepath)
        file_stats = os.stat(filepath)
        
        # Kombiniere Dateiname, Größe und Änderungszeit für einen eindeutigen Hashwert
        id_string = f"{filename}_{file_stats.st_size}_{file_stats.st_mtime}"
        return hashlib.md5(id_string.encode()).hexdigest()[:12]
    
    def extract_content_and_metadata(self, filepath: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extrahiert Text und grundlegende Metadaten aus einem Dokument.
        
        Args:
            filepath: Pfad zur Datei
            
        Returns:
            Tuple aus (extrahierter Text, Dictionary mit Metadaten)
        """
        # Bestimme den Parser basierend auf dem Dateityp
        parser = determine_parser_for_file(filepath, self.ocr_if_needed)
        
        if not parser:
            file_ext = os.path.splitext(filepath)[1].lower()
            raise ValueError(f"Dateityp {file_ext} wird nicht unterstützt")
        
        # Extrahiere Text und Basis-Metadaten
        text, metadata = parser.parse(filepath)
        
        # Versuche fehlende Metadaten aus dem Text zu extrahieren
        if 'title' not in metadata or not metadata['title']:
            potential_title = extract_title_from_text(text)
            if potential_title:
                metadata['title'] = potential_title
        
        if 'author' not in metadata or not metadata['author']:
            potential_authors = extract_authors_from_text(text, filepath)
            if potential_authors:
                metadata['author'] = potential_authors
        
        return text, metadata
    
    def _save_processing_results(self, doc_dir: str, text: str, metadata: Dict[str, Any], chunks: List[Dict[str, Any]]):
        """Speichert die Verarbeitungsergebnisse."""
        import json
        
        # Text speichern
        with open(os.path.join(doc_dir, "fulltext.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        
        # Metadaten speichern
        with open(os.path.join(doc_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # Chunks speichern
        with open(os.path.join(doc_dir, "chunks.json"), "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)