import os
import datetime
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging
import uuid
import json

# Eigene Module importieren
from app.core.document_manager import get_document_manager

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("scilit")

# Verzeichnisse im Hauptverzeichnis
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

# Verzeichnisse erstellen
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Document Manager initialisieren
document_manager = get_document_manager(BASE_DIR)

# FastAPI-App erstellen
app = FastAPI(title="SciLit", description="Wissenschaftliche Literaturverwaltung mit KI")

# Statische Dateien und Templates konfigurieren
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Hintergrundverarbeitung von Dokumenten
def process_document_task(filename: str, options: Dict[str, Any]):
    """Verarbeitet ein Dokument im Hintergrund."""
    try:
        document_manager.process_document(filename, options)
        logger.info(f"Dokument {filename} erfolgreich verarbeitet")
    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung von {filename}: {str(e)}")

# Hilfsfunktion für Template-Kontext
def get_base_context(request: Request):
    """Fügt dem Template-Kontext Basiswerte hinzu, die in allen Templates benötigt werden."""
    return {
        "request": request,
        "year": datetime.datetime.now().year
    }

# Routen
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    context = get_base_context(request)
    
    # Füge die neuesten Dokumente hinzu
    documents = document_manager.get_all_documents()
    # Sortiere nach Hinzufügedatum (neueste zuerst)
    documents.sort(key=lambda x: x.get('added_at', ''), reverse=True)
    # Beschränke auf die neuesten 4
    recent_documents = documents[:4]
    
    context["recent_documents"] = recent_documents
    
    return templates.TemplateResponse("index.html", context)

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    context = get_base_context(request)
    return templates.TemplateResponse("upload.html", context)

@app.post("/upload")
async def upload_file(
    request: Request, 
    background_tasks: BackgroundTasks,  # Parameter hinzugefügt
    files: List[UploadFile] = File(...),
    extract_metadata: bool = Form(True),
    ocr_if_needed: bool = Form(True),
    language: str = Form("auto"),
    use_crossref: bool = Form(True),
    use_openlib: bool = Form(True),
    use_k10plus: bool = Form(True),
    use_googlebooks: bool = Form(True),
    use_openalex: bool = Form(True),
    skip_review: bool = Form(False)
):
    context = get_base_context(request)
    results = []
    
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
    
    # Wenn skip_review wahr ist, werden die Dateien direkt verarbeitet
    if skip_review:
        for file in files:
            try:
                # Datei speichern
                file_path = os.path.join(UPLOAD_DIR, file.filename)
                with open(file_path, "wb") as f:
                    contents = await file.read()
                    f.write(contents)
                
                # Hintergrundverarbeitung starten
                background_tasks.add_task(process_document_task, file.filename, processing_options)  # Hier background_tasks korrekt verwenden
                
                # Ergebnis hinzufügen
                results.append({
                    "filename": file.filename,
                    "size": len(contents),
                    "status": "uploaded",
                    "message": "Dokument wurde hochgeladen und wird im Hintergrund verarbeitet."
                })
                logger.info(f"Datei hochgeladen: {file.filename}")
                
            except Exception as e:
                logger.error(f"Fehler beim Upload von {file.filename}: {str(e)}")
                results.append({
                    "filename": file.filename,
                    "error": str(e),
                    "status": "failed"
                })
        
        context["results"] = results
        return templates.TemplateResponse("upload.html", context)

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    context = get_base_context(request)
    return templates.TemplateResponse("search.html", context)

@app.post("/search")
async def search_documents(request: Request, query: str = Form(...)):
    context = get_base_context(request)
    
    # Dummy-Ergebnisse für den Anfang
    results = [
        {
            "text": "Beispiel-Ergebnis 1 für die Anfrage: " + query,
            "source": "Beispiel-Paper (Smith et al., 2023)",
            "relevance": 0.95
        },
        {
            "text": "Beispiel-Ergebnis 2 für die Anfrage: " + query,
            "source": "Beispiel-Buch (Johnson, 2022)",
            "relevance": 0.85
        }
    ]
    
    context["query"] = query
    context["results"] = results
    context["search_type"] = "question"
    
    return templates.TemplateResponse("results.html", context)

@app.get("/documents", response_class=HTMLResponse)
async def list_documents(request: Request):
    context = get_base_context(request)
    
    # Alle Dokumente aus dem Manager holen
    documents = document_manager.get_all_documents()
    
    # Dokumente aufbereiten und nötige Felder hinzufügen
    for doc in documents:
        # Fehlende Felder mit Standardwerten auffüllen
        if 'author' not in doc['metadata'] or not doc['metadata']['author']:
            doc['metadata']['author'] = ['Unbekannt']
        elif isinstance(doc['metadata']['author'], str):
            doc['metadata']['author'] = [doc['metadata']['author']]
            
        if 'title' not in doc['metadata'] or not doc['metadata']['title']:
            doc['metadata']['title'] = os.path.basename(doc['filename'])
            
        if 'year' not in doc['metadata'] or not doc['metadata']['year']:
            doc['metadata']['year'] = 'Unbekannt'
            
        if 'source' not in doc['metadata'] or not doc['metadata']['source']:
            if 'journal' in doc['metadata'] and doc['metadata']['journal']:
                doc['metadata']['source'] = doc['metadata']['journal']
            elif 'publisher' in doc['metadata'] and doc['metadata']['publisher']:
                doc['metadata']['source'] = doc['metadata']['publisher']
            else:
                doc['metadata']['source'] = 'Unbekannt'
    
    # Statistiken
    stats = document_manager.get_statistics()
    
    context["documents"] = documents
    context["total_pages"] = stats["total_pages"]
    context["total_chunks"] = stats["total_chunks"]
    context["storage_used"] = stats["storage_used"]
    
    return templates.TemplateResponse("documents.html", context)

@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, doc_id: str):
    context = get_base_context(request)
    
    # Dokument aus dem Manager holen
    document = document_manager.get_document(doc_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    # Vollständige Metadaten und Chunks holen
    metadata = document_manager.get_document_metadata(doc_id)
    chunks = document_manager.get_document_chunks(doc_id)
    
    # Kontext vorbereiten
    context["document"] = document
    context["metadata"] = metadata
    context["chunks"] = chunks
    context["chunk_count"] = len(chunks)
    
    return templates.TemplateResponse("document_detail.html", context)

@app.get("/documents/{doc_id}/metadata", response_class=JSONResponse)
async def get_document_metadata(doc_id: str):
    # Metadaten abrufen
    metadata = document_manager.get_document_metadata(doc_id)
    
    if not metadata:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    return metadata

@app.post("/documents/{doc_id}/metadata")
async def update_document_metadata(doc_id: str, metadata: Dict[str, Any]):
    # Metadaten aktualisieren
    success = document_manager.update_document_metadata(doc_id, metadata)
    
    if not success:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden oder Aktualisierung fehlgeschlagen")
    
    return {"status": "success", "message": "Metadaten aktualisiert"}

# Diese Route zu main.py hinzufügen, nach der Definition der bestehenden Routen

@app.post("/documents/{doc_id}/reprocess")
async def reprocess_document(request: Request, doc_id: str, background_tasks: BackgroundTasks):
    """Verarbeitet ein bestehendes Dokument neu mit dem DocumentProcessor."""
    # Überprüfen, ob das Dokument existiert
    document = document_manager.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    try:
        # Dateinamen extrahieren
        filename = document['filename']
        
        # Optionen für die Verarbeitung
        options = {
            "ocr_if_needed": True,
            "language": document['metadata'].get('language', 'auto'),
            "use_crossref": True,
            "use_openlib": True,
            "use_k10plus": True,
            "use_googlebooks": True,
            "use_openalex": True
        }
        
        # Verarbeitung im Hintergrund starten
        background_tasks.add_task(process_document_task, filename, options)
        
        return {"status": "success", "message": f"Dokument {filename} wird im Hintergrund neu verarbeitet."}
    
    except Exception as e:
        logger.error(f"Fehler bei der Neuverarbeitung von {doc_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fehler bei der Neuverarbeitung: {str(e)}")


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    # Dokument löschen
    success = document_manager.delete_document(doc_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden oder Löschung fehlgeschlagen")
    
    return {"status": "success", "message": "Dokument gelöscht"}


@app.post("/extract-metadata")
async def extract_metadata(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Extrahiert Metadaten aus einer PDF-Datei, ohne sie vollständig zu verarbeiten.
    Gibt die extrahierten Metadaten zurück, damit der Benutzer sie überprüfen und bearbeiten kann.
    """
    context = get_base_context(request)
    
    try:
        # Temporäres Speichern der hochgeladenen Datei
        temp_file_path = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
        with open(temp_file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        
        # Metadaten extrahieren mit dem DocumentProcessor
        processor = document_manager.processor
        text, basic_metadata = processor.extract_content_and_metadata(temp_file_path)
        
        # Erweiterte Metadaten über APIs abrufen
        enhanced_metadata = processor.enhance_metadata(basic_metadata)
        
        # Löschen der temporären Datei
        os.remove(temp_file_path)
        
        # Rückgabe der extrahierten Metadaten
        return {
            "success": True,
            "filename": file.filename,
            "metadata": enhanced_metadata
        }
        
    except Exception as e:
        logger.error(f"Fehler bei der Metadatenextraktion von {file.filename}: {str(e)}")
        
        # Versuche, die temporäre Datei zu löschen, falls sie noch existiert
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        return {
            "success": False,
            "filename": file.filename,
            "error": str(e)
        }
    
    # Neuer Endpunkt für die Metadaten-Extraktionsseite
# Diese Funktion in die main.py Datei nach den bestehenden Routen einfügen

@app.get("/extract-metadata", response_class=HTMLResponse)
async def extract_metadata_page(request: Request):
    """Zeigt die Seite zur Extraktion von Metadaten aus PDF-Dateien an."""
    context = get_base_context(request)
    return templates.TemplateResponse("extract_metadata.html", context)

@app.get("/review-metadata", response_class=HTMLResponse)
async def review_metadata_page(request: Request, session: str):
    """Zeigt die Seite zur Überprüfung der extrahierten Metadaten aus hochgeladenen Dokumenten an."""
    context = get_base_context(request)
    
    # Session-Daten laden
    session_file = os.path.join(UPLOAD_DIR, f"session_{session}.json")
    
    if not os.path.exists(session_file):
        # Wenn die Session nicht existiert, zurück zur Upload-Seite leiten
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
    context = get_base_context(request)
    
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
                options = file_info["options"]
                
                # Starte die Verarbeitung im Hintergrund
                background_tasks.add_task(process_document_task, filename, options)
                
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
    
if __name__ == "__main__":
    # Browser automatisch öffnen (optional)
    import webbrowser
    import threading
    import time
    
    def open_browser():
        time.sleep(2)  # 2 Sekunden warten
        webbrowser.open('http://localhost:8000')
    
    # Browser in einem separaten Thread öffnen
    threading.Thread(target=open_browser).start()
    
    # Server starten
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)