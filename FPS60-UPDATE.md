# Evoland Toolkit — 60 FPS update (Patch 004)

This cumulative source update includes Patch 003 (mushroom jumps) and Patch 004 (60 FPS cap). Extract the files into your existing toolkit repository. It does not change editor.py, the save format, or your GitHub workflow.

1. Close Evoland Legendary Edition.
2. Rebuild the toolkit or run it from source.
3. Open Game Patches, check your installation, retain your desired existing fixes, select **004 · 60 FPS frame limiter**, and Apply selection.
4. Launch the game and confirm with an FPS overlay (disable any external FPS cap during the test). Test menu cursor, water droplets, Plum's boulders, and Windy Caves. To isolate the effect of the cap, test Patch 004 by itself against the original game.
5. If the game does not launch, restore original game files using the toolkit. Existing backups and earlier patch combinations remain recognized.

Validation: both original supplied bytecode builds, all 16 combinations each, unchanged previous hashes, exact restoration, rollback, deterministic simulation of emitted limiter opcodes, save-editor regression tests and GUI smoke tests. No live game/JIT validation. DirectX uses an added standard HashLink sys_sleep import; the installed runtime DLL export has not been checked. Coarse OS timers may cause longer frames or increased CPU usage while yielding. The shared engine loop may affect both Evoland games. No game binaries or saves included.

Developer tests with original local boot files: `python test_patches.py /path/to/game` and `python test_fps60.py /path/to/game`.
