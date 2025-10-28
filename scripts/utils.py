import os
import subprocess
from typing import Optional, Dict

def get_videos_processed():
    """Retorna o número total de vídeos processados"""
    outputs_dir = "outputs"
    if os.path.exists(outputs_dir):
        return len([f for f in os.listdir(outputs_dir) if f.endswith('.mp4')])
    return 0

def get_time_saved():
    """Calcula o tempo economizado (estimativa: 1h por vídeo processado)"""
    return get_videos_processed() * 1

def get_success_clips():
    """Retorna número de clips de sucesso (estimativa)"""
    return get_videos_processed() * 3  # Assumindo 3 clips por vídeo

def _is_valid_video(file_path: str) -> bool:
    """Verifica se o vídeo é válido (possui stream de vídeo) usando ffprobe."""
    try:
        # Tenta extrair o nome do codec do stream de vídeo (v:0)
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
            check=False # Não levanta exceção se ffprobe falhar, apenas verifica a saída
        )
        # Se a saída não estiver vazia, um codec de vídeo foi encontrado
        return bool(result.stdout.strip())
    except Exception:
        return False

def get_video_fps(video_path: str) -> Optional[str]:
    """
    Usa ffprobe para detectar o framerate de um vídeo e o retorna como uma fração (string).
    Retorna None se a detecção falhar.
    """
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        fps_fraction = result.stdout.strip()
        
        if not fps_fraction:
            print(f"⚠️ FFprobe não retornou um FPS para o vídeo: {video_path}")
            return None
            
        return fps_fraction
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar ffprobe (FPS) no arquivo {video_path}: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ Ocorreu um erro inesperado ao obter o FPS: {e}")
        return None

def get_video_dimensions(video_path: str) -> Optional[Dict[str, int]]:
    """
    Usa ffprobe para detectar a largura e altura de um vídeo.
    """
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        video_path
    ]
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        
        # O resultado JSON é complexo; tentaremos analisar a largura e altura
        import json
        data = json.loads(result.stdout)
        
        if 'streams' in data and data['streams']:
            width = data['streams'][0].get('width')
            height = data['streams'][0].get('height')
            if width and height:
                return {'width': int(width), 'height': int(height)}
                
        return None
        
    except Exception as e:
        print(f"❌ Erro ao obter dimensões do vídeo com ffprobe: {e}")
        return None