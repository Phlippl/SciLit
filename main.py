import os
import datetime
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from typing import List, Optional
from pydantic import BaseModel
import logging

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

# FastAPI-App erstellen
app = FastAPI(title="SciLit", description="Wissenschaftliche Literaturverwaltung mit KI")

# Statische Dateien und Templates konfigurieren
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Datenmodelle
class SearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 10

class Document(BaseModel):
    id: str
    title: str
    authors: List[str]
    year: Optional[int] = None
    source: str
    file_path: str

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
    return templates.TemplateResponse("index.html", context)

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    context = get_base_context(request)
    return templates.TemplateResponse("upload.html", context)

@app.post("/upload")
async def upload_file(request: Request, files: List[UploadFile] = File(...)):
    context = get_base_context(request)
    results = []
    
    for file in files:
        try:
            # Datei speichern
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                contents = await file.read()
                f.write(contents)
            
            # Ergebnis hinzufügen
            results.append({
                "filename": file.filename,
                "size": len(contents),
                "status": "uploaded"
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
    
    # Dummy-Dokumente für den Anfang
    documents = [
        Document(
            id="doc1",
            title="Beispiel-Paper über KI",
            authors=["Smith, J.", "Johnson, A."],
            year=2023,
            source="Journal of AI Research",
            file_path="example1.pdf"
        ),
        Document(
            id="doc2",
            title="Maschinelles Lernen in der Praxis",
            authors=["Müller, T."],
            year=2022,
            source="Springer",
            file_path="example2.pdf"
        )
    ]
    
    context["documents"] = documents
    return templates.TemplateResponse("documents.html", context)

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