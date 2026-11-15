#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m PyInstaller --noconfirm --clean --onedir --windowed --name EvolandSaveEditor --add-data 'catalog.json:.' editor.py
mkdir -p release
mkdir -p AppDir/usr/bin
cp -a dist/EvolandSaveEditor AppDir/usr/bin/
cp packaging/AppRun AppDir/AppRun
cp packaging/evoland-save-editor.{desktop,svg} AppDir/
# Desktop Exec must refer to the app entry point.
sed -i 's/^Exec=.*/Exec=EvolandSaveEditor %f/' AppDir/evoland-save-editor.desktop
# Preserve a portable tarball for hosts without FUSE.
tar -C dist -czf release/EvolandSaveEditor-linux-x86_64.tar.gz EvolandSaveEditor
if command -v xvfb-run >/dev/null; then xvfb-run -a dist/EvolandSaveEditor/EvolandSaveEditor --smoke-test; fi
if [[ -z "${APPIMAGETOOL:-}" ]]; then
  echo 'Set APPIMAGETOOL to an appimagetool executable to build an AppImage.' >&2
  exit 0
fi
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" AppDir release/EvolandSaveEditor-linux-x86_64.AppImage
if command -v xvfb-run >/dev/null; then APPIMAGE_EXTRACT_AND_RUN=1 xvfb-run -a release/EvolandSaveEditor-linux-x86_64.AppImage --smoke-test; fi
