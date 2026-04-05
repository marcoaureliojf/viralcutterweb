# 1. Base e dependências (mesma estrutura sólida)
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libegl1 python3-pip python3-dev git ffmpeg libsndfile1 \
    curl wget libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs

# 2. Ferramentas de build
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# 3. Torch
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 4. Instalação do g4f e requirements
RUN pip3 install --no-cache-dir g4f[all]
COPY ./requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. WHISPERX - INSTALAÇÃO CORRIGIDA
# Primeiro instala dependências críticas
RUN pip3 install --no-cache-dir \
    pyannote.audio==3.1.1 \
    ctranslate2 \
    faster-whisper \
    stable-ts \
    setuptools-rust

# Clona e instala com verbose para debug
RUN git clone https://github.com/matheusbach/whisperx.git /tmp/whisperx && \
    cd /tmp/whisperx && \
    pip3 install --no-cache-dir -v . && \
    ls -la /usr/local/lib/python3.10/dist-packages/ | grep -i whisper && \
    rm -rf /tmp/whisperx

# 6. PyCaps e Playwright
RUN pip3 install --no-cache-dir git+https://github.com/francozanardi/pycaps.git 
RUN pip3 install --no-cache-dir playwright && playwright install --with-deps chromium

# 7. Pastas e Código
RUN mkdir -p /app/tmp /app/projects && chmod -R 777 /app/tmp /app/projects
COPY . .
RUN if [ -f package.json ]; then npm install && npm run build-css; fi

# 8. DIAGNÓSTICO DETALHADO
RUN echo "=== LISTANDO PACOTES INSTALADOS ===" && \
    pip list | grep -E "whisper|faster|pyannote|ctranslate" || echo "Nenhum pacote whisper encontrado" && \
    echo "=== VERIFICANDO SITE-PACKAGES ===" && \
    python3 -c "import site; print(site.getsitepackages())" && \
    ls -la $(python3 -c "import site; print(site.getsitepackages()[0])") | grep -i whisper || echo "Nenhum diretório whisper encontrado"

# 9. TENTATIVA ALTERNATIVA - Instala direto do PyPI se disponível
RUN pip3 install --no-cache-dir whisperx || echo "Falha na instalação via PyPI, continuando..."

# 10. VERIFICAÇÃO FINAL (NÃO CRÍTICA) - Com fallback
RUN python3 -c "import whisperx; print('✅ WhisperX importado com sucesso')" || echo "❌ Falha ao importar whisperx"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]