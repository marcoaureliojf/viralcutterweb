import os
from pycaps import *

def process_with_pycaps(intermediate_path: str, final_output_path: str, keywords_output_path: str):
    """
    Processa um vídeo intermediário com PyCaps para gerar/queimar legendas automaticamente.
    """
    # --- 1. Create a custom tagger ---
    tagger = SemanticTagger()
    tagger.add_wordlist_rule(Tag("important"), wordlist=keywords_output_path)

    # --- Configurações do template ---
    template = 'word-focus'
    print(f"🔥 Executando PyCaps (template {template}) para gerar/queimar legendas...")

    builder = (
        TemplateLoader(template)
        .with_input_video(intermediate_path)
        .load(False)
    )
    builder.with_output_video(final_output_path)
    builder.with_video_quality(VideoQuality.HIGH)
    builder.with_semantic_tagger(tagger)
    builder.with_whisper_config(model_size='small')
    builder.add_animation(
        animation=PopInBounce(duration=0.5),
        when=EventType.ON_NARRATION_STARTS,
        what=ElementType.WORD,
        tag_condition=TagConditionFactory.parse("important")
    )

    pipeline = builder.build()
    try:
        pipeline.run()
        print(f"✅ Processo PyCaps concluído: {final_output_path}")
    except Exception as e:
        print(f"❌ Erro ao rodar PyCaps (legendas): {e}")
        print("⚠️ Como fallback, vou manter a versão sem legendas como saída final.")

        if os.path.exists(intermediate_path):
            if os.path.exists(final_output_path):
                os.remove(final_output_path)
            os.rename(intermediate_path, final_output_path)