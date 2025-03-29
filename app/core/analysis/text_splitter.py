"""
Textanalyse und Textverarbeitung für SciLit
-----------------------------------------
Funktionen zum Aufteilen von Texten in semantisch sinnvolle Chunks.
"""

import re
import logging
from typing import Dict, List, Optional, Any

import spacy
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import CHUNK_SIZE, CHUNK_OVERLAP, SPACY_MODEL_DE, SPACY_MODEL_EN

# Logger konfigurieren
logger = logging.getLogger("scilit.analysis.text_splitter")

class TextSplitter:
    """
    Klasse zum Aufteilen von Texten in semantisch sinnvolle Chunks für die Vektorisierung.
    
    Diese Klasse verwendet sowohl LangChain's RecursiveCharacterTextSplitter als auch
    spaCy für eine verbesserte Chunking-Qualität, die semantische und syntaktische
    Strukturen berücksichtigt.
    
    Attributes:
        nlp_de: SpaCy-Modell für deutsche Texte
        nlp_en: SpaCy-Modell für englische Texte
        text_splitter: LangChain-Textsplitter
    """
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        """
        Initialisiert den TextSplitter.
        
        Args:
            chunk_size: Maximale Größe eines Chunks
            chunk_overlap: Überlappung zwischen Chunks
        """
        # SpaCy Modelle werden verzögert geladen (Lazy Loading)
        self._nlp_de = None
        self._nlp_en = None
        
        # Textsplitter für Chunks erstellen
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        
        logger.debug(f"TextSplitter initialisiert mit chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    
    def _load_spacy_model(self, language: str):
        """
        Lädt das entsprechende SpaCy-Modell nach Bedarf.
        
        Args:
            language: Sprachcode ('de' oder 'en')
            
        Returns:
            Geladenes SpaCy-Modell
        """
        if language == "de" and self._nlp_de is None:
            try:
                logger.debug(f"Lade SpaCy-Modell '{SPACY_MODEL_DE}'")
                self._nlp_de = spacy.load(SPACY_MODEL_DE)
            except OSError:
                logger.warning(f"SpaCy-Modell '{SPACY_MODEL_DE}' nicht gefunden, wird heruntergeladen...")
                spacy.cli.download(SPACY_MODEL_DE)
                self._nlp_de = spacy.load(SPACY_MODEL_DE)
        elif language == "en" and self._nlp_en is None:
            try:
                logger.debug(f"Lade SpaCy-Modell '{SPACY_MODEL_EN}'")
                self._nlp_en = spacy.load(SPACY_MODEL_EN)
            except OSError:
                logger.warning(f"SpaCy-Modell '{SPACY_MODEL_EN}' nicht gefunden, wird heruntergeladen...")
                spacy.cli.download(SPACY_MODEL_EN)
                self._nlp_en = spacy.load(SPACY_MODEL_EN)
        
        return self._nlp_de if language == "de" else self._nlp_en
    
    def _detect_language(self, text: str) -> str:
        """
        Erkennt die Sprache eines Textes basierend auf häufigen Wörtern.
        
        Args:
            text: Der zu analysierende Text
            
        Returns:
            Sprachcode ('de' oder 'en')
        """
        # Eine einfache sprachunabhängige Erkennung basierend auf häufigen Wörtern
        text_sample = text[:1500].lower()
        
        # Zähle deutsche und englische häufige Wörter
        de_words = ["der", "die", "das", "und", "ist", "von", "für", "auf", "mit", "dem", "sich", "des", "ein", "nicht", "auch"]
        en_words = ["the", "and", "of", "to", "in", "is", "that", "for", "it", "as", "was", "with", "be", "by", "on"]
        
        de_count = sum(1 for word in de_words if f" {word} " in f" {text_sample} ")
        en_count = sum(1 for word in en_words if f" {word} " in f" {text_sample} ")
        
        return "de" if de_count > en_count else "en"
    
    def split_text_into_chunks(self, text: str, language: str = "auto") -> List[Dict[str, Any]]:
        """
        Teilt den Text in Chunks auf für die Vektorisierung.
        
        Diese Methode kombiniert LangChain's Textsplitter mit SpaCy-basierter
        Analyse, um qualitativ hochwertige Chunks mit zusätzlichen Metadaten
        wie Entitäten zu erstellen.
        
        Args:
            text: Der zu teilende Text
            language: Die Sprache des Textes ("de", "en", "auto")
            
        Returns:
            Liste von Chunks mit Text und Metadaten
        """
        logger.info(f"Teile Text in Chunks auf (Sprache: {language})")
        
        # Wenn Sprache "auto", versuche die Sprache zu erkennen
        if language == "auto" or language == "mixed":
            detected_lang = self._detect_language(text)
            logger.debug(f"Erkannte Sprache: {detected_lang}")
            language = detected_lang
        
        # NLP-Modell für die entsprechende Sprache laden
        nlp = self._load_spacy_model(language)
        
        # Chunks mit RecursiveCharacterTextSplitter erstellen
        raw_chunks = self.text_splitter.split_text(text)
        logger.debug(f"{len(raw_chunks)} Basis-Chunks erstellt")
        
        # Chunks mit Metadaten anreichern
        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            # Performance-Optimierung: Beschränke die SpaCy-Analyse auf die ersten 10000 Zeichen
            analysis_text = chunk_text[:10000]
            doc = nlp(analysis_text)
            
            # Wichtige Entitäten extrahieren
            entities = self._extract_entities(doc)
            
            # Keywords und wichtige Konzepte extrahieren
            keywords = self._extract_keywords(doc)
            
            # Chunk mit Metadaten erstellen
            chunk = {
                "chunk_id": i,
                "text": chunk_text,
                "entities": entities,
                "keywords": keywords,
                "language": language,
                "token_count": len(doc)
            }
            
            chunks.append(chunk)
        
        logger.info(f"Text in {len(chunks)} Chunks aufgeteilt")
        return chunks
    
    def _extract_entities(self, doc) -> Dict[str, List[str]]:
        """
        Extrahiert benannte Entitäten aus einem SpaCy-Dokument.
        
        Args:
            doc: SpaCy-Dokument
            
        Returns:
            Dictionary mit Entitätstypen als Schlüssel und Listen von Entitäten als Werte
        """
        entities = {}
        for ent in doc.ents:
            entity_type = ent.label_
            if entity_type not in entities:
                entities[entity_type] = []
            if ent.text not in entities[entity_type]:
                entities[entity_type].append(ent.text)
        
        return entities
    
    def _extract_keywords(self, doc) -> List[str]:
        """
        Extrahiert Keywords aus einem SpaCy-Dokument basierend auf POS-Tags.
        
        Args:
            doc: SpaCy-Dokument
            
        Returns:
            Liste der extrahierten Keywords
        """
        # Extrahiere Substantive, Eigennamen und Adjektive als potenzielle Keywords
        keywords = []
        for token in doc:
            if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 3:
                if token.text.lower() not in keywords:
                    keywords.append(token.text.lower())
            elif token.pos_ == "ADJ" and token.is_stop == False and len(token.text) > 3:
                if token.text.lower() not in keywords:
                    keywords.append(token.text.lower())
        
        # Beschränke auf die 20 wichtigsten Keywords
        return keywords[:20]
    
    def improve_chunk_quality(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Verbessert die Qualität der Chunks durch zusätzliche Analysen.
        
        Diese Methode kann nachträglich auf bereits erstellte Chunks angewendet werden,
        um ihre Qualität zu verbessern, z.B. durch bessere Chunk-Grenzen oder zusätzliche
        Metadaten.
        
        Args:
            chunks: Liste der Basis-Chunks
            
        Returns:
            Verbesserte Chunks mit zusätzlichen Metadaten
        """
        logger.info(f"Verbessere Qualität von {len(chunks)} Chunks")
        improved_chunks = []
        
        for chunk in chunks:
            # Sprache des Chunks bestimmen
            language = chunk.get("language", "en")
            
            # SpaCy-Modell für die Sprache laden
            nlp = self._load_spacy_model(language)
            
            # Begrenze die Textlänge für die Analyse 
            analysis_text = chunk["text"][:10000]
            doc = nlp(analysis_text)
            
            # Zusätzliche Features extrahieren
            summary = self._generate_summary(doc)
            sentiment = self._analyze_sentiment(doc)
            
            # Verbessertes Chunk erstellen
            improved_chunk = chunk.copy()
            improved_chunk.update({
                "summary": summary,
                "sentiment": sentiment,
                "improved": True
            })
            
            improved_chunks.append(improved_chunk)
        
        return improved_chunks
    
    def _generate_summary(self, doc) -> str:
        """
        Generiert eine kurze Zusammenfassung eines SpaCy-Dokuments.
        
        Diese einfache Implementierung extrahiert die wichtigsten Sätze basierend auf
        Position und Entitäten.
        
        Args:
            doc: SpaCy-Dokument
            
        Returns:
            Kurze Zusammenfassung des Textes
        """
        # Einfache Extraktion der wichtigsten Sätze
        if len(doc.sents) == 0:
            return ""
        
        # Nehme den ersten Satz als Schlüsselsatz an
        first_sent = next(doc.sents)
        summary = first_sent.text
        
        # Falls verfügbar, füge einen weiteren wichtigen Satz hinzu
        entity_rich_sents = []
        for sent in doc.sents:
            if sent != first_sent:  # Ersten Satz nicht doppelt
                entity_count = sum(1 for _ in sent.ents)
                if entity_count > 0:
                    entity_rich_sents.append((entity_count, sent.text))
        
        # Füge den Satz mit den meisten Entitäten hinzu, falls vorhanden
        if entity_rich_sents:
            entity_rich_sents.sort(reverse=True)
            if len(summary) + len(entity_rich_sents[0][1]) <= 280:  # Begrenze Zusammenfassung
                summary += " " + entity_rich_sents[0][1]
        
        return summary
    
    def _analyze_sentiment(self, doc) -> Dict[str, float]:
        """
        Führt eine einfache Stimmungsanalyse durch.
        
        Diese Methode nutzt einen regelbasierten Ansatz mit Lexika für Stimmungswörter.
        Für eine genauere Analyse könnte ein dediziertes Sentiment-Modell verwendet werden.
        
        Args:
            doc: SpaCy-Dokument
            
        Returns:
            Dictionary mit Stimmungswerten (positiv, negativ, neutral)
        """
        # Einfache lexikonbasierte Stimmungsanalyse
        # Echte Implementierung würde ein trainiertes Modell oder bessere Lexika verwenden
        positive_words = {"gut", "großartig", "exzellent", "hervorragend", "positiv", "vorteilhaft", 
                         "good", "great", "excellent", "outstanding", "positive", "beneficial"}
        negative_words = {"schlecht", "furchtbar", "schrecklich", "negativ", "nachteilig", "problematisch",
                         "bad", "terrible", "awful", "negative", "detrimental", "problematic"}
        
        positive_score = 0
        negative_score = 0
        total_words = 0
        
        for token in doc:
            if not token.is_punct and not token.is_stop:
                total_words += 1
                if token.lemma_.lower() in positive_words:
                    positive_score += 1
                elif token.lemma_.lower() in negative_words:
                    negative_score += 1
        
        # Vermeide Division durch Null
        if total_words == 0:
            return {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
        
        positive_ratio = positive_score / total_words
        negative_ratio = negative_score / total_words
        neutral_ratio = 1 - (positive_ratio + negative_ratio)
        
        return {
            "positive": round(positive_ratio, 3),
            "negative": round(negative_ratio, 3),
            "neutral": round(neutral_ratio, 3)
        }
    
    def create_improved_chunks(self, text: str, language: str = "auto") -> List[Dict[str, Any]]:
        """
        Kompatibilitätsmethode, die split_text_into_chunks aufruft und verbesserte Chunks zurückgibt.
        
        Dies dient der Konsistenz mit älteren Versionen der Codebase.
        
        Args:
            text: Der zu teilende Text
            language: Die Sprache des Textes
                
        Returns:
            Liste von verbesserten Chunks mit Text und Metadaten
        """
        # Erstelle Basis-Chunks
        chunks = self.split_text_into_chunks(text, language)
        
        # Verbessere die Qualität der Chunks durch zusätzliche Analysen
        return self.improve_chunk_quality(chunks)