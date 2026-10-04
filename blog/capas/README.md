# Capas da série

Uma por artigo, mais uma do índice, em tema claro e escuro. 1200×340.

Geradas por [`gerar.py`](gerar.py), não editadas à mão:

```bash
python3 blog/capas/gerar.py            # claro
python3 blog/capas/gerar.py --escuro   # escuro
```

O desenho reusa a identidade da aplicação que a turma constrói: a rampa do vermelho ao verde do IFC, a mesma do `card::before` do `index.html`, só que em blocos discretos de 24px em vez de gradiente contínuo. Tudo com `shape-rendering="crispEdges"`, sem anti-aliasing.

Para mudar título, rodapé ou tema, mexa no dicionário `CAPAS` e nos `TEMAS` no topo do gerador. O tamanho do título se ajusta sozinho para caber, com 8% de folga, porque o cálculo de largura é estimativa e a fonte real da máquina que rasterizar pode ser mais larga.

## Converter para PNG

Plataforma de blog costuma querer PNG ou JPG. Nenhuma ferramenta de conversão está no projeto, então use uma destas:

```bash
# librsvg
sudo apt install librsvg2-bin
for f in blog/capas/capa-*.svg; do rsvg-convert -w 1200 "$f" -o "${f%.svg}.png"; done

# ImageMagick
for f in blog/capas/capa-*.svg; do magick -density 150 "$f" "${f%.svg}.png"; done
```

Sem nenhuma delas instalada, abrir o SVG no navegador e salvar a imagem também resolve.
