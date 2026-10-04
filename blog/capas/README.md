# Capas da série

Uma por artigo, mais uma do índice. 1200×340, tema claro.

- **`.webp`** é o que se publica. Lossless, 3,4 a 5 KB cada.
- **`.svg`** é a fonte da verdade, versiona bem e serve para editar.

## Gerar

```bash
python3 blog/capas/gerar.py          # só os SVG
<venv>/bin/python blog/capas/gerar.py   # SVG e WebP, se houver Pillow
```

O WebP sai `lossless=True`: são cores chapadas e bordas duras, e o modo com perda só introduziria sujeira nas bordas sem economizar nada que valha.

Não são desenhadas à mão. Para mudar título, rodapé ou estilo, mexa no dicionário `CAPAS` e em `TEMA` no topo do gerador, e as quinze saem de novo.

## Desenho

A rampa do vermelho ao verde do IFC, a mesma do `card::before` do `index.html`, em blocos discretos de 24px no lugar do gradiente contínuo. Grade de 40px bem fraca no fundo, tipografia monoespaçada em caixa baixa, cursor em bloco verde fechando o título.

## A fonte

O gerador procura, nesta ordem: Cascadia Mono, Consolas e DejaVu Sans Mono. Num WSL as fontes do Windows estão em `/mnt/c/Windows/Fonts`, que é de onde o Consolas sai. Numa máquina sem nenhuma delas, o gerador avisa em vez de produzir uma capa com fonte errada.

O tamanho do título se ajusta sozinho para caber em 92% da largura útil, medido com a métrica real da fonte, não estimado.
