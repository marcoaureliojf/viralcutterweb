import os, subprocess, json, shutil, requests, ffmpeg, pandas as pd
from scripts import create_viral_segments, cut_segments, edit_video, adjust_subtitles, translate_text
from glob import glob

KOKORO_API_BASE_URL = "http://192.168.1.200:8880/v1" # URL base da API Kokoro para dublagem

def generate_whisperx(input_file: str, output_dir: str, model: str, compute_type: str, batch_size: int):
    print("\n" + "="*50); print("INICIANDO PROCESSO DE TRANSCRIÇÃO"); print("="*50)
    if not os.path.exists(input_file): raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_file}")
    os.makedirs(output_dir, exist_ok=True)
    command = f"""whisperx "{input_file}" --model {model} --task transcribe --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --chunk_size 10 --vad_onset 0.4 --vad_offset 0.3 --compute_type {compute_type} --batch_size {batch_size} --output_dir "{output_dir}" --output_format tsv --verbose True"""
    try:
        print(f"Salvando transcrição em: {output_dir}")
        subprocess.run(command, shell=True, text=True, capture_output=True, encoding='utf-8', check=True)
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        expected_tsv = os.path.join(output_dir, f"{base_name}.tsv")
        if output_dir == 'tmp':
            renamed_tsv = os.path.join('tmp', 'input_video.tsv'); os.rename(expected_tsv, renamed_tsv)
            return renamed_tsv
        print(f"Arquivo de transcrição de clipe criado: {expected_tsv}")
        return expected_tsv
    except subprocess.CalledProcessError as e: print(f"\n❌ ERRO WhisperX:\nStderr: {e.stderr}"); raise

def initial_process(job_id: str, jobs_dict: dict, input_video_path: str, model: str, compute_type: str, batch_size: int):
    print(f"Iniciando processamento inicial para o Job ID: {job_id}")
    try:
        generate_whisperx(input_video_path, output_dir='tmp', model=model, compute_type=compute_type, batch_size=batch_size)
        viral_segments = create_viral_segments.create(num_segments=5, viral_mode=True, themes='', tempo_minimo=40, tempo_maximo=90)
        cut_files = cut_segments.cut(viral_segments, input_video_path)
        jobs_dict[job_id]["clips"] = cut_files
        jobs_dict[job_id]["status"] = "pending_adjustment"
        print(f"Processamento inicial para o Job {job_id} concluído.")
    except Exception as e:
        jobs_dict[job_id]["status"] = "error"; print(f"\n❌ ERRO no processamento inicial do Job {job_id}: {str(e)}")

def finalize_process(job_id: str, jobs_dict: dict, clips_data: dict, original_base_name: str, dub_video: bool, target_language: str):
    print(f"Iniciando processamento final para o Job ID: {job_id}")
    dub_options = {}
    try:
        print("Transcrevendo clipes individuais...")
        for clip_path in clips_data.keys():
             generate_whisperx(clip_path, output_dir='subs', model='base', compute_type='float16', batch_size=2)
        
        if dub_video:
            print(f"Iniciando fluxo de DUBLAGEM para o idioma '{target_language}'...")
            for clip_path in clips_data.keys():
                base_name = os.path.splitext(os.path.basename(clip_path))[0]
                tsv_path = os.path.join('subs', f"{base_name}.tsv")
                df = pd.read_csv(tsv_path, sep='\t')
                original_text = " ".join(df['text'].astype(str))
                
                translated_text = translate_text.translate(original_text, target_language)
                
                response = requests.post(f"{KOKORO_API_BASE_URL}/audio/speech", json={"input": translated_text, "voice": "af_heart"})
                response.raise_for_status()
                dub_audio_path = os.path.join('tmp', f"{base_name}_dub.mp3")
                with open(dub_audio_path, 'wb') as f: f.write(response.content)

                video_duration = float(ffmpeg.probe(clip_path)['format']['duration'])
                audio_duration = float(ffmpeg.probe(dub_audio_path)['format']['duration'])
                speed_factor = audio_duration / video_duration
                dub_options[clip_path] = {"audio_path": dub_audio_path, "speed_factor": speed_factor}

                df_translated = df.copy()
                df_translated['text'] = translated_text
                translated_tsv_path = os.path.join('subs', f"{base_name}_translated.tsv")
                df_translated.to_csv(translated_tsv_path, sep='\t', index=False)
            
            adjust_subtitles.adjust(clips_data.keys(), translated=True)
        else:
            print("Iniciando fluxo original de TELA DIVIDIDA...")
            adjust_subtitles.adjust(clips_data.keys(), translated=False)

        edit_video.edit(clips_data, dub_options)

        source_folder = 'burned_sub'
        destination_folder = 'outputs'
        final_files = glob(os.path.join(source_folder, '*.mp4'))
        for file_path in final_files:
            clip_base_name = os.path.basename(file_path)
            unique_final_name = f"{original_base_name}_{clip_base_name}"
            destination_path = os.path.join(destination_folder, unique_final_name)
            shutil.move(file_path, destination_path)
            print(f"Arquivo final movido e renomeado para: {destination_path}")
        
        jobs_dict[job_id]["status"] = "complete"
        print(f"Processamento final para o Job {job_id} concluído com sucesso!")
    except Exception as e:
        jobs_dict[job_id]["status"] = "error"; print(f"\n❌ ERRO no processamento final do Job {job_id}: {str(e)}")
    finally:
        for dir_name in ['tmp', 'final', 'subs', 'subs_ass', 'burned_sub', 'uploads']:
            if os.path.exists(dir_name) and os.path.isdir(dir_name): shutil.rmtree(dir_name)
            os.makedirs(dir_name, exist_ok=True)