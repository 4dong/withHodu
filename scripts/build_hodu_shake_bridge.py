"""Keep every original water-shake pose and join it with generated opaque in-betweens."""
import json
import math
from PIL import Image, ImageDraw
from build_hodu_home_quality import ROOT, REFERENCE, package


def main():
    manifest_path = ROOT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    old = next(a for a in manifest['animations'] if a['id'] == 'home-shake-02')
    bridge = package('home-shake-bridge-01', '물 털기 준비와 정리',
                     'source/home-shake-bridge-01.png',
                     [None, 0, 1, 2, 3, 4, 5, 6, 7, None],
                     [100] * 10, isolate_subject=True)
    neutral = Image.open(REFERENCE).convert('RGBA')
    # Bake the previously reviewed 1.062 CSS scale/foot anchor into the old art.
    # No recoloring, pose replacement, opacity interpolation or image blending.
    originals = []
    for path in old['frames']:
        image = Image.open(ROOT / path).convert('RGBA')
        image = image.resize((391, 391), Image.Resampling.NEAREST)
        frame = Image.new('RGBA', (368, 368))
        frame.alpha_composite(image, (-23, -20))
        originals.append(frame)
    generated = [Image.open(ROOT / p).convert('RGBA') for p in bridge['frames'][1:-1]]
    frames = [neutral] + generated[:4] + originals + generated[4:] + [neutral]
    durations = [100] + [90]*4 + [180] + old['durationsMs'][1:-1] + [220] + [110]*4 + [360]
    assert len(frames) == len(durations)
    name = 'home-shake-04'
    folder = ROOT / 'frames' / name
    folder.mkdir(parents=True, exist_ok=True)
    columns, rows = 6, math.ceil(len(frames)/6)
    sheet = Image.new('RGBA', (368*columns, 368*rows))
    contact = Image.new('RGB', (368*columns, 396*rows), '#edf3ef')
    draw = ImageDraw.Draw(contact)
    paths = []
    for i, frame in enumerate(frames):
        path = f'frames/{name}/{name}-{i+1:02d}.png'
        frame.save(ROOT/path, optimize=True)
        paths.append(path)
        sheet.alpha_composite(frame, (i%columns*368, i//columns*368))
        contact.paste(frame, (i%columns*368, i//columns*396), frame)
        draw.text((i%columns*368+12, i//columns*396+372), f'{i+1:02d} / {durations[i]}ms', fill='#315c49')
    sheet.save(ROOT/f'sheets/{name}.png', optimize=True)
    contact.save(ROOT/f'previews/{name}-contact.png')
    frames[0].save(ROOT/f'previews/{name}.apng',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
    entry = dict(id=name,title='원래 물 털기 + 생성 중간 자세',frameCount=len(frames),frameWidth=368,frameHeight=368,columns=columns,rows=rows,order='row-major',anchor=[180,324],durationsMs=durations,loop=False,source='source/home-shake-bridge-01.png',sheet=f'sheets/{name}.png',preview=f'previews/{name}.apng',frames=paths,preservedAnimation='home-shake-02',preservedFrameRange=[5,27],notes='All 23 original water-shake frames retained with fixed scale. Eight generated preparation/settling poses. Exact idle endpoints; no opacity crossfade.')
    manifest['animations']=[a for a in manifest['animations'] if a['id'] not in {name,bridge['id']}] + [bridge,entry]
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'{name}: {len(frames)} frames / {sum(durations)}ms; all {len(originals)} original poses preserved')


if __name__ == '__main__':
    main()
