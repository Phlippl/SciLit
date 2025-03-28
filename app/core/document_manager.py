"""
Dokumentenverwaltungssystem für SciLit
--------------------------------------
Dieses Modul stellt die Hauptschnittstelle für die Dokumentenverwaltung bereit,
einschließlich Speicherung, Abruf und Verwaltung von verarbeiteten Dokumenten.
"""

import os
import json
import logging
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime

from .document_processor import DocumentProcessor
from .metadata_api_client import MetadataAPIClient
from .text_analysis import TextAnalyzer

# Logger konfigurieren
logger = logging.getLogger("scilit.document_manager")

class DocumentManager:
    """Zentrale Klasse zur Verwaltung aller Dokumente."""
    
    def __init__(self, base_dir: str):
        """
        Initialisiert den Dokumenten-Manager.
        
        Args:
            base_dir: Basisverzeichnis für alle Dateien
        """
        self.base_dir = base_dir
        self.upload_dir = os.path.join(base_dir, "uploads")
        self.processed_dir = os.path.join(base_dir, "processed")
        
        # Verzeichnisse sicherstellen
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        
        # Dokumenten-Index initialisieren
        self.index_file = os.path.join(self.processed_dir, "document_index.json")
        self.documents = self._load_document_index()
        
        # Dokumenten-Prozessor erstellen
        self.processor = DocumentProcessor(self.upload_dir, self.processed_dir)
    
    def _load_document_index(self) -> Dict[str, Dict[str, Any]]:
        """Lädt den Index aller verarbeiteten Dokumente."""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Fehler beim Laden des Dokument-Index: {str(e)}")
                return {}
        return {}
    
    def _save_document_index(self):
        """Speichert den Index aller verarbeiteten Dokumente."""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Fehler beim Speichern des Dokument-Index: {str(e)}")
    
    def process_document(self, filename: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Verarbeitet ein hochgeladenes Dokument.
        
        Args:
            filename: Name der zu verarbeitenden Datei im Upload-Verzeichnis
            options: Optionen für die Verarbeitung (z.B. OCR-Einstellungen)
            
        Returns:
            Dokumentinformationen nach der Verarbeitung
        """
        try:
            # Optionen für den Prozessor setzen
            if options:
                if 'ocr_if_needed' in options:
                    self.processor.ocr_if_needed = options['ocr_if_needed']
                if 'language' in options:
                    self.processor.language = options['language']
                if any(k.startswith('use_') for k in options):
                    # Metadaten-API-Optionen setzen
                    for key in options:
                        if key.startswith('use_') and key in self.processor.metadata_sources:
                            self.processor.metadata_sources[key] = options[key]
            
            # Dokument verarbeiten
            result = self.processor.process_document(filename)
            
            # Zu Dokumentenindex hinzufügen
            doc_id = result['id']
            
            # Aktuelle Zeit für hinzugefügt/aktualisiert
            timestamp = datetime.now().isoformat()
            
            if doc_id in self.documents:
                # Dokument aktualisieren
                self.documents[doc_id].update({
                    'metadata': result['metadata'],
                    'chunks_count': result['chunks_count'],
                    'updated_at': timestamp
                })
            else:
                # Neues Dokument
                self.documents[doc_id] = {
                    'id': doc_id,
                    'filename': result['filename'],
                    'filepath': result['filepath'],
                    'metadata': result['metadata'],
                    'chunks_count': result['chunks_count'],
                    'added_at': timestamp,
                    'updated_at': timestamp
                }
            
            # Index speichern
            self._save_document_index()
            
            return self.documents[doc_id]
            
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung von {filename}: {str(e)}")
            raise
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Gibt alle verfügbaren Dokumente zurück."""
        return list(self.documents.values())
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Gibt ein spezifisches Dokument zurück."""
        return self.documents.get(doc_id)
    
    def get_document_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Gibt die Metadaten eines Dokuments zurück."""
        if doc_id not in self.documents:
            return None
        
        doc_dir = os.path.join(self.processed_dir, doc_id)
        metadata_file = os.path.join(doc_dir, "metadata.json")
        
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self.documents[doc_id].get('metadata', {})
        
        return self.documents[doc_id].get('metadata', {})
    
    def get_document_text(self, doc_id: str) -> Optional[str]:
        """Gibt den vollständigen Text eines Dokuments zurück."""
        if doc_id not in self.documents:
            return None
        
        doc_dir = os.path.join(self.processed_dir, doc_id)
        text_file = os.path.join(doc_dir, "fulltext.txt")
        
        if os.path.exists(text_file):
            try:
                with open(text_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except IOError:
                return None
        
        return None
    
    def get_document_chunks(self, doc_id: str) -> Optional[List[Dict[str, Any]]]:
        """Gibt die Chunks eines Dokuments zurück."""
        if doc_id not in self.documents:
            return None
        
        doc_dir = os.path.join(self.processed_dir, doc_id)
        chunks_file = os.path.join(doc_dir, "chunks.json")
        
        if os.path.exists(chunks_file):
            try:
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        
        return []
    
    def delete_document(self, doc_id: str) -> bool:
        """Löscht ein Dokument und alle zugehörigen Dateien."""
        if doc_id not in self.documents:
            return False
        
        try:
            # Verzeichnis löschen
            doc_dir = os.path.join(self.processed_dir, doc_id)
            if os.path.exists(doc_dir):
                shutil.rmtree(doc_dir)
            
            # Aus Index entfernen
            del self.documents[doc_id]
            
            # Index speichern
            self._save_document_index()
            
            return True
        except Exception as e:
            logger.error(f"Fehler beim Löschen von Dokument {doc_id}: {str(e)}")
            return False
    
    def update_document_metadata(self, doc_id: str, metadata: Dict[str, Any]) -> bool:
        """Aktualisiert die Metadaten eines Dokuments."""
        if doc_id not in self.documents:
            return False
        
        try:
            # Metadaten im Index aktualisieren
            self.documents[doc_id]['metadata'].update(metadata)
            self.documents[doc_id]['updated_at'] = datetime.now().isoformat()
            
            # Metadaten-Datei aktualisieren
            doc_dir = os.path.join(self.processed_dir, doc_id)
            metadata_file = os.path.join(doc_dir, "metadata.json")
            
            if os.path.exists(metadata_file):
                # Bestehende Metadaten laden und aktualisieren
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        existing_metadata = json.load(f)
                    
                    existing_metadata.update(metadata)
                    
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(existing_metadata, f, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Fehler beim Aktualisieren der Metadaten für {doc_id}: {str(e)}")
                    return False
            else:
                # Neue Metadaten-Datei erstellen
                os.makedirs(doc_dir, exist_ok=True)
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(self.documents[doc_id]['metadata'], f, ensure_ascii=False, indent=2)
            
            # Index speichern
            self._save_document_index()
            
            return True
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Metadaten für {doc_id}: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Gibt Statistiken über alle verwalteten Dokumente zurück."""
        stats = {
            "total_documents": len(self.documents),
            "total_pages": 0,
            "total_chunks": 0,
            "file_types": {},
            "years": {},
            "languages": {},
            "storage_used": self._calculate_storage_usage()
        }
        
        for doc_id, doc in self.documents.items():
            # Seitenzahl addieren
            page_count = doc['metadata'].get('page_count', 0)
            stats["total_pages"] += page_count
            
            # Chunks addieren
            chunks_count = doc.get('chunks_count', 0)
            stats["total_chunks"] += chunks_count
            
            # Dateityp zählen
            file_ext = os.path.splitext(doc['filename'])[1].lower()
            if file_ext in stats["file_types"]:
                stats["file_types"][file_ext] += 1
            else:
                stats["file_types"][file_ext] = 1
            
            # Jahr zählen
            year = doc['metadata'].get('year')
            if year:
                year_str = str(year)
                if year_str in stats["years"]:
                    stats["years"][year_str] += 1
                else:
                    stats["years"][year_str] = 1
            
            # Sprache zählen
            language = doc['metadata'].get('language')
            if language:
                if language in stats["languages"]:
                    stats["languages"][language] += 1
                else:
                    stats["languages"][language] = 1
        
        return stats
    
    def _calculate_storage_usage(self) -> str:
        """Berechnet den verwendeten Speicherplatz in einem lesbaren Format."""
        total_size = 0
        
        # Größe des Upload-Verzeichnisses
        for root, dirs, files in os.walk(self.upload_dir):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        
        # Größe des Verarbeitungs-Verzeichnisses
        for root, dirs, files in os.walk(self.processed_dir):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        
        # In lesbare Größe umwandeln
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size_format = total_size
        unit_index = 0
        
        while size_format >= 1024 and unit_index < len(units) - 1:
            size_format /= 1024
            unit_index += 1
        
        return f"{size_format:.2f} {units[unit_index]}"


# Singleton-Instanz des Document Manager
_instance = None

def get_document_manager(base_dir: str) -> DocumentManager:
    """Gibt eine Singleton-Instanz des DocumentManager zurück."""
    global _instance
    if _instance is None:
        _instance = DocumentManager(base_dir)
    return _instance