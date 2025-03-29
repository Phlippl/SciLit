"""
Google Books API Client für SciLit
--------------------------------
Client für die Google Books API zur Abfrage von Buchmetadaten.
"""

import re
import json
import logging
import urllib.parse
import requests

from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher

from app.api.BaseAPIClient import BaseAPIClient
from app.core.metadata.extractor import string_similarity
from app.config import GOOGLEBOOKS_API_URL, GOOGLEBOOKS_API_KEY

# Logger konfigurieren
logger = logging.getLogger("scilit.api.googlebooks")

class GoogleBooksClient(BaseAPIClient):
    """
    Client für die Google Books API.
    
    Google Books bietet umfangreiche Informationen zu Büchern und Publikationen
    und ermöglicht die Suche nach ISBN, Titel oder Autor.
    
    Attributes:
        api_url (str): Basis-URL für die Google Books API
        api_key (str): API-Schlüssel für die Google Books API
    """
    
    def __init__(self):
        """Initialisiert den Google Books API Client."""
        super().__init__(name="googlebooks")
        self.api_url = GOOGLEBOOKS_API_URL
        self.api_key = GOOGLEBOOKS_API_KEY
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten mit Daten aus Google Books.
        
        Args:
            basic_metadata: Grundlegende Metadaten aus dem Dokument
            
        Returns:
            Erweiterte Metadaten
        """
        # Extraktion der nötigen Informationen aus den Basis-Metadaten
        title = basic_metadata.get('title', '')
        authors = basic_metadata.get('author', [])
        if isinstance(authors, str):
            authors = [authors]
        
        # ISBN extrahieren, falls vorhanden
        isbn = None
        for key, value in basic_metadata.items():
            if key.lower() == 'isbn' and isinstance(value, str):
                isbn = re.sub(r'[^0-9X]', '', value)
                break
        
        logger.info(f"Erweitere Metadaten mit Google Books: Titel='{title}', Autoren={authors}, ISBN={isbn}")
        
        # Metadaten aus Google Books abrufen
        googlebooks_metadata = self.fetch_metadata(title, authors, isbn)
        if not googlebooks_metadata:
            logger.debug("Keine Metadaten von Google Books gefunden")
            return basic_metadata
        
        # Bewertung der gefundenen Metadaten
        score = self._score_metadata(googlebooks_metadata, title, authors)
        logger.info(f"Google Books-Metadaten gefunden mit Score {score:.2f}")
        
        # Bei hohem Score die Metadaten vollständig übernehmen
        if score > 70:
            logger.debug("Hoher Score: Übernehme alle Google Books-Metadaten")
            enhanced_metadata = basic_metadata.copy()
            for key, value in googlebooks_metadata.items():
                if value:  # Leere Werte nicht übernehmen
                    enhanced_metadata[key] = value
            return enhanced_metadata
        
        # Bei niedrigem Score nur ausgewählte Felder übernehmen
        logger.debug("Niedriger Score: Übernehme nur ausgewählte Google Books-Metadaten")
        for key in ['publisher', 'isbn', 'year', 'page_count', 'keywords']:
            if key in googlebooks_metadata and googlebooks_metadata[key]:
                basic_metadata[key] = googlebooks_metadata[key]
        
        return basic_metadata
    
    def fetch_metadata(self, title: str = None, authors: List[str] = None, isbn: str = None) -> Dict[str, Any]:
        """
        Ruft Metadaten von Google Books ab, entweder über ISBN oder Titel/Autoren.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            isbn: ISBN der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler/nicht gefunden
        """
        # Bei vorhandenem ISBN direkt danach suchen
        if isbn:
            return self._fetch_by_isbn(isbn)
        
        # Ansonsten nach Titel und/oder Autoren suchen
        if title or authors:
            return self._fetch_by_query(title, authors)
        
        return {}
    
    def _fetch_by_isbn(self, isbn: str) -> Dict[str, Any]:
        """
        Sucht direkt nach einer ISBN in Google Books.
        
        Args:
            isbn: Die ISBN der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler
        """
        cache_key = self._create_cache_key("isbn", isbn)
        
        def fetch_func():
            query = f"isbn:{isbn}"
            url = f"{self.api_url}?q={query}&maxResults=1"
            
            # API-Key hinzufügen, falls vorhanden
            if self.api_key:
                url += f"&key={self.api_key}"
            
            try:
                response = self._make_request("get", url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'items' in data and data['items']:
                        return self._parse_googlebooks_item(data['items'][0])
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei Google Books ISBN-Anfrage: {str(e)}")
            
            return {}
        
        return self._get_cached_or_fetch(cache_key, fetch_func)
    
    def _fetch_by_query(self, title: str = None, authors: List[str] = None) -> Dict[str, Any]:
        """
        Sucht nach Publikationen basierend auf Titel und/oder Autoren.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler
        """
        # Keine ausreichenden Suchkriterien
        if not title and not authors:
            return {}
        
        cache_key = self._create_cache_key("query", title, "_".join(authors or []))
        
        def fetch_func():
            query_parts = []
            
            if title:
                # Bereinigter Titel für die Suche
                clean_title = re.sub(r'[^\w\s]', ' ', title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                query_parts.append(f"intitle:{urllib.parse.quote(clean_title)}")
            
            if authors and len(authors) > 0:
                # Verwende den ersten Autor für die Suche
                first_author = authors[0]
                query_parts.append(f"inauthor:{urllib.parse.quote(first_author)}")
            
            query = "+".join(query_parts)
            url = f"{self.api_url}?q={query}&maxResults=5"
            
            # API-Key hinzufügen, falls vorhanden
            if self.api_key:
                url += f"&key={self.api_key}"
            
            try:
                response = self._make_request("get", url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'items' in data and data['items']:
                        # Bewerte die Ergebnisse und wähle das beste
                        best_item = None
                        best_score = -1
                        
                        for item in data['items'][:5]:
                            score = self._score_googlebooks_item(item, title, authors or [])
                            if score > best_score:
                                best_score = score
                                best_item = item
                        
                        # Wenn ein gutes Ergebnis gefunden wurde
                        if best_item and best_score > 10:
                            logger.debug(f"Google Books-Ergebnis mit Score {best_score} gefunden")
                            return self._parse_googlebooks_item(best_item)
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei Google Books-Suche: {str(e)}")
            
            return {}
        
        return self._get_cached_or_fetch(cache_key, fetch_func)
    
    def _parse_googlebooks_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahiert relevante Metadaten aus einem Google Books-Item.
        
        Args:
            item: Google Books-Item
            
        Returns:
            Extrahierte Metadaten
        """
        metadata = {}
        
        # Volumeinfo extrahieren
        if 'volumeInfo' not in item:
            return metadata
        
        vol_info = item['volumeInfo']
        
        # Titel
        if 'title' in vol_info:
            metadata['title'] = vol_info['title']
            # Untertitel, falls vorhanden
            if 'subtitle' in vol_info:
                metadata['title'] += ": " + vol_info['subtitle']
        
        # Autoren
        if 'authors' in vol_info:
            metadata['author'] = vol_info['authors']
        
        # Erscheinungsjahr
        if 'publishedDate' in vol_info:
            # Format kann YYYY, YYYY-MM oder YYYY-MM-DD sein
            date_str = vol_info['publishedDate']
            year_match = re.match(r'(\d{4})', date_str)
            if year_match:
                metadata['year'] = int(year_match.group(1))
        
        # Verlag
        if 'publisher' in vol_info:
            metadata['publisher'] = vol_info['publisher']
        
        # ISBN
        if 'industryIdentifiers' in vol_info:
            for identifier in vol_info['industryIdentifiers']:
                if identifier['type'] == 'ISBN_13':
                    metadata['isbn'] = identifier['identifier']
                    break
                elif identifier['type'] == 'ISBN_10' and 'isbn' not in metadata:
                    metadata['isbn'] = identifier['identifier']
        
        # Seitenzahl
        if 'pageCount' in vol_info:
            metadata['page_count'] = vol_info['pageCount']
        
        # Sprache
        if 'language' in vol_info:
            language = vol_info['language']
            if language == 'en':
                metadata['language'] = 'en'
            elif language == 'de':
                metadata['language'] = 'de'
            else:
                metadata['language'] = language
        
        # Kategorien / Schlagwörter
        if 'categories' in vol_info:
            metadata['keywords'] = vol_info['categories']
        
        # Beschreibung / Abstract
        if 'description' in vol_info:
            metadata['abstract'] = vol_info['description']
        
        return metadata
    
    def _score_googlebooks_item(self, item: Dict[str, Any], title: str, authors: List[str]) -> float:
        """
        Bewertet ein Google Books-Ergebnis basierend auf Titel und Autoren.
        
        Args:
            item: Google Books-Item
            title: Zu vergleichender Titel
            authors: Zu vergleichende Autoren
            
        Returns:
            Score von 0 bis 100
        """
        score = 0
        
        if 'volumeInfo' not in item:
            return score
        
        vol_info = item['volumeInfo']
        
        # Titelvergleich
        if 'title' in vol_info and title:
            item_title = vol_info['title']
            if 'subtitle' in vol_info:
                item_title += ": " + vol_info['subtitle']
            
            title_similarity = SequenceMatcher(None, title.lower(), item_title.lower()).ratio()
            score += title_similarity * 50
        
        # Autorenvergleich
        if 'authors' in vol_info and authors:
            author_found = False
            for author in vol_info['authors']:
                for orig_author in authors:
                    if orig_author.lower() in author.lower() or author.lower() in orig_author.lower():
                        author_found = True
                        break
            if author_found:
                score += 30
        
        # Bonus für vollständige Metadaten
        if 'publishedDate' in vol_info:
            score += 5
        if 'publisher' in vol_info:
            score += 5
        if 'industryIdentifiers' in vol_info:
            score += 5
        if 'categories' in vol_info:
            score += 5
        
        return score
    
    def _score_metadata(self, metadata: Dict[str, Any], original_title: str, original_authors: List[str]) -> float:
        """
        Bewertet die Qualität der gefundenen Metadaten im Vergleich zu den ursprünglichen Daten.
        
        Args:
            metadata: Gefundene Metadaten
            original_title: Originaltitel
            original_authors: Originalautoren
            
        Returns:
            Score von 0 bis 100
        """
        score = 0.0
        
        # Titelvergleich (bis zu 50 Punkte)
        if 'title' in metadata and original_title:
            title_similarity = string_similarity(metadata['title'], original_title)
            title_points = title_similarity * 50
            score += title_points
            logger.debug(f"Titelscore: {title_points:.2f} (Ähnlichkeit: {title_similarity:.2f})")
        
        # Autorenvergleich (bis zu 30 Punkte)
        if 'author' in metadata and original_authors:
            found_authors = metadata['author']
            if isinstance(found_authors, str):
                found_authors = [found_authors]
            
            # Für jeden gefundenen Autor prüfen, ob er mit einem Original-Autor übereinstimmt
            author_similarity = 0
            for found_author in found_authors:
                if not found_author:
                    continue
                best_match = max([string_similarity(found_author, orig_author) for orig_author in original_authors],
                                default=0)
                author_similarity += best_match
            
            if found_authors:
                author_similarity /= len(found_authors)
                author_points = author_similarity * 30
                score += author_points
                logger.debug(f"Autorenscore: {author_points:.2f} (Ähnlichkeit: {author_similarity:.2f})")
        
        # Zusätzliche Metadaten geben Extrapunkte (bis zu 20 Punkte)
        bonus_score = 0
        if 'year' in metadata and metadata['year']:
            bonus_score += 4
        if 'publisher' in metadata and metadata['publisher']:
            bonus_score += 3
        if 'isbn' in metadata and metadata['isbn']:
            bonus_score += 5
        if 'page_count' in metadata and metadata['page_count']:
            bonus_score += 3
        if 'keywords' in metadata and metadata['keywords']:
            bonus_score += 5
        
        score += bonus_score
        logger.debug(f"Bonus-Score für zusätzliche Metadaten: {bonus_score}")
        
        return score