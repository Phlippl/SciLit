"""
Hilfsfunktionen für SciLit
-------------------------
Verschiedene Hilfsfunktionen für mehrere Module.
"""

import os
import re
import hashlib
from typing import Any, Dict, List, Optional

def generate_document_id(filepath: str) -> str:
    """
    Erzeugt eine eindeutige ID für ein Dokument basierend auf Inhalt und Name.
    
    Args:
        filepath: Pfad zur Datei
        
    Returns:
        Eine eindeutige ID als Hexadezimalstring
    """
    filename = os.path.basename(filepath)
    file_stats = os.stat(filepath)
    
    # Kombiniere Dateiname, Größe und Änderungszeit für einen eindeutigen Hashwert
    id_string = f"{filename}_{file_stats.st_size}_{file_stats.st_mtime}"
    return hashlib.md5(id_string.encode()).hexdigest()[:12]

def normalize_string(text: str) -> str:
    """
    Normalisiert einen String für Vergleiche.
    
    Args:
        text: Der zu normalisierende Text
        
    Returns:
        Normalisierter Text
    """
    if not text:
        return ""
    
    # Entferne Sonderzeichen und führe einfache Filterung durch
    clean_text = re.sub(r'[^\w\s]', ' ', text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip().lower()
    return clean_text

def extract_year_from_date(date_str: str) -> Optional[int]:
    """
    Extrahiert das Jahr aus einem Datumsstring.
    
    Args:
        date_str: Datumsstring in verschiedenen Formaten
        
    Returns:
        Jahr als Integer oder None, wenn kein Jahr gefunden wurde
    """
    if not date_str:
        return None
    
    # Versuche verschiedene Formate
    year_patterns = [
        r'(\d{4})-\d{2}-\d{2}',  # ISO Format: 2022-01-31
        r'D:(\d{4})',  # PDF Format: D:20220131120000
        r'(\d{4})\.',  # Jahr mit Punkt: 2022.
        r'\((\d{4})\)',  # Jahr in Klammern: (2022)
        r'\b(\d{4})\b'  # Einfach vier Ziffern: 2022
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                year = int(match.group(1))
                # Plausibilitätsprüfung: Jahr zwischen 1800 und aktuellem Jahr + 5
                import datetime
                current_year = datetime.datetime.now().year
                if 1800 <= year <= current_year + 5:
                    return year
            except ValueError:
                pass
    
    return None

def format_citation(metadata: Dict[str, Any], style: str = "apa") -> str:
    """
    Formatiert eine Referenz nach einem bestimmten Zitierstil.
    
    Args:
        metadata: Metadaten des Dokuments
        style: Zitierstil ('apa', 'mla', 'chicago', 'harvard')
        
    Returns:
        Formatierte Zitierung
    """
    title = metadata.get('title', 'Unbekannter Titel')
    authors = metadata.get('author', [])
    if isinstance(authors, str):
        authors = [authors]
    year = metadata.get('year', 'o. J.')
    publisher = metadata.get('publisher', '')
    journal = metadata.get('journal', '')
    doi = metadata.get('doi', '')
    
    if style == "apa":
        # APA 7th Edition
        author_str = ""
        if authors:
            for i, author in enumerate(authors):
                name_parts = author.split()
                if name_parts:
                    last_name = name_parts[-1]
                    initials = "".join([n[0] + "." for n in name_parts[:-1]])
                    if initials:
                        author_format = f"{last_name}, {initials}"
                    else:
                        author_format = last_name
                    
                    if i == 0:
                        author_str = author_format
                    elif i == len(authors) - 1:
                        author_str += f", & {author_format}"
                    else:
                        author_str += f", {author_format}"
        
        citation = f"{author_str} ({year}). {title}."
        
        if journal:
            citation += f" {journal}."
        elif publisher:
            citation += f" {publisher}."
        
        if doi:
            citation += f" https://doi.org/{doi}"
        
        return citation
    
    elif style == "mla":
        # MLA 9th Edition
        author_str = ""
        if authors:
            # In MLA steht der erste Autor mit Nachname zuerst
            name_parts = authors[0].split()
            if name_parts:
                last_name = name_parts[-1]
                first_name = " ".join(name_parts[:-1])
                author_str = f"{last_name}, {first_name}"
                
            # Weitere Autoren
            if len(authors) == 2:
                name_parts = authors[1].split()
                author_str += f", and {' '.join(name_parts)}"
            elif len(authors) > 2:
                author_str += ", et al"
        
        citation = f"{author_str}. {title}."
        
        if journal:
            citation += f" {journal},"
        elif publisher:
            citation += f" {publisher},"
        
        citation += f" {year}."
        
        if doi:
            citation += f" DOI: {doi}."
        
        return citation
    
    elif style == "chicago":
        # Chicago 17th Edition
        author_str = ""
        if authors:
            for i, author in enumerate(authors):
                name_parts = author.split()
                if name_parts:
                    # Erster Autor mit Nachnamen zuerst
                    if i == 0:
                        last_name = name_parts[-1]
                        first_name = " ".join(name_parts[:-1])
                        author_str = f"{last_name}, {first_name}"
                    # Weitere Autoren in normaler Reihenfolge
                    else:
                        if i == len(authors) - 1:
                            author_str += f", and {author}"
                        else:
                            author_str += f", {author}"
        
        citation = f"{author_str}. {title}."
        
        if journal:
            citation += f" {journal}"
        
        if publisher:
            citation += f" {publisher},"
        
        citation += f" {year}."
        
        if doi:
            citation += f" https://doi.org/{doi}."
        
        return citation
    
    elif style == "harvard":
        # Harvard Style
        author_str = ""
        if authors:
            for i, author in enumerate(authors):
                name_parts = author.split()
                if name_parts:
                    last_name = name_parts[-1]
                    initials = "".join([n[0] + "." for n in name_parts[:-1]])
                    author_format = f"{last_name}, {initials}" if initials else last_name
                    
                    if i == 0:
                        author_str = author_format
                    elif i == len(authors) - 1:
                        author_str += f" and {author_format}"
                    else:
                        author_str += f", {author_format}"
        
        citation = f"{author_str} ({year}) {title}."
        
        if journal:
            citation += f" {journal},"
        
        if publisher:
            citation += f" {publisher}."
        
        if doi:
            citation += f" Available at: https://doi.org/{doi}."
        
        return citation
    
    else:
        # Standardformat, wenn der Stil nicht erkannt wird
        author_str = ", ".join(authors) if authors else "Unbekannter Autor"
        citation = f"{author_str} ({year}). {title}."
        
        if journal:
            citation += f" In: {journal}."
        elif publisher:
            citation += f" {publisher}."
        
        if doi:
            citation += f" DOI: {doi}"
        
        return citation