import os
import subprocess
from .utils import _is_valid_video # Importa a função de validação

def cut(viral_segments, input_video_path):
    print("Iniciando o corte dos segmentos de vídeo...")
    output_dir = "tmp"
    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    for i, segment in enumerate(viral_segments["segments"]):
        start_time = segment["start"]
        end_time = segment["end"]
        duration = end_time - start_time
        output_filename = os.path.join(output_dir, f"output{str(i).zfill(3)}.mp4")

        # 1️⃣ Tenta com -c copy (rápido)
        copy_cmd = [
            "ffmpeg",
            "-ss", str(start_time),  
            "-i", input_video_path,
            "-t", str(duration),  
            "-c", "copy",
            "-async", "1",  
            "-y",
            output_filename,
        ]

        success = False
        try:
            print(f"Tentando cortar segmento {i} com -c copy...")
            subprocess.run(copy_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            if _is_valid_video(output_filename):
                print(f"Segmento {i} cortado com sucesso (copy): {output_filename}")
                success = True
            else:
                print(f"Segmento {i} com copy resultou inválido, tentando reencode...")
                if os.path.exists(output_filename): os.remove(output_filename) # Limpa o arquivo inválido
        except subprocess.CalledProcessError as e:
            print(f"Erro ao cortar segmento {i} com copy: {e.stderr}. Tentando reencode.")
            if os.path.exists(output_filename): os.remove(output_filename)

        # 2️⃣ Se falhar ou for inválido, reencode com qualidade alta
        if not success:
            reencode_cmd = [
                "ffmpeg",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", input_video_path,
                "-c:v", "libx264",
                "-preset", "faster",
                "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                "-y",
                output_filename,
            ]
            try:
                print(f"Tentando reencode para segmento {i}...")
                subprocess.run(reencode_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
                if not _is_valid_video(output_filename):
                    raise ValueError(f"Arquivo de saída inválido: {output_filename}")
                print(f"Segmento {i} cortado com sucesso (reencode): {output_filename}")
                success = True
            except subprocess.CalledProcessError as e:
                print(f"ERRO ao cortar segmento {i} mesmo com reencode:\nStderr: {e.stderr}")
                raise

        if success:
            created_files.append(output_filename)

    return created_files