@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if not exist "%ROOT%" (
  echo [ERROR] Script directory not found.
  exit /b 1
)

for %%D in (bak decrypt encrypt export source) do call :clear_dir "%ROOT%%%D"

echo [OK] Done.
exit /b 0

:clear_dir
set "DIR=%~1"
if not exist "%DIR%" (
  mkdir "%DIR%"
  echo [INFO] Created %DIR%
  exit /b 0
)

del /f /q "%DIR%\*" >nul 2>nul
for /d %%G in ("%DIR%\*") do rmdir /s /q "%%~fG" >nul 2>nul
echo [OK] Cleared %DIR%
exit /b 0
