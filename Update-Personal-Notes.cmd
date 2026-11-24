@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Put these two updater files in your my-website folder, next to build_blog.py.
    echo This uses the same Python environment you used to preview your posts.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "update_personal_notes.py" --setup
set "notes_result=%ERRORLEVEL%"
if "%notes_result%"=="0" start "" "%~dp0blog\personal\index.html"
echo.
pause
exit /b %notes_result%
