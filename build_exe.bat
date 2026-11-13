@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo  Ectype IDML - build the .exe
echo ==============================================

rem Prefer the Python launcher (py) if it is installed.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || goto :nopython

if not exist ".venv\Scripts\python.exe" (
    echo Creating a private Python environment in .venv ...
    %PY% -m venv .venv || goto :fail
)
set "VPY=.venv\Scripts\python.exe"

echo Installing requirements ...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r requirements.txt pyinstaller tkinterdnd2 || goto :fail

rem The program carries its version in its name: "Ectype-IDML-1.0.0.exe"
"%VPY%" -c "import ectype_idml; print(ectype_idml.__version__)" > "%TEMP%\d2i_version.txt" || goto :fail
set /p VER=<"%TEMP%\d2i_version.txt"
del "%TEMP%\d2i_version.txt"

echo Building Ectype IDML %VER% ...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "Ectype-IDML-%VER%" ^
    --add-data "ectype_idml\idml\base;ectype_idml\idml\base" ^
    --collect-submodules fontTools.ttLib.tables ^
    --collect-all tkinterdnd2 ^
    --hidden-import win32com.client ^
    --hidden-import pythoncom ^
    run_app.py || goto :fail

echo.
echo Done:  "dist\Ectype-IDML-%VER%.exe"
echo.
pause
exit /b 0

:nopython
echo Python 3.10 or newer is required to build the .exe.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
pause
exit /b 1

:fail
echo.
echo The build failed. Scroll up for the error message.
pause
exit /b 1
