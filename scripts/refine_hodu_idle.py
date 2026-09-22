"""Assemble generated tail in-betweens behind one immutable reference body."""
from pathlib import Path
from PIL import Image, ImageDraw
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]/'assets/hodu/animations'
base=Image.open(ROOT/'frames/home-idle-01/home-idle-01-01.png').convert('RGBA')
# Preserve a dedicated reference so this script is reproducible after replacing frames.
ref=ROOT/'source/home-idle-fixed-reference.png'
if ref.exists(): base=Image.open(ref).convert('RGBA')
else: base.save(ref)
# The old polygon shaved off the cheek/flank tufts. Reuse the left
# silhouette's actual pixel steps for the right edge; keep the inner face intact.
rgba=np.array(base)
body_pixels=rgba.copy()
for y in range(145,305):
    occupied=np.flatnonzero(rgba[y,:156,3]>32)
    if not len(occupied): continue
    left=int(occupied[0]);right=312-left
    body_pixels[y,right+1:]=0
    # Restore only the outer fur strip, not the eyes, muzzle, chest or paws.
    for x in range(right-26,right+1):
        body_pixels[y,x]=rgba[y,312-x]
body=Image.fromarray(body_pixels)
src=Image.open(ROOT/'source/home-idle-tail-v5.png').convert('RGBA')
tails=[]
for i in range(12):
    cell=src.crop((i%4*362,i//4*362,(i%4+1)*362,(i//4+1)*362))
    a=np.array(cell);a[a[:,:,3]<32]=0;cell=Image.fromarray(a)
    box=cell.getbbox();tail=cell.crop(box)
    tail=tail.resize((round(tail.width*.44),round(tail.height*.44)),Image.Resampling.NEAREST)
    canvas=Image.new('RGBA',(368,368));canvas.alpha_composite(tail,(255-tail.width//2,294-tail.height));tails.append(canvas)
# Three generated cushions share the same root and interpolated size.
extra=Image.open(ROOT/'source/home-idle-tail-cushion.png').convert('RGBA')
for j in range(3):
    w,h=extra.size
    cell=extra.crop((round(j*w/3),0,round((j+1)*w/3),h))
    pixels=np.array(cell);pixels[pixels[:,:,3]<32]=0;cell=Image.fromarray(pixels)
    cell=cell.crop(cell.getbbox())
    left=tails[4].getbbox();right=tails[5].getbbox();t=(j+1)/4
    tw=round((left[2]-left[0])*(1-t)+(right[2]-right[0])*t)
    th=round((left[3]-left[1])*(1-t)+(right[3]-right[1])*t)
    cell=cell.resize((tw,th),Image.Resampling.NEAREST)
    canvas=Image.new('RGBA',(368,368));canvas.alpha_composite(cell,(255-tw//2,294-th));tails.append(canvas)
# A restrained blink uses only the two existing eye regions, never swaps the head.
closed=Image.open(ROOT/'frames/home-idle-01/home-idle-01-05.png').convert('RGBA')
closedref=ROOT/'source/home-idle-closed-reference.png'
if closedref.exists():closed=Image.open(closedref).convert('RGBA')
else:closed.save(closedref)
frames=[]
sequence=[0,1,2,2,3,3,4,4,12,13,14,5,6,7,7,6,5,14,13,12,4,4,3,3,2,2,1,0]
for i,t in enumerate(sequence):
    frame=tails[t].copy();frame.alpha_composite(body)
    frames.append(frame)
# Blink while tail rests; only eye pixels are replaced. Keep nose, ears and feet fixed.
for phase in [0,1,2,1,0]:
    frame=frames[0].copy()
    if phase:
        for x in [108,175]:
            eye_source=closed if phase==2 else Image.open(ROOT/'frames/home-idle-01/home-idle-01-04.png').convert('RGBA')
            patch=eye_source.crop((x,124,x+34,161))
            frame.alpha_composite(patch,(x,124))
    frames.append(frame)
durations=[80 if t>=12 else 110 for t in sequence]+[900,70,100,70,900]
name='home-idle-02';folder=ROOT/'frames'/name;folder.mkdir(exist_ok=True)
rows=(len(frames)+5)//6
sheet=Image.new('RGBA',(368*6,368*rows))
for i,f in enumerate(frames):
    f.save(folder/f'{name}-{i+1:02d}.png');sheet.alpha_composite(f,(i%6*368,i//6*368))
sheet.save(ROOT/'sheets'/f'{name}.png')
frames[0].save(ROOT/'previews'/f'{name}.apng',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
contact=Image.new('RGB',sheet.size,'#edf3ef');contact.paste(sheet,mask=sheet.getchannel('A'));contact.save(ROOT/'previews'/f'{name}-contact.png')
p=ROOT/'manifest.json';m=json.loads(p.read_text());old=next(a for a in m['animations'] if a['id']=='home-idle-01');a={**old,'id':name,'title':'몸통 고정 · 눈 깜박임과 꼬리 2','frameCount':len(frames),'columns':6,'rows':rows,'durationsMs':durations,'source':'source/home-idle-tail-v5.png','sheet':f'sheets/{name}.png','preview':f'previews/{name}.apng','frames':[f'frames/{name}/{name}-{i+1:02d}.png' for i in range(len(frames))],'notes':'Immutable reference body; generated tail in-betweens composited behind body; eye-only blink.'}
m['animations']=[v for v in m['animations'] if v['id']!='home-idle-02']+[a];p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
# Fixed torso/head/nose/paws must be byte-identical in every frame.
fixed=np.array(body)[:,:,3]==255
fixed[124:161,108:142]=False
fixed[124:161,175:209]=False
assert all(np.array_equal(np.array(f)[fixed],np.array(frames[0])[fixed]) for f in frames)
print(f'{len(frames)} frames; torso pixel invariance passed')
