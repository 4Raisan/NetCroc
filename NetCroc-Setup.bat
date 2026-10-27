@echo off
setlocal
cd /d "%~dp0"
echo NetCroc source setup
where py >nul 2>&1
if errorlevel 1 goto no_python
py -3 -c "import sys; assert (3,12) <= sys.version_info[:2] <= (3,14); import tkinter, venv" >nul 2>&1
if errorlevel 1 goto bad_python
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto failure
)
.venv\Scripts\python.exe -c "import sys; assert (3,12) <= sys.version_info[:2] <= (3,14); import tkinter" >nul 2>&1
if errorlevel 1 goto bad_environment
.venv\Scripts\python.exe -m pip install -r src\requirements.txt
if errorlevel 1 goto failure
.venv\Scripts\python.exe -c "import tkinter, PIL, pystray, psutil, paramiko" >nul 2>&1
if errorlevel 1 goto failure
echo Setup complete. Launching NetCroc...
start "" .venv\Scripts\pythonw.exe src\app.py
exit /b 0
:no_python
echo Python launcher missing. Install Python 3.12-3.14 from https://www.python.org/downloads/ with pip and Tcl/Tk, then retry.
goto failure
:bad_python
echo Python 3.12-3.14 with Tcl/Tk is required. Repair or install Python, then retry.
goto failure
:bad_environment
echo The existing .venv is incompatible. Back it up and create a new environment before retrying.
:failure
echo Setup did not finish. Check the messages above and try again.
pause
exit /b 1
