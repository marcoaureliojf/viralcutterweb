import cv2
import subprocess
import os
import shutil

def edit(clips_data: dict):
    """
    Processa os vídeos criando um efeito de TELA DIVIDIDA e QUEIMANDO AS LEGENDAS
    em um único e eficiente comando FFmpeg.
    """
    print("Iniciando processo de TELA DIVIDIDA e QUEIMA DE LEGENDAS...")
    output_dir = 'burned_sub'
    subtitle_dir = 'subs_ass'
    os.makedirs(output_dir, exist_ok=True)

    for video_path, data in clips_data.items():
        if not os.path.exists(video_path):
            print(f"AVISO: Arquivo de vídeo não encontrado, pulando: {video_path}")
            continue

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        subtitle_path = os.path.join(subtitle_dir, f"{base_name}.ass")

        if not os.path.exists(subtitle_path):
            print(f"AVISO: Arquivo de legenda não encontrado para {video_path}. O vídeo será gerado sem legendas.")
            subtitle_path = None

        print(f"Processando clipe: {video_path}")
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

        if subtitle_path:
            # --- MUDANÇA CRÍTICA AQUI ---
            # Passa o caminho absoluto do Linux de forma limpa, sem escapes desnecessários.
            subtitle_abs_path = os.path.abspath(subtitle_path)
            filter_complex_string += f";[vstack_out]subtitles='{subtitle_abs_path}'[out]"
        else:
            filter_complex_string += ";[vstack_out]copy[out]"
        
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
        
        print(f"Executando comando FFmpeg para {final_output_path}...")
        # Imprime o comando exato que será executado para facilitar a depuração manual
        print(" ".join(command)) 
        
        try:
            # Modificação: capture stdout e stderr para diagnóstico
            result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
            print("Processo combinado (tela dividida e legendas) concluído com sucesso.")
            # A saída do FFmpeg pode conter avisos úteis, mesmo em caso de sucesso
            if result.stderr:
                print(f"Avisos do FFmpeg (stderr):\n{result.stderr}")

        except subprocess.CalledProcessError as e:
            # Erro fatal: Imprime o stdout e stderr para entender a causa
            print(f"ERRO FATAL ao aplicar filtro combinado: {e}")
            print(f"--- STDOUT ---\n{e.stdout}")
            print(f"--- STDERR (Causa Provável do Erro) ---\n{e.stderr}")
            raise