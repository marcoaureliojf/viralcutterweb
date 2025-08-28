import os
from glob import glob
from pycaps.template import TemplateService
from pycaps.render import Renderer

def burn():
    """
    Queima as legendas .ass nos vídeos processados usando PyCaps.
    """
    print("Iniciando a queima de legendas nos vídeos com PyCaps...")
    video_dir = 'final'
    subtitle_dir = 'subs_ass'
    output_dir = 'burned_sub'
    os.makedirs(output_dir, exist_ok=True)

    video_files = glob(os.path.join(video_dir, '*_processed.mp4'))
    if not video_files:
        print("⚠️ Nenhum vídeo processado encontrado para queimar legendas.")
        return

    # Criar serviço de templates e instanciar renderer
    template_service = TemplateService()
    template_name = "my_custom_template"

    # Se não existir, cria um template baseado no "default"
    if not os.path.exists(template_name):
        template_service.create(template_name, from_template="default")

    renderer = Renderer()

    for video_path in video_files:
        base_name = os.path.basename(video_path).replace('_processed.mp4', '')
        subtitle_path = os.path.join(subtitle_dir, f"{base_name}_processed.ass")
        output_path = os.path.join(output_dir, f"{base_name}_processed_subtitled.mp4")

        if not os.path.exists(subtitle_path):
            print(f"⚠️ Legenda não encontrada em {subtitle_path} para o vídeo {video_path}. Pulando.")
            continue

        print(f"🎬 Renderizando {base_name}...")
        try:
            renderer.render(
                input_path=video_path,
                subtitle_path=subtitle_path,  # PyCaps aceita .ass
                template=template_name,
                output_path=output_path
            )
            print(f"✅ Legenda queimada com sucesso: {output_path}")
        except Exception as e:
            print(f"❌ Erro ao queimar a legenda no vídeo {base_name}: {e}")
