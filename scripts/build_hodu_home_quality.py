"""Package reviewed generated sheets at the idle reference's scale and foot baseline.

Original sources are preserved. Nearest-neighbor resampling retains pixel edges.
Every action starts and ends with the actual idle frame, not a generated imitation.
"""
from pathlib import Path
import json
import math
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / 'assets/hodu/animations'
REFERENCE = ROOT / 'frames/home-idle-02/home-idle-02-01.png'


def visible_bounds(image):
    alpha = image.getchannel('A').point(lambda a: 255 if a >= 32 else 0)
    return alpha.getbbox()


def package(name, title, source, sequence, durations, *, isolate_subject=False):
    ref = Image.open(REFERENCE).convert('RGBA')
    image = Image.open(ROOT / source).convert('RGBA')
    w, h = image.size
    cells = [image.crop((round(i % 4 * w / 4), round(i // 4 * h / 2),
                         round((i % 4 + 1) * w / 4), round((i // 4 + 1) * h / 2))) for i in range(8)]
    ref_box = visible_bounds(ref)
    box = visible_bounds(cells[0])
    scale = (ref_box[3] - ref_box[1]) / (box[3] - box[1])
    target_center = (ref_box[0] + ref_box[2]) / 2
    # Shared scale per sheet; only align baseline to eliminate generated row drift.
    normalized = []
    metrics = []
    first = cells[0].getchannel('A').crop((0, round(cells[0].height * .65), cells[0].width, cells[0].height)).point(lambda a: 255 if a >= 32 else 0).getbbox()
    neutral_center = (first[0] + first[2]) / 2 * scale
    for cell in cells:
        pixel = np.array(cell)
        pixel[pixel[:, :, 3] < 16] = 0
        if isolate_subject:
            # Discard neighboring-cell spill, never change the dog's connected pixels.
            from scipy import ndimage
            labels, _ = ndimage.label(pixel[:, :, 3] >= 16)
            sizes = np.bincount(labels.ravel())
            sizes[0] = 0
            pixel[labels != sizes.argmax()] = 0
        cell = Image.fromarray(pixel).resize((round(cell.width * scale), round(cell.height * scale)), Image.Resampling.NEAREST)
        b = visible_bounds(cell)
        # Use lower-body bounds: hands and head tilts must not shift the feet.
        lower = cell.getchannel('A').crop((0, round(cell.height * .65), cell.width, cell.height)).point(lambda a: 255 if a >= 32 else 0).getbbox()
        center = (lower[0] + lower[2]) / 2
        dx = round(target_center - (box[0]+box[2])/2*scale + neutral_center - center)
        dy = ref_box[3] - b[3]
        frame = Image.new('RGBA', ref.size)
        frame.alpha_composite(cell, (dx, dy))
        normalized.append(frame)
        metrics.append({'bounds':visible_bounds(frame), 'offset':[dx,dy]})
    frames = [ref.copy() if i is None else normalized[i] for i in sequence]
    assert len(frames) == len(durations)
    assert frames[0].tobytes() == frames[-1].tobytes() == ref.tobytes()
    folder = ROOT / 'frames' / name
    folder.mkdir(parents=True, exist_ok=True)
    columns = 4
    rows = math.ceil(len(frames)/columns)
    sheet = Image.new('RGBA', (368*columns,368*rows))
    contact = Image.new('RGB', (368*columns,396*rows), '#edf3ef')
    draw = ImageDraw.Draw(contact)
    paths = []
    for i, frame in enumerate(frames):
        path = f'frames/{name}/{name}-{i+1:02d}.png'
        frame.save(ROOT/path, optimize=True)
        paths.append(path)
        sheet.alpha_composite(frame,(i%columns*368,i//columns*368))
        contact.paste(frame,(i%columns*368,i//columns*396),frame)
        draw.text((i%columns*368+12,i//columns*396+372),f'{i+1:02d} / {durations[i]}ms', fill='#315c49')
    sheet.save(ROOT/f'sheets/{name}.png', optimize=True)
    contact.save(ROOT/f'previews/{name}-contact.png')
    frames[0].save(ROOT/f'previews/{name}.apng', save_all=True, append_images=frames[1:], duration=durations,loop=0,disposal=0,blend=0)
    entry = dict(id=name,title=title,frameCount=len(frames),frameWidth=368,frameHeight=368,columns=columns,rows=rows,order='row-major',anchor=[180,324],durationsMs=durations,loop=False,source=source,sheet=f'sheets/{name}.png',preview=f'previews/{name}.apng',frames=paths,notes='Generated from exact idle reference; shared scale per sheet; fixed foot baseline; original idle pixels at both endpoints.',sourceScale=scale,alignment=metrics)
    return entry


def main():
    manifest_path = ROOT/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    entries=[
        package('home-pet-01','머리 쓰담쓰담', 'source/home-pet-01.png',
                [None,1,2,3,4,3,4,2,6,None], [160,160,160,200,200,200,200,160,160,400]),
        package('home-shake-03','같은 호두 · 몸 털고 제자리', 'source/home-shake-03.png',
                [None,1,2,3,2,3,4,5,6,None], [200,130,110,110,100,100,130,150,140,500])
    ]
    ids={e['id'] for e in entries}
    manifest['animations']=[e for e in manifest['animations'] if e['id'] not in ids]+entries
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{e['id']:{'duration':sum(e['durationsMs']),'scale':e['sourceScale']}} for e in entries]))


if __name__ == '__main__':
    main()
