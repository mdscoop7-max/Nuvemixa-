from PIL import Image, ImageDraw, ImageFont
import numpy as np, cv2
a=np.array(Image.open('/home/claude/gad_en_full.png').convert('RGB'))[3:-3,3:-3].copy()
H,W,_=a.shape
ai=a.astype(int)
white=(ai.min(axis=2)>140)
orange=(ai[:,:,0]>190)&(ai[:,:,1]>60)&(ai[:,:,1]<180)&(ai[:,:,2]<90)
m=np.zeros((H,W),np.uint8)
y0,y1,x0,x1=232,535,75,840
m[y0:y1,x0:x1]=((white|orange)[y0:y1,x0:x1])*255
m[472:y1,640:x1]=0; m[494:y1,575:640]=0
# button text (white on blue)
m[588:648,120:480]=(white[588:648,120:480])*255
m=cv2.dilate(m,np.ones((7,7),np.uint8))
a=cv2.inpaint(a,m,6,cv2.INPAINT_TELEA)
# button: smooth blue fill by vertical interpolation to remove inpaint blotches
b=a.astype(float)
for x in range(118,484):
    top=b[584,x].copy(); bot=b[652,x].copy()
    for y in range(584,652):
        t=(y-584)/68; b[y,x]=top*(1-t)+bot*t
im=Image.fromarray(np.clip(b,0,255).astype('uint8'))
d=ImageDraw.Draw(im)
F='/usr/share/fonts/opentype/inter/'
hb=ImageFont.truetype(F+'Inter-Bold.otf',70); sb=ImageFont.truetype(F+'Inter-Regular.otf',34); bt=ImageFont.truetype(F+'Inter-SemiBold.otf',42)
WHITE=(255,255,255); OR=(255,120,24)
def line(x,ytop,parts,font):
    asc=font.getmetrics()[0]; bb=d.textbbox((0,0),'H',font=font); base=ytop-bb[1]+asc
    for t,c in parts:
        d.text((x,base),t,font=font,fill=c,anchor='ls'); x+=d.textlength(t,font=font)
    return x
e1=line(86,245,[("Unieke gadgets voor",WHITE)],hb)
e2=line(86,318,[("een ",WHITE),("slimmer leven.",OR)],hb)
for t,y in zip(["Ontdek bijzondere, praktische gadgets","die je dagelijks leven makkelijker,","leuker en moderner maken."],[412,455,498]):
    line(88,y,[(t,(236,240,246))],sb)
t="Bekijk gadgets →"; tw=d.textlength(t,font=bt); bb=d.textbbox((0,0),t,font=bt)
d.text(((83+500)/2-tw/2,(567+665)/2-(bb[1]+bb[3])/2),t,font=bt,fill=WHITE)
im.save('/home/claude/repo/alwaysdata/heroes/gadgets-2026.jpg',quality=86,optimize=True,progressive=True)
Image.open('/home/claude/gad_en_full.png').convert('RGB').crop((3,3,1713,719)).save('/home/claude/repo/alwaysdata/heroes/gadgets-2026-en.jpg',quality=86,optimize=True,progressive=True)
im.save('/home/claude/shots/gad_nl_preview.png'); print(e1,e2)
