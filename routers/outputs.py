from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import zipfile

from database import get_db, crud

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/outputs", response_class=HTMLResponse)
async def list_outputs(request: Request, project_id: str = None, db: Session = Depends(get_db)):
    """
    Lista vídeos de saída. Se project_id for fornecido, filtra por projeto.
    Caso contrário, lista todos os vídeos.
    """
    projects = crud.get_all_projects(db)
    
    if project_id:
        # Filtrar clips por projeto específico
        clips = crud.get_clips_by_project(db, project_id)
        # Filtrar apenas clips que têm output_path
        videos_data = []
        for clip in clips:
            if clip.output_path and os.path.exists(clip.output_path):
                videos_data.append({
                    "filename": os.path.basename(clip.output_path),
                    "path": clip.output_path,
                    "title": clip.title,
                    "project_id": clip.project_id,
                    "created_at": clip.created_at
                })
        # Ordenar por data de criação (mais recente primeiro)
        videos_data.sort(key=lambda x: x["created_at"], reverse=True)
    else:
        # Listar todos os clips de todos os projetos
        videos_data = []
        for project in projects:
            clips = crud.get_clips_by_project(db, project.id)
            for clip in clips:
                if clip.output_path and os.path.exists(clip.output_path):
                    videos_data.append({
                        "filename": os.path.basename(clip.output_path),
                        "path": clip.output_path,
                        "title": clip.title,
                        "project_id": clip.project_id,
                        "created_at": clip.created_at
                    })
        # Ordenar por data de criação (mais recente primeiro)
        videos_data.sort(key=lambda x: x["created_at"], reverse=True)
    
    return templates.TemplateResponse(
        request=request,
        name="outputs.html",
        context={
            "videos": videos_data,
            "projects": projects,
            "selected_project_id": project_id
        }
    )


@router.get("/download/{filename}")
async def download_video(filename: str, db: Session = Depends(get_db)):
    """
    Baixa um vídeo. Procura primeiro nos projetos, depois no diretório legado.
    """
    # Primeiro, tentar encontrar o clip no banco de dados
    all_clips = []
    for project in crud.get_all_projects(db):
        all_clips.extend(crud.get_clips_by_project(db, project.id))
    
    # Procurar pelo filename
    for clip in all_clips:
        if clip.output_path and os.path.basename(clip.output_path) == filename:
            if os.path.exists(clip.output_path):
                return FileResponse(clip.output_path, media_type='video/mp4', filename=filename)
    
    # Fallback: procurar no diretório legado
    legacy_path = os.path.join("outputs", filename)
    if os.path.exists(legacy_path):
        return FileResponse(legacy_path, media_type='video/mp4', filename=filename)
    
    raise HTTPException(status_code=404, detail="Arquivo não encontrado.")


@router.post("/delete/{filename}")
async def delete_video(filename: str, db: Session = Depends(get_db)):
    """
    Deleta um vídeo. Procura primeiro nos projetos, depois no diretório legado.
    """
    # Procurar o clip no banco de dados
    all_clips = []
    for project in crud.get_all_projects(db):
        all_clips.extend(crud.get_clips_by_project(db, project.id))
    
    # Procurar pelo filename e deletar
    for clip in all_clips:
        if clip.output_path and os.path.basename(clip.output_path) == filename:
            # Deletar arquivo físico
            if os.path.exists(clip.output_path):
                os.remove(clip.output_path)
            # Deletar registro do banco de dados
            crud.delete_clip(db, clip.id)
            return RedirectResponse(url="/outputs", status_code=303)
    
    # Fallback: deletar do diretório legado
    legacy_path = os.path.join("outputs", filename)
    if os.path.exists(legacy_path):
        os.remove(legacy_path)
    
    return RedirectResponse(url="/outputs", status_code=303)


@router.get("/download-all")
async def download_all_videos(background_tasks: BackgroundTasks):
    outputs_dir = "outputs"
    video_files = [f for f in os.listdir(outputs_dir) if f.endswith('.mp4')]
    
    if not video_files:
        return RedirectResponse(url="/outputs")
    
    tmp_dir = "tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    
    zip_path = os.path.join(tmp_dir, "viralcutter_videos.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for video in video_files:
            zipf.write(os.path.join(outputs_dir, video), arcname=video)
    
    return FileResponse(
        zip_path,
        media_type='application/zip',
        filename='viralcutter_videos.zip',
        background=background_tasks.add_task(os.remove, zip_path)
    )


@router.post("/delete-all")
async def delete_all_videos():
    outputs_dir = "outputs"
    for filename in os.listdir(outputs_dir):
        if filename.endswith('.mp4'): os.remove(os.path.join(outputs_dir, filename))
    return RedirectResponse(url="/outputs", status_code=303)
