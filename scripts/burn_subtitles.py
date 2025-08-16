import subprocess
import os
from glob import glob

def burn():
    """
    Burns the generated .ass subtitles onto the corresponding processed videos.
    """
    print("Iniciando a queima de legendas nos vídeos...")
    video_dir = 'final'
    subtitle_dir = 'subs_ass'
    output_dir = 'burned_sub'
    os.makedirs(output_dir, exist_ok=True)
    
    video_files = glob(os.path.join(video_dir, '*_processed.mp4'))
    if not video_files:
        print("AVISO: Nenhum vídeo processado encontrado para queimar legendas.")
        return

    for video_path in video_files:
        base_name = os.path.basename(video_path).replace('_processed.mp4', '')
        subtitle_path = os.path.join(subtitle_dir, f"{base_name}_processed.ass")
        output_path = os.path.join(output_dir, f"{base_name}_processed_subtitled.mp4")

        if not os.path.exists(subtitle_path):
            print(f"AVISO: Legenda não encontrada em {subtitle_path} para o vídeo {video_path}. Pulando.")
            continue

        # FFmpeg requires a specific path format for the subtitles filter on Windows
        # We escape colons and backslashes
        # escaped_subtitle_path = subtitle_path.replace('\\', '/').replace(':', '\\:')

        command = [
            'ffmpeg',
            '-i', video_path,
            '-vf', f"subtitles='{subtitle_path}'",
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'fast',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        print(f"Executando comando para queimar legenda em {base_name}: {' '.join(command)}")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Legenda queimada com sucesso: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"ERRO ao queimar a legenda no vídeo {base_name}:")
            print(f"Stderr: {e.stderr}")
            raise