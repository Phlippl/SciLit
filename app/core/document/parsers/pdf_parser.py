"""
PDF-Parser für SciLit
-------------------
Parser für PDF-Dokumente mit Unterstützung für OCR.
"""

import re
import logging
import tempfile
from typing import Dict, Tuple, Any

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
                if pdf_metadata:
                    if "title" in pdf_metadata and pdf_metadata["title"]:
                        metadata["title"] = pdf_metadata["title"]
                    if "author" in pdf_metadata and pdf_metadata["author"]:
                        # Autoren können als Komma- oder Semikolon-separierte Liste kommen
                        authors = re.split(r'[,;]\s*', pdf_metadata["author"])
                        metadata["author"] = [author.strip() for author in authors if author.strip()]
                    if "subject" in pdf_metadata and pdf_metadata["subject"]:
                        metadata["subject"] = pdf_metadata["subject"]
                    if "keywords" in pdf_metadata and pdf_metadata["keywords"]:
                        metadata["keywords"] = pdf_metadata["keywords"]
                    if "creator" in pdf_metadata and pdf_metadata["creator"]:
                        metadata["creator"] = pdf_metadata["creator"]
                
                # Extrahiere Text von jeder Seite
                text_content = []
                
                for page_num, page in enumerate(pdf):
                    page_text = page.get_text()
                    if page_text.strip():
                        text_content.append(page_text)
                    
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
                    else:
                        logger.warning("OCR-Bibliotheken fehlen. Installiere pytesseract, pillow und pdf2image.")
            
            # Metadaten um OCR-Info ergänzen
            if used_ocr:
                metadata["ocr_applied"] = True
                metadata["ocr_language"] = self.ocr_language
            
            return self._clean_text(text), metadata
            
        except fitz.FileDataError as e:
            raise DocumentParsingError(f"Fehler beim Öffnen der PDF-Datei: {str(e)}")
        except Exception as e:
            raise DocumentParsingError(f"Allgemeiner Fehler beim PDF-Parsing: {str(e)}")
    
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