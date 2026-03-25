@echo off
title Veille Scientifique & Tech
cd /d "%~dp0"

echo ================================
echo   Veille Scientifique ^& Tech
echo ================================
echo.

:: Vérifie si les dépendances sont installées
python -c "import flask" 2>nul
if errorlevel 1 (
    echo [!] Installation des dependances...
    pip install -r requirements.txt
    echo.
)

echo [*] Démarrage du serveur sur http://localhost:5000
echo [*] Ctrl+C pour arrêter
echo.
start "" http://localhost:5000
python app.py

pause
