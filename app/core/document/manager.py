"""
Dokumentenverwaltungssystem für SciLit
--------------------------------------
Dieses Modul stellt die zentrale Schnittstelle für die Dokumentenverwaltung bereit,
einschließlich Speicherung, Abruf und Verwaltung von verarbeiteten Dokumenten.
"""

import os
import json
import logging
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from app.config import PROCESSED_DIR, UPLOAD_DIR
from app.core.document.processor import DocumentProcessor
from app.utils.file_utils import get_file_size_str

# Logger konfigurieren
logger = logging.getLogger("scilit.document.manager")

class DocumentManager:
    """
    Zentrale Klasse zur Verwaltung aller Dokumente im SciLit-System.
    
    Diese Klasse bietet Methoden zum Verarbeiten, Abrufen, Aktualisieren und Löschen
    von Dokumenten sowie zum Verwalten des Dokumentenindex.
    
    Attributes:
        upload_dir (Path): Verzeichnis für hochgeladene Dateien
        processed_dir (Path): Verzeichnis für verarbeitete Dateien
        index_file (Path): Pfad zur Index-Datei
        documents (Dict): In-Memory-Cache der Dokumente
        processor (DocumentProcessor): Prozessor für Dokumentenverarbeitung
    """
    
    def __init__(self):
        """Initialisiert den DocumentManager mit Standardeinstellungen."""
        self.upload_dir = Path(UPLOAD_DIR)
        self.processed_dir = Path(PROCESSED_DIR)
        
        # Dokumenten-Index initialisieren
        self.index_file = self.processed_dir / "document_index.json"
        self.documents = self._load_document_index()
        
        # Dokumenten-Prozessor erstellen
        self.processor = DocumentProcessor()
    
    def _load_document_index(self) -> Dict[str, Dict[str, Any]]:
        """
        Lädt den Index aller verarbeiteten Dokumente.
        
        Returns:
            Dict[str, Dict[str, Any]]: Index der Dokumente mit Dokument-ID als Schlüssel
        """
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Fehler beim Laden des Dokument-Index: {str(e)}")
                # Sicherungskopie des beschädigten Index erstellen
                if self.index_file.exists():
                    backup_path = self.index_file.with_suffix('.json.bak')
                    shutil.copy2(self.index_file, backup_path)
                    logger.info(f"Sicherungskopie des beschädigten Index erstellt: {backup_path}")
                return {}
        return {}
    
    def _save_document_index(self) -> bool:
        """
        Speichert den Index aller verarbeiteten Dokumente.
        
        Returns:
            bool: True bei erfolgreichem Speichern, False bei Fehler
        """
        try:
            # Temporäre Datei verwenden, um Datenverlust zu vermeiden
            temp_file = self.index_file.with_suffix('.json.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
            
            # Nach erfolgreichem Schreiben die Datei umbenennen
            temp_file.replace(self.index_file)
            return True
        except IOError as e:
            logger.error(f"Fehler beim Speichern des Dokument-Index: {str(e)}")
            return False
    
    def process_document(self, filename: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Verarbeitet ein hochgeladenes Dokument mit dem DocumentProcessor.
        
        Args:
            filename (str): Name der zu verarbeitenden Datei im Upload-Verzeichnis
            options (Dict[str, Any], optional): Optionen für die Verarbeitung
            
        Returns:
            Dict[str, Any]: Dokumentinformationen nach der Verarbeitung
            
        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert
            ValueError: Bei ungültigen Optionen oder Dateiformaten
            RuntimeError: Bei Verarbeitungsfehlern
        """
        try:
            # Prüfen, ob die Datei existiert
            file_path = self.upload_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Datei nicht gefunden: {filename}")
            
            # Dokument verarbeiten
            result = self.processor.process_document(str(file_path), options)
            
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
                logger.info(f"Dokument aktualisiert: {doc_id}")
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
                logger.info(f"Neues Dokument hinzugefügt: {doc_id}")
            
            # Index speichern
            self._save_document_index()
            
            return self.documents[doc_id]
            
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung von {filename}: {str(e)}")
            raise
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Gibt eine Liste aller verfügbaren Dokumente zurück.
        
        Returns:
            List[Dict[str, Any]]: Liste aller Dokumente
        """
        # Dokumente als Liste zurückgeben
        return list(self.documents.values())
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Gibt ein spezifisches Dokument anhand seiner ID zurück.
        
        Args:
            doc_id (str): Die Dokument-ID
            
        Returns:
            Optional[Dict[str, Any]]: Das Dokument oder None, wenn nicht gefunden
        """
        return self.documents.get(doc_id)
    
    def get_document_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Gibt die Metadaten eines Dokuments zurück.
        
        Lädt die vollständigen Metadaten aus der JSON-Datei, nicht nur aus dem Index.
        
        Args:
            doc_id (str): Die Dokument-ID
            
        Returns:
            Optional[Dict[str, Any]]: Die Metadaten oder None, wenn nicht gefunden
        """
        if doc_id not in self.documents:
            return None
        
        doc_dir = self.processed_dir / doc_id
        metadata_file = doc_dir / "metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Fehler beim Laden der Metadaten für {doc_id}: {str(e)}")
                return self.documents[doc_id].get('metadata', {})
        
        return self.documents[doc_id].get('metadata', {})
    
    def get_document_text(self, doc_id: str) -> Optional[str]:
        """
        Gibt den vollständigen Text eines Dokuments zurück.
        
        Args:
            doc_id (str): Die Dokument-ID
            
        Returns:
            Optional[str]: Der Text oder None, wenn nicht gefunden
        """
        if doc_id not in self.documents:
            return None
        
        doc_dir = self.processed_dir / doc_id
        text_file = doc_dir / "fulltext.txt"
        
        if text_file.exists():
            try:
                with open(text_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except IOError as e:
                logger.warning(f"Fehler beim Lesen der Textdatei für {doc_id}: {str(e)}")
                return None
        
        return None
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Gibt die Chunks eines Dokuments zurück.
        
        Args:
            doc_id (str): Die Dokument-ID
            
        Returns:
            List[Dict[str, Any]]: Die Chunks oder leere Liste, wenn nicht gefunden
        """
        if doc_id not in self.documents:
            return []
        
        doc_dir = self.processed_dir / doc_id
        chunks_file = doc_dir / "chunks.json"
        
        if chunks_file.exists():
            try:
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Fehler beim Laden der Chunks für {doc_id}: {str(e)}")
                return []
        
        return []
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Löscht ein Dokument und alle zugehörigen Dateien.
        
        Args:
            doc_id (str): Die Dokument-ID
            
        Returns:
            bool: True bei erfolgreicher Löschung, False bei Fehler
        """
        if doc_id not in self.documents:
            logger.warning(f"Dokument nicht gefunden für Löschung: {doc_id}")
            return False
        
        try:
            # Verzeichnis löschen
            doc_dir = self.processed_dir / doc_id
            if doc_dir.exists():
                shutil.rmtree(doc_dir)
                logger.info(f"Verzeichnis gelöscht für Dokument {doc_id}")
            
            # Aus Index entfernen
            del self.documents[doc_id]
            logger.info(f"Dokument aus Index entfernt: {doc_id}")
            
            # Index speichern
            success = self._save_document_index()
            if not success:
                logger.warning(f"Fehler beim Speichern des Index nach Löschung von {doc_id}")
            
            return True
        except Exception as e:
            logger.error(f"Fehler beim Löschen von Dokument {doc_id}: {str(e)}")
            return False
    
    def update_document_metadata(self, doc_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Aktualisiert die Metadaten eines Dokuments.
        
        Args:
            doc_id (str): Die Dokument-ID
            metadata (Dict[str, Any]): Die zu aktualisierenden Metadaten
            
        Returns:
            bool: True bei erfolgreicher Aktualisierung, False bei Fehler
        """
        if doc_id not in self.documents:
            logger.warning(f"Dokument nicht gefunden für Metadaten-Update: {doc_id}")
            return False
        
        try:
            # Metadaten im Index aktualisieren
            if 'metadata' not in self.documents[doc_id]:
                self.documents[doc_id]['metadata'] = {}
                
            self.documents[doc_id]['metadata'].update(metadata)
            self.documents[doc_id]['updated_at'] = datetime.now().isoformat()
            
            # Metadaten-Datei aktualisieren
            doc_dir = self.processed_dir / doc_id
            metadata_file = doc_dir / "metadata.json"
            
            if metadata_file.exists():
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
                # Verzeichnis erstellen, falls es nicht existiert
                doc_dir.mkdir(parents=True, exist_ok=True)
                
                # Neue Metadaten-Datei erstellen
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(self.documents[doc_id]['metadata'], f, ensure_ascii=False, indent=2)
            
            # Index speichern
            success = self._save_document_index()
            if not success:
                logger.warning(f"Fehler beim Speichern des Index nach Metadaten-Update für {doc_id}")
                return False
            
            logger.info(f"Metadaten aktualisiert für Dokument {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Metadaten für {doc_id}: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Gibt Statistiken über alle verwalteten Dokumente zurück.
        
        Returns:
            Dict[str, Any]: Statistiken über Dokumente, Seitenzahlen, Speicher, etc.
        """
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
            page_count = doc.get('metadata', {}).get('page_count', 0)
            stats["total_pages"] += page_count
            
            # Chunks addieren
            chunks_count = doc.get('chunks_count', 0)
            stats["total_chunks"] += chunks_count
            
            # Dateityp zählen
            file_ext = Path(doc.get('filename', '')).suffix.lower()
            if file_ext in stats["file_types"]:
                stats["file_types"][file_ext] += 1
            else:
                stats["file_types"][file_ext] = 1
            
            # Jahr zählen
            year = doc.get('metadata', {}).get('year')
            if year:
                year_str = str(year)
                if year_str in stats["years"]:
                    stats["years"][year_str] += 1
                else:
                    stats["years"][year_str] = 1
            
            # Sprache zählen
            language = doc.get('metadata', {}).get('language')
            if language:
                if language in stats["languages"]:
                    stats["languages"][language] += 1
                else:
                    stats["languages"][language] = 1
        
        return stats
    
    def _calculate_storage_usage(self) -> str:
        """
        Berechnet den verwendeten Speicherplatz in einem lesbaren Format.
        
        Returns:
            str: Formatierte Speichernutzung (z.B. "1.23 MB")
        """
        total_size = 0
        
        # Größe des Upload-Verzeichnisses
        for item in self.upload_dir.glob('**/*'):
            if item.is_file():
                total_size += item.stat().st_size
        
        # Größe des Verarbeitungs-Verzeichnisses
        for item in self.processed_dir.glob('**/*'):
            if item.is_file():
                total_size += item.stat().st_size
        
        return get_file_size_str(total_size)


# Singleton-Instanz des Document Manager
_instance = None

def get_document_manager() -> DocumentManager:
    """
    Gibt eine Singleton-Instanz des DocumentManager zurück.
    
    Returns:
        DocumentManager: Die Singleton-Instanz
    """
    global _instance
    if _instance is None:
        _instance = DocumentManager()
    return _instance