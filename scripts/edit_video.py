import cv2
import subprocess
import os

def edit(clips_data: dict):
    """
    Processa os vídeos criando um efeito de TELA DIVIDIDA, QUEIMANDO AS LEGENDAS
    e ADICIONANDO UM TÍTULO em um único e eficiente comando FFmpeg.
    """
    print("Iniciando processo de TELA DIVIDIDA, LEGENDAS e TÍTULOS...")
    output_dir = 'burned_sub'
    subtitle_dir = 'subs_ass'
    os.makedirs(output_dir, exist_ok=True)

    for video_path, data in clips_data.items():
        if not os.path.exists(video_path):
            print(f"AVISO: Arquivo de vídeo não encontrado, pulando: {video_path}")
            continue

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        subtitle_path = os.path.join(subtitle_dir, f"{base_name}.ass")
        title_text = data.get('title', '')

        # --- PREPARAÇÃO DO FILTRO DE TÍTULO (drawtext) ---
        # Escapa caracteres especiais que podem quebrar o comando FFmpeg
        escaped_title = title_text.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")
        
        # Define a fonte (deve existir no container Docker)
        font_path = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'

        # Configurações do filtro drawtext: texto centralizado no topo com fundo semitransparente
        title_filter = (
            f"drawtext=fontfile='{font_path}':text='{escaped_title}':"
            "fontcolor=white:fontsize=60:box=1:boxcolor=black@0.5:boxborderw=10:"
            "x=(w-text_w)/2:y=50"
        )

        cap = cv2.VideoCapture(video_path)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        roi1 = data['roi1']; roi2 = data['roi2']
        roi1_px = { 'x': int(frame_width * roi1['x']/100), 'y': int(frame_height * roi1['y']/100), 'w': int(frame_width * roi1['w']/100), 'h': int(frame_height * roi1['h']/100) }
        roi2_px = { 'x': int(frame_width * roi2['x']/100), 'y': int(frame_height * roi2['y']/100), 'w': int(frame_width * roi2['w']/100), 'h': int(frame_height * roi2['h']/100) }

        final_w = 1080; final_h_half = 960
        
        filter_roi1 = f"crop={roi1_px['w']}:{roi1_px['h']}:{roi1_px['x']}:{roi1_px['y']},scale={final_w}:{final_h_half}"
        filter_roi2 = f"crop={roi2_px['w']}:{roi2_px['h']}:{roi2_px['x']}:{roi2_px['y']},scale={final_w}:{final_h_half}"

        filter_complex_string = (
            f"[0:v]split=2[v1][v2];"
            f"[v1]{filter_roi1}[top];"
            f"[v2]{filter_roi2}[bottom];"
            f"[top][bottom]vstack=inputs=2[vstack_out]"
        )

        # --- ENCADEAMENTO DE FILTROS ATUALIZADO ---
        # A saída de um filtro se torna a entrada do próximo
        last_video_stream = "[vstack_out]"
        
        if os.path.exists(subtitle_path):
            subtitle_abs_path = os.path.abspath(subtitle_path)
            filter_complex_string += f";{last_video_stream}subtitles=filename='{subtitle_abs_path}'[subtitled_out]"
            last_video_stream = "[subtitled_out]"

        # Adiciona o filtro de título na cadeia
        filter_complex_string += f";{last_video_stream}{title_filter}[out]"
        
        final_output_path = os.path.join(output_dir, f"{base_name}_final.mp4")

        command = [
            'ffmpeg', '-i', video_path,
            '-filter_complex', filter_complex_string,
            '-map', '[out]',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'copy',
            '-y', final_output_path
        ]
        
        print(f"Aplicando filtro combinado para {final_output_path}...")
        print(" ".join(command))
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
            print("Processo combinado (tela dividida, legendas e título) concluído com sucesso.")
            if result.stderr:
                print(f"Avisos do FFmpeg (stderr):\n{result.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"ERRO FATAL ao aplicar filtro combinado: {e}")
            print(f"--- STDOUT ---\n{e.stdout}")
            print(f"--- STDERR (Causa Provável do Erro) ---\n{e.stderr}")
            raise