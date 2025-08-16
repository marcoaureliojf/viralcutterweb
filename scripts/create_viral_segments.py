import g4f
import pandas as pd
import json
import os

def create(num_segments, viral_mode, themes, tempo_minimo, tempo_maximo):
    """
    Analyzes the transcription and generates a list of potential viral segments.
    """
    print("Analisando transcrição para encontrar segmentos virais...")

    # Define the output path for the viral segments
    output_path = os.path.join('tmp', 'viral_segments.txt')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Read the transcription data
    try:
        df = pd.read_csv(os.path.join('tmp', 'input_video.tsv'), sep='\t')
    except FileNotFoundError:
        print("ERRO: Arquivo 'input_video.tsv' não encontrado. A transcrição falhou.")
        raise

    full_transcript = " ".join(df['text'].astype(str))

    # Build the prompt for the AI
    if viral_mode:
        theme_prompt = "analisando a transcrição para encontrar os momentos mais virais e de maior impacto."
    else:
        theme_prompt = f"com base nos seguintes temas: {themes}."

    prompt = f"""
    "Com base na transcrição fornecida, atue como um especialista em cortes de vídeo para redes sociais, {theme_prompt}
    Identifique {num_segments} segmentos que tenham entre {tempo_minimo} e {tempo_maximo} segundos.
    Para cada segmento, forneça:
    - O tempo de início e fim (em segundos).
    - Um título curto e atraente (máximo de 5 palavras).
    - Uma breve descrição do porquê esse segmento é um bom corte (máximo de 15 palavras).
    - Uma pontuação de 'viralidade' de 0 a 100.

    A resposta DEVE ser um objeto JSON válido, sem nenhum texto adicional antes ou depois.
    O formato JSON deve ser:
    {{
      "segments": [
        {{
          "start": <start_time_in_seconds>,
          "end": <end_time_in_seconds>,
          "title": "<title>",
          "description": "<description>",
          "score": <score>
        }}
      ]
    }}

    Transcrição:
    '{full_transcript}'"
    """

    print("Enviando prompt para o modelo de linguagem...")
    try:
        response = g4f.ChatCompletion.create(
            # --- ESTA É A LINHA CORRIGIDA ---
            # Substituído o modelo obsoleto pelo modelo padrão e mais estável.
            model=g4f.models.gpt_4,
            messages=[{"role": "user", "content": prompt}],
        )
        print("Resposta recebida do modelo.")
        # Clean the response to ensure it's valid JSON
        cleaned_response = response.strip().replace('```json', '').replace('```', '')
        viral_segments = json.loads(cleaned_response)

        # Save the segments to the specified file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(viral_segments, f, ensure_ascii=False, indent=4)

        print(f"Segmentos virais salvos em {output_path}")
        return viral_segments

    except Exception as e:
        print(f"ERRO: Falha ao gerar ou processar segmentos virais. {e}")
        raise