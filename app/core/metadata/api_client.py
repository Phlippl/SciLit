"""
API-Client für Metadaten-Dienste
-------------------------------
Verbindet zu verschiedenen Metadatendiensten für wissenschaftliche Literatur.
"""

import re
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import requests
import urllib.parse
from difflib import SequenceMatcher

from app.config import (
    CROSSREF_API_URL, OPENALEX_API_URL, OPENLIB_API_URL,
    GOOGLEBOOKS_API_URL, K10PLUS_API_URL
)
from app.core.metadata.extractor import string_similarity

# Logger konfigurieren
logger = logging.getLogger("scilit.metadata.api_client")

class MetadataAPIClient:
    """
    Client für verschiedene Metadaten-APIs von wissenschaftlichen Publikationen.
    
    Diese Klasse ermöglicht den Zugriff auf verschiedene externe APIs, um erweiterte 
    Metadaten für wissenschaftliche Dokumente abzurufen. Die Ergebnisse der APIs werden 
    bewertet und kombiniert, um optimale Metadaten für jedes Dokument zu erhalten.
    
    Attributes:
        metadata_sources (Dict[str, bool]): Konfiguration, welche APIs genutzt werden sollen
        session (requests.Session): HTTP-Session für Anfragen mit Caching/Wiederverwendung
        cache (Dict): Einfacher In-Memory-Cache für API-Ergebnisse
    """
    
    def __init__(self, metadata_sources: Dict[str, bool]):
        """
        Initialisiert den API-Client.
        
        Args:
            metadata_sources: Welche Metadaten-APIs verwendet werden sollen
        """
        self.metadata_sources = metadata_sources
        
        # Eine Session für alle Anfragen verwenden (für Connection Pooling)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SciLit/1.0 (https://github.com/yourusername/scilit; mailto:your.email@example.com)'
        })
        
        # Einfacher In-Memory-Cache für API-Antworten
        self.cache = {}
        
        logger.debug(f"MetadataAPIClient initialisiert mit Quellen: {metadata_sources}")
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten durch Abfragen verschiedener APIs.
        
        Diese Methode koordiniert die Abfragen an verschiedene Metadatendienste und
        kombiniert die Ergebnisse zu einem optimierten Metadatensatz.
        
        Args:
            basic_metadata: Aus dem Dokument extrahierte Metadaten
            
        Returns:
            Erweiterte Metadaten
        """
        metadata = basic_metadata.copy()
        
        # Titel oder Autor aus den Basis-Metadaten extrahieren
        title = metadata.get('title', '')
        authors = metadata.get('author', [])
        if isinstance(authors, str):
            authors = [authors]
        
        # DOI extrahieren, falls vorhanden
        doi = None
        for key, value in metadata.items():
            if key.lower() in ['doi', 'identifier'] and isinstance(value, str):
                doi_match = re.search(r'10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+', value)
                if doi_match:
                    doi = doi_match.group(0)
                    break
        
        logger.info(f"Erweitere Metadaten für Titel: {title}, Autoren: {authors}, DOI: {doi}")
        
        # Ergebnisliste für die Bewertung vorbereiten
        api_results = []
        
        # 1. CrossRef API
        if self.metadata_sources.get("use_crossref", True) and (title or authors or doi):
            try:
                crossref_metadata = self._fetch_crossref_metadata(title, authors, doi)
                if crossref_metadata:
                    logger.info("Metadaten über CrossRef gefunden")
                    score = self._score_metadata(crossref_metadata, title, authors)
                    api_results.append(('crossref', score, crossref_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei CrossRef-Abfrage: {str(e)}")
        
        # 2. Open Library API
        if self.metadata_sources.get("use_openlib", True) and (title or authors):
            try:
                openlib_metadata = self._fetch_openlib_metadata(title, authors)
                if openlib_metadata:
                    logger.info("Metadaten über Open Library gefunden")
                    score = self._score_metadata(openlib_metadata, title, authors)
                    api_results.append(('openlib', score, openlib_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei Open Library-Abfrage: {str(e)}")
        
        # 3. K10plus API
        if self.metadata_sources.get("use_k10plus", True) and (title or authors):
            try:
                k10plus_metadata = self._fetch_k10plus_metadata(title, authors)
                if k10plus_metadata:
                    logger.info("Metadaten über K10plus gefunden")
                    score = self._score_metadata(k10plus_metadata, title, authors)
                    api_results.append(('k10plus', score, k10plus_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei K10plus-Abfrage: {str(e)}")
        
        # 4. Google Books API
        if self.metadata_sources.get("use_googlebooks", True) and (title or authors):
            try:
                googlebooks_metadata = self._fetch_googlebooks_metadata(title, authors)
                if googlebooks_metadata:
                    logger.info("Metadaten über Google Books gefunden")
                    score = self._score_metadata(googlebooks_metadata, title, authors)
                    api_results.append(('googlebooks', score, googlebooks_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei Google Books-Abfrage: {str(e)}")
        
        # 5. OpenAlex API
        if self.metadata_sources.get("use_openalex", True) and (title or authors):
            try:
                openalex_metadata = self._fetch_openalex_metadata(title, authors)
                if openalex_metadata:
                    logger.info("Metadaten über OpenAlex gefunden")
                    score = self._score_metadata(openalex_metadata, title, authors)
                    api_results.append(('openalex', score, openalex_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei OpenAlex-Abfrage: {str(e)}")
        
        # Sortiere Ergebnisse nach Score und wähle das beste
        if api_results:
            api_results.sort(key=lambda x: x[1], reverse=True)
            best_source, best_score, best_metadata = api_results[0]
            logger.info(f"Beste Metadaten von {best_source} mit Score {best_score:.2f}")
            
            # Bei hohem Score das gesamte Ergebnis übernehmen
            if best_score > 70:
                logger.debug(f"Übernehme alle Metadaten von {best_source} aufgrund des hohen Scores")
                enhanced_metadata = metadata.copy()
                for key, value in best_metadata.items():
                    if value:  # Leere Werte nicht übernehmen
                        enhanced_metadata[key] = value
                return enhanced_metadata
            else:
                # Bei niedrigem Score selektiv nur bestimmte Felder übernehmen
                logger.debug(f"Übernehme ausgewählte Metadaten aufgrund des niedrigen Scores von {best_source}")
                for key in ['journal', 'publisher', 'doi', 'isbn', 'year']:
                    if key in best_metadata and best_metadata[key]:
                        metadata[key] = best_metadata[key]
        
        # Sicherstellen, dass die Grunddaten nicht leer sind
        if not metadata.get('title'):
            metadata['title'] = title or "Unbekannter Titel"
        
        if not metadata.get('author'):
            metadata['author'] = authors or ["Unbekannter Autor"]
        
        return metadata
    
    def _score_metadata(self, metadata: Dict[str, Any], original_title: str, original_authors: List[str]) -> float:
        """
        Bewertet die Qualität der gefundenen Metadaten im Vergleich zu den ursprünglichen Daten.
        
        Diese Methode berechnet einen Score, der angibt, wie gut die gefundenen Metadaten
        mit den ursprünglichen Daten übereinstimmen. Der Score wird verwendet, um das beste
        Ergebnis aus verschiedenen APIs auszuwählen.
        
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
        if 'isbn' in metadata and metadata['isbn']:
            bonus_score += 4
        
        score += bonus_score
        logger.debug(f"Bonus-Score für zusätzliche Metadaten: {bonus_score}")
        
        return score
    
    def _fetch_crossref_metadata(self, title: str, authors: List[str], doi: Optional[str]) -> Dict[str, Any]:
        """
        Ruft Metadaten von CrossRef ab.
        
        CrossRef ist eine zentrale Quelle für DOIs und Metadaten akademischer Publikationen.
        Diese Methode sucht entweder direkt nach einer DOI oder nach Titel und Autoren.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            doi: DOI, falls vorhanden
            
        Returns:
            Dictionary mit Metadaten oder leeres Dictionary bei Fehler
        """
        metadata = {}
        
        # Cache-Schlüssel erstellen
        cache_key = f"crossref_{doi or title}_{authors}"
        
        # Cache prüfen
        if cache_key in self.cache:
            logger.debug(f"Verwende gecachte CrossRef-Ergebnisse für {doi or title}")
            return self.cache[cache_key]
        
        # Bei vorhandener DOI direkt danach suchen
        if doi:
            url = f"{CROSSREF_API_URL}/{doi}"
            try:
                logger.debug(f"Suche bei CrossRef nach DOI: {doi}")
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'message' in data:
                        message = data['message']
                        
                        # Metadaten extrahieren
                        metadata = self._parse_crossref_message(message)
                        
                        # In Cache speichern
                        self.cache[cache_key] = metadata
                        return metadata
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei CrossRef-DOI-Anfrage: {str(e)}")
        
        # Falls keine DOI verfügbar oder Suche fehlgeschlagen, versuche Titel/Autor-Suche
        if title or authors:
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
                logger.debug("Nicht genug Daten für CrossRef-Suche")
                return {}
            
            query = " ".join(query_parts)
            url = f"{CROSSREF_API_URL}?query={query}&rows=5"
            
            try:
                logger.debug(f"Suche bei CrossRef mit Query: {query}")
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'message' in data and 'items' in data['message'] and data['message']['items']:
                        # Mehrere Ergebnisse durchgehen und das beste auswählen
                        best_item = None
                        best_score = -1
                        
                        for item in data['message']['items'][:5]:  # Nur die ersten 5 prüfen
                            score = self._score_crossref_item(item, title, authors)
                            if score > best_score:
                                best_score = score
                                best_item = item
                        
                        # Wenn ein gutes Ergebnis gefunden wurde
                        if best_item and best_score > 10:
                            metadata = self._parse_crossref_message(best_item)
                            
                            # In Cache speichern
                            self.cache[cache_key] = metadata
                            logger.debug(f"CrossRef-Ergebnis mit Score {best_score} gefunden")
                            return metadata
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei CrossRef-Suche: {str(e)}")
        
        # Keine Ergebnisse
        logger.debug("Keine Ergebnisse von CrossRef")
        return {}
    
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
    
    def _fetch_openalex_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """
        Ruft Metadaten von OpenAlex ab.
        
        OpenAlex ist ein offener akademischer Graph und Index, der Informationen
        über wissenschaftliche Publikationen bereitstellt.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            
        Returns:
            Dictionary mit Metadaten oder leeres Dictionary bei Fehler
        """
        if not title:
            return {}
        
        # Cache-Schlüssel erstellen
        cache_key = f"openalex_{title}_{authors}"
        
        # Cache prüfen
        if cache_key in self.cache:
            logger.debug(f"Verwende gecachte OpenAlex-Ergebnisse für {title}")
            return self.cache[cache_key]
        
        # Bereinigter Titel für die Suche
        clean_title = re.sub(r'[^\w\s]', ' ', title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # Anfrage erstellen
        query = f"title.search:{urllib.parse.quote(clean_title)}"
        
        # Autorenfilter hinzufügen, wenn möglich
        if authors and len(authors) > 0:
            # Extrahiere den Nachnamen des ersten Autors
            name_parts = authors[0].split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                query += f"&filter=author.display_name.search:{urllib.parse.quote(last_name)}"
        
        url = f"{OPENALEX_API_URL}?filter={query}&sort=relevance_score:desc&per-page=5"
        headers = {"Accept": "application/json"}
        
        try:
            logger.debug(f"Suche bei OpenAlex mit Query: {query}")
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'results' in data and data['results']:
                    # Bewerte die Ergebnisse und wähle das beste
                    best_work = None
                    best_score = -1
                    
                    for work in data['results'][:5]:
                        score = self._score_openalex_work(work, title, authors)
                        if score > best_score:
                            best_score = score
                            best_work = work
                    
                    # Wenn ein gutes Ergebnis gefunden wurde
                    if best_work and best_score > 10:
                        metadata = self._parse_openalex_work(best_work)
                        
                        # In Cache speichern
                        self.cache[cache_key] = metadata
                        logger.debug(f"OpenAlex-Ergebnis mit Score {best_score} gefunden")
                        return metadata
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.warning(f"Fehler bei OpenAlex-Abfrage: {str(e)}")
        
        # Keine Ergebnisse
        logger.debug("Keine Ergebnisse von OpenAlex")
        return {}
    
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
    
    # Weitere Methoden für andere APIs (_fetch_openlib_metadata, _fetch_googlebooks_metadata, _fetch_k10plus_metadata)
    # folgen dem gleichen Muster und würden hier implementiert werden
    
    def _fetch_googlebooks_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """
        Ruft Metadaten von der Google Books API ab.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            
        Returns:
            Dictionary mit Metadaten oder leeres Dictionary bei Fehler
        """
        # Implementierung ähnlich zu den anderen API-Methoden
        return {}
    
    def _fetch_openlib_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """
        Ruft Metadaten von der Open Library API ab.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            
        Returns:
            Dictionary mit Metadaten oder leeres Dictionary bei Fehler
        """
        # Implementierung ähnlich zu den anderen API-Methoden
        return {}
    
    def _fetch_k10plus_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """
        Ruft Metadaten vom K10plus-Katalog ab.
        
        Args:
            title: Titel der Publikation
            authors: Liste der Autoren
            
        Returns:
            Dictionary mit Metadaten oder leeres Dictionary bei Fehler
        """
        # Implementierung ähnlich zu den anderen API-Methoden
        return {}