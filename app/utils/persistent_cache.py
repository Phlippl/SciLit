"""
Persistenter Cache für SciLit
---------------------------
Bietet einen einfachen, persistenten Cache für API-Antworten und andere Daten.
"""

import os
import json
import time
import logging
import pickle
from typing import Any, Optional, Dict
from pathlib import Path

from app.config import CACHE_DIR, CACHE_TTL

# Logger konfigurieren
logger = logging.getLogger("scilit.utils.cache")

class PersistentCache:
    """
    Ein einfacher, persistenter Datei-basierter Cache.
    
    Diese Klasse speichert Daten in Dateien unter einem angegebenen Verzeichnis
    und bietet automatisches Ablaufen der Cache-Einträge.
    
    Attributes:
        cache_dir (Path): Verzeichnis für Cache-Dateien
        default_ttl (int): Standardzeit bis zum Ablaufen der Cache-Einträge in Sekunden
    """
    
    def __init__(self, cache_dir: str = None, default_ttl: int = CACHE_TTL):
        """
        Initialisiert den persistenten Cache.
        
        Args:
            cache_dir: Verzeichnis für Cache-Dateien (standardmäßig aus config)
            default_ttl: Standardzeit bis zum Ablaufen der Cache-Einträge in Sekunden
        """
        self.cache_dir = Path(cache_dir or CACHE_DIR)
        self.default_ttl = default_ttl
        
        # Verzeichnis erstellen, falls es nicht existiert
        os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.debug(f"Persistenter Cache initialisiert. Verzeichnis: {self.cache_dir}")
    
    def _get_cache_path(self, key: str) -> Path:
        """
        Erzeugt den Dateipfad für einen Cache-Schlüssel.
        
        Args:
            key: Der Cache-Schlüssel
            
        Returns:
            Dateipfad für den Cache-Eintrag
        """
        # Bereinige den Schlüssel für die Verwendung als Dateiname
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        
        # Falls der Schlüssel zu lang ist, verwende einen Hash
        if len(safe_key) > 100:
            import hashlib
            hashed_key = hashlib.md5(key.encode()).hexdigest()
            safe_key = f"{safe_key[:50]}_{hashed_key}"
        
        return self.cache_dir / f"{safe_key}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Lädt einen Wert aus dem Cache.
        
        Args:
            key: Der Cache-Schlüssel
            
        Returns:
            Der gecachte Wert oder None, wenn der Schlüssel nicht existiert oder abgelaufen ist
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            logger.debug(f"Cache-Miss: {key} (Datei existiert nicht)")
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
            
            # Prüfe, ob der Cache-Eintrag abgelaufen ist
            if 'expiry' in cached_data and cached_data['expiry'] < time.time():
                logger.debug(f"Cache-Miss: {key} (abgelaufen)")
                # Optional: Abgelaufene Dateien aufräumen
                os.remove(cache_path)
                return None
            
            logger.debug(f"Cache-Hit: {key}")
            return cached_data['value']
        except (IOError, pickle.PickleError, KeyError) as e:
            logger.warning(f"Fehler beim Laden des Cache-Eintrags {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Speichert einen Wert im Cache.
        
        Args:
            key: Der Cache-Schlüssel
            value: Der zu cachende Wert
            ttl: Zeit bis zum Ablaufen in Sekunden (None für den Standard-TTL)
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        if ttl is None:
            ttl = self.default_ttl
        
        cache_path = self._get_cache_path(key)
        
        try:
            # Speichere den Wert mit Ablaufzeit
            cache_data = {
                'value': value,
                'expiry': time.time() + ttl,
                'created': time.time()
            }
            
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.debug(f"Cache-Eintrag gespeichert: {key}")
            return True
        except (IOError, pickle.PickleError) as e:
            logger.warning(f"Fehler beim Speichern des Cache-Eintrags {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Löscht einen Eintrag aus dem Cache.
        
        Args:
            key: Der Cache-Schlüssel
            
        Returns:
            True wenn der Eintrag gelöscht wurde, False bei Fehler oder nicht existierendem Schlüssel
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            logger.debug(f"Cache-Eintrag zum Löschen nicht gefunden: {key}")
            return False
        
        try:
            os.remove(cache_path)
            logger.debug(f"Cache-Eintrag gelöscht: {key}")
            return True
        except IOError as e:
            logger.warning(f"Fehler beim Löschen des Cache-Eintrags {key}: {str(e)}")
            return False
    
    def clear(self, prefix: Optional[str] = None) -> int:
        """
        Löscht alle oder bestimmte Einträge aus dem Cache.
        
        Args:
            prefix: Optionaler Präfix für zu löschende Schlüssel
            
        Returns:
            Anzahl der gelöschten Einträge
        """
        count = 0
        
        for cache_file in self.cache_dir.glob("*.cache"):
            # Wenn ein Präfix angegeben ist, prüfen ob der Dateiname damit beginnt
            if prefix and not cache_file.stem.startswith(prefix):
                continue
            
            try:
                os.remove(cache_file)
                count += 1
            except IOError as e:
                logger.warning(f"Fehler beim Löschen von {cache_file}: {str(e)}")
        
        logger.info(f"{count} Cache-Einträge gelöscht" + (f" mit Präfix '{prefix}'" if prefix else ""))
        return count

# Singleton-Instanz
_cache_instance = None

def get_cache() -> PersistentCache:
    """
    Gibt eine Singleton-Instanz des PersistentCache zurück.
    
    Returns:
        PersistentCache-Instanz
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = PersistentCache()
    return _cache_instance