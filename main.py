import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# Importa database
from database import init_db, get_db
from database import crud
from scripts.utils import get_videos_processed, get_time_saved, get_success_clips

# Importa routers
from routers import projects, videos, outputs

# --- CONFIGURAÇÃO DA APLICAÇÃO ---
app = FastAPI()

# Inicializa o banco de dados
@app.on_event("startup")
async def startup_event():
    init_db()
    print("🚀 ViralCutter iniciado com sistema de projetos (Refatorado)")

# Garante que os diretórios existam (mantém estrutura legada temporariamente)
os.makedirs("uploads", exist_ok=True); os.makedirs("outputs", exist_ok=True); os.makedirs("tmp", exist_ok=True)
os.makedirs("burned_sub", exist_ok=True); os.makedirs("subs_ass", exist_ok=True)
# Cria diretório de projetos
os.makedirs("projects", exist_ok=True)

# Mounts de arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/clips", StaticFiles(directory="tmp"), name="clips")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# CORREÇÃO DO CONFLITO: Mudando de /projects para /media/projects
app.mount("/media/projects", StaticFiles(directory="projects"), name="projects_media")

templates = Jinja2Templates(directory="templates")

# Inclui os routers
app.include_router(projects.router)
app.include_router(videos.router)
app.include_router(outputs.router)

# --- ENDPOINTS PRINCIPAIS (RAIZ) ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    projects_list = crud.get_all_projects(db)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "videos_processed": get_videos_processed(),
            "time_saved": get_time_saved(),
            "success_clips": get_success_clips(),
            "projects": projects_list
        }
    )