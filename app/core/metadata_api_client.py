"""
API-Client für Metadaten-Dienste
-------------------------------
Verbindet zu verschiedenen Metadatendiensten für wissenschaftliche Literatur.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any
import requests
from difflib import SequenceMatcher

from .metadata_extraction import string_similarity

# Logger konfigurieren
logger = logging.getLogger("scilit.metadata_api_client")

class MetadataAPIClient:
    """Client für verschiedene Metadaten-APIs."""
    
    def __init__(self, metadata_sources: Dict[str, bool]):
        """
        Initialisiert den API-Client.
        
        Args:
            metadata_sources: Welche Metadaten-APIs verwendet werden sollen
        """
        self.metadata_sources = metadata_sources
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten durch Abfragen verschiedener APIs.
        Mit verbesserten Suchstrategien und Fehlerbehandlung.
        
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
        
        # Wir erstellen eine Liste, um die Ergebnisse zu speichern und später zu bewerten
        api_results = []
        
        # 1. CrossRef API
        if self.metadata_sources.get("use_crossref", True) and (title or authors or doi):
            try:
                crossref_metadata = self._fetch_crossref_metadata(title, authors, doi)
                if crossref_metadata:
                    logger.info("Metadaten über CrossRef gefunden")
                    api_results.append(('crossref', self._score_metadata(crossref_metadata, title, authors), crossref_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei CrossRef-Abfrage: {str(e)}")
        
        # 2. Open Library API
        if self.metadata_sources.get("use_openlib", True) and (title or authors):
            try:
                openlib_metadata = self._fetch_openlib_metadata(title, authors)
                if openlib_metadata:
                    logger.info("Metadaten über Open Library gefunden")
                    api_results.append(('openlib', self._score_metadata(openlib_metadata, title, authors), openlib_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei Open Library-Abfrage: {str(e)}")
        
        # 3. K10plus API
        if self.metadata_sources.get("use_k10plus", True) and (title or authors):
            try:
                k10plus_metadata = self._fetch_k10plus_metadata(title, authors)
                if k10plus_metadata:
                    logger.info("Metadaten über K10plus gefunden")
                    api_results.append(('k10plus', self._score_metadata(k10plus_metadata, title, authors), k10plus_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei K10plus-Abfrage: {str(e)}")
        
        # 4. Google Books API
        if self.metadata_sources.get("use_googlebooks", True) and (title or authors):
            try:
                googlebooks_metadata = self._fetch_googlebooks_metadata(title, authors)
                if googlebooks_metadata:
                    logger.info("Metadaten über Google Books gefunden")
                    api_results.append(('googlebooks', self._score_metadata(googlebooks_metadata, title, authors), googlebooks_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei Google Books-Abfrage: {str(e)}")
        
        # 5. OpenAlex API
        if self.metadata_sources.get("use_openalex", True) and (title or authors):
            try:
                openalex_metadata = self._fetch_openalex_metadata(title, authors)
                if openalex_metadata:
                    logger.info("Metadaten über OpenAlex gefunden")
                    api_results.append(('openalex', self._score_metadata(openalex_metadata, title, authors), openalex_metadata))
            except Exception as e:
                logger.warning(f"Fehler bei OpenAlex-Abfrage: {str(e)}")
        
        # Sortiere Ergebnisse nach Score und wähle das beste
        if api_results:
            api_results.sort(key=lambda x: x[1], reverse=True)
            best_source, best_score, best_metadata = api_results[0]
            logger.info(f"Beste Metadaten von {best_source} mit Score {best_score}")
            
            # Nimm nur die Metadaten, bei denen wir vertrauen, dass sie richtig sind (basierend auf dem Score)
            if best_score > 70:  # Schwellenwert für "gute" Übereinstimmung
                metadata.update(best_metadata)
            else:
                # Bei niedrigem Score selektiv nur bestimmte Felder übernehmen
                for key in ['journal', 'publisher', 'doi', 'isbn']:
                    if key in best_metadata and best_metadata[key]:
                        metadata[key] = best_metadata[key]
        
        # Sicherstellen, dass die Grunddaten nicht leer sind
        if not metadata.get('title'):
            metadata['title'] = title or "Unbekannter Titel"
        
        if not metadata.get('author'):
            metadata['author'] = authors or ["Unbekannter Autor"]
        
        return metadata
    
    def _score_metadata(self, metadata: Dict[str, Any], original_title: str, original_authors: List[str]) -> float:
        """Bewertet die Qualität der gefundenen Metadaten im Vergleich zu den ursprünglichen Daten."""
        score = 0.0
        
        # Titelvergleich
        if 'title' in metadata and original_title:
            title_similarity = string_similarity(metadata['title'], original_title)
            score += title_similarity * 50  # Titel ist besonders wichtig
        
        # Autorenvergleich
        if 'author' in metadata and original_authors:
            found_authors = metadata['author']
            if isinstance(found_authors, str):
                found_authors = [found_authors]
            
            # Für jeden gefundenen Autor prüfen, ob er mit einem Original-Autor übereinstimmt
            author_similarity = 0
            for found_author in found_authors:
                best_match = max([string_similarity(found_author, orig_author) for orig_author in original_authors], default=0)
                author_similarity += best_match
            
            if found_authors:
                author_similarity /= len(found_authors)
                score += author_similarity * 30  # Autoren sind auch wichtig
        
        # Zusätzliche Metadaten geben Extrapunkte
        if 'year' in metadata and metadata['year']:
            score += 5
        if 'journal' in metadata and metadata['journal']:
            score += 5
        if 'publisher' in metadata and metadata['publisher']:
            score += 5
        if 'doi' in metadata and metadata['doi']:
            score += 10
        if 'isbn' in metadata and metadata['isbn']:
            score += 10
        
        return score
    
    def _fetch_crossref_metadata(self, title: str, authors: List[str], doi: Optional[str]) -> Dict[str, Any]:
        """Ruft Metadaten von CrossRef ab mit verbesserter Suchanfrage und Fehlerbehandlung."""
        metadata = {}
        
        if doi:
            # Direkte Suche nach DOI
            url = f"https://api.crossref.org/works/{doi}"
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'message' in data:
                        message = data['message']
                        
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
                        metadata['doi'] = doi
                        
                        return metadata
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei CrossRef-DOI-Anfrage: {str(e)}")
        
        # Suche nach Titel und/oder Autor, wenn kein DOI oder DOI-Suche erfolglos
        if title or authors:
            query_parts = []
            
            if title:
                # Entferne Sonderzeichen und führe einfache Filterung durch
                clean_title = re.sub(r'[^\w\s]', ' ', title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                query_parts.append(f'title:"{clean_title}"')
            
            if authors and len(authors) > 0:
                # Nehme den ersten Autor und bereite ihn für die Suche vor
                first_author = authors[0]
                # Trenne Nachname (letzter Teil) vom Rest
                name_parts = first_author.split()
                if len(name_parts) > 1:
                    last_name = name_parts[-1]
                    query_parts.append(f'author:"{last_name}"')
                else:
                    query_parts.append(f'author:"{first_author}"')
            
            query = " ".join(query_parts)
            url = f"https://api.crossref.org/works?query={requests.utils.quote(query)}&rows=5"
            
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'message' in data and 'items' in data['message'] and data['message']['items']:
                        # Mehrere Ergebnisse durchgehen und das beste auswählen
                        best_item = None
                        best_score = -1
                        
                        for item in data['message']['items'][:5]:  # Betrachte nur die ersten 5 Ergebnisse
                            score = 0
                            
                            # Bewerte Titelübereinstimmung
                            if 'title' in item and item['title'] and title:
                                title_similarity = SequenceMatcher(None, title.lower(), item['title'][0].lower()).ratio()
                                score += title_similarity * 10
                            
                            # Bewerte Autorenübereinstimmung
                            if 'author' in item and authors:
                                author_found = False
                                for author in item['author']:
                                    if 'family' in author:
                                        for orig_author in authors:
                                            if author['family'].lower() in orig_author.lower():
                                                author_found = True
                                                break
                                if author_found:
                                    score += 5
                            
                            # Bewerte Jahr, falls vorhanden
                            if 'published' in item and 'date-parts' in item['published']:
                                date_parts = item['published']['date-parts'][0]
                                if date_parts and len(date_parts) > 0:
                                    score += 2
                            
                            if score > best_score:
                                best_score = score
                                best_item = item
                        
                        # Verwende das beste Ergebnis, wenn es einen Mindestscore erreicht
                        if best_item and best_score > 5:
                            # Titel
                            if 'title' in best_item and best_item['title']:
                                metadata['title'] = best_item['title'][0]
                            
                            # Autoren
                            if 'author' in best_item:
                                authors = []
                                for author in best_item['author']:
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
                            if 'container-title' in best_item and best_item['container-title']:
                                metadata['journal'] = best_item['container-title'][0]
                            
                            # Jahr
                            if 'published' in best_item and 'date-parts' in best_item['published']:
                                date_parts = best_item['published']['date-parts'][0]
                                if date_parts and len(date_parts) > 0:
                                    metadata['year'] = date_parts[0]
                            
                            # Verleger
                            if 'publisher' in best_item:
                                metadata['publisher'] = best_item['publisher']
                            
                            # DOI
                            if 'DOI' in best_item:
                                metadata['doi'] = best_item['DOI']
                            
                            return metadata
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Fehler bei CrossRef-Suche: {str(e)}")
        
        return metadata
    
    def _fetch_googlebooks_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """Ruft Metadaten von Google Books ab mit verbesserter Suchanfrage."""
        metadata = {}
        
        if not title:
            return metadata
        
        # Bereite eine präzisere Suchanfrage vor
        query_parts = []
        
        # Füge den Titel hinzu
        clean_title = re.sub(r'[^\w\s]', ' ', title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        if clean_title:
            query_parts.append(f'intitle:"{clean_title}"')
        
        # Füge den ersten Autor hinzu, falls vorhanden
        if authors and len(authors) > 0:
            first_author = authors[0]
            # Trenne Nachname (letzter Teil) vom Rest
            name_parts = first_author.split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                query_parts.append(f'inauthor:"{last_name}"')
            else:
                query_parts.append(f'inauthor:"{first_author}"')
        
        # Erstelle die Suchanfrage
        query = " ".join(query_parts)
        url = f"https://www.googleapis.com/books/v1/volumes?q={requests.utils.quote(query)}&maxResults=5"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'items' in data and data['items']:
                    # Mehrere Ergebnisse durchgehen und das beste auswählen
                    best_item = None
                    best_score = -1
                    
                    for item in data['items'][:5]:  # Betrachte nur die ersten 5 Ergebnisse
                        if 'volumeInfo' not in item:
                            continue
                        
                        volume_info = item['volumeInfo']
                        score = 0
                        
                        # Bewerte Titelübereinstimmung
                        if 'title' in volume_info and title:
                            title_similarity = SequenceMatcher(None, title.lower(), volume_info['title'].lower()).ratio()
                            score += title_similarity * 10
                        
                        # Bewerte Autorenübereinstimmung
                        if 'authors' in volume_info and authors:
                            author_found = False
                            for author in volume_info['authors']:
                                for orig_author in authors:
                                    if orig_author.lower() in author.lower() or author.lower() in orig_author.lower():
                                        author_found = True
                                        break
                            if author_found:
                                score += 5
                        
                        # Bewerte Vollständigkeit der Metadaten
                        if 'publishedDate' in volume_info:
                            score += 2
                        if 'publisher' in volume_info:
                            score += 2
                        if 'industryIdentifiers' in volume_info:
                            score += 3
                        
                        if score > best_score:
                            best_score = score
                            best_item = volume_info
                    
                    # Verwende das beste Ergebnis, wenn es einen Mindestscore erreicht
                    if best_item and best_score > 5:
                        # Titel
                        if 'title' in best_item:
                            metadata['title'] = best_item['title']
                        
                        # Autoren
                        if 'authors' in best_item:
                            metadata['author'] = best_item['authors']
                        
                        # Verlag
                        if 'publisher' in best_item:
                            metadata['publisher'] = best_item['publisher']
                        
                        # Jahr
                        if 'publishedDate' in best_item:
                            # Jahr aus Datumsstring extrahieren
                            year_match = re.search(r'(\d{4})', best_item['publishedDate'])
                            if year_match:
                                metadata['year'] = int(year_match.group(1))
                        
                        # ISBN
                        if 'industryIdentifiers' in best_item:
                            for identifier in best_item['industryIdentifiers']:
                                if identifier['type'] in ['ISBN_13', 'ISBN_10']:
                                    metadata['isbn'] = identifier['identifier']
                                    break
                        
                        # Seitenzahl
                        if 'pageCount' in best_item:
                            metadata['page_count'] = best_item['pageCount']
                        
                        # Kategorie/Fachbereich
                        if 'categories' in best_item and best_item['categories']:
                            metadata['categories'] = best_item['categories']
                        
                        # Sprache
                        if 'language' in best_item:
                            metadata['language'] = best_item['language']
                        
                        return metadata
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.warning(f"Fehler bei Google Books-Abfrage: {str(e)}")
        
        return metadata
    
    def _fetch_openalex_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """Ruft Metadaten von OpenAlex ab mit verbesserter Suche."""
        metadata = {}
        
        if not title:
            return metadata
        
        # Bereite eine präzisere Suchanfrage vor
        clean_title = re.sub(r'[^\w\s]', ' ', title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        query = f"title.search:{requests.utils.quote(clean_title)}"
        
        # Füge Autorenfilter hinzu, wenn möglich
        if authors and len(authors) > 0:
            # Versuche, Vor- und Nachnamen zu trennen
            name_parts = authors[0].split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                query += f"&filter=author.display_name.search:{requests.utils.quote(last_name)}"
        
        url = f"https://api.openalex.org/works?filter={query}&sort=relevance_score:desc&per-page=5"
        headers = {"Accept": "application/json"}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'results' in data and data['results']:
                    # Mehrere Ergebnisse durchgehen und das beste auswählen
                    best_work = None
                    best_score = -1
                    
                    for work in data['results'][:5]:  # Betrachte nur die ersten 5 Ergebnisse
                        score = 0
                        
                        # Bewerte Titelübereinstimmung
                        if 'title' in work and title:
                            title_similarity = SequenceMatcher(None, title.lower(), work['title'].lower()).ratio()
                            score += title_similarity * 10
                        
                        # Bewerte Autorenübereinstimmung
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
                                score += 5
                        
                        # Bewerte Jahr, falls vorhanden
                        if 'publication_year' in work:
                            score += 2
                        
                        # Bewerte Quelle, falls vorhanden
                        if 'primary_location' in work and 'source' in work['primary_location']:
                            score += 2
                        
                        # Bewerte DOI, falls vorhanden
                        if 'doi' in work and work['doi']:
                            score += 3
                        
                        # Bewerte Zitationszahl
                        if 'cited_by_count' in work and work['cited_by_count'] > 10:
                            score += 1
                        
                        if score > best_score:
                            best_score = score
                            best_work = work
                    
                    # Verwende das beste Ergebnis, wenn es einen Mindestscore erreicht
                    if best_work and best_score > 5:
                        # Titel
                        if 'title' in best_work:
                            metadata['title'] = best_work['title']
                        
                        # DOI
                        if 'doi' in best_work and best_work['doi']:
                            metadata['doi'] = best_work['doi']
                        
                        # Autoren
                        if 'authorships' in best_work:
                            authors = []
                            for authorship in best_work['authorships']:
                                if 'author' in authorship and 'display_name' in authorship['author']:
                                    authors.append(authorship['author']['display_name'])
                            if authors:
                                metadata['author'] = authors
                        
                        # Jahr
                        if 'publication_year' in best_work:
                            metadata['year'] = best_work['publication_year']
                        
                        # Journal/Quelle
                        if 'primary_location' in best_work and 'source' in best_work['primary_location']:
                            source = best_work['primary_location']['source']
                            if 'display_name' in source:
                                metadata['journal'] = source['display_name']
                        
                        # Zitationen
                        if 'cited_by_count' in best_work:
                            metadata['cited_by_count'] = best_work['cited_by_count']
                        
                        # Fachgebiet
                        if 'concepts' in best_work and best_work['concepts']:
                            concepts = []
                            for concept in best_work['concepts']:
                                if 'display_name' in concept:
                                    concepts.append(concept['display_name'])
                            if concepts:
                                metadata['concepts'] = concepts
                        
                        # Open Access Status
                        if 'open_access' in best_work and 'is_oa' in best_work['open_access']:
                            metadata['is_open_access'] = best_work['open_access']['is_oa']
                        
                        return metadata
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.warning(f"Fehler bei OpenAlex-Abfrage: {str(e)}")
        
        return metadata
    
    def _fetch_openlib_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """Ruft Metadaten von Open Library ab mit verbesserter Suche."""
        metadata = {}
        
        if not title:
            return metadata
        
        # Bereite eine präzisere Suchanfrage vor
        clean_title = re.sub(r'[^\w\s]', ' ', title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # Erstelle eine Suchanfrage mit Titel
        query = f'"{clean_title}"'
        
        # Füge Autor hinzu, falls vorhanden
        if authors and authors[0]:
            # Trenne Nachname (letzter Teil) vom Rest
            name_parts = authors[0].split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                query += f" author:{last_name}"
            else:
                query += f" author:{authors[0]}"
        
        url = f"https://openlibrary.org/search.json?q={requests.utils.quote(query)}&limit=5"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'docs' in data and data['docs']:
                    # Mehrere Ergebnisse durchgehen und das beste auswählen
                    best_doc = None
                    best_score = -1
                    
                    for doc in data['docs'][:5]:  # Betrachte nur die ersten 5 Ergebnisse
                        score = 0
                        
                        # Bewerte Titelübereinstimmung
                        if 'title' in doc and title:
                            title_similarity = SequenceMatcher(None, title.lower(), doc['title'].lower()).ratio()
                            score += title_similarity * 10
                        
                        # Bewerte Autorenübereinstimmung
                        if 'author_name' in doc and authors:
                            author_found = False
                            for author in doc['author_name']:
                                for orig_author in authors:
                                    if orig_author.lower() in author.lower() or author.lower() in orig_author.lower():
                                        author_found = True
                                        break
                            if author_found:
                                score += 5
                        
                        # Bewerte Vollständigkeit der Metadaten
                        if 'first_publish_year' in doc:
                            score += 2
                        if 'publisher' in doc:
                            score += 2
                        if 'isbn' in doc:
                            score += 3
                        
                        if score > best_score:
                            best_score = score
                            best_doc = doc
                    
                    # Verwende das beste Ergebnis, wenn es einen Mindestscore erreicht
                    if best_doc and best_score > 5:
                        # Titel
                        if 'title' in best_doc:
                            metadata['title'] = best_doc['title']
                        
                        # Autoren
                        if 'author_name' in best_doc:
                            metadata['author'] = best_doc['author_name']
                        
                        # Jahr
                        if 'first_publish_year' in best_doc:
                            metadata['year'] = best_doc['first_publish_year']
                        
                        # Verleger
                        if 'publisher' in best_doc:
                            if isinstance(best_doc['publisher'], list) and best_doc['publisher']:
                                metadata['publisher'] = best_doc['publisher'][0]
                            else:
                                metadata['publisher'] = best_doc['publisher']
                        
                        # ISBN
                        if 'isbn' in best_doc and best_doc['isbn']:
                            if isinstance(best_doc['isbn'], list):
                                metadata['isbn'] = best_doc['isbn'][0]
                            else:
                                metadata['isbn'] = best_doc['isbn']
                        
                        # Sprache
                        if 'language' in best_doc and best_doc['language']:
                            if isinstance(best_doc['language'], list):
                                metadata['language'] = best_doc['language'][0]
                            else:
                                metadata['language'] = best_doc['language']
                        
                        # Seitenzahl
                        if 'number_of_pages_median' in best_doc:
                            metadata['page_count'] = best_doc['number_of_pages_median']
                        
                        return metadata
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.warning(f"Fehler bei Open Library-Abfrage: {str(e)}")
        
        return metadata
    
    def _fetch_k10plus_metadata(self, title: str, authors: List[str]) -> Dict[str, Any]:
        """
        Ruft Metadaten vom K10plus-Katalog über die SRU-API ab.
        Optimiert basierend auf der K10plus SRU-Dokumentation.
        """
        metadata = {}
        
        if not title:
            return metadata
        
        # Bereinige den Titel für die Suche
        clean_title = re.sub(r'[^\w\s]', ' ', title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # Erstelle CQL-Suchanfrage (Contextual Query Language)
        # Verwende pica.tit für Titelsuche
        query_parts = [f'pica.tit="{clean_title}"']
        
        # Füge Autorsuche hinzu, falls vorhanden
        if authors and len(authors) > 0:
            # Trenne Nachname (letzter Teil) vom Rest
            name_parts = authors[0].split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                # Verwende pica.per für Personensuche
                query_parts.append(f'pica.per="{last_name}"')
        
        # Verbinde Suchteile mit AND
        query = " and ".join(query_parts)
        
        # Der Standardserver ist: sru.k10plus.de
        # Verwende die GBV Datenbank (opac-de-627) wie in der Dokumentation empfohlen
        base_url = "https://sru.k10plus.de/opac-de-627"
        
        # Parameter gemäß SRU-Standard:
        # - version=1.1: SRU Version
        # - operation=searchRetrieve: Suchanfrage
        # - query: CQL-Suchanfrage
        # - maximumRecords: Maximale Anzahl Ergebnisse
        # - recordSchema: Format der Rückgabe (PicaXML ist detaillierter als Dublin Core)
        url = f"{base_url}?version=1.1&operation=searchRetrieve&query={requests.utils.quote(query)}&maximumRecords=5&recordSchema=picaxml"
        
        try:
            response = requests.get(url, timeout=15)  # Längeres Timeout für diese API
            
            if response.status_code == 200:
                # Ergebnis im XML-Format verarbeiten
                import xml.etree.ElementTree as ET
                
                try:
                    root = ET.fromstring(response.text)
                    
                    # K10plus nutzt diese Namespaces gemäß Dokumentation
                    ns = {
                        'zs': 'http://www.loc.gov/zing/srw/',
                        'pica': 'info:srw/schema/5/picaXML-v1.0'
                    }
                    
                    # Prüfe, ob Ergebnisse vorhanden sind
                    record_count_elem = root.find('.//zs:numberOfRecords', ns)
                    if record_count_elem is not None and record_count_elem.text != '0':
                        # Mehrere Ergebnisse durchgehen und das beste auswählen
                        best_record = None
                        best_score = -1
                        
                        # Finde alle Datensätze
                        records = root.findall('.//pica:record', ns)
                        
                        for record in records[:5]:  # Betrachte nur die ersten 5 Ergebnisse
                            score = 0
                            
                            # Extrahiere Titel nach K10plus PICA+ Format
                            # 021A $a enthält den Haupttitel
                            title_field = record.find('.//pica:datafield[@tag="021A"]/pica:subfield[@code="a"]', ns)
                            record_title = title_field.text if title_field is not None else ""
                            
                            # Bewerte Titelübereinstimmung
                            if record_title and title:
                                title_similarity = SequenceMatcher(None, title.lower(), record_title.lower()).ratio()
                                score += title_similarity * 10
                            
                            # Extrahiere Autor nach K10plus PICA+ Format
                            # 028A enthält den ersten Autor (Haupteintragung)
                            # 028B enthält weitere Autoren (Nebeneintragungen)
                            author_fields = []
                            author_fields.extend(record.findall('.//pica:datafield[@tag="028A"]', ns))
                            author_fields.extend(record.findall('.//pica:datafield[@tag="028B"]', ns))
                            
                            author_found = False
                            record_authors = []
                            
                            for author_field in author_fields:
                                author_parts = []
                                
                                # Nachname $a
                                last_name = author_field.find('./pica:subfield[@code="a"]', ns)
                                if last_name is not None:
                                    author_parts.append(last_name.text)
                                
                                # Vorname $d
                                first_name = author_field.find('./pica:subfield[@code="d"]', ns)
                                if first_name is not None:
                                    author_parts.append(first_name.text)
                                
                                if author_parts:
                                    record_author = ' '.join(author_parts)
                                    record_authors.append(record_author)
                                    
                                    for orig_author in authors:
                                        if orig_author.lower() in record_author.lower() or record_author.lower() in orig_author.lower():
                                            author_found = True
                                            break
                            
                            if author_found:
                                score += 5
                            
                            # Jahr nach K10plus PICA+ Format
                            # 011@ $a enthält das Erscheinungsjahr
                            year_field = record.find('.//pica:datafield[@tag="011@"]/pica:subfield[@code="a"]', ns)
                            if year_field is not None:
                                score += 2
                            
                            # Verlag nach K10plus PICA+ Format
                            # 033A $n enthält den Verlagsnamen
                            publisher_field = record.find('.//pica:datafield[@tag="033A"]/pica:subfield[@code="n"]', ns)
                            if publisher_field is not None:
                                score += 2
                            
                            # ISBN nach K10plus PICA+ Format
                            # 004A $0 enthält die ISBN
                            isbn_field = record.find('.//pica:datafield[@tag="004A"]/pica:subfield[@code="0"]', ns)
                            if isbn_field is not None:
                                score += 3
                            
                            if score > best_score:
                                best_score = score
                                best_record = record
                        
                        # Verwende das beste Ergebnis, wenn es einen Mindestscore erreicht
                        if best_record and best_score > 5:
                            # Titel extrahieren
                            title_field = best_record.find('.//pica:datafield[@tag="021A"]/pica:subfield[@code="a"]', ns)
                            if title_field is not None:
                                metadata['title'] = title_field.text
                                
                                # Untertitel falls vorhanden (021A $d)
                                subtitle_field = best_record.find('.//pica:datafield[@tag="021A"]/pica:subfield[@code="d"]', ns)
                                if subtitle_field is not None:
                                    metadata['title'] += " : " + subtitle_field.text
                            
                            # Autoren extrahieren
                            authors = []
                            all_author_fields = []
                            all_author_fields.extend(best_record.findall('.//pica:datafield[@tag="028A"]', ns))
                            all_author_fields.extend(best_record.findall('.//pica:datafield[@tag="028B"]', ns))
                            
                            for author_field in all_author_fields:
                                author_parts = []
                                
                                # Nachname $a
                                last_name = author_field.find('./pica:subfield[@code="a"]', ns)
                                if last_name is not None:
                                    author_parts.append(last_name.text)
                                
                                # Vorname $d
                                first_name = author_field.find('./pica:subfield[@code="d"]', ns)
                                if first_name is not None:
                                    author_parts.append(first_name.text)
                                
                                # Akademischer Titel falls vorhanden $c
                                academic_title = author_field.find('./pica:subfield[@code="c"]', ns)
                                if academic_title is not None:
                                    author_parts.append(f"({academic_title.text})")
                                
                                if author_parts:
                                    authors.append(' '.join(author_parts))
                            
                            if authors:
                                metadata['author'] = authors
                            
                            # Jahr extrahieren
                            year_field = best_record.find('.//pica:datafield[@tag="011@"]/pica:subfield[@code="a"]', ns)
                            if year_field is not None:
                                # Jahr aus Datumsstring extrahieren
                                year_match = re.search(r'(\d{4})', year_field.text)
                                if year_match:
                                    metadata['year'] = int(year_match.group(1))
                            
                            # Verlag extrahieren
                            publisher_field = best_record.find('.//pica:datafield[@tag="033A"]/pica:subfield[@code="n"]', ns)
                            publisher_place = best_record.find('.//pica:datafield[@tag="033A"]/pica:subfield[@code="p"]', ns)
                            
                            if publisher_field is not None:
                                publisher_text = publisher_field.text
                                if publisher_place is not None:
                                    publisher_text = f"{publisher_place.text}: {publisher_text}"
                                    
                                metadata['publisher'] = publisher_text
                            
                            # ISBN extrahieren
                            isbn_field = best_record.find('.//pica:datafield[@tag="004A"]/pica:subfield[@code="0"]', ns)
                            if isbn_field is not None:
                                metadata['isbn'] = isbn_field.text
                            
                            # Seitenzahl extrahieren
                            # 034D $a enthält den Umfang (z.B. "240 S.")
                            pages_field = best_record.find('.//pica:datafield[@tag="034D"]/pica:subfield[@code="a"]', ns)
                            if pages_field is not None:
                                # Extrahiere Zahl aus Seitenangabe
                                pages_match = re.search(r'(\d+)\s*S', pages_field.text)
                                if pages_match:
                                    metadata['page_count'] = int(pages_match.group(1))
                            
                            # Sprache extrahieren
                            # 010@ $a enthält den Sprachcode
                            language_field = best_record.find('.//pica:datafield[@tag="010@"]/pica:subfield[@code="a"]', ns)
                            if language_field is not None:
                                language_code = language_field.text
                                # Konvertiere Sprachcode zu Vollform nach ISO 639-1
                                language_map = {
                                    'ger': 'de',  # Deutsch
                                    'eng': 'en',  # Englisch
                                    'fre': 'fr',  # Französisch
                                    'spa': 'es',  # Spanisch
                                    'ita': 'it',  # Italienisch
                                    'rus': 'ru',  # Russisch
                                    'jpn': 'ja',  # Japanisch
                                    'chi': 'zh',  # Chinesisch
                                    'lat': 'la',  # Latein
                                    'gre': 'el'   # Griechisch
                                }
                                metadata['language'] = language_map.get(language_code, language_code)
                            
                            # Schlagwörter extrahieren
                            # 044K enthält Schlagwörter
                            keywords = []
                            keyword_fields = best_record.findall('.//pica:datafield[@tag="044K"]/pica:subfield[@code="a"]', ns)
                            for keyword_field in keyword_fields:
                                if keyword_field.text:
                                    keywords.append(keyword_field.text)
                            
                            if keywords:
                                metadata['keywords'] = keywords
                                
                            # PPN-ID (für spätere Referenz)
                            ppn_field = best_record.find('.//pica:datafield[@tag="003@"]/pica:subfield[@code="0"]', ns)
                            if ppn_field is not None:
                                metadata['ppn'] = ppn_field.text
                            
                            return metadata
                
                except ET.ParseError as e:
                    logger.warning(f"Fehler beim Parsen der K10plus XML-Antwort: {str(e)}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Fehler bei K10plus-Abfrage: {str(e)}")
        
        return metadata