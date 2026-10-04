# -*- coding: utf-8 -*-
"""Capas da série: SVG (fonte da verdade) e WebP (o que se publica).

1200x340, blocado, paleta do IFC. A faixa do topo é a mesma rampa do
`card::before` do index.html, em blocos discretos no lugar do gradiente.

    python3 blog/capas/gerar.py              # só SVG
    <venv>/bin/python blog/capas/gerar.py    # SVG + WebP, se houver Pillow

O WebP sai lossless: são cores chapadas, e lossy introduziria sujeira nas
bordas duras sem economizar nada que valha.
"""
import io, os, sys

# 16:9. Medido no preview do AWS Builder: ele corta para preencher o slot, e
# qualquer coisa mais larga que isso perde as laterais.
L, A = 1200, 675
MARGEM = 90
LIMITE = L - 2 * MARGEM
FAIXA_H = 20
GRADE = 45
RODAPE_Y = 600
MAX_LINHAS = 2

RAMPA = ["#ca2027", "#ca2027", "#ca2027", "#349a46", "#3cb04f", "#3cb04f",
         "#62ca71", "#8eda96", "#c2ecc4", "#e9f9e9"]

MONO = "Cascadia Mono,JetBrains Mono,Consolas,ui-monospace,monospace"

# Candidatas em ordem de preferência, espelhando a pilha do MONO acima.
FONTES = [
    ("/mnt/c/Windows/Fonts/CascadiaMono.ttf", "/mnt/c/Windows/Fonts/CascadiaMono.ttf"),
    ("/mnt/c/Windows/Fonts/consola.ttf", "/mnt/c/Windows/Fonts/consolab.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
]

TEMA = dict(fundo="#ffffff", titulo="#242424", fraco="#616161",
            marca="#277233", grade="#f2f2f2")

CAPAS = [
 ("indice", "encurtador de url na aws",            "14 artigos, do console ao codigo"),
 ("00",     "preparando a maquina",                "preparacao · cli, node, credenciais"),
 ("01",     "o site sem servidor",                 "parte 1 · s3"),
 ("02",     "onde o dado mora",                    "parte 1 · dynamodb"),
 ("03",     "o codigo que roda sem servidor",      "parte 1 · lambda, iam, cloudwatch"),
 ("04",     "a porta de entrada",                  "parte 1 · api gateway"),
 ("05",     "tirando trabalho do caminho critico", "parte 1 · sqs"),
 ("06",     "reagindo a mudancas no banco",        "parte 1 · streams, pipes"),
 ("07",     "avisando o mundo",                    "parte 1 · sns, parameter store"),
 ("08",     "a mesma coisa, agora em codigo",      "parte 2 · sst v4"),
 ("09",     "uma linha em vez de tres passos",     "parte 2 · sst v4, link()"),
 ("10",     "a api, agora em tres linhas",         "parte 2 · sst v4, api gateway"),
 ("11",     "a fila, e o que o subscribe esconde", "parte 2 · sst v4, sqs"),
 ("12",     "reagindo ao dado, nao ao codigo",     "parte 2 · sst v4, streams, pipes, sns"),
 ("13",     "o que mudou, e o que isso custou",    "fechamento"),
]

RODAPE_DIR = "minicurso_ifc · 2026"
AVANCO = 0.55          # largura de um caractere, em em. Medido: Consolas = 0,543


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def quebrar(texto, tamanho, medir):
    """Quebra em palavras, guloso, respeitando a largura útil."""
    alvo = LIMITE * 0.94
    linhas, atual = [], ""
    for palavra in texto.split():
        tentativa = (atual + " " + palavra).strip()
        if atual and medir(tentativa, tamanho) > alvo:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
    if atual:
        linhas.append(atual)
    return linhas


def ajustar(texto, medir=None, maximo=76, minimo=38):
    """Maior tamanho em que o título cabe em MAX_LINHAS linhas.

    O cursor entra na conta da última linha: ele ocupa pouco mais de meio
    caractere e é o que estourava a margem na versão anterior."""
    medir = medir or (lambda s, t: len(s) * AVANCO * t)
    alvo = LIMITE * 0.94
    tam = maximo
    while tam > minimo:
        linhas = quebrar(texto, tam, medir)
        if len(linhas) <= MAX_LINHAS and \
           medir(linhas[-1], tam) + tam * 0.75 <= alvo:
            return tam, linhas
        tam -= 2
    return tam, quebrar(texto, tam, medir)


def blocos_rampa():
    n, w = L // 25, 25
    return [(i * w, 0, w, FAIXA_H, RAMPA[min(int(i / n * len(RAMPA)), len(RAMPA) - 1)])
            for i in range(n)]


def linhas_grade():
    v = [(x, FAIXA_H, 1, A - FAIXA_H) for x in range(0, L, GRADE)]
    h = [(0, y, L, 1) for y in range(FAIXA_H, A, GRADE)]
    return v + h


def topo_titulo(n_linhas, tam):
    """Centraliza o bloco do título entre a faixa e o rodapé."""
    altura = n_linhas * tam * 1.22
    return FAIXA_H + (RODAPE_Y - 40 - FAIXA_H - altura) / 2


# ── SVG ────────────────────────────────────────────────────────────────────

def svg(titulo, rodape):
    c = TEMA
    tam, linhas = ajustar(titulo)
    topo = topo_titulo(len(linhas), tam)
    passo = tam * 1.22
    grade = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c["grade"]}"/>'
                    for x, y, w, h in linhas_grade())
    faixa = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{cor}"/>'
                    for x, y, w, h, cor in blocos_rampa())
    textos = "".join(
        f'\n  <text x="{MARGEM}" y="{topo + tam + i*passo:.0f}" font-family="{MONO}" '
        f'font-size="{tam}" font-weight="700" fill="{c["titulo"]}">{esc(l)}</text>'
        for i, l in enumerate(linhas))
    cx = MARGEM + len(linhas[-1] + " ") * AVANCO * tam
    cy = topo + (len(linhas) - 1) * passo + tam * 0.22
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}"
     viewBox="0 0 {L} {A}" shape-rendering="crispEdges">
  <rect width="{L}" height="{A}" fill="{c['fundo']}"/>
  {grade}
  {faixa}{textos}
  <rect x="{cx:.0f}" y="{cy:.0f}" width="{tam*0.55:.0f}" height="{tam}"
        fill="{c['marca']}"/>
  <text x="{MARGEM}" y="{RODAPE_Y}" font-family="{MONO}" font-size="22"
        fill="{c['fraco']}">{esc(rodape)}</text>
  <text x="{L-MARGEM}" y="{RODAPE_Y}" font-family="{MONO}" font-size="22"
        fill="{c['fraco']}" text-anchor="end">{esc(RODAPE_DIR)}</text>
</svg>
"""


# ── WebP ───────────────────────────────────────────────────────────────────

def _fontes():
    from PIL import ImageFont
    for regular, negrito in FONTES:
        if os.path.exists(regular) and os.path.exists(negrito):
            return regular, negrito
    raise SystemExit("nenhuma fonte monoespacada encontrada: %s" %
                     ", ".join(r for r, _ in FONTES))


def webp(titulo, rodape, caminho):
    from PIL import Image, ImageDraw, ImageFont
    regular, negrito = _fontes()
    c = TEMA

    def medir(texto, tamanho):
        return ImageFont.truetype(negrito, tamanho).getlength(texto)

    tam, linhas = ajustar(titulo, medir=medir)
    f_tit = ImageFont.truetype(negrito, tam)
    f_rod = ImageFont.truetype(regular, 22)
    topo = topo_titulo(len(linhas), tam)
    passo = tam * 1.22

    img = Image.new("RGB", (L, A), c["fundo"])
    d = ImageDraw.Draw(img)
    for x, y, w, h in linhas_grade():
        d.rectangle([x, y, x + w - 1, y + h - 1], fill=c["grade"])
    for x, y, w, h, cor in blocos_rampa():
        d.rectangle([x, y, x + w - 1, y + h - 1], fill=cor)

    for i, l in enumerate(linhas):
        d.text((MARGEM, topo + i * passo), l, font=f_tit, fill=c["titulo"])

    cx = MARGEM + f_tit.getlength(linhas[-1] + " ")
    cy = topo + (len(linhas) - 1) * passo + tam * 0.22
    d.rectangle([cx, cy, cx + tam * 0.55, cy + tam], fill=c["marca"])

    d.text((MARGEM, RODAPE_Y - 22), rodape, font=f_rod, fill=c["fraco"])
    larg = f_rod.getlength(RODAPE_DIR)
    d.text((L - MARGEM - larg, RODAPE_Y - 22), RODAPE_DIR, font=f_rod, fill=c["fraco"])

    img.save(caminho, "WEBP", lossless=True, method=6)
    return tam, len(linhas)


destino = os.path.dirname(os.path.abspath(__file__))
try:
    import PIL  # noqa: F401
    tem_pillow = True
except ImportError:
    tem_pillow = False

for slug, tit, rod in CAPAS:
    io.open(os.path.join(destino, f"capa-{slug}.svg"), "w", encoding="utf-8").write(svg(tit, rod))
    linha = "  capa-%-7s" % slug
    if tem_pillow:
        alvo = os.path.join(destino, f"capa-{slug}.webp")
        tam, n = webp(tit, rod, alvo)
        linha += " %2dpx, %d linha%s, %5.1f KB" % (
            tam, n, "s" if n > 1 else " ", os.path.getsize(alvo) / 1024)
    else:
        tam, linhas = ajustar(tit)
        linha += " %2dpx, %d linha(s)  (sem Pillow, so SVG)" % (tam, len(linhas))
    print(linha)

if not tem_pillow:
    print("\n  (sem Pillow: só os SVG. Rode com o python do venv para gerar os WebP)")
