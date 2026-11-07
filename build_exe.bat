@echo off
setlocal
cd /d "%~dp0"

python -m PyInstaller ^
  --noconfirm ^
  --onedir ^
  --name BingoBot ^
  --add-data "assets;assets" ^
  --add-data "calibration;calibration" ^
  main.py

if errorlevel 1 (
  echo.
  echo Build falhou. Confirme que as dependencias foram instaladas:
  echo pip install -r requirements.txt
  exit /b 1
)

if not exist "dist\BingoBot\assets" mkdir "dist\BingoBot\assets"
if exist "assets" xcopy /E /I /Y "assets" "dist\BingoBot\assets" >nul

if not exist "dist\BingoBot\calibration" mkdir "dist\BingoBot\calibration"
if exist "calibration" xcopy /E /I /Y "calibration" "dist\BingoBot\calibration" >nul

if not exist "dist\BingoBot\debug" mkdir "dist\BingoBot\debug"

echo.
echo Build concluido em dist\BingoBot\BingoBot.exe
echo Pastas editaveis copiadas para dist\BingoBot\assets, calibration e debug
