import g4f
import pandas as pd
import json
import os

def get_transcript_chunks(df: pd.DataFrame, chunk_duration_sec: int, overlap_duration_sec: int):
    """
    Divide o DataFrame da transcrição em chunks de duração específica com sobreposição.
    """
    chunks = []
    total_duration = df['end'].max() if not df.empty else 0
    current_start_time = 0.0

    while current_start_time < total_duration:
        chunk_end_time = min(current_start_time + chunk_duration_sec, total_duration)

        chunk_df = df[(df['start'] >= current_start_time - 0.1) & (df['end'] <= chunk_end_time + 0.1)].copy()

        if not chunk_df.empty:
            chunk_text = " ".join(chunk_df['text'].astype(str))
            
            chunks.append({
                "chunk_text": chunk_text,
                "start_time_offset": current_start_time
            })
        
        current_start_time += (chunk_duration_sec - overlap_duration_sec)
        
        if current_start_time < 0: 
            current_start_time = 0

    return chunks


def create(input_tsv_path: str, num_segments, viral_mode, themes, tempo_minimo, tempo_maximo):
    """
    Analyzes the transcription and generates a list of potential viral segments.
    """
    print("Analisando transcrição para encontrar segmentos virais...")

    output_path = os.path.join('tmp', 'viral_segments.txt')

    # Read the transcription data from the explicit path
    try:
        df = pd.read_csv(input_tsv_path, sep='\t')
    except FileNotFoundError:
        print(f"ERRO: Arquivo de transcrição não encontrado: {input_tsv_path}.")
        raise

    if df.empty:
        print("A transcrição está vazia. Nenhum segmento pode ser gerado.")
        return {"segments": []}
    
    # Adiciona a verificação de tipo e conversão, se necessário.
    if df['start'].dtype != float or df['end'].dtype != float:
        df['start'] = df['start'] / 1000
        df['end'] = df['end'] / 1000
        print("DEBUG: Colunas 'start' e 'end' convertidas para segundos.")

    # --- Configuração de Chunking ---
    CHUNK_DURATION_SEC = 600  # 10 minutos por chunk
    OVERLAP_DURATION_SEC = 10   # 10 segundos de sobreposição

    transcript_chunks = get_transcript_chunks(df, CHUNK_DURATION_SEC, OVERLAP_DURATION_SEC)
    
    if not transcript_chunks:
        print("Nenhum chunk de transcrição foi gerado. Verifique os dados de entrada.")
        return {"segments": []}

    all_potential_segments = []

    for i, chunk_info in enumerate(transcript_chunks):
        chunk_text = chunk_info['chunk_text']
        chunk_offset = chunk_info['start_time_offset']

        print(f"Processando chunk {i+1}/{len(transcript_chunks)} (Início: {chunk_offset:.2f}s)...")

        # Build the prompt for the AI
        if viral_mode:
            theme_prompt = "analisando a transcrição para encontrar os momentos mais virais e de maior impacto."
        else:
            theme_prompt = f"com base nos seguintes temas: {themes}."

        # O prompt agora inclui o offset do chunk e instrui o LLM a retornar tempos absolutos
        prompt = f"""
        "Based on THIS TRANSCRIPT EXCERPT, act as an expert in viral video cuts for social media, {theme_prompt}
        Identify all the themes covered and select segments that have between {tempo_minimo} and {tempo_maximo} seconds with the highest virality scores.
        If you identify more than one theme in the description, try to distribute the segments among them. Ignore long introductions and pauses.
        THE SEGMENTS MUST MAKE SENSE ON THEIR OWN, even when viewed out of context.
        IT IS CRITICAL that the start and end times are ABSOLUTE in relation to the beginning of the FULL VIDEO, considering that this transcript begins approximately at the second {chunk_offset:.2f} of the original video.
        For each segment, provide:
        - The start and end times (in seconds), ABSOLUTE in relation to the beginning of the video.
        - A short and attractive title in Portuguese (maximum 5 words).
        - A brief description of why this segment is a good fit (maximum 15 words).
        - A 'virality' score from 0 to 100.
        - A list of up to 5 keywords in Portuguese that summarize the topic of the segment.

        The response MUST be a valid JSON object, with no additional text before or after.
        The JSON format should be:
        {{
          "segments": [
            {{
              "start": <start_time_in_seconds>,
              "end": <end_time_in_seconds>,
              "title": "<title>",
              "description": "<description>",
              "score": <score>,
              "keywords": ["<keyword1>", "<keyword2>", "..."]
            }}
          ]
        }}

        Transcription of the excerpt:
        '{chunk_text}'"
        """

        try:
            response = g4f.ChatCompletion.create(
                model=g4f.models.gpt_4,
                messages=[{"role": "user", "content": prompt}],
            )
            # Clean the response to ensure it's valid JSON
            cleaned_response = response.strip().replace('```json', '').replace('```', '')
            chunk_viral_segments = json.loads(cleaned_response)
            
            for segment in chunk_viral_segments.get('segments', []):
                # Basic validation: ensure times are within reasonable bounds
                if segment.get('start', -1) >= 0 and segment.get('end', 0) > segment.get('start', -1):
                    all_potential_segments.append(segment)

        except json.JSONDecodeError as e:
            print(f"ERRO: Falha ao decodificar JSON do chunk {i+1}. Resposta inválida: {cleaned_response}. Erro: {e}")
        except Exception as e:
            print(f"ERRO: Falha ao gerar ou processar segmentos virais para o chunk {i+1}. {e}")

    # --- Pós-processamento: Remover Duplicatas e Selecionar os Melhores ---
    print("Agregando e filtrando segmentos de todos os chunks...")

    unique_segments = {}
    for segment in all_potential_segments:
        # Usar uma tupla (start_rounded, end_rounded, title) como chave para identificar "duplicatas"
        key = (round(segment.get('start', 0), 1), round(segment.get('end', 0), 1), segment.get('title', '').lower())
        
        if key not in unique_segments or segment.get('score', 0) > unique_segments[key].get('score', 0):
            unique_segments[key] = segment

    final_segments = list(unique_segments.values())

    # Ordenar por score de viralidade (descendente) e pegar os 'num_segments' melhores
    final_segments.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    final_segments_to_save = {"segments": final_segments[:max(0, num_segments)]}

    # Save the segments to the specified file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_segments_to_save, f, ensure_ascii=False, indent=4)

    print(f"Segmentos virais finais ({len(final_segments_to_save['segments'])} selecionados) salvos em {output_path}")

    # --- NOVO: Gerar transcrição dos segmentos ---
    print("Gerando transcrição dos segmentos selecionados...")
    for idx, segment in enumerate(final_segments_to_save.get('segments', [])):
        start_time = segment.get('start', 0)
        end_time = segment.get('end', 0)
        # Transcrição nomeada de acordo com o padrão de corte: output000.tsv, output001.tsv, etc.
        transcription_output_path = os.path.join('tmp', f"output{idx:03d}.tsv") 
        with open(transcription_output_path, 'w', encoding='utf-8') as f:
            f.write("start\tend\ttext\n") 
            # Garante que a transcrição do segmento comece em 0 para o PyCaps
            segment_transcription = df[(df['start'] >= start_time) & (df['end'] <= end_time)].copy()
            segment_transcription['start'] = segment_transcription['start'] - start_time
            segment_transcription['end'] = segment_transcription['end'] - start_time
            for _, row in segment_transcription.iterrows():
                f.write(f"{row['start']:.3f}\t{row['end']:.3f}\t{row['text']}\n")
        print(f"Transcrição do segmento {idx} salva em {transcription_output_path}")

    return final_segments_to_save