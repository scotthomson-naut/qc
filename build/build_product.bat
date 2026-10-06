@echo off
setlocal EnableExtensions
cls


rem ------------------------------------------------------------
rem Variables
rem ------------------------------------------------------------

set "bat_path=%~dp0"
set "build_script=%bat_path%build_products.py"
set "version_file=%bat_path%..\VERSION"
set "product_version="

if not exist "%version_file%" (
    echo.
    echo Error: VERSION file was not found.
    echo Expected: %version_file%
    goto :error
)

set /p product_version=<"%version_file%"


rem ------------------------------------------------------------
rem Product Version
rem ------------------------------------------------------------

:version_prompt
echo.
echo Scriptronaut QC Checker Build
echo ==========================================
echo Current version: %product_version%
echo.
set "requested_version="
set /p "requested_version=Version to build [%product_version%]: "

if not defined requested_version set "requested_version=%product_version%"

rem Python owns semantic-version validation and writes VERSION.  We validate
rem here before showing the remaining build menus so an invalid value can be
rem corrected immediately.
python -c "import re,sys; sys.exit(0 if re.fullmatch(r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)', sys.argv[1]) else 1)" "%requested_version%"
if errorlevel 1 (
    echo.
    echo Error: Invalid version "%requested_version%".
    echo Please enter a semantic version such as 0.1.0 or 1.2.3.
    goto :version_prompt
)

if /I not "%requested_version%"=="%product_version%" (
    echo.
    echo Update project version:
    echo   %product_version% ^-^> %requested_version%
    echo.
    choice /c YN /n /m "Continue? [Y/N]: "
    if errorlevel 2 goto :end
)

set "product_version=%requested_version%"


rem ------------------------------------------------------------
rem Build Mode
rem ------------------------------------------------------------

echo.
echo Build Mode:
echo 1. Development Build + Persistent Blender Junction
echo 2. Installable Beta ZIP
echo.

choice /c 12 /n /m "Select 1 or 2: "

if errorlevel 2 (
    set "build_mode=package"
) else (
    set "build_mode=dev"
)


rem ------------------------------------------------------------
rem Build Tier
rem ------------------------------------------------------------

echo.
echo Scriptronaut QC Checker Build
echo ==========================================
echo Version: %product_version%
echo.
echo Build Tier:
echo 1. Core
echo 2. Pro
echo.

choice /c 12 /n /m "Select 1 or 2: "

if errorlevel 2 (
    set "tier=pro"
) else (
    set "tier=core"
)


rem ------------------------------------------------------------
rem Beta Tools
rem ------------------------------------------------------------

echo.
echo Beta Tools:
echo Include the Beta panel, build label, Send Feedback, and documentation link?
choice /c YN /n /m "Include Beta tools? [Y/N]: "
if errorlevel 2 (
    set "beta_tools=no"
) else (
    set "beta_tools=yes"
)


if /I "%build_mode%"=="package" goto :package_build

rem ------------------------------------------------------------
rem Blender Version
rem ------------------------------------------------------------

echo.
set /p "blender_version=Your Blender Version? "

if not defined blender_version (
    echo.
    echo Error: Blender version was not entered.
    goto :error
)


rem ------------------------------------------------------------
rem Validate Blender Version
rem Expected format: X.X
rem ------------------------------------------------------------

set "version_major="
set "version_minor="
set "version_extra="

for /f "tokens=1,2,3 delims=." %%A in ("%blender_version%") do (
    set "version_major=%%A"
    set "version_minor=%%B"
    set "version_extra=%%C"
)

if not defined version_major goto :invalid_blender_version
if not defined version_minor goto :invalid_blender_version
if defined version_extra goto :invalid_blender_version

rem Major must contain numbers only.
for /f "delims=0123456789" %%A in ("%version_major%") do (
    goto :invalid_blender_version
)

rem Minor must contain numbers only.
for /f "delims=0123456789" %%A in ("%version_minor%") do (
    goto :invalid_blender_version
)

goto :blender_version_valid


:invalid_blender_version
echo.
echo Error: Invalid Blender version "%blender_version%".
echo Please enter a version such as 4.3 or 5.1.
goto :error


:blender_version_valid


rem ------------------------------------------------------------
rem Paths
rem ------------------------------------------------------------

set "blender_path=%APPDATA%\Blender Foundation\Blender\%blender_version%"
set "blender_addons_path=%blender_path%\scripts\addons"
set "blender_addon_path=%blender_addons_path%\qc_checker"

set "local_tool_path=%bat_path%dev\qc_checker_%tier%"


rem ------------------------------------------------------------
rem Validate Blender Folder
rem ------------------------------------------------------------

if not exist "%blender_path%\" (
    echo.
    echo Error: Blender %blender_version% user folder was not found.
    echo.
    echo Expected:
    echo %blender_path%
    goto :error
)


rem ------------------------------------------------------------
rem Validate Build Script
rem ------------------------------------------------------------

if not exist "%build_script%" (
    echo.
    echo Error: build_products.py was not found.
    echo.
    echo Expected:
    echo %build_script%
    goto :error
)


rem ------------------------------------------------------------
rem Display Build Information
rem ------------------------------------------------------------

echo.
echo ------------------------------------------------------------
echo Build Information
echo ------------------------------------------------------------
echo Tier:
echo   %tier%
echo.
echo Beta Tools:
echo   %beta_tools%
echo.
echo Blender:
echo   %blender_version%
echo.
echo Product Build:
echo   %local_tool_path%
echo.
echo Blender Addon Link:
echo   %blender_addon_path%
echo ------------------------------------------------------------
echo.


rem ------------------------------------------------------------
rem Build Product
rem ------------------------------------------------------------

python "%build_script%" --dev %tier% --version "%product_version%" --beta-tools %beta_tools%

if errorlevel 1 (
    echo.
    echo Error: Product build failed.
    goto :error
)


rem ------------------------------------------------------------
rem Validate Generated Product
rem ------------------------------------------------------------

if not exist "%local_tool_path%\__init__.py" (
    echo.
    echo Error: Generated product was not found.
    echo.
    echo Expected:
    echo %local_tool_path%
    goto :error
)


rem ------------------------------------------------------------
rem Ensure Blender Addons Folder Exists
rem ------------------------------------------------------------

if not exist "%blender_addons_path%\" (
    mkdir "%blender_addons_path%"

    if errorlevel 1 (
        echo.
        echo Error: Could not create Blender addons folder.
        echo %blender_addons_path%
        goto :error
    )
)


rem ------------------------------------------------------------
rem Remove Existing qc_checker Link
rem
rem IMPORTANT:
rem We intentionally use plain RMDIR without /S.
rem
rem - A directory symbolic link is removed safely.
rem - A normal non-empty qc_checker folder will NOT be deleted.
rem
rem This prevents the development script from accidentally deleting a real
rem addon installation.
rem ------------------------------------------------------------

if exist "%blender_addon_path%\" (
    echo.
    echo Removing existing qc_checker development link...

    rmdir "%blender_addon_path%" >nul 2>&1

    if exist "%blender_addon_path%\" (
        echo.
        echo Error: "%blender_addon_path%" could not be removed.
        echo.
        echo It may be a real non-empty addon folder instead of a
        echo development symbolic link.
        echo.
        echo Remove or rename it manually, then run this build again.
        goto :error
    )
)


rem ------------------------------------------------------------
rem Create System Link
rem ------------------------------------------------------------

echo.
echo Creating Blender development link...

rem directory junction
mklink /J "%blender_addon_path%" "%local_tool_path%"

if errorlevel 1 (
    echo.
    echo Error: Could not create the Blender development symbolic link.
    echo.
    echo Link:
    echo   %blender_addon_path%
    echo.
    echo Target:
    echo   %local_tool_path%
    echo.
    echo If Windows reports insufficient privilege, enable Windows
    echo Developer Mode or run this batch file as Administrator.
    goto :error
)


rem ------------------------------------------------------------
rem Success
rem ------------------------------------------------------------

echo.
echo ============================================================
echo Development Build Ready
echo ============================================================
echo.
echo Tier:
echo   %tier%
echo.
echo Blender %blender_version% now points to:
echo   %local_tool_path%
echo.
echo Link:
echo   %blender_addon_path%
echo.
echo Restart Blender or reload the addon before testing.
echo.
echo IMPORTANT: Keep build\dev while this development addon is enabled.
echo Future Development Builds update this same persistent location.
echo Installable Beta builds do NOT remove it.
echo ============================================================
echo.

goto :end




:package_build
echo.
echo ------------------------------------------------------------
echo Installable Beta Package
echo ------------------------------------------------------------
echo Tier:
echo   %tier%
echo.
echo Version:
echo   %product_version%
echo.
echo Beta Tools:
echo   %beta_tools%
echo.
echo Output Folder:
echo   %bat_path%dist
echo ------------------------------------------------------------
echo.

python "%build_script%" --package %tier% --version "%product_version%" --beta-tools %beta_tools%

if errorlevel 1 (
    echo.
    echo Error: Installable package build failed.
    goto :error
)

echo.
echo ============================================================
echo Installable Beta ZIP Ready
echo ============================================================
echo.
echo The ZIP in:
echo   %bat_path%dist
echo.
echo is ready for Blender:
echo   Preferences ^> Get Extensions ^> menu ^> Install from Disk
echo.
echo Do NOT zip the dev folder manually.
echo ============================================================
echo.
goto :end


:error
echo.
echo ============================================================
echo Development Build Failed
echo ============================================================
echo.


:end
pause
endlocal
