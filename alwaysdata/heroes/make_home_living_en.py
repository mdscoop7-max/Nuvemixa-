from PIL import Image, ImageDraw, ImageFont
import numpy as np
src=Image.open('/mnt/user-data/uploads/1102f4f1-image.png').convert('RGB')
a=np.array(src).astype(float)
H,W,_=a.shape
# orange text colour: brightest orange in 'praktisch' box
box=a[320:382,370:660]; mask=(box[:,:,0]>200)&(box[:,:,1]>90)&(box[:,:,2]<80)
ORANGE=tuple(int(v) for v in np.median(box[mask],axis=0)) if mask.any() else (255,140,0)
# 1) headline + subtitle: inpaint only the text pixels (dilated) so the background/photo stays natural
import cv2
y0,y1,x0,x1=255,572,70,672
reg=a[y0:y1,x0:x1]
lum=reg.mean(axis=2)
txt=((lum>110)|((reg[:,:,0]>170)&(reg[:,:,1]>60)&(reg[:,:,2]<90)))
# only treat as text where the original background is dark navy (left part); right part near photo uses stricter test
m=np.zeros(a.shape[:2],np.uint8); m[y0:y1,x0:x1]=txt.astype(np.uint8)*255
strict=((reg.mean(axis=2)>170)|((reg[:,:,0]>220)&(reg[:,:,1]>100)&(reg[:,:,2]<60)))
m[y0:y1,640:x1]=(strict[:,640-x0:].astype(np.uint8))*255
m=cv2.dilate(m,np.ones((7,7),np.uint8),iterations=1)
img8=np.clip(a,0,255).astype(np.uint8)
img8=cv2.inpaint(img8,m,5,cv2.INPAINT_TELEA)
a=img8.astype(float)
# 2) button interior: vertical interpolation between rows above/below the text
by0,by1,bx0,bx1=606,676,112,612
for x in range(bx0,bx1):
    top=a[by0,x]; bot=a[by1,x]
    for y in range(by0,by1):
        t=(y-by0)/(by1-by0); a[y,x]=top*(1-t)+bot*t
# 3) bottom labels: per-row background sampled just left of each label
labels=[(188,416),(582,865),(1027,1238),(1405,1673)]
for lx0,lx1 in labels:
    for y in range(758,800):
        bg=a[y,lx0-6:lx0-2].mean(axis=0); bg2=a[y,lx1+2:lx1+6].mean(axis=0)
        for x in range(lx0,lx1):
            t=(x-lx0)/(lx1-lx0); a[y,x]=bg*(1-t)+bg2*t
im=Image.fromarray(np.clip(a,0,255).astype('uint8'))
d=ImageDraw.Draw(im)
B='/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
R='/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf'
M='/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf'
import os
if not os.path.exists(M): M=R
hb=ImageFont.truetype(B,58); sb=ImageFont.truetype(R,29); btn=ImageFont.truetype(B,40); lb=ImageFont.truetype(M,24)
WHITE=(255,255,255)
def line(x,ytop,parts,font):
    for txt,col in parts:
        bb=d.textbbox((0,0),txt,font=font)
        d.text((x,ytop-bb[1]),txt,font=font,fill=col); x+=d.textlength(txt,font=font)
line(84,262,[("Smart solutions",WHITE)],hb)
line(87,322,[("for a ",WHITE),("practical",ORANGE)],hb)
line(87,386,[("home.",WHITE)],hb)
for i,t in enumerate(["Handy organizers, kitchen accessories","and stylish home accessories","for every day."]):
    line(91,[463,500,539][i],[(t,(240,244,248))],sb)
# button text centred in button
t="View Home & Living"
tw=d.textlength(t,font=btn); bb=d.textbbox((0,0),t,font=btn)
cx=(79+628)/2; cy=(591+690)/2
aw=46; x0b=cx-(tw+18+aw)/2; d.text((x0b, cy-(bb[1]+bb[3])/2), t, font=btn, fill=WHITE); ax=x0b+tw+18; d.line([(ax,cy),(ax+aw-6,cy)],fill=WHITE,width=5); d.polygon([(ax+aw,cy),(ax+aw-16,cy-12),(ax+aw-16,cy+12)],fill=WHITE)
for (lx0,lx1),t in zip(labels,["Kitchen accessories","Organizers & Storage","Home accessories","Household helpers"]):
    bb=d.textbbox((0,0),t,font=lb)
    d.text((lx0+4, 786), t, font=lb, fill=WHITE, anchor='ls')
im.save('/home/claude/repo/alwaysdata/heroes/home-living-2026-en.jpg',quality=86,optimize=True,progressive=True)
im.save('/home/claude/shots/home-living-en-preview.png')
print(ORANGE)
