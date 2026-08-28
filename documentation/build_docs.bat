@echo off
setlocal EnableExtensions
cls

echo ============================================
echo Scriptronaut QC Documentation Builder
echo ============================================
echo.

set "bat_path=%~dp0"

rem ------------------------------------------------------------
rem Core
rem ------------------------------------------------------------

choice /c YN /n /m "Build Core documentation? [Y/N]: "

if errorlevel 2 (
    set "build_core=0"
) else (
    set "build_core=1"
)

rem ------------------------------------------------------------
rem Pro
rem ------------------------------------------------------------

choice /c YN /n /m "Build Pro documentation? [Y/N]: "

if errorlevel 2 (
    set "build_pro=0"
) else (
    set "build_pro=1"
)

rem ------------------------------------------------------------
rem Packs
rem ------------------------------------------------------------

choice /c YN /n /m "Build all discovered Pack documentation? [Y/N]: "

if errorlevel 2 (
    set "packs=none"
) else (
    set "packs=all"
)


rem ------------------------------------------------------------
rem Product Pages
rem ------------------------------------------------------------

choice /c YN /n /m "Build product pages for the selected products? [Y/N]: "

if errorlevel 2 (
    set "product_pages=none"
) else (
    set "product_pages=selected"
)

rem ------------------------------------------------------------
rem Resolve Core / Pro selection
rem ------------------------------------------------------------

if "%build_core%"=="1" (
    if "%build_pro%"=="1" (
        set "product=all"
    ) else (
        set "product=core"
    )
) else (
    if "%build_pro%"=="1" (
        set "product=pro"
    ) else (
        set "product=none"
    )
)

if "%product%"=="none" if "%packs%"=="none" (
    echo.
    echo Error: Nothing was selected to build.
    goto :end
)

echo.
echo ============================================
echo Build Selection
echo ============================================
echo Core / Pro: %product%
echo Packs:      %packs%
echo Product pages: %product_pages%
echo.

python "%bat_path%build_docs.py" ^
    --product %product% ^
    --packs %packs% ^
    --product-pages %product_pages% ^
    --version 1.0

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
echo.


:end
echo.
pause

rmdir /s /q "%bat_path%.site_build" >nul 2>&1
rmdir /s /q "%bat_path%__pycache__" >nul 2>&1

echo.
echo ============================================
echo Cleaned Up Temp Folders
echo ============================================
echo.

endlocal
