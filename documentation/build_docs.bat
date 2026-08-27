@echo off
setlocal EnableExtensions
cls

echo ============================================
echo Scriptronaut QC Documentation Builder
echo ============================================
echo.

set "bat_path=%~dp0"

echo Build Documentation:
echo 1. Core
echo 2. Pro
echo 3. Core + Pro
echo.
choice /c 123 /n /m "Select 1, 2 or 3: "

if errorlevel 3 (
    set "product=all"
) else if errorlevel 2 (
    set "product=pro"
) else (
    set "product=core"
)

echo.
echo Building: %product%
echo.

python "%bat_path%build_docs.py" --product %product% --version 1.0

if errorlevel 1 (
    echo.
    echo ============================================
    echo Documentation Build Failed
    echo ============================================
    goto :end
)

echo.
echo ============================================
echo Documentation Complete
echo ============================================
echo Site:
echo %bat_path%site


:end
echo.
pause

echo.
rmdir /s /q "%bat_path%.site_build"
rmdir /s /q "%bat_path%__pycache__"
echo.
echo ============================================
echo Cleaned Up Temp folders
echo ============================================
echo.

endlocal
