# Überarbeitung der app/services/search_service.py

"""
Such-Service für SciLit
---------------------
Bietet Funktionen für die Suche in verarbeiteten Dokumenten und die 
Generierung von Antworten auf Fragen.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from app.core.document.manager import get_document_manager
from app.core.llm.ollama_client import get_ollama_client
from app.core.metadata.formatter import format_citation

# Logger konfigurieren
logger = logging.getLogger("scilit.services.search")

class SearchService:
    """
    Service für Such- und Frage-Antwort-Funktionalitäten.
    
    Diese Klasse bietet Methoden für semantische Stichwortsuche, Stichwortsuche und
    Frage-Antwort auf Basis der gespeicherten Dokumente.
    
    Attributes:
        document_manager: Manager für Zugriff auf verarbeitete Dokumente
        ollama_client: Client für Interaktion mit dem LLM
    """
    
    def __init__(self):
        """Initialisiert den SearchService."""
        self.document_manager = get_document_manager()
        self.ollama_client = get_ollama_client()
        logger.debug("SearchService initialisiert")
    
    def semantic_search(self, query: str, filters: Dict[str, Any] = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Führt eine semantische Suche nach Chunks durch, die der Anfrage ähnlich sind.
        
        Args:
            query: Die Suchanfrage
            filters: Optionale Filter (Autor, Jahr, Dokument, etc.)
            max_results: Maximale Anzahl der Ergebnisse
            
        Returns:
            Liste von relevanten Chunks mit Metadaten
        """
        # TODO: Implementierung mit Vektorisierung und Ähnlichkeitssuche
        # Für die erste Version: Einfache Keyword-Suche durchführen
        return self.keyword_search(query, filters, max_results)
    
    def keyword_search(self, query: str, filters: Dict[str, Any] = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Führt eine einfache Stichwortsuche durch.
        
        Args:
            query: Die Suchanfrage (Stichwörter)
            filters: Optionale Filter (Autor, Jahr, Dokument, etc.)
            max_results: Maximale Anzahl der Ergebnisse
            
        Returns:
            Liste von relevanten Chunks mit Metadaten
        """
        results = []
        query_terms = query.lower().split()
        
        # Alle Dokumente durchgehen
        documents = self.document_manager.get_all_documents()
        
        for doc in documents:
            # Prüfen, ob das Dokument den Filtern entspricht
            if not self._document_matches_filters(doc, filters):
                continue
            
            # Chunks des Dokuments abrufen
            doc_id = doc["id"]
            chunks = self.document_manager.get_document_chunks(doc_id)
            metadata = self.document_manager.get_document_metadata(doc_id)
            
            # Jeden Chunk prüfen
            for chunk in chunks:
                text = chunk.get("text", "").lower()
                
                # Einfache Relevanzberechnung: Anzahl der Vorkommen der Suchbegriffe
                relevance = sum(term in text for term in query_terms) / len(query_terms)
                
                if relevance > 0:
                    result = {
                        "text": chunk["text"],
                        "chunk_id": chunk.get("chunk_id", 0),
                        "document_id": doc_id,
                        "relevance": relevance,
                        "source": self._format_source(metadata),
                        "metadata": metadata
                    }
                    results.append(result)
        
        # Nach Relevanz sortieren und begrenzen
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:max_results]
    
    def answer_question(self, 
                        question: str, 
                        filters: Dict[str, Any] = None,
                        citation_style: str = "apa",
                        max_context_chunks: int = 5) -> Dict[str, Any]:
        """
        Beantwortet eine Frage basierend auf den verfügbaren Dokumenten.
        
        Args:
            question: Die zu beantwortende Frage
            filters: Optionale Filter für die Suche
            citation_style: Zitationsstil für das Literaturverzeichnis
            max_context_chunks: Maximale Anzahl der Kontextausschnitte
            
        Returns:
            Dict mit Antwort, Quellen und weiteren Informationen
        """
        # 1. Relevante Chunks finden
        relevant_chunks = self.semantic_search(question, filters, max_context_chunks)
        
        if not relevant_chunks:
            return {
                "answer": "Ich konnte keine relevanten Informationen zu deiner Frage in deiner Literatursammlung finden.",
                "sources": [],
                "chunks": []
            }
        
        # 2. Kontext für das LLM vorbereiten
        context = []
        used_document_ids = set()
        
        for chunk in relevant_chunks:
            doc_id = chunk["document_id"]
            metadata = self.document_manager.get_document_metadata(doc_id)
            
            context_item = {
                "text": chunk["text"],
                "author": metadata.get("author", ["Unbekannt"]),
                "year": metadata.get("year", "n.d."),
                "title": metadata.get("title", "Unbekanntes Dokument"),
                "page": chunk.get("page", ""),
                "chunk_id": chunk.get("chunk_id", 0),
                "document_id": doc_id
            }
            context.append(context_item)
            used_document_ids.add(doc_id)
        
        # 3. Antwort vom LLM generieren
        answer = self.ollama_client.generate_response(question, context)
        
        # 4. Literaturverzeichnis erstellen
        sources = []
        for doc_id in used_document_ids:
            metadata = self.document_manager.get_document_metadata(doc_id)
            citation = format_citation(metadata, citation_style)
            if citation:
                sources.append({
                    "document_id": doc_id,
                    "citation": citation,
                    "metadata": metadata
                })
        
        # 5. Ergebnis zurückgeben
        return {
            "answer": answer,
            "sources": sources,
            "chunks": relevant_chunks
        }
    
    def _document_matches_filters(self, document: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
        """
        Prüft, ob ein Dokument den angegebenen Filtern entspricht.
        
        Args:
            document: Das zu prüfende Dokument
            filters: Die anzuwendenden Filter oder None
            
        Returns:
            True, wenn das Dokument den Filtern entspricht, sonst False
        """
        if not filters:
            return True
        
        metadata = document.get("metadata", {})
        
        # Filter nach Autor
        if "author" in filters and filters["author"]:
            if "author" not in metadata:
                return False
            
            author_filter = filters["author"].lower()
            if isinstance(metadata["author"], list):
                if not any(author_filter in author.lower() for author in metadata["author"]):
                    return False
            elif isinstance(metadata["author"], str):
                if author_filter not in metadata["author"].lower():
                    return False
        
        # Filter nach Jahr
        if "year_min" in filters and filters["year_min"]:
            if "year" not in metadata or not metadata["year"]:
                return False
            if int(metadata["year"]) < int(filters["year_min"]):
                return False
        
        if "year_max" in filters and filters["year_max"]:
            if "year" not in metadata or not metadata["year"]:
                return False
            if int(metadata["year"]) > int(filters["year_max"]):
                return False
        
        # Filter nach Quelle/Journal
        if "source" in filters and filters["source"]:
            source_filter = filters["source"].lower()
            
            # Suche in Journal, Publisher oder anderen Quellenfeldern
            source_fields = ["journal", "publisher", "source"]
            found = False
            
            for field in source_fields:
                if field in metadata and metadata[field]:
                    if source_filter in str(metadata[field]).lower():
                        found = True
                        break
            
            if not found:
                return False
        
        # Filter nach Dokument-ID
        if "document_id" in filters and filters["document_id"]:
            if document.get("id") != filters["document_id"]:
                return False
        
        return True
    
    def _format_source(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert eine Quellenangabe für die Anzeige in den Suchergebnissen.
        
        Args:
            metadata: Metadaten des Dokuments
            
        Returns:
            Formatierte Quellenangabe
        """
        parts = []
        
        # Autor(en)
        if "author" in metadata and metadata["author"]:
            if isinstance(metadata["author"], list):
                if len(metadata["author"]) == 1:
                    parts.append(metadata["author"][0])
                elif len(metadata["author"]) == 2:
                    parts.append(f"{metadata['author'][0]} & {metadata['author'][1]}")
                else:
                    parts.append(f"{metadata['author'][0]} et al.")
            else:
                parts.append(metadata["author"])
        
        # Jahr
        if "year" in metadata and metadata["year"]:
            parts.append(f"({metadata['year']})")
        
        # Quelle
        source_info = []
        if "title" in metadata and metadata["title"]:
            source_info.append(metadata["title"])
        
        if "journal" in metadata and metadata["journal"]:
            source_info.append(metadata["journal"])
        elif "publisher" in metadata and metadata["publisher"]:
            source_info.append(metadata["publisher"])
        
        if source_info:
            parts.append(": ".join(source_info))
        
        return " ".join(parts) if parts else "Unbekannte Quelle"

# Singleton-Instanz
_search_service_instance = None

def get_search_service() -> SearchService:
    """
    Gibt eine Singleton-Instanz des SearchService zurück.
    
    Returns:
        SearchService-Instanz
    """
    global _search_service_instance
    if _search_service_instance is None:
        _search_service_instance = SearchService()
    return _search_service_instance