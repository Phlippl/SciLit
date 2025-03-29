"""
Basis-API-Client für SciLit
--------------------------
Diese Klasse dient als Grundlage für alle spezifischen API-Clients.
"""

import json
import logging
import time
import hashlib
from typing import Dict, Any, Optional
from pathlib import Path
import requests

from app.utils.persistent_cache import get_cache
from app.config import CACHE_TTL

# Logger konfigurieren
logger = logging.getLogger("scilit.api.base")

class BaseAPIClient:
    """
    Basisklasse für API-Clients mit gemeinsamer Funktionalität.
    
    Diese Klasse stellt gemeinsame Funktionen wie Caching, HTTP-Anfragen
    und Fehlerbehandlung bereit, die von allen spezifischen API-Clients
    verwendet werden können.
    
    Attributes:
        name (str): Name des API-Clients für Logs und Cache-Keys
        session (requests.Session): HTTP-Session für Anfragen
    """
    
    def __init__(self, name: str, user_agent: str = None):
        """
        Initialisiert den Basis-API-Client.
        
        Args:
            name: Name des API-Clients für Logs und Cache-Keys
            user_agent: Benutzerdefinierter User-Agent für HTTP-Anfragen
        """
        self.name = name
        self.cache = get_cache()
        
        # HTTP-Session mit Verbindungs-Pooling
        self.session = requests.Session()
        
        # User-Agent setzen
        if user_agent:
            self.user_agent = user_agent
        else:
            self.user_agent = f"SciLit/{self.name}/1.0 (https://github.com/yourusername/scilit; mailto:your.email@example.com)"
        
        self.session.headers.update({
            'User-Agent': self.user_agent
        })
        
        logger.debug(f"{self.name} API-Client initialisiert")
    
    def _create_cache_key(self, prefix: str, *args) -> str:
        """
        Erstellt einen Cache-Schlüssel aus den übergebenen Argumenten.
        
        Args:
            prefix: Präfix für den Cache-Schlüssel
            *args: Beliebige Argumente, die in den Schlüssel einfließen
            
        Returns:
            Cache-Schlüssel
        """
        # Stringrepräsentation der Argumente erstellen
        arg_str = "_".join(str(arg) for arg in args if arg)
        
        # Vollständigen Schlüssel erstellen
        full_key = f"{self.name}_{prefix}_{arg_str}"
        
        # Für lange Schlüssel einen Hash verwenden
        if len(full_key) > 100:
            return f"{self.name}_{prefix}_{hashlib.md5(arg_str.encode()).hexdigest()}"
        
        return full_key
    
    def _get_cached_or_fetch(self, cache_key: str, fetch_func, *args, **kwargs) -> Any:
        """
        Versucht, ein Ergebnis aus dem Cache zu laden oder ruft es frisch ab.
        
        Args:
            cache_key: Schlüssel für den Cache-Eintrag
            fetch_func: Funktion zum Abrufen der Daten, falls nicht im Cache
            *args, **kwargs: Argumente für fetch_func
            
        Returns:
            Daten aus dem Cache oder fresh abgerufen
        """
        # Versuche, aus dem Cache zu laden
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"{self.name}: Cache-Treffer für {cache_key}")
            return cached_result
        
        # Nicht im Cache, also frisch abrufen
        logger.debug(f"{self.name}: Cache-Fehltreffer für {cache_key}, rufe Daten ab")
        result = fetch_func(*args, **kwargs)
        
        # In Cache speichern, wenn das Ergebnis nicht leer ist
        if result:
            self.cache.set(cache_key, result)
        
        return result
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Führt eine HTTP-Anfrage mit Wiederholungslogik und Fehlerbehandlung durch.
        
        Args:
            method: HTTP-Methode ('get', 'post', etc.)
            url: Ziel-URL
            **kwargs: Weitere Argumente für requests
            
        Returns:
            Response-Objekt
            
        Raises:
            requests.RequestException: Bei Netzwerkfehlern
        """
        max_retries = kwargs.pop('max_retries', 3)
        timeout = kwargs.pop('timeout', 10)
        retry_delay = kwargs.pop('retry_delay', 1)
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"{self.name}: {method.upper()}-Anfrage an {url} (Versuch {attempt+1}/{max_retries})")
                response = self.session.request(method, url, timeout=timeout, **kwargs)
                
                # Bei Ratengrenzüberschreitung warten und erneut versuchen
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', retry_delay * 2))
                    logger.warning(f"{self.name}: Ratenlimit erreicht, warte {retry_after} Sekunden")
                    time.sleep(retry_after)
                    continue
                
                # Für andere Fehler sofort zurückgeben
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                logger.warning(f"{self.name}: Anfragefehler: {str(e)}")
                
                # Bei letztem Versuch, Fehler weitergeben
                if attempt == max_retries - 1:
                    raise
                
                # Ansonsten warten und erneut versuchen
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponentielles Backoff
        
        # Sollte nie erreicht werden, aber zur Sicherheit
        raise requests.RequestException(f"{self.name}: Maximale Anzahl von Wiederholungen erreicht")

    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die Metadaten aus einer spezifischen API-Quelle.
        Diese Methode muss von abgeleiteten Klassen implementiert werden.
        
        Args:
            basic_metadata: Grundlegende Metadaten
            
        Returns:
            Erweiterte Metadaten
        """
        raise NotImplementedError("Diese Methode muss von abgeleiteten Klassen implementiert werden")
    
    def _score_metadata(self, metadata: Dict[str, Any], title: str, authors: list) -> float:
        """
        Bewertet die Qualität der gefundenen Metadaten.
        Diese Methode sollte von abgeleiteten Klassen überschrieben werden.
        
        Args:
            metadata: Gefundene Metadaten
            title: Originaltitel zur Bewertung
            authors: Originalautoren zur Bewertung
            
        Returns:
            Bewertungspunktzahl (0-100)
        """
        # Standardimplementierung, die von abgeleiteten Klassen überschrieben werden kann
        return 0.0