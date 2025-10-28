import subprocess
import os
import shutil
from .pycaps_processing import process_with_pycaps
from .utils import get_video_fps, get_video_dimensions # Importa funções de utils

# Constante para o caminho da fonte (facilita a portabilidade/ajuste)
FONT_PATH = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'

def edit(clips_data: dict, pycaps_template: str):
    """
    Mantém a edição de TELA DIVIDIDA + TÍTULO com FFmpeg (gera vídeo intermediário),
    e então usa PyCaps para gerar/queimar legendas automaticamente.
    Saída final: burned_sub/{base_name}_final.mp4
    """
    print("Iniciando processo de TELA DIVIDIDA + TÍTULOS (FFmpeg) e LEGENDAS (PyCaps)...")

    output_dir = 'burned_sub'
    os.makedirs(output_dir, exist_ok=True)

    for video_path, data in clips_data.items():
        if not os.path.exists(video_path):
            print(f"⚠️ Arquivo de vídeo não encontrado, pulando: {video_path}")
            continue

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        title_text = data.get('title', '')
        segment_tsv_path = data.get('segment_tsv_path') # Caminho do TSV do segmento na pasta 'tmp'
        
        # --- 1. DETECÇÃO AUTOMÁTICA ---
        print(f"🔎 Detectando FPS e Dimensões para: {video_path}...")
        framerate = get_video_fps(video_path)
        dimensions = get_video_dimensions(video_path)
        
        if not framerate or not dimensions: 
            print(f"❌ Não foi possível determinar FPS ou Dimensões. Pulando o vídeo: {video_path}")
            continue

        frame_width = dimensions['width']
        frame_height = dimensions['height']
        print(f"✅ FPS detectado: {framerate}. Dimensões: {frame_width}x{frame_height}")

        # --- 2. PREPARAÇÃO DO FILTRO DE TÍTULO ---
        escaped_title = (
            title_text.replace("'", "\\'")
                      .replace(":", "\\:")
                      .replace(",", "\\,")
        )
        title_filter = (
            f"drawtext=fontfile='{FONT_PATH}':text='{escaped_title}':"
            "fontcolor=white:fontsize=60:box=1:boxcolor=black@0.5:boxborderw=10:"
            "x=(w-text_w)/2:y=50"
        )

        # --- 3. DIMENSÕES / ROIs ---
        roi1 = data['roi1']
        roi2 = data['roi2']

        # Converte percentuais para pixels
        roi1_px = {
            'x': int(frame_width * roi1['x'] / 100),
            'y': int(frame_height * roi1['y'] / 100),
            'w': int(frame_width * roi1['w'] / 100),
            'h': int(frame_height * roi1['h'] / 100)
        }
        roi2_px = {
            'x': int(frame_width * roi2['x'] / 100),
            'y': int(frame_height * roi2['y'] / 100),
            'w': int(frame_width * roi2['w'] / 100),
            'h': int(frame_height * roi2['h'] / 100)
        }

        final_w = 1080
        final_h_half = 960

        filter_roi1 = (
            f"crop={roi1_px['w']}:{roi1_px['h']}:{roi1_px['x']}:{roi1_px['y']},"
            f"scale={final_w}:{final_h_half}"
        )
        filter_roi2 = (
            f"crop={roi2_px['w']}:{roi2_px['h']}:{roi2_px['x']}:{roi2_px['y']},"
            f"scale={final_w}:{final_h_half}"
        )

        # --- 4. NOVO FILTER_COMPLEX ---
        filter_complex_string = (
            # Reset timestamps e primeira transformação
            f"[0:v]setpts=PTS-STARTPTS,{filter_roi1}[top];"
            # Reset timestamps e segunda transformação
            f"[0:v]setpts=PTS-STARTPTS,{filter_roi2}[bottom];"
            # Combina as duas partes
            f"[top][bottom]vstack=inputs=2[stacked];"
            # Adiciona o título
            f"[stacked]{title_filter}[video_out];"
            # Reset timestamp do áudio separadamente
            f"[0:a]asetpts=PTS-STARTPTS[audio_out]"
        )

        # --- 5. Saída intermediária e preparação do PyCaps ---
        intermediate_path = os.path.join(output_dir, f"{base_name}_no_subs.mp4")
        final_output_path = os.path.join(output_dir, f"{base_name}_final.mp4")
        
        # PyCaps requer que o TSV esteja ao lado do vídeo com o mesmo nome
        pycaps_tsv_path = os.path.splitext(intermediate_path)[0] + ".tsv" 
        
        if not os.path.exists(segment_tsv_path):
            print(f"❌ TSV do segmento não encontrado em: {segment_tsv_path}. Pulando as legendas.")
            # Se o TSV falhar, define o final como a versão sem legendas e pula o PyCaps
            shutil.copy(intermediate_path, final_output_path)
            continue
            
        # Move o TSV de 'tmp' para 'burned_sub' com o nome do vídeo intermediário
        shutil.copy(segment_tsv_path, pycaps_tsv_path)

        command = [
            'ffmpeg', '-i', video_path,
            '-filter_complex', filter_complex_string,
            '-map', '[video_out]',
            '-map', '[audio_out]',
            '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
            '-g', '30', '-keyint_min', '30',
            '-r', framerate, 
            '-vsync', 'cfr',     
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            '-y', intermediate_path
        ]

        print(f"🎬 Gerando versão SEM legendas: {intermediate_path} ...")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro no FFmpeg: {e.stderr}")
            raise
        
        # --- 6. Chama o script de legendas ---
        process_with_pycaps(intermediate_path, final_output_path, pycaps_template)
        
        # Limpa o TSV copiado após o PyCaps
        if os.path.exists(pycaps_tsv_path):
            os.remove(pycaps_tsv_path)

    print("Todos os vídeos processados.")