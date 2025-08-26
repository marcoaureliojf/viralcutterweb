import g4f

def translate(text: str, target_language: str) -> str:
    """
    Traduz um texto para o idioma de destino usando a API g4f.
    """
    if not text.strip():
        return ""
        
    print(f"Traduzindo texto para o idioma: {target_language}...")
    try:
        prompt = f"Translate the following text to {target_language}. Return ONLY the translated text, with no additional explanations, context, or quotation marks:\n\n{text}"
        
        response = g4f.ChatCompletion.create(
            model=g4f.models.gpt_4,
            messages=[{"role": "user", "content": prompt}],
        )
        
        translated_text = response.strip().strip('"')
        print(f"Tradução concluída: '{translated_text[:50]}...'")
        return translated_text
    except Exception as e:
        print(f"ERRO durante a tradução: {e}. Retornando texto original.")
        return text