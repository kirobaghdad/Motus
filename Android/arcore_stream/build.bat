@echo off
setlocal
cd /d "%~dp0"
if not exist "gradle\wrapper\gradle-wrapper.jar" call bootstrap.bat
if errorlevel 1 exit /b 1
call gradlew.bat assembleDebug
if errorlevel 1 exit /b 1
echo.
echo APK created at:
echo %CD%\app\build\outputs\apk\debug\app-debug.apk
