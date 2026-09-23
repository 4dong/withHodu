"""One approved water-shake identity for idle, petting and all action endpoints.

Only sheet slicing, fixed-scale packaging and disconnected spill cleanup occur
here. Appearance changes come from the generated source, not color filters.
"""
from pathlib import Path
import json
import math
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]/'assets/hodu/animations'
SOURCE = ROOT/'source/home-unified-01.png'


def bounds(image):
    return image.getchannel('A').point(lambda a: 255 if a>=32 else 0).getbbox()


def emit(name, title, frames, durations, *, loop=False, **extra):
    assert len(frames)==len(durations)
    columns, rows=6,math.ceil(len(frames)/6)
    folder=ROOT/'frames'/name
    folder.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGBA',(368*columns,368*rows))
    contact=Image.new('RGB',(368*columns,396*rows),'#edf3ef')
    draw=ImageDraw.Draw(contact)
    paths=[]
    for i,frame in enumerate(frames):
        path=f'frames/{name}/{name}-{i+1:02d}.png'
        frame.save(ROOT/path,optimize=True);paths.append(path)
        sheet.alpha_composite(frame,(i%columns*368,i//columns*368))
        contact.paste(frame,(i%columns*368,i//columns*396),frame)
        draw.text((i%columns*368+12,i//columns*396+372),f'{i+1:02d} / {durations[i]}ms',fill='#315c49')
    sheet.save(ROOT/f'sheets/{name}.png',optimize=True)
    contact.save(ROOT/f'previews/{name}-contact.png')
    frames[0].save(ROOT/f'previews/{name}.apng',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
    return dict(id=name,title=title,frameCount=len(frames),frameWidth=368,frameHeight=368,columns=columns,rows=rows,order='row-major',anchor=[180,324],durationsMs=durations,loop=loop,source='source/home-unified-01.png',sheet=f'sheets/{name}.png',preview=f'previews/{name}.apng',frames=paths,identityReference='home-shake-02',**extra)


def main():
    p=ROOT/'manifest.json';manifest=json.loads(p.read_text())
    old=next(a for a in manifest['animations'] if a['id']=='home-shake-02')
    original=[]
    for path in old['frames']:
        image=Image.open(ROOT/path).convert('RGBA').resize((391,391),Image.Resampling.NEAREST)
        frame=Image.new('RGBA',(368,368));frame.alpha_composite(image,(-23,-20));original.append(frame)
    reference=original[0]
    source=Image.open(SOURCE).convert('RGBA');w,h=source.size
    cells=[]
    # Reviewed gutters: the generator padded the first row more than the others.
    row_bounds=[(160,465),(475,830),(839,1197)]
    for i in range(12):
        top,bottom=row_bounds[i//4]
        cell=source.crop((round(i%4*w/4),top,round((i%4+1)*w/4),bottom))
        pixels=np.array(cell);pixels[pixels[:,:,3]<16]=0
        labels,_=ndimage.label(pixels[:,:,3]>=16)
        counts=np.bincount(labels.ravel());counts[0]=0
        # Keep the hand too, if disconnected; only remove tiny cell-edge spill.
        keep=counts>=max(16,counts.max()*.004);keep[0]=False
        pixels[~keep[labels]]=0
        cells.append(Image.fromarray(pixels))
    base=bounds(cells[0]);target=bounds(reference)
    scale=(target[3]-target[1])/(base[3]-base[1])
    scale_x=(target[2]-target[0])/(base[2]-base[0])
    normalized=[]
    for cell in cells:
        cell=cell.resize((round(cell.width*scale_x),round(cell.height*scale)),Image.Resampling.NEAREST)
        b=bounds(cell)
        # Body is fixed; exclude the entering hand from horizontal alignment.
        strip=cell.crop((0,round(cell.height*.65),cell.width,cell.height))
        lower=bounds(strip)
        initial=cells[0].crop((0,round(cells[0].height*.65),cells[0].width,cells[0].height))
        first=bounds(initial)
        dx=round((target[0]+target[2])/2-(base[0]+base[2])/2*scale_x+(first[0]+first[2])/2*scale_x-(lower[0]+lower[2])/2)
        dy=target[3]-b[3]
        frame=Image.new('RGBA',(368,368));frame.alpha_composite(cell,(dx,dy));normalized.append(frame)
    idle=[reference,normalized[1],normalized[2],normalized[3],reference]
    pet=[reference]+[normalized[i] for i in [4,5,6,7,8,9,5,10]]+[reference]
    # Original movement retained in full. A settling blink shares the new idle art.
    shake=original+[normalized[1],normalized[2],normalized[3],reference]
    entries=[
        emit('home-idle-03','물 털기 기준 · 가벼운 눈 깜빡임',idle,[2300,80,120,80,1400],loop=True),
        emit('home-pet-02','물 털기 기준 · 쓰담쓰담',pet,[160,160,160,200,200,200,200,160,160,400]),
        emit('home-shake-05','원래 물 털기 · 같은 호두로 복귀',shake,old['durationsMs']+[80,120,80,300],preservedAnimation='home-shake-02',preservedFrameRange=[0,22])
    ]
    for entry in entries:
        first=Image.open(ROOT/entry['frames'][0]).convert('RGBA')
        last=Image.open(ROOT/entry['frames'][-1]).convert('RGBA')
        assert first.tobytes()==last.tobytes()==reference.tobytes()
    ids={a['id'] for a in entries}
    manifest['animations']=[a for a in manifest['animations'] if a['id'] not in ids]+entries
    p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({a['id']:sum(a['durationsMs']) for a in entries}))


if __name__=='__main__':main()
