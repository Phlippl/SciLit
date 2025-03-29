"""
K10plus API Client für SciLit
---------------------------
Client für den K10plus-Katalog zur Abfrage von Literaturmetadaten im deutschsprachigen Raum.
"""

import re
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher

from app.api.base_client import BaseAPIClient
from app.core.metadata.extractor import string_similarity
from app.config import K10PLUS_API_URL

# Logger konfigurieren
logger = logging.getLogger("scilit.api.k10plus")

class K10plusClient(BaseAPIClient):
    """
    Client für den K10plus-Katalog.
    
    K10plus ist der größte Bibliothekskatalog im deutschsprachigen Raum.
    Diese Implementierung nutzt die SRU-Schnittstelle (Search/Retrieve via URL).
    
    Attributes:
        api_url (str): Basis-URL für die K10plus API (SRU)
    """
    
    def __init__(self):
        """Initialisiert den K10plus API Client."""
        super().__init__(name="k10plus")
        self.api_url = K10PLUS_API_URL
    
    def enhance_metadata(self, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erweitert die grundlegenden Metadaten mit Daten aus dem K10plus-Katalog.
        
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
        
        logger.info(f"Erweitere Metadaten mit K10plus: Titel='{title}', Autoren={authors}, ISBN={isbn}")
        
        # Metadaten aus K10plus abrufen
        k10plus_metadata = self.fetch_metadata(title, authors, isbn)
        if not k10plus_metadata:
            logger.debug("Keine Metadaten von K10plus gefunden")
            return basic_metadata
        
        # Bewertung der gefundenen Metadaten
        score = self._score_metadata(k10plus_metadata, title, authors)
        logger.info(f"K10plus-Metadaten gefunden mit Score {score:.2f}")
        
        # Bei hohem Score die Metadaten vollständig übernehmen
        if score > 70:
            logger.debug("Hoher Score: Übernehme alle K10plus-Metadaten")
            enhanced_metadata = basic_metadata.copy()
            for key, value in k10plus_metadata.items():
                if value:  # Leere Werte nicht übernehmen
                    enhanced_metadata[key] = value
            return enhanced_metadata
        
        # Bei niedrigem Score nur ausgewählte Felder übernehmen
        logger.debug("Niedriger Score: Übernehme nur ausgewählte K10plus-Metadaten")
        for key in ['publisher', 'isbn', 'year', 'page_count', 'language']:
            if key in k10plus_metadata and k10plus_metadata[key]:
                basic_metadata[key] = k10plus_metadata[key]
        
        return basic_metadata
    
    def fetch_metadata(self, title: str = None, authors: List[str] = None, isbn: str = None) -> Dict[str, Any]:
        """
        Ruft Metadaten vom K10plus-Katalog ab, entweder über ISBN oder Titel/Autoren.
        
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
        Sucht direkt nach einer ISBN im K10plus-Katalog.
        
        Args:
            isbn: Die ISBN der Publikation
            
        Returns:
            Metadaten oder leeres Dictionary bei Fehler
        """
        cache_key = self._create_cache_key("isbn", isbn)
        
        def fetch_func():
            # CQL-Query für ISBN-Suche
            query = f"NUM=ISBN {isbn}"
            url = f"{self.api_url}?version=1.1&operation=searchRetrieve&query={urllib.parse.quote(query)}&maximumRecords=1&recordSchema=marcxml"
            
            try:
                response = self._make_request("get", url, timeout=15)  # Längeres Timeout für SRU
                
                if response.status_code == 200:
                    # MARCXML parsen
                    try:
                        root = ET.fromstring(response.text)
                        num_records = root.find(".//{http://www.loc.gov/zing/srw/}numberOfRecords")
                        
                        if num_records is not None and int(num_records.text) > 0:
                            # Erstes Record extrahieren
                            record = root.find(".//{http://www.loc.gov/MARC21/slim}record")
                            if record is not None:
                                return self._parse_k10plus_record(record)
                    except ET.ParseError as e:
                        logger.warning(f"Fehler beim Parsen der K10plus XML-Antwort: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Fehler bei K10plus ISBN-Anfrage: {str(e)}")
            
            return {}
        
        return self._get_cached_or_fetch(cache_key, fetch_func)
    
    def _fetch_by_query(self, title: str = None, authors: List[str] = None) -> Dict[str, Any]:
        """
        Sucht nach Publikationen basierend auf Titel und/oder Autoren im K10plus-Katalog.
        
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
            # CQL-Anfrage erstellen
            query_parts = []
            
            if title:
                # Bereinigter Titel für die Suche
                clean_title = re.sub(r'[^\w\s]', ' ', title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                query_parts.append(f'pica.tit="{urllib.parse.quote(clean_title)}"')
            
            if authors and len(authors) > 0:
                # Verwende den ersten Autor für die Suche
                first_author = authors[0]
                name_parts = first_author.split()
                if len(name_parts) > 1:
                    query_parts.append(f'pica.per="{urllib.parse.quote(name_parts[-1])}"')  # Nachname
                else:
                    query_parts.append(f'pica.per="{urllib.parse.quote(first_author)}"')
            
            query = " and ".join(query_parts)
            url = f"{self.api_url}?version=1.1&operation=searchRetrieve&query={urllib.parse.quote(query)}&maximumRecords=5&recordSchema=marcxml"
            
            try:
                response = self._make_request("get", url, timeout=15)  # Längeres Timeout für SRU
                
                if response.status_code == 200:
                    try:
                        root = ET.fromstring(response.text)
                        num_records = root.find(".//{http://www.loc.gov/zing/srw/}numberOfRecords")
                        
                        if num_records is not None and int(num_records.text) > 0:
                            # Records durchgehen und bestes auswählen
                            records = root.findall(".//{http://www.loc.gov/MARC21/slim}record")
                            
                            best_record = None
                            best_score = -1
                            
                            for record in records[:5]:
                                temp_metadata = self._parse_k10plus_record(record)
                                score = self._score_metadata(temp_metadata, title, authors)
                                if score > best_score:
                                    best_score = score
                                    best_record = record
                            
                            # Wenn ein gutes Ergebnis gefunden wurde
                            if best_record is not None and best_score > 10:
                                logger.debug(f"K10plus-Ergebnis mit Score {best_score} gefunden")
                                return self._parse_k10plus_record(best_record)
                    except ET.ParseError as e:
                        logger.warning(f"Fehler beim Parsen der K10plus XML-Antwort: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Fehler bei K10plus-Suche: {str(e)}")
            
            return {}
        
        return self._get_cached_or_fetch(cache_key, fetch_func)
    
    def _parse_k10plus_record(self, record: ET.Element) -> Dict[str, Any]:
        """
        Extrahiert Metadaten aus einem K10plus MARCXML-Record.
        
        Args:
            record: MARCXML-Record-Element
            
        Returns:
            Extrahierte Metadaten
        """
        metadata = {}
        
        # Namespace für MARC-Elemente
        ns = {'marc': 'http://www.loc.gov/MARC21/slim'}
        
        # Titel extrahieren (Feld 245, Unterfelder a, b)
        title_parts = []
        
        title_field = record.find('.//marc:datafield[@tag="245"]', ns)
        if title_field is not None:
            for subfield in title_field.findall('.//marc:subfield[@code="a" or @code="b"]', ns):
                if subfield.text:
                    title_parts.append(subfield.text.strip())
        
        if title_parts:
            metadata['title'] = ' '.join(title_parts)
        
        # Autoren extrahieren (Felder 100, 700)
        authors = []
        
        main_author = record.find('.//marc:datafield[@tag="100"]', ns)
        if main_author is not None:
            name_part = main_author.find('.//marc:subfield[@code="a"]', ns)
            if name_part is not None and name_part.text:
                author_name = name_part.text.strip()
                author_name = re.sub(r', \d{4}-\d{4}$', '', author_name)  # Lebensdaten entfernen
                authors.append(author_name)
        
        add_authors = record.findall('.//marc:datafield[@tag="700"]', ns)
        for add_author in add_authors:
            name_part = add_author.find('.//marc:subfield[@code="a"]', ns)
            if name_part is not None and name_part.text:
                author_name = name_part.text.strip()
                author_name = re.sub(r', \d{4}-\d{4}$', '', author_name)  # Lebensdaten entfernen
                authors.append(author_name)
        
        if authors:
            metadata['author'] = authors
        
        # Erscheinungsjahr (Feld 008, Positionen 7-10 oder Feld 264, Unterfeld c)
        year = None
        
        control_field = record.find('.//marc:controlfield[@tag="008"]', ns)
        if control_field is not None and control_field.text:
            year_str = control_field.text[7:11]
            if year_str.isdigit():
                year = int(year_str)
        
        if not year:
            publ_field = record.find('.//marc:datafield[@tag="264"]', ns)
            if publ_field is not None:
                year_part = publ_field.find('.//marc:subfield[@code="c"]', ns)
                if year_part is not None and year_part.text:
                    year_match = re.search(r'\d{4}', year_part.text)
                    if year_match:
                        year = int(year_match.group(0))
        
        if year:
            metadata['year'] = year
        
        # Verlag (Feld 264, Unterfeld b)
        publisher_field = record.find('.//marc:datafield[@tag="264"]', ns)
        if publisher_field is not None:
            publisher_part = publisher_field.find('.//marc:subfield[@code="b"]', ns)
            if publisher_part is not None and publisher_part.text:
                metadata['publisher'] = publisher_part.text.strip().rstrip(':,.')
        
        # ISBN (Feld 020, Unterfeld a)
        isbn_fields = record.findall('.//marc:datafield[@tag="020"]', ns)
        for isbn_field in isbn_fields:
            isbn_part = isbn_field.find('.//marc:subfield[@code="a"]', ns)
            if isbn_part is not None and isbn_part.text:
                # ISBN extraieren (nur Ziffern und X)
                isbn_match = re.search(r'[\dX]{10,13}', isbn_part.text)
                if isbn_match:
                    metadata['isbn'] = isbn_match.group(0)
                    break
        
        # Seitenzahl (Feld 300, Unterfeld a)
        extent_field = record.find('.//marc:datafield[@tag="300"]', ns)
        if extent_field is not None:
            extent_part = extent_field.find('.//marc:subfield[@code="a"]', ns)
            if extent_part is not None and extent_part.text:
                pages_match = re.search(r'(\d+) Seiten|(\d+) S\.|(\d+) pages|(\d+) p\.', extent_part.text)
                if pages_match:
                    # Nehme den ersten nicht-None-Match
                    for group in pages_match.groups():
                        if group:
                            metadata['page_count'] = int(group)
                            break
        
        # Sprache (Feld 008, Positionen 35-37)
        if control_field is not None and control_field.text and len(control_field.text) >= 38:
            lang_code = control_field.text[35:38]
            if lang_code == 'ger':
                metadata['language'] = 'de'
            elif lang_code == 'eng':
                metadata['language'] = 'en'
            else:
                metadata['language'] = lang_code
        
        # Schlagwörter / Themen (Feld 650, Unterfeld a)
        subjects = []
        subject_fields = record.findall('.//marc:datafield[@tag="650"]', ns)
        for subject_field in subject_fields:
            subject_part = subject_field.find('.//marc:subfield[@code="a"]', ns)
            if subject_part is not None and subject_part.text:
                subjects.append(subject_part.text.strip())
        
        if subjects:
            metadata['keywords'] = subjects[:5]  # Maximal 5 Schlagwörter
        
        return metadata
    
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
        if 'language' in metadata and metadata['language']:
            bonus_score += 5
        
        score += bonus_score
        logger.debug(f"Bonus-Score für zusätzliche Metadaten: {bonus_score}")
        
        return score