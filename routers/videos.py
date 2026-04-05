from fastapi import APIRouter, Depends, HTTPException, Request, Form, File, UploadFile, BackgroundTasks, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import uuid
import shutil
import yt_dlp

from database import get_db, crud
from processing import initial_process, finalize_process

# Importar JOBS do main (precisamos de uma maneira de compartilhar estado)
# Por enquanto, vamos redefinir aqui ou importar de um módulo compartilhado.
# Para simplificar, vamos criar um módulo shared.py para o estado global.
# Mas como não posso criar muitos arquivos, vou manter o JOBS aqui e importar no main.
# O ideal seria usar Redis ou DB para jobs, mas vamos manter em memória por enquanto.

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Estado global de jobs (compartilhado)
# NOTA: Isso precisa ser importado pelo main.py para que o estado seja consistente
JOBS = {}

@router.post("/upload/", response_class=HTMLResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    request: Request,
    project_id: str = Form(...),
    model: str = Form(...),
    compute_type: str = Form(...),
    batch_size: int = Form(...),
    pycaps_template: str = Form(...),
    video: UploadFile = File(None),
    video_url: str = Form(None),
    db: Session = Depends(get_db)
):
    if not video and not video_url: 
        raise HTTPException(status_code=400, detail="Nenhum arquivo de vídeo ou URL fornecido.")
    
    # Validar que o projeto existe
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    # Criar diretórios do projeto se não existirem
    project_dir = f"projects/{project_id}"
    for subdir in ["uploads", "outputs", "tmp", "burned_sub", "subs_ass"]:
        os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)
    
    video_path = ""
    original_filename = ""
    
    if video and video.filename:
        # Salvar no diretório do projeto
        original_filename = video.filename
        video_path = os.path.join(project_dir, "uploads", video.filename)
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
    elif video_url:
        # Gera um nome de arquivo único para URLs
        unique_filename = f"{uuid.uuid4()}.mp4"
        original_filename = unique_filename
        video_path = os.path.join(project_dir, "uploads", unique_filename)
        ydl_opts = {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best", 
            'outtmpl': video_path, 
            'noplaylist': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Não foi possível baixar o vídeo. Erro: {e}")

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=500, detail="Falha ao salvar ou baixar o vídeo.")
    
    # Usa o nome base do arquivo (sem extensão) para a saída final
    original_base_name = os.path.splitext(os.path.basename(video_path))[0]
    job_id = str(uuid.uuid4())
    
    # Caminho explícito para a transcrição principal (no diretório do projeto)
    main_transcript_path = os.path.join(project_dir, 'tmp', f"{job_id}_main.tsv")
    
    # Criar registro de Video no banco de dados
    crud.create_video(
        db=db,
        video_id=job_id,
        project_id=project_id,
        original_filename=original_filename,
        upload_path=video_path,
        status="processing",
        settings={
            "model": model,
            "compute_type": compute_type,
            "batch_size": batch_size,
            "pycaps_template": pycaps_template
        },
        main_transcript_path=main_transcript_path
    )

    # Mantém JOBS para compatibilidade    # Atualizar JOBS dict
    JOBS[job_id] = {
        "status": "processing",
        "clips": [],
        "original_name": original_base_name,
        "pycaps_template": pycaps_template,
        "main_transcript_path": main_transcript_path,
        "project_id": project_id,
        "logs": []  # Inicializa lista de logs
    }
    
    background_tasks.add_task(
        initial_process,
        job_id=job_id,
        jobs_dict=JOBS,
        input_video_path=video_path,
        model=model,
        compute_type=compute_type,
        pycaps_template=pycaps_template,
        batch_size=batch_size,
        main_transcript_path=main_transcript_path,
        project_id=project_id,
        db_session=db
    )
    
    print(f"✅ Upload iniciado: {original_filename} no projeto {project.name}")
    return RedirectResponse(url=f"/adjust/{job_id}", status_code=303)


@router.get("/adjust/{job_id}", response_class=HTMLResponse)
async def adjust_page(request: Request, job_id: str = Path(...)):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job não encontrado.")
    
    if job["status"] in ["processing", "finalizing"]:
        return templates.TemplateResponse(request=request, name="result.html", context={"job_id": job_id})
        
    if job["status"] == "complete":
        return RedirectResponse(url="/outputs", status_code=303)

    clips_for_template = []
    for clip_data in job.get("clips", []):
        path = clip_data["path"]
        clips_for_template.append({
            "path": path,
            "title": clip_data["title"],
            "name": os.path.basename(path),
            "url": f"/clips/{os.path.basename(path)}"
        })

    return templates.TemplateResponse(request=request, name="adjust.html", context={"job_id": job_id, "clips": clips_for_template})


@router.post("/finalize/{job_id}", response_class=HTMLResponse)
async def finalize_job(request: Request, background_tasks: BackgroundTasks, job_id: str = Path(...)):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    
    form_data = await request.form()
    clips_data = {}
    i = 0
    while f"clip_path_{i}" in form_data:
        path = form_data[f"clip_path_{i}"]
        title = form_data.get(f"clip_title_{i}", "Título não encontrado")
        clips_data[path] = {
            'title': title,
            'segment_tsv_path': os.path.join('tmp', f"{os.path.splitext(os.path.basename(path))[0]}.tsv"),
            'roi1': {
                'x': float(form_data[f"roi1_x_{i}"]),
                'y': float(form_data[f"roi1_y_{i}"]),
                'w': float(form_data[f"roi1_w_{i}"]),
                'h': float(form_data[f"roi1_h_{i}"])
            },
            'roi2': {
                'x': float(form_data[f"roi2_x_{i}"]),
                'y': float(form_data[f"roi2_y_{i}"]),
                'w': float(form_data[f"roi2_w_{i}"]),
                'h': float(form_data[f"roi2_h_{i}"])
            }
        }
        i += 1

    job["status"] = "finalizing"
    original_name = job.get("original_name", "video_sem_nome")
    pycaps_template = job.get("pycaps_template", "default")
    
    background_tasks.add_task(
        finalize_process,
        job_id=job_id,
        jobs_dict=JOBS,
        clips_data=clips_data,
        original_base_name=original_name,
        pycaps_template=pycaps_template
    )
    return RedirectResponse(url=f"/adjust/{job_id}", status_code=303)


@router.get("/status/{job_id}", response_class=JSONResponse)
async def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job não encontrado.")
    return {"status": job.get("status")}


@router.get("/api/jobs/{job_id}/logs", response_class=JSONResponse)
async def get_job_logs(job_id: str):
    """Retorna os logs de processamento de um job."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    return {
        "status": job.get("status"),
        "logs": job.get("logs", [])
    }


@router.get("/api/videos/{video_id}/transcript", response_class=JSONResponse)
async def get_video_transcript(video_id: str, db: Session = Depends(get_db)):
    """Retorna a transcrição de um vídeo em formato JSON."""
    video = crud.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    
    if not video.main_transcript_path:
        raise HTTPException(status_code=404, detail="Transcrição não disponível")
    
    if not os.path.exists(video.main_transcript_path):
        raise HTTPException(status_code=404, detail="Arquivo de transcrição não existe")
    
    # Ler TSV e retornar como JSON
    transcript = []
    try:
        with open(video.main_transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    transcript.append({
                        "start": parts[0],
                        "end": parts[1],
                        "text": parts[2]
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler transcrição: {str(e)}")
    
    return {
        "video_id": video_id,
        "filename": video.original_filename,
        "transcript": transcript
    }


@router.post("/projects/{project_id}/reprocess/{video_id}", response_class=JSONResponse)
async def reprocess_video(
    project_id: str,
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Reprocessa um vídeo existente."""
    video = crud.get_video(db, video_id)
    if not video or video.project_id != project_id:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    
    if not os.path.exists(video.upload_path):
        raise HTTPException(status_code=404, detail="Arquivo de vídeo não encontrado")
    
    # Atualizar status para processing
    crud.update_video_status(db, video_id, "processing")
    
    # Reprocessar usando as configurações salvas
    settings = video.settings or {}
    model = settings.get("model", "base")
    compute_type = settings.get("compute_type", "int8")
    pycaps_template = settings.get("pycaps_template", "word-focus")
    batch_size = settings.get("batch_size", 16)
    
    # Atualizar JOBS dict
    JOBS[video_id] = {
        "status": "processing",
        "clips": [],
        "original_name": os.path.splitext(video.original_filename)[0],
        "pycaps_template": pycaps_template,
        "main_transcript_path": video.main_transcript_path,
        "project_id": project_id,
        "logs": []  # Inicializa lista de logs
    }
    
    background_tasks.add_task(
        initial_process,
        job_id=video_id,
        jobs_dict=JOBS,
        input_video_path=video.upload_path,
        model=model,
        compute_type=compute_type,
        pycaps_template=pycaps_template,
        batch_size=batch_size,
        main_transcript_path=video.main_transcript_path,
        project_id=project_id,
        db_session=db
    )
    
    print(f"🔄 Reprocessamento iniciado: {video.original_filename} (ID: {video_id})")
    return {
        "message": "Reprocessamento iniciado com sucesso",
        "video_id": video_id,
        "status": "processing"
    }
