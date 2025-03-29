"""
Metadaten-Extraktion für SciLit
--------------------------
Funktionen zur Extraktion von Metadaten aus Text.
"""

import os
import re
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

# Logger konfigurieren
logger = logging.getLogger("scilit.metadata.extractor")

def extract_title_from_text(text: str) -> Optional[str]:
    """
    Extrahiert einen möglichen Titel aus dem Text mit verbesserter Logik.
    
    Diese Funktion versucht, den Titel eines wissenschaftlichen Dokuments 
    zu identifizieren, indem sie nach typischen Mustern am Anfang des Textes sucht.
    
    Args:
        text: Der zu analysierende Text
        
    Returns:
        Der extrahierte Titel oder None, wenn kein Titel gefunden wurde
    """
    logger.debug("Versuche Titel aus Text zu extrahieren")
    
    # Erste paar Zeilen des Texts durchsuchen
    lines = [line.strip() for line in text.split('\n') if line.strip()][:20]  # Erhöht auf 20 Zeilen
    
    # Typische Muster für Titel
    title_patterns = [
        # Muster für akademische Paper
        r'(?i)^(?:\s*|.*?\n\s*)(?:title[:\s]*|)([A-Z][\w\s\-:,;&]+[?!.)]?)(?:\s*\n|$)',
        # Muster für Buchtitel
        r'(?i)^(?:\s*|.*?\n\s*)([A-Z][\w\s\-:,;&]+)(?:\s*\nby\s+|$)',
        # Muster für deutsche Titel
        r'(?i)^(?:\s*|.*?\n\s*)(?:titel[:\s]*|)([A-Z][\w\säöüÄÖÜß\-:,;&]+[?!.)]?)(?:\s*\n|$)',
    ]
    
    # Versuche zuerst, Titel anhand von typischen Mustern zu finden
    for pattern in title_patterns:
        title_match = re.search(pattern, '\n'.join(lines[:10]))
        if title_match:
            title = title_match.group(1).strip()
            logger.debug(f"Titel über Muster gefunden: {title}")
            return title
    
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
    
    if candidate_lines:
        title = candidate_lines[0][1]
        logger.debug(f"Titel über Kandidaten-Analyse gefunden: {title}")
        return title
    
    logger.debug("Kein Titel gefunden")
    return None


def extract_authors_from_text(text: str, filepath: str = "") -> Optional[List[str]]:
    """
    Extrahiert mögliche Autoren aus dem Text mit verbesserter Logik.
    
    Diese Funktion versucht, Autoren eines wissenschaftlichen Dokuments zu 
    identifizieren, indem sie nach typischen Autorenpatterns oder -markierungen sucht.
    
    Args:
        text: Der zu analysierende Text
        filepath: Optionaler Pfad zur Datei (für Extraktion aus Dateiname)
        
    Returns:
        Liste der extrahierten Autoren oder None, wenn keine Autoren gefunden wurden
    """
    logger.debug("Versuche Autoren aus Text zu extrahieren")
    
    # Häufige Muster für Autorenlisten
    patterns = [
        # Autor(en) oder Author(s) gefolgt von einer Liste
        r'(?i)(?:author[s]?|autor[en]?|by)[:\s]+([^,\n]+(?:,\s*[^,\n]+)*)',
        
        # Autoren oben auf der Seite vor Affiliationen
        r'(?i)^(?:\s*|.*?\n\s*)([A-Z][a-z]+ [A-Z][a-z]+(?:,\s*[A-Z][a-z]+ [A-Z][a-z]+)*)',
        
        # Autoren mit akademischen Titeln
        r'(?i)(?:prof\.|dr\.|ph\.d\.|professor|doctor)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
        
        # Autoren mit Fußnoten oder Affiliationszeichen
        r'([A-Z][a-z]+ [A-Z][a-z]+)(?:\s*[0-9\*†‡§])',
        
        # Autor und Datum im Format "Name (Jahr)"
        r'([A-Z][a-z]+ [A-Z][a-z]+)(?:\s*\([0-9]{4}\))',
        
        # Erweiterte Muster für deutsche Namen
        r'(?i)(?:von|zu|van|der|de)\s+([A-Z][a-z]+ [A-Z][a-z]+)'
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
                logger.debug(f"Autoren gefunden: {filtered_authors}")
                return filtered_authors
    
    # Bei PDF-Titel aus dem Namen raten
    if filepath:
        filename = os.path.basename(filepath)
        # Versuch, Autoren aus dem Dateinamen zu extrahieren
        # Format: "Autorenname_Titel.pdf" oder "Autorenname et al_Titel.pdf"
        filename_author_match = re.match(r'([A-Za-z]+(?:\s*et\s*al)?)[_\s\-]', filename)
        if filename_author_match:
            author = filename_author_match.group(1)
            logger.debug(f"Autor aus Dateiname extrahiert: {author}")
            return [author]
    
    logger.debug("Keine Autoren gefunden")
    return None


def extract_year_from_text(text: str) -> Optional[int]:
    """
    Extrahiert ein Publikationsjahr aus dem Text.
    
    Diese Funktion sucht nach typischen Jahresangaben in einem wissenschaftlichen Text,
    wie z.B. "Published in 2020" oder "© 2021".
    
    Args:
        text: Der zu analysierende Text
        
    Returns:
        Das extrahierte Jahr als Integer oder None, wenn kein Jahr gefunden wurde
    """
    logger.debug("Versuche Jahr aus Text zu extrahieren")
    
    # Typische Muster für Jahreszahlen in Papers
    year_patterns = [
        r'(?i)(?:published|accepted|received).*?(\d{4})',
        r'(?i)(?:copyright|©).*?(\d{4})',
        r'(?i)(?:\d{1,2}\.{0,1}\s*)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.{0,1}\s*(?:\d{1,2},?\s*)?(\d{4})',
        r'\((\d{4})\)',  # Jahr in Klammern
        r'(?<=\s)(\d{4})(?=\s)',  # Isoliertes Jahr
        r'Volume\s+\d+,?\s+\((\d{4})\)',  # Jahrgangsnummer
    ]
    
    # Auf die ersten 2000 Zeichen beschränken für Performance
    first_part = text[:2000]
    
    current_year = 2025  # Aktuelles Jahr als Maximum
    min_valid_year = 1900  # Sinnvolle Untergrenze
    
    # Alle Jahre sammeln und nach Plausibilität filtern
    years = []
    
    for pattern in year_patterns:
        for match in re.finditer(pattern, first_part):
            try:
                year = int(match.group(1))
                if min_valid_year <= year <= current_year:
                    years.append(year)
            except (ValueError, IndexError):
                continue
    
    if years:
        # Nehme das am häufigsten vorkommende Jahr
        from collections import Counter
        most_common_year = Counter(years).most_common(1)[0][0]
        logger.debug(f"Jahr extrahiert: {most_common_year}")
        return most_common_year
    
    logger.debug("Kein Jahr gefunden")
    return None


def extract_publisher_from_text(text: str) -> Optional[str]:
    """
    Extrahiert einen Verleger oder eine Quelle aus dem Text.
    
    Diese Funktion sucht nach typischen Verlagsangaben oder Journalnamen
    in einem wissenschaftlichen Text.
    
    Args:
        text: Der zu analysierende Text
        
    Returns:
        Der extrahierte Verleger oder None, wenn kein Verleger gefunden wurde
    """
    logger.debug("Versuche Verleger aus Text zu extrahieren")
    
    # Typische Muster für Verlage oder Journals
    publisher_patterns = [
        r'(?i)published by\s+([^\.]+)\.',
        r'(?i)©\s*\d{4}\s+([^\.]+)',
        r'(?i)journal of\s+([^\.]+)',
        r'(?i)university\s+of\s+([^\.]+)\s+press',
        r'(?i)verlag\s+([^\.]+)',
        r'(?i)press\s+([^\.]+)'
    ]
    
    # Bekannte Verlage und Journals für die Erkennung
    known_publishers = [
        "Elsevier", "Springer", "Wiley", "IEEE", "ACM", "Nature", "Science", 
        "Oxford University Press", "Cambridge University Press", "MIT Press",
        "Springer Nature", "Taylor & Francis", "SAGE", "Wolters Kluwer",
        "De Gruyter", "Thieme", "Hanser", "Academic Press"
    ]
    
    # Auf die ersten 3000 Zeichen beschränken für Performance
    first_part = text[:3000]
    
    # Zuerst nach bekannten Verlagen suchen
    for publisher in known_publishers:
        if re.search(r'\b' + re.escape(publisher) + r'\b', first_part, re.IGNORECASE):
            logger.debug(f"Verleger gefunden (bekannte Liste): {publisher}")
            return publisher
    
    # Dann nach Patterns suchen
    for pattern in publisher_patterns:
        match = re.search(pattern, first_part)
        if match:
            publisher = match.group(1).strip()
            # Kurze Filter für unplausible Ergebnisse
            if len(publisher) > 3 and len(publisher) < 100:
                logger.debug(f"Verleger gefunden (Muster): {publisher}")
                return publisher
    
    logger.debug("Kein Verleger gefunden")
    return None


def extract_doi_from_text(text: str) -> Optional[str]:
    """
    Extrahiert eine DOI (Digital Object Identifier) aus dem Text.
    
    Diese Funktion sucht nach dem standardisierten DOI-Format in einem 
    wissenschaftlichen Text.
    
    Args:
        text: Der zu analysierende Text
        
    Returns:
        Die extrahierte DOI oder None, wenn keine DOI gefunden wurde
    """
    logger.debug("Versuche DOI aus Text zu extrahieren")
    
    # Standard DOI-Muster
    doi_pattern = r'(?i)(?:doi|DOI|https?://doi\.org/)[:\s/]*(10\.\d{4,}(?:[.][0-9]+)*/(?:(?!["&\'<>])\S)+)'
    
    match = re.search(doi_pattern, text)
    if match:
        doi = match.group(1).strip()
        logger.debug(f"DOI gefunden: {doi}")
        return doi
    
    logger.debug("Keine DOI gefunden")
    return None


def extract_isbn_from_text(text: str) -> Optional[str]:
    """
    Extrahiert eine ISBN (International Standard Book Number) aus dem Text.
    
    Diese Funktion sucht nach sowohl ISBN-10 als auch ISBN-13 Formaten
    in einem wissenschaftlichen Text.
    
    Args:
        text: Der zu analysierende Text
        
    Returns:
        Die extrahierte ISBN oder None, wenn keine ISBN gefunden wurde
    """
    logger.debug("Versuche ISBN aus Text zu extrahieren")
    
    # Muster für ISBN-10 und ISBN-13
    isbn_patterns = [
        r'(?i)ISBN(?:-10)?[:\s]*(\d{1,5}[- ]\d{1,7}[- ]\d{1,7}[- ][\dXx])',  # ISBN-10
        r'(?i)ISBN(?:-13)?[:\s]*(\d{3}[- ]\d{1,5}[- ]\d{1,7}[- ]\d{1,7}[- ][\dXx])',  # ISBN-13
        r'(?i)ISBN(?:-10)?[:\s]*(\d{10})',  # ISBN-10 ohne Trennzeichen
        r'(?i)ISBN(?:-13)?[:\s]*(\d{13})'  # ISBN-13 ohne Trennzeichen
    ]
    
    for pattern in isbn_patterns:
        match = re.search(pattern, text)
        if match:
            isbn = match.group(1).strip()
            # Entferne Trennzeichen für eine standardisierte Rückgabe
            isbn = re.sub(r'[- ]', '', isbn)
            logger.debug(f"ISBN gefunden: {isbn}")
            return isbn
    
    logger.debug("Keine ISBN gefunden")
    return None


def extract_journal_from_text(text: str) -> Optional[str]:
    """
    Extrahiert einen Journalnamen aus dem Text.
    
    Diese Funktion sucht nach typischen Journalnamen in einem 
    wissenschaftlichen Text.
    
    Args:
        text: Der zu analysierende Text
        
    Returns:
        Der extrahierte Journalname oder None, wenn kein Journal gefunden wurde
    """
    logger.debug("Versuche Journal aus Text zu extrahieren")
    
    # Typische Muster für Journals
    journal_patterns = [
        r'(?i)published in[:\s]*([^\.]+)',
        r'(?i)journal of ([^\.]+)',
        r'(?i)proceedings of ([^\.]+)',
        r'(?i)transactions on ([^\.]+)',
        r'(?i)zeitschrift für ([^\.]+)',
        r'(?i)in\: ([^\.]+), vol\.'
    ]
    
    # Bekannte Journale für die Erkennung
    known_journals = [
        "Nature", "Science", "PNAS", "Cell", "The Lancet", "JAMA", 
        "IEEE Transactions", "ACM Transactions", "Physical Review", 
        "Journal of the American Chemical Society", "Angewandte Chemie",
        "Bioinformatics", "Journal of Machine Learning Research", "PLOS ONE", 
        "Nucleic Acids Research", "New England Journal of Medicine"
    ]
    
    # Auf die ersten 3000 Zeichen beschränken für Performance
    first_part = text[:3000]
    
    # Zuerst nach bekannten Journals suchen
    for journal in known_journals:
        if re.search(r'\b' + re.escape(journal) + r'\b', first_part, re.IGNORECASE):
            logger.debug(f"Journal gefunden (bekannte Liste): {journal}")
            return journal
    
    # Dann nach Patterns suchen
    for pattern in journal_patterns:
        match = re.search(pattern, first_part)
        if match:
            journal = match.group(1).strip()
            # Kurze Filter für unplausible Ergebnisse
            if len(journal) > 3 and len(journal) < 100:
                # Entferne typische Zusätze
                journal = re.sub(r'(?i)\s*\(.*?\)', '', journal)  # Klammern
                journal = re.sub(r'(?i)\s*vol\..*$', '', journal)  # Volume
                journal = re.sub(r'(?i)\s*pp\..*$', '', journal)  # Seiten
                
                logger.debug(f"Journal gefunden (Muster): {journal}")
                return journal
    
    logger.debug("Kein Journal gefunden")
    return None


def extract_language_from_text(text: str, min_sample_size: int = 500) -> str:
    """
    Erkennt die Sprache eines Textes basierend auf Wörterstatistiken.
    
    Diese Funktion nutzt häufige Wörter und Artikel, um zu bestimmen,
    ob ein Text auf Deutsch oder Englisch verfasst ist.
    
    Args:
        text: Der zu analysierende Text
        min_sample_size: Minimale Anzahl zu analysierender Zeichen
        
    Returns:
        Sprachcode ('de', 'en' oder 'mixed')
    """
    logger.debug("Versuche Sprache aus Text zu extrahieren")
    
    # Stelle sicher, dass genug Text für eine zuverlässige Analyse vorhanden ist
    if not text or len(text) < min_sample_size:
        logger.debug(f"Text zu kurz für zuverlässige Spracherkennung ({len(text)} < {min_sample_size})")
        return "en"  # Standardwert
    
    # Probegröße begrenzen (für Performance)
    sample_text = text[:5000].lower()
    
    # Häufige Wörter und Artikel für jede Sprache
    de_words = ["der", "die", "das", "und", "ist", "von", "für", "auf", "mit", "dem", "sich", "des", "ein", "nicht", "auch", "es", "bei", "wird", "sind", "einer"]
    en_words = ["the", "and", "of", "to", "in", "is", "that", "for", "it", "as", "was", "with", "be", "by", "on", "not", "he", "this", "are", "from"]
    
    # Normalisierung für besseren Vergleich
    words = re.findall(r'\b\w+\b', sample_text)
    total_words = len(words)
    
    if total_words == 0:
        logger.debug("Keine Wörter gefunden")
        return "en"  # Standardwert
    
    # Zählen der deutschen und englischen Wörter
    de_count = sum(1 for word in words if word in de_words)
    en_count = sum(1 for word in words if word in en_words)
    
    # Berechnung der relativen Häufigkeiten
    de_ratio = de_count / total_words
    en_ratio = en_count / total_words
    
    # Wenn beide Sprachen etwa gleich stark vorhanden sind, könnte es ein gemischter Text sein
    mixed_threshold = 0.05  # 5% Unterschied
    if abs(de_ratio - en_ratio) < mixed_threshold and de_ratio > 0.05 and en_ratio > 0.05:
        logger.debug(f"Gemischter Text erkannt (DE: {de_ratio:.2f}, EN: {en_ratio:.2f})")
        return "mixed"
    
    # Sonst wähle die Sprache mit dem höheren Anteil
    if de_ratio > en_ratio:
        logger.debug(f"Deutsch erkannt (DE: {de_ratio:.2f}, EN: {en_ratio:.2f})")
        return "de"
    else:
        logger.debug(f"Englisch erkannt (DE: {de_ratio:.2f}, EN: {en_ratio:.2f})")
        return "en"


def extract_all_metadata_from_text(text: str, filepath: str = "") -> Dict[str, Any]:
    """
    Extrahiert alle verfügbaren Metadaten aus einem Text.
    
    Diese Funktion kombiniert alle Extraktionsmethoden, um einen umfassenden
    Metadatensatz aus einem Text zu erstellen.
    
    Args:
        text: Der zu analysierende Text
        filepath: Optionaler Pfad zur Datei
        
    Returns:
        Dictionary mit allen extrahierten Metadaten
    """
    logger.info(f"Extrahiere alle Metadaten aus Text{f' für {filepath}' if filepath else ''}")
    
    metadata = {}
    
    # Titel
    title = extract_title_from_text(text)
    if title:
        metadata["title"] = title
    
    # Autoren
    authors = extract_authors_from_text(text, filepath)
    if authors:
        metadata["author"] = authors
    
    # Jahr
    year = extract_year_from_text(text)
    if year:
        metadata["year"] = year
    
    # Sprache
    language = extract_language_from_text(text)
    metadata["language"] = language
    
    # DOI
    doi = extract_doi_from_text(text)
    if doi:
        metadata["doi"] = doi
    
    # ISBN
    isbn = extract_isbn_from_text(text)
    if isbn:
        metadata["isbn"] = isbn
    
    # Journal
    journal = extract_journal_from_text(text)
    if journal:
        metadata["journal"] = journal
    
    # Verlag
    publisher = extract_publisher_from_text(text)
    if publisher:
        metadata["publisher"] = publisher
    
    # Dateiinformationen
    if filepath:
        file_path = Path(filepath)
        metadata["filename"] = file_path.name
        metadata["file_extension"] = file_path.suffix
        metadata["file_size"] = file_path.stat().st_size
    
    logger.info(f"Extrahierte Metadaten: {', '.join(metadata.keys())}")
    return metadata


def string_similarity(str1: str, str2: str) -> float:
    """
    Berechnet die Ähnlichkeit zwischen zwei Strings.
    
    Diese Funktion verwendet verschiedene Metriken, um die Ähnlichkeit
    zwischen zwei Strings zu berechnen.
    
    Args:
        str1: Erster String
        str2: Zweiter String
        
    Returns:
        Ähnlichkeitswert zwischen 0.0 (völlig verschieden) und 1.0 (identisch)
    """
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