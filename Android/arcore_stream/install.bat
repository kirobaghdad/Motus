@echo off
setlocal
cd /d "%~dp0"
if not exist "app\build\outputs\apk\debug\app-debug.apk" call build.bat
if errorlevel 1 exit /b 1
where adb >nul 2>nul
if errorlevel 1 (
  echo adb was not found. Install Android Platform Tools and add it to PATH.
  exit /b 1
)
adb install -r "app\build\outputs\apk\debug\app-debug.apk"
