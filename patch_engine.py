"""Hash-gated, reversible local patch application. No game data is bundled."""
from pathlib import Path
import hashlib,json,os,stat,tempfile,datetime
ROOT=Path(__file__).resolve().parent
PATCH_INFO={
 'shooter':('001 · Shooter softlock','Correct horizontal formation boundaries using actual frame movement. Remove regular enemies after three continuous offscreen seconds, once their entrance is finished. Bosses and rebosses are excluded from cleanup.'),
 'dragon':('002 · Future Trunkodile wake-up','Experimental watchdog: if the 3D wake animation fails to start movement within two seconds, run the original movement callback. Normal Fina attacks, obstacles and puzzle rules are unchanged. Does not repair trapped coordinates.'),
 'mushroom':('003 · Windy Caves mushroom jumps','Experimental: use smaller physics steps in the future cave, limit mushroom thrust to its exact duration and stabilize held-jump height with a small clearance margin. Other maps are unchanged.'),
 'fps60':('004 · 60 FPS frame limiter','Cap the engine loop at 60 FPS using real elapsed time, without relying on VSync or GPU drivers. Aims to prevent high-FPS timing bugs across the game; slower frames are not sped up. Experimental.')}
class PatchError(RuntimeError):pass

def sha(data):return hashlib.sha256(data).hexdigest()

def manifest():return json.loads((ROOT/'patch_manifest.json').read_text(encoding='utf8'))['builds']

def key(patches):
    if not set(patches)<=set(PATCH_INFO):raise PatchError('Unknown patch selection.')
    return ','.join(sorted(patches))

def transform(original,record,patches):
    if sha(original)!=record['original']:raise PatchError('Original game file hash does not match.')
    k=key(patches);edits=[(a,b,bytes.fromhex(c)) for p in patches for a,b,c in record['patches'][p]];result=bytearray();pos=0
    for off,length,data in sorted(edits):
        if off<pos or off+length>len(original):raise PatchError('Invalid patch edit range.')
        result+=original[pos:off]+data;pos=off+length
    result+=original[pos:];result=bytes(result)
    if sha(result)!=record['outputs'][k]:raise PatchError('Patched output did not match expected SHA-256.')
    return result

def atomic_write(path,data,mode=None):
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if mode is not None:os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def inspect(folder):
    folder=Path(folder).expanduser().resolve();result=[]
    for name,record in manifest().items():
        path=folder/name
        if not path.exists():continue
        if path.is_symlink() or not path.is_file():raise PatchError(f'{name} must be a regular file, not a link.')
        digest=sha(path.read_bytes());state=next((k for k,v in record['outputs'].items() if v==digest),None)
        backup=folder/'.evoland-toolkit'/name
        backup_ok=backup.is_file() and not backup.is_symlink() and sha(backup.read_bytes())==record['original']
        result.append(dict(name=name,state=state,digest=digest,backup=backup_ok))
    if not result:raise PatchError('No hlboot.dat or sdlboot.dat found. Select the game installation folder, not the save folder.')
    return result

def apply(folder,patches):
    folder=Path(folder).expanduser().resolve();patches=set(patches);k=key(patches);records=manifest();states=inspect(folder);backup_dir=folder/'.evoland-toolkit'
    if backup_dir.is_symlink():raise PatchError('Backup folder must not be a symbolic link.')
    plans=[]
    for s in states:
        name=s['name'];path=folder/name;record=records[name];before=path.read_bytes()
        if s['state'] is None or sha(before)!=s['digest']:raise PatchError(f'{name} has an unknown or changed hash. Nothing was modified.')
        backup=backup_dir/name
        if backup.exists():
            if not s['backup']:raise PatchError(f'{name} backup is invalid. Nothing was modified.')
            original=backup.read_bytes()
        elif s['state']=='':original=before
        else:raise PatchError(f'{name} is patched but its verified original backup is missing. Nothing was modified.')
        after=transform(original,record,patches);plans.append((path,before,after,original,backup,path.stat().st_mode))
    if all(before==after for _,before,after,_,_,_ in plans):return inspect(folder)
    backup_dir.mkdir(exist_ok=True)
    # All originals must be verified and backed up before the first game write.
    for path,before,after,original,backup,mode in plans:
        if not backup.exists():atomic_write(backup,original,mode)
        if sha(backup.read_bytes())!=records[path.name]['original']:raise PatchError('Backup validation failed; no game files modified.')
    completed=[]
    try:
        for path,before,after,original,backup,mode in plans:
            if path.read_bytes()!=before:raise PatchError(f'{path.name} changed externally during patching.')
            if before==after:continue
            atomic_write(path,after,mode);completed.append((path,before,after,mode))
            if sha(path.read_bytes())!=records[path.name]['outputs'][k]:raise PatchError('Output verification failed.')
    except Exception as e:
        failures=[]
        for path,before,after,mode in reversed(completed):
            try:
                if path.read_bytes()!=after:raise PatchError('File changed during rollback; backup retained.')
                atomic_write(path,before,mode)
            except Exception as rollback:failures.append(f'{path.name}: {rollback}')
        raise PatchError(f'Patch failed: {e}. '+('Rollback incomplete: '+'; '.join(failures) if failures else 'All completed writes rolled back.')) from e
    try:
        with (backup_dir/'patch.log').open('a',encoding='utf8') as log:log.write(f'{datetime.datetime.now(datetime.timezone.utc).isoformat()} {k or "restore originals"}: '+', '.join(p.name+' '+sha(a) for p,_,a,_,_,_ in plans)+'\n')
    except OSError:pass  # Log failure must not invalidate successful verified writes.
    return inspect(folder)
