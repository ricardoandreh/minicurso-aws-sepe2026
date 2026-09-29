#!/usr/bin/env bash
# Gera layers/strands-openai/build/python/ — rodar UMA VEZ antes da aula,
# nunca ao vivo (ver "Princípios de execução" no roteiro.md). O sst.config.ts
# usa $asset() pra zipar esse diretório na hora do deploy — não precisamos
# gerar o zip aqui.
set -euo pipefail

cd "$(dirname "$0")"
rm -rf build
mkdir -p build/python

if command -v docker >/dev/null 2>&1; then
  # preferido: compila as dependências no mesmo runtime do Lambda
  docker run --rm \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -v "$PWD":/var/task \
    -w /var/task \
    public.ecr.aws/sam/build-python3.13:latest \
    pip install -r requirements.txt -t build/python --no-cache-dir
else
  echo "docker não encontrado, usando pip com --platform (fallback)" >&2
  pip install \
    -r requirements.txt \
    -t build/python \
    --platform manylinux2014_x86_64 \
    --python-version 3.13 \
    --implementation cp \
    --only-binary=:all: \
    --no-cache-dir
fi

find build/python -type d -name "__pycache__" -exec rm -rf {} +

echo "Layer criada em layers/strands-openai/build/python"
