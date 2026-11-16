"""Integration tests against a user-supplied supported game installation (copies only)."""
import sys, tempfile, shutil
from itertools import combinations
from pathlib import Path
from unittest.mock import patch
import patch_engine as p

def run(source):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); names=list(p.manifest())
        for name in names: shutil.copy2(source/name,root/name)
        orig={n:(root/n).read_bytes() for n in names}
        assert all(s['state']=='' for s in p.inspect(root))
        # Upgrade from an existing two-patch installation; visit every combination.
        selections=[{'shooter','dragon'}]+[set(c) for n in range(1,len(p.PATCH_INFO)+1) for c in combinations(sorted(p.PATCH_INFO),n)]+[set()]
        for selected in selections:
            states=p.apply(root,selected)
            assert all(s['state']==p.key(selected) and s['backup'] for s in states)
            for n in names:
                assert (root/n).read_bytes()==p.transform(orig[n],p.manifest()[n],selected)
        assert all((root/n).read_bytes()==orig[n] for n in names)
        target=root/names[0]; target.write_bytes(orig[names[0]]+b'!')
        try: p.apply(root,{'shooter'}); raise AssertionError('Unknown build accepted')
        except p.PatchError: pass
        assert target.read_bytes()==orig[names[0]]+b'!'
        target.write_bytes(orig[names[0]])
        backup=root/'.evoland-toolkit'/names[0]; backup.write_bytes(b'bad')
        try: p.apply(root,{'dragon'}); raise AssertionError('Invalid backup accepted')
        except p.PatchError: pass
        backup.write_bytes(orig[names[0]])
        write=p.atomic_write
        def fail_second(path,data,mode=None):
            if path==root/names[1]: raise OSError('simulated failure')
            return write(path,data,mode)
        with patch.object(p,'atomic_write',side_effect=fail_second):
            try: p.apply(root,{'shooter'}); raise AssertionError('Expected simulated failure')
            except p.PatchError as e: assert 'rolled back' in str(e)
        assert all((root/n).read_bytes()==orig[n] for n in names)
    print('PASS: both builds, all patch combinations, exact restore, unknown hash refusal, backup corruption refusal, rollback')

if __name__=='__main__': run(Path(sys.argv[1]))
