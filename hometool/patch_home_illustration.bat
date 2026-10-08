@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set /p NEW_ID=Target id / New id: 
if "%NEW_ID%"=="" (
    echo [ERROR] Target id is empty.
    pause
    exit /b 1
)

echo.
echo [1/2] Dry-run: checking planned edits...
python patch_home_illustration_skel.py "%NEW_ID%" --dry-run
if errorlevel 1 (
    echo.
    echo Dry-run failed. Nothing was written.
    pause
    exit /b 1
)

echo.
echo Press Enter to write the renamed bundle.
pause >nul

echo.
echo [2/2] Patching...
python patch_home_illustration_skel.py "%NEW_ID%" --overwrite
if errorlevel 1 (
    echo.
    echo Patching failed.
    pause
    exit /b 1
)
echo.
pause
