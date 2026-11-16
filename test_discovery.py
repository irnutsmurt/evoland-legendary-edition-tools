import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import game_discovery as d

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.steam = self.root / 'Steam'
        (self.steam / 'steamapps').mkdir(parents=True)
        self.settings = self.root / 'settings' / 'installation.json'
        p = patch.object(d, 'config_path', return_value=self.settings)
        p.start(); self.addCleanup(p.stop)
    def install(self, library, name=d.GAME_NAME):
        p = library / 'steamapps/common' / name
        p.mkdir(parents=True)
        for f in ('evo1.pak', 'evo2.pak'): (p / f).touch()
        return p
    def test_default(self):
        p = self.install(self.steam)
        self.assertEqual(d.discover_installations(roots=[self.steam]), [p])
    def test_secondary_manifest_custom_name(self):
        library = self.root / 'My other drive'
        p = self.install(library, 'Custom Game Name')
        (library / 'steamapps/appmanifest_1020470.acf').write_text('"AppState" { "appid" "1020470" "installdir" "Custom Game Name" }')
        (self.steam / 'steamapps/libraryfolders.vdf').write_text(f'"libraryfolders" {{ "1" {{ "path" "{library}" "apps" {{ "1020470" "1" }} }} }}')
        self.assertEqual(d.discover_installations(roots=[self.steam]), [p])
    def test_legacy_vdf_and_duplicates(self):
        library = self.root / 'Other Library'
        p = self.install(library)
        (self.steam / 'steamapps/libraryfolders.vdf').write_text(f'"LibraryFolders" {{ "1" "{library}" }}')
        self.assertEqual(d.discover_installations(roots=[self.steam, library]), [p])
    def test_windows_escaped_paths(self):
        f = self.root / 'libraryfolders.vdf'
        f.write_text(r'"libraryfolders" { "1" { "path" "D:\\SteamLibrary" } }')
        self.assertIn(('path', r'D:\SteamLibrary'), d.vdf_strings(f))
    def test_remember_and_invalid(self):
        p = self.install(self.root / 'manual')
        d.remember_installation(p)
        self.assertEqual(d.discover_installations(roots=[]), [p])
        self.assertEqual(d.discover_installations(False, roots=[]), [])
        (p / 'evo2.pak').unlink()
        self.assertEqual(d.discover_installations(roots=[]), [])
        with self.assertRaises(ValueError): d.remember_installation(p)
    def test_wrong_game(self):
        p = self.steam / 'steamapps/common' / d.GAME_NAME
        p.mkdir(parents=True); (p / 'hlboot.dat').touch()
        self.assertEqual(d.discover_installations(roots=[self.steam]), [])
    def test_save_locations(self):
        p = self.install(self.steam)
        self.assertEqual(d.save_directory(p), p)
        (p / 'slot0.sav').touch()
        self.assertEqual(d.save_directory(p), p)
        (p / 'save').mkdir(); (p / 'save/slot1.sav').touch()
        self.assertEqual(d.save_directory(p), p / 'save')
        self.assertIsNone(d.save_directory(None))

if __name__ == '__main__': unittest.main(verbosity=2)
