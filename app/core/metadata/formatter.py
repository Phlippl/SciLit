# Neue Datei: app/core/metadata/formatter.py

"""
Metadaten-Formatierung für SciLit
---------------------------------
Enthält Funktionen zur Formatierung von bibliografischen Referenzen in verschiedenen Zitationsstilen.
"""

import logging
from typing import Dict, List, Any, Optional, Union

# Logger konfigurieren
logger = logging.getLogger("scilit.metadata.formatter")

class MetadataFormatter:
    """
    Klasse zur Formatierung von Metadaten in verschiedenen Zitationsstilen.
    
    Diese Klasse bietet Methoden zur Erzeugung von formatierten Zitaten und Bibliografien
    nach gängigen akademischen Zitationsstilen wie APA, MLA, Chicago und Harvard.
    """
    
    def __init__(self):
        """Initialisiert den MetadataFormatter."""
        logger.debug("MetadataFormatter initialisiert")
    
    def format_citation(self, metadata: Dict[str, Any], style: str = "apa") -> str:
        """
        Formatiert ein Zitat im angegebenen Stil.
        
        Args:
            metadata: Die zu formatierenden Metadaten
            style: Der Zitationsstil ('apa', 'mla', 'chicago', 'harvard', 'ieee')
            
        Returns:
            Formatiertes Zitat als String
        """
        style = style.lower()
        
        if style == "apa":
            return self._format_apa(metadata)
        elif style == "mla":
            return self._format_mla(metadata)
        elif style == "chicago":
            return self._format_chicago(metadata)
        elif style == "harvard":
            return self._format_harvard(metadata)
        elif style == "ieee":
            return self._format_ieee(metadata)
        else:
            logger.warning(f"Unbekannter Zitationsstil: {style}, verwende APA")
            return self._format_apa(metadata)
    
    def format_inline_citation(self, metadata: Dict[str, Any], style: str = "apa", page: str = None) -> str:
        """
        Formatiert ein Inline-Zitat (Kurzzitat) im angegebenen Stil.
        
        Args:
            metadata: Die zu formatierenden Metadaten
            style: Der Zitationsstil ('apa', 'mla', 'chicago', 'harvard', 'ieee')
            page: Optionale Seitenzahl für das Zitat
            
        Returns:
            Formatiertes Inline-Zitat als String
        """
        style = style.lower()
        
        # Basis-Informationen für alle Stile
        author = self._get_author_last_name(metadata)
        year = metadata.get("year", "n.d.")
        
        # Stil-spezifische Formatierung
        if style == "apa":
            cite = f"({author}, {year}"
            if page:
                cite += f", S. {page}"
            cite += ")"
            return cite
        
        elif style == "mla":
            cite = f"({author}"
            if page:
                cite += f" {page}"
            cite += ")"
            return cite
        
        elif style == "chicago":
            cite = f"({author} {year}"
            if page:
                cite += f", {page}"
            cite += ")"
            return cite
        
        elif style == "harvard":
            cite = f"({author}, {year}"
            if page:
                cite += f": {page}"
            cite += ")"
            return cite
        
        elif style == "ieee":
            # IEEE verwendet numerische Zitate, vereinfacht für den Kontext
            cite = f"[{page or '1'}]"
            return cite
        
        else:
            logger.warning(f"Unbekannter Zitationsstil für Inline-Zitat: {style}, verwende APA")
            cite = f"({author}, {year}"
            if page:
                cite += f", S. {page}"
            cite += ")"
            return cite
    
    def _format_apa(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert ein Zitat im APA-Stil (7. Edition).
        
        Args:
            metadata: Die zu formatierenden Metadaten
            
        Returns:
            APA-formatiertes Zitat
        """
        # Autor(en)
        authors = self._format_authors_apa(metadata)
        
        # Jahr
        year = metadata.get("year", "n.d.")
        year_part = f"({year}). "
        
        # Titel
        title = metadata.get("title", "Unbekannter Titel")
        if metadata.get("type") == "article" or metadata.get("journal"):
            # Artikel: Titel normal
            title_part = f"{title}. "
        else:
            # Buch: Titel kursiv
            title_part = f"*{title}*. "
        
        # Quelle/Verlag
        source_part = ""
        if metadata.get("journal"):
            # Zeitschriftenartikel
            journal = metadata.get("journal", "")
            volume = metadata.get("volume", "")
            issue = metadata.get("issue", "")
            page_range = metadata.get("pages", "")
            
            source_part = f"*{journal}*"
            if volume:
                source_part += f", {volume}"
                if issue:
                    source_part += f"({issue})"
            if page_range:
                source_part += f", {page_range}"
            source_part += "."
        elif metadata.get("publisher"):
            # Buch oder ähnliches
            publisher = metadata.get("publisher", "")
            source_part = f"{publisher}."
        
        # DOI/URL
        doi_part = ""
        if metadata.get("doi"):
            doi = metadata.get("doi", "")
            if not doi.startswith("https://doi.org/"):
                doi = f"https://doi.org/{doi}"
            doi_part = f" {doi}"
        
        # Komplettes Zitat zusammenbauen
        citation = f"{authors}{year_part}{title_part}{source_part}{doi_part}"
        return citation
    
    def _format_mla(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert ein Zitat im MLA-Stil (9. Edition).
        
        Args:
            metadata: Die zu formatierenden Metadaten
            
        Returns:
            MLA-formatiertes Zitat
        """
        # Autor(en)
        authors = self._format_authors_mla(metadata)
        
        # Titel
        title = metadata.get("title", "Unbekannter Titel")
        if metadata.get("type") == "article" or metadata.get("journal"):
            # Artikel: Titel in Anführungszeichen
            title_part = f"\"{title}.\" "
        else:
            # Buch: Titel kursiv
            title_part = f"*{title}*. "
        
        # Container (Journal, Buch, etc.)
        container_part = ""
        if metadata.get("journal"):
            journal = metadata.get("journal", "")
            volume = metadata.get("volume", "")
            issue = metadata.get("issue", "")
            container_part = f"*{journal}*"
            if volume:
                container_part += f", vol. {volume}"
            if issue:
                container_part += f", no. {issue}"
            container_part += ", "
        
        # Verlag
        publisher_part = ""
        if metadata.get("publisher"):
            publisher = metadata.get("publisher", "")
            publisher_part = f"{publisher}, "
        
        # Jahr
        year = metadata.get("year", "n.d.")
        year_part = f"{year}"
        
        # Seiten
        pages_part = ""
        if metadata.get("pages") and metadata.get("journal"):
            pages = metadata.get("pages", "")
            pages_part = f", pp. {pages}"
        
        # DOI/URL
        doi_part = ""
        if metadata.get("doi"):
            doi = metadata.get("doi", "")
            if not doi.startswith("https://doi.org/"):
                doi = f"https://doi.org/{doi}"
            doi_part = f". {doi}"
        
        # Komplettes Zitat zusammenbauen
        citation = f"{authors}{title_part}{container_part}{publisher_part}{year_part}{pages_part}{doi_part}."
        return citation
    
    def _format_chicago(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert ein Zitat im Chicago-Stil (17. Edition).
        
        Args:
            metadata: Die zu formatierenden Metadaten
            
        Returns:
            Chicago-formatiertes Zitat
        """
        # Autor(en)
        authors = self._format_authors_chicago(metadata)
        
        # Titel
        title = metadata.get("title", "Unbekannter Titel")
        if metadata.get("type") == "article" or metadata.get("journal"):
            # Artikel: Titel in Anführungszeichen
            title_part = f"\"{title}.\" "
        else:
            # Buch: Titel kursiv
            title_part = f"*{title}*. "
        
        # Journal/Quelle
        source_part = ""
        if metadata.get("journal"):
            journal = metadata.get("journal", "")
            volume = metadata.get("volume", "")
            issue = metadata.get("issue", "")
            pages = metadata.get("pages", "")
            year = metadata.get("year", "n.d.")
            
            source_part = f"*{journal}* "
            if volume:
                source_part += f"{volume}"
                if issue:
                    source_part += f", no. {issue} "
            source_part += f"({year})"
            if pages:
                source_part += f": {pages}"
            source_part += "."
        else:
            # Buch
            city = metadata.get("publisher_location", "")
            publisher = metadata.get("publisher", "")
            year = metadata.get("year", "n.d.")
            
            if city and publisher:
                source_part = f"{city}: {publisher}, {year}."
            elif publisher:
                source_part = f"{publisher}, {year}."
            else:
                source_part = f"{year}."
        
        # DOI/URL
        doi_part = ""
        if metadata.get("doi"):
            doi = metadata.get("doi", "")
            if not doi.startswith("https://doi.org/"):
                doi = f"https://doi.org/{doi}"
            doi_part = f" {doi}."
        
        # Komplettes Zitat zusammenbauen
        citation = f"{authors}{title_part}{source_part}{doi_part}"
        return citation
    
    def _format_harvard(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert ein Zitat im Harvard-Stil.
        
        Args:
            metadata: Die zu formatierenden Metadaten
            
        Returns:
            Harvard-formatiertes Zitat
        """
        # Autor(en)
        authors = self._format_authors_harvard(metadata)
        
        # Jahr
        year = metadata.get("year", "n.d.")
        year_part = f"({year}) "
        
        # Titel
        title = metadata.get("title", "Unbekannter Titel")
        if metadata.get("type") == "article" or metadata.get("journal"):
            # Artikel: Titel normal
            title_part = f"'{title}', "
        else:
            # Buch: Titel kursiv
            title_part = f"*{title}*, "
        
        # Quelle/Verlag
        source_part = ""
        if metadata.get("journal"):
            # Zeitschriftenartikel
            journal = metadata.get("journal", "")
            volume = metadata.get("volume", "")
            issue = metadata.get("issue", "")
            pages = metadata.get("pages", "")
            
            source_part = f"*{journal}*"
            if volume:
                source_part += f", {volume}"
                if issue:
                    source_part += f"({issue})"
            if pages:
                source_part += f", pp. {pages}"
            source_part += "."
        elif metadata.get("publisher"):
            # Buch oder ähnliches
            publisher = metadata.get("publisher", "")
            location = metadata.get("publisher_location", "")
            if location:
                source_part = f"{location}: {publisher}."
            else:
                source_part = f"{publisher}."
        
        # DOI/URL
        doi_part = ""
        if metadata.get("doi"):
            doi = metadata.get("doi", "")
            if not doi.startswith("https://doi.org/"):
                doi = f"https://doi.org/{doi}"
            doi_part = f" Verfügbar unter: {doi} [Zugriff am: --]."
        
        # Komplettes Zitat zusammenbauen
        citation = f"{authors}{year_part}{title_part}{source_part}{doi_part}"
        return citation
    
    def _format_ieee(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert ein Zitat im IEEE-Stil.
        
        Args:
            metadata: Die zu formatierenden Metadaten
            
        Returns:
            IEEE-formatiertes Zitat
        """
        # Autor(en)
        authors = self._format_authors_ieee(metadata)
        if authors:
            authors += ", "
        
        # Titel
        title = metadata.get("title", "Unbekannter Titel")
        title_part = f"\"{title},\" "
        
        # Quelle/Verlag
        source_part = ""
        if metadata.get("journal"):
            # Zeitschriftenartikel
            journal = metadata.get("journal", "")
            volume = metadata.get("volume", "")
            issue = metadata.get("issue", "")
            pages = metadata.get("pages", "")
            year = metadata.get("year", "n.d.")
            
            source_part = f"*{journal}*"
            if volume:
                source_part += f", vol. {volume}"
                if issue:
                    source_part += f", no. {issue}"
            if pages:
                source_part += f", pp. {pages}"
            source_part += f", {year}."
        elif metadata.get("publisher"):
            # Buch oder ähnliches
            publisher = metadata.get("publisher", "")
            year = metadata.get("year", "n.d.")
            source_part = f"{publisher}, {year}."
        else:
            year = metadata.get("year", "n.d.")
            source_part = f"{year}."
        
        # DOI/URL
        doi_part = ""
        if metadata.get("doi"):
            doi = metadata.get("doi", "")
            if not doi.startswith("https://doi.org/"):
                doi = f"https://doi.org/{doi}"
            doi_part = f" DOI: {doi}."
        
        # Komplettes Zitat zusammenbauen
        citation = f"{authors}{title_part}{source_part}{doi_part}"
        return citation
    
    def _get_author_last_name(self, metadata: Dict[str, Any]) -> str:
        """
        Extrahiert den Nachnamen des ersten Autors oder gibt eine Standardangabe zurück.
        
        Args:
            metadata: Die Metadaten
            
        Returns:
            Nachname des ersten Autors oder Platzhalter
        """
        author_info = metadata.get("author", ["Unbekannt"])
        
        if not author_info:
            return "Unbekannt"
        
        if isinstance(author_info, list):
            first_author = author_info[0]
        else:
            first_author = author_info
        
        # Nachname extrahieren (letztes Wort im Namen)
        name_parts = first_author.split()
        if name_parts:
            if len(author_info) > 1 and isinstance(author_info, list):
                return f"{name_parts[-1]} et al."
            return name_parts[-1]
        else:
            return "Unbekannt"
    
    def _format_authors_apa(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert Autoren nach APA-Stil.
        
        Args:
            metadata: Die Metadaten
            
        Returns:
            Formatierte Autorenliste
        """
        author_info = metadata.get("author", [])
        
        if not author_info:
            return ""
        
        if isinstance(author_info, str):
            author_info = [author_info]
        
        # Bis zu 20 Autoren bei APA
        authors = []
        for author in author_info[:20]:
            name_parts = author.split()
            if len(name_parts) > 1:
                # Nachname, Initialen
                last_name = name_parts[-1]
                initials = "".join([part[0] + "." for part in name_parts[:-1]])
                authors.append(f"{last_name}, {initials}")
            else:
                authors.append(author)
        
        # APA-Format: Bis zu 20 Autoren alle auflisten, bei mehr als 20 die ersten 19 und dann "& letzter Autor"
        if len(authors) == 1:
            return authors[0]
        elif len(authors) == 2:
            return f"{authors[0]} & {authors[1]}"
        elif len(authors) <= 20:
            return ", ".join(authors[:-1]) + f", & {authors[-1]}"
        else:
            return ", ".join(authors[:19]) + f", ... {authors[-1]}"
    
    def _format_authors_mla(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert Autoren nach MLA-Stil.
        
        Args:
            metadata: Die Metadaten
            
        Returns:
            Formatierte Autorenliste
        """
        author_info = metadata.get("author", [])
        
        if not author_info:
            return ""
        
        if isinstance(author_info, str):
            author_info = [author_info]
        
        # MLA: Erster Autor "Nachname, Vorname", weitere "Vorname Nachname"
        if len(author_info) == 1:
            name_parts = author_info[0].split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                first_name = " ".join(name_parts[:-1])
                return f"{last_name}, {first_name}. "
            else:
                return f"{author_info[0]}. "
        elif len(author_info) == 2:
            name_parts1 = author_info[0].split()
            if len(name_parts1) > 1:
                last_name1 = name_parts1[-1]
                first_name1 = " ".join(name_parts1[:-1])
                return f"{last_name1}, {first_name1}, and {author_info[1]}. "
            else:
                return f"{author_info[0]}, and {author_info[1]}. "
        elif len(author_info) == 3:
            name_parts1 = author_info[0].split()
            if len(name_parts1) > 1:
                last_name1 = name_parts1[-1]
                first_name1 = " ".join(name_parts1[:-1])
                return f"{last_name1}, {first_name1}, et al. "
            else:
                return f"{author_info[0]}, et al. "
        else:
            name_parts1 = author_info[0].split()
            if len(name_parts1) > 1:
                last_name1 = name_parts1[-1]
                first_name1 = " ".join(name_parts1[:-1])
                return f"{last_name1}, {first_name1}, et al. "
            else:
                return f"{author_info[0]}, et al. "
    
    def _format_authors_chicago(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert Autoren nach Chicago-Stil.
        
        Args:
            metadata: Die Metadaten
            
        Returns:
            Formatierte Autorenliste
        """
        author_info = metadata.get("author", [])
        
        if not author_info:
            return ""
        
        if isinstance(author_info, str):
            author_info = [author_info]
        
        # Chicago: Erster Autor "Nachname, Vorname", weitere "Vorname Nachname"
        if len(author_info) == 1:
            name_parts = author_info[0].split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                first_name = " ".join(name_parts[:-1])
                return f"{last_name}, {first_name}. "
            else:
                return f"{author_info[0]}. "
        elif len(author_info) == 2:
            name_parts1 = author_info[0].split()
            if len(name_parts1) > 1:
                last_name1 = name_parts1[-1]
                first_name1 = " ".join(name_parts1[:-1])
                return f"{last_name1}, {first_name1}, and {author_info[1]}. "
            else:
                return f"{author_info[0]}, and {author_info[1]}. "
        elif len(author_info) == 3:
            name_parts1 = author_info[0].split()
            if len(name_parts1) > 1:
                last_name1 = name_parts1[-1]
                first_name1 = " ".join(name_parts1[:-1])
                name_parts2 = author_info[1].split()
                name_parts3 = author_info[2].split()
                return f"{last_name1}, {first_name1}, {' '.join(name_parts2)}, and {' '.join(name_parts3)}. "
            else:
                return f"{author_info[0]}, {author_info[1]}, and {author_info[2]}. "
        else:
            name_parts1 = author_info[0].split()
            if len(name_parts1) > 1:
                last_name1 = name_parts1[-1]
                first_name1 = " ".join(name_parts1[:-1])
                return f"{last_name1}, {first_name1}, et al. "
            else:
                return f"{author_info[0]}, et al. "
    
    def _format_authors_harvard(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert Autoren nach Harvard-Stil.
        
        Args:
            metadata: Die Metadaten
            
        Returns:
            Formatierte Autorenliste
        """
        author_info = metadata.get("author", [])
        
        if not author_info:
            return ""
        
        if isinstance(author_info, str):
            author_info = [author_info]
        
        # Harvard: Autoren mit Nachnamen und Initialen
        authors = []
        for author in author_info:
            name_parts = author.split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                initials = "".join([part[0] + "." for part in name_parts[:-1]])
                authors.append(f"{last_name}, {initials}")
            else:
                authors.append(author)
        
        # Harvard-Format
        if len(authors) == 1:
            return authors[0]
        elif len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"
        elif len(authors) == 3:
            return f"{authors[0]}, {authors[1]} and {authors[2]}"
        else:
            return f"{authors[0]} et al."
    
    def _format_authors_ieee(self, metadata: Dict[str, Any]) -> str:
        """
        Formatiert Autoren nach IEEE-Stil.
        
        Args:
            metadata: Die Metadaten
            
        Returns:
            Formatierte Autorenliste
        """
        author_info = metadata.get("author", [])
        
        if not author_info:
            return ""
        
        if isinstance(author_info, str):
            author_info = [author_info]
        
        # IEEE: Initialen vor Nachnamen
        authors = []
        for author in author_info:
            name_parts = author.split()
            if len(name_parts) > 1:
                last_name = name_parts[-1]
                initials = " ".join([part[0] + "." for part in name_parts[:-1]])
                authors.append(f"{initials} {last_name}")
            else:
                authors.append(author)
        
        # IEEE-Format: Alle Autoren durch Kommas getrennt
        if len(authors) == 1:
            return authors[0]
        elif len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"
        else:
            return ", ".join(authors[:-1]) + f", and {authors[-1]}"

# Singleton-Instanz
_formatter_instance = None

def get_metadata_formatter() -> MetadataFormatter:
    """
    Gibt eine Singleton-Instanz des MetadataFormatters zurück.
    
    Returns:
        MetadataFormatter-Instanz
    """
    global _formatter_instance
    if _formatter_instance is None:
        _formatter_instance = MetadataFormatter()
    return _formatter_instance

def format_citation(metadata: Dict[str, Any], style: str = "apa") -> str:
    """
    Hilfsfunktion zum Formatieren eines Zitats.
    
    Args:
        metadata: Die zu formatierenden Metadaten
        style: Der Zitationsstil
        
    Returns:
        Formatiertes Zitat
    """
    formatter = get_metadata_formatter()
    return formatter.format_citation(metadata, style)