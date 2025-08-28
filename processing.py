import os
import subprocess
import json
import shutil
from scripts import create_viral_segments, cut_segments, edit_video, adjust_subtitles
from glob import glob

def generate_whisperx(input_file: str, output_dir: str, model: str, compute_type: str, batch_size: int):
    """
    Executa a transcrição do WhisperX e salva o resultado no diretório de saída especificado.
    """
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
            renamed_tsv = os.path.join('tmp', 'input_video.tsv')
            # Renomeia apenas se o arquivo esperado existir
            if os.path.exists(expected_tsv):
                os.rename(expected_tsv, renamed_tsv)
                print(f"Arquivo de saída principal renomeado para: {renamed_tsv}")
                return renamed_tsv
            return expected_tsv
            
        print(f"Arquivo de transcrição de clipe criado: {expected_tsv}")
        return expected_tsv
    except subprocess.CalledProcessError as e: print(f"\n❌ ERRO WhisperX:\nStderr: {e.stderr}"); raise

def initial_process(job_id: str, jobs_dict: dict, input_video_path: str, model: str, compute_type: str, batch_size: int):
    """
    Etapa 1: Transcreve o vídeo principal e o corta em segmentos.
    """
    print(f"Iniciando processamento inicial para o Job ID: {job_id}")
    try:
        generate_whisperx(input_video_path, output_dir='tmp', model=model, compute_type=compute_type, batch_size=batch_size)
        
        viral_segments = create_viral_segments.create(num_segments=10, viral_mode=True, themes='', tempo_minimo=40, tempo_maximo=90)
        cut_files = cut_segments.cut(viral_segments, input_video_path)

        # --- MUDANÇA CRÍTICA AQUI ---
        # Agora salvamos uma lista de dicionários, cada um contendo o caminho e o título do clipe.
        # Isso garante que o título gerado pela IA seja associado ao arquivo de vídeo correto.
        clips_with_titles = []
        for segment_data, file_path in zip(viral_segments['segments'], cut_files):
            clips_with_titles.append({
                "path": file_path,
                "title": segment_data.get("title", "Título Padrão") # Usa .get para segurança
            })
        
        jobs_dict[job_id]["clips"] = clips_with_titles
        jobs_dict[job_id]["status"] = "pending_adjustment"
        print(f"Processamento inicial para o Job {job_id} concluído. Aguardando ajuste do usuário.")
    except Exception as e:
        jobs_dict[job_id]["status"] = "error"
        print(f"\n❌ ERRO no processamento inicial do Job {job_id}: {str(e)}")

def finalize_process(job_id: str, jobs_dict: dict, clips_data: dict, original_base_name: str):
    """
    Etapa 2: Pega os dados de ajuste, cria legendas, e então reenquadra E queima as legendas/títulos de uma só vez.
    """
    print(f"Iniciando processamento final para o Job ID: {job_id}")
    try:
        # A lista de caminhos para os próximos passos é extraída do clips_data
        clip_paths = list(clips_data.keys())

        #Função inutilizada com o uso do PyCaps
        #for clip_path in clip_paths:
        #     generate_whisperx(clip_path, output_dir='subs', model='medium', compute_type='float16', batch_size=2)
        
        #Função inutilizada com o uso do PyCaps
        # adjust_subtitles.adjust(clip_paths)

        # A função edit_video agora recebe os dados completos, incluindo os títulos
        edit_video.edit(clips_data)

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
        jobs_dict[job_id]["status"] = "error"
        print(f"\n❌ ERRO no processamento final do Job {job_id}: {str(e)}")
    finally:
        # Limpa as pastas temporárias
        for dir_name in ['tmp', 'final', 'subs_ass', 'burned_sub']:
            if os.path.exists(dir_name) and os.path.isdir(dir_name):
                shutil.rmtree(dir_name)