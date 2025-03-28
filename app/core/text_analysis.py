"""
Textanalyse und Textverarbeitung für SciLit
-----------------------------------------
Funktionen zur Analyse und Verarbeitung von Texten.
"""

import re
import logging
from typing import Dict, List, Optional, Any

import spacy
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Logger konfigurieren
logger = logging.getLogger("scilit.text_analysis")

# Konfigurieren der Modelle
SPACY_MODEL_DE = "de_core_news_sm"
SPACY_MODEL_EN = "en_core_web_sm"

class TextAnalyzer:
    """Klasse für verschiedene Textanalyse-Aufgaben."""
    
    def __init__(self):
        """Initialisiert den TextAnalyzer."""
        # SpaCy Modelle laden (verzögert, um nicht unnötig Speicher zu belegen)
        self._nlp_de = None
        self._nlp_en = None
        
        # Textsplitter für Chunks erstellen
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
    
    def _load_spacy_model(self, language: str):
        """Lädt das entsprechende SpaCy-Modell nach Bedarf."""
        if language == "de" and self._nlp_de is None:
            try:
                self._nlp_de = spacy.load(SPACY_MODEL_DE)
                logger.info(f"SpaCy Modell '{SPACY_MODEL_DE}' geladen")
            except OSError:
                logger.warning(f"SpaCy Modell '{SPACY_MODEL_DE}' nicht gefunden, wird heruntergeladen...")
                spacy.cli.download(SPACY_MODEL_DE)
                self._nlp_de = spacy.load(SPACY_MODEL_DE)
        elif language == "en" and self._nlp_en is None:
            try:
                self._nlp_en = spacy.load(SPACY_MODEL_EN)
                logger.info(f"SpaCy Modell '{SPACY_MODEL_EN}' geladen")
            except OSError:
                logger.warning(f"SpaCy Modell '{SPACY_MODEL_EN}' nicht gefunden, wird heruntergeladen...")
                spacy.cli.download(SPACY_MODEL_EN)
                self._nlp_en = spacy.load(SPACY_MODEL_EN)
        
        return self._nlp_de if language == "de" else self._nlp_en
    
    def split_text_into_chunks(self, text: str, language: str = "auto") -> List[Dict[str, Any]]:
        """
        Teilt den Text in Chunks auf für die Vektorisierung.
        
        Args:
            text: Der zu teilende Text
            language: Die Sprache des Textes ("de", "en", "auto")
            
        Returns:
            Liste von Chunks mit Text und Metadaten
        """
        # Wenn Sprache "auto", versuche die Sprache zu erkennen
        if language == "auto":
            language = self._detect_language(text)
        
        # NLP-Modell für die entsprechende Sprache laden
        nlp = self._load_spacy_model(language)
        
        # Chunks mit RecursiveCharacterTextSplitter erstellen
        raw_chunks = self.text_splitter.split_text(text)
        
        # Chunks mit Metadaten anreichern
        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            # Spacy-Verarbeitung für zusätzliche Metadaten (Entitäten, etc.)
            doc = nlp(chunk_text[:10000])  # Limit für Performance
            
            # Wichtige Entitäten extrahieren
            entities = {}
            for ent in doc.ents:
                entity_type = ent.label_
                if entity_type not in entities:
                    entities[entity_type] = []
                if ent.text not in entities[entity_type]:
                    entities[entity_type].append(ent.text)
            
            # Chunk mit Metadaten erstellen
            chunk = {
                "chunk_id": i,
                "text": chunk_text,
                "entities": entities,
                "language": language,
                "token_count": len(doc)
            }
            
            chunks.append(chunk)
        
        return chunks
    
    def _detect_language(self, text: str) -> str:
        """Erkennt die Sprache eines Textes (vereinfachte Version)."""
        # Eine einfache sprachunabhängige Erkennung basierend auf häufigen Wörtern
        text_sample = text[:1000].lower()
        
        # Zähle deutsche und englische häufige Wörter
        de_words = ["der", "die", "das", "und", "ist", "von", "für", "auf", "mit", "dem", "sich", "des", "ein", "nicht", "auch"]
        en_words = ["the", "and", "of", "to", "in", "is", "that", "for", "it", "as", "was", "with", "be", "by", "on"]
        
        de_count = sum(1 for word in de_words if f" {word} " in f" {text_sample} ")
        en_count = sum(1 for word in en_words if f" {word} " in f" {text_sample} ")
        
        return "de" if de_count > en_count else "en"