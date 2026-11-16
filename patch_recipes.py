"""Developer-only recipe generator for known HashLink v4 builds.
Reads local game bytecode; emits only targeted instruction edits, never a game file.
"""
import hashlib, json, sys
from itertools import combinations
from pathlib import Path
from hlbytecode import HL, OPS

OP = {x[:-1]: i for i,x in enumerate(OPS)}

def index(n):
    if 0 <= n < 128: return bytes([n])
    a=abs(n); sign=32 if n<0 else 0
    if a < 8192: return bytes([128|sign|(a>>8), a&255])
    if a < 1<<29: return bytes([192|sign|(a>>24),(a>>16)&255,(a>>8)&255,a&255])
    raise ValueError('Index out of range')

def encode(op,args):
    b=bytes([OP[op]])
    if OPS[OP[op]][-1]=='*' and op!='Switch':
        return b+index(args[0])+index(args[1])+bytes([len(args)-2])+b''.join(map(index,args[2:]))
    return b+b''.join(map(index,args))

def digest(b):return hashlib.sha256(b).hexdigest()

def apply_edits(data,edits):
    out=bytearray(); p=0
    for off,length,new in sorted(edits,key=lambda x:x[0]):
        if not p<=off<=len(data) or off+length>len(data):raise ValueError('Overlapping/out-of-range edits')
        out+=data[p:off];out+=new;p=off+length
    out+=data[p:];return bytes(out)

class Function:
    def __init__(self,h,f):
        self.h=h;self.f=f;self.fn=h.funcs[f];self.ops=[(op,list(a)) for op,a,_ in self.fn['ops']];self.n=len(self.ops);self.regs=list(self.fn['regs']);self.changed=set();self.labels={};self.pending=[];self.hooks={}
    def expect(self,i,op,args=None):
        actual=self.ops[i]
        if actual[0]!=op or args is not None and actual[1]!=args:raise ValueError(f'Unexpected opcode f{self.f}:{i}: {actual}')
    def set(self,i,op,*args):self.ops[i]=(op,list(args));self.changed.add(i)
    def emit(self,op,*args):self.ops.append((op,list(args)));return len(self.ops)-1
    def label(self,n):self.labels[n]=len(self.ops)
    def branch(self,op,*args,to):
        i=self.emit(op,*args,0);self.pending.append((i,to))
    def hook(self,i):
        self.hooks[i]=len(self.ops)
    def edits(self):
        for i,to in self.pending:
            target=self.labels[to] if isinstance(to,str) else to
            self.ops[i][1][-1]=target-i-1
        fn=self.fn;h=self.h;source_ops=self.ops
        # Inline new blocks at their hooks. Relocate EVERY jump/switch offset,
        # including old loop backedges, without introducing new backward edges.
        starts=sorted(self.hooks.values())+[len(source_ops)]
        groups={i:list(range(self.hooks[i],starts[starts.index(self.hooks[i])+1])) if i in self.hooks else [i] for i in range(self.n)}
        mapping={};order=[];debug=[]
        for i,group in groups.items():
            mapping[i]=len(order)
            for old in group:
                mapping[old]=len(order);order.append(old);debug.append(fn['debug'][i] if fn['debug'] else (-1,0))
        mapping[len(source_ops)]=len(order)
        if self.n not in mapping:mapping[self.n]=len(order)
        newops=[]
        for pos,old in enumerate(order):
            op,a=source_ops[old];a=list(a)
            jump_indexes=[len(a)-1] if op.startswith('J') or op=='Trap' else list(range(2,len(a))) if op=='Switch' else []
            for j in jump_indexes:
                target=old+1+a[j]
                if target==self.n and old<self.n: newtarget=len(order)
                else:newtarget=mapping[target]
                a[j]=newtarget-pos-1
            newops.append((op,a))
        # Existing and new jumps into a loop must target Label for the JIT.
        for pos,(op,a) in enumerate(newops):
            if op.startswith('J') and a[-1]<0:
                assert newops[pos+1+a[-1]][0]=='Label',(self.f,pos,op,a)
        self.ops=newops;self.debug=debug
        p=h.p;h.p=fn['start'];positions=[]
        for _ in range(4):
            a=h.p;v=h.idx();positions.append((a,h.p,v))
        rstart=h.p
        for _ in fn['regs']:h.idx()
        rend=h.p;h.p=p
        out=[]
        if len(self.regs)!=len(fn['regs']):a,b,_=positions[2];out.append((a,b-a,index(len(self.regs))))
        if len(self.ops)!=self.n:a,b,_=positions[3];out.append((a,b-a,index(len(self.ops))))
        if self.regs!=fn['regs']:out.append((rstart,rend-rstart,b''.join(map(index,self.regs))))
        for i,group in groups.items():
            a=fn['ops'][i][2];b=fn['ops'][i+1][2] if i+1<self.n else fn['ops_end'];new=b''.join(encode(*self.ops[mapping[j]]) for j in group)
            if new!=h.b[a:b]:out.append((a,b-a,new))
        self.assign=list(fn['assign'])
        if h.flags&1 and len(self.ops)!=self.n:
            db=bytearray();lastfile=-1;lastline=0;i=0
            while i<len(debug):
                fi,line=debug[i]
                if fi!=lastfile:
                    db+=bytes([((fi>>8)<<1)|1,fi&255]);lastfile=fi
                if line==lastline:
                    count=1
                    while count<15 and i+count<len(debug) and debug[i+count]==(fi,line):count+=1
                    db.append((count<<2)|2);i+=count;continue
                delta=line-lastline
                if 0<=delta<=31:db.append((delta<<3)|4)
                else:db+=bytes([(line&31)<<3,(line>>5)&255,(line>>13)&255])
                lastline=line;i+=1
            out.append((fn['ops_end'],fn['debug_end']-fn['ops_end'],bytes(db)))
            # Assignment positions are instruction boundaries (0 for args, -1 for captures).
            self.assign=[];p=h.p;h.p=fn['debug_end'];n=h.idx()
            for _ in range(n):
                name=h.idx();a=h.p;old=h.idx();b=h.p;new=(mapping[old] if old<self.n else len(order)) if old>0 else old
                self.assign.append((h.strings[name],new))
                if new!=old:out.append((a,b-a,index(new)))
            h.p=p
        return out

def fid(h,name):
    fs=[f for f,n in h.names.items() if n==name]
    if len(fs)!=1:raise ValueError(f'Function lookup failed: {name}, {fs}')
    return fs[0]

def field(h,ty,name):return next(i for i,(n,t) in enumerate(h.fields(ty)) if n==name)
def typ(h,name):return next(i for i,t in enumerate(h.types) if t.get('name')==name and t['k']==11)
def fl(h,value):return h.floats.index(value)
def it(h,value):return h.ints.index(value)

def shooter(h):
    move=Function(h,fid(h,'map.ShootLevel3d.updateMove'));move.expect(0,'InstanceClosure');move.expect(35,'CallClosure',[12,3,6,13]);move.expect(101,'SetField',[19,0,16]);border=Function(h,move.ops[0][1][1]);
    # Predict the actual target movement, not the lagging sprite position.
    for i in (14,21):border.expect(i,'Field',[9,5,8]);border.set(i,'Field',9,5,38)
    for i in (16,23):border.expect(i,'Field',[8,9,12]);border.set(i,'Field',8,9,0)
    for i in (15,22):border.expect(i,'NullCheck',[9]);border.set(i,'JNull',9,29-i-1)
    border.regs[9]=typ(h,'h3d.col.Point')
    move.hook(35);move.emit('Mul',22,13,1);move.emit('CallClosure',12,3,6,22);move.branch('JAlways',to=36)
    # Clamp the final formation target after either direction reversal, avoiding drift.
    move.hook(101);move.emit('Call1',22,fid(h,'map.ShootLevel3d.minX'),0);move.branch('JNotLt',16,22,to='upper');move.emit('Mov',16,22);move.label('upper');move.emit('Call1',22,fid(h,'map.ShootLevel3d.maxX'),0);move.branch('JNotLt',22,16,to='store');move.emit('Mov',16,22);move.label('store');move.emit('SetField',19,0,16);move.branch('JAlways',to=102)
    # Three continuous seconds offscreen after entry. In 3D formation mobs patrolSleep
    # has no patrol behavior: it is initialized to zero and otherwise only decremented.
    # We repurpose it exclusively for 3D mobs, leaving 2D patrols alone.
    u=Function(h,fid(h,'ent.s.Mob.update'));u.expect(16,'Ret',[3]);u.regs.extend([7,3,typ(h,'h3d.col.Point'),h.fields(u.regs[0])[36][1],6,3]);b,life,target,state,threshold,enum=range(4,10)
    u.hook(16);u.emit('GetThis',b,14);u.branch('JFalse',b,to='return');u.emit('GetThis',b,37);u.branch('JTrue',b,to='return');u.emit('GetThis',b,52);u.branch('JTrue',b,to='return');u.emit('GetThis',life,21);u.emit('Int',enum,it(h,0));u.branch('JSGte',enum,life,to='return')
    u.emit('GetThis',b,12);u.branch('JTrue',b,to='reset');u.emit('GetThis',target,38);u.branch('JNull',target,to='reset');u.emit('GetThis',state,36);u.branch('JNull',state,to='reset');u.emit('EnumIndex',enum,state);u.emit('Int',life,it(h,7));u.branch('JEq',enum,life,to='reset');u.emit('Int',life,it(h,5));u.branch('JEq',enum,life,to='return')
    u.emit('Call1',b,fid(h,'ent.s.Mob.outOfScreen'),0);u.branch('JFalse',b,to='reset');u.emit('GetThis',2,42);u.emit('Float',threshold,fl(h,0.0));u.branch('JNotGte',threshold,2,to='return');u.emit('Call1',3,fid(h,'ent.s.Mob.remove'),0);u.branch('JAlways',to='return')
    u.label('reset');u.emit('Float',2,fl(h,180.0));u.emit('SetThis',42,2);u.label('return');u.emit('Ret',3)
    return [border,move,u]

def dragon(h):
    hit=Function(h,fid(h,'ent.z.sylves.SDragon.hurt'));hit.expect(37,'GetGlobal');hit.expect(39,'InstanceClosure',[22,hit.ops[39][1][1],0]);cb=Function(h,hit.ops[39][1][1]);cb.expect(0,'NullCheck',[0]);cb.expect(18,'GetGlobal');run=cb.ops[18][1][1]
    # Reset the watchdog on a new 3D wake, without changing attack eligibility.
    original=hit.ops[37];hit.hook(37);hit.emit('Float',26,fl(h,0.0));hit.emit('SetThis',51,26);hit.emit(*original[:1],*original[1]);hit.branch('JAlways',to=38)
    # Make the wake callback idempotent, including if the animation eventually finishes.
    cb.regs.extend([7,cb.regs[7]]);cb.hook(0);cb.emit('NullCheck',0);cb.emit('Field',12,0,50);cb.branch('JFalse',12,to='return');cb.emit('Field',13,0,37);cb.emit('GetGlobal',7,run);cb.branch('JEq',13,7,to='return');cb.branch('JAlways',to=1);cb.label('return');cb.emit('Ret',1)
    # A two-second watchdog on the existing moveSpeed accumulator ONLY while waiting
    # for wakeup, before the normal Run movement begins. The original callback resets it.
    u=Function(h,fid(h,'ent.z.sylves.SDragon.updateState'));u.expect(0,'Mov',[2,0]);u.hook(0)
    u.emit('GetThis',34,14);u.branch('JFalse',34,to='continue');u.emit('GetThis',34,50);u.branch('JFalse',34,to='continue');u.emit('GetThis',5,37)
    u.regs.append(u.regs[5]);u.emit('GetGlobal',56,run);u.branch('JEq',5,56,to='continue');u.emit('GetThis',7,51);u.emit('Add',7,7,1);u.emit('SetThis',51,7);u.emit('Float',8,fl(h,120.0));u.branch('JNotGte',7,8,to='continue');u.emit('Call1',3,cb.f,0)
    u.label('continue');u.emit('Mov',2,0);u.branch('JAlways',to=1)
    return [hit,cb,u]

def mushroom(h):
    # Only the future Windy Caves: cap the existing adaptive entity simulation
    # at a nominal 60 Hz step rather than introducing a second simulation loop.
    cave=next(g for g,fields in h.const if fields[0]==h.strings.index('WindvalleyClimb') and h.typename(h.globals[g])=='String')
    game=Function(h,fid(h,'Game.update'))
    game.expect(87,'Add',[8,8,21]);game.expect(88,'JNotLt',[8,7,2])
    game.regs.extend([13,13,89,3,3]);level,other,era,num,future=range(41,46)
    game.hook(87);game.emit('Field',level,4,1);game.emit('GetGlobal',other,cave);game.branch('JNotEq',level,other,to='original')
    game.emit('Field',era,4,2);game.branch('JNull',era,to='original');game.emit('SafeCast',num,era);game.emit('Int',future,it(h,2));game.branch('JNotEq',num,future,to='original')
    game.branch('JAlways',to=88);game.label('original');game.emit('Add',8,8,21);game.branch('JAlways',to=88)
    # Clip the mushroom thrust window to exactly eight frames. Stabilize the
    # held-jump cap at -0.367, inside the original dt=1..2 range; the slight
    # clearance margin is intentional. Regular jumps keep the original cap.
    hero=Function(h,fid(h,'ent.p.Hero.updateState'))
    hero.expect(768,'GetThis',[45,46]);hero.expect(775,'Mul',[44,44,1]);hero.expect(810,'Mul',[52,52,1]);hero.expect(850,'Field',[43,0,48])
    hero.regs.extend([7,hero.regs[17],hero.regs[16],13,13,6,6,89,3,3]);scope,g,st,l,other,remaining,temp,era,num,future=range(68,78)
    hero.hook(768);hero.emit('Bool',scope,0);hero.emit('GetThis',45,46);hero.branch('JFalse',45,to='done');hero.emit('GetThis',45,14);hero.branch('JFalse',45,to='done');hero.emit('GetThis',g,0);hero.branch('JNull',g,to='done');hero.emit('Field',st,g,8);hero.branch('JNull',st,to='done');hero.emit('Field',l,st,1);hero.emit('GetGlobal',other,cave);hero.branch('JNotEq',l,other,to='done');hero.emit('Field',era,st,2);hero.branch('JNull',era,to='done');hero.emit('SafeCast',num,era);hero.emit('Int',future,it(h,2));hero.branch('JNotEq',num,future,to='done');hero.emit('Bool',scope,1);hero.label('done');hero.emit('GetThis',45,46);hero.branch('JAlways',to=769)
    hero.hook(775);hero.branch('JFalse',scope,to='stockboost');hero.emit('Float',remaining,fl(h,8.0));hero.emit('GetThis',temp,48);hero.emit('Sub',remaining,remaining,temp);hero.branch('JNotLt',remaining,1,to='stockboost');hero.emit('Mul',44,44,remaining);hero.branch('JAlways',to=776);hero.label('stockboost');hero.emit('Mul',44,44,1);hero.branch('JAlways',to=776)
    hero.hook(810);hero.branch('JFalse',scope,to='stockcap');hero.emit('Float',52,fl(h,0.017));hero.branch('JAlways',to=811);hero.label('stockcap');hero.emit('Mul',52,52,1);hero.branch('JAlways',to=811)
    return [game,hero]

def native_sleep(h):
    """Use existing std.sys_sleep or append its standard v4 runtime import.

    HashLink 1.8 exports sys_sleep(double)->void on Windows and POSIX.
    Append, never renumber existing strings/functions. All edits use original offsets.
    """
    existing=[f for f in h.natives if h.names[f]=='std.sys_sleep']
    if existing:
        assert len(existing)==1 and h.types[h.natives[existing[0]]]=={'k':10,'args':[6],'ret':0}
        return existing[0],[]
    import struct
    oldpos=h.p;h.p=4
    positions=[]
    for _ in range(10):
        start=h.p;value=h.idx();positions.append((start,h.p,value))
    _,ni,nf,ns,nt,ng,nn,nfn,nc,entry=[x[2] for x in positions]
    h.p+=ni*4+nf*8
    sizepos=h.p;size=struct.unpack('<I',h.take(4))[0];h.p+=size;dataend=h.p
    for _ in range(ns):h.idx()
    lengthend=h.p;h.p=oldpos
    newname=b'sys_sleep';f=max(h.natives.keys()|h.funcs.keys())+1
    assert f==nn+nfn and len(h.strings)==ns and 'sys_sleep' not in h.strings
    ty=next(i for i,t in enumerate(h.types) if t=={'k':10,'args':[6],'ret':0})
    native= b''.join(index(x) for x in (h.strings.index('std'),ns,ty,f))
    edits=[]
    for i in (3,6):
        a,b,v=positions[i];edits.append((a,b-a,index(v+1)))
    edits.extend([(sizepos,4,struct.pack('<I',size+len(newname)+1)),
                  (dataend,0,newname+b'\0'),(lengthend,0,index(len(newname))),
                  (min(fn['start'] for fn in h.funcs.values()),0,native)])
    return f,edits


def fps60(h):
    """Pace the outer update+render loop, not the simulation clock.

    Sleep most of the remaining frame budget; yield/recheck near the deadline.
    Learn coarse OS sleep overshoot so later frames avoid unnecessary long sleeps.
    Slow frames never wait or trigger catch-up frames. The timer remains untouched.
    """
    loop=Function(h,fid(h,'hxd.$System.runMainLoop'))
    sleep,extra=native_sleep(h)
    clock=fid(h,'std.sys_time')
    assert h.types[h.natives[clock]]=={'k':10,'args':[],'ret':6}
    loop.expect(0,'StaticClosure');loop.expect(6,'Call0',[5,fid(h,'haxe.$MainLoop.tick')]);loop.expect(7,'Call0',[2,fid(h,'hxd.$System.mainLoop')]);loop.expect(11,'EndTrap',[1]);loop.expect(12,'JAlways',[4])
    # guard, period, start, now, remaining, request, after, overshoot, one_ms, zero
    guard,period,start,now,remaining,request,after,over,ms,zero,count,limit=range(len(loop.regs),len(loop.regs)+12)
    loop.regs.extend([6]*10+[3,3])
    loop.hook(0);loop.emit('StaticClosure',*loop.ops[0][1]);loop.emit('Float',guard,fl(h,0.002));loop.emit('Float',period,fl(h,1/60));loop.emit('Float',ms,fl(h,0.001));loop.emit('Float',zero,fl(h,0.0));loop.emit('Int',limit,it(h,1000000));loop.branch('JAlways',to=1)
    loop.hook(6);loop.emit('Call0',start,clock);loop.emit('Call0',*loop.ops[6][1]);loop.branch('JAlways',to=7)
    # Successful frame only, after the original exception trap has ended.
    loop.hook(12);loop.emit('Int',count,it(h,0));loop.label('wait');loop.emit('Label');loop.emit('Incr',count);loop.branch('JSGte',count,limit,to='done');loop.emit('Call0',now,clock)
    loop.branch('JSLt',now,start,to='done');loop.emit('Sub',remaining,now,start);loop.emit('Sub',remaining,period,remaining);loop.branch('JNotLt',zero,remaining,to='done')
    loop.emit('Sub',request,remaining,guard);loop.branch('JSLt',request,ms,to='yield')
    loop.emit('Call1',1,sleep,request);loop.emit('Call0',after,clock);loop.branch('JSLt',after,now,to='done');loop.emit('Sub',over,after,now);loop.emit('Sub',over,over,request);loop.emit('Add',over,over,ms)
    loop.branch('JNotLt',guard,over,to='wait');loop.branch('JSLt',over,period,to='learn');loop.emit('Mov',over,period);loop.label('learn');loop.emit('Mov',guard,over);loop.branch('JAlways',to='wait')
    loop.label('yield');loop.emit('Call1',1,sleep,zero);loop.branch('JAlways',to='wait')
    loop.label('done');loop.branch('JAlways',to=17)
    loop.extra_edits=extra
    return [loop]


def recipe_edits(functions):
    return [e for f in functions for e in f.edits()+getattr(f,'extra_edits',[])]

PATCHES={'shooter':shooter,'dragon':dragon,'mushroom':mushroom,'fps60':fps60}
KNOWN={'hlboot.dat':'8d075d40eb189577afb542298b12e87c93b943d58046148e401008235a9c565d','sdlboot.dat':'fc78de84a96997f93d3c39ab335bc6435dcdbf5da76a7588d9c79274b9ba12ae'}

def validate(h,modified,functions):
    new=HL(modified)
    assert len(new.funcs)==len(h.funcs) and new.types==h.types and new.const==h.const
    assert new.globals==h.globals and new.ints==h.ints and new.floats==h.floats and new.files==h.files
    assert all(new.natives.get(f)==t and new.names[f]==h.names[f] for f,t in h.natives.items())
    if any(getattr(f,'extra_edits',[]) for f in functions):
        assert new.strings==h.strings+['sys_sleep'] and len(new.natives)==len(h.natives)+1
        f=max(new.natives);assert new.names[f]=='std.sys_sleep' and new.types[new.natives[f]]=={'k':10,'args':[6],'ret':0}
    else:assert new.strings==h.strings and new.natives==h.natives
    edited={f.f:f for f in functions}
    for f,fn in h.funcs.items():
        other=new.funcs[f]
        if f not in edited:
            assert h.b[fn['start']:fn['end']]==new.b[other['start']:other['end']],f
            continue
        expected=edited[f];assert other['regs']==expected.regs and [(o,a) for o,a,_ in other['ops']]==expected.ops
        assert other['debug']==expected.debug and other['assign']==expected.assign
        for i,(op,a,_) in enumerate(other['ops']):
            if op.startswith('J'):assert 0<=i+1+a[-1]<len(other['ops']),(f,i,op,a)
    return new

def generate(folder):
    result={'format':1,'builds':{}}
    for filename,expected in KNOWN.items():
        h=HL(Path(folder)/filename);assert digest(h.b)==expected
        record={'original':expected,'patches':{},'outputs':{}}
        for key,fn in PATCHES.items():
            funcs=fn(h);edits=recipe_edits(funcs);data=apply_edits(h.b,edits);validate(h,data,funcs);record['patches'][key]=[[a,b,c.hex()] for a,b,c in edits];record['outputs'][key]=digest(data);print(filename,key,len(edits),'edits',len(data)-len(h.b),'added bytes',digest(data))
        for count in range(2,len(PATCHES)+1):
            for selection in combinations(sorted(PATCHES),count):
                funcs=[f for key in selection for f in PATCHES[key](h)]
                assert len({f.f for f in funcs})==len(funcs), 'Patch function overlap'
                edits=recipe_edits(funcs);data=apply_edits(h.b,edits);validate(h,data,funcs)
                record['outputs'][','.join(selection)]=digest(data)
        record['outputs']['']=expected;result['builds'][filename]=record
    return result
if __name__=='__main__':
    root=Path(__file__).resolve().parent; result=generate(sys.argv[1]);(root/'patch_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
