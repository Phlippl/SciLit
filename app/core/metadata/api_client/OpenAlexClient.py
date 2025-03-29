"""
OpenAlex API Client für SciLit
----------------------------
Client für die OpenAlex API zur Abfrage wissenschaftlicher Publikationsmetadaten.
"""

import re
import json
import logging
import urllib.parse
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher

from app.api.base_client import BaseAPIClient
from app.core.metadata.extractor import string_similarity
from app.config import OPENALEX_API_URL

# Logger konfigurieren
logger = logging.getLogger("scilit.api.openalex")

class OpenAlexClient(BaseAPIClient):
    """
    Client für die OpenAlex API.
    
    OpenAlex ist ein offener akademischer Graph und Index für wissenschaftliche Publikationen
    und bietet umfassende Metadaten zu Artikeln, Autoren, Institutionen usw.
    
    Attributes:
        api_url (str): Basis-URL für die OpenAlex API
    """
    
    def __init__(self):
        """Initialisiert den OpenAlex API Client."""
        super().__init__(name="openalex")
        self.api_url = OPENALEX_API_URL
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten mit Daten aus OpenAlex.
        
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
        
        logger.info(f"Erweitere Metadaten mit OpenAlex: Titel='{title}', Autoren={authors}, DOI={doi}")
        
        # Metadaten aus OpenAlex abrufen
        openalex_metadata = self.fetch_metadata(title, authors, doi)
        if not openalex_metadata:
            logger.debug("Keine Metadaten von OpenAlex gefunden")
            return basic_metadata
        
        # Bewertung der gefundenen Metadaten
        score = self._score_metadata(openalex_metadata, title, authors)
        logger.info(f"OpenAlex-Metadaten gefunden mit Score {score:.2f}")
        
        # Bei hohem Score die Metadaten vollständig übernehmen
        if score > 70:
            logger.debug("Hoher Score: Übernehme alle OpenAlex-Metadaten")
            enhanced_metadata = basic_metadata.copy()
            for key, value in openalex_metadata.items():
                if value:  # Leere Werte nicht übernehmen
                    enhanced_metadata[key] = value
            return enhanced_metadata
        
        # Bei niedrigem Score nur ausgewählte Felder übernehmen
        logger.debug("Niedriger Score: Übernehme nur ausgewählte OpenAlex-Metadaten")
        for key in ['journal', 'publisher', 'doi', 'year', 'keywords']:
            if key in openalex_metadata and openalex_metadata[key]:
                basic_metadata[key] = openalex_metadata[key]
        
        return basic_metadata
    
    def fetch_metadata(self, title: str = None, authors: List[str] = None, doi: str = None) -> Dict[str, Any]:
        """
        Ruft Metadaten von OpenAlex ab, entweder über DOI oder Titel/Autoren.
        
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
        Sucht direkt nach einer DOI in OpenAlex.
        
        Args:
            doi: Die DOI der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler
        """
        cache_key = self._create_cache_key("doi", doi)
        
        def fetch_func():
            url = f"{self.api_url}?filter=doi:{urllib.parse.quote(doi)}"
            headers = {"Accept": "application/json"}
            
            try:
                response = self._make_request("get", url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'results' in data and data['results']:
                        return self._parse_openalex_work(data['results'][0])
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei OpenAlex-DOI-Anfrage: {str(e)}")
            
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
            # Bereinigter Titel für die Suche
            if title:
                clean_title = re.sub(r'[^\w\s]', ' ', title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                query = f"title.search:{urllib.parse.quote(clean_title)}"
            else:
                return {}  # Ohne Titel können wir keine gute Suche durchführen
            
            # Autorenfilter hinzufügen, wenn möglich
            filter_parts = [query]
            if authors and len(authors) > 0:
                #Extrahiere den Nachnamen des ersten Autors
                name_parts = authors[0].split()
                if len(name_parts) > 1:
                    last_name = name_parts[-1]
                    filter_parts.append(f"author.display_name.search:{urllib.parse.quote(last_name)}")
            
            # Anfrage erstellen
            url = f"{self.api_url}?filter={';'.join(filter_parts)}&sort=relevance_score:desc&per-page=5"
            headers = {"Accept": "application/json"}
            
            try:
                response = self._make_request("get", url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'results' in data and data['results']:
                        # Bewerte die Ergebnisse und wähle das beste
                        best_work = None
                        best_score = -1
                        
                        for work in data['results'][:5]:
                            score = self._score_openalex_work(work, title, authors or [])
                            if score > best_score:
                                best_score = score
                                best_work = work
                        
                        # Wenn ein gutes Ergebnis gefunden wurde
                        if best_work and best_score > 10:
                            logger.debug(f"OpenAlex-Ergebnis mit Score {best_score} gefunden")
                            return self._parse_openalex_work(best_work)
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei OpenAlex-Suche: {str(e)}")
            
            return {}
        
        return self._get_cached_or_fetch(cache_key, fetch_func)
    
    def _parse_openalex_work(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahiert relevante Metadaten aus einer OpenAlex-Antwort.
        
        Args:
            work: OpenAlex-Antwortobjekt
            
        Returns:
            Extrahierte Metadaten
        """
        metadata = {}
        
        # Titel
        if 'title' in work:
            metadata['title'] = work['title']
        
        # DOI
        if 'doi' in work and work['doi']:
            metadata['doi'] = work['doi']
        
        # Autoren
        if 'authorships' in work:
            authors = []
            for authorship in work['authorships']:
                if 'author' in authorship and 'display_name' in authorship['author']:
                    authors.append(authorship['author']['display_name'])
            if authors:
                metadata['author'] = authors
        
        # Jahr
        if 'publication_year' in work:
            metadata['year'] = work['publication_year']
        
        # Journal/Quelle
        if 'primary_location' in work and 'source' in work['primary_location']:
            source = work['primary_location']['source']
            if 'display_name' in source:
                metadata['journal'] = source['display_name']
                
            # ISSN
            if 'issn_l' in source:
                metadata['issn'] = source['issn_l']
        
        # Herausgeber
        if 'primary_location' in work and 'source' in work['primary_location'] and 'host_organization' in work['primary_location']['source']:
            if 'display_name' in work['primary_location']['source']['host_organization']:
                metadata['publisher'] = work['primary_location']['source']['host_organization']['display_name']
        
        # Zitationen
        if 'cited_by_count' in work:
            metadata['cited_by_count'] = work['cited_by_count']
        
        # Fachgebiet
        if 'concepts' in work and work['concepts']:
            concepts = []
            for concept in work['concepts'][:3]:  # Top 3 Konzepte
                if 'display_name' in concept:
                    concepts.append(concept['display_name'])
            if concepts:
                metadata['keywords'] = concepts
        
        # Open Access Status
        if 'open_access' in work and 'is_oa' in work['open_access']:
            metadata['is_open_access'] = work['open_access']['is_oa']
        
        # Typ
        if 'type' in work:
            metadata['type'] = work['type']
        
        # Abstract
        if 'abstract_inverted_index' in work:
            try:
                # OpenAlex speichert Abstracts in einem invertierten Index, wir müssen ihn rekonstruieren
                inverted_index = work['abstract_inverted_index']
                words = []
                max_position = 0
                
                # Finde die maximale Position
                for positions in inverted_index.values():
                    max_position = max(max_position, max(positions) if positions else 0)
                
                # Erstelle ein Array für alle Wortpositionen
                words = [''] * (max_position + 1)
                
                # Fülle das Array
                for word, positions in inverted_index.items():
                    for pos in positions:
                        words[pos] = word
                
                # Verbinde die Wörter zu einem Text
                abstract = ' '.join(words)
                metadata['abstract'] = abstract
            except Exception as e:
                logger.warning(f"Fehler beim Rekonstruieren des Abstracts: {str(e)}")
        
        return metadata
    
    def _score_openalex_work(self, work: Dict[str, Any], title: str, authors: List[str]) -> float:
        """
        Bewertet ein OpenAlex-Ergebnis basierend auf Titel und Autoren.
        
        Args:
            work: OpenAlex-Ergebnisobjekt
            title: Zu vergleichender Titel
            authors: Zu vergleichende Autoren
            
        Returns:
            Score von 0 bis 100
        """
        score = 0
        
        # Titelvergleich
        if 'title' in work and title:
            title_similarity = SequenceMatcher(None, title.lower(), work['title'].lower()).ratio()
            score += title_similarity * 50
        
        # Autorenvergleich
        if 'authorships' in work and authors:
            author_found = False
            for authorship in work['authorships']:
                if 'author' in authorship and 'display_name' in authorship['author']:
                    author_name = authorship['author']['display_name']
                    for orig_author in authors:
                        if orig_author.lower() in author_name.lower() or author_name.lower() in orig_author.lower():
                            author_found = True
                            break
            if author_found:
                score += 30
        
        # Bonus für vollständige Metadaten
        if 'publication_year' in work:
            score += 5
        if 'primary_location' in work and 'source' in work['primary_location']:
            score += 5
        if 'doi' in work and work['doi']:
            score += 5
        if 'cited_by_count' in work and work['cited_by_count'] > 0:
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
        if 'keywords' in metadata and metadata['keywords']:
            bonus_score += 4
        
        score += bonus_score
        logger.debug(f"Bonus-Score für zusätzliche Metadaten: {bonus_score}")
        
        return score