"""Exercise the *emitted* frame-limiter opcodes against a deterministic clock.
No actual game runtime; run locally with original supported boot files.
"""
import math, sys
from pathlib import Path
from patch_recipes import HL, KNOWN, fps60, recipe_edits, apply_edits, validate, fid


def simulate(h, render_seconds, sleep_quantum, frames=100, backwards=False):
    """Minimal interpreter of the patched outer loop, substituting only natives
    and the original engine calls. Captures start intervals and sleep requests.
    """
    f=fid(h,'hxd.$System.runMainLoop'); ops=h.funcs[f]['ops']; r=[0]*len(h.funcs[f]['regs']); pc=0; now=10.; starts=[]; sleeps=[]; ticks=0
    for _ in range(5000000):
        op,a,_=ops[pc];pc+=1
        if op=='StaticClosure':r[a[0]]=a[1]
        elif op=='Float':r[a[0]]=h.floats[a[1]]
        elif op=='Int':r[a[0]]=h.ints[a[1]]
        elif op=='Bool':r[a[0]]=bool(a[1])
        elif op=='Mov':r[a[0]]=r[a[1]]
        elif op=='Incr':r[a[0]]+=1
        elif op in ('Add','Sub'):r[a[0]]=r[a[1]]+r[a[2]] if op=='Add' else r[a[1]]-r[a[2]]
        elif op in ('Label','Trap','EndTrap'):pass
        elif op in ('Call0','Call1'):
            name=h.names[a[1]]
            if name=='std.sys_time':
                now+=.000002;r[a[0]]=now
            elif name=='std.sys_sleep':
                request=r[a[2]];assert 0<=request<=1/60;sleeps.append(request)
                now+=math.ceil(request/sleep_quantum)*sleep_quantum if request>0 else .00005
            elif name=='haxe.$MainLoop.tick':starts.append(now);ticks+=1;r[a[0]]=0
            elif name=='hxd.$System.mainLoop':
                r[a[0]]=ticks<frames
                now+=render_seconds
                if backwards and ticks==1:now-=.1
            elif name=='std.set_error_handler':pass
            elif name=='std.sys_exit':return starts,sleeps
            else:raise AssertionError(name)
        elif op=='JAlways':pc+=a[-1]
        elif op in ('JTrue','JFalse'):
            if bool(r[a[0]])==(op=='JTrue'):pc+=a[-1]
        elif op in ('JSLt','JSGte','JNotLt'):
            x,y=r[a[0]],r[a[1]];cond=x<y if op=='JSLt' else x>=y
            if cond:pc+=a[-1]
        else:raise AssertionError((pc,op,a))
    raise AssertionError('Loop did not exit')


def run(folder):
    for filename in KNOWN:
        original=HL(folder/filename);functions=fps60(original)
        h=validate(original,apply_edits(original.b,recipe_edits(functions)),functions)
        for render,quantum in [(0.001,0.001),(.004,0.0001),(.010,.015625),(.001,.015625),(.033,.001)]:
            starts,sleeps=simulate(h,render,quantum)
            intervals=[b-a for a,b in zip(starts,starts[1:])]
            assert len(starts)==100 and min(intervals)>=1/60-1e-8,(filename,render,quantum,min(intervals))
            assert max(intervals[-20:]) <= max(render,1/60)+.0002,(filename,render,quantum,max(intervals[-20:]))
            if render>1/60:assert not sleeps
            else:assert sleeps
            print(filename, 'render',render, 'sleep quantum',quantum, 'steady fps', round(20/sum(intervals[-20:]),3))
        starts,_=simulate(h,.001,.001,frames=3,backwards=True);assert len(starts)==3
    print('PASS: emitted pacing opcodes, fast/slow rendering, fine/coarse OS sleeps, backwards clock and normal exit')

if __name__=='__main__':run(Path(sys.argv[1]))
