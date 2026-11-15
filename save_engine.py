"""Evoland 2 Haxe save parser and byte-preserving editor (stdlib only)."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote
import hashlib, re, os, tempfile, shutil
from datetime import datetime

class SaveError(ValueError): pass
@dataclass
class Node:
    start: int
    end: int
    value: object
    tag: str

class Parser:
    def __init__(self, text):
        self.s=text; self.p=0; self.strings=[]; self.objects=[]; self.nodes=[]
    def fail(self, msg): raise SaveError(f'{msg} at offset {self.p}')
    def take(self):
        if self.p>=len(self.s): self.fail('Unexpected end')
        c=self.s[self.p]; self.p+=1; return c
    def expect(self,c):
        if self.take()!=c: self.fail(f'Expected {c!r}')
    def num(self, pattern=r'-?\d+'):
        m=re.match(pattern,self.s[self.p:])
        if not m: self.fail('Invalid number')
        self.p+=len(m[0]); return m[0]
    def obj(self, end):
        d={}
        while self.s[self.p]!=end:
            k=self.node().value
            if not isinstance(k,str): self.fail('Invalid object key')
            if k in d: self.fail('Duplicate object key')
            d[k]=self.node()
        self.p+=1; return d
    def node(self):
        start=self.p; t=self.take(); v=None
        if t=='y':
            n=int(self.num()); self.expect(':'); raw=self.s[self.p:self.p+n]
            if n<0 or len(raw)!=n: self.fail('Invalid string length')
            self.p+=n; v=unquote(raw,errors='strict'); self.strings.append(v)
        elif t=='R':
            i=int(self.num()); v=self.strings[i] if 0<=i<len(self.strings) else self.fail('Invalid string reference')
        elif t=='r':
            i=int(self.num()); v=self.objects[i] if 0<=i<len(self.objects) else self.fail('Invalid object reference')
        elif t=='i': v=int(self.num())
        elif t=='d': v=float(self.num(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'))
        elif t=='z': v=0
        elif t=='t': v=True
        elif t=='f': v=False
        elif t=='n': v=None
        elif t in 'kmp': v={'k':float('nan'),'m':float('-inf'),'p':float('inf')}[t]
        elif t in 'ocb':
            if t=='c': name=self.node().value
            self.objects.append(None); idx=len(self.objects)-1
            v=self.obj('h' if t=='b' else 'g'); self.objects[idx]=v
        elif t in 'al':
            v=[]; self.objects.append(v)
            while self.s[self.p]!='h':
                if self.s[self.p]=='u':
                    self.p+=1; n=int(self.num());
                    if not 0<=n<=1000000: self.fail('Invalid null count')
                    v.extend([None]*n)
                else: v.append(self.node())
            self.p+=1
        elif t=='q':
            v={}; self.objects.append(v)
            while self.s[self.p]!='h':
                self.expect(':'); k=int(self.num()); v[k]=self.node()
            self.p+=1
        elif t=='M':
            v=[]; self.objects.append(v)
            while self.s[self.p]!='h': v.append((self.node(),self.node()))
            self.p+=1
        elif t in 'wj':
            name=self.node().value
            if t=='w': ctor=self.node().value
            else: self.expect(':'); ctor=int(self.num())
            self.expect(':'); count=int(self.num()); v=(name,ctor,[self.node() for _ in range(count)]); self.objects.append(v)
        elif t=='s':
            n=int(self.num()); self.expect(':'); v=self.s[self.p:self.p+n]; self.p+=n; self.objects.append(v)
        elif t=='v': v=self.s[self.p:self.p+19]; self.p+=19; self.objects.append(v)
        elif t in 'AB': v=self.node().value
        else: self.fail(f'Unsupported Haxe token {t!r}')
        n=Node(start,self.p,v,t); self.nodes.append(n); return n
    def parse(self):
        try:
            n=self.node()
            if self.p!=len(self.s): self.fail('Unexpected trailing data')
            return n
        except (IndexError, RecursionError, UnicodeError) as e: raise SaveError(f'Malformed save at offset {self.p}') from e

def checksum(body):
    def sha(s): return hashlib.sha1(s.encode('utf-8')).hexdigest()
    return sha(body+sha(body+'s*al!t'))[4:36]

def unpack(text):
    if '#' not in text: raise SaveError('Missing save checksum')
    body,check=text.rsplit('#',1)
    if checksum(body)!=check: raise SaveError('Save checksum mismatch. Original file may be damaged or unsupported.')
    root=Parser(body).parse().value
    if not isinstance(root,dict) or 'data' not in root or 'game' not in root: raise SaveError('Unsupported save structure')
    if root['game'].value[:2] not in (('GameType','Evo1'),('GameType','Evo2')): raise SaveError('Unsupported game')
    return body,root['data'].value

FIELDS={'level':('level','level'),'attack':('level','attack'),'defense':('level','defense'),'max_hp':('level','life'),'hp':('life',),'xp':('level','xp'),'gold':('gold',)}
LIMITS={'level':(1,999),'attack':(0,99999),'defense':(0,99999),'max_hp':(1,99999),'hp':(0,99999),'xp':(0,2147483647),'gold':(0,2147483647)}
def field(state,path):
    for part in path[:-1]: state=state[part].value
    return state[path[-1]]
def stats(state): return {k:field(state,p).value for k,p in FIELDS.items()}
def positions(state):
    sylves=state.get('sylves')
    if not sylves or not isinstance(sylves.value,dict): return {}
    dr=sylves.value.get('dr')
    if not dr or not isinstance(dr.value,dict): return {}
    return {k:((n.value&65535)/4,(n.value>>16)/4) for k,n in dr.value.items() if type(n.value)==int and n.value>=0}
def replace(text,edits):
    for n,new in sorted(edits,key=lambda x:x[0].start,reverse=True): text=text[:n.start]+new+text[n.end:]
    return text

def encode_int(v): return 'z' if v==0 else 'i'+str(v)
def encode_string(v):
    raw=quote(v,safe="-_.!~*'()")
    return f'y{len(raw)}:{raw}'
def validate_values(values):
    for k,v in values.items():
        if k not in LIMITS or type(v)!=int or not LIMITS[k][0]<=v<=LIMITS[k][1]: raise SaveError(f'Invalid {k}: {v}')
def edit_state(text,state,values,coords,checkpoints,depth=0):
    if depth>100: raise SaveError('Too many nested checkpoints')
    edits=[]
    for k,v in values.items():
        n=field(state,FIELDS[k]);
        if n.tag not in ('i','z'): raise SaveError(f'Unexpected type for {k}')
        if n.value!=v: edits.append((n,encode_int(v)))
    newstats={**stats(state),**values}
    if newstats['hp']>newstats['max_hp']: raise SaveError('Current HP exceeds maximum HP (including a checkpoint if selected)')
    if coords:
        available=positions(state)
        for k,(x,y) in coords.items():
            if k not in available: raise SaveError(f'Unknown Trunkodile ID {k}')
            if not all(0<=v<=16383.75 and v*4==int(v*4) for v in (x,y)): raise SaveError('Coordinates must be nonnegative quarter-tile increments')
            n=state['sylves'].value['dr'].value[k]; packed=(int(y*4)<<16)|int(x*4)
            if packed>2147483647: raise SaveError('Position exceeds signed 32-bit range')
            if n.value!=packed: edits.append((n,encode_int(packed)))
    prev=state.get('prevSave')
    if checkpoints and prev and prev.value is not None:
        if prev.tag!='y': raise SaveError('Unexpected checkpoint encoding')
        sub=prev.value; substate=Parser(sub).parse().value
        modified=edit_state(sub,substate,values,{},True,depth+1)
        if modified!=sub: edits.append((prev,encode_string(modified)))
    return replace(text,edits)
def edit(text,values=None,coords=None,checkpoints=False):
    values=values or {}; validate_values(values)
    body,state=unpack(text)
    changed=edit_state(body,state,values,coords or {},checkpoints)
    result=changed+'#'+checksum(changed); unpack(result)
    return result

def load(path): return Path(path).read_bytes().decode('utf-8')
def write_save(path,text):
    unpack(text); path=Path(path); backup=None
    if path.exists():
        suffix=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup=path.with_name(path.name+'.'+suffix+'.bak'); shutil.copy2(path,backup)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(text.encode('utf-8')); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return backup

# General editing: rebuild only affected values and string-cache tokens. Object
# references are deliberately rejected for structural edits (not seen in samples).
def resolve(state,path):
    for key in path:
        n=state[key]
        state=n.value
    return n

def game_type(text):
    body,_=unpack(text)
    return Parser(body).parse().value['game'].value[1]

def plain(n):
    if n is None:return None
    v=n.value
    if isinstance(v,dict):return {k:plain(x) for k,x in v.items()}
    if isinstance(v,list):return [plain(x) for x in v]
    return v

def general_edit(text, changes):
    if not changes:return text
    body,_=unpack(text); p=Parser(body); root=p.parse(); state=root.value['data'].value
    targets={}
    for path,v in changes.items():
        if not path or path[0]=='prevSave':raise SaveError('Checkpoint payload is protected')
        n=resolve(state,path)
        if n.tag not in ('i','z','d','t','f','n','y','R','a','w'):raise SaveError('Unsupported editable type: '+n.tag)
        old=n.value
        if n.tag=='w' and (not isinstance(v,tuple) or len(v)!=3 or v[0]!=old[0] or old[2] or v[2]):raise SaveError('Unsupported enum replacement')
        if n.tag=='a':
            if not isinstance(v,list) or path not in [('inventory',),('equip',),('cards',),('items',)]:raise SaveError('Only supported collections can be replaced')
            if any(x.tag=='r' for x in p.nodes):raise SaveError('Structural edit refused: object references present')
        elif type(old)!=type(v) and not (type(old) in (int,float) and type(v) in (int,float)) and not (old is None and isinstance(v,str)):
            raise SaveError('Value type must match original')
        if type(v)==int and not -2147483648<=v<=2147483647:raise SaveError('Integer out of range')
        if n.tag=='a' and plain(n)==v or n.tag!='a' and old==v:continue
        targets[n.start]=(n.end,v)
    if not targets:return text
    spans=sorted((a,b) for a,(b,_) in targets.items())
    if any(b>c for (_,b),(c,_) in zip(spans,spans[1:])):raise SaveError('Overlapping edits')
    cache={}; count=0
    def string(v):
        nonlocal count
        if v in cache:return 'R'+str(cache[v])
        cache[v]=count; count+=1;return encode_string(v)
    def enc(v):
        if v is None:return 'n'
        if type(v)==bool:return 't' if v else 'f'
        if type(v)==int:return encode_int(v)
        if type(v)==float:
            import math
            if not math.isfinite(v):raise SaveError('Nonfinite number')
            return 'd'+repr(v)
        if isinstance(v,str):return string(v)
        if isinstance(v,tuple) and len(v)==3 and isinstance(v[0],str) and isinstance(v[1],str) and not v[2]:return 'w'+string(v[0])+string(v[1])+':0'
        if isinstance(v,list):return 'a'+''.join(enc(x) for x in v)+'h'
        if isinstance(v,dict):return 'o'+''.join(string(k)+enc(x) for k,x in v.items())+'g'
        raise SaveError('Unsupported replacement')
    events={n.start:(n.end,n.value) for n in p.nodes if n.tag in ('y','R')}; events.update(targets)
    out=[]; pos=0
    for a,(b,v) in sorted(events.items()):
        if a<pos:continue
        out.extend([body[pos:a],enc(v)]);pos=b
    out.append(body[pos:]); new=''.join(out); result=new+'#'+checksum(new)
    _,after=unpack(result)
    expected={k:plain(n) for k,n in state.items()}
    for path,v in changes.items():
        parent=expected
        for key in path[:-1]:parent=parent[key]
        parent[path[-1]]=v
    if expected!={k:plain(n) for k,n in after.items()}:raise SaveError('Round-trip verification failed: unexpected state change')
    return result
