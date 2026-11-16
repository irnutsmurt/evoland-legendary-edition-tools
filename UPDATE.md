# Evoland Toolkit — installation discovery update

Copy the five Python files in this archive into the root of the existing repository (replace editor.py, patch_gui.py and test_editor.py; add game_discovery.py and test_discovery.py). This includes the previous dark-mode update. Do not replace the repository's GitHub Actions workflow.

On launch the application detects the Legendary Edition via Steam paths, Windows Steam registry values, libraryfolders.vdf and appmanifest_1020470.acf. It validates that both game archives exist. The game folder can be changed manually and is remembered; Rescan searches Steam again. Open save starts in the detected save directory. The patch manager still independently verifies hashes and backups before allowing changes. Non-Steam installations can be selected manually.

Run `python test_editor.py` to execute discovery and editor checks. Native Windows registry lookup was not tested on Windows; automated fixtures and Linux GUI smoke tests passed.
