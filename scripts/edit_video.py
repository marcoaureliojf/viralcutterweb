import cv2
import subprocess
import os
from pycaps import TemplateLoader


def edit(clips_data: dict):
    """
    Mantém a edição de TELA DIVIDIDA + TÍTULO com FFmpeg (gera vídeo intermediário),
    e então usa PyCaps (TemplateLoader('hype')) para gerar/queimar legendas automaticamente.
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

        # --- PREPARAÇÃO DO FILTRO DE TÍTULO ---
        escaped_title = (
            title_text.replace("'", "\\'")
                      .replace(":", "\\:")
                      .replace(",", "\\,")
        )
        font_path = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
        title_filter = (
            f"drawtext=fontfile='{font_path}':text='{escaped_title}':"
            "fontcolor=white:fontsize=60:box=1:boxcolor=black@0.5:boxborderw=10:"
            "x=(w-text_w)/2:y=50"
        )

        # --- DIMENSÕES / ROIs ---
        cap = cv2.VideoCapture(video_path)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        roi1 = data['roi1']
        roi2 = data['roi2']

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

        # --- NOVO FILTER_COMPLEX COM RESET DE TIMESTAMPS ---
        filter_complex_string = (
            f"[0:v]{filter_roi1}[top];"
            f"[0:v]{filter_roi2}[bottom];"
            f"[top][bottom]vstack=inputs=2[vstack_out];"
            f"[vstack_out]{title_filter},"  # Adiciona uma vírgula aqui
            f"setpts=PTS-STARTPTS[out_v];"  # Adiciona o filtro para resetar o PTS do vídeo
            f"[0:a]asetpts=PTS-STARTPTS[out_a]"  # Adiciona o filtro para resetar o PTS do áudio
        )

        # --- Saída intermediária sem legendas ---
        intermediate_path = os.path.join(output_dir, f"{base_name}_no_subs.mp4")
        final_output_path = os.path.join(output_dir, f"{base_name}_final.mp4")

        command = [
            'ffmpeg', '-i', video_path,
            '-filter_complex', filter_complex_string,
            # Mapeia as saídas de vídeo e áudio do filter_complex
            '-map', '[out_v]',
            '-map', '[out_a]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-g', '30', '-keyint_min', '30',
            '-vsync', '1', # 'vsync 1' é obsoleto, mas pode ser trocado por '-r 30' (ou fps do seu vídeo) se quiser
            # O filtro 'aresample' não é mais necessário, pois o 'asetpts' já lida com a sincronia
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

        # --- Executa PyCaps (template) para gerar/queimar legendas automaticamente ---
        template = 'papo-de-preta'
        print(f"🔥 Executando PyCaps (template {template}) para gerar/queimar legendas...")
        try:
            builder = (
                TemplateLoader(template)
                .with_input_video(intermediate_path)
                .load(False)
            )
            builder.with_output_video(final_output_path)
            pipeline = builder.build()
            pipeline.run()
            print(f"✅ Processo PyCaps concluído: {final_output_path}")
        except Exception as e:
            print(f"❌ Erro ao rodar PyCaps (legendas): {e}")
            print("⚠️ Como fallback, vou manter a versão sem legendas como saída final.")

            if os.path.exists(intermediate_path):
                if os.path.exists(final_output_path):
                    os.remove(final_output_path)
                os.rename(intermediate_path, final_output_path)

            continue

        finally:
            if os.path.exists(intermediate_path):
                try:
                    os.remove(intermediate_path)
                except Exception:
                    pass

    print("Todos os vídeos processados.")
