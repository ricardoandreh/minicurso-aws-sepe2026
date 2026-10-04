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

L, A = 1200, 340
MARGEM = 80
LIMITE = L - 2 * MARGEM
BASE = 130
RODAPE_Y = 265

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


def tamanho_titulo(texto, medir=None, maximo=46, minimo=28):
    """Encolhe até caber em 92% da largura útil, contando o cursor."""
    alvo = LIMITE * 0.92
    t = maximo
    while t > minimo:
        larg = medir(texto, t) if medir else len(texto) * AVANCO * t
        if larg + t * 0.55 * 2 <= alvo:
            break
        t -= 1
    return t


def blocos_rampa():
    n, w = L // 24, 24
    return [(i * w, 0, w, 14, RAMPA[min(int(i / n * len(RAMPA)), len(RAMPA) - 1)])
            for i in range(n)]


def linhas_grade():
    v = [(x, 14, 1, A - 14) for x in range(0, L, 40)]
    h = [(0, y, L, 1) for y in range(14, A, 40)]
    return v + h


# ── SVG ────────────────────────────────────────────────────────────────────

def svg(titulo, rodape):
    t = TEMA
    ts = tamanho_titulo(titulo)
    cursor_x = MARGEM + (len(titulo) + 0.6) * AVANCO * ts
    grade = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{t["grade"]}"/>'
                    for x, y, w, h in linhas_grade())
    faixa = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/>'
                    for x, y, w, h, c in blocos_rampa())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}"
     viewBox="0 0 {L} {A}" shape-rendering="crispEdges">
  <rect width="{L}" height="{A}" fill="{t['fundo']}"/>
  {grade}
  {faixa}
  <text x="{MARGEM}" y="{BASE + ts}" font-family="{MONO}" font-size="{ts}"
        font-weight="700" fill="{t['titulo']}">{esc(titulo)}</text>
  <rect x="{cursor_x:.0f}" y="{BASE + 6}" width="{ts*0.55:.0f}" height="{ts}"
        fill="{t['marca']}"/>
  <text x="{MARGEM}" y="{RODAPE_Y}" font-family="{MONO}" font-size="19"
        fill="{t['fraco']}">{esc(rodape)}</text>
  <text x="{L-MARGEM}" y="{RODAPE_Y}" font-family="{MONO}" font-size="19"
        fill="{t['fraco']}" text-anchor="end">{esc(RODAPE_DIR)}</text>
</svg>
'''


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
    t = TEMA

    def medir(texto, tamanho):
        return ImageFont.truetype(negrito, tamanho).getlength(texto)

    ts = tamanho_titulo(titulo, medir=medir)
    f_tit = ImageFont.truetype(negrito, ts)
    f_rod = ImageFont.truetype(regular, 19)

    img = Image.new("RGB", (L, A), t["fundo"])
    d = ImageDraw.Draw(img)
    for x, y, w, h in linhas_grade():
        d.rectangle([x, y, x + w - 1, y + h - 1], fill=t["grade"])
    for x, y, w, h, c in blocos_rampa():
        d.rectangle([x, y, x + w - 1, y + h - 1], fill=c)

    d.text((MARGEM, BASE), titulo, font=f_tit, fill=t["titulo"])
    cx = MARGEM + f_tit.getlength(titulo + " ")
    d.rectangle([cx, BASE + 6, cx + ts * 0.55, BASE + 6 + ts], fill=t["marca"])

    d.text((MARGEM, RODAPE_Y - 19), rodape, font=f_rod, fill=t["fraco"])
    larg_dir = f_rod.getlength(RODAPE_DIR)
    d.text((L - MARGEM - larg_dir, RODAPE_Y - 19), RODAPE_DIR, font=f_rod, fill=t["fraco"])

    img.save(caminho, "WEBP", lossless=True, method=6)
    return ts


destino = os.path.dirname(os.path.abspath(__file__))
try:
    import PIL  # noqa: F401
    tem_pillow = True
except ImportError:
    tem_pillow = False

for slug, tit, rod in CAPAS:
    io.open(os.path.join(destino, f"capa-{slug}.svg"), "w", encoding="utf-8").write(svg(tit, rod))
    linha = "  capa-%-7s svg %2dpx" % (slug, tamanho_titulo(tit))
    if tem_pillow:
        alvo = os.path.join(destino, f"capa-{slug}.webp")
        ts = webp(tit, rod, alvo)
        linha += "   webp %2dpx, %5.1f KB" % (ts, os.path.getsize(alvo) / 1024)
    print(linha)

if not tem_pillow:
    print("\n  (sem Pillow: só os SVG. Rode com o python do venv para gerar os WebP)")
