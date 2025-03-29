"""
PDF-Parser für SciLit - Verbesserte Version
-------------------
Parser für PDF-Dokumente mit Unterstützung für OCR und wissenschaftliche Artikel.
"""

import re
import logging
import tempfile
from typing import Dict, Tuple, Any, List, Optional
from pathlib import Path

# PDF-Verarbeitung
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# OCR mit Tesseract
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
except ImportError:
    pytesseract = None
    Image = None
    convert_from_path = None

from app.config import OCR_LANGUAGES
from app.core.document.parsers.base_parser import DocumentParser, DocumentParsingError

# Logger konfigurieren
logger = logging.getLogger("scilit.document.parsers.pdf")

class PDFParser(DocumentParser):
    """
    Parser für PDF-Dokumente.
    
    Dieser Parser extrahiert Text und Metadaten aus PDFs mit PyMuPDF (fitz).
    Bei Bedarf wird OCR angewendet, wenn der Text nicht direkt extrahierbar ist.
    Enthält verbesserte Erkennung für wissenschaftliche Artikel.
    
    Attributes:
        ocr_if_needed (bool): Ob OCR bei Bedarf angewendet werden soll
        ocr_language (str): Sprache für OCR
    """
    
    def __init__(self, ocr_if_needed: bool = True, ocr_language: str = "auto"):
        """
        Initialisiert den PDF-Parser.
        
        Args:
            ocr_if_needed: Ob OCR bei Bedarf angewendet werden soll
            ocr_language: Sprache für OCR ('de', 'en', 'auto', 'mixed')
        """
        super().__init__()
        self.ocr_if_needed = ocr_if_needed
        self.ocr_language = ocr_language
    
    def parse(self, filepath: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parst ein PDF-Dokument und extrahiert Text und Metadaten.
        
        Bei Textlayern im PDF wird der Text direkt extrahiert. Falls kein Text
        gefunden wird und OCR aktiviert ist, wird Texterkennung angewendet.
        Spezielle Behandlung für wissenschaftliche Artikel.
        
        Args:
            filepath: Pfad zum PDF
            
        Returns:
            Tuple aus (extrahierter Text, Dictionary mit Metadaten)
            
        Raises:
            DocumentParsingError: Bei Problemen mit dem Parsing
        """
        if not fitz:
            raise DocumentParsingError("PyMuPDF (fitz) ist nicht installiert")
        
        try:
            text = ""
            metadata = self._extract_basic_metadata(filepath)
            used_ocr = False
            
            # Öffne das PDF mit PyMuPDF
            with fitz.open(filepath) as pdf:
                self.page_count = len(pdf)
                metadata["page_count"] = self.page_count
                
                # PDF-Metadaten extrahieren
                pdf_metadata = pdf.metadata
                self._extract_pdf_metadata(pdf_metadata, metadata)
                
                # Extrahiere Text von jeder Seite
                text_content = []
                first_page_text = ""
                
                for page_num, page in enumerate(pdf):
                    page_text = page.get_text()
                    if page_text.strip():
                        text_content.append(page_text)
                        
                        # Speichere den Text der ersten Seite separat für spezialisierte Analyse
                        if page_num == 0:
                            first_page_text = page_text
                    
                    # Wenn minimaler Text (weniger als 100 Zeichen auf der 1. Seite), eventuell OCR benötigt
                    if page_num == 0 and len(page_text.strip()) < 100 and self.ocr_if_needed:
                        logger.info(f"Wenig Text auf Seite 1 gefunden, könnte gescanntes PDF sein")
                
                text = "\n\n".join(text_content)
                
                # Wenn wenig oder kein Text gefunden wurde und OCR aktiviert ist
                if len(text.strip()) < 100 and self.ocr_if_needed:
                    if pytesseract and Image and convert_from_path:
                        logger.info(f"Wenig Text im PDF gefunden, versuche OCR: {filepath}")
                        ocr_text = self._apply_ocr(filepath)
                        if ocr_text:
                            text = ocr_text
                            used_ocr = True
                            # OCR-Text der ersten Seite extrahieren für Metadaten
                            first_page_lines = ocr_text.split('\n')
                            first_page_text = '\n'.join(first_page_lines[:min(30, len(first_page_lines))])
                    else:
                        logger.warning("OCR-Bibliotheken fehlen. Installiere pytesseract, pillow und pdf2image.")
            
            # Bessere Metadatenextraktion für wissenschaftliche Artikel durchführen
            self._extract_scientific_metadata(first_page_text, metadata)
            
            # DOI aus gesamtem Text extrahieren (falls nicht in Metadaten gefunden)
            if "doi" not in metadata or not metadata["doi"]:
                doi = self._extract_doi_from_text(text)
                if doi:
                    logger.info(f"DOI im Text gefunden: {doi}")
                    metadata["doi"] = doi
            
            # Qualitätsprüfung für extrahierte Metadaten
            self._validate_and_clean_metadata(metadata)
            
            # Metadaten um OCR-Info ergänzen
            if used_ocr:
                metadata["ocr_applied"] = True
                metadata["ocr_language"] = self.ocr_language
            
            return self._clean_text(text), metadata
            
        except fitz.FileDataError as e:
            raise DocumentParsingError(f"Fehler beim Öffnen der PDF-Datei: {str(e)}")
        except Exception as e:
            raise DocumentParsingError(f"Allgemeiner Fehler beim PDF-Parsing: {str(e)}")
    
    def _extract_pdf_metadata(self, pdf_metadata: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """
        Extrahiert Metadaten aus dem PDF-Metadatenobjekt.
        
        Args:
            pdf_metadata: Metadaten aus dem PDF
            metadata: Ziel-Dictionary für extrahierte Metadaten
        """
        if not pdf_metadata:
            return
            
        # Titel aus PDF-Metadaten
        if "title" in pdf_metadata and pdf_metadata["title"]:
            title = pdf_metadata["title"].strip()
            # Ignoriere unerwünschte Titel wie "Full Terms & Conditions..."
            if not self._is_irrelevant_text(title):
                metadata["title"] = title
        
        # Autoren aus PDF-Metadaten
        if "author" in pdf_metadata and pdf_metadata["author"]:
            # Autoren können als Komma- oder Semikolon-separierte Liste kommen
            authors = re.split(r'[,;]\s*', pdf_metadata["author"])
            # Leere und unwichtige Einträge entfernen
            authors = [author.strip() for author in authors if author.strip() and not self._is_irrelevant_text(author.strip())]
            if authors:
                metadata["author"] = authors
        
        # Weitere Metadatenfelder
        if "subject" in pdf_metadata and pdf_metadata["subject"]:
            metadata["subject"] = pdf_metadata["subject"]
        
        if "keywords" in pdf_metadata and pdf_metadata["keywords"]:
            metadata["keywords"] = pdf_metadata["keywords"]
        
        if "creator" in pdf_metadata and pdf_metadata["creator"]:
            metadata["creator"] = pdf_metadata["creator"]
    
    def _extract_scientific_metadata(self, first_page_text: str, metadata: Dict[str, Any]) -> None:
        """
        Extrahiert Metadaten aus dem Text der ersten Seite mit Fokus auf wissenschaftliche Artikel.
        
        Args:
            first_page_text: Text der ersten Seite
            metadata: Ziel-Dictionary für extrahierte Metadaten
        """
        # Teile den Text in Zeilen auf
        lines = [line.strip() for line in first_page_text.split('\n') if line.strip()]
        
        if not lines:
            return
        
        # Ignoriere Header- und Footer-Zeilen
        filtered_lines = self._filter_header_footer_lines(lines)
        
        # Extrahiere Titel (oft der erste längere Text in der oberen Hälfte der Seite)
        title = self._extract_scientific_title(filtered_lines)
        if title and not self._is_irrelevant_text(title):
            if "title" not in metadata or not metadata["title"]:
                metadata["title"] = title
            elif len(title) > len(metadata["title"]) and not self._is_irrelevant_text(title):
                # Ersetze den Titel, wenn der neue länger und relevant ist
                metadata["title"] = title
        
        # Extrahiere Autoren (oft nach dem Titel, vor dem Abstract)
        authors = self._extract_scientific_authors(filtered_lines, title)
        if authors:
            if "author" not in metadata or not metadata["author"]:
                metadata["author"] = authors
        
        # Extrahiere DOI (oft am Anfang oder Ende der Seite)
        doi = self._extract_doi_from_text(first_page_text)
        if doi:
            metadata["doi"] = doi
        
        # Extrahiere Journal/Publisher
        journal = self._extract_journal_info(filtered_lines)
        if journal:
            metadata["journal"] = journal
        
        # Extrahiere Jahr
        year = self._extract_year(first_page_text)
        if year:
            metadata["year"] = year
    
    def _filter_header_footer_lines(self, lines: List[str]) -> List[str]:
        """
        Filtert Header- und Footer-Zeilen aus der Liste der Textzeilen.
        
        Args:
            lines: Liste von Textzeilen
            
        Returns:
            Gefilterte Liste ohne typische Header/Footer
        """
        if not lines:
            return []
        
        # Typische Ausschlussmuster für Header/Footer
        exclusion_patterns = [
            r'(?i)full terms',
            r'(?i)conditions of (access|use)',
            r'(?i)copyright',
            r'(?i)^page \d+',
            r'(?i)^issn',
            r'(?i)^doi:',
            r'^\d+$',  # Nur Seitennummern
            r'(?i)all rights reserved'
        ]
        
        # Zeilen filtern
        filtered_lines = []
        for line in lines:
            if not any(re.search(pattern, line) for pattern in exclusion_patterns):
                # Zeile ist kein typischer Header/Footer
                filtered_lines.append(line)
        
        return filtered_lines
    
    def _extract_scientific_title(self, lines: List[str]) -> Optional[str]:
        """
        Extrahiert den Titel eines wissenschaftlichen Artikels.
        
        Args:
            lines: Gefilterte Textzeilen
            
        Returns:
            Extrahierter Titel oder None
        """
        if not lines:
            return None
        
        # In wissenschaftlichen Artikeln ist der Titel oft:
        # 1. Eine der ersten längeren Zeilen
        # 2. Oft zentriert/hervorgehoben
        # 3. Keine Seitenzahl, keine Autor-Zeile
        
        # Ignoriere sehr kurze Zeilen am Anfang
        potential_titles = []
        
        for i, line in enumerate(lines[:10]):  # Beschränke auf die ersten 10 Zeilen
            # Ignoriere kurze Zeilen und typische Nicht-Titel
            if len(line) < 20:
                continue
                
            if re.search(r'(?i)(abstract|keywords|introduction|references)', line):
                continue
                
            if re.search(r'(?i)(university|department|faculty|school of)', line):
                continue
            
            # Potentieller Titel gefunden
            potential_titles.append((i, line))
        
        if not potential_titles:
            return None
        
        # Bevorzuge längere Zeilen unter den ersten Kandidaten
        potential_titles.sort(key=lambda x: len(x[1]), reverse=True)
        
        return potential_titles[0][1]
    
    def _extract_scientific_authors(self, lines: List[str], title: Optional[str]) -> List[str]:
        """
        Extrahiert Autorennamen aus den Textzeilen.
        
        Args:
            lines: Gefilterte Textzeilen
            title: Bereits erkannter Titel
            
        Returns:
            Liste der extrahierten Autoren
        """
        authors = []
        
        if not title or not lines:
            return authors
        
        # Finde die Position des Titels
        title_index = -1
        for i, line in enumerate(lines):
            if title in line:
                title_index = i
                break
        
        if title_index == -1 or title_index + 1 >= len(lines):
            return authors
        
        # Suche nach Autorennamen nach dem Titel
        # Typische Autorenmuster in wissenschaftlichen Artikeln:
        # 1. Name(n) auf einer Zeile, oft in gemischter Groß-/Kleinschreibung
        # 2. Manchmal mit akademischen Titeln/Abschlüssen
        # 3. Manchmal mit Fußnoten/Nummern für Affiliationen
        
        # Muster für typische Autorennamen
        author_patterns = [
            r'^([A-Z][a-z]+\s+[A-Z][a-z]+)$',  # Einfacher Name: "John Smith"
            r'^([A-Z][A-Z\s]+)$',  # Nur Großbuchstaben: "JOHN SMITH"
            r'^([A-Z][a-z]+(?:\s+[A-Z]\.?)+\s+[A-Z][a-z]+)$',  # Mit Initialen: "John A. Smith"
            r'^([A-Z][a-z]+(?:-[A-Z][a-z]+)?\s+[A-Z][a-z]+)$',  # Mit Bindestrich: "Jean-Pierre Dupont"
        ]
        
        # Suche nach Autorenzeilen
        for i in range(title_index + 1, min(title_index + 10, len(lines))):
            line = lines[i].strip()
            
            # Ignoriere kurze Zeilen und typische Nicht-Autorennamen
            if len(line) < 3 or len(line) > 100:
                continue
                
            # Prüfe auf typische Autorenmuster
            is_author_line = False
            for pattern in author_patterns:
                if re.search(pattern, line):
                    is_author_line = True
                    break
            
            # Prüfe auch auf typische akademische Titel/Keywords
            if not is_author_line and re.search(r'(?i)(professor|dr\.|ph\.?d|department|university)', line):
                # Ignoriere Zeilen, die nur Institutionen/Affiliationen enthalten
                if not re.search(r'(?i)^(department|school|faculty|university)', line):
                    is_author_line = True
            
            if is_author_line and not self._is_irrelevant_text(line):
                authors.append(line)
        
        # Alternative: Extrahiere Namen mit typischen Formaten, falls keine Autoren gefunden wurden
        if not authors:
            # Suche nach typischen Namensformaten im gesamten ersten Teil des Dokuments
            all_text = " ".join(lines[:min(30, len(lines))])
            name_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+)', all_text)
            
            if name_matches:
                # Filtere Duplikate und irrelevante Texte
                authors = list(set(name for name in name_matches if not self._is_irrelevant_text(name)))
        
        return authors
    
    def _extract_journal_info(self, lines: List[str]) -> Optional[str]:
        """
        Extrahiert Journal/Publisher-Informationen.
        
        Args:
            lines: Gefilterte Textzeilen
            
        Returns:
            Journal-/Publisher-Name oder None
        """
        if not lines:
            return None
        
        # Typische Journal-Muster
        journal_patterns = [
            r'(?i)journal of ([^,\.]+)',
            r'(?i)([^,\.]+) journal',
            r'(?i)transactions on ([^,\.]+)',
            r'(?i)proceedings of ([^,\.]+)'
        ]
        
        # Durchsuche die ersten Zeilen nach Journal-Informationen
        for line in lines[:10]:
            for pattern in journal_patterns:
                match = re.search(pattern, line)
                if match:
                    return match.group(0).strip()
        
        return None
    
    def _extract_year(self, text: str) -> Optional[int]:
        """
        Extrahiert eine Jahreszahl aus dem Text.
        
        Args:
            text: Zu durchsuchender Text
            
        Returns:
            Extrahierte Jahreszahl oder None
        """
        # Suche nach Jahreszahlen zwischen 1900 und aktuellem Jahr
        year_matches = re.findall(r'(?<!\d)((19|20)\d{2})(?!\d)', text)
        if year_matches:
            # Versuche, die relevanteste Jahreszahl zu finden
            years = [int(year[0]) for year in year_matches]
            # Bevorzuge Jahre zwischen 1990 und 2030
            filtered_years = [year for year in years if 1990 <= year <= 2030]
            if filtered_years:
                # Nehme das neueste Jahr an (typisch für Publikationsdatum)
                return max(filtered_years)
            return years[0]  # Falls kein Jahr im Bereich, nimm das erste
        
        return None
    
    def _extract_doi_from_text(self, text: str) -> Optional[str]:
        """
        Extrahiert eine DOI aus dem Text.
        
        Args:
            text: Zu durchsuchender Text
            
        Returns:
            Extrahierte DOI oder None
        """
        # Verbesserte DOI-Muster
        doi_patterns = [
            r'(?i)DOI:\s*(10\.\d{4,}(?:[.][0-9]+)*/(?:(?!["&\'<>])\S)+)',
            r'(?i)https?://doi\.org/(10\.\d{4,}(?:[.][0-9]+)*/(?:(?!["&\'<>])\S)+)',
            r'(?i)doi\.org/(10\.\d{4,}(?:[.][0-9]+)*/(?:(?!["&\'<>])\S)+)',
            r'(?i)DOI\s+(10\.\d{4,}(?:[.][0-9]+)*/(?:(?!["&\'<>])\S)+)',
            r'(?i)(10\.\d{4,}(?:[.][0-9]+)*/(?:(?!["&\'<>])\S)+)'
        ]
        
        for pattern in doi_patterns:
            match = re.search(pattern, text)
            if match:
                # Bereinige die DOI
                doi = match.group(1).strip()
                # Entferne Satzzeichen am Ende
                doi = re.sub(r'[,;.\s]+$', '', doi)
                return doi
        
        return None
    
    def _is_irrelevant_text(self, text: str) -> bool:
        """
        Prüft, ob ein Text irrelevant ist (z.B. Copyright-Hinweise, Terms & Conditions).
        
        Args:
            text: Zu prüfender Text
            
        Returns:
            True, wenn der Text irrelevant ist, sonst False
        """
        # Muster für irrelevante Texte
        irrelevant_patterns = [
            r'(?i)full terms',
            r'(?i)conditions of (access|use)',
            r'(?i)copyright',
            r'(?i)all rights reserved',
            r'(?i)Taylor & Francis',
            r'(?i)elsevier',
            r'(?i)springer',
            r'(?i)john wiley',
            r'(?i)https?://',
            r'(?i)terms and conditions'
        ]
        
        return any(re.search(pattern, text) for pattern in irrelevant_patterns)
    
    def _validate_and_clean_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Validiert und bereinigt die extrahierten Metadaten.
        
        Args:
            metadata: Zu prüfende und bereinigende Metadaten
        """
        # Bereinige den Titel
        if "title" in metadata and metadata["title"]:
            title = metadata["title"]
            # Entferne Zeilenumbrüche und überschüssige Leerzeichen
            title = re.sub(r'\s+', ' ', title).strip()
            # Kürze extrem lange Titel
            if len(title) > 300:
                title = title[:300] + "..."
            metadata["title"] = title
        
        # Bereinige Autorenliste
        if "author" in metadata and metadata["author"]:
            if isinstance(metadata["author"], list):
                # Entferne zu kurze oder zu lange Namen sowie irrelevante Texte
                authors = [author for author in metadata["author"] 
                          if isinstance(author, str) and 3 <= len(author) <= 100
                          and not self._is_irrelevant_text(author)]
                metadata["author"] = authors if authors else metadata["author"]
            else:
                # Wenn author kein List ist, konvertiere es zu einer Liste
                metadata["author"] = [metadata["author"]]
    
    def _apply_ocr(self, filepath: str) -> str:
        """
        Wendet OCR auf ein PDF an.
        
        Args:
            filepath: Pfad zur PDF-Datei
            
        Returns:
            Extrahierter Text oder leerer String bei Fehler
        """
        try:
            # OCR-Sprache basierend auf der Konfiguration bestimmen
            ocr_lang = OCR_LANGUAGES.get(self.ocr_language, "eng+deu")
            
            # Temporäres Verzeichnis für Bilder
            with tempfile.TemporaryDirectory() as temp_dir:
                # PDF zu Bildern konvertieren
                logger.info(f"Konvertiere PDF zu Bildern für OCR")
                images = convert_from_path(filepath, output_folder=temp_dir)
                
                ocr_texts = []
                
                # OCR auf jedes Bild anwenden
                for i, image in enumerate(images):
                    logger.debug(f"OCR für Seite {i+1} von {len(images)}")
                    ocr_text = pytesseract.image_to_string(image, lang=ocr_lang)
                    ocr_texts.append(ocr_text)
                
                return "\n\n".join(ocr_texts)
                
        except Exception as e:
            logger.error(f"Fehler bei OCR: {str(e)}")
            return ""