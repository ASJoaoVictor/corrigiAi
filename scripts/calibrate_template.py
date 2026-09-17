"""Reproduce measured PDF geometry; needs development dependency PyMuPDF."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
def rect(x,y,w,h): return dict(x=x/433,y=y/613,width=w/433,height=h/613)
t=dict(id='opi_fundamental_2026',name='OPI Fundamental 2026',normalized_width=1299,normalized_height=1839,source='Frame 1.pdf; 433 x 613 pt',cpf=dict(enabled=True,digits=11,region=rect(17,164,156,18),cells=[rect(x,164,13,18) for x in [17+13*i for i in range(9)]+[147,160]]),questions=dict(count=30,alternatives=list('ABCDE'),regions=[]),thresholds=dict(min_fill=.60,multiple_mark=.48,min_difference=.18,blank_max=.40))
for n in range(30):
 block,row=divmod(n,10)
 t['questions']['regions'].append(dict(number=n+1,bubbles=[dict(answer=a,**rect(61+129*block+16*i,373+19*row,13,13)) for i,a in enumerate('ABCDE')]))
(ROOT/'app/omr/templates/opi_fundamental_2026.json').write_text(json.dumps(t,indent=2))
im=Image.open(ROOT/'docs/card-reference.png').convert('RGB'); d=ImageDraw.Draw(im)
def box(r,color,label):
 x,y,w,h=[r[k]*s for k,s in [('x',im.width),('y',im.height),('width',im.width),('height',im.height)]]
 d.rectangle((x,y,x+w,y+h),outline=color,width=2);d.text((x,y-12),label,fill=color)
box(t['cpf']['region'],'blue','CPF')
for i,r in enumerate(t['cpf']['cells']):box(r,'red',str(i+1))
for q in t['questions']['regions']:
 for b in q['bubbles']:box(b,'red',f"{q['number']:02}{b['answer']}")
im.save(ROOT/'docs/template-validation.png')
