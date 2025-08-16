import pandas as pd
import os
import subprocess

def get_duration(video_path: str) -> float:
    """Obtém a duração do vídeo em segundos usando ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"⚠️ Erro ao obter duração de {video_path}: {e}")
        return None

def adjust(clip_paths):
    """
    Cria arquivos de legenda .ass estilizados a partir dos arquivos .tsv correspondentes,
    normalizando tempos, descartando legendas fora da duração do clipe
    e aplicando efeito karaoke palavra a palavra.
    """
    print("Ajustando e estilizando legendas (KARAOKE palavra a palavra)...")
    subs_dir = 'subs'
    output_dir = 'subs_ass'
    os.makedirs(output_dir, exist_ok=True)
    
    for clip_path in clip_paths:
        base_name = os.path.splitext(os.path.basename(clip_path))[0]
        tsv_file = os.path.join(subs_dir, f"{base_name}.tsv")

        if not os.path.exists(tsv_file):
            print(f"⚠️ TSV não encontrado para {base_name}, pulando. Procurado em: {tsv_file}")
            continue
        
        df = pd.read_csv(tsv_file, sep='\t')
        if df.empty:
            print(f"⚠️ TSV vazio para {base_name}, nenhuma legenda será gerada.")
            continue

        duration = get_duration(clip_path)
        if not duration:
            print(f"⚠️ Duração do vídeo não encontrada para {base_name}, pulando.")
            continue

        # Converte ms → segundos
        df['start'] = df['start'] / 1000.0
        df['end']   = df['end'] / 1000.0

        ass_path = os.path.join(output_dir, f"{base_name}.ass")
        with open(ass_path, 'w', encoding='utf-8') as f:
            # Header e estilos
            f.write("[Script Info]\nTitle: ViralCutter\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n")
            f.write("[V4+ Styles]\n")
            f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                    "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: Default,Arial,55,&H00FFFFFF,&H0000FFFF,&H00000000,&H60000000,"
                    "-1,0,0,0,100,100,0,0,1,3,1.5,5,10,10,60,1\n\n") 
            f.write("[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

            for _, row in df.iterrows():
                start_s = float(row['start'])
                end_s = float(row['end'])

                if start_s >= duration:
                    continue
                if end_s > duration:
                    end_s = duration

                # Converte para formato ASS
                start_time = f"{int(start_s // 3600)}:{int((start_s % 3600) // 60):02d}:{int(start_s % 60):02d}.{int((start_s - int(start_s)) * 100):02d}"
                end_time   = f"{int(end_s // 3600)}:{int((end_s % 3600) // 60):02d}:{int(end_s % 60):02d}.{int((end_s - int(end_s)) * 100):02d}"

                text = str(row['text']).strip().replace('\n', ' ')
                words = text.split()

                # Karaoke palavra a palavra
                if words:
                    per_word = int(((end_s - start_s) * 100) / len(words))  # centésimos
                    karaoke_tag = "".join([f"{{\\k{per_word}}}{w} " for w in words])
                else:
                    karaoke_tag = ""

                f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{karaoke_tag.strip()}\n")

        print(f"Arquivo de legenda criado: {ass_path} (Duração do clipe: {duration:.2f}s)")
