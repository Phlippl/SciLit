"""
Metadaten-Extraktion für SciLit
--------------------------
Funktionen zur Extraktion von Metadaten aus Text.
"""

import os
import re
from typing import List, Optional

def extract_title_from_text(text: str) -> Optional[str]:
    """Extrahiert einen möglichen Titel aus dem Text mit verbesserter Logik."""
    # Erste paar Zeilen des Texts durchsuchen
    lines = [line.strip() for line in text.split('\n') if line.strip()][:20]  # Erhöht auf 20 Zeilen
    
    # Typische Muster für Titel
    title_patterns = [
        # Muster für akademische Paper
        r'(?i)^(?:\s*|.*?\n\s*)(?:title[:\s]*|)([A-Z][\w\s\-:,;&]+[?!.)]?)(?:\s*\n|$)',
        # Muster für Buchtitel
        r'(?i)^(?:\s*|.*?\n\s*)([A-Z][\w\s\-:,;&]+)(?:\s*\nby\s+|$)',
    ]
    
    # Versuche zuerst, Titel anhand von typischen Mustern zu finden
    for pattern in title_patterns:
        title_match = re.search(pattern, '\n'.join(lines[:10]))
        if title_match:
            return title_match.group(1).strip()
    
    # Fallback: Suche nach der längsten Linie in den ersten Zeilen,
    # die keinen Autor oder andere typische Elemente enthält
    candidate_lines = []
    for line in lines:
        # Ignoriere kurze Zeilen und typische Nicht-Titel-Zeilen
        if len(line) < 10 or len(line) > 300:
            continue
        if re.search(r'(?i)(abstract|keywords|introduction|chapter|volume|edition|©|copyright|author|by\s+|university|journal)', line):
            continue
        if re.match(r'^[\d\.]+\s+', line):  # Nummerierte Abschnitte
            continue
        
        # Ein guter Titelkandidat
        candidate_lines.append((len(line), line))
    
    # Sortiere nach Länge in absteigender Reihenfolge
    candidate_lines.sort(reverse=True)
    
    # Wähle den ersten Kandidaten oder gib None zurück
    return candidate_lines[0][1] if candidate_lines else None


def extract_authors_from_text(text: str, filepath: str = "") -> Optional[List[str]]:
    """Extrahiert mögliche Autoren aus dem Text mit verbesserter Logik."""
    # Häufige Muster für Autorenlisten
    patterns = [
        # Autor(en) oder Author(s) gefolgt von einer Liste
        r'(?i)(?:author[s]?|autor[en]?|by)[:\s]+([^,\n]+(?:,\s*[^,\n]+)*)',
        
        # Autoren oben auf der Seite vor Affiliationen
        r'(?i)^(?:\s*|.*?\n\s*)([A-Z][a-z]+ [A-Z][a-z]+(?:, [A-Z][a-z]+ [A-Z][a-z]+)*)',
        
        # Autoren mit akademischen Titeln
        r'(?i)(?:prof\.|dr\.|ph\.d\.|professor|doctor)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
        
        # Autoren mit Fußnoten oder Affiliationszeichen
        r'([A-Z][a-z]+ [A-Z][a-z]+)(?:\s*[0-9\*†‡§])',
        
        # Autor und Datum im Format "Name (Jahr)"
        r'([A-Z][a-z]+ [A-Z][a-z]+)(?:\s*\([0-9]{4}\))',
    ]
    
    # Versuche zuerst die ersten 1500 Zeichen
    first_part = text[:1500]
    
    for pattern in patterns:
        matches = re.search(pattern, first_part)
        if matches:
            authors_text = matches.group(1)
            
            # Trenne Autoren, wenn sie durch Kommas, "und"/"and" oder "&" getrennt sind
            authors = re.split(r',\s*|\s+(?:und|and|&)\s+', authors_text)
            
            # Bereinige die Autorenliste
            authors = [author.strip() for author in authors if len(author.strip()) > 3]
            
            # Entferne bekannte Nicht-Autorenwörter
            filtered_authors = []
            for author in authors:
                if not re.search(r'(?i)(university|institute|department|abstract|keyword|introduction)', author):
                    filtered_authors.append(author)
            
            if filtered_authors:
                return filtered_authors
    
    # Bei PDF-Titel aus dem Namen raten
    if filepath:
        filename = os.path.basename(filepath)
        # Versuch, Autoren aus dem Dateinamen zu extrahieren
        # Format: "Autorenname_Titel.pdf" oder "Autorenname et al_Titel.pdf"
        filename_author_match = re.match(r'([A-Za-z]+(?:\s*et\s*al)?)[_\s\-]', filename)
        if filename_author_match:
            return [filename_author_match.group(1)]
    
    return None


def string_similarity(str1: str, str2: str) -> float:
    """Berechnet die Ähnlichkeit zwischen zwei Strings mit verschiedenen Methoden."""
    if not str1 or not str2:
        return 0.0
    
    # Strings normalisieren
    str1 = str1.lower().strip()
    str2 = str2.lower().strip()
    
    # Einfache Übereinstimmung
    if str1 == str2:
        return 1.0
    
    # Versuche es mit Levenshtein-Distanz
    try:
        import Levenshtein
        distance = Levenshtein.distance(str1, str2)
        max_len = max(len(str1), len(str2))
        if max_len == 0:
            return 0.0
        return 1.0 - (distance / max_len)
    except ImportError:
        # Fallback: Sequence Matcher
        from difflib import SequenceMatcher
        return SequenceMatcher(None, str1, str2).ratio()