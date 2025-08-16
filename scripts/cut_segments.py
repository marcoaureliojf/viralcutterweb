import subprocess
import os

def cut(viral_segments, input_video_path):
    print("Iniciando o corte dos segmentos de vídeo...")
    output_dir = 'tmp'
    os.makedirs(output_dir, exist_ok=True)
    
    created_files = []
    for i, segment in enumerate(viral_segments['segments']):
        start_time = segment['start']
        end_time = segment['end']
        output_filename = os.path.join(output_dir, f"output{str(i).zfill(3)}_original_scale.mp4")
        command = ['ffmpeg', '-i', input_video_path, '-ss', str(start_time), '-to', str(end_time), '-c', 'copy', '-y', output_filename]
        
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Segmento {i} cortado com sucesso: {output_filename}")
            created_files.append(output_filename)
        except subprocess.CalledProcessError as e:
            print(f"ERRO ao cortar o segmento {i}:\nStderr: {e.stderr}")
            raise
    return created_files