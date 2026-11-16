import struct,sys,collections
from pathlib import Path
OPS='Mov2 Int2 Float2 Bool2 Bytes2 String2 Null1 Add3 Sub3 Mul3 SDiv3 UDiv3 SMod3 UMod3 Shl3 SShr3 UShr3 And3 Or3 Xor3 Neg2 Not2 Incr1 Decr1 Call02 Call13 Call24 Call35 Call46 CallN* CallMethod* CallThis* CallClosure* StaticClosure2 InstanceClosure3 VirtualClosure3 GetGlobal2 SetGlobal2 Field3 SetField3 GetThis2 SetThis2 DynGet3 DynSet3 JTrue2 JFalse2 JNull2 JNotNull2 JSLt3 JSGte3 JSGt3 JSLte3 JULt3 JUGte3 JNotLt3 JNotGte3 JEq3 JNotEq3 JAlways1 ToDyn2 ToSFloat2 ToUFloat2 ToInt2 SafeCast2 UnsafeCast2 ToVirtual2 Label0 Ret1 Throw1 Rethrow1 Switch* NullCheck1 Trap2 EndTrap1 GetI83 GetI163 GetMem3 GetArray3 SetI83 SetI163 SetMem3 SetArray3 New1 ArraySize2 Type2 GetType2 GetTID2 Ref2 Unref2 Setref2 MakeEnum* EnumAlloc2 EnumIndex2 EnumField4 SetEnumField3 Assert0 RefData2 RefOffset3 Nop0'.split()
class HL:
 def __init__(self,path):
  self.b=path if isinstance(path,bytes) else Path(path).read_bytes();self.p=4; assert self.b[:4]==b'HLB\x04'
  self.flags,ni,nf,ns,nt,ng,nn,nfn,nc,self.entry=[self.idx() for _ in range(10)]
  self.ints=struct.unpack('<%di'%ni,self.take(4*ni));self.floats=struct.unpack('<%dd'%nf,self.take(8*nf)); self.strings=self.strpool(ns);self.files=self.strpool(self.idx()) if self.flags&1 else []
  self.types=[];self.names={};self.funcs={};self.natives={}
  for ti in range(nt):
   k=self.byte();t={'k':k};self.types.append(t)
   if k in (10,20):t['args']=[self.idx() for _ in range(self.byte())];t['ret']=self.idx()
   elif k==11:
    t['name']=self.s();t['super']=self.idx();t['global']=self.idx();a,b,c=[self.idx() for _ in range(3)];t['fields']=[(self.s(),self.idx()) for _ in range(a)];t['proto']=[(self.s(),self.idx(),self.idx()) for _ in range(b)];t['bindings']=[(self.idx(),self.idx()) for _ in range(c)]
    for n,f,p in t['proto']:self.names[f]=t['name']+'.'+n
   elif k in (14,19):t['param']=self.idx()
   elif k==15:t['fields']=[(self.s(),self.idx()) for _ in range(self.idx())]
   elif k==17:t['name']=self.s()
   elif k==18:
    t['name']=self.s();t['global']=self.idx();t['constructs']=[(self.s(),[self.idx() for _ in range(self.idx())]) for _ in range(self.byte())]
   elif k>=21:raise ValueError((k,ti,self.p,self.types[-6:],self.b[self.p-25:self.p+25].hex()))
  self.globals=[self.idx() for _ in range(ng)]
  for _ in range(nn):
   lib,n,t,f=self.s(),self.s(),self.idx(),self.idx();self.names[f]=lib+'.'+n;self.natives[f]=t
  for i in range(nfn):
   start=self.p;t,f,nr,no=[self.idx() for _ in range(4)];regs=[self.idx() for _ in range(nr)];ops=[]
   for j in range(no):
    off=self.p;op=OPS[self.byte()];name=op[:-1];n=op[-1]
    if n!='*':a=[self.idx() for _ in range(int(n))]
    elif name=='Switch':a=[self.idx(),self.idx()];a +=[self.idx() for _ in range(a[1]+1)]
    else:a=[self.idx(),self.idx()];a +=[self.idx() for _ in range(self.byte())]
    ops.append((name,a,off))
   ops_end=self.p;debug=[];assign=[];debug_end=self.p
   if self.flags&1:
    fi=-1;line=0
    while len(debug)<no:
     c=self.byte()
     if c&1:fi=(c>>1)*256+self.byte()
     elif c&2:debug.extend([(fi,line)]*((c>>2)&15));line+=c>>6
     elif c&4:line+=c>>3;debug.append((fi,line))
     else:line=(c>>3)|(self.byte()<<5)|(self.byte()<<13);debug.append((fi,line))
    debug_end=self.p;assign=[(self.s(),self.idx()) for _ in range(self.idx())]
   self.funcs[f]=dict(t=t,regs=regs,ops=ops,debug=debug,assign=assign,start=start,end=self.p,ops_end=ops_end,debug_end=debug_end)
  self.const=[(self.idx(),[self.idx() for _ in range(self.idx())]) for _ in range(nc)]
  assert self.p==len(self.b),(self.p,len(self.b))
  for t in self.types:
   if t['k']==11:
    fields=self.fields(self.types.index(t))
    for fi,f in t['bindings']:
     if fi<len(fields):self.names.setdefault(f,t['name']+'.'+fields[fi][0])
  # All sections have been consumed exactly.
 def take(self,n):b=self.b[self.p:self.p+n];self.p+=n;return b
 def byte(self):b=self.b[self.p];self.p+=1;return b
 def idx(self):
  b=self.byte()
  if b<128:return b
  n=(b&31)*256+self.byte() if b<192 else ((b&31)<<24)|(self.byte()<<16)|(self.byte()<<8)|self.byte()
  return -n if b&32 else n
 def s(self):return self.strings[self.idx()]
 def strpool(self,n):
  size=struct.unpack('<I',self.take(4))[0];b=self.take(size);pos=0;out=[]
  for _ in range(n):
   l=self.idx();assert b[pos+l]==0;out.append(b[pos:pos+l].decode('utf8','replace'));pos+=l+1
  assert pos==size;return out
 def fields(self,t):
  ty=self.types[t];return (self.fields(ty['super']) if ty.get('super',-1)>=0 else [])+ty.get('fields',[])
 def proto(self,t):
  ty=self.types[t];d=self.proto(ty['super']) if ty.get('super',-1)>=0 else {};d.update({p:(n,f) for n,f,p in ty.get('proto',[]) if p>=0});return d
 def typename(self,t):return self.types[t].get('name',str(t)+':'+str(self.types[t]['k']))
 def detail(self,f):
  fn=self.funcs[f];print('\nFUNCTION',f,self.names.get(f), 'assign',fn['assign'],'regs',[(i,self.typename(t)) for i,t in enumerate(fn['regs'])]);regs=fn['regs']
  for j,(op,a,off) in enumerate(fn['ops']):
   extra=''
   try:
    if op=='Int':extra=str(self.ints[a[1]])
    elif op=='Float':extra=str(self.floats[a[1]])
    elif op in ('String','Bytes'):extra=repr(self.strings[a[1]])[:150]
    elif op.startswith('Call') and op not in ('CallMethod','CallThis','CallClosure') or op in ('StaticClosure','InstanceClosure'):extra=self.names.get(a[1],str(a[1]))
    elif op=='CallMethod':extra=str(self.proto(regs[a[2]]).get(a[1]))
    elif op=='CallThis':extra=str(self.proto(regs[0]).get(a[1]))
    elif op in ('Field','SetField','GetThis','SetThis'):
     ri= a[1] if op=='Field' else a[0] if op=='SetField' else 0;fi=a[2] if op=='Field' else a[1] if op!='SetThis' else a[0];extra=self.fields(regs[ri])[fi][0]
    elif op.startswith('J'):extra='->'+str(j+1+a[-1])
   except (IndexError,KeyError):pass
   d=fn['debug'][j] if fn['debug'] else (-1,0);print(f'{j:4} {d[1]:4} {off:7x} {op:16} {str(a):28} {extra}')
if __name__=='__main__':
 h=HL(sys.argv[1]);import re
 for f,fn in h.funcs.items():
  file=h.files[fn['debug'][0][0]] if fn['debug'] else ''
  if re.search(sys.argv[2], h.names.get(f,'')+' '+file,re.I):
   if len(sys.argv)>3:h.detail(f)
   else:print(f,h.names.get(f),file,fn['debug'][0][1],len(fn['ops']))
