"""
Zentrale Konfigurationsdatei für SciLit
---------------------------------------
Enthält alle Konfigurationseinstellungen, Konstanten und Umgebungsvariablen.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# .env-Datei für Umgebungsvariablen laden
load_dotenv()

# Basisverzeichnisse
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"
LOG_DIR = BASE_DIR / "logs"

# Verzeichnisse erstellen, falls sie nicht existieren
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# API-Schlüssel und URLs
CROSSREF_API_URL = "https://api.crossref.org/works"
OPENALEX_API_URL = "https://api.openalex.org/works"
OPENLIB_API_URL = "https://openlibrary.org/search.json"
GOOGLEBOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"
K10PLUS_API_URL = "https://sru.k10plus.de/opac-de-627"

# Google Books API Konfiguration
GOOGLEBOOKS_API_KEY = os.getenv("GOOGLEBOOKS_API_KEY", "")  # Leer lassen oder einen Schlüssel setzen, falls vorhanden

# Default-Optionen für Dokumentenverarbeitung
DEFAULT_PROCESSING_OPTIONS = {
    "ocr_if_needed": True,
    "language": "auto",
    "use_crossref": True,
    "use_openlib": True,
    "use_k10plus": True,
    "use_googlebooks": True,
    "use_openalex": True,
}

# SpaCy Modelle
SPACY_MODEL_DE = "de_core_news_sm"
SPACY_MODEL_EN = "en_core_web_sm"

# OCR-Sprachkonfiguration
OCR_LANGUAGES = {
    'de': 'deu',
    'en': 'eng',
    'auto': 'deu+eng',  # Mehrsprachenerkennung
    'mixed': 'deu+eng'  # Deutsch und Englisch
}

# Logging-Konfiguration
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOG_DIR / "scilit.log"

# Web-App-Konfiguration
APP_NAME = "SciLit"
APP_DESCRIPTION = "Wissenschaftliche Literaturverwaltung mit KI"
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", 8000))

# Chunk-Konfiguration für Textanalysis
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Maximale Dateigröße für Uploads (in Bytes)
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB

# Cache-Konfiguration
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 60 * 60 * 24  # 24 Stunden in Sekunden