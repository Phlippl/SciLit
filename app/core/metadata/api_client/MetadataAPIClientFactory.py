"""
API Client Factory für SciLit
---------------------------
Factory-Klasse zum Erstellen und Verwalten der verschiedenen Metadaten-API-Clients.
"""

import logging
from typing import Dict, List, Any, Optional

from app.api.base_client import BaseAPIClient
from app.api.crossref_client import CrossRefClient
from app.api.openalex_client import OpenAlexClient
from app.api.googlebooks_client import GoogleBooksClient
from app.api.openlib_client import OpenLibraryClient
from app.api.k10plus_client import K10plusClient

# Logger konfigurieren
logger = logging.getLogger("scilit.api.factory")

class MetadataAPIClientFactory:
    """
    Factory-Klasse zum Erstellen und Verwalten von API-Clients.
    
    Diese Klasse erstellt und cached API-Client-Instanzen und bietet eine
    einheitliche Schnittstelle für den Zugriff auf verschiedene Metadatendienste.
    
    Attributes:
        clients (Dict[str, BaseAPIClient]): Cache für API-Client-Instanzen
    """
    
    def __init__(self):
        """Initialisiert die MetadataAPIClientFactory."""
        self.clients = {}
        logger.debug("MetadataAPIClientFactory initialisiert")
    
    def get_client(self, client_type: str) -> Optional[BaseAPIClient]:
        """
        Gibt eine Instanz des angeforderten API-Clients zurück.
        
        Args:
            client_type: Typ des gewünschten Clients ('crossref', 'openalex', etc.)
            
        Returns:
            API-Client-Instanz oder None, wenn der Typ nicht unterstützt wird
        """
        # Normalisiere Typ zur Konsistenz
        client_type = client_type.lower()
        
        # Wenn der Client bereits instanziiert wurde, aus dem Cache zurückgeben
        if client_type in self.clients:
            return self.clients[client_type]
        
        # Andernfalls neuen Client erstellen, cachen und zurückgeben
        client = self._create_client(client_type)
        if client:
            self.clients[client_type] = client
            return client
        
        logger.warning(f"Unbekannter API-Client-Typ: {client_type}")
        return None
    
    def _create_client(self, client_type: str) -> Optional[BaseAPIClient]:
        """
        Erstellt eine neue Instanz des angeforderten API-Clients.
        
        Args:
            client_type: Typ des zu erstellenden Clients
            
        Returns:
            Neue API-Client-Instanz oder None, wenn der Typ nicht unterstützt wird
        """
        if client_type == 'crossref':
            return CrossRefClient()
        elif client_type == 'openalex':
            return OpenAlexClient()
        elif client_type == 'googlebooks':
            return GoogleBooksClient()
        elif client_type == 'openlib':
            return OpenLibraryClient()
        elif client_type == 'k10plus':
            return K10plusClient()
        else:
            return None
    
    def get_all_clients(self) -> Dict[str, BaseAPIClient]:
        """
        Gibt ein Dictionary mit allen verfügbaren API-Clients zurück.
        
        Returns:
            Dictionary mit Client-Namen als Schlüssel und Instanzen als Werte
        """
        # Stelle sicher, dass alle unterstützten Clients erstellt wurden
        for client_type in ['crossref', 'openalex', 'googlebooks', 'openlib', 'k10plus']:
            if client_type not in self.clients:
                self.get_client(client_type)
        
        return self.clients
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any], metadata_sources: Dict[str, bool] = None) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten durch Abfragen aller aktivierten APIs.
        
        Diese Methode koordiniert die Abfragen an verschiedene Metadatendienste und
        kombiniert die Ergebnisse zu einem optimierten Metadatensatz.
        
        Args:
            basic_metadata: Aus dem Dokument extrahierte Metadaten
            metadata_sources: Welche Metadaten-APIs verwendet werden sollen
                            (falls None, werden alle verwendet)
            
        Returns:
            Erweiterte Metadaten
        """
        # Standardmäßig alle APIs aktivieren, wenn nichts anderes angegeben ist
        if metadata_sources is None:
            metadata_sources = {
                'crossref': True,
                'openalex': True,
                'googlebooks': True,
                'openlib': True,
                'k10plus': True
            }
        
        # Titel oder Autor aus den Basis-Metadaten extrahieren
        title = basic_metadata.get('title', '')
        authors = basic_metadata.get('author', [])
        if isinstance(authors, str):
            authors = [authors]
        
        logger.info(f"Erweitere Metadaten für Titel: {title}, Autoren: {authors}")
        
        # Ergebnisse aus allen aktivierten APIs sammeln
        api_results = []
        
        for client_type, enabled in metadata_sources.items():
            if not enabled:
                continue
            
            client = self.get_client(client_type)
            if not client:
                continue
            
            try:
                logger.debug(f"Rufe API-Client {client_type} ab")
                metadata = client.enhance_metadata(basic_metadata)
                
                if metadata:
                    # Bewerte die Qualität der Metadaten
                    score = client._score_metadata(metadata, title, authors)
                    api_results.append((client_type, score, metadata))
                    logger.info(f"Metadaten von {client_type} mit Score {score:.2f} gefunden")
            except Exception as e:
                logger.warning(f"Fehler bei {client_type}-Abfrage: {str(e)}")
        
        # Keine Ergebnisse?
        if not api_results:
            logger.info("Keine erweiterten Metadaten gefunden")
            return basic_metadata
        
        # Sortiere Ergebnisse nach Score und wähle das beste
        api_results.sort(key=lambda x: x[1], reverse=True)
        best_source, best_score, best_metadata = api_results[0]
        logger.info(f"Beste Metadaten von {best_source} mit Score {best_score:.2f}")
        
        # Bei hohem Score das gesamte Ergebnis übernehmen
        if best_score > 70:
            logger.debug(f"Übernehme alle Metadaten von {best_source} aufgrund des hohen Scores")
            enhanced_metadata = basic_metadata.copy()
            for key, value in best_metadata.items():
                if value:  # Leere Werte nicht übernehmen
                    enhanced_metadata[key] = value
            return enhanced_metadata
        
        # Bei niedrigem Score aus allen Quellen die besten Informationen kombinieren
        logger.debug("Kombiniere Metadaten aus mehreren Quellen")
        enhanced_metadata = basic_metadata.copy()
        
        # Wichtige Metadatenfelder mit Prioritätsreihenfolge
        fields_with_priority = {
            'title': [],
            'author': [],
            'year': [],
            'publisher': [],
            'journal': [],
            'doi': [],
            'isbn': [],
            'page_count': [],
            'language': [],
            'keywords': [],
            'abstract': []
        }
        
        # Sammle alle Werte für jedes Feld mit ihren Scores
        for source, score, metadata in api_results:
            for field in fields_with_priority:
                if field in metadata and metadata[field]:
                    fields_with_priority[field].append((metadata[field], score, source))
        
        # Wähle den besten Wert für jedes Feld
        for field, values in fields_with_priority.items():
            if not values:
                continue
                
            # Sortiere nach Score
            values.sort(key=lambda x: x[1], reverse=True)
            best_value, best_value_score, best_value_source = values[0]
            
            # Nur übernehmen, wenn gut genug oder besser als vorhandener Wert
            if best_value_score > 30 or field not in enhanced_metadata or not enhanced_metadata[field]:
                enhanced_metadata[field] = best_value
                logger.debug(f"Feld '{field}' von {best_value_source} übernommen")
        
        return enhanced_metadata


# Singleton-Instanz
_factory_instance = None

def get_metadata_api_factory() -> MetadataAPIClientFactory:
    """
    Gibt eine Singleton-Instanz der MetadataAPIClientFactory zurück.
    
    Returns:
        MetadataAPIClientFactory-Instanz
    """
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = MetadataAPIClientFactory()
    return _factory_instance