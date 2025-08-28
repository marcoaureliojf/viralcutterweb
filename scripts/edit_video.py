import cv2
import subprocess
import os
import time
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

        filter_complex_string = (
            f"[0:v]split=2[v1][v2];"
            f"[v1]{filter_roi1}[top];"
            f"[v2]{filter_roi2}[bottom];"
            f"[top][bottom]vstack=inputs=2[vstack_out];"
            f"[vstack_out]{title_filter}[out]"
        )

        # --- Saída intermediária sem legendas ---
        intermediate_path = os.path.join(output_dir, f"{base_name}_no_subs.mp4")
        final_output_path = os.path.join(output_dir, f"{base_name}_final.mp4")

        command = [
            'ffmpeg', '-i', video_path,
            '-filter_complex', filter_complex_string,
            '-map', '[out]', '-map', '0:a?',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'copy', '-y', intermediate_path
        ]

        print(f"🎬 Gerando versão SEM legendas: {intermediate_path} ...")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro no FFmpeg: {e.stderr}")
            raise

        # --- Executa PyCaps (template 'hype') para gerar/queimar legendas automaticamente ---
        print(f"🔥 Executando PyCaps (template 'hype') para gerar/queimar legendas...")
        try:
            # Carrega o template 'hype' e obtém o builder (load(False) retorna o builder)
            builder = (
                TemplateLoader("word-focus")
                .with_input_video(intermediate_path)
                .load(False)
            )

            # Se quiser adicionar CSS customizado programaticamente:
            # builder.add_css("meu_estilo.css")

            pipeline = builder.build()

            # Tentativa de forçar saída em `final_output_path`
            try:
                if hasattr(pipeline, "_output_video_path"):
                    pipeline._output_video_path = final_output_path
                    pipeline.run()
                else:
                    before = set(os.listdir(output_dir))
                    pipeline.run()
                    after = set(os.listdir(output_dir))

                    new = sorted(
                        [p for p in after - before if p.lower().endswith(('.mp4', '.mkv', '.webm'))],
                        key=lambda n: os.path.getmtime(os.path.join(output_dir, n))
                    )

                    if new:
                        produced = os.path.join(output_dir, new[-1])
                        os.replace(produced, final_output_path)
                    else:
                        print("⚠️ Não consegui detectar o arquivo de saída do PyCaps automaticamente.")
                        raise RuntimeError("Saída do PyCaps não encontrada automaticamente.")

            except Exception as inner_exc:
                print(f"⚠️ Tentativa direta de set_output/run falhou: {inner_exc}. "
                      f"Tentando estratégia de detecção de arquivo...")

                before = set(os.listdir(output_dir))
                pipeline.run()
                after = set(os.listdir(output_dir))

                new = sorted(
                    [p for p in after - before if p.lower().endswith(('.mp4', '.mkv', '.webm'))],
                    key=lambda n: os.path.getmtime(os.path.join(output_dir, n))
                )

                if new:
                    produced = os.path.join(output_dir, new[-1])
                    os.replace(produced, final_output_path)
                else:
                    raise

            print(f"✅ Processo PyCaps concluído: {final_output_path}")

        except Exception as e:
            # Se algo falhar no PyCaps, mantemos o intermediário
            print(f"❌ Erro ao rodar PyCaps (legendas): {e}")
            print("⚠️ Como fallback, vou manter a versão sem legendas como saída final.")

            if os.path.exists(intermediate_path):
                if os.path.exists(final_output_path):
                    os.remove(final_output_path)
                os.rename(intermediate_path, final_output_path)

            continue

        finally:
            # Limpa intermediário
            if os.path.exists(intermediate_path):
                try:
                    os.remove(intermediate_path)
                except Exception:
                    pass

    print("Todos os vídeos processados.")
