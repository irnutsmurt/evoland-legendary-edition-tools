"""Read-only Legendary Edition installation discovery; no third-party packages."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile

APP_ID = '1020470'
GAME_NAME = 'Evoland Legendary Edition'


def config_path():
    base = os.environ.get('APPDATA') if sys.platform == 'win32' else os.environ.get('XDG_CONFIG_HOME')
    return (Path(base) if base else Path.home() / '.config') / 'EvolandToolkit' / 'installation.json'


def is_installation(folder):
    if not folder:
        return False
    try:
        p = Path(folder).expanduser()
        # Require the two game resource archives, not just a generic HashLink boot file.
        return all((p / name).is_file() for name in ('evo1.pak', 'evo2.pak'))
    except (OSError, ValueError):
        return False


def remembered_installation():
    try:
        p = json.loads(config_path().read_text(encoding='utf8')).get('installation')
        return Path(p).expanduser().resolve() if is_installation(p) else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def remember_installation(folder):
    if not is_installation(folder):
        raise ValueError('Choose the Legendary Edition folder containing evo1.pak and evo2.pak.')
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.installation-', dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as f:
            json.dump({'installation': str(Path(folder).expanduser().resolve())}, f)
        os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def registry_steam_roots():
    if sys.platform != 'win32':
        return []
    import winreg
    roots = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key in (r'Software\Valve\Steam', r'Software\WOW6432Node\Valve\Steam'):
            for view in (0, winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                try:
                    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as k:
                        for field in ('SteamPath', 'InstallPath'):
                            try:
                                value = winreg.QueryValueEx(k, field)[0]
                                if isinstance(value, str) and value:
                                    roots.append(Path(value))
                            except OSError:
                                pass
                except OSError:
                    pass
    return roots


def steam_roots():
    home = Path.home()
    roots = registry_steam_roots()
    if sys.platform == 'win32':
        for v in ('ProgramFiles(x86)', 'ProgramFiles', 'ProgramW6432'):
            if os.environ.get(v):
                roots.append(Path(os.environ[v]) / 'Steam')
    else:
        roots += [home / '.steam/steam', home / '.steam/root', home / '.local/share/Steam',
                  home / '.var/app/com.valvesoftware.Steam/.local/share/Steam',
                  home / 'snap/steam/common/.local/share/Steam']
        if os.environ.get('XDG_DATA_HOME'):
            roots.append(Path(os.environ['XDG_DATA_HOME']) / 'Steam')
    return roots


def vdf_strings(path):
    """Read quoted Valve KeyValues pairs; support both libraryfolders layouts."""
    try:
        text = path.read_text(encoding='utf-8-sig', errors='replace')
    except OSError:
        return []
    tokens = re.findall(r'//[^\n]*|"(?:\\.|[^"\\])*"|[{}]', text)
    pairs = []
    def decode(s):
        return re.sub(r'\\([\\"])', r'\1', s[1:-1])
    for a, b in zip(tokens, tokens[1:]):
        if a.startswith('"') and b.startswith('"'):
            pairs.append((decode(a), decode(b)))
    return pairs


def unique_paths(paths):
    seen = set()
    for path in paths:
        try:
            p = Path(path).expanduser().resolve()
            k = os.path.normcase(str(p))
            if k not in seen:
                seen.add(k)
                yield p
        except (OSError, RuntimeError, ValueError):
            continue


def steam_installations(roots=None):
    roots = list(steam_roots() if roots is None else roots)
    libraries = list(roots)
    for root in unique_paths(roots):
        for key, value in vdf_strings(root / 'steamapps/libraryfolders.vdf'):
            # Older files have numeric keys and absolute paths instead of path fields.
            if key.lower() == 'path' or (key.isdigit() and Path(value).is_absolute()):
                if Path(value).is_absolute():
                    libraries.append(Path(value))
    candidates = []
    for root in unique_paths(libraries):
        apps = root / 'steamapps'
        fields = dict(vdf_strings(apps / f'appmanifest_{APP_ID}.acf'))
        name = fields.get('installdir')
        if name and name not in ('.', '..') and Path(name).name == name and '/' not in name and '\\' not in name:
            candidates.append(apps / 'common' / name)
        candidates.append(apps / 'common' / GAME_NAME)
    return [p for p in unique_paths(candidates) if is_installation(p)]


def discover_installations(include_remembered=True, roots=None):
    candidates = []
    if include_remembered:
        saved = remembered_installation()
        if saved:
            candidates.append(saved)
    candidates.extend(steam_installations(roots))
    return list(unique_paths(candidates))


def discover():
    choices = discover_installations()
    return str(choices[0]) if choices else ''


def save_directory(installation):
    if not is_installation(installation):
        return None
    p = Path(installation)
    for folder in (p / 'save', p):
        try:
            if any(f.is_file() for f in folder.glob('*.sav')):
                return folder
        except OSError:
            pass
    return p / 'save' if (p / 'save').is_dir() else p
