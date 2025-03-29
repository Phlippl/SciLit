"""
Fehlerbehandlung für SciLit
------------------------
Definiert benutzerdefinierte Ausnahmen und Hilfsfunktionen für die Fehlerbehandlung.
"""

import logging
import traceback
import sys
from typing import Optional, Dict, Any, Type

# Logger konfigurieren
logger = logging.getLogger("scilit.utils.errors")

class ScilitError(Exception):
    """
    Basisklasse für alle SciLit-spezifischen Ausnahmen.
    
    Attributes:
        message (str): Die Fehlermeldung
        error_code (str): Ein optionaler Fehlercode
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        """
        Initialisiert eine SciLit-Ausnahme.
        
        Args:
            message: Die Fehlermeldung
            error_code: Ein optionaler Fehlercode
        """
        self.message = message
        self.error_code = error_code
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertiert die Ausnahme in ein Dictionary für API-Antworten.
        
        Returns:
            Dictionary mit Fehlerdaten
        """
        error_dict = {
            "error": True,
            "message": self.message
        }
        
        if self.error_code:
            error_dict["error_code"] = self.error_code
        
        return error_dict

class DocumentProcessingError(ScilitError):
    """
    Fehler bei der Dokumentenverarbeitung.
    
    Attributes:
        document_name (str): Name des Dokuments, bei dem der Fehler aufgetreten ist
        processing_stage (str): Phase der Verarbeitung, in der der Fehler aufgetreten ist
    """
    
    def __init__(
        self, 
        message: str, 
        document_name: Optional[str] = None, 
        processing_stage: Optional[str] = None,
        error_code: Optional[str] = None
    ):
        """
        Initialisiert einen Dokumentenverarbeitungsfehler.
        
        Args:
            message: Die Fehlermeldung
            document_name: Name des betroffenen Dokuments
            processing_stage: Phase der Verarbeitung
            error_code: Ein optionaler Fehlercode
        """
        self.document_name = document_name
        self.processing_stage = processing_stage
        super().__init__(message, error_code or "DOCUMENT_PROCESSING_ERROR")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertiert die Ausnahme in ein Dictionary für API-Antworten.
        
        Returns:
            Dictionary mit Fehlerdaten
        """
        error_dict = super().to_dict()
        
        if self.document_name:
            error_dict["document_name"] = self.document_name
        
        if self.processing_stage:
            error_dict["processing_stage"] = self.processing_stage
        
        return error_dict

class APIError(ScilitError):
    """
    Fehler bei API-Anfragen.
    
    Attributes:
        api_name (str): Name der API, bei der der Fehler aufgetreten ist
        status_code (int): HTTP-Statuscode (falls zutreffend)
    """
    
    def __init__(
        self, 
        message: str, 
        api_name: Optional[str] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None
    ):
        """
        Initialisiert einen API-Fehler.
        
        Args:
            message: Die Fehlermeldung
            api_name: Name der betroffenen API
            status_code: HTTP-Statuscode (falls zutreffend)
            error_code: Ein optionaler Fehlercode
        """
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(message, error_code or "API_ERROR")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertiert die Ausnahme in ein Dictionary für API-Antworten.
        
        Returns:
            Dictionary mit Fehlerdaten
        """
        error_dict = super().to_dict()
        
        if self.api_name:
            error_dict["api_name"] = self.api_name
        
        if self.status_code:
            error_dict["status_code"] = self.status_code
        
        return error_dict

class ConfigurationError(ScilitError):
    """Fehler in der Konfiguration oder beim Starten der Anwendung."""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        """
        Initialisiert einen Konfigurationsfehler.
        
        Args:
            message: Die Fehlermeldung
            error_code: Ein optionaler Fehlercode
        """
        super().__init__(message, error_code or "CONFIGURATION_ERROR")

def handle_exception(
    exception: Exception, 
    log_level: int = logging.ERROR, 
    reraise: bool = False,
    default_error_class: Type[ScilitError] = ScilitError
) -> Optional[Dict[str, Any]]:
    """
    Behandelt eine Ausnahme einheitlich.
    
    Diese Funktion protokolliert die Ausnahme, konvertiert sie optional in ein
    Dictionary für API-Antworten und wirft sie bei Bedarf weiter.
    
    Args:
        exception: Die zu behandelnde Ausnahme
        log_level: Log-Level für die Protokollierung
        reraise: Ob die Ausnahme weitergeworfen werden soll
        default_error_class: Standardklasse für nicht-SciLit-Ausnahmen
        
    Returns:
        Dictionary mit Fehlerdaten oder None, wenn reraise=True
        
    Raises:
        Die übergebene Ausnahme, wenn reraise=True
    """
    # Exception zum Log hinzufügen
    exc_info = sys.exc_info()
    logger.log(log_level, f"Ausnahme gefangen: {str(exception)}", exc_info=exc_info if log_level >= logging.ERROR else None)
    
    # Umwandlung in SciLit-spezifische Ausnahme, falls nötig
    if not isinstance(exception, ScilitError):
        error = default_error_class(str(exception))
    else:
        error = exception
    
    # Weiterwerfen, falls gewünscht
    if reraise:
        raise error
    
    # Als Dictionary für API-Antworten zurückgeben
    return error.to_dict()

def format_exception(exception: Exception, include_traceback: bool = False) -> str:
    """
    Formatiert eine Ausnahme für die Anzeige.
    
    Args:
        exception: Die zu formatierende Ausnahme
        include_traceback: Ob der Stacktrace enthalten sein soll
        
    Returns:
        Formatierte Fehlermeldung als String
    """
    if include_traceback:
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    else:
        return f"{exception.__class__.__name__}: {str(exception)}"