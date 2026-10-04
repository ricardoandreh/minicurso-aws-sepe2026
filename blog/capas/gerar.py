# -*- coding: utf-8 -*-
"""Capas da série, 1200x340, blocado, paleta do IFC.

shape-rendering=crispEdges em tudo: sem anti-aliasing, bordas duras de
propósito. A faixa do topo é a mesma rampa do card do encurtador, em blocos
discretos no lugar do gradiente contínuo.

    python3 blog/capas/gerar.py [--escuro]
"""
import io, os, sys

L, A = 1200, 340
MARGEM = 80
LIMITE = L - 2 * MARGEM

RAMPA = ["#ca2027", "#ca2027", "#ca2027", "#349a46", "#3cb04f", "#3cb04f",
         "#62ca71", "#8eda96", "#c2ecc4", "#e9f9e9"]

MONO = "Cascadia Mono,JetBrains Mono,Consolas,ui-monospace,monospace"

TEMAS = {
    "claro":  dict(fundo="#ffffff", titulo="#242424", fraco="#616161",
                   marca="#277233", grade="#f2f2f2"),
    "escuro": dict(fundo="#141414", titulo="#ffffff", fraco="#adadad",
                   marca="#63c072", grade="#1f1f1f"),
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def corpo_mono(n, tamanho):
    """Largura aproximada de n caracteres monoespaçados: 0.6em é o avanço
    típico dessa família."""
    return n * tamanho * 0.6


def tamanho_titulo(texto, maximo=46, minimo=28):
    """Encolhe o título até caber na largura útil, descontando o cursor.

    O alvo é 92% da largura, não 100%: o avanço de 0.6em é estimativa, e a
    fonte real na máquina que converter pode ser um pouco mais larga. Sem essa
    folga, um título no limite estoura a margem na hora de rasterizar."""
    alvo = LIMITE * 0.92
    t = maximo
    while t > minimo and corpo_mono(len(texto) + 2, t) > alvo:
        t -= 1
    return t


def faixa():
    n, w = L // 24, 24
    return "".join(
        f'<rect x="{i*w}" y="0" width="{w}" height="14" '
        f'fill="{RAMPA[min(int(i / n * len(RAMPA)), len(RAMPA)-1)]}"/>'
        for i in range(n))


def grade(cor):
    v = "".join(f'<rect x="{x}" y="14" width="1" height="{A-14}" fill="{cor}"/>'
                for x in range(0, L, 40))
    h = "".join(f'<rect x="0" y="{y}" width="{L}" height="1" fill="{cor}"/>'
                for y in range(14, A, 40))
    return v + h


BASE = 130


def capa(titulo, rodape, tema="claro"):
    t = TEMAS[tema]
    ts = tamanho_titulo(titulo)
    cursor_x = MARGEM + corpo_mono(len(titulo) + 0.6, ts)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}"
     viewBox="0 0 {L} {A}" shape-rendering="crispEdges">
  <rect width="{L}" height="{A}" fill="{t['fundo']}"/>
  {grade(t['grade'])}
  {faixa()}
  <text x="{MARGEM}" y="{BASE + ts}" font-family="{MONO}" font-size="{ts}"
        font-weight="700" fill="{t['titulo']}">{esc(titulo)}</text>
  <rect x="{cursor_x:.0f}" y="{BASE + 6}" width="{ts*0.55:.0f}" height="{ts}"
        fill="{t['marca']}"/>
  <text x="{MARGEM}" y="265" font-family="{MONO}" font-size="19"
        fill="{t['fraco']}">{esc(rodape)}</text>
  <text x="{L-MARGEM}" y="265" font-family="{MONO}" font-size="19"
        fill="{t['fraco']}" text-anchor="end">minicurso_ifc · 2026</text>
</svg>
'''


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

tema = "escuro" if "--escuro" in sys.argv else "claro"
destino = os.path.dirname(os.path.abspath(__file__))
for slug, tit, rod in CAPAS:
    sufixo = "" if tema == "claro" else "-escuro"
    caminho = os.path.join(destino, f"capa-{slug}{sufixo}.svg")
    io.open(caminho, "w", encoding="utf-8").write(capa(tit, rod, tema))
    ts = tamanho_titulo(tit)
    larg = corpo_mono(len(tit) + 2, ts)
    alerta = "  <-- apertado" if larg > LIMITE * 0.97 else ""
    print("  %-26s %2dpx, %4.0f/%d px%s" %
          (os.path.basename(caminho), ts, larg, LIMITE, alerta))
