"""
Open Library API Client für SciLit
--------------------------------
Client für die Open Library API zur Abfrage von Buchmetadaten.
"""

import re
import json
import logging
import urllib.parse
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher

from app.api.base_client import BaseAPIClient
from app.core.metadata.extractor import string_similarity
from app.config import OPENLIB_API_URL

# Logger konfigurieren
logger = logging.getLogger("scilit.api.openlib")

class OpenLibraryClient(BaseAPIClient):
    """
    Client für die Open Library API.
    
    Open Library bietet einen öffentlichen Zugang zu Buchmetadaten, einschließlich
    Titel, Autoren, Verlagen, ISBNs usw.
    
    Attributes:
        api_url (str): Basis-URL für die Open Library API
    """
    
    def __init__(self):
        """Initialisiert den Open Library API Client."""
        super().__init__(name="openlib")
        self.api_url = OPENLIB_API_URL
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten mit Daten aus Open Library.
        
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
        
        logger.info(f"Erweitere Metadaten mit Open Library: Titel='{title}', Autoren={authors}, ISBN={isbn}")
        
        # Metadaten aus Open Library abrufen
        openlib_metadata = self.fetch_metadata(title, authors, isbn)
        if not openlib_metadata:
            logger.debug("Keine Metadaten von Open Library gefunden")
            return basic_metadata
        
        # Bewertung der gefundenen Metadaten
        score = self._score_metadata(openlib_metadata, title, authors)
        logger.info(f"Open Library-Metadaten gefunden mit Score {score:.2f}")
        
        # Bei hohem Score die Metadaten vollständig übernehmen
        if score > 70:
            logger.debug("Hoher Score: Übernehme alle Open Library-Metadaten")
            enhanced_metadata = basic_metadata.copy()
            for key, value in openlib_metadata.items():
                if value:  # Leere Werte nicht übernehmen
                    enhanced_metadata[key] = value
            return enhanced_metadata
        
        # Bei niedrigem Score nur ausgewählte Felder übernehmen
        logger.debug("Niedriger Score: Übernehme nur ausgewählte Open Library-Metadaten")
        for key in ['publisher', 'isbn', 'year', 'page_count', 'keywords', 'language']:
            if key in openlib_metadata and openlib_metadata[key]:
                basic_metadata[key] = openlib_metadata[key]
        
        return basic_metadata
    
    def fetch_metadata(self, title: str = None, authors: List[str] = None, isbn: str = None) -> Dict[str, Any]:
        """
        Ruft Metadaten von Open Library ab, entweder über ISBN oder Titel/Autoren.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            isbn: ISBN der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler/nicht gefunden
        """
        # Bei vorhandenem ISBN direkt danach suchen
        if isbn:
            isbn_metadata = self._fetch_by_isbn(isbn)
            if isbn_metadata:
                return isbn_metadata
            # Ansonsten nach Titel und/oder Autoren suchen
        if title or authors:
            return self._fetch_by_query(title, authors)
        
        return {}
    
    def _fetch_by_isbn(self, isbn: str) -> Dict[str, Any]:
        """
        Sucht direkt nach einer ISBN in Open Library.
        
        Args:
            isbn: Die ISBN der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler
        """
        cache_key = self._create_cache_key("isbn", isbn)
        
        def fetch_func():
            url = f"{self.api_url}?isbn={isbn}"
            try:
                response = self._make_request("get", url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'docs' in data and data['docs']:
                        return self._parse_openlib_response(data['docs'][0])
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei Open Library ISBN-Anfrage: {str(e)}")
            
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
                query_parts.append(f"title:{urllib.parse.quote(clean_title)}")
            
            if authors and len(authors) > 0:
                # Verwende den ersten Autor für die Suche
                first_author = authors[0]
                name_parts = first_author.split()
                if len(name_parts) > 1:
                    last_name = name_parts[-1]
                    query_parts.append(f"author:{urllib.parse.quote(last_name)}")
                else:
                    query_parts.append(f"author:{urllib.parse.quote(first_author)}")
            
            query = "+".join(query_parts)
            url = f"{self.api_url}?q={query}&limit=5"
            
            try:
                response = self._make_request("get", url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'docs' in data and data['docs']:
                        # Bewerte die Ergebnisse und wähle das beste
                        best_doc = None
                        best_score = -1
                        
                        for doc in data['docs'][:5]:
                            score = self._score_openlib_doc(doc, title, authors or [])
                            if score > best_score:
                                best_score = score
                                best_doc = doc
                        
                        # Wenn ein gutes Ergebnis gefunden wurde
                        if best_doc and best_score > 10:
                            logger.debug(f"Open Library-Ergebnis mit Score {best_score} gefunden")
                            return self._parse_openlib_response(best_doc)
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei Open Library Suche: {str(e)}")
            
            return {}
        
        return self._get_cached_or_fetch(cache_key, fetch_func)
    
    def _parse_openlib_response(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahiert relevante Metadaten aus einer Open Library-Antwort.
        
        Args:
            doc: Open Library-Dokumentobjekt
            
        Returns:
            Extrahierte Metadaten
        """
        metadata = {}
        
        # Titel
        if 'title' in doc:
            metadata['title'] = doc['title']
        
        # Autoren
        if 'author_name' in doc:
            metadata['author'] = doc['author_name']
        
        # Erscheinungsjahr
        if 'first_publish_year' in doc:
            metadata['year'] = doc['first_publish_year']
        elif 'publish_year' in doc and doc['publish_year']:
            metadata['year'] = min(doc['publish_year'])  # Nehme das früheste Jahr
        
        # Verlag
        if 'publisher' in doc and doc['publisher']:
            metadata['publisher'] = doc['publisher'][0]  # Nehme den ersten Verlag
        
        # ISBN
        if 'isbn' in doc and doc['isbn']:
            metadata['isbn'] = doc['isbn'][0]  # Nehme die erste ISBN
        
        # Sprache
        if 'language' in doc and doc['language']:
            languages = []
            for lang in doc['language']:
                if lang == 'eng':
                    languages.append('en')
                elif lang == 'ger' or lang == 'deu':
                    languages.append('de')
                else:
                    languages.append(lang)
            if languages:
                metadata['language'] = '/'.join(languages)
        
        # Seitenzahl
        if 'number_of_pages_median' in doc:
            metadata['page_count'] = doc['number_of_pages_median']
        
        # Themen/Schlagwörter
        keywords = []
        if 'subject' in doc and doc['subject']:
            for subject in doc['subject'][:5]:  # Begrenze auf 5 Schlagwörter
                keywords.append(subject)
        metadata['keywords'] = keywords
        
        return metadata
    
    def _score_openlib_doc(self, doc: Dict[str, Any], title: str, authors: List[str]) -> float:
        """
        Bewertet ein Open Library-Ergebnis basierend auf Titel und Autoren.
        
        Args:
            doc: Open Library-Dokumentobjekt
            title: Zu vergleichender Titel
            authors: Zu vergleichende Autoren
            
        Returns:
            Score von 0 bis 100
        """
        score = 0
        
        # Titelvergleich
        if 'title' in doc and title:
            title_similarity = SequenceMatcher(None, title.lower(), doc['title'].lower()).ratio()
            score += title_similarity * 50
        
        # Autorenvergleich
        if 'author_name' in doc and authors:
            author_found = False
            for author in doc['author_name']:
                for orig_author in authors:
                    if orig_author.lower() in author.lower() or author.lower() in orig_author.lower():
                        author_found = True
                        break
            if author_found:
                score += 30
        
        # Bonus für vollständige Metadaten
        if 'first_publish_year' in doc or ('publish_year' in doc and doc['publish_year']):
            score += 5
        if 'publisher' in doc and doc['publisher']:
            score += 5
        if 'isbn' in doc and doc['isbn']:
            score += 5
        if 'subject' in doc and doc['subject']:
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