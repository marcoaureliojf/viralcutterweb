import os
import shutil
import uuid
import yt_dlp
import zipfile
from fastapi import FastAPI, File, UploadFile, Request, BackgroundTasks, Form, HTTPException, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from processing import initial_process, finalize_process

# --- CONFIGURAÇÃO DA APLICAÇÃO ---
app = FastAPI()

os.makedirs("uploads", exist_ok=True); os.makedirs("outputs", exist_ok=True); os.makedirs("tmp", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/clips", StaticFiles(directory="tmp"), name="clips")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

templates = Jinja2Templates(directory="templates")
JOBS = {}

# --- ENDPOINTS PRINCIPAIS DA APLICAÇÃO ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload/", response_class=HTMLResponse)
async def upload_video(background_tasks: BackgroundTasks, request: Request, model: str = Form(...), compute_type: str = Form(...), batch_size: int = Form(...), video: UploadFile = File(None), video_url: str = Form(None)):
    if not video and not video_url: raise HTTPException(status_code=400, detail="Nenhum arquivo de vídeo ou URL fornecido.")
    
    video_path = ""
    if video and video.filename:
        video_path = os.path.join("uploads", video.filename)
        with open(video_path, "wb") as buffer: shutil.copyfileobj(video.file, buffer)
    elif video_url:
        upload_dir = "uploads"; unique_filename = f"{uuid.uuid4()}.mp4"; video_path = os.path.join(upload_dir, unique_filename)
        ydl_opts = {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': video_path, 'noplaylist': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([video_url])
        except Exception as e: raise HTTPException(status_code=400, detail=f"Não foi possível baixar o vídeo. Erro: {e}")

    if not video_path or not os.path.exists(video_path): raise HTTPException(status_code=500, detail="Falha ao salvar ou baixar o vídeo.")
    
    original_base_name = os.path.splitext(os.path.basename(video_path))[0]
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "processing", "clips": [], "original_name": original_base_name}
    
    background_tasks.add_task(initial_process, job_id=job_id, jobs_dict=JOBS, input_video_path=video_path, model=model, compute_type=compute_type, batch_size=batch_size)
    return RedirectResponse(url=f"/adjust/{job_id}", status_code=303)

@app.get("/adjust/{job_id}", response_class=HTMLResponse)
async def adjust_page(request: Request, job_id: str = Path(...)):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job não encontrado.")
    
    if job["status"] in ["processing", "finalizing"]:
        return templates.TemplateResponse("result.html", {"request": request, "job_id": job_id})
        
    if job["status"] == "complete":
        return RedirectResponse(url="/outputs", status_code=303)

    # --- MUDANÇA CRÍTICA AQUI ---
    # Prepara os dados para o template, garantindo que o nome do arquivo e a URL também sejam passados.
    clips_for_template = []
    for clip_data in job.get("clips", []):
        path = clip_data["path"]
        clips_for_template.append({
            "path": path,
            "title": clip_data["title"],
            "name": os.path.basename(path),
            "url": f"/clips/{os.path.basename(path)}"
        })

    return templates.TemplateResponse("adjust.html", {"request": request, "job_id": job_id, "clips": clips_for_template})

@app.post("/finalize/{job_id}", response_class=HTMLResponse)
async def finalize_job(request: Request, background_tasks: BackgroundTasks, job_id: str = Path(...)):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job não encontrado.")
    
    form_data = await request.form()
    clips_data = {}
    i = 0
    # --- MUDANÇA CRÍTICA AQUI ---
    # O loop agora lê o caminho E o título do formulário para cada clipe.
    while f"clip_path_{i}" in form_data:
        path = form_data[f"clip_path_{i}"]
        title = form_data.get(f"clip_title_{i}", "Título não encontrado") # Pega o título do novo campo
        clips_data[path] = {
            'title': title, # Armazena o título
            'roi1': {'x': float(form_data[f"roi1_x_{i}"]), 'y': float(form_data[f"roi1_y_{i}"]), 'w': float(form_data[f"roi1_w_{i}"]), 'h': float(form_data[f"roi1_h_{i}"])},
            'roi2': {'x': float(form_data[f"roi2_x_{i}"]), 'y': float(form_data[f"roi2_y_{i}"]), 'w': float(form_data[f"roi2_w_{i}"]), 'h': float(form_data[f"roi2_h_{i}"])}
        }
        i += 1
            
    job["status"] = "finalizing"
    original_name = job.get("original_name", "video_sem_nome")
    
    background_tasks.add_task(finalize_process, job_id=job_id, jobs_dict=JOBS, clips_data=clips_data, original_base_name=original_name)
    return RedirectResponse(url=f"/adjust/{job_id}", status_code=303)

@app.get("/status/{job_id}", response_class=JSONResponse)
async def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job não encontrado.")
    return {"status": job.get("status")}

@app.get("/outputs", response_class=HTMLResponse)
async def list_outputs(request: Request):
    outputs_dir = "outputs"
    videos = sorted([f for f in os.listdir(outputs_dir) if f.endswith('.mp4')], reverse=True)
    return templates.TemplateResponse("outputs.html", {"request": request, "videos": videos})

@app.get("/download/{filename}")
async def download_video(filename: str):
    path = os.path.join("outputs", filename)
    if not os.path.exists(path): raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(path, media_type='video/mp4', filename=filename)

@app.post("/delete/{filename}")
async def delete_video(filename: str):
    path = os.path.join("outputs", filename)
    if os.path.exists(path): os.remove(path)
    return RedirectResponse(url="/outputs", status_code=303)

from fastapi import BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse
import os, zipfile

@app.get("/download-all")
async def download_all_videos():
    outputs_dir = "outputs"
    video_files = [f for f in os.listdir(outputs_dir) if f.endswith('.mp4')]
    
    if not video_files:
        return RedirectResponse(url="/outputs")
    
    # Garante que a pasta tmp exista
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
        background=BackgroundTasks().add_task(os.remove, zip_path)
    )


@app.post("/delete-all")
async def delete_all_videos():
    outputs_dir = "outputs"
    for filename in os.listdir(outputs_dir):
        if filename.endswith('.mp4'): os.remove(os.path.join(outputs_dir, filename))
    return RedirectResponse(url="/outputs", status_code=303)