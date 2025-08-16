import json
import os

def save_viral_segments(viral_segments):
    """
    Saves the generated viral segments data to a text file in the 'tmp' directory.
    This function is a bit redundant if create_viral_segments already saves it,
    but we keep it for modularity as in the original script.
    """
    output_path = os.path.join('tmp', 'viral_segments.txt')
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(viral_segments, f, ensure_ascii=False, indent=4)
        print(f"JSON com segmentos virais salvo em {output_path}")
    except Exception as e:
        print(f"ERRO ao salvar o JSON dos segmentos virais: {e}")
        raise