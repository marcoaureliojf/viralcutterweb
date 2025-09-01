import os
from pycaps import *

def process_with_pycaps(intermediate_path: str, final_output_path: str, trasncription_output_path: str, template: str):
    """
    Processa um vídeo intermediário com PyCaps para gerar/queimar legendas automaticamente.
    """
    
    # --- Configurações do template ---
    print(f"🔥 Executando PyCaps (template {template}) para gerar/queimar legendas...")

    builder = (
        TemplateLoader(template)
        .with_input_video(intermediate_path)
        .load(False)
    )
    builder.with_output_video(final_output_path)

    pipeline = builder.build()
    try:
        pipeline.run()
        print(f"✅ Processo PyCaps concluído: {final_output_path}")
    except Exception as e:
        print(f"❌ Erro ao rodar PyCaps (legendas): {e}")
        print("⚠️ Como fallback, vou manter a versão sem legendas como saída final.")

    if os.path.exists(intermediate_path):
        if os.path.exists(final_output_path):
            os.remove(intermediate_path)