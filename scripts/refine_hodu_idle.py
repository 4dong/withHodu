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
mask=Image.new('L',base.size,0)
ImageDraw.Draw(mask).polygon([(0,0),(368,0),(368,145),(254,145),(253,167),(248,182),(247,205),(255,223),(263,244),(269,269),(269,300),(247,325),(0,368)],fill=255)
body=base.copy();body.putalpha(Image.fromarray(np.minimum(np.array(base.getchannel('A')),np.array(mask))))
src=Image.open(ROOT/'source/home-idle-tail-v2.png').convert('RGBA')
tails=[]
for i in range(12):
    cell=src.crop((i%4*362,i//4*362,(i%4+1)*362,(i//4+1)*362))
    a=np.array(cell);a[a[:,:,3]<32]=0;cell=Image.fromarray(a)
    box=cell.getbbox();tail=cell.crop(box)
    tail=tail.resize((round(tail.width*.56),round(tail.height*.56)),Image.Resampling.NEAREST)
    canvas=Image.new('RGBA',(368,368));canvas.alpha_composite(tail,(255-tail.width//2,294-tail.height));tails.append(canvas)
# A restrained blink uses only the two existing eye regions, never swaps the head.
closed=Image.open(ROOT/'frames/home-idle-01/home-idle-01-05.png').convert('RGBA')
closedref=ROOT/'source/home-idle-closed-reference.png'
if closedref.exists():closed=Image.open(closedref).convert('RGBA')
else:closed.save(closedref)
frames=[]
sequence=list(range(12))+list(range(10,0,-1))
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
durations=[110]*22+[900,70,100,70,900]
name='home-idle-02';folder=ROOT/'frames'/name;folder.mkdir(exist_ok=True)
sheet=Image.new('RGBA',(368*6,368*5))
for i,f in enumerate(frames):
    f.save(folder/f'{name}-{i+1:02d}.png');sheet.alpha_composite(f,(i%6*368,i//6*368))
sheet.save(ROOT/'sheets'/f'{name}.png')
frames[0].save(ROOT/'previews'/f'{name}.apng',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
contact=Image.new('RGB',sheet.size,'#edf3ef');contact.paste(sheet,mask=sheet.getchannel('A'));contact.save(ROOT/'previews'/f'{name}-contact.png')
p=ROOT/'manifest.json';m=json.loads(p.read_text());old=next(a for a in m['animations'] if a['id']=='home-idle-01');a={**old,'id':name,'title':'몸통 고정 · 눈 깜박임과 꼬리 2','frameCount':len(frames),'columns':6,'rows':5,'durationsMs':durations,'source':'source/home-idle-tail-v2.png','sheet':f'sheets/{name}.png','preview':f'previews/{name}.apng','frames':[f'frames/{name}/{name}-{i+1:02d}.png' for i in range(len(frames))],'notes':'Immutable reference body; generated tail in-betweens composited behind body; eye-only blink.'}
m['animations']=[v for v in m['animations'] if v['id']!='home-idle-02']+[a];p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
# Fixed torso/head/nose/paws must be byte-identical in every frame.
fixed=np.array(body)[:,:,3]==255
fixed[124:161,108:142]=False
fixed[124:161,175:209]=False
assert all(np.array_equal(np.array(f)[fixed],np.array(frames[0])[fixed]) for f in frames)
print(f'{len(frames)} frames; torso pixel invariance passed')
