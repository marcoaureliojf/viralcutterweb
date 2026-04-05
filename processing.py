import os
import subprocess
import json
import shutil
from scripts import create_viral_segments, cut_segments, edit_video
from glob import glob
from pathlib import Path

def generate_whisperx(input_file: str, output_tsv_path: str, model: str, compute_type: str, batch_size: int, log_func=print):
    """
    Executa a transcrição do WhisperX e salva/move o resultado para o caminho TSV especificado.
    """
    log_func("\n" + "="*50); log_func("INICIANDO PROCESSO DE TRANSCRIÇÃO"); log_func("="*50)
    if not os.path.exists(input_file): raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_file}")
    
    # O WhisperX gera o arquivo na pasta de trabalho (cwd) ou em --output_dir
    tmp_dir = "tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    
    # WhisperX nomeia o arquivo gerado com o mesmo nome do input (sem caminho)
    input_base_name = Path(input_file).stem
    expected_tsv = os.path.join(tmp_dir, f"{input_base_name}.tsv")
    
    command = f"""whisperx "{input_file}" --model {model} --task transcribe --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --chunk_size 10 --vad_onset 0.4 --vad_offset 0.3 --compute_type {compute_type} --batch_size {batch_size} --output_dir "{tmp_dir}" --output_format tsv --verbose True"""
    try:
        log_func(f"Executando WhisperX. Esperando saída em: {expected_tsv}")
        # Executa o subprocesso, o TSV será gerado em 'tmp'
        subprocess.run(command, shell=True, text=True, capture_output=True, encoding='utf-8', check=True)
        
        if os.path.exists(expected_tsv):
            # Move/Renomeia o TSV gerado para o caminho de saída final explícito
            shutil.move(expected_tsv, output_tsv_path)
            log_func(f"Arquivo de transcrição movido para: {output_tsv_path}")
            return output_tsv_path
        else:
            raise FileNotFoundError(f"WhisperX executou, mas não encontrou o TSV esperado em {expected_tsv}")
            
    except subprocess.CalledProcessError as e: log_func(f"\n❌ ERRO WhisperX:\nStderr: {e.stderr}"); raise

def initial_process(job_id: str, jobs_dict: dict, input_video_path: str, model: str, compute_type: str, batch_size: int, pycaps_template: str, main_transcript_path: str, project_id: str = None, db_session=None):
    """
    Etapa 1: Transcreve o vídeo principal e o corta em segmentos.
    """
    # Função auxiliar de log que imprime e salva no dicionário
    def log(msg):
        print(msg)
        if job_id in jobs_dict:
            if "logs" not in jobs_dict[job_id]:
                jobs_dict[job_id]["logs"] = []
            jobs_dict[job_id]["logs"].append(msg)

    log(f"Iniciando processamento inicial para o Job ID: {job_id} com o template PyCaps: {pycaps_template}")
    try:
        # 1. Transcrição do vídeo principal
        generate_whisperx(input_video_path, output_tsv_path=main_transcript_path, model=model, compute_type=compute_type, batch_size=batch_size, log_func=log)
        
        # 2. Geração de segmentos virais e seus TSVs
        log("Analisando transcrição para encontrar segmentos virais...")
        viral_segments = create_viral_segments.create(
            input_tsv_path=main_transcript_path, # Passa o caminho explícito
            num_segments=10, 
            viral_mode=True, 
            themes='', 
            tempo_minimo=40, 
            tempo_maximo=120
        )
        log(f"Segmentos virais encontrados: {len(viral_segments.get('segments', []))}")
        
        # 3. Corte dos segmentos de vídeo
        log("Iniciando o corte dos segmentos de vídeo...")
        cut_files = cut_segments.cut(viral_segments, input_video_path)
        log(f"Segmentos cortados com sucesso: {len(cut_files)}")

        # Associa os caminhos dos arquivos cortados com os títulos gerados pela IA
        clips_with_titles = []
        for segment_data, file_path in zip(viral_segments['segments'], cut_files):
            clips_with_titles.append({
                "path": file_path,
                "title": segment_data.get("title", "Título Padrão")
            })
        
        jobs_dict[job_id]["clips"] = clips_with_titles
        jobs_dict[job_id]["status"] = "pending_adjustment"
        
        # Atualizar status no banco de dados se db_session foi fornecido
        if db_session and project_id:
            from database import crud
            crud.update_video_status(db_session, job_id, "pending_adjustment")
        
        log(f"Processamento inicial para o Job {job_id} concluído. Aguardando ajuste do usuário.")
    except Exception as e:
        jobs_dict[job_id]["status"] = "error"
        
        # Atualizar status de erro no banco
        if db_session:
            from database import crud
            crud.update_video_status(db_session, job_id, "error", error_message=str(e))
        
        log(f"\n❌ ERRO no processamento inicial do Job {job_id}: {str(e)}")
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
    
    # Recuperar project_id do job para determinar o destino correto
    job = jobs_dict.get(job_id)
    project_id = job.get("project_id") if job else None
    
    try:
        # Passa os dados completos, incluindo o caminho TSV do segmento
        edit_video.edit(clips_data, pycaps_template)

        source_folder = 'burned_sub'
        
        # Define a pasta de destino correta (Projeto ou Global)
        if project_id:
            destination_folder = os.path.join("projects", project_id, "outputs")
        else:
            destination_folder = 'outputs'
            
        os.makedirs(destination_folder, exist_ok=True)
        
        final_files = glob(os.path.join(source_folder, '*_final.mp4')) # Certifica que pega apenas os arquivos finais
        
        # Inicializar sessão do banco de dados para criar os clips
        from database import crud, SessionLocal
        db = SessionLocal()
        
        try:
            for file_path in final_files:
                clip_base_name = os.path.basename(file_path).replace('_final.mp4', '.mp4')
                unique_final_name = f"{original_base_name}_{clip_base_name}"
                destination_path = os.path.join(destination_folder, unique_final_name)
                
                shutil.move(file_path, destination_path)
                print(f"Arquivo final movido e renomeado para: {destination_path}")
                
                # Se temos um projeto, precisamos criar o registro do Clip no banco de dados
                if project_id:
                    # Encontrar os dados originais do clip para este arquivo
                    # clips_data chaves são os caminhos de entrada (ex: tmp/output000.mp4)
                    # clip_base_name é ex: output000.mp4
                    
                    matched_data = None
                    matched_input_path = None
                    
                    for input_path, data in clips_data.items():
                        if os.path.splitext(os.path.basename(input_path))[0] == os.path.splitext(clip_base_name)[0]:
                            matched_data = data
                            matched_input_path = input_path
                            break
                    
                    if matched_data:
                        # Criar o clip no banco de dados
                        crud.create_clip(
                            db=db,
                            video_id=job_id,
                            project_id=project_id,
                            title=matched_data.get('title', 'Clip Sem Título'),
                            clip_path=matched_input_path,
                            output_path=destination_path,
                            segment_tsv_path=matched_data.get('segment_tsv_path'),
                            roi1=matched_data.get('roi1'),
                            roi2=matched_data.get('roi2'),
                            duration=None # TODO: Calcular duração se necessário
                        )
                        print(f"Clip registrado no banco de dados: {unique_final_name}")
                    else:
                        print(f"AVISO: Não foi possível encontrar dados originais para {clip_base_name}")

            jobs_dict[job_id]["status"] = "complete"
            print(f"Processamento final para o Job {job_id} concluído com sucesso!")
            
        except Exception as db_e:
            print(f"Erro durante operações de banco de dados ou arquivo: {db_e}")
            raise db_e
        finally:
            db.close()

    except Exception as e:
        jobs_dict[job_id]["status"] = "error"
        print(f"\n❌ ERRO no processamento final do Job {job_id}: {str(e)}")
    finally:
        # Limpa as pastas temporárias
        # IMPORTANTE: Não remover os diretórios raiz, apenas o conteúdo
        for dir_name in ['tmp', 'burned_sub', 'subs_ass']:
            if os.path.exists(dir_name) and os.path.isdir(dir_name):
                try:
                    for item in os.listdir(dir_name):
                        item_path = os.path.join(dir_name, item)
                        try:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                            else:
                                shutil.rmtree(item_path)
                        except Exception as cleanup_item_e:
                            print(f"Erro ao limpar item {item_path}: {cleanup_item_e}")
                except Exception as cleanup_dir_e:
                    print(f"Erro ao listar diretório {dir_name}: {cleanup_dir_e}")