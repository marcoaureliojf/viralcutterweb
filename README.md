# ViralCutterWeb

Versão: 0.1

## Descrição
ViralCutterWeb é uma aplicação web para corte automático de vídeos virais, inspirada no projeto [ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter). Utiliza inteligência artificial para sugerir cortes e o pacote [pycaps](https://github.com/francozanardi/pycaps) para geração automática de legendas estilizadas.

## Principais Funcionalidades
- Upload de vídeos ou download via URL
- Sugestão automática de cortes virais
- Geração de legendas automáticas com PyCaps
- Interface web para ajuste dos cortes e templates de legendas

## Como usar
1. Faça upload de um vídeo ou forneça uma URL
2. Ajuste os cortes sugeridos e escolha o template de legendas
3. Aguarde o processamento e baixe os vídeos finais

## Requisitos
- Docker
- Python 3.10+
- FFmpeg

## Como executar
```bash
git clone https://github.com/marcao/viralcutterweb.git
cd viralcutterweb
sudo docker compose up -d
```
Acesse a interface web em `http://localhost:8000`

## Observações
- **Atenção:** O tamanho médio da imagem Docker pode ser elevado devido à inclusão de dependências de IA e processamento de vídeo.
- Recomenda-se rodar em máquinas com pelo menos 4GB de RAM.

## Inspiração
- [ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter)
- [pycaps](https://github.com/francozanardi/pycaps)

---
Este projeto está em desenvolvimento inicial. Sugestões e contribuições são bem-vindas!
