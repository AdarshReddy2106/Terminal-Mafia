@echo off
echo ==============================================
echo Building Terminal Mafia Executables
echo ==============================================

REM Check if PyInstaller is installed
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] PyInstaller is not installed.
    echo Please run: pip install -r requirements.txt
    exit /b 1
)

echo.
echo [1/2] Building Client...
python -m PyInstaller --onefile --clean ^
    --name "TerminalMafia_Client" ^
    --add-data "assets\ascii_art.py;assets" ^
    run_client.py

echo.
echo [2/2] Building Server...
python -m PyInstaller --onefile --clean ^
    --name "TerminalMafia_Server" ^
    --add-data "assets\ascii_art.py;assets" ^
    run_server.py

echo.
echo ==============================================
echo Build Complete!
echo Executables can be found in the "dist" folder.
echo ==============================================
pause
