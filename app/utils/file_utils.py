"""
Datei-Hilfsfunktionen für SciLit
--------------------------------
Enthält nützliche Funktionen für Dateisystem-Operationen.
"""

import os
import shutil
import hashlib
import tempfile
from typing import List, Optional, Tuple
from pathlib import Path
import logging

# Logger konfigurieren
logger = logging.getLogger("scilit.utils.file")

def get_file_size_str(size_bytes: int) -> str:
    """
    Konvertiert eine Dateigröße in Bytes in ein lesbares Format.
    
    Args:
        size_bytes: Größe in Bytes
        
    Returns:
        Formatierte Größe (z.B. "1.23 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    # Einheiten und Präfixe
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    size_float = float(size_bytes)
    
    while size_float >= 1024.0 and i < len(units) - 1:
        size_float /= 1024.0
        i += 1
    
    return f"{size_float:.2f} {units[i]}"

def compute_file_hash(filepath: str, algorithm: str = 'md5', block_size: int = 65536) -> str:
    """
    Berechnet einen Hash für eine Datei.
    
    Args:
        filepath: Pfad zur Datei
        algorithm: Hash-Algorithmus ('md5', 'sha1', 'sha256')
        block_size: Blockgröße für das Lesen der Datei
        
    Returns:
        Hexadezimal-String des Dateihashes
    """
    hash_algorithms = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha256': hashlib.sha256
    }
    
    if algorithm not in hash_algorithms:
        raise ValueError(f"Unbekannter Hash-Algorithmus: {algorithm}. " 
                         f"Verfügbare Algorithmen: {', '.join(hash_algorithms.keys())}")
    
    file_hash = hash_algorithms[algorithm]()
    
    try:
        with open(filepath, 'rb') as f:
            while True:
                data = f.read(block_size)
                if not data:
                    break
                file_hash.update(data)
                
        return file_hash.hexdigest()
    except Exception as e:
        logger.error(f"Fehler beim Berechnen des Hashes für {filepath}: {str(e)}")
        raise

def generate_unique_id(filepath: str, include_content: bool = False) -> str:
    """
    Erzeugt eine eindeutige ID für eine Datei basierend auf Name, Größe und Änderungszeit.
    Optional kann auch der Dateiinhalt berücksichtigt werden.
    
    Args:
        filepath: Pfad zur Datei
        include_content: Ob der Dateiinhalt berücksichtigt werden soll
        
    Returns:
        Eindeutige ID als Hexadezimalstring
    """
    file_path = Path(filepath)
    file_stats = file_path.stat()
    
    # Basis-Komponenten für die ID
    id_components = [
        file_path.name,
        str(file_stats.st_size),
        str(file_stats.st_mtime)
    ]
    
    # Optional den Inhalt hinzufügen (für kleine Dateien)
    if include_content and file_stats.st_size < 10 * 1024 * 1024:  # < 10 MB
        try:
            file_hash = compute_file_hash(filepath, algorithm='md5')
            id_components.append(file_hash)
        except Exception as e:
            logger.warning(f"Hash für Dateiinhalt nicht verfügbar: {str(e)}")
    
    # Eindeutige ID generieren
    id_string = "_".join(id_components)
    return hashlib.md5(id_string.encode()).hexdigest()[:12]

def safe_filename(filename: str) -> str:
    """
    Entfernt unsichere Zeichen aus einem Dateinamen.
    
    Args:
        filename: Originaler Dateiname
        
    Returns:
        Bereinigter Dateiname
    """
    # Entferne ungültige Zeichen
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Sonstige Bereinigungen
    filename = filename.strip()
    
    # Sicherstellen, dass ein gültiger Name zurückgegeben wird
    if not filename:
        filename = "unnamed_file"
    
    return filename

def copy_with_backup(source: str, destination: str) -> bool:
    """
    Kopiert eine Datei und erstellt eine Sicherungskopie des Ziels, falls es existiert.
    
    Args:
        source: Quellpfad
        destination: Zielpfad
        
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        dest_path = Path(destination)
        
        # Sicherungskopie erstellen, falls das Ziel existiert
        if dest_path.exists():
            backup_path = dest_path.with_suffix(dest_path.suffix + '.bak')
            shutil.copy2(destination, backup_path)
            logger.info(f"Sicherungskopie erstellt: {backup_path}")
        
        # Neue Datei kopieren
        shutil.copy2(source, destination)
        return True
    except Exception as e:
        logger.error(f"Fehler beim Kopieren von {source} nach {destination}: {str(e)}")
        return False

def create_temp_file(content: bytes = None, suffix: str = None) -> Tuple[str, tempfile.NamedTemporaryFile]:
    """
    Erstellt eine temporäre Datei mit optionalem Inhalt.
    
    Args:
        content: Optionaler Dateiinhalt
        suffix: Optionale Dateiendung
        
    Returns:
        Tuple mit Dateipfad und temporärem Dateiobjekt
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    
    if content:
        temp_file.write(content)
        temp_file.flush()
    
    return temp_file.name, temp_file

def list_files_by_type(directory: str, extensions: List[str] = None, recursive: bool = False) -> List[str]:
    """
    Listet Dateien in einem Verzeichnis nach Dateityp auf.
    
    Args:
        directory: Verzeichnispfad
        extensions: Liste der Dateiendungen (z.B. ['.pdf', '.docx'])
        recursive: Ob Unterverzeichnisse durchsucht werden sollen
        
    Returns:
        Liste der Dateipfade
    """
    path = Path(directory)
    file_list = []
    
    # Funktionen zum Filtern nach Dateiendungen
    def has_valid_extension(file: Path) -> bool:
        if not extensions:
            return True
        return file.suffix.lower() in extensions
    
    # Dateien sammeln
    if recursive:
        for file in path.glob('**/*'):
            if file.is_file() and has_valid_extension(file):
                file_list.append(str(file))
    else:
        for file in path.glob('*'):
            if file.is_file() and has_valid_extension(file):
                file_list.append(str(file))
    
    return file_list

def ensure_dir_exists(directory: str) -> bool:
    """
    Stellt sicher, dass ein Verzeichnis existiert, und erstellt es bei Bedarf.
    
    Args:
        directory: Verzeichnispfad
        
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Fehler beim Erstellen des Verzeichnisses {directory}: {str(e)}")
        return False

def get_file_extension(filename: str) -> str:
    """
    Gibt die Dateiendung in Kleinbuchstaben zurück.
    
    Args:
        filename: Dateiname
        
    Returns:
        Dateiendung (z.B. '.pdf')
    """
    return Path(filename).suffix.lower()