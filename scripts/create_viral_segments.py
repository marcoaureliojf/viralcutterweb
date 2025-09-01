import g4f
import pandas as pd
import json
import os

def get_transcript_chunks(df: pd.DataFrame, chunk_duration_sec: int, overlap_duration_sec: int):
    """
    Divide o DataFrame da transcrição em chunks de duração específica com sobreposição.
    Retorna uma lista de dicionários, onde cada dicionário contém:
    - 'chunk_text': A transcrição concatenada do chunk.
    - 'start_time_offset': O tempo de início (em segundos) do chunk em relação ao vídeo completo.
    """
    chunks = []
    total_duration = df['end'].max() if not df.empty else 0
    current_start_time = 0.0

    while current_start_time < total_duration:
        chunk_end_time = min(current_start_time + chunk_duration_sec, total_duration)

        # Seleciona as linhas do DataFrame que caem dentro do chunk atual
        # Adicionamos uma pequena margem para garantir que a última palavra do chunk esteja incluída
        chunk_df = df[(df['start'] >= current_start_time - 0.1) & (df['end'] <= chunk_end_time + 0.1)].copy()

        if not chunk_df.empty:
            chunk_text = " ".join(chunk_df['text'].astype(str))
            
            # Garantir que o offset do chunk seja o 'start' real do primeiro item
            # ou o 'current_start_time' se for mais preciso para o propósito de contexto.
            # Aqui, usaremos o 'current_start_time' como referência para o LLM.
            chunks.append({
                "chunk_text": chunk_text,
                "start_time_offset": current_start_time
            })
        else:
            # Se não houver texto no chunk, mas ainda houver duração total,
            # avançamos para evitar loops infinitos em espaços vazios.
            pass

        # Move o ponteiro para o próximo chunk, considerando a sobreposição
        current_start_time += (chunk_duration_sec - overlap_duration_sec)
        
        # Garante que não haja sobreposição negativa caso o chunk_duration_sec seja menor que overlap_duration_sec
        if current_start_time < 0: 
            current_start_time = 0

    return chunks


def create(num_segments, viral_mode, themes, tempo_minimo, tempo_maximo):
    """
    Analyzes the transcription and generates a list of potential viral segments,
    using chunking with overlap for long videos. It also extracts keywords for each
    segment and saves them to separate .tsv files corresponding to the video segments.
    """
    print("Analisando transcrição para encontrar segmentos virais...")

    # Define the output paths
    output_path = os.path.join('tmp', 'viral_segments.txt')
    keywords_output_path = os.path.join('tmp', 'viral_segments_keywords.txt')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Read the transcription data
    try:
        df = pd.read_csv(os.path.join('tmp', 'input_video.tsv'), sep='\t')
    except FileNotFoundError:
        print("ERRO: Arquivo 'input_video.tsv' não encontrado. A transcrição falhou.")
        raise

    if df.empty:
        print("A transcrição está vazia. Nenhum segmento pode ser gerado.")
        return {"segments": []}
    
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

        # O prompt agora inclui o offset do chunk e instrui o LLM a retornar tempos absolutos e palavras-chave
        prompt = f"""
        "Com base NESTE TRECHO DA TRANSCRIÇÃO, atue como um especialista em cortes de vídeo virais para redes sociais, {theme_prompt}
        Identifique todos os temas tratados e selecione segmentos que tenham entre {tempo_minimo} e {tempo_maximo} segundos com as maiores pontuações de viralidade.
        Caso identifique mais de um tema na descrição, tente distribuir os segmentos entre os temas. Ignore introduções longas e pausas.
        OS SEGMENTOS DEVEM FAZER SENTIDO POR SI SÓ, mesmo que vistos fora de contexto.
        É CRÍTICO que os tempos de início e fim (start e end) sejam ABSOLUTOS em relação ao início do VÍDEO COMPLETO, considerando que este trecho da transcrição inicia aproximadamente no segundo {chunk_offset:.2f} do vídeo original.
        Para cada segmento, forneça:
        - O tempo de início e fim (em segundos), ABSOLUTO em relação ao início do vídeo.
        - Um título em português, curto e atraente (máximo de 5 palavras).
        - Uma breve descrição do porquê esse segmento é um bom corte (máximo de 15 palavras).
        - Uma pontuação de 'viralidade' de 0 a 100.
        - Uma lista de até 5 palavras-chave (keywords) em português que resumem o tema do segmento.

        A resposta DEVE ser um objeto JSON válido, sem nenhum texto adicional antes ou depois.
        O formato JSON deve ser:
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

        Transcrição do Trecho:
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
            
            # Adicionar os segmentos do chunk à lista geral
            for segment in chunk_viral_segments.get('segments', []):
                # Basic validation: ensure times are within reasonable bounds
                if segment.get('start', -1) >= 0 and segment.get('end', 0) > segment.get('start', -1):
                    all_potential_segments.append(segment)

        except json.JSONDecodeError as e:
            print(f"ERRO: Falha ao decodificar JSON do chunk {i+1}. Resposta inválida: {cleaned_response}. Erro: {e}")
        except Exception as e:
            print(f"ERRO: Falha ao gerar ou processar segmentos virais para o chunk {i+1}. {e}")
            # Decide if you want to continue or stop

    # --- Pós-processamento: Remover Duplicatas e Selecionar os Melhores ---
    print("Agregando e filtrando segmentos de todos os chunks...")

    unique_segments = {}
    for segment in all_potential_segments:
        # Arredondar tempos para evitar problemas de float e considerá-los "iguais" se estiverem muito próximos
        # Usar uma tupla (start_rounded, end_rounded, title) como chave para identificar "duplicatas"
        key = (round(segment.get('start', 0), 1), round(segment.get('end', 0), 1), segment.get('title', '').lower())
        
        # Se um segmento com a mesma chave já existe, mantenha o de maior score
        if key not in unique_segments or segment.get('score', 0) > unique_segments[key].get('score', 0):
            unique_segments[key] = segment

    final_segments = list(unique_segments.values())

    # Ordenar por score de viralidade (descendente) e pegar os 'num_segments' melhores
    final_segments.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Garante que pegue no máximo o número de segmentos disponíveis.
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
        transcription_output_path = os.path.join('tmp', f"output{idx:03d}.tsv")
        with open(transcription_output_path, 'w', encoding='utf-8') as f:
            f.write("start\tend\ttext\n")  # Cabeçalho do arquivo TSV
            segment_transcription = df[(df['start'] >= start_time) & (df['end'] <= end_time)]
            for _, row in segment_transcription.iterrows():
                f.write(f"{row['start']:.3f}\t{row['end']:.3f}\t{row['text']}\n")
        print(f"Transcrição do segmento {idx} salva em {transcription_output_path}")
    # --- FIM DO NOVO BLOCO ---

    return final_segments_to_save