"""
Dokumentenverarbeitung für SciLit
---------------------------------
Hauptklasse für die Koordination der Dokumentenverarbeitung.
"""

import os
import logging
import shutil
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from app.config import UPLOAD_DIR, PROCESSED_DIR, DEFAULT_PROCESSING_OPTIONS
from app.core.document.parsers import determine_parser_for_file, DocumentParsingError
from app.core.metadata.extractor import extract_title_from_text, extract_authors_from_text
from app.core.metadata.api_client import MetadataAPIClient
from app.core.analysis.text_splitter import TextSplitter
from app.utils.file_utils import generate_unique_id, ensure_dir_exists

# Logger konfigurieren
logger = logging.getLogger("scilit.document.processor")

class DocumentProcessor:
    """
    Hauptklasse für die Verarbeitung von Dokumenten in SciLit.
    
    Diese Klasse koordiniert den gesamten Verarbeitungsprozess eines Dokuments:
    1. Text- und Metadatenextraktion aus dem Originaldokument
    2. Erweiterung der Metadaten über externe APIs
    3. Aufteilung des Textes in Chunks für die Vektorisierung
    4. Speicherung aller Verarbeitungsergebnisse
    
    Attributes:
        upload_dir (str): Verzeichnis für hochgeladene Dateien
        processed_dir (str): Verzeichnis für verarbeitete Dateien
        ocr_if_needed (bool): Ob OCR bei Bedarf angewendet werden soll
        language (str): Hauptsprache der Dokumente ('de', 'en', 'auto', 'mixed')
        metadata_sources (Dict[str, bool]): Welche Metadaten-APIs verwendet werden sollen
    """
    
    def __init__(
        self, 
        upload_dir: str = UPLOAD_DIR, 
        processed_dir: str = PROCESSED_DIR,
        **kwargs
    ):
        """
        Initialisiert den Dokumentenprozessor.
        
        Args:
            upload_dir: Verzeichnis für hochgeladene Dateien
            processed_dir: Verzeichnis für verarbeitete Dateien
            **kwargs: Weitere Optionen, die die Standardeinstellungen überschreiben
        """
        self.upload_dir = upload_dir
        self.processed_dir = processed_dir
        
        # Verarbeitungsoptionen mit Standardwerten initialisieren
        options = DEFAULT_PROCESSING_OPTIONS.copy()
        options.update(kwargs)  # Überschreibe mit übergebenen Optionen
        
        self.ocr_if_needed = options.get("ocr_if_needed", True)
        self.language = options.get("language", "auto")
        self.metadata_sources = {k: v for k, v in options.items() if k.startswith("use_")}
        
        # Verzeichnisse sicherstellen
        ensure_dir_exists(self.upload_dir)
        ensure_dir_exists(self.processed_dir)
        
        # Hilfsobjekte initialisieren
        self.text_splitter = TextSplitter()
        self.api_client = MetadataAPIClient(self.metadata_sources)
    
    def process_document(self, filepath: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Verarbeitet ein Dokument vollständig.
        
        Diese Methode koordiniert den gesamten Verarbeitungsprozess eines Dokuments und
        gibt die Ergebnisse zurück.
        
        Args:
            filepath: Pfad zur zu verarbeitenden Datei
            options: Optionale Überschreibungen für die Verarbeitungseinstellungen
            
        Returns:
            Dict mit Metadaten und Verarbeitungsergebnissen
            
        Raises:
            FileNotFoundError: Wenn die Datei nicht gefunden wird
            DocumentParsingError: Bei Problemen mit der Dokumentenanalyse
            ValueError: Bei Problemen mit den Verarbeitungsoptionen
            IOError: Bei Problemen mit Dateisystem-Operationen
        """
        filepath = os.path.abspath(filepath)
        logger.info(f"Verarbeite Dokument: {filepath}")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Datei nicht gefunden: {filepath}")
        
        # Temporäre Optionen anwenden, falls vorhanden
        original_options = {}
        if options:
            # Optionen speichern, um sie später wiederherzustellen
            if "ocr_if_needed" in options:
                original_options["ocr_if_needed"] = self.ocr_if_needed
                self.ocr_if_needed = options["ocr_if_needed"]
            
            if "language" in options:
                original_options["language"] = self.language
                self.language = options["language"]
            
            for key, value in options.items():
                if key.startswith("use_") and key in self.metadata_sources:
                    original_options[key] = self.metadata_sources[key]
                    self.metadata_sources[key] = value
        
        try:
            # Eindeutige ID für das Dokument erzeugen
            doc_id = generate_unique_id(filepath)
            filename = os.path.basename(filepath)
            
            # Metadaten-Verzeichnis erstellen
            doc_dir = os.path.join(self.processed_dir, doc_id)
            ensure_dir_exists(doc_dir)
            
            # Datei ins verarbeitete Verzeichnis kopieren
            target_filepath = os.path.join(doc_dir, filename)
            shutil.copy2(filepath, target_filepath)
            
            # Extrahiere Text und Basis-Metadaten aus dem Dokument
            text, basic_metadata = self.extract_content_and_metadata(filepath)
            
            # Erweiterte Metadaten über APIs abrufen
            metadata = self.api_client.enhance_metadata(basic_metadata)
            
            # Text in Chunks aufteilen
            chunks = self.text_splitter.split_text_into_chunks(text, metadata.get("language", self.language))
            
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
        
        finally:
            # Originale Optionen wiederherstellen
            for key, value in original_options.items():
                if key == "ocr_if_needed":
                    self.ocr_if_needed = value
                elif key == "language":
                    self.language = value
                elif key in self.metadata_sources:
                    self.metadata_sources[key] = value
    
    def extract_content_and_metadata(self, filepath: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extrahiert Text und grundlegende Metadaten aus einem Dokument.
        
        Diese Methode bestimmt den passenden Parser für den Dateityp und extrahiert
        den Text und die Metadaten. Fehlende Metadaten werden, wenn möglich, 
        aus dem Text abgeleitet.
        
        Args:
            filepath: Pfad zur Datei
            
        Returns:
            Tuple aus (extrahierter Text, Dictionary mit Metadaten)
            
        Raises:
            DocumentParsingError: Wenn die Dokumentenverarbeitung fehlschlägt
            ValueError: Wenn der Dateityp nicht unterstützt wird
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
        
        # Standardsprache hinzufügen, falls nicht angegeben
        if 'language' not in metadata or not metadata['language']:
            metadata['language'] = self.language
        
        return text, metadata
    
    def _save_processing_results(self, doc_dir: str, text: str, metadata: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
        """
        Speichert die Verarbeitungsergebnisse im Dokumentenverzeichnis.
        
        Args:
            doc_dir: Verzeichnis für die Dokumente
            text: Extrahierter Text
            metadata: Metadaten-Dictionary
            chunks: Liste der Textabschnitte mit Metadaten
            
        Raises:
            IOError: Bei Problemen mit dem Dateisystem
        """
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
        
        logger.debug(f"Verarbeitungsergebnisse gespeichert in {doc_dir}")
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten durch Abfragen verschiedener APIs.
        
        Delegiert an den MetadataAPIClient, um Metadaten anzureichern.
        
        Args:
            basic_metadata: Aus dem Dokument extrahierte Metadaten
            
        Returns:
            Erweiterte Metadaten
        """
        return self.api_client.enhance_metadata(basic_metadata)