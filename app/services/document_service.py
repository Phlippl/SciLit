# Neue Datei: app/services/document_service.py

"""
Dokument-Service für SciLit
-------------------------
Service für den Zugriff auf verarbeitete Dokumente und zugehörige Operationen.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from app.core.document.manager import get_document_manager
from app.core.document.processor import DocumentProcessor
from app.utils.error_handling import DocumentProcessingError

# Logger konfigurieren
logger = logging.getLogger("scilit.services.document")

class DocumentService:
    """
    Service für Dokumentenoperationen.
    
    Diese Klasse stellt eine vereinfachte Schnittstelle zu Dokumentenoperationen
    bereit und kapselt die Komplexität der zugrunde liegenden Implementierung.
    
    Attributes:
        document_manager: Manager für verarbeitete Dokumente
        document_processor: Prozessor für neue Dokumente
    """
    
    def __init__(self):
        """Initialisiert den DocumentService."""
        self.document_manager = get_document_manager()
        self.document_processor = DocumentProcessor()
        logger.debug("DocumentService initialisiert")
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Gibt alle verfügbaren Dokumente zurück.
        
        Returns:
            Liste aller Dokumente mit ihren Metadaten
        """
        return self.document_manager.get_all_documents()
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Gibt ein bestimmtes Dokument anhand seiner ID zurück.
        
        Args:
            doc_id: ID des gewünschten Dokuments
            
        Returns:
            Das Dokument oder None, wenn nicht gefunden
        """
        return self.document_manager.get_document(doc_id)
    
    def get_document_metadata(self, doc_id: str) -> Dict[str, Any]:
        """
        Gibt die Metadaten eines Dokuments zurück.
        
        Args:
            doc_id: ID des Dokuments
            
        Returns:
            Metadaten des Dokuments oder leeres Dict, wenn nicht gefunden
        """
        return self.document_manager.get_document_metadata(doc_id) or {}
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Gibt die Chunks eines Dokuments zurück.
        
        Args:
            doc_id: ID des Dokuments
            
        Returns:
            Liste der Chunks oder leere Liste, wenn nicht gefunden
        """
        return self.document_manager.get_document_chunks(doc_id) or []
    
    def get_document_text(self, doc_id: str) -> str:
        """
        Gibt den vollständigen Text eines Dokuments zurück.
        
        Args:
            doc_id: ID des Dokuments
            
        Returns:
            Vollständiger Text oder leerer String, wenn nicht gefunden
        """
        text = self.document_manager.get_document_text(doc_id)
        return text or ""
    
    def update_document_metadata(self, doc_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Aktualisiert die Metadaten eines Dokuments.
        
        Args:
            doc_id: ID des Dokuments
            metadata: Neue oder aktualisierte Metadaten
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        return self.document_manager.update_document_metadata(doc_id, metadata)
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Löscht ein Dokument und alle zugehörigen Daten.
        
        Args:
            doc_id: ID des zu löschenden Dokuments
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        return self.document_manager.delete_document(doc_id)
    
    def process_uploaded_document(self, filepath: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Verarbeitet ein hochgeladenes Dokument.
        
        Args:
            filepath: Pfad zur hochgeladenen Datei
            options: Optionale Verarbeitungseinstellungen
            
        Returns:
            Ergebnis der Verarbeitung mit Dokument-ID und Metadaten
            
        Raises:
            DocumentProcessingError: Bei Fehlern während der Verarbeitung
        """
        try:
            return self.document_processor.process_document(filepath, options)
        except Exception as e:
            logger.error(f"Fehler bei der Dokumentenverarbeitung: {str(e)}")
            raise DocumentProcessingError(f"Fehler bei der Verarbeitung: {str(e)}", 
                                        document_name=filepath.split('/')[-1])
    
    def reprocess_document(self, doc_id: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Verarbeitet ein bereits vorhandenes Dokument neu.
        
        Args:
            doc_id: ID des zu aktualisierenden Dokuments
            options: Optionale Verarbeitungseinstellungen
            
        Returns:
            Ergebnis der erneuten Verarbeitung
            
        Raises:
            DocumentProcessingError: Bei Fehlern während der Verarbeitung
            ValueError: Wenn das Dokument nicht gefunden wird
        """
        # Dokument abrufen
        document = self.document_manager.get_document(doc_id)
        if not document:
            raise ValueError(f"Dokument mit ID {doc_id} nicht gefunden")
        
        # Pfad zur ursprünglichen Datei
        filepath = document.get('filepath')
        if not filepath:
            raise DocumentProcessingError(f"Dokumentpfad nicht gefunden für ID {doc_id}", 
                                        document_name=document.get('filename', ''))
        
        # Dokument neu verarbeiten
        return self.process_uploaded_document(filepath, options)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Gibt allgemeine Statistiken über die Dokumentenbibliothek zurück.
        
        Returns:
            Dictionary mit Statistiken (Anzahl Dokumente, Chunks, etc.)
        """
        return self.document_manager.get_statistics()
    
    def search_documents(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Sucht nach Dokumenten anhand von Metadaten (nicht Volltextsuche).
        
        Args:
            query: Suchbegriff (für Titel, Autor, etc.)
            filters: Optionale Filter (Jahr, Dokumenttyp, etc.)
            
        Returns:
            Liste der passenden Dokumente
        """
        documents = self.get_all_documents()
        results = []
        
        query = query.lower()
        
        for doc in documents:
            # Wenn Filter angegeben sind
            if filters and not self._apply_filters(doc, filters):
                continue
            
            # Prüfen auf Übereinstimmung im Titel
            if ('title' in doc.get('metadata', {}) and 
                query in doc['metadata']['title'].lower()):
                results.append(doc)
                continue
            
            # Prüfen auf Übereinstimmung bei Autoren
            authors = doc.get('metadata', {}).get('author', [])
            if isinstance(authors, list):
                for author in authors:
                    if query in author.lower():
                        results.append(doc)
                        break
            elif isinstance(authors, str) and query in authors.lower():
                results.append(doc)
                continue
                
            # Prüfen auf Übereinstimmung in anderen Feldern
            search_fields = ['journal', 'publisher', 'abstract']
            for field in search_fields:
                value = doc.get('metadata', {}).get(field)
                if value and isinstance(value, str) and query in value.lower():
                    results.append(doc)
                    break
        
        return results
    
    def _apply_filters(self, document: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Wendet Filter auf ein Dokument an.
        
        Args:
            document: Das zu prüfende Dokument
            filters: Die anzuwendenden Filter
            
        Returns:
            True, wenn das Dokument den Filtern entspricht, sonst False
        """
        metadata = document.get('metadata', {})
        
        # Filter nach Jahr
        if 'year' in filters and filters['year']:
            doc_year = metadata.get('year')
            if not doc_year or str(doc_year) != str(filters['year']):
                return False
        
        # Filter nach Typ
        if 'type' in filters and filters['type']:
            doc_type = metadata.get('type')
            if not doc_type or doc_type != filters['type']:
                return False
        
        # Filter nach Sprache
        if 'language' in filters and filters['language']:
            doc_lang = metadata.get('language')
            if not doc_lang or doc_lang != filters['language']:
                return False
                
        # Alle Filter bestanden
        return True

# Singleton-Instanz
_document_service_instance = None

def get_document_service() -> DocumentService:
    """
    Gibt eine Singleton-Instanz des DocumentService zurück.
    
    Returns:
        DocumentService-Instanz
    """
    global _document_service_instance
    if _document_service_instance is None:
        _document_service_instance = DocumentService()
    return _document_service_instance