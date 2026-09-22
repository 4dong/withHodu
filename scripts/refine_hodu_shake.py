"""Insert generated cushioning poses and retain the original shake keyframes."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from prepare_hodu_animations import anchor, remove_key
ROOT=Path(__file__).resolve().parents[1]/'assets/hodu/animations'
m=json.loads((ROOT/'manifest.json').read_text());old=next(a for a in m['animations'] if a['id']=='home-shake-01')
src=remove_key(Image.open(ROOT/'source/home-shake-inbetweens.png').convert('RGBA'))
base=[Image.open(ROOT/p).convert('RGBA') for p in old['frames']]
frames=[];durations=[]
for i,f in enumerate(base):
    frames.append(f);durations.append(500 if i==0 else 1000 if i==11 else 130)
    if i==11:break
    w,h=src.size;c=src.crop((round(i%4*w/4),round(i//4*h/3),round((i%4+1)*w/4),round((i//4+1)*h/3)))
    x,y,b=anchor(c)
    # Match the neighboring keyframe body height, excluding detached droplets.
    target=sum(anchor(base[j])[2][3]-anchor(base[j])[2][1] for j in (i,i+1))/2
    scale=target/(b[3]-b[1]);c=c.resize((round(c.width*scale),round(c.height*scale)),Image.Resampling.NEAREST)
    x,y,b=anchor(c);out=Image.new('RGBA',(368,368));out.alpha_composite(c,(round(184-x),round(324-y)))
    frames.append(out);durations.append(130)
name='home-shake-02';folder=ROOT/'frames'/name;folder.mkdir(exist_ok=True)
sheet=Image.new('RGBA',(368*6,368*4))
for i,f in enumerate(frames):
    f.save(folder/f'{name}-{i+1:02d}.png');sheet.alpha_composite(f,(i%6*368,i//6*368))
sheet.save(ROOT/'sheets'/f'{name}.png')
frames[0].save(ROOT/'previews'/f'{name}.apng',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
bg=Image.new('RGBA',sheet.size,'#edf3ef');bg.alpha_composite(sheet);bg.convert('RGB').save(ROOT/'previews'/f'{name}-contact.png')
a={**old,'id':name,'title':'물기 털기 · 완충 자세','frameCount':len(frames),'columns':6,'rows':4,'durationsMs':durations,'sheet':f'sheets/{name}.png','preview':f'previews/{name}.apng','source':'source/home-shake-inbetweens.png','frames':[f'frames/{name}/{name}-{i+1:02d}.png' for i in range(len(frames))],'notes':'12 original keyframes plus 11 generated cushioning poses; 4230ms total.'}
m['animations']=[a for a in m['animations'] if a['id']!=name]+[a];(ROOT/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
print(len(frames),sum(durations))
