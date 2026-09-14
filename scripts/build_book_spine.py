"""Render the cloth book-spine texture used on the essay bookshelf.

The image is a neutral grey luminance map (128 = no change): the light and shade of a rounded
spine, a cloth weave, raised bands near the head and tail, and worn edges. The page tints it
with each spine's colour through CSS background-blend-mode: overlay, so one image serves
every tone, including the green of the open book.
Run from the repository root: python3 scripts/build_book_spine.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'assets/essay/book-spine.png'
WIDTH, HEIGHT = 108, 348  # 2x the widest and tallest spine (54 x 174 css px)


def main():
    rng = np.random.default_rng(20260914)
    xi, yi = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    x = (np.arange(WIDTH) + 0.5) / WIDTH
    y = (np.arange(HEIGHT) + 0.5) / HEIGHT

    # Across the spine: shadow at the hinge, a soft sheen a third of the way in, falling off to the far edge.
    across = np.interp(x, [0.0, 0.05, 0.14, 0.32, 0.55, 0.8, 0.93, 1.0], [-46, -18, 8, 30, 14, -6, -22, -44])
    tex = 128.0 + np.broadcast_to(across, (HEIGHT, WIDTH)).copy()

    # Cloth: fine grain and a faint weave.
    tex += rng.normal(0, 5, (HEIGHT, WIDTH))
    tex += np.where(xi % 2 == 0, 2.5, -2.5) + np.where(yi % 3 == 0, 2.0, -1.0)

    # Slow unevenness along the length, like a book that has been handled.
    tex += np.interp(y, np.linspace(0, 1, 9), rng.normal(0, 4, 9))[:, None]

    # Raised bands: a lit ridge over a shaded groove, two near the head and two near the tail.
    for centre in (0.075, 0.105, 0.895, 0.925):
        row = int(centre * HEIGHT)
        tex[row - 2:row] += 26
        tex[row:row + 2] -= 30

    # Worn head and tail edges.
    edge = np.clip(1 - np.minimum(yi, HEIGHT - 1 - yi) / 6, 0, 1)
    tex += edge * rng.normal(10, 8, (HEIGHT, WIDTH))

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(tex, 0, 255).astype(np.uint8), 'L').save(TARGET, optimize=True)
    print(f'wrote {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
