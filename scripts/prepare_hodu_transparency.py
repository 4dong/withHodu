"""Create an alpha atlas without redrawing or moving any original RGB pixels.

Only pale, low-chroma pixels connected to the atlas border are background.
Enclosed light fur, paper, eyes, and books retain their original opacity.
Run from the repository root: python3 scripts/prepare_hodu_transparency.py
"""
from collections import deque
from pathlib import Path
import json

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/hodu/hodu-pixel-reference-v1.png'
TARGET = ROOT / 'assets/hodu/hodu-pixel-transparent-v1.png'


def main():
    rgb = np.array(Image.open(SOURCE).convert('RGB'))
    r, g, b = [rgb[:, :, i].astype(np.int16) for i in range(3)]
    candidate = (r >= 240) & (g >= 232) & (b >= 215) & ((rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2)) <= 40)
    height, width = candidate.shape
    removed = np.zeros_like(candidate)
    queue = deque()

    def visit(y, x):
        if candidate[y, x] and not removed[y, x]:
            removed[y, x] = True
            queue.append((y, x))

    for x in range(width):
        visit(0, x)
        visit(height - 1, x)
    for y in range(height):
        visit(y, 0)
        visit(y, width - 1)
    while queue:
        y, x = queue.popleft()
        if y: visit(y - 1, x)
        if y + 1 < height: visit(y + 1, x)
        if x: visit(y, x - 1)
        if x + 1 < width: visit(y, x + 1)

    rgba = np.dstack((rgb, np.where(removed, 0, 255).astype(np.uint8)))
    Image.fromarray(rgba).save(TARGET, optimize=True)
    saved = np.array(Image.open(TARGET))
    assert saved.shape == (height, width, 4)
    assert np.array_equal(saved[:, :, :3], rgb), 'Original colors changed'
    assert saved[0, 0, 3] == 0
    assert 0.25 < removed.mean() < 0.8, 'Unexpected foreground/background split'
    # Interior light muzzle, dark eye, and a paper/book interior must stay opaque.
    for x, y in ((161, 203), (169, 252), (117, 929), (1180, 588)):
        assert saved[y, x, 3] == 255, f'Foreground lost at {x},{y}'
    report = {'source': str(SOURCE.relative_to(ROOT)), 'output': str(TARGET.relative_to(ROOT)),
              'size': [width, height], 'mode': 'RGBA', 'rgb_preserved': True,
              'transparent_pixels': int(removed.sum()), 'transparent_fraction': float(removed.mean())}
    (TARGET.parent / 'hodu-transparency-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
