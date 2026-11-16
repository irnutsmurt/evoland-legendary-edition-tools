# Evoland Toolkit — alpha 0.1

An offline desktop toolkit with a save editor for **Evoland** and **Evoland 2** (Legendary Edition). Automatically detects the game from the save's GameType, not its filename. No game archives or personal save files are included.

## Quick start

1. Extract the entire ZIP into a folder.
2. Install Python 3.10 or newer if not already available. On Windows, run `Launch-Windows.bat`. On Linux, run `./launch-linux.sh` or `python3 editor.py`. Tkinter is included with standard Windows Python; some Linux distributions package it separately (`python3-tk` on Debian/Ubuntu, `tk` on Arch/Manjaro).
3. Close the game. Click **Open save…**, then select the `.sav` file. The editor will identify the game automatically.
4. Choose a tab. Double-click a table row to edit it. Forms have an **Apply** button, which stages changes without writing to disk.
5. Use **Review changes** to see staged operations. **Undo** reverses the last operation; **Reset edits** returns to the original.
6. Use **Save as…** to make a test copy, or **Overwrite save** to replace the opened file. Every overwrite creates a timestamped `.bak` file alongside the save. Never edit a save while the game is running; cloud sync may overwrite manual changes.

Typical Steam location: `steamapps/common/Evoland Legendary Edition/save/`. Slot names alone are not reliable game identifiers. You can pass a save path on the command line, e.g. `python editor.py slot0.sav`.

## Experimental game patches (Evoland 2)

Open **Game Patches** from the main window; no save needs to be open. Close the game, select its installation directory, and click **Check**. Enable any patch independently and click **Apply selection**. To undo, click **Restore original game**. Only the exact supplied Legendary Edition boot-file builds are accepted. The patcher verifies SHA-256 before and after modification, backs up the originals in `.evoland-toolkit`, and rolls back completed writes on a detected failure. Keep your own save backup before testing. No game files or saves are distributed; the patch manifest contains targeted instruction edits only.

- **001 — Shooter softlock:** correct formation target boundary calculations using actual delta-scaled movement; clamp formation targets to the bounds. Regular enemies continuously offscreen for approximately three seconds after entering the play area are removed using the existing enemy removal routine, which also updates the wave list. Bosses and rebosses are excluded from the cleanup. Escaping enemies grant no kill rewards. Test by deliberately letting regular enemies escape, then verify the wave and boss progression.
- **002 — Future Trunkodile wake-up:** if the 3D creature starts waking but does not begin movement within approximately two seconds, invoke its original wake-up callback. Guard against duplicate callbacks. Fina's charged attack and collision logic are not bypassed. Test both a fresh puzzle and an affected save. If the creature is blocked by geometry rather than the animation callback, this patch may not resolve it; the existing save editor remains available to repair positions.

- **003 — Windy Caves mushroom jumps:** in the future Windy Caves (`WindvalleyClimb`), cap the existing entity-update substeps at one nominal 60 Hz frame. Mushroom-assisted jumps receive their boost for exactly eight nominal frames; the held-jump velocity limit is stabilized at -0.367 tile/frame (the original cap was -0.35 minus 0.012 times the frame delta). This is within the original range at 30–60 Hz and gives a modest clearance margin, rather than removing the cap. The boost changes apply only to 3D mushroom-assisted jumps in this map. Other entities in the future cave also use the finer substeps; regular jump constants, collision geometry, and other maps are unchanged. Test held jumps at different frame rates, especially closely spaced platforms, moving mushrooms, and spikes. The patch is not a proof that all collision failures have been resolved.

- **004 — 60 FPS frame limiter:** pace the shared HashLink engine loop using its existing high-resolution elapsed-time clock and standard runtime sleep. The maximum target is 60 frames per second (16.667 ms minimum per completed loop); slow frames run normally, with no artificial catch-up ticks or VSync/monitor requirement. Adaptive sleep and a short yield/recheck loop handle OS sleep precision. The SDL build already imports `std.sys_sleep`; the DirectX build adds that standard HashLink v4 runtime import, without redistributing a runtime or executable. The actual Windows DLL export and game execution still need testing. Both games may be affected if they share this outer loop; no save data is modified. Check menu animation, water droplets, Plum’s boulder phase and the Windy Caves at 60 FPS, and use an FPS overlay to confirm pacing. Driver caps and VSync are independent; if enabled they can lower the achievable FPS further. Coarse OS timers can cause occasional longer frames or more CPU usage during yielding. The limiter is a compatibility workaround, not a rewrite of all frame-dependent logic.

These patches are **experimental**: bytecode structure, branches, debug information and unchanged functions were checked in both supplied builds; no running-game/JIT or gameplay verification has been performed. Do not treat these as confirmed fixes. The timers are engineering defaults, not measured gameplay thresholds. A game update may require new patch recipes. The patcher refuses unknown hashes and never edits saves. A forced interruption between boot-file writes may leave a mixed selection; reopen the patcher and apply the desired selection or restore originals.

Run the optional integration tests against a folder containing both original boot files:

```sh
python3 test_patches.py /path/to/game
```

Tests operate on temporary copies only. `patch_recipes.py` and `hlbytecode.py` are developer tools for regenerating and checking the manifest locally. No original game binaries are included.

## Editing features

| Tab | Evoland 1 | Evoland 2 |
|---|---|---|
| Stats | Hero/companion level and XP, glis, life, final-stage life, keys, names | Level, XP, gold, attack, defense, max/current HP, full heal, boss preset, nested checkpoint stats |
| Items | 13 named inventory types | 74 named item definitions, quantities, category and owned-only filters |
| Equipment | Gear quantity editing | Slot-filtered weapons, armor, belts and boots; auto-add gear; highest bonus selector |
| Collectibles | Stars and raw card indices (names provisional) | Stars, cards, add all cards |
| Loot | 24 Diablo-style loot definitions, existing raw flags | — |
| Companions | Level and XP on Stats | Existing unlock values and HP/MP |
| World | Raw world enum and coordinates | 93 area definitions, 129 linked timeline variants (132 raw map records), explicit map anchors, forest object editor |
| Progression | Existing chest flags, world records, achievements, unlock flags | Existing quest/area flags, achievements, tactics troops and events |
| Advanced | Search and edit existing scalar fields | Search and edit existing scalar fields |
| Reference | Items, cards, worlds, chest reward names | Items, cards, maps, 172 enemy definitions, RTC map event IDs |

## Safety and limits

- Reads and verifies the original integrity checksum before editing. Regenerates it after every staged edit; validates the resulting Haxe serialization. Structural edits rebuild string-cache references and compare the resulting state against the requested changes.
- No automatic inventory or quest manipulation on load. All changes are staged. Original files are untouched until a save action. Atomic file replacement and timestamped backups protect against partial writes; the editor refuses to overwrite its opened file if it has changed externally.
- The equipment tab displays the game's gear bonuses. It does **not** recalculate stored attack/defense, since their relationship to equipped gear is not verified. Set combat stats separately if desired.
- Evoland 1 does not expose direct attack/defense fields in the supplied save. Raw life fields may represent different combat modes. Card/loot names are based on XML order and the mapping to saved indices is provisional. Raw loot flags are not claimed to mean ownership or equipment status. Chest reward names are reference-only; they are not mapped to save chest IDs.
- Evoland 2 teleports are limited to known map/timeline/anchor combinations, but this does not ensure that the area is unlocked or story state is compatible. Quest edits do not infer missing flags, update associated counters or complete cutscenes. Companion unlock values are raw; unsupported values can be unsafe. Only the stat editor can update embedded checkpoints; inventory, gear and other changes apply to the current state.
- The advanced tab is intentionally restricted to existing scalar values. It cannot create arbitrary progression records, change enum types or edit serialized checkpoint strings. Unknown object-reference layouts may be refused for structural changes. Preserve backups.
- Validated against five supplied Legendary Edition saves (one Evoland 1, four Evoland 2), including a final-boss save. Tested parser, editing, checksums, inventory, equipment, cards, relocation serialization, backups, and GUI rendering/undo under Linux/Xvfb. Not tested inside the running games, on Windows, or with every possible early-game save. Standalone editions and other platform formats are unverified.

## Catalogs

The bundled `catalog.json` is a compact derived reference (IDs, names, numeric attributes, maps and anchors), generated from the supplied Legendary Edition resource archives. It contains no PAKs, executable bytecode, music, artwork, save files, or full game databases. `catalog.py` reads the Heaps PAK index and extracts the relevant CastleDB and XML/CSV metadata from a local installation. **Import game catalogs…** regenerates the catalog in memory from the folder containing `evo1.pak` and `evo2.pak`; `evo2-extra.pak` is optional and supplies updated English localization when present. To regenerate the bundled catalog permanently:

```sh
python3 catalog.py '/path/to/Evoland Legendary Edition' > catalog.new.json
# After confirming the command succeeds, replace catalog.json with catalog.new.json.
```

`evo1-extra.pak` contains supplementary localizations/assets; `hlboot.dat` was inspected for Evoland 1 enum identifiers. Neither is required by the editor. No proprietary executables are distributed.

## Optional Windows executable

Run `build-windows.bat` on Windows with Python installed. This installs PyInstaller and builds `dist/EvolandToolkit.exe` with the catalog included. A Windows executable is not included in this ZIP; this build script has not been run on Windows in this environment.

## Offline tests

```sh
python3 test_editor.py
python3 test_editor.py /path/to/slot0.sav /path/to/slot1.sav
```

The optional real-save tests edit only in memory and never overwrite input files.

## Standalone release builds (no Python required for users)

The GitHub Actions workflow `.github/workflows/build.yml` builds an x86-64 Windows portable `.exe`, a Linux AppImage, and a Linux portable archive. Run **Actions → Build standalone toolkit → Run workflow** after pushing this source to a GitHub repository. Download the artifacts from the completed run. Pushing a `v*` tag also creates or updates a GitHub Release with all binaries. No account tokens are required beyond the automatic repository workflow token.

Windows users double-click the executable. Linux users mark the AppImage executable (`chmod +x EvolandToolkit-linux-x86_64.AppImage`) and launch it. On a system without FUSE use `--appimage-extract-and-run`, or extract the portable tar.gz and launch `EvolandToolkit`. The release workflow targets Ubuntu 22.04 as its Linux build baseline (glibc 2.35); actual compatibility depends on installed desktop libraries. Windows binaries are unsigned and may trigger SmartScreen. The workflow builds on its native operating systems and smoke-tests the packaged GUI. The continuous AppImage tool download is not pinned; pin a reviewed version/checksum for reproducible public releases.
