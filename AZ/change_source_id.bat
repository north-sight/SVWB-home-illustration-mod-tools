@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "SOURCE=%ROOT%source.txt"
set "SCRIPT=%ROOT%change_source_id.py"

if not exist "%SOURCE%" (
  echo [ERROR] source.txt not found: "%SOURCE%"
  exit /b 1
)

if not exist "%SCRIPT%" (
  echo [ERROR] helper script not found: "%SCRIPT%"
  exit /b 1
)

set /p "NEW_ID=Input new id, for example 1227: "
if not defined NEW_ID (
  echo [ERROR] Empty id.
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python was not found.
    exit /b 1
  )
  py -3 "%SCRIPT%" --source "%SOURCE%" --new-id "%NEW_ID%"
) else (
  python "%SCRIPT%" --source "%SOURCE%" --new-id "%NEW_ID%"
)

if errorlevel 1 (
  echo [ERROR] Failed to update source.txt.
  exit /b 1
)

echo [OK] source.txt saved.
exit /b 0
