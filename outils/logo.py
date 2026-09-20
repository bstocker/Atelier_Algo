#!/usr/bin/env python3
"""Produit les declinaisons web du logo depuis la source de design/.

    python3 outils/logo.py

Necessite Pillow, qui n'est pas une dependance de l'application :
    pip install Pillow

Regenere a partir de design/Logo_Evalio.png et design/Favicon.png :
  - atelier/static/img/logo-evalio.png               verrouillage complet
  - atelier/static/img/logo-evalio-dark.png          idem, theme sombre
  - atelier/static/img/logo-evalio-compact.png       barre de navigation
  - atelier/static/img/logo-evalio-compact-dark.png  idem, theme sombre
  - atelier/static/img/favicon.ico           16 / 32 / 48 px
  - atelier/static/img/apple-touch-icon.png  180 px
"""

import colorsys
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow est requis : pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "design", "Logo_Evalio.png")
ICON_SOURCE = os.path.join(ROOT, "design", "Favicon.png")
OUT = os.path.join(ROOT, "atelier", "static", "img")

LOGO_WIDTH = 560      # verrouillage complet, pour le README
COMPACT_WIDTH = 320   # barre de navigation : affiche a 30 px de haut, ecran 2x
PALETTE = 128         # le logo n'a qu'une poignee de teintes
MARK_SPLIT = 0.26     # le pictogramme occupe le quart gauche de la source
WORD_SPLIT = 0.28     # le mot-symbole commence juste apres


def drop_white_background(img):
    """Rend le fond blanc transparent, en douceur pour garder l'anticrenelage."""
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, _ = px[x, y]
            high, spread = max(r, g, b), max(r, g, b) - min(r, g, b)
            if high >= 250 and spread < 10:
                px[x, y] = (r, g, b, 0)
            elif high > 225 and spread < 14:
                px[x, y] = (r, g, b, int(255 * (250 - high) / 25))
    return img.crop(img.getbbox())


def lighten_for_dark_theme(img):
    """L' = max(L, 1 - L) : aucun pixel ne reste sombre.

    Teinte et saturation sont conservees. Le bleu marine s'eclaircit sans que
    le turquoise ne s'assombrisse, et le gris clair du sous-titre reste clair
    — ce qu'une simple inversion de luminosite aurait casse.
    """
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            r2, g2, b2 = colorsys.hls_to_rgb(h, max(l, 1 - l), s)
            px[x, y] = (round(r2 * 255), round(g2 * 255), round(b2 * 255), a)
    return out


def write(img, name, width):
    path = os.path.join(OUT, name)
    resized = img.resize((width, round(img.height * width / img.width)),
                         Image.LANCZOS)
    resized.quantize(colors=PALETTE, method=Image.FASTOCTREE).save(
        path, optimize=True)
    print("%-28s %4dx%-4d %6.1f Ko" % (name, resized.width, resized.height,
                                       os.path.getsize(path) / 1024))


def compact_lockup(img):
    """Pictogramme + mot-symbole, sans la baseline.

    La baseline « QUIZZES FOR A BRIGHTER YOU » mesure 35 px sur une source de
    456 : affichee a 30 px de haut dans la barre de navigation, elle tombe
    sous les 3 px et se reduit a une bavure. Le verrouillage complet reste
    donc reserve au README et aux grands formats.
    """
    mark = img.crop((0, 0, int(img.width * MARK_SPLIT), img.height))
    mark = mark.crop(mark.getbbox())

    word = img.crop((int(img.width * WORD_SPLIT), 0, img.width, img.height))
    blocks = _row_blocks(word)
    if len(blocks) < 2:
        return img                      # pas de baseline detectee : on garde tout
    top, bottom = blocks[0]             # premier bloc = le mot « Evalio »
    word = word.crop((0, top, word.width, bottom))
    word = word.crop(word.getbbox())

    gap = round(mark.height * 0.12)
    height = max(mark.height, word.height)
    canvas = Image.new("RGBA", (mark.width + gap + word.width, height),
                       (0, 0, 0, 0))
    canvas.paste(mark, (0, (height - mark.height) // 2), mark)
    canvas.paste(word, (mark.width + gap, (height - word.height) // 2), word)
    return canvas.crop(canvas.getbbox())


def _row_blocks(img):
    """Bandes horizontales contenant de la matiere, du haut vers le bas."""
    alpha = img.split()[3]
    rows = [sum(alpha.crop((0, y, img.width, y + 1)).getdata())
            for y in range(img.height)]
    limit = max(rows) * 0.02 if rows else 0

    blocks, start = [], None
    for y, value in enumerate(rows):
        if value > limit and start is None:
            start = y
        elif value <= limit and start is not None:
            blocks.append((start, y))
            start = None
    if start is not None:
        blocks.append((start, img.height))
    return blocks


def square(img, pad_ratio=0.06, background=None):
    """Recadre sur le contenu, puis centre dans un carre."""
    img = img.crop(img.getbbox())
    side = max(img.size)
    pad = round(side * pad_ratio)
    size = side + 2 * pad
    canvas = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def icon_source(logo):
    """Pictogramme des icones.

    On privilegie design/Favicon.png, fourni avec sa transparence et en haute
    definition. A defaut, on le decoupe dans la partie gauche du logo : le
    resultat est correct, mais moins net.
    """
    if os.path.isfile(ICON_SOURCE):
        print("pictogramme : design/Favicon.png")
        return Image.open(ICON_SOURCE).convert("RGBA")
    print("pictogramme : decoupe dans le logo (design/Favicon.png absent)")
    return logo.crop((0, 0, int(logo.width * MARK_SPLIT), logo.height))


def main():
    if not os.path.isfile(SOURCE):
        sys.exit("source introuvable : %s" % SOURCE)
    os.makedirs(OUT, exist_ok=True)

    logo = drop_white_background(Image.open(SOURCE).convert("RGBA"))
    print("contenu utile : %dx%d" % logo.size)

    write(logo, "logo-evalio.png", LOGO_WIDTH)
    write(lighten_for_dark_theme(logo), "logo-evalio-dark.png", LOGO_WIDTH)

    compact = compact_lockup(logo)
    write(compact, "logo-evalio-compact.png", COMPACT_WIDTH)
    write(lighten_for_dark_theme(compact), "logo-evalio-compact-dark.png",
          COMPACT_WIDTH)

    mark = icon_source(logo)

    # Favicon : fond transparent, l'onglet du navigateur le compose lui-meme.
    ico = os.path.join(OUT, "favicon.ico")
    square(mark).save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    print("%-28s %19.1f Ko" % ("favicon.ico", os.path.getsize(ico) / 1024))

    # Icone iOS : fond opaque. Un PNG transparent y serait compose sur du
    # noir, et le bleu marine de la toque y disparaitrait.
    write(square(mark, 0.12, (255, 255, 255, 255)), "apple-touch-icon.png", 180)


if __name__ == "__main__":
    main()
