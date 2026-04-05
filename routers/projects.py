from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import shutil

from database import get_db, crud
from database.models import Project

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- HTML PAGES ---

@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, db: Session = Depends(get_db)):
    """Página de gerenciamento de projetos."""
    projects = crud.get_all_projects(db)
    
    # Adicionar estatísticas para cada projeto
    projects_with_stats = []
    for project in projects:
        project_dict = project.to_dict()
        project_dict["stats"] = crud.get_project_stats(db, project.id)
        projects_with_stats.append(project_dict)
    
    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={"projects": projects_with_stats}
    )


@router.get("/projects/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_page(project_id: str, request: Request, db: Session = Depends(get_db)):
    """Página de edição de projeto."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    videos = crud.get_videos_by_project(db, project_id)
    clips = crud.get_clips_by_project(db, project_id)
    stats = crud.get_project_stats(db, project_id)
    
    # Enriquecer vídeos com informações adicionais
    videos_data = []
    for video in videos:
        video_dict = video.to_dict()
        # Verificar se arquivo de upload existe
        video_dict["upload_exists"] = os.path.exists(video.upload_path) if video.upload_path else False
        # Verificar se transcrição existe
        video_dict["transcript_exists"] = os.path.exists(video.main_transcript_path) if video.main_transcript_path else False
        videos_data.append(video_dict)
    
    # Enriquecer clips com informações adicionais
    clips_data = []
    for clip in clips:
        clip_dict = clip.to_dict()
        # Verificar se arquivo de output existe
        clip_dict["output_exists"] = os.path.exists(clip.output_path) if clip.output_path else False
        clips_data.append(clip_dict)
    
    return templates.TemplateResponse(
        request=request,
        name="project_edit.html",
        context={
            "project": project.to_dict(),
            "videos": videos_data,
            "clips": clips_data,
            "stats": stats
        }
    )


# --- API ENDPOINTS ---

@router.get("/api/projects", response_class=JSONResponse)
async def list_projects(db: Session = Depends(get_db)):
    """Lista todos os projetos."""
    projects = crud.get_all_projects(db)
    return [p.to_dict() for p in projects]


@router.post("/api/projects", response_class=JSONResponse)
async def create_project_endpoint(
    name: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    """Cria um novo projeto."""
    # Validar nome
    if not name or len(name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Nome do projeto é obrigatório")
    
    project = crud.create_project(db, name=name.strip(), description=description)
    
    # Criar diretórios do projeto
    project_dir = f"projects/{project.id}"
    for subdir in ["uploads", "outputs", "tmp", "burned_sub", "subs_ass"]:
        os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)
    
    print(f"✅ Projeto criado: {project.name} (ID: {project.id})")
    return project.to_dict()


@router.get("/api/projects/{project_id}", response_class=JSONResponse)
async def get_project_endpoint(project_id: str, db: Session = Depends(get_db)):
    """Obtém detalhes de um projeto."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    # Adicionar estatísticas
    stats = crud.get_project_stats(db, project_id)
    project_dict = project.to_dict()
    project_dict["stats"] = stats
    
    return project_dict


@router.put("/api/projects/{project_id}", response_class=JSONResponse)
async def update_project_endpoint(
    project_id: str,
    name: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    """Atualiza um projeto."""
    project = crud.update_project(db, project_id, name=name, description=description)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    print(f"✅ Projeto atualizado: {project.name}")
    return project.to_dict()


@router.delete("/api/projects/{project_id}", response_class=JSONResponse)
async def delete_project_endpoint(project_id: str, db: Session = Depends(get_db)):
    """
    Deleta um projeto e todos os recursos associados (vídeos, clips, arquivos).
    """
    # Verificar se o projeto existe
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    project_name = project.name
    
    # Deletar do banco de dados (cascade automático para videos e clips)
    success = crud.delete_project(db, project_id)
    if not success:
        raise HTTPException(status_code=500, detail="Erro ao deletar projeto do banco de dados")
    
    # Deletar diretório do projeto e todos os arquivos
    project_dir = f"projects/{project_id}"
    if os.path.exists(project_dir):
        try:
            shutil.rmtree(project_dir)
            print(f"🗑️  Diretório do projeto removido: {project_dir}")
        except Exception as e:
            print(f"⚠️  Erro ao remover diretório do projeto: {e}")
    
    print(f"✅ Projeto deletado: {project_name} (ID: {project_id})")
    return {
        "message": "Projeto deletado com sucesso",
        "project_id": project_id,
        "project_name": project_name
    }


@router.get("/api/projects/{project_id}/videos", response_class=JSONResponse)
async def list_project_videos(project_id: str, db: Session = Depends(get_db)):
    """Lista todos os vídeos de um projeto."""
    videos = crud.get_videos_by_project(db, project_id)
    return [v.to_dict() for v in videos]


@router.get("/api/projects/{project_id}/clips", response_class=JSONResponse)
async def list_project_clips(project_id: str, db: Session = Depends(get_db)):
    """Lista todos os clips de um projeto."""
    clips = crud.get_clips_by_project(db, project_id)
    return [c.to_dict() for c in clips]
