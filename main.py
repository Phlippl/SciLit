"""
SciLit Hauptanwendung
--------------------
FastAPI-Hauptanwendung für die SciLit-Plattform.
"""

import logging
import datetime
import os
import json
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Importe aus app-Modulen
from app.config import (
    APP_NAME, APP_DESCRIPTION, DEBUG, HOST, PORT, 
    STATIC_DIR, TEMPLATES_DIR, UPLOAD_DIR, LOG_FORMAT, LOG_LEVEL
)
from app.services.document_service import get_document_service
from app.services.search_service import get_search_service
from app.utils.error_handling import handle_exception
from app.routes import search_routes

# Logging konfigurieren
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT
)
logger = logging.getLogger("scilit")

# Verzeichnisse erstellen, falls sie nicht existieren
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

# Services initialisieren
document_service = get_document_service()
search_service = get_search_service()

# FastAPI-App erstellen
app = FastAPI(title=APP_NAME, description=APP_DESCRIPTION)

# Statische Dateien und Templates konfigurieren
logger.info(f"Statische Dateien aus: {STATIC_DIR}")
logger.info(f"Templates aus: {TEMPLATES_DIR}")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Routen aus anderen Modulen einbinden
app.include_router(search_routes.router)

# Hintergrundverarbeitung von Dokumenten
def process_document_task(filepath: str, options: Dict[str, Any]):
    """Verarbeitet ein Dokument im Hintergrund und aktualisiert den Status."""
    try:
        # Process the document
        result = document_service.process_uploaded_document(filepath, options)
        doc_id = result.get("id")
        
        # Update the processing status
        if doc_id:
            # Set a flag in a status file to indicate processing is complete
            status_path = os.path.join(PROCESSED_DIR, doc_id, "processing_complete")
            with open(status_path, "w") as f:
                f.write("complete")
            
        logger.info(f"Dokument {filepath} erfolgreich verarbeitet, ID: {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung von {filepath}: {str(e)}")
        return False

# Hilfsfunktion für Template-Kontext
def get_base_context(request: Request):
    """Fügt dem Template-Kontext Basiswerte hinzu."""
    return {
        "request": request,
        "year": datetime.datetime.now().year
    }

#
# Hauptrouten
#

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Startseite mit Übersicht der neuesten Dokumente."""
    context = get_base_context(request)
    
    # Die neuesten Dokumente hinzufügen
    documents = document_service.get_all_documents()
    # Sortiere nach Hinzufügedatum (neueste zuerst)
    documents.sort(key=lambda x: x.get('added_at', ''), reverse=True)
    # Beschränke auf die neuesten 4
    recent_documents = documents[:4]
    
    context["recent_documents"] = recent_documents
    
    return templates.TemplateResponse("index.html", context)

#
# Upload-bezogene Routen
#

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Zeigt die Dokument-Upload-Seite an."""
    context = get_base_context(request)
    return templates.TemplateResponse("upload.html", context)

@app.post("/upload")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    extract_metadata: bool = Form(True),
    ocr_if_needed: bool = Form(True),
    language: str = Form("auto"),
    use_crossref: bool = Form(True),
    use_openlib: bool = Form(True),
    use_k10plus: bool = Form(True),
    use_googlebooks: bool = Form(True),
    use_openalex: bool = Form(True)
):
    """Nimmt Dokumente direkt entgegen und verarbeitet sie."""
    # Verarbeitungsoptionen
    processing_options = {
        "ocr_if_needed": ocr_if_needed,
        "language": language,
        "use_crossref": use_crossref,
        "use_openlib": use_openlib,
        "use_k10plus": use_k10plus,
        "use_googlebooks": use_googlebooks,
        "use_openalex": use_openalex
    }
    
    results = []
    
    # Dateien verarbeiten
    for file in files:
        try:
            # Datei speichern
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                contents = await file.read()
                f.write(contents)
                
            # Dokument im Hintergrund verarbeiten
            background_tasks.add_task(process_document_task, file_path, processing_options)
            
            results.append({
                "filename": file.filename,
                "status": "processing",
                "message": "Wird im Hintergrund verarbeitet"
            })
            
            logger.info(f"Datei hochgeladen und Verarbeitung gestartet: {file.filename}")
            
        except Exception as e:
            logger.error(f"Fehler beim Upload von {file.filename}: {str(e)}")
            results.append({
                "filename": file.filename,
                "status": "error",
                "message": str(e)
            })
    
    # Umleitung zur Dokumentenliste
    return RedirectResponse(url="/documents", status_code=303)

@app.get("/api/document_status/{doc_id}")
async def get_document_status(doc_id: str):
    """Prüft den Verarbeitungsstatus eines Dokuments."""
    # Check if document exists
    document = document_service.get_document(doc_id)
    if document:
        return {"status": "complete", "document": document}
    
    # Check if document is being processed
    status_path = os.path.join(PROCESSED_DIR, doc_id, "processing_complete")
    if os.path.exists(status_path):
        # Document exists but hasn't been loaded in memory yet
        return {"status": "complete", "reload": True}
    
    # Document is still processing or doesn't exist
    return {"status": "processing"}

@app.post("/upload-with-review")
async def upload_for_review(
    request: Request,
    files: List[UploadFile] = File(...),
    extract_metadata: bool = Form(True),
    ocr_if_needed: bool = Form(True),
    language: str = Form("auto"),
    use_crossref: bool = Form(True),
    use_openlib: bool = Form(True),
    use_k10plus: bool = Form(True),
    use_googlebooks: bool = Form(True),
    use_openalex: bool = Form(True)
):
    """Lädt Dateien hoch und extrahiert Metadaten für die Überprüfung."""
    # Erstelle eine eindeutige Session-ID
    session_id = str(uuid.uuid4())
    uploaded_files = []
    
    # Verarbeitungsoptionen
    processing_options = {
        "ocr_if_needed": ocr_if_needed,
        "language": language,
        "use_crossref": use_crossref,
        "use_openlib": use_openlib,
        "use_k10plus": use_k10plus,
        "use_googlebooks": use_googlebooks,
        "use_openalex": use_openalex
    }
    
    # Dateien verarbeiten
    for file in files:
        try:
            # Datei speichern
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                contents = await file.read()
                f.write(contents)
            
            # Metadaten extrahieren
            try:
                # Verwende den DocumentService für die Extraktion
                text, basic_metadata = document_service.document_processor.extract_content_and_metadata(file_path)
                enhanced_metadata = document_service.document_processor.enhance_metadata(basic_metadata)
                
                uploaded_files.append({
                    "filename": file.filename,
                    "size": len(contents),
                    "status": "uploaded",
                    "metadata": enhanced_metadata,
                    "options": processing_options
                })
                
            except Exception as e:
                logger.error(f"Fehler bei der Metadatenextraktion von {file.filename}: {str(e)}")
                uploaded_files.append({
                    "filename": file.filename,
                    "size": len(contents),
                    "status": "failed",
                    "error": f"Fehler bei der Metadatenextraktion: {str(e)}"
                })
            
            logger.info(f"Datei für Metadatenüberprüfung hochgeladen: {file.filename}")
            
        except Exception as e:
            logger.error(f"Fehler beim Upload von {file.filename}: {str(e)}")
            uploaded_files.append({
                "filename": file.filename,
                "error": str(e),
                "status": "failed"
            })
    
    # Speichere die Session-Daten
    session_file = os.path.join(UPLOAD_DIR, f"session_{session_id}.json")
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(uploaded_files, f, ensure_ascii=False, indent=2)
    
    # Weiterleitung zur Überprüfungsseite
    return RedirectResponse(url=f"/review-metadata?session={session_id}", status_code=303)

@app.get("/review-metadata", response_class=HTMLResponse)
async def review_metadata_page(request: Request, session: str):
    """Zeigt die Seite zur Überprüfung der extrahierten Metadaten an."""
    context = get_base_context(request)
    
    # Session-Daten laden
    session_file = os.path.join(UPLOAD_DIR, f"session_{session}.json")
    
    if not os.path.exists(session_file):
        logger.error(f"Session-Datei nicht gefunden: {session_file}")
        return RedirectResponse(url="/upload", status_code=303)
    
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            uploaded_files_data = json.load(f)
        
        context["session_id"] = session
        context["uploaded_files"] = uploaded_files_data
        
        return templates.TemplateResponse("review_metadata.html", context)
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Session-Daten: {str(e)}")
        return RedirectResponse(url="/upload", status_code=303)

@app.post("/process-reviewed-files")
async def process_reviewed_files(
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    file_data: str = Form(...)  # JSON-String mit den überprüften Metadaten
):
    """Verarbeitet die überprüften Dateien mit ihren aktualisierten Metadaten."""
    # Session-Datei finden
    session_file = os.path.join(UPLOAD_DIR, f"session_{session_id}.json")
    
    if not os.path.exists(session_file):
        return JSONResponse(content={
            "success": False,
            "error": "Session nicht gefunden."
        })
    
    try:
        # Überprüfte Dateidaten verarbeiten
        reviewed_files = json.loads(file_data)
        results = []
        
        for file_info in reviewed_files:
            try:
                filename = file_info["filename"]
                filepath = os.path.join(UPLOAD_DIR, filename)
                options = file_info.get("options", {})
                
                # Starte die Verarbeitung im Hintergrund
                background_tasks.add_task(process_document_task, filepath, options)
                
                results.append({
                    "filename": filename,
                    "status": "processing"
                })
                
            except Exception as e:
                logger.error(f"Fehler bei der Verarbeitung von {file_info.get('filename', 'unbekannt')}: {str(e)}")
                results.append({
                    "filename": file_info.get('filename', 'unbekannt'),
                    "status": "failed",
                    "error": str(e)
                })
        
        # Session-Datei löschen
        try:
            os.remove(session_file)
        except:
            logger.warning(f"Konnte Session-Datei nicht löschen: {session_file}")
        
        # Erfolgsmeldung zurückgeben
        return JSONResponse(content={
            "success": True,
            "message": "Dateien werden verarbeitet und in die Bibliothek aufgenommen.",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Fehler beim Verarbeiten der überprüften Dateien: {str(e)}")
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })

@app.post("/extract-metadata")
async def extract_metadata(
    request: Request,
    file: UploadFile = File(...)
):
    """Extrahiert Metadaten aus einer PDF-Datei ohne vollständige Verarbeitung."""
    try:
        # Temporäres Speichern der hochgeladenen Datei
        temp_file_path = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
        with open(temp_file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        
        # Metadaten extrahieren mit dem DocumentService
        text, basic_metadata = document_service.document_processor.extract_content_and_metadata(temp_file_path)
        enhanced_metadata = document_service.document_processor.enhance_metadata(basic_metadata)
        
        # Löschen der temporären Datei
        os.unlink(temp_file_path)
        
        # Rückgabe der extrahierten Metadaten
        return {
            "success": True,
            "filename": file.filename,
            "metadata": enhanced_metadata
        }
        
    except Exception as e:
        error_info = handle_exception(e)
        logger.error(f"Fehler bei der Metadatenextraktion von {file.filename}: {str(e)}")
        
        # Versuche, die temporäre Datei zu löschen, falls sie noch existiert
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            
        return {
            "success": False,
            "filename": file.filename,
            "error": str(e)
        }

@app.get("/extract-metadata", response_class=HTMLResponse)
async def extract_metadata_page(request: Request):
    """Zeigt die Metadatenextraktion-Seite an."""
    context = get_base_context(request)
    return templates.TemplateResponse("extract_metadata.html", context)

#
# Dokument-bezogene Routen
#

@app.get("/documents", response_class=HTMLResponse)
async def list_documents(request: Request):
    """Zeigt eine Liste aller Dokumente in der Bibliothek an."""
    context = get_base_context(request)
    
    # Alle Dokumente aus dem DocumentService holen
    documents = document_service.get_all_documents()
    
    # Dokumente aufbereiten und nötige Felder hinzufügen
    for doc in documents:
        # Fehlende Felder mit Standardwerten auffüllen
        metadata = doc.get('metadata', {})
        if 'author' not in metadata or not metadata['author']:
            metadata['author'] = ['Unbekannt']
        elif isinstance(metadata['author'], str):
            metadata['author'] = [metadata['author']]
            
        if 'title' not in metadata or not metadata['title']:
            metadata['title'] = os.path.basename(doc.get('filename', 'Unbekannt'))
            
        if 'year' not in metadata or not metadata['year']:
            metadata['year'] = 'Unbekannt'
            
        if 'source' not in metadata:
            if 'journal' in metadata and metadata['journal']:
                metadata['source'] = metadata['journal']
            elif 'publisher' in metadata and metadata['publisher']:
                metadata['source'] = metadata['publisher']
            else:
                metadata['source'] = 'Unbekannt'
    
    # Statistiken
    stats = document_service.get_statistics()
    
    context["documents"] = documents
    context["total_pages"] = stats.get("total_pages", 0)
    context["total_chunks"] = stats.get("total_chunks", 0)
    context["storage_used"] = stats.get("storage_used", "0 B")
    
    return templates.TemplateResponse("documents.html", context)

@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, doc_id: str):
    """Zeigt die Detailansicht eines Dokuments an."""
    context = get_base_context(request)
    
    # Dokument aus dem DocumentService holen
    document = document_service.get_document(doc_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    # Vollständige Metadaten und Chunks holen
    metadata = document_service.get_document_metadata(doc_id)
    chunks = document_service.get_document_chunks(doc_id)
    
    # Kontext vorbereiten
    context["document"] = document
    context["metadata"] = metadata
    context["chunks"] = chunks
    context["chunk_count"] = len(chunks)
    
    return templates.TemplateResponse("document_detail.html", context)

@app.post("/documents/{doc_id}/metadata")
async def update_document_metadata(
    doc_id: str, 
    title: Optional[str] = Form(None),
    authors: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    journal: Optional[str] = Form(None),
    publisher: Optional[str] = Form(None),
    doi: Optional[str] = Form(None),
    isbn: Optional[str] = Form(None)
):
    """Aktualisiert die Metadaten eines Dokuments."""
    # Metadaten zusammenbauen
    metadata = {}
    if title:
        metadata["title"] = title
    if authors:
        metadata["author"] = [author.strip() for author in authors.split(',')]
    if year:
        try:
            metadata["year"] = int(year)
        except:
            metadata["year"] = year
    if journal:
        metadata["journal"] = journal
    if publisher:
        metadata["publisher"] = publisher
    if doi:
        metadata["doi"] = doi
    if isbn:
        metadata["isbn"] = isbn
    
    # Metadaten aktualisieren
    success = document_service.update_document_metadata(doc_id, metadata)
    
    if not success:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden oder Aktualisierung fehlgeschlagen")
    
    # Zurück zur Dokument-Detailseite
    return RedirectResponse(url=f"/documents/{doc_id}", status_code=303)

@app.post("/documents/{doc_id}/reprocess", response_class=JSONResponse)
async def reprocess_document(doc_id: str, background_tasks: BackgroundTasks):
    """Verarbeitet ein bestehendes Dokument neu mit dem DocumentProcessor."""
    try:
        # Dokument im Hintergrund neu verarbeiten
        background_tasks.add_task(
            document_service.reprocess_document,
            doc_id,
            None  # Standard-Optionen verwenden
        )
        
        return {
            "success": True,
            "message": f"Dokument wird im Hintergrund neu verarbeitet."
        }
    
    except Exception as e:
        error_info = handle_exception(e)
        return {
            "success": False,
            "error": str(e)
        }

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Löscht ein Dokument und alle zugehörigen Dateien."""
    # Dokument löschen
    success = document_service.delete_document(doc_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden oder Löschung fehlgeschlagen")
    
    return {"success": True, "message": "Dokument gelöscht"}

if __name__ == "__main__":
    # Browser automatisch öffnen (optional)
    import webbrowser
    import threading
    import time
    
    def open_browser():
        time.sleep(2)  # 2 Sekunden warten
        webbrowser.open(f'http://{HOST}:{PORT}')
    
    # Browser in einem separaten Thread öffnen
    threading.Thread(target=open_browser).start()
    
    # Server starten
    uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG)