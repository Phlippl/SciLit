"""
Core-Module für SciLit
"""
from .document.processor import DocumentProcessor
from .document.parsers import DocumentParser, DocumentParsingError
from .metadata.formatter import MetadataFormatter  
from .analysis.text_splitter import TextSplitter  
from app.utils.file_utils import generate_unique_id  # Korrigiert von generate_document_id
from .metadata.formatter import format_citation  

# MetadataAPIClient scheint nicht zu existieren, wir sollten stattdessen die Factory nutzen
from app.api.MetadataAPIClientFactory import get_metadata_api_factory