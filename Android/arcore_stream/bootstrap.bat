@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "GRADLE_VERSION=8.11.1"
set "BOOT_DIR=%PROJECT_DIR%.gradle-bootstrap"
set "ZIP_FILE=%BOOT_DIR%\gradle-%GRADLE_VERSION%-bin.zip"
set "GRADLE_BAT=%BOOT_DIR%\gradle-%GRADLE_VERSION%\bin\gradle.bat"

if exist "%PROJECT_DIR%gradle\wrapper\gradle-wrapper.jar" goto done
if not exist "%BOOT_DIR%" mkdir "%BOOT_DIR%"
if not exist "%ZIP_FILE%" (
  echo Downloading Gradle %GRADLE_VERSION%...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Invoke-WebRequest -Uri 'https://services.gradle.org/distributions/gradle-%GRADLE_VERSION%-bin.zip' -OutFile '%ZIP_FILE%'"
  if errorlevel 1 goto fail
)
if not exist "%GRADLE_BAT%" (
  echo Extracting Gradle...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%BOOT_DIR%' -Force"
  if errorlevel 1 goto fail
)

echo Creating the official Gradle wrapper...
pushd "%PROJECT_DIR%"
call "%GRADLE_BAT%" wrapper --gradle-version %GRADLE_VERSION% --distribution-type bin
if errorlevel 1 (
  popd
  goto fail
)
popd

:done
echo Gradle wrapper is ready.
exit /b 0

:fail
echo Failed to create the Gradle wrapper.
exit /b 1
