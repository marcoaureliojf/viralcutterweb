import os
import subprocess

def is_video_valid(file_path: str) -> bool:
    """Verifica se o vídeo é válido usando ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return bool(result.stdout.strip())  # se encontrou codec de vídeo, é válido
    except subprocess.CalledProcessError:
        return False

def is_valid_video(path: str) -> bool:
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True
        )
        return bool(probe.stdout.strip())
    except subprocess.CalledProcessError:
        return False
    
def cut(viral_segments, input_video_path):
    print("Iniciando o corte dos segmentos de vídeo...")
    output_dir = "tmp"
    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    for i, segment in enumerate(viral_segments["segments"]):
        start_time = segment["start"]
        end_time = segment["end"]
        output_filename = os.path.join(output_dir, f"output{str(i).zfill(3)}.mp4")

        # 1️⃣ Tenta com -c copy (rápido)
        #copy_cmd = [
        #    "ffmpeg",
        #    "-ss", str(start_time),  # seeking antes do input é mais preciso
        #    "-i", input_video_path,
        #    "-t", str(end_time - start_time),  # duração em vez de tempo final
        #    "-c", "copy",
        #    "-async", "1",  # ressincroniza o áudio
        #    "-y",
        #    output_filename,
        #]

        success = False
        #try:
        #    subprocess.run(copy_cmd, check=True, capture_output=True, text=True)
        #    if is_video_valid(output_filename):
        #        print(f"Segmento {i} cortado com sucesso (copy): {output_filename}")
        #        success = True
        #    else:
        #        print(f"Segmento {i} com copy resultou inválido, tentando reencode...")
        #except subprocess.CalledProcessError as e:
        #    print(f"Erro ao cortar segmento {i} com copy: {e.stderr}")

        # 2️⃣ Se falhar, reencode com qualidade alta
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
                subprocess.run(reencode_cmd, check=True, capture_output=True, text=True)
                if not is_valid_video(output_filename):
                    raise ValueError(f"Arquivo de saída inválido: {output_filename}")
                success = True
            except subprocess.CalledProcessError as e:
                print(f"ERRO ao cortar segmento {i} mesmo com reencode:\nStderr: {e.stderr}")
                raise

        if success:
            created_files.append(output_filename)

    return created_files
