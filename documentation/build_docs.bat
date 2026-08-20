@echo off
setlocal

echo ============================================
echo Scriptronaut QC Documentation Builder
echo ============================================
echo.

REM Root folder (folder this BAT is in)
set ROOT=%~dp0

set CHECKS=%ROOT%..\qc_checker\checks
set TEMPLATE=%ROOT%\template
set OUTPUT=%ROOT%\site

python "%ROOT%\build_docs.py" ^
    "%CHECKS%" ^
    "%TEMPLATE%" ^
    "%OUTPUT%" ^
    --version 1.1

echo.
echo ============================================
echo Documentation Complete
echo ============================================
pause