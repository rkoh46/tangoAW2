from scenes import *
import struct, json, sys
from aw2test import rom as romlib
img = romlib.Image.load()
ids = []
for t in range(0x400):
    c = img.tile_class(t) & 0x1f
    if c in (6,8,10,11,14,20,9) or c>=16:
        ids.append(t)
print(len(ids), "ids")
LATT=[(x,y) for y in range(2,19,5) for x in range(3,28,5)]   # 5x4=20 per map... 
LATT=[(14,10)]
def read_objs(e):
    e.cmd("dumprange 07000000 1024 /tmp/_oam_t.bin")
    oam=open("/tmp/_oam_t.bin","rb").read()
    io=e.read(0x04000000,0x20)
    hof=struct.unpack_from("<H",io,0x10+12)[0]; vof=struct.unpack_from("<H",io,0x12+12)[0]
    out=[]
    for k in range(128):
        a0,a1,a2=struct.unpack_from("<HHH",oam,8*k)
        if (a0>>8)&3==2: continue
        y=a0&255; x=a1&511
        if 160<=y<224: continue
        if (a2>>10)&3!=3: continue
        if y>=160: y-=256
        if x>=240: x-=512
        shape=a0>>14; size=a1>>14
        w,h=[[(8,8),(16,16),(32,32),(64,64)],[(16,8),(32,8),(32,16),(64,32)],[(8,16),(8,32),(16,32),(32,64)]][shape][size]
        out.append(dict(x=x,y=y,w=w,h=h,tile=a2&1023,pal=a2>>12,hf=(a1>>12)&1,vf=(a1>>13)&1,idx=k,mode=(a0>>10)&3))
    return out,hof,vof
result={}
hq=[t for t in ids if img.tile_class(t)&0x1f==8]
rest=[t for t in ids if t not in hq]
batches=[rest[i:i+len(LATT)] for i in range(0,len(rest),len(LATT))]+[hq[i:i+2] for i in range(0,len(hq),2)]
weather=os.environ.get("W","clear")
ctx = mkctx("propsI_"+weather)
for bi,batch in enumerate(batches):
    m = ctx.map("props%d"%bi)
    place={}
    for t,(x,y) in zip(batch,LATT):
        m.terrain(x,y,t); place[t]=(x,y)
    nh=sum(1 for t in batch if img.tile_class(t)&0x1f==8)
    g=None
    for nco in (2+nh,3,4,2):
        try:
            g = ctx.start(m, ["andy","grit","drake","sonja"][:nco], weather=weather); break
        except Exception as ex:
            print("retry",hex(batch[0]),nco,str(ex)[:60],flush=True)
            for gg in ctx.games: 
                try: gg.e.close()
                except Exception: pass
            ctx.games.clear()
    if g is None: continue
    e=g.e
    for t,(x,y) in place.items():
        g.goto(x,y); e.wait(25)
        objs,hof,vof=read_objs(e)
        cx0=16*x-hof; cy0=16*y-vof
        near=objs
        result[t]=[dict(o,dx=o["x"]-cx0,dy=o["y"]-cy0) for o in near]
    e.close()
    print("batch",bi,len(result),flush=True)
json.dump(result,open("propsI_%s.json"%weather,"w"))
