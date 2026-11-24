@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Extract both updater files into my-website, beside build_blog.py.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -B "add_science_note.py"
set "science_result=%ERRORLEVEL%"
if "%science_result%"=="0" start "" "%~dp0blog\science\index.html"
echo.
pause
exit /b %science_result%
