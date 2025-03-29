# Neue Datei: app/core/llm/ollama_client.py

"""
Ollama LLM Client für SciLit
-------------------------
Client für die Kommunikation mit dem lokalen Ollama-Service für LLM-Anfragen.
"""

import json
import logging
import requests
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger("scilit.llm.ollama")

class OllamaClient:
    """
    Client für die Kommunikation mit dem Ollama LLM-Service.
    
    Ollama ermöglicht die lokale Ausführung von großen Sprachmodellen wie Llama.
    Diese Klasse bietet eine Schnittstelle für Anfragen an den Ollama-Service.
    
    Attributes:
        api_url (str): URL des Ollama-Services
        model (str): Name des zu verwendenden LLM-Modells
        context_size (int): Maximale Kontextgröße des Modells
    """
    
    def __init__(self, api_url: str = "http://localhost:11434", model: str = "llama2"):
        """
        Initialisiert den Ollama LLM Client.
        
        Args:
            api_url: URL des Ollama API-Endpunkts
            model: Name des zu verwendenden Modells
        """
        self.api_url = api_url
        self.model = model
        self.context_size = 4096  # Standard-Kontextgröße für die meisten Modelle
        
        logger.debug(f"OllamaClient initialisiert mit URL={api_url}, Modell={model}")
    
    def generate_response(self, 
                          prompt: str, 
                          context: Optional[List[Dict[str, Any]]] = None,
                          temperature: float = 0.7,
                          max_tokens: int = 1024) -> str:
        """
        Generiert eine Antwort auf einen Prompt mit optionalem Kontext.
        
        Args:
            prompt: Der Prompt für das LLM
            context: Optionaler Kontext (z.B. relevante Textstellen)
            temperature: Kreativität der Antwort (0.0 - 1.0)
            max_tokens: Maximale Länge der Antwort in Tokens
            
        Returns:
            Generierte Antwort als String
        """
        # Kontext in den Prompt einbauen, falls vorhanden
        full_prompt = self._build_prompt_with_context(prompt, context) if context else prompt
        
        try:
            # API-Anfrage vorbereiten
            url = f"{self.api_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            # Anfrage senden
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            # Antwort verarbeiten
            result = response.json()
            if "response" in result:
                return result["response"].strip()
            else:
                logger.error(f"Unerwartetes Antwortformat von Ollama: {result}")
                return "Fehler bei der Generierung der Antwort."
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler bei der Kommunikation mit Ollama: {str(e)}")
            return f"Fehler bei der Kommunikation mit dem LLM-Service: {str(e)}"
    
    def _build_prompt_with_context(self, 
                                  question: str, 
                                  context: List[Dict[str, Any]]) -> str:
        """
        Baut einen Prompt mit Kontext auf, um dem LLM Referenzmaterial zu geben.
        
        Args:
            question: Die Frage des Benutzers
            context: Liste von relevanten Textstellen mit Metadaten
            
        Returns:
            Vollständiger Prompt mit Kontext
        """
        # Format anpassen je nach verwendetem LLM und Aufgabe
        prompt_parts = ["Du bist ein wissenschaftlicher Assistent, der auf Grundlage folgender Quellen Fragen beantwortet. Verwende ausschließlich die gegebenen Quellen für deine Antwort und füge Kurzzitate in der Form (Autor, Jahr, S. X) ein."]
        
        prompt_parts.append("\n\n### Quellen:\n")
        
        # Kontext hinzufügen mit Quellenangaben
        for i, item in enumerate(context, 1):
            source_info = f"[{i}] "
            
            # Autor(en) hinzufügen
            if "author" in item and item["author"]:
                if isinstance(item["author"], list):
                    authors = ", ".join(item["author"][:3])
                    if len(item["author"]) > 3:
                        authors += " et al."
                    source_info += f"{authors}"
                else:
                    source_info += f"{item['author']}"
            
            # Jahr hinzufügen
            if "year" in item and item["year"]:
                source_info += f" ({item['year']})"
            
            # Titel hinzufügen
            if "title" in item and item["title"]:
                source_info += f": {item['title']}"
            
            # Quelltext hinzufügen
            if "text" in item and item["text"]:
                content = item["text"].strip()
                # Längere Texte kürzen, um in den Kontext zu passen
                if len(content) > 1000:
                    content = content[:997] + "..."
                prompt_parts.append(f"{source_info}\n{content}\n")
        
        # Frage am Ende hinzufügen
        prompt_parts.append("\n### Frage:\n" + question)
        
        # Aufforderung zur Antwort
        prompt_parts.append("\n### Antwort:\n")
        
        return "\n".join(prompt_parts)
    
    def get_available_models(self) -> List[str]:
        """
        Ruft die Liste der verfügbaren Modelle vom Ollama-Service ab.
        
        Returns:
            Liste der verfügbaren Modellnamen
        """
        try:
            url = f"{self.api_url}/api/tags"
            response = requests.get(url)
            response.raise_for_status()
            
            result = response.json()
            if "models" in result:
                return [model["name"] for model in result["models"]]
            else:
                logger.warning(f"Unerwartetes Format bei Modellabfrage: {result}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen der Modelle: {str(e)}")
            return []
    
    def set_model(self, model_name: str) -> bool:
        """
        Ändert das aktive LLM-Modell.
        
        Args:
            model_name: Name des zu verwendenden Modells
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        # Prüfen, ob das Modell existiert
        available_models = self.get_available_models()
        if model_name not in available_models:
            logger.warning(f"Modell {model_name} nicht verfügbar. Verfügbare Modelle: {available_models}")
            return False
        
        self.model = model_name
        logger.info(f"Modell gewechselt zu: {model_name}")
        return True

# Singleton-Instanz
_ollama_instance = None

def get_ollama_client() -> OllamaClient:
    """
    Gibt eine Singleton-Instanz des OllamaClient zurück.
    
    Returns:
        OllamaClient-Instanz
    """
    global _ollama_instance
    if _ollama_instance is None:
        _ollama_instance = OllamaClient()
    return _ollama_instance