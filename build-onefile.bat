@echo off
setlocal

cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found in PATH.
    echo Install uv first, then run this script again.
    exit /b 1
)

echo Building AutoInput single-file executable...
uv run --with pyinstaller python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name AutoInput ^
    --distpath dist ^
    --workpath build ^
    auto_input_gui.py

if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo Build complete: dist\AutoInput.exe
endlocal
