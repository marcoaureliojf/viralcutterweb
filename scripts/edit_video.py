import cv2
import subprocess
import os
from pycaps import *

def get_video_fps(video_path: str) -> str | None:
    """
    Usa ffprobe para detectar o framerate de um vídeo e o retorna como uma fração (string).
    Retorna None se a detecção falhar.
    """
    command = [
        'ffprobe',
        '-v', 'error',          # Não exibe o banner, apenas erros
        '-select_streams', 'v:0', # Seleciona apenas o primeiro stream de vídeo
        '-show_entries', 'stream=r_frame_rate', # Pede para mostrar apenas a entrada do framerate
        '-of', 'default=noprint_wrappers=1:nokey=1' # Formato de saída: apenas o valor, sem a chave "r_frame_rate="
    ]
    
    # Adiciona o caminho do vídeo ao final do comando
    command.append(video_path)

    try:
        # Executa o comando e captura a saída
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        # A saída é a fração do FPS, ex: "30/1" ou "30000/1001".
        # .strip() remove quebras de linha ou espaços em branco.
        fps_fraction = result.stdout.strip()
        
        if not fps_fraction:
            print(f"⚠️ FFprobe não retornou um FPS para o vídeo: {video_path}")
            return None
            
        return fps_fraction
        
    except FileNotFoundError:
        print("❌ Erro: 'ffprobe' não foi encontrado. Certifique-se de que o FFmpeg está instalado e no PATH do sistema.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar ffprobe no arquivo {video_path}: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ Ocorreu um erro inesperado ao obter o FPS: {e}")
        return None


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
        
        # --- DETECÇÃO AUTOMÁTICA DO FRAMERATE ---
        print(f"🔎 Detectando FPS para: {video_path}...")
        framerate = get_video_fps(video_path)
        
        # Se a detecção falhar, pula para o próximo vídeo
        if not framerate: 
            print(f"❌ Não foi possível determinar o FPS. Pulando o vídeo: {video_path}")
            continue
        print(f"✅ FPS detectado: {framerate}")

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
            '-map', '[out_v]',
            '-map', '[out_a]',
            '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
            '-g', '30', '-keyint_min', '30',
            # --- ALTERAÇÕES AQUI ---
            '-r', framerate, 
            '-vsync', 'cfr',     
            # -------------------------
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
        
        
        # --- 1. Create a custom tagger ---
        tagger = SemanticTagger()
        tagger.add_regex_rule(Tag("shoutout"), r"(?i)shoutout to \w+") # Case insensitive regex for "shoutout to <word>" 
        tagger.add_wordlist_rule(Tag("important"), ["key", "critical", "important"])
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
            builder.with_video_quality(VideoQuality.HIGH)
            builder.with_semantic_tagger(tagger)
            builder.with_whisper_config(model_size='medium')
            builder.add_animation(
                animation=ZoomOut(duration=0.2),
                when=EventType.ON_NARRATION_STARTS,
                what=ElementType.WORD,
                tag_condition=TagConditionFactory.parse("important")
            )
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
