@echo off
setlocal EnableExtensions
cls

set "bat_path=%~dp0"
set "build_script=%bat_path%build_pack.py"

echo.
echo Scriptronaut QC Check Pack Build
echo =================================
echo.

if not exist "%build_script%" (
    echo Error: build_pack.py was not found.
    goto :error
)

set "pack_name=%~1"

if not defined pack_name (
    set /p "pack_name=Pack folder name [rigging or all]: "
)

if not defined pack_name set "pack_name=rigging"

if /i "%pack_name%"=="all" (
    python "%build_script%" --all
) else (
    python "%build_script%" --pack "%pack_name%"
)

if errorlevel 1 goto :error

echo.
echo Pack build completed successfully.
echo Output folder:
echo   %bat_path%dist
echo.
pause
exit /b 0

:error
echo.
echo Pack build failed.
echo.
pause
exit /b 1
