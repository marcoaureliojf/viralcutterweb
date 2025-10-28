import os
import subprocess
import json
import shutil
from scripts import create_viral_segments, cut_segments, edit_video
from glob import glob
from pathlib import Path

def generate_whisperx(input_file: str, output_tsv_path: str, model: str, compute_type: str, batch_size: int):
    """
    Executa a transcrição do WhisperX e salva/move o resultado para o caminho TSV especificado.
    """
    print("\n" + "="*50); print("INICIANDO PROCESSO DE TRANSCRIÇÃO"); print("="*50)
    if not os.path.exists(input_file): raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_file}")
    
    # O WhisperX gera o arquivo na pasta de trabalho (cwd) ou em --output_dir
    tmp_dir = "tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    
    # WhisperX nomeia o arquivo gerado com o mesmo nome do input (sem caminho)
    input_base_name = Path(input_file).stem
    expected_tsv = os.path.join(tmp_dir, f"{input_base_name}.tsv")
    
    command = f"""whisperx "{input_file}" --model {model} --task transcribe --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --chunk_size 10 --vad_onset 0.4 --vad_offset 0.3 --compute_type {compute_type} --batch_size {batch_size} --output_dir "{tmp_dir}" --output_format tsv --verbose True"""
    try:
        print(f"Executando WhisperX. Esperando saída em: {expected_tsv}")
        # Executa o subprocesso, o TSV será gerado em 'tmp'
        subprocess.run(command, shell=True, text=True, capture_output=True, encoding='utf-8', check=True)
        
        if os.path.exists(expected_tsv):
            # Move/Renomeia o TSV gerado para o caminho de saída final explícito
            shutil.move(expected_tsv, output_tsv_path)
            print(f"Arquivo de transcrição movido para: {output_tsv_path}")
            return output_tsv_path
        else:
            raise FileNotFoundError(f"WhisperX executou, mas não encontrou o TSV esperado em {expected_tsv}")
            
    except subprocess.CalledProcessError as e: print(f"\n❌ ERRO WhisperX:\nStderr: {e.stderr}"); raise

def initial_process(job_id: str, jobs_dict: dict, input_video_path: str, model: str, compute_type: str, batch_size: int, pycaps_template: str, main_transcript_path: str):
    """
    Etapa 1: Transcreve o vídeo principal e o corta em segmentos.
    """
    print(f"Iniciando processamento inicial para o Job ID: {job_id} com o template PyCaps: {pycaps_template}")
    try:
        # 1. Transcrição do vídeo principal
        generate_whisperx(input_video_path, output_tsv_path=main_transcript_path, model=model, compute_type=compute_type, batch_size=batch_size)
        
        # 2. Geração de segmentos virais e seus TSVs
        viral_segments = create_viral_segments.create(
            input_tsv_path=main_transcript_path, # Passa o caminho explícito
            num_segments=10, 
            viral_mode=True, 
            themes='', 
            tempo_minimo=40, 
            tempo_maximo=120
        )
        
        # 3. Corte dos segmentos de vídeo
        cut_files = cut_segments.cut(viral_segments, input_video_path)

        # Associa os caminhos dos arquivos cortados com os títulos gerados pela IA
        clips_with_titles = []
        for segment_data, file_path in zip(viral_segments['segments'], cut_files):
            clips_with_titles.append({
                "path": file_path,
                "title": segment_data.get("title", "Título Padrão")
            })
        
        jobs_dict[job_id]["clips"] = clips_with_titles
        jobs_dict[job_id]["status"] = "pending_adjustment"
        print(f"Processamento inicial para o Job {job_id} concluído. Aguardando ajuste do usuário.")
    except Exception as e:
        jobs_dict[job_id]["status"] = "error"
        print(f"\n❌ ERRO no processamento inicial do Job {job_id}: {str(e)}")
    finally:
        # Opcional: Remover o vídeo original de uploads após o processamento (opcional, mantive a exclusão para depois)
        # if os.path.exists(input_video_path):
        #     os.remove(input_video_path)
        pass # Mantém o arquivo para debug, se necessário.

def finalize_process(job_id: str, jobs_dict: dict, clips_data: dict, original_base_name: str, pycaps_template: str):
    """
    Etapa 2: Pega os dados de ajuste, cria legendas, e então reenquadra E queima as legendas/títulos de uma só vez.
    """
    print(f"Iniciando processamento final para o Job ID: {job_id}")
    try:
        # Passa os dados completos, incluindo o caminho TSV do segmento
        edit_video.edit(clips_data, pycaps_template)

        source_folder = 'burned_sub'
        destination_folder = 'outputs'
        final_files = glob(os.path.join(source_folder, '*_final.mp4')) # Certifica que pega apenas os arquivos finais
        
        for file_path in final_files:
            clip_base_name = os.path.basename(file_path).replace('_final.mp4', '.mp4')
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
        # Não remove 'uploads' e 'outputs'
        for dir_name in ['tmp', 'burned_sub', 'subs_ass']:
            if os.path.exists(dir_name) and os.path.isdir(dir_name):
                # O 'tmp' contém o TSV principal, vamos limpar apenas o conteúdo
                if dir_name == 'tmp':
                    for item in os.listdir(dir_name):
                        item_path = os.path.join(dir_name, item)
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        else:
                            shutil.rmtree(item_path)
                else:
                    shutil.rmtree(dir_name)