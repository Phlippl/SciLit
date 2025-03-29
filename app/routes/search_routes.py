# Update für app/routes/search_routes.py

"""
Such-Routen für SciLit
---------------------
FastAPI-Routen für die Suche und Frage-Antwort-Funktionalität.
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Request, Form, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.search_service import get_search_service
from app.services.document_service import get_document_service

# Logger konfigurieren
logger = logging.getLogger("scilit.routes.search")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Zeigt die Suchseite an."""
    document_service = get_document_service()
    recent_searches = []  # Hier könnten die letzten Suchen geladen werden
    
    # Alle Dokumente für die Filteroptionen
    documents = document_service.get_all_documents()
    # Alle verfügbaren Jahre
    years = sorted(list(set(doc.get('metadata', {}).get('year', None) 
                         for doc in documents if doc.get('metadata', {}).get('year'))))
    
    return templates.TemplateResponse("search.html", {
        "request": request,
        "documents": documents,
        "available_years": years,
        "recent_searches": recent_searches
    })

@router.post("/search", response_class=HTMLResponse)
async def search_documents(
    request: Request,
    query: str = Form(...),
    search_type: str = Form("semantic"),
    citation_style: str = Form("apa"),
    sort_by: str = Form("relevance"),
    filter_document: str = Form(None),
    filter_year_min: str = Form(None),
    filter_year_max: str = Form(None),
    filter_author: str = Form(None),
    filter_source: str = Form(None),
    max_results: int = Form(10)
):
    """Führt eine Suche durch und zeigt die Ergebnisse an."""
    search_service = get_search_service()
    
    # Filter aufbauen
    filters = {}
    if filter_document:
        filters["document_id"] = filter_document
    if filter_year_min:
        filters["year_min"] = filter_year_min
    if filter_year_max:
        filters["year_max"] = filter_year_max
    if filter_author:
        filters["author"] = filter_author
    if filter_source:
        filters["source"] = filter_source
    
    # Suche basierend auf Typ durchführen
    if search_type == "question":
        search_result = search_service.answer_question(
            question=query,
            filters=filters,
            citation_style=citation_style
        )
        
        # Template-Kontext vorbereiten
        context = {
            "request": request,
            "query": query,
            "search_type": search_type,
            "results": search_result.get("chunks", []),
            "answer": search_result.get("answer", ""),
            "sources": search_result.get("sources", []),
            "citation_style": citation_style
        }
        
    elif search_type == "semantic":
        results = search_service.semantic_search(
            query=query,
            filters=filters,
            max_results=max_results
        )
        
        context = {
            "request": request,
            "query": query,
            "search_type": search_type,
            "results": results
        }
        
    else:  # Keyword-Suche
        results = search_service.keyword_search(
            query=query,
            filters=filters,
            max_results=max_results
        )
        
        context = {
            "request": request,
            "query": query,
            "search_type": search_type,
            "results": results
        }
    
    # Sortierung anwenden, wenn erforderlich
    if "results" in context and sort_by != "relevance":
        if sort_by == "date-desc":
            context["results"].sort(
                key=lambda x: x.get("metadata", {}).get("year", 0),
                reverse=True
            )
        elif sort_by == "date-asc":
            context["results"].sort(
                key=lambda x: x.get("metadata", {}).get("year", 0)
            )
    
    # Suche speichern (für "letzte Suchen")
    # Hier könnte der Code zum Speichern der Suche kommen
    
    return templates.TemplateResponse("results.html", context)

@router.get("/api/search", response_class=JSONResponse)
async def api_search(
    query: str,
    search_type: str = "semantic",
    filter_document: str = None,
    filter_year_min: str = None,
    filter_year_max: str = None,
    filter_author: str = None,
    filter_source: str = None,
    max_results: int = 10
):
    """API-Endpunkt für Suche, gibt Ergebnisse als JSON zurück."""
    search_service = get_search_service()
    
    # Filter aufbauen
    filters = {}
    if filter_document:
        filters["document_id"] = filter_document
    if filter_year_min:
        filters["year_min"] = filter_year_min
    if filter_year_max:
        filters["year_max"] = filter_year_max
    if filter_author:
        filters["author"] = filter_author
    if filter_source:
        filters["source"] = filter_source
    
    try:
        # Suche basierend auf Typ durchführen
        if search_type == "question":
            result = search_service.answer_question(
                question=query,
                filters=filters
            )
            return result
        elif search_type == "semantic":
            result = search_service.semantic_search(
                query=query,
                filters=filters,
                max_results=max_results
            )
            return {"results": result}
        else:  # Keyword-Suche
            result = search_service.keyword_search(
                query=query,
                filters=filters,
                max_results=max_results
            )
            return {"results": result}
    except Exception as e:
        logger.error(f"Fehler bei API-Suche: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Suchfehler: {str(e)}")

@router.get("/api/models", response_class=JSONResponse)
async def get_available_models():
    """Gibt verfügbare LLM-Modelle zurück."""
    search_service = get_search_service()
    
    try:
        # Dieser Aufruf erfordert die Ergänzung der Methode im SearchService
        models = search_service.ollama_client.get_available_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Modelle: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Abrufen der Modelle: {str(e)}")

@router.post("/api/set-model", response_class=JSONResponse)
async def set_model(model_name: str = Form(...)):
    """Legt das zu verwendende LLM-Modell fest."""
    search_service = get_search_service()
    
    try:
        success = search_service.ollama_client.set_model(model_name)
        if success:
            return {"success": True, "message": f"Modell auf {model_name} gewechselt"}
        else:
            raise HTTPException(status_code=400, detail=f"Modell {model_name} nicht verfügbar")
    except Exception as e:
        logger.error(f"Fehler beim Setzen des Modells: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Setzen des Modells: {str(e)}")

@router.get("/api/recent-searches", response_class=JSONResponse)
async def get_recent_searches(max_count: int = 5):
    """Gibt die letzten Suchen zurück."""
    # Hier könnte der Code zum Laden der letzten Suchen stehen
    # Für jetzt geben wir Dummy-Daten zurück
    recent_searches = [
        {"query": "Neuronale Netzwerke", "type": "keyword", "timestamp": "2025-03-25T14:30:00"},
        {"query": "Wie funktioniert Deep Learning?", "type": "question", "timestamp": "2025-03-24T10:15:00"}
    ]
    return {"searches": recent_searches[:max_count]}

@router.post("/api/save-search", response_class=JSONResponse)
async def save_search(
    query: str = Form(...),
    search_type: str = Form("semantic")
):
    """Speichert eine Suche für später."""
    # Hier könnte der Code zum Speichern der Suche stehen
    
    return {"success": True, "message": "Suche gespeichert"}