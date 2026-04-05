import os
import shutil
from pycaps import *
        
def process_with_pycaps(intermediate_path: str, final_output_path: str, template: str):
    """
    Processa um vídeo intermediário com PyCaps para gerar/queimar legendas automaticamente.
    O arquivo TSV necessário DEVE estar ao lado do intermediate_path com o mesmo nome base.
    """
    
    # --- Configurações do template ---
    print(f"🔥 Executando PyCaps (template {template}) para gerar/queimar legendas...")

    builder = (
        TemplateLoader(template)
        .with_input_video(intermediate_path)
        .load(False) # Não exige TSV no momento da carga, será buscado no .run()
    )
    builder.with_output_video(final_output_path)

    pipeline = builder.build()
    try:
        pipeline.run()
        print(f"✅ Processo PyCaps concluído: {final_output_path}")
    except Exception as e:
        print(f"❌ Erro ao rodar PyCaps (legendas): {e}")
        print("⚠️ Como fallback, vou manter a versão sem legendas como saída final.")

    # Limpeza do arquivo intermediário
    if os.path.exists(intermediate_path):
        # Se o PyCaps falhou (o final_output_path não existe), renomeamos a versão sem legendas
        if not os.path.exists(final_output_path):
            shutil.move(intermediate_path, final_output_path)
            print(f"⚠️ PyCaps falhou. Versão intermediária renomeada para: {final_output_path}")
        else:
            os.remove(intermediate_path)