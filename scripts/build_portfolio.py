"""Rebuild the submission portfolio from repository evidence and screenshots."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from PIL import Image
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
TMP = ROOT / 'tmp/pdfs'
TMP.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('KR', '/Library/Fonts/Arial Unicode.ttf'))
W, H = 960, 600
INK, GREEN, MUTED, BG = '#20332D', '#315E4C', '#617168', '#F6F7F2'
c = canvas.Canvas(str(OUT / 'withHodu-portfolio.pdf'), pagesize=(W, H))
c.setTitle('withHodu | 호두랑 프로젝트 포트폴리오')
c.setAuthor('withHodu')
manuscript = []

def box(x,y,w,h,color='#FFFFFF',radius=14):
    c.setFillColor(HexColor(color)); c.roundRect(x,H-y-h,w,h,radius,stroke=0,fill=1)

def text(s,x,y,size=14,color=INK,width=850):
    p=Paragraph(s, ParagraphStyle('p',fontName='KR',fontSize=size,leading=size*1.55,textColor=HexColor(color),wordWrap='CJK'))
    _,h=p.wrap(width,1000); p.drawOn(c,x,H-y-h)
    manuscript.append(s.replace('<br/>','\n'))
    return h

def page(n,section,title):
    c.setFillColor(HexColor(BG));c.rect(0,0,W,H,stroke=0,fill=1)
    text('withHodu  /  PROJECT PORTFOLIO',44,23,10,GREEN)
    text(section,650,23,10,MUTED,width=270)
    text(title,44,65,30,width=880)
    c.setStrokeColor(HexColor('#DCE3DB')); c.line(44,45,916,45)
    text('호두랑 · 논문 읽기와 자기소개서 정리',44,563,9,MUTED)
    text(f'{n:02d} / 04',866,563,9,MUTED,width=60)

def pic(path,x,y,w,h):
    im=Image.open(ROOT/path); iw,ih=im.size; scale=min(w/iw,h/ih)
    c.drawImage(str(ROOT/path),x+(w-iw*scale)/2,H-y-(h+ih*scale)/2,iw*scale,ih*scale,mask='auto')

def clipped_pic(path, region, x, y, w, h):
    # Place a source screenshot inside a PDF clipping frame, preserving its pixels.
    im=Image.open(ROOT/path)
    left,top,right,bottom=region
    scale=min(w/(right-left),h/(bottom-top))
    dw,dh=(right-left)*scale,(bottom-top)*scale
    dx,dy=x+(w-dw)/2,y+(h-dh)/2
    c.saveState()
    frame=c.beginPath();frame.rect(dx,H-dy-dh,dw,dh);c.clipPath(frame,stroke=0)
    c.drawImage(str(ROOT/path),dx-left*scale,H-dy-(im.height-top)*scale,im.width*scale,im.height*scale,mask='auto')
    c.restoreState()

page(1,'핵심 기능','호두랑 withHodu')
pic(Path('docs/screenshots/home.png'),395,133,521,352)
for y,title,body in [
    (154,'논문 읽기','영어 원문과 한국어 번역을 나란히 읽고, 같은 문단을 하이라이트로 확인합니다.'),
    (280,'논문 보관·비교','읽은 논문을 주제별 서재에 모으고 여러 논문을 비교한 보고서를 만듭니다.'),
    (406,'자소서 추출·정리','사진·PDF에서 문항과 본문을 추출하고, 원본과 비교해 수정·보관합니다.')]:
    text(title,44,y,21,GREEN,width=327)
    text(body,44,y+43,14,width=319)
text('Python · Streamlit · PyMuPDF · Gemini',44,524,11,MUTED,width=850)
c.showPage()

page(2,'화면 예시 01','논문 대역 리더')
pic(Path('docs/screenshots/reader-formula-hover.png'),44,123,627,412)
text('원문 위치 확인',705,173,19,GREEN,width=211)
text('번역 문단에 마우스를 올리면 해당 원문이 함께 강조됩니다.',705,212,14,width=207)
text('수식 표시',705,321,19,GREEN,width=211)
text('문장 속 수식은 KaTeX로, 줄 수식은 PDF 원본 이미지로 보여 줍니다.',705,360,14,width=207)
c.showPage()

page(3,'화면 예시 02','나의 서재')
clipped_pic(Path('scratch/hodu-ui-verification/library-desktop.png'),(319,85,1420,585),44,141,627,360)
text('주제별 논문 보관',705,173,19,GREEN,width=211)
text('읽은 논문을 컬렉션으로 모아 두고, 필요할 때 다시 엽니다.',705,212,14,width=207)
text('여러 논문 비교',705,321,19,GREEN,width=211)
text('논문을 골라 구조·평가 지표·학습 방식을 비교하고 보고서로 저장합니다.',705,360,14,width=207)
text('예시 자료를 넣은 서재 화면',44,515,10,MUTED,width=627)
c.showPage()

page(4,'화면 예시 03','자소서 추출과 검수')
clipped_pic(Path('scratch/hodu-ui-verification/essay-자료 추가.png'),(319,241,1420,920),44,137,591,347)
for y,title,body in [
    (142,'1. 파일 등록','사진·PDF를 지원서별로 묶어 올립니다.'),
    (255,'2. 문항·본문 추출','Gemini Vision으로 질문과 답변을 나눠 텍스트로 옮깁니다.'),
    (382,'3. 검수·내보내기','원본과 비교해 수정한 뒤 보관하고, 텍스트·Markdown 등으로 내보냅니다.')]:
    text(title,670,y,18,GREEN,width=246)
    text(body,670,y+38,13,width=241)
box(44,505,872,38,'#E6EDE3')
text('GitHub   github.com/4dong/withHodu',62,512,14,GREEN,width=835)
c.linkURL('https://github.com/4dong/withHodu',(44,H-543,916,H-505),relative=0)
c.showPage();c.save()
(OUT/'withHodu-portfolio-text.md').write_text('# withHodu 제출용 포트폴리오 원고\n\n'+'\n\n'.join(manuscript),encoding='utf-8')
doc=fitz.open(OUT/'withHodu-portfolio.pdf')
checks=[];thumbs=[]
for i,p in enumerate(doc):
    pix=p.get_pixmap(matrix=fitz.Matrix(1.5,1.5));pix.save(TMP/f'page-{i+1:02}.png')
    blocks=p.get_text('blocks')
    checks.append({'page':i+1,'text_chars':len(p.get_text()),'out_of_page_blocks':[b[:4] for b in blocks if b[0]<0 or b[1]<0 or b[2]>W or b[3]>H]})
    im=Image.open(TMP/f'page-{i+1:02}.png').convert('RGB');im.thumbnail((720,450));thumbs.append(im)
sheet=Image.new('RGB',(720,450*len(thumbs)),'#DCE3DB')
for i,im in enumerate(thumbs):sheet.paste(im,(0,i*450))
sheet.save(TMP/'contact-sheet.jpg')
(TMP/'checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
assert len(doc)==4 and all(not x['out_of_page_blocks'] for x in checks)
print(json.dumps({'pages':len(doc),'pdf':str(OUT/'withHodu-portfolio.pdf'),'checks':checks},ensure_ascii=False))
