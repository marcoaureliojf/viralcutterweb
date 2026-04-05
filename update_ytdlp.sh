#!/bin/bash
# Script para atualizar yt-dlp no container Docker

echo "🔄 Atualizando yt-dlp no container..."

# Atualizar yt-dlp para a versão mais recente
sudo docker exec viralcutter_container pip install --upgrade yt-dlp

echo "✅ yt-dlp atualizado!"
echo ""
echo "📋 Versão instalada:"
sudo docker exec viralcutter_container yt-dlp --version
