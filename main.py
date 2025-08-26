from fastapi import FastAPI, File, UploadFile, Request, BackgroundTasks, Form, HTTPException, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import shutil, os, yt_dlp, uuid

from processing import initial_process, finalize_process

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/clips", StaticFiles(directory="tmp"), name="clips")
templates = Jinja2Templates(directory="templates")
os.makedirs("uploads", exist_ok=True); os.makedirs("outputs", exist_ok=True); os.makedirs("tmp", exist_ok=True)
JOBS = {}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request): return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload/", response_class=HTMLResponse)
async def upload_video(
    background_tasks: BackgroundTasks, request: Request, model: str = Form(...), 
    compute_type: str = Form(...), batch_size: int = Form(...), 
    video: UploadFile = File(None), video_url: str = Form(None),
    dub_video: bool = Form(False), target_language: str = Form("English")
):
    if not video and not video_url: raise HTTPException(status_code=400, detail="No video file or URL provided.")
    video_path = ""
    if video and video.filename:
        video_path = os.path.join("uploads", video.filename); 
        with open(video_path, "wb") as buffer: shutil.copyfileobj(video.file, buffer)
    elif video_url:
        upload_dir = "uploads"; unique_filename = f"{uuid.uuid4()}.mp4"; video_path = os.path.join(upload_dir, unique_filename)
        ydl_opts = {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': video_path, 'noplaylist': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([video_url])
        except Exception as e: raise HTTPException(status_code=400, detail=f"Could not download video. Error: {e}")
    if not video_path or not os.path.exists(video_path): raise HTTPException(status_code=500, detail="Failed to save or download the video.")
    
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "processing", "clips": [], 
        "original_name": os.path.splitext(os.path.basename(video_path))[0],
        "dub_video": dub_video,
        "target_language": target_language
    }
    
    background_tasks.add_task(initial_process, job_id=job_id, jobs_dict=JOBS, input_video_path=video_path, model=model, compute_type=compute_type, batch_size=batch_size)
    return RedirectResponse(url=f"/adjust/{job_id}", status_code=303)

@app.get("/adjust/{job_id}", response_class=HTMLResponse)
async def adjust_page(request: Request, job_id: str = Path(...)):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] == "processing": return templates.TemplateResponse("result.html", {"request": request})
    clips_for_template = [{"name": os.path.basename(p), "path": p, "url": f"/clips/{os.path.basename(p)}"} for p in job["clips"]]
    return templates.TemplateResponse("adjust.html", {"request": request, "job_id": job_id, "clips": clips_for_template})

@app.post("/finalize/{job_id}", response_class=HTMLResponse)
async def finalize_job(request: Request, background_tasks: BackgroundTasks, job_id: str = Path(...)):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found.")
    form_data = await request.form()
    
    clips_data = {}
    i = 0
    while True:
        clip_path_key = f"clip_path_{i}"
        if clip_path_key not in form_data: break
        path = form_data[clip_path_key]
        clips_data[path] = {
            'roi1': {'x': float(form_data[f"roi1_x_{i}"]), 'y': float(form_data[f"roi1_y_{i}"]), 'w': float(form_data[f"roi1_w_{i}"]), 'h': float(form_data[f"roi1_h_{i}"])},
            'roi2': {'x': float(form_data[f"roi2_x_{i}"]), 'y': float(form_data[f"roi2_y_{i}"]), 'w': float(form_data[f"roi2_w_{i}"]), 'h': float(form_data[f"roi2_h_{i}"])}}
        i += 1
            
    job["status"] = "finalizing"
    background_tasks.add_task(
        finalize_process, job_id=job_id, jobs_dict=JOBS, clips_data=clips_data, 
        original_base_name=job.get("original_name", "video"),
        dub_video=job.get("dub_video", False),
        target_language=job.get("target_language", "en")
    )
    return templates.TemplateResponse("result.html", {"request": request})