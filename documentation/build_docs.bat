@echo off
setlocal

echo ============================================
echo Scriptronaut QC Documentation Builder
echo ============================================
echo.

REM Root folder (folder this BAT is in)
set ROOT=%~dp0

set QC_MODULES=%ROOT%..\qc_checker\qc_modules
set TEMPLATE=%ROOT%\template
set OUTPUT=%ROOT%\site

python "%ROOT%\build_docs.py" ^
    "%QC_MODULES%" ^
    "%TEMPLATE%" ^
    "%OUTPUT%" ^
    --version 1.1

echo.
echo ============================================
echo Documentation Complete
echo ============================================
pause