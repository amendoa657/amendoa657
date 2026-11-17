#!/usr/bin/env python3
"""Gera os SVGs do README do perfil, na estética da Mosaic.

Cada peça sai em duas versões: escura (tema Mosaic) e clara (tema Papel).
O README escolhe uma pelo tema do GitHub de quem está vendo.

    python3 assets/gerar.py

Precisa de Pillow e fontTools (com brotli) e das fontes Space Grotesk e
JetBrains Mono em assets/fontes/.
"""

import base64
import io
import math
import random
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
FONTES = AQUI / "fontes"
SAIDA = AQUI

TEMAS = {
    "escuro": {
        "fundo": "#0f0d15", "cartao": "#1b1820", "elevada": "#36333c", "linha": "#2b2832",
        "texto": "#e6e0ec", "texto2": "#bdb6c4", "texto3": "#8f8996",
        "a": "#86d7ac", "b": "#e9b9d3", "c": "#b5c5f9", "d": "#cfbfe6",
        "sobre_a": "#003823", "sobre_b": "#3a2130", "sobre_c": "#1b2a55", "sobre_d": "#2c2240",
        "sombra": "#06050a", "olho": "#0f0d15",
    },
    "claro": {
        "fundo": "#efebe2", "cartao": "#faf8f3", "elevada": "#e2ddd1", "linha": "#cfc9bd",
        "texto": "#161513", "texto2": "#3d3a35", "texto3": "#6b665e",
        "a": "#e5432d", "b": "#2a5bd7", "c": "#e0a800", "d": "#161513",
        "sobre_a": "#fff7f0", "sobre_b": "#ffffff", "sobre_c": "#2b2000", "sobre_d": "#efebe2",
        "sombra": "#161513", "olho": "#efebe2",
    },
}
TONS = ["a", "b", "c", "d"]

ONDAS = [
    (0.0062, 0.0048, 0.05, 0.032, 1.7, 0.0),
    (0.0051, 0.0069, -0.041, 0.046, 1.4, 2.1),
    (0.0072, 0.0055, 0.036, -0.052, 1.9, 4.4),
]


def onda_em(x, y, t=37.0):
    """A mesma conta do campo de pixels da Mosaic UI: qual onda vence no ponto."""
    melhor, forca = 0, -9
    for k, (fx, fy, vx, vy, torcao, fase) in enumerate(ONDAS):
        u = x * fx + t * vx + math.sin(y * fy * 0.7 + t * 0.07 + fase) * torcao
        v = y * fy + t * vy + math.cos(x * fx * 0.6 - t * 0.05 + fase) * torcao
        valor = math.sin(u) * math.cos(v)
        if valor > forca:
            melhor, forca = k, valor
    return melhor, forca


# ---------------------------------------------------------------------------
# Fontes: um subconjunto pequeno, embutido em base64 em cada SVG
# ---------------------------------------------------------------------------
CARACTERES = "".join(chr(c) for c in range(32, 127)) + "áàâãéêíóôõúçÁÉÍÓÚÇ✦—–→↗·…“”’×"


def fonte_embutida(arquivo, familia):
    fonte = TTFont(FONTES / arquivo)
    opcoes = subset.Options()
    opcoes.flavor = "woff2"
    opcoes.layout_features = ["*"]
    sub = subset.Subsetter(opcoes)
    sub.populate(text=CARACTERES)
    sub.subset(fonte)
    buf = io.BytesIO()
    fonte.flavor = "woff2"
    fonte.save(buf)
    dados = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:'{familia}';font-weight:300 700;src:url(data:font/woff2;base64,{dados}) format('woff2');}}"


FONTE_CSS = None


def estilos_base():
    global FONTE_CSS
    if FONTE_CSS is None:
        FONTE_CSS = fonte_embutida("space-grotesk.woff2", "SG") + fonte_embutida("jetbrains-mono.woff2", "JB")
    return FONTE_CSS + (
        ".sg{font-family:'SG',system-ui,sans-serif}.jb{font-family:'JB',ui-monospace,monospace}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    )


def svg(largura, altura, corpo, css, titulo):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}" '
        f'role="img" aria-label="{titulo}"><title>{titulo}</title><style>{estilos_base()}{css}</style>{corpo}</svg>'
    )


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def largura_mono(texto, tam):
    return len(texto) * tam * 0.6


_medidor = {}


def largura_sg(texto, tam, peso=500):
    chave = (tam, peso)
    if chave not in _medidor:
        f = ImageFont.truetype(str(FONTES / "space-grotesk.woff2"), tam)
        try:
            f.set_variation_by_axes([peso])
        except Exception:
            pass
        _medidor[chave] = f
    return _medidor[chave].getlength(texto)


# ---------------------------------------------------------------------------
# Pixels de um texto (para montar o nome)
# ---------------------------------------------------------------------------
def pixels_do_texto(texto, tam, peso, passo):
    f = ImageFont.truetype(str(FONTES / "space-grotesk.woff2"), tam)
    try:
        f.set_variation_by_axes([peso])
    except Exception:
        pass
    x0, y0, x1, y1 = f.getbbox(texto)
    im = Image.new("L", (x1 + 10, y1 + 10), 0)
    ImageDraw.Draw(im).text((0, 0), texto, font=f, fill=255)
    celulas = []
    for y in range(y0, y1, passo):
        for x in range(0, x1, passo):
            if im.getpixel((min(x + passo // 2, im.width - 1), min(y + passo // 2, im.height - 1))) > 120:
                celulas.append((x, y - y0))
    return celulas, x1, y1 - y0


def campo_de_pontos(L, A, passo, t, opacidade, mascara=None):
    """Retícula estática do campo, com uma animação leve por cor."""
    grupos = {0: [], 1: [], 2: [], 3: []}
    for j in range(A // passo + 1):
        for i in range(L // passo + 1):
            x = i * passo + passo / 2
            y = j * passo + passo / 2
            if mascara and mascara(x, y):
                continue
            k, forca = onda_em(x, y, t)
            nivel = max(0.0, (forca - 0.35) / 0.65)
            if nivel <= 0.02:
                lado, k = 1.4, 3
            else:
                lado = min(1.6 + nivel * 4.6 * (passo / 15), passo - 5)
            grupos[k].append(f'<rect x="{x - lado / 2:.1f}" y="{y - lado / 2:.1f}" width="{lado:.1f}" height="{lado:.1f}"/>')
    saida = []
    for k, rects in grupos.items():
        cls = f"p{k}"
        saida.append(f'<g class="{cls}">{"".join(rects)}</g>')
    return "".join(saida)


# ---------------------------------------------------------------------------
# 1. Herói
# ---------------------------------------------------------------------------
def heroi(nome_tema):
    T = TEMAS[nome_tema]
    L, A = 1280, 470
    random.seed(7)

    passo_campo = 20
    campo = campo_de_pontos(L, A, passo_campo, 37.0, 0.4, mascara=lambda x, y: x < 760 and 60 < y < 330 and False)

    # O nome, em pixels: "Italo" pesado, "Cunha" fino e na cor de destaque
    passo = 6
    ital, w1, h1 = pixels_do_texto("Italo", 150, 700, passo)
    cunh, w2, h2 = pixels_do_texto("Cunha", 150, 300, passo)
    ox1, oy1 = 64, 70
    ox2, oy2 = 64 + 120, 70 + h1 + 14

    def colunas(celulas, ox, oy, cor_final, base_atraso):
        porx = {}
        for (x, y) in celulas:
            porx.setdefault(x, []).append(y)
        grupos = []
        for x in sorted(porx):
            k, _ = onda_em(x + ox, oy, 37.0)
            tom = T[TONS[k]]
            dx = random.uniform(-160, 160)
            dy = random.uniform(-120, 160)
            atraso = base_atraso + (x / 600) * 0.9 + random.uniform(0, 0.25)
            lado = passo - 1
            rects = "".join(f'<rect x="{ox + x}" y="{oy + y}" width="{lado}" height="{lado}"/>' for y in porx[x])
            grupos.append(
                f'<g class="voa" style="--dx:{dx:.0f}px;--dy:{dy:.0f}px;--t:{tom};--f:{cor_final};animation-delay:{atraso:.2f}s">{rects}</g>'
            )
        return "".join(grupos)

    nome = colunas(ital, ox1, oy1, T["texto"], 0.15) + colunas(cunh, ox2, oy2, T["a"], 0.55)

    # O mascote: a marca viva, com olhos que piscam e olham em volta
    mx, my, mt = 1010, 96, 190
    vao = mt * 0.1
    bl = (mt - vao) / 2
    blocos = ""
    for idx, (bx, by) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
        cor = T[TONS[idx]] if nome_tema == "escuro" else [T["a"], T["c"], T["b"], T["d"]][idx]
        x = mx + bx * (bl + vao)
        y = my + by * (bl + vao)
        blocos += f'<rect x="{x:.1f}" y="{y + 6:.1f}" width="{bl:.1f}" height="{bl:.1f}" fill="{T["sombra"]}" opacity=".55"/>'
        blocos += f'<rect class="bloco b{idx}" x="{x:.1f}" y="{y:.1f}" width="{bl:.1f}" height="{bl:.1f}" fill="{cor}"/>'
    cx, cy = mx + mt / 2, my + mt / 2
    ow, oh = mt * 0.15, mt * 0.2
    olhos = ""
    for s in (-1, 1):
        ex = cx + s * (mt * 0.035 + ow / 2) - ow / 2
        ey = cy - oh / 2
        olhos += (
            f'<g class="olho" style="transform-origin:{ex + ow / 2:.1f}px {cy:.1f}px">'
            f'<rect x="{ex - 4:.1f}" y="{ey - 4:.1f}" width="{ow + 8:.1f}" height="{oh + 8:.1f}" fill="{T["olho"]}"/>'
            f'<rect class="pupila" x="{ex + ow * 0.27:.1f}" y="{ey + oh * 0.33:.1f}" width="{ow * 0.46:.1f}" height="{oh * 0.34:.1f}" fill="{T["texto"]}"/>'
            f"</g>"
        )
    mascote = f'<g class="mascote">{blocos}{olhos}</g>'

    # "faço ..." — as frases se alternam numa varrida de bloco
    frases = ["jogos na Godot", "back-end", "desktop em Delphi", "Rust, aprendendo", "Go, o próximo", "interfaces", "C++ competitivo"]
    n = len(frases)
    ciclo = n * 2.6
    fy = oy2 + h2 + 70
    faco = f'<text class="jb" x="64" y="{fy - 8}" font-size="13" letter-spacing="2" fill="{T["texto3"]}">FAÇO</text>'
    for i, fr in enumerate(frases):
        faco += (
            f'<text class="sg frase" x="120" y="{fy}" font-size="40" font-weight="600" letter-spacing="-1.2" fill="{T["a"]}" '
            f'style="animation-delay:{i * 2.6:.1f}s">{esc(fr)}</text>'
        )
    varre_w = 470
    faco += f'<rect class="varre" x="116" y="{fy - 40}" width="{varre_w}" height="52" fill="{T["a"]}"/>'

    rodape_y = A - 26
    rodape = (
        f'<line x1="0" y1="{rodape_y - 22}" x2="{L}" y2="{rodape_y - 22}" stroke="{T["linha"]}" stroke-width="1"/>'
        f'<text class="jb" x="64" y="{rodape_y}" font-size="12.5" letter-spacing="2.2" fill="{T["texto3"]}">'
        f'PORTFÓLIO ✦ 2019 — 2026 ✦ MG, BRASIL</text>'
        f'<text class="jb" x="{L - 64}" y="{rodape_y}" font-size="12.5" letter-spacing="1" fill="{T["texto2"]}" text-anchor="end">'
        f"jogos · back-end · desktop · interfaces · a Mosaic</text>"
    )
    tema_tag = (
        f'<text class="jb" x="{mx + mt / 2}" y="{my + mt + 44}" font-size="11.5" letter-spacing="2" fill="{T["texto3"]}" '
        f'text-anchor="middle">{"TEMA MOSAIC" if nome_tema == "escuro" else "TEMA PAPEL"} · troca com o seu GitHub</text>'
    )

    css = (
        f".p0{{fill:{T['a']};opacity:.42;animation:pulsa 6s ease-in-out infinite}}"
        f".p1{{fill:{T['b']};opacity:.42;animation:pulsa 6s ease-in-out infinite 2s}}"
        f".p2{{fill:{T['c']};opacity:.42;animation:pulsa 6s ease-in-out infinite 4s}}"
        f".p3{{fill:{T['texto']};opacity:.16}}"
        "@keyframes pulsa{0%,100%{opacity:.42}50%{opacity:.16}}"
        ".voa{fill:var(--f);animation:voa 1s cubic-bezier(.23,1,.32,1) both}"
        "@keyframes voa{0%{transform:translate(var(--dx),var(--dy));opacity:0;fill:var(--t)}"
        "60%{fill:var(--t);opacity:1}100%{transform:none;opacity:1;fill:var(--f)}}"
        ".mascote{animation:entra .8s cubic-bezier(.23,1,.32,1) both 1.4s}"
        "@keyframes entra{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}"
        ".olho{animation:pisca 4.2s infinite 2.4s}"
        "@keyframes pisca{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.08)}}"
        ".pupila{animation:olha 9s ease-in-out infinite 2s}"
        "@keyframes olha{0%,18%,100%{transform:none}24%,40%{transform:translate(-5px,2px)}48%,62%{transform:translate(5px,-3px)}70%,86%{transform:translate(2px,4px)}}"
        f".frase{{opacity:0;animation:frase {ciclo:.1f}s steps(1,end) infinite}}"
        f"@keyframes frase{{0%{{opacity:1}}{100 / n:.3f}%{{opacity:0}}100%{{opacity:0}}}}"
        f".varre{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:varre 2.6s cubic-bezier(.77,0,.175,1) infinite .26s}}"
        "@keyframes varre{0%,80%{transform:scaleX(0);transform-origin:left}90%{transform:scaleX(1);transform-origin:left}90.01%{transform-origin:right}100%{transform:scaleX(0);transform-origin:right}}"
    )
    corpo = f'<rect width="{L}" height="{A}" fill="{T["fundo"]}"/>{campo}{nome}{mascote}{faco}{tema_tag}{rodape}'
    return svg(L, A, corpo, css, "Italo Cunha — jogos, back-end, desktop e a Mosaic")


# ---------------------------------------------------------------------------
# 2. O que eu sei fazer
# ---------------------------------------------------------------------------
AREAS = [
    ("Back-end & APIs", "APIs REST em camadas, autenticação por token e integração com banco.",
     [("Python", "d"), ("Flask", "d"), ("SQLAlchemy", "p"), ("Java", "p"), ("Spring Boot", "p"), ("JPA", "p"), ("Laravel", "p"), ("PHP", "p"), ("Go", "a")]),
    ("Banco de dados", "Modelagem, migrations versionadas e busca full-text local.",
     [("SQL", "d"), ("MySQL", "d"), ("SQLite", "p"), ("FTS5", "p"), ("migrations", "p"), ("ORM", "p")]),
    ("Desktop & sistemas", "Sistemas com usuário, permissão e log; apps de janela; ferramentas de SO.",
     [("Delphi", "d"), ("Object Pascal", "d"), ("VCL", "p"), ("FireDAC", "p"), ("C++", "d"), ("pywebview", "p"), ("Electron", "p"), ("Rust", "a")]),
    ("Front-end & interface", "Interface sem framework, um design system inteiro e direção de arte.",
     [("HTML", "d"), ("CSS", "d"), ("JavaScript", "d"), ("Canvas", "p"), ("Web Workers", "p"), ("QML", "p"), ("design system", "p"), ("motion", "p")]),
    ("Jogos", "Jogos 2D na Godot, gráficos na mão em Pygame e a matemática por trás.",
     [("Godot", "d"), ("GDScript", "d"), ("Pygame", "p"), ("GameMaker", "p"), ("pixel art", "p"), ("raycasting", "p")]),
    ("Algoritmos", "Competitiva: custo antes de sintaxe, estruturas de dados, matemática.",
     [("C++", "d"), ("STL", "d"), ("estruturas de dados", "d"), ("complexidade", "p"), ("álgebra linear", "p")]),
    ("Linux & ferramentas", "Linux desde 2021: shell, PKGBUILD, rice própria e Git que conta história.",
     [("Linux", "d"), ("Arch / CachyOS", "d"), ("Git", "d"), ("Neovim", "d"), ("fish · bash", "d"), ("Hyprland", "p"), ("PKGBUILD", "p"), ("Matugen", "p")]),
]


def sei_fazer(nome_tema):
    T = TEMAS[nome_tema]
    L = 1280
    topo = 92
    linha_h = 104
    A = topo + linha_h * len(AREAS) + 24
    corpo = f'<rect width="{L}" height="{A}" fill="{T["fundo"]}"/>'
    # legenda
    corpo += f'<text class="jb" x="40" y="44" font-size="12.5" letter-spacing="2.2" fill="{T["texto3"]}">O QUE EU SEI FAZER ✦ italo --help</text>'
    lx = L - 40
    for rotulo, tipo in reversed([("uso todo dia", "d"), ("já entreguei projeto", "p"), ("aprendendo agora", "a")]):
        w = largura_mono(rotulo, 12.5)
        lx -= w
        corpo += f'<text class="jb" x="{lx:.0f}" y="44" font-size="12.5" fill="{T["texto2"]}">{rotulo}</text>'
        lx -= 26
        if tipo == "d":
            corpo += f'<rect x="{lx:.0f}" y="34" width="18" height="12" fill="{T["a"]}"/>'
        elif tipo == "p":
            corpo += f'<rect x="{lx + 0.75:.1f}" y="34.75" width="16.5" height="10.5" fill="none" stroke="{T["texto2"]}" stroke-width="1.5"/>'
        else:
            corpo += f'<rect x="{lx + 0.75:.1f}" y="34.75" width="16.5" height="10.5" fill="none" stroke="{T["texto2"]}" stroke-width="1.5" stroke-dasharray="3 2"/>'
        lx -= 26
    corpo += f'<line x1="40" y1="{topo - 20}" x2="{L - 40}" y2="{topo - 20}" stroke="{T["texto"]}" stroke-width="1.5"/>'

    for i, (area, desc, ferr) in enumerate(AREAS):
        y = topo + i * linha_h
        tom = T[TONS[i % 4]]
        sobre = T["sobre_" + TONS[i % 4]]
        g = f'<g class="linha" style="animation-delay:{0.1 + i * 0.09:.2f}s">'
        g += f'<text class="jb" x="40" y="{y + 26}" font-size="13" fill="{tom}">{i + 1:02d}</text>'
        g += f'<text class="sg" x="86" y="{y + 30}" font-size="30" font-weight="700" letter-spacing="-1" fill="{T["texto"]}">{esc(area)}</text>'
        g += f'<text class="sg" x="86" y="{y + 58}" font-size="15" fill="{T["texto2"]}">{esc(desc)}</text>'
        # ferramentas, quebrando linha quando precisa
        cx0 = 640
        cx, cy = cx0, y + 8
        for nome, nivel in ferr:
            tam = 13
            w = largura_mono(nome, tam) + 24 + (largura_mono("aprendendo", 9.5) + 8 if nivel == "a" else 0)
            if cx + w > L - 40:
                cx = cx0
                cy += 40
            if nivel == "d":
                g += f'<rect x="{cx:.0f}" y="{cy + 3}" width="{w:.0f}" height="30" fill="{T["sombra"]}" opacity=".55"/>'
                g += f'<rect x="{cx:.0f}" y="{cy}" width="{w:.0f}" height="30" fill="{tom}"/>'
                g += f'<text class="jb" x="{cx + 12:.0f}" y="{cy + 20}" font-size="{tam}" font-weight="700" fill="{sobre}">{esc(nome)}</text>'
            elif nivel == "p":
                g += f'<rect x="{cx + 0.75:.1f}" y="{cy + 0.75}" width="{w - 1.5:.0f}" height="28.5" fill="none" stroke="{tom}" stroke-opacity=".75" stroke-width="1.5"/>'
                g += f'<text class="jb" x="{cx + 12:.0f}" y="{cy + 20}" font-size="{tam}" fill="{T["texto"]}">{esc(nome)}</text>'
            else:
                g += f'<rect x="{cx + 0.75:.1f}" y="{cy + 0.75}" width="{w - 1.5:.0f}" height="28.5" fill="none" stroke="{tom}" stroke-width="1.5" stroke-dasharray="5 3"/>'
                g += f'<text class="jb" x="{cx + 12:.0f}" y="{cy + 20}" font-size="{tam}" fill="{tom}">{esc(nome)}</text>'
                g += f'<text class="jb" x="{cx + 12 + largura_mono(nome, tam) + 8:.0f}" y="{cy + 19}" font-size="9.5" letter-spacing="1" fill="{tom}">APRENDENDO</text>'
            cx += w + 8
        g += f'<line x1="40" y1="{y + linha_h - 8}" x2="{L - 40}" y2="{y + linha_h - 8}" stroke="{T["linha"]}" stroke-width="1"/>'
        g += "</g>"
        corpo += g
    css = ".linha{animation:sobe .6s cubic-bezier(.23,1,.32,1) both}@keyframes sobe{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
    return svg(L, A, corpo, css, "O que eu sei fazer: sete áreas com as ferramentas por nível")


# ---------------------------------------------------------------------------
# 3. Evolução: a linha do tempo como um grafo de commits
# ---------------------------------------------------------------------------
COMMITS = [
    ("2019", "gamemaker", "init"), ("2021", "ubuntu", "feat(sistema)"), ("2022", "artix", "refactor"),
    ("2023", "zé gotinha", "feat(jogos)"), ("2024", "c++", "perf"), ("2025", "matemática", "feat(algoritmos)"),
    ("2025", "ftc", "test(equipe)"), ("2026", "back-end", "feat(back-end)"), ("2026", "mosaic store", "feat(mosaic)"),
    ("2026", "tuxassist", "feat(voz)"), ("2026", "delphi", "feat(desktop)"), ("2026", "mosaic os", "feat(mosaic)"),
    ("hoje", "HEAD", "rust · go"),
]


def evolucao(nome_tema):
    T = TEMAS[nome_tema]
    L, A = 1280, 250
    x0, x1 = 70, L - 70
    ly = 128
    n = len(COMMITS)
    passo = (x1 - x0) / (n - 1)
    corpo = f'<rect width="{L}" height="{A}" fill="{T["fundo"]}"/>'
    corpo += f'<text class="jb" x="40" y="40" font-size="12.5" letter-spacing="2.2" fill="{T["texto3"]}">A EVOLUÇÃO ✦ git log --reverse</text>'
    corpo += f'<line x1="{x0}" y1="{ly}" x2="{x1}" y2="{ly}" stroke="{T["linha"]}" stroke-width="2"/>'
    corpo += f'<line class="traco" x1="{x0}" y1="{ly}" x2="{x1}" y2="{ly}" stroke="url(#grad)" stroke-width="3" pathLength="1"/>'
    corpo += (
        f'<defs><linearGradient id="grad" x1="0" x2="1"><stop offset="0" stop-color="{T["a"]}"/>'
        f'<stop offset=".5" stop-color="{T["b"]}"/><stop offset="1" stop-color="{T["c"]}"/></linearGradient></defs>'
    )
    ano_antes = None
    for i, (ano, rot, tipo) in enumerate(COMMITS):
        x = x0 + i * passo
        tom = T[TONS[i % 4]]
        atraso = 0.2 + i * (2.2 / n)
        g = f'<g class="no" style="animation-delay:{atraso:.2f}s;transform-origin:{x:.1f}px {ly}px">'
        if ano != ano_antes:
            g += f'<text class="sg" x="{x:.1f}" y="{ly - 34}" font-size="22" font-weight="700" letter-spacing="-.8" text-anchor="middle" fill="{tom}">{ano}</text>'
            ano_antes = ano
        ultimo = i == n - 1
        lado = 22 if ultimo else 16
        g += f'<rect x="{x - lado / 2:.1f}" y="{ly - lado / 2}" width="{lado}" height="{lado}" fill="{tom}" transform="rotate(45 {x:.1f} {ly})"/>'
        g += f'<text class="jb" x="{x:.1f}" y="{ly + 34}" font-size="12" text-anchor="middle" fill="{T["texto"]}">{esc(rot)}</text>'
        g += f'<text class="jb" x="{x:.1f}" y="{ly + 52}" font-size="10" text-anchor="middle" fill="{T["texto3"]}">{esc(tipo)}</text>'
        g += "</g>"
        if ultimo:
            g += f'<rect class="pulso" x="{x - 15:.1f}" y="{ly - 15}" width="30" height="30" fill="none" stroke="{tom}" stroke-width="2" transform="rotate(45 {x:.1f} {ly})" style="transform-origin:{x:.1f}px {ly}px"/>'
        corpo += g
    css = (
        ".traco{stroke-dasharray:1;stroke-dashoffset:1;animation:traco 2.4s cubic-bezier(.65,0,.35,1) forwards .2s}"
        "@keyframes traco{to{stroke-dashoffset:0}}"
        ".no{animation:no .5s cubic-bezier(.23,1,.32,1) both}"
        "@keyframes no{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:none}}"
        ".pulso{animation:pulso 2s ease-out infinite 2.8s;opacity:0}"
        "@keyframes pulso{0%{opacity:.9;transform:rotate(45deg) scale(.7)}100%{opacity:0;transform:rotate(45deg) scale(1.5)}}"
    )
    return svg(L, A, corpo, css, "A evolução de 2019 até hoje, como um grafo de commits")


# ---------------------------------------------------------------------------
# 4. Agora: a fila de compilação
# ---------------------------------------------------------------------------
FILA = [
    ("D", "delphi · pascal", "HW Atendimento, completo", "INSTALADO", 1.0, "c"),
    ("R", "rust", "aprendendo — e gostando", "COMPILANDO", 0.42, "a"),
    ("G", "go", "o próximo back-end", "NA FILA", 0.04, "b"),
    ("J", "java · spring boot", "a API do mesmo domínio", "INSTALADO", 1.0, "d"),
]


def agora(nome_tema):
    T = TEMAS[nome_tema]
    L, A = 1280, 236
    corpo = f'<rect width="{L}" height="{A}" fill="{T["fundo"]}"/>'
    corpo += f'<text class="jb" x="40" y="40" font-size="12.5" letter-spacing="2.2" fill="{T["texto3"]}">AGORA COMPILANDO ✦ paru -S italo-2026</text>'
    colw = (L - 80 - 3 * 14) / 4
    for i, (letra, nome, sub, status, p, tomk) in enumerate(FILA):
        x = 40 + i * (colw + 14)
        y = 62
        tom = T[tomk]
        sobre = T["sobre_" + tomk]
        vivo = status == "COMPILANDO"
        g = f'<g class="item" style="animation-delay:{0.1 + i * 0.12:.2f}s">'
        g += f'<rect x="{x}" y="{y}" width="{colw:.0f}" height="150" fill="{T["cartao"]}" stroke="{T["linha"]}"/>'
        if vivo:
            g += f'<rect x="{x}" y="{y}" width="4" height="150" fill="{tom}"/>'
        g += f'<rect x="{x + 20}" y="{y + 22}" width="44" height="44" fill="{tom}"/>'
        g += f'<text class="jb" x="{x + 42}" y="{y + 51}" font-size="19" font-weight="700" text-anchor="middle" fill="{sobre}">{letra}</text>'
        g += f'<text class="sg" x="{x + 78}" y="{y + 41}" font-size="19" font-weight="600" fill="{T["texto"]}">{esc(nome)}</text>'
        g += f'<text class="sg" x="{x + 78}" y="{y + 62}" font-size="13" fill="{T["texto3"]}">{esc(sub)}</text>'
        sw = largura_mono(status, 11) + 16
        if vivo:
            g += f'<rect x="{x + 20}" y="{y + 86}" width="{sw:.0f}" height="22" fill="{tom}"/>'
            g += f'<text class="jb" x="{x + 28}" y="{y + 101}" font-size="11" font-weight="700" fill="{sobre}">{status}</text>'
        else:
            g += f'<rect x="{x + 20.75}" y="{y + 86.75}" width="{sw - 1.5:.0f}" height="20.5" fill="none" stroke="{tom}" stroke-width="1.5"/>'
            g += f'<text class="jb" x="{x + 28}" y="{y + 101}" font-size="11" font-weight="700" fill="{tom}">{status}</text>'
        bw = colw - 40
        g += f'<rect x="{x + 20}" y="{y + 124}" width="{bw:.0f}" height="5" fill="{T["linha"]}"/>'
        if vivo:
            g += f'<clipPath id="barra{nome_tema}"><rect x="{x + 20}" y="{y + 124}" width="{bw * p:.0f}" height="5"/></clipPath>'
            g += f'<g clip-path="url(#barra{nome_tema})"><rect class="listras" x="{x - 8}" y="{y + 124}" width="{bw + 40:.0f}" height="5" fill="url(#listras{nome_tema})"/></g>'
            g += (
                f'<defs><pattern id="listras{nome_tema}" width="14" height="5" patternUnits="userSpaceOnUse">'
                f'<rect width="10" height="5" fill="{tom}"/><rect x="10" width="4" height="5" fill="{tom}" opacity=".4"/></pattern></defs>'
            )
            g += f'<text class="jb pct" x="{x + 20 + bw:.0f}" y="{y + 101}" font-size="12" text-anchor="end" fill="{T["texto2"]}">42%</text>'
        else:
            g += f'<rect x="{x + 20}" y="{y + 124}" width="{bw * p:.0f}" height="5" fill="{tom}"/>'
        g += "</g>"
        corpo += g
    css = (
        ".item{animation:sobe .6s cubic-bezier(.23,1,.32,1) both}@keyframes sobe{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
        ".listras{animation:corre .8s linear infinite}@keyframes corre{to{transform:translateX(14px)}}"
        ".pct{animation:piscar 1.6s steps(1) infinite}@keyframes piscar{50%{opacity:.35}}"
    )
    return svg(L, A, corpo, css, "Agora compilando: Delphi instalado, Rust compilando, Go na fila, Spring Boot instalado")


# ---------------------------------------------------------------------------
# 5. Teclas de contato
# ---------------------------------------------------------------------------
TECLAS = [
    ("portfolio", "portfólio ↗", "a"),
    ("email", "e-mail", "elevada"),
    ("linkedin", "linkedin", "elevada"),
    ("instagram", "instagram", "elevada"),
]


def tecla(nome_tema, rotulo, cor):
    T = TEMAS[nome_tema]
    tam = 17
    w = int(largura_sg(rotulo, tam, 600)) + 52
    h = 52
    face = T[cor] if cor != "elevada" else T["elevada"]
    texto = T["sobre_a"] if cor == "a" else T["texto"]
    borda = "#000" if nome_tema == "escuro" else T["texto"]
    extra = ""
    if nome_tema == "claro":
        extra = f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" fill="none" stroke="{T["texto"]}" stroke-width="1.5"/>'
        sombra = f'<rect x="4" y="5" width="{w}" height="{h}" fill="{T["texto"]}"/>'
    else:
        sombra = f'<rect x="0" y="5" width="{w}" height="{h}" fill="{borda}" opacity=".6"/>'
    corpo = (
        f'{sombra}<g class="face"><rect width="{w}" height="{h}" fill="{face}"/>{extra}'
        f'<text class="sg" x="{w / 2}" y="{h / 2 + 6}" font-size="{tam}" font-weight="600" text-anchor="middle" fill="{texto}">{esc(rotulo)}</text></g>'
    )
    css = ".face{animation:afunda 4s cubic-bezier(.23,1,.32,1) infinite}@keyframes afunda{0%,88%,100%{transform:none}92%,95%{transform:translateY(5px)}}"
    return svg(w + 5, h + 6, corpo, css if cor == "a" else "", rotulo)


def main():
    for nome_tema in TEMAS:
        (SAIDA / f"heroi-{nome_tema}.svg").write_text(heroi(nome_tema), encoding="utf-8")
        (SAIDA / f"sei-fazer-{nome_tema}.svg").write_text(sei_fazer(nome_tema), encoding="utf-8")
        (SAIDA / f"evolucao-{nome_tema}.svg").write_text(evolucao(nome_tema), encoding="utf-8")
        (SAIDA / f"agora-{nome_tema}.svg").write_text(agora(nome_tema), encoding="utf-8")
        for chave, rotulo, cor in TECLAS:
            (SAIDA / f"tecla-{chave}-{nome_tema}.svg").write_text(tecla(nome_tema, rotulo, cor), encoding="utf-8")
    print("pronto")


if __name__ == "__main__":
    main()
