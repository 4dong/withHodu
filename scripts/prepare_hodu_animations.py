"""Prepare generated Hodu animation sheets for review (local asset tool).
Requires Pillow, NumPy, SciPy. Does not call services or change application code.
"""
from pathlib import Path
import json
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/hodu/animations'
SPECS = {
    'loading-walk-01': ('걷기 로딩 1', [80] * 12, 'ui/hodu.py::walking_html / .h-walk-dog'),
    'loading-fetch-02': ('논문 가져오기 로딩 2', [90] * 12, 'app.py::process_paper_and_load / loading(pose="fetch")'),
    'reading-01': ('책 넘기기 1', [700,140,120,110,90,100,120,120,120,100,160,700], 'loading(pose="read") / 번역·전사'),
    'home-shake-01': ('물기 털기 1', [500,100,60,60,60,60,60,60,90,110,160,1200], 'ui/home.py::.hodu-hero-dog'),
    'home-idle-01': ('눈 깜박임과 꼬리 1', [1000,120,120,70,80,90,180,180,120,120,180,1200], 'ui/home.py::.hodu-hero-dog'),
}


def remove_key(image):
    rgba = np.array(image.convert('RGBA'))
    if np.any(rgba[:, :, 3] == 0):
        # The image tool may already key the requested background. Keep real alpha;
        # discard barely visible (<6%) chroma residue rather than flattening it.
        rgba[rgba[:, :, 3] < 16] = 0
        return Image.fromarray(rgba)
    rgb = rgba[:, :, :3]
    r, g, b = [rgb[:, :, i].astype(np.int16) for i in range(3)]
    key = (r - g > 65) & (b - g > 45) & (r > 130) & (b > 110)
    rgba[key] = 0
    return Image.fromarray(rgba)


def anchor(frame):
    alpha = np.array(frame)[:, :, 3] > 32
    labels, count = ndimage.label(alpha)
    if not count:
        raise ValueError('Empty animation cell')
    sizes = np.bincount(labels.ravel()); sizes[0] = 0
    component = labels == sizes.argmax()
    ys, xs = np.where(component)
    return ((int(xs.min()) + int(xs.max()) + 1) / 2, int(ys.max()) + 1,
            [int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1])


def prepare(name):
    title, durations, usage = SPECS[name]
    source = OUT / 'source' / f'{name}.png'
    image = Image.open(source)
    transparent = remove_key(image)
    w, h = image.size
    raw = [transparent.crop((round(col*w/4),round(row*h/3),round((col+1)*w/4),round((row+1)*h/3)))
           for row in range(3) for col in range(4)]
    anchors = [anchor(frame) for frame in raw]
    # One canvas/anchor for all frames, no per-frame rescaling or redrawing.
    size = int(math.ceil(max(w/4,h/3)/8)*8)
    target_x, target_y = size // 2, round(size * .88)
    frames, shifts = [], []
    for frame, (x, y, bounds) in zip(raw, anchors):
        dx, dy = round(target_x-x), round(target_y-y)
        bbox = frame.getbbox()
        if bbox and (bbox[0]+dx < 0 or bbox[1]+dy < 0 or bbox[2]+dx > size or bbox[3]+dy > size):
            raise ValueError(f'{name}: movement would crop frame; review source cell spacing')
        aligned = Image.new('RGBA',(size,size))
        aligned.alpha_composite(frame,(dx,dy))
        frames.append(aligned); shifts.append([dx,dy])
    folder = OUT / 'frames' / name
    folder.mkdir(parents=True,exist_ok=True)
    for index, frame in enumerate(frames,1):
        frame.save(folder/f'{name}-{index:02d}.png',optimize=True)
    sheet = Image.new('RGBA',(size*4,size*3))
    for i, frame in enumerate(frames):sheet.alpha_composite(frame,((i%4)*size,(i//4)*size))
    (OUT/'sheets').mkdir(exist_ok=True); sheet.save(OUT/'sheets'/f'{name}.png',optimize=True)
    (OUT/'previews').mkdir(exist_ok=True)
    frames[0].save(OUT/'previews'/f'{name}.apng',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
    # Contact sheet labels are for inspection only, never baked into runtime frames.
    contact = Image.new('RGB',(size*4,(size+28)*3),'#F7F8FA'); draw=ImageDraw.Draw(contact)
    for i,frame in enumerate(frames):
        x,y=(i%4)*size,(i//4)*(size+28)
        contact.paste(frame,(x,y),frame)
        draw.text((x+12,y+size+6),f'{i+1:02d} / {durations[i]}ms',fill='#315C49')
    contact.save(OUT/'previews'/f'{name}-contact.png')
    return {'id':name,'title':title,'frameCount':12,'frameWidth':size,'frameHeight':size,'columns':4,'rows':3,
            'order':'row-major','anchor':[target_x,target_y],'durationsMs':durations,'loop':name != 'home-shake-01',
            'previewLoops':True,'suggestedIdleDelayMs':[12000,20000] if name == 'home-shake-01' else None,
            'source':f'source/{name}.png','sheet':f'sheets/{name}.png','preview':f'previews/{name}.apng',
            'frames':[f'frames/{name}/{name}-{i+1:02d}.png' for i in range(12)],
            'applicationTarget':usage,'alignmentOffsets':shifts,'sourceMainComponentBounds':[a[2] for a in anchors],
            'notes':'Generated key poses; alpha removal and translation-only anchor alignment. No per-frame scale interpolation.'}


def main():
    animations = [prepare(name) for name in SPECS if (OUT/'source'/f'{name}.png').is_file()]
    (OUT/'manifest.json').write_text(json.dumps({'version':1,'reference':'../hodu-pixel-reference-v1.png','animations':animations},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({a['id']:{'frames':a['frameCount'],'size':[a['frameWidth'],a['frameHeight']]} for a in animations},ensure_ascii=False))


if __name__=='__main__':main()
