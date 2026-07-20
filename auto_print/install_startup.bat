@echo off
setlocal enabledelayedexpansion

where pythonw >nul 2>nul
if errorlevel 1 (
    echo Impossible de trouver pythonw.exe dans le PATH.
    echo Verifie que Python est installe et que la case "Add python.exe to PATH" a ete cochee a l'installation.
    pause
    exit /b 1
)

for /f "delims=" %%P in ('where pythonw') do (
    set "PYTHONW=%%P"
    goto :found
)

:found
set "SCRIPT=%~dp0watch_and_print.py"

schtasks /Create /TN "AutoPrintDossier" /TR "\"!PYTHONW!\" \"!SCRIPT!\"" /SC ONLOGON /RL LIMITED /F

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Tache planifiee "AutoPrintDossier" creee avec succes.
    echo Le script se lancera automatiquement, en arriere-plan, a chaque ouverture de session Windows.
) else (
    echo.
    echo Echec de la creation de la tache planifiee.
)
pause
