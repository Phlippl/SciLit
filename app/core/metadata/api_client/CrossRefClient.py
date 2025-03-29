"""
CrossRef API Client für SciLit
----------------------------
Client für die CrossRef API zur Abfrage von DOIs und akademischen Publikationsmetadaten.
"""

import re
import json
import logging
import urllib.parse
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher

from app.api.base_client import BaseAPIClient
from app.core.metadata.extractor import string_similarity
from app.config import CROSSREF_API_URL

# Logger konfigurieren
logger = logging.getLogger("scilit.api.crossref")

class CrossRefClient(BaseAPIClient):
    """
    Client für die CrossRef API.
    
    CrossRef ist eine zentrale Quelle für DOIs und Metadaten akademischer Publikationen.
    Dieser Client ermöglicht die Suche nach Publikationen basierend auf DOI, Titel oder Autor.
    
    Attributes:
        api_url (str): Basis-URL für die CrossRef API
    """
    
    def __init__(self):
        """Initialisiert den CrossRef API Client."""
        super().__init__(name="crossref")
        self.api_url = CROSSREF_API_URL
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten mit Daten aus CrossRef.
        
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
        
        # DOI extrahieren, falls vorhanden
        doi = None
        for key, value in basic_metadata.items():
            if key.lower() in ['doi', 'identifier'] and isinstance(value, str):
                doi_match = re.search(r'10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+', value)
                if doi_match:
                    doi = doi_match.group(0)
                    break
        
        logger.info(f"Erweitere Metadaten mit CrossRef: Titel='{title}', Autoren={authors}, DOI={doi}")
        
        # Metadaten aus CrossRef abrufen
        crossref_metadata = self.fetch_metadata(title, authors, doi)
        if not crossref_metadata:
            logger.debug("Keine Metadaten von CrossRef gefunden")
            return basic_metadata
        
        # Bewertung der gefundenen Metadaten
        score = self._score_metadata(crossref_metadata, title, authors)
        logger.info(f"CrossRef-Metadaten gefunden mit Score {score:.2f}")
        
        # Bei hohem Score die Metadaten vollständig übernehmen
        if score > 70:
            logger.debug("Hoher Score: Übernehme alle CrossRef-Metadaten")
            enhanced_metadata = basic_metadata.copy()
            for key, value in crossref_metadata.items():
                if value:  # Leere Werte nicht übernehmen
                    enhanced_metadata[key] = value
            return enhanced_metadata
        
        # Bei niedrigem Score nur ausgewählte Felder übernehmen
        logger.debug("Niedriger Score: Übernehme nur ausgewählte CrossRef-Metadaten")
        for key in ['journal', 'publisher', 'doi', 'issn', 'year']:
            if key in crossref_metadata and crossref_metadata[key]:
                basic_metadata[key] = crossref_metadata[key]
        
        return basic_metadata
    
    def fetch_metadata(self, title: str = None, authors: List[str] = None, doi: str = None) -> Dict[str, Any]:
        """
        Ruft Metadaten von CrossRef ab, entweder über DOI oder Titel/Autoren.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            doi: DOI der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler/nicht gefunden
        """
        # Bei vorhandenem DOI direkt danach suchen
        if doi:
            return self._fetch_by_doi(doi)
        
        # Ansonsten nach Titel und/oder Autoren suchen
        if title or authors:
            return self._fetch_by_query(title, authors)
        
        return {}
    
    def _fetch_by_doi(self, doi: str) -> Dict[str, Any]:
        """
        Sucht direkt nach einer DOI in CrossRef.
        
        Args:
            doi: Die DOI der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler
        """
        cache_key = self._create_cache_key("doi", doi)
        
        def fetch_func():
            url = f"{self.api_url}/{doi}"
            try:
                response = self._make_request("get", url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'message' in data:
                        return self._parse_crossref_message(data['message'])
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei CrossRef-DOI-Anfrage: {str(e)}")
            
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
                if clean_title:
                    query_parts.append(f'title:"{urllib.parse.quote(clean_title)}"')
            
            if authors and len(authors) > 0:
                # Verwende den ersten Autor für die Suche
                first_author = authors[0]
                # Extrahiere den Nachnamen (letzter Teil)
                name_parts = first_author.split()
                if len(name_parts) > 1:
                    last_name = name_parts[-1]
                    query_parts.append(f'author:"{urllib.parse.quote(last_name)}"')
                else:
                    query_parts.append(f'author:"{urllib.parse.quote(first_author)}"')
            
            if not query_parts:
                return {}
            
            query = " ".join(query_parts)
            url = f"{self.api_url}?query={query}&rows=5"
            
            try:
                response = self._make_request("get", url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'message' in data and 'items' in data['message'] and data['message']['items']:
                        # Mehrere Ergebnisse durchgehen und das beste auswählen
                        best_item = None
                        best_score = -1
                        
                        for item in data['message']['items'][:5]:  # Nur die ersten 5 prüfen
                            score = self._score_crossref_item(item, title, authors or [])
                            if score > best_score:
                                best_score = score
                                best_item = item
                        
                        # Wenn ein gutes Ergebnis gefunden wurde
                        if best_item and best_score > 10:
                            logger.debug(f"CrossRef-Ergebnis mit Score {best_score} gefunden")
                            return self._parse_crossref_message(best_item)
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei CrossRef-Suche: {str(e)}")
            
            return {}
        
        return self._get_cached_or_fetch(cache_key, fetch_func)
    
    def _parse_crossref_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahiert relevante Metadaten aus einer CrossRef-Antwort.
        
        Args:
            message: CrossRef-Antwortobjekt
            
        Returns:
            Extrahierte Metadaten
        """
        metadata = {}
        
        # Titel
        if 'title' in message and message['title']:
            metadata['title'] = message['title'][0]
        
        # Autoren
        if 'author' in message:
            authors = []
            for author in message['author']:
                name_parts = []
                if 'given' in author:
                    name_parts.append(author['given'])
                if 'family' in author:
                    name_parts.append(author['family'])
                if name_parts:
                    authors.append(' '.join(name_parts))
            if authors:
                metadata['author'] = authors
        
        # Journal/Quelle
        if 'container-title' in message and message['container-title']:
            metadata['journal'] = message['container-title'][0]
        
        # Jahr
        if 'published' in message and 'date-parts' in message['published']:
            date_parts = message['published']['date-parts'][0]
            if date_parts and len(date_parts) > 0:
                metadata['year'] = date_parts[0]
        
        # Verleger
        if 'publisher' in message:
            metadata['publisher'] = message['publisher']
        
        # DOI
        if 'DOI' in message:
            metadata['doi'] = message['DOI']
        
        # ISSN
        if 'ISSN' in message and message['ISSN']:
            metadata['issn'] = message['ISSN'][0]
        
        # Typ
        if 'type' in message:
            metadata['type'] = message['type']
        
        # Abstract
        if 'abstract' in message:
            metadata['abstract'] = message['abstract']
        
        return metadata
    
    def _score_crossref_item(self, item: Dict[str, Any], title: str, authors: List[str]) -> float:
        """
        Bewertet ein CrossRef-Ergebnis basierend auf Titel und Autoren.
        
        Args:
            item: CrossRef-Ergebnisobjekt
            title: Zu vergleichender Titel
            authors: Zu vergleichende Autoren
            
        Returns:
            Score von 0 bis 100
        """
        score = 0
        
        # Titelvergleich
        if 'title' in item and item['title'] and title:
            title_similarity = SequenceMatcher(None, title.lower(), item['title'][0].lower()).ratio()
            score += title_similarity * 50
        
        # Autorenvergleich
        if 'author' in item and authors:
            author_found = False
            for author in item['author']:
                if 'family' in author:
                    for orig_author in authors:
                        name_parts = orig_author.split()
                        if name_parts and author['family'].lower() in orig_author.lower():
                            author_found = True
                            break
            if author_found:
                score += 30
        
        # Bonus für vollständige Metadaten
        if 'published' in item and 'date-parts' in item['published']:
            score += 5
        if 'container-title' in item and item['container-title']:
            score += 5
        if 'publisher' in item:
            score += 5
        if 'DOI' in item:
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
        if 'journal' in metadata and metadata['journal']:
            bonus_score += 4
        if 'publisher' in metadata and metadata['publisher']:
            bonus_score += 3
        if 'doi' in metadata and metadata['doi']:
            bonus_score += 5
        if 'issn' in metadata and metadata['issn']:
            bonus_score += 4
        
        score += bonus_score
        logger.debug(f"Bonus-Score für zusätzliche Metadaten: {bonus_score}")
        
        return score