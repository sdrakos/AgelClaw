@echo off
title AgelClaw Installer
color 0A

echo.
echo  ==========================================
echo       AgelClaw - One-Click Installer
echo   Self-evolving AI Agent for your desktop
echo  ==========================================
echo.
echo  This will install everything you need.
echo  Just follow the prompts.
echo.
pause

:: Step 1: Check Python
echo.
echo  [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Python not found. Installing...
    winget install Python.Python.3.13 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo  ERROR: Could not install Python automatically.
        echo  Please download Python from: https://www.python.org/downloads/
        echo  IMPORTANT: Check "Add Python to PATH" during installation!
        echo.
        pause
        exit /b 1
    )
    echo  Python installed. Please close this window and double-click install.bat again.
    pause
    exit /b 0
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo  OK: %%i

:: Step 2: Check Node.js
echo.
echo  [2/6] Checking Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Node.js not found. Installing...
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo  ERROR: Could not install Node.js automatically.
        echo  Please download from: https://nodejs.org/
        echo.
        pause
        exit /b 1
    )
    echo  Node.js installed. Please close this window and double-click install.bat again.
    pause
    exit /b 0
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo  OK: Node.js %%i

:: Step 3: Install Claude Code
echo.
echo  [3/6] Installing Claude Code...
call npm install -g @anthropic-ai/claude-code 2>nul
if %errorlevel% neq 0 (
    echo  WARNING: Claude Code installation had issues.
    echo  You may need to run this as Administrator.
)
claude --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Claude Code not available. Try restarting and running again.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('claude --version 2^>^&1') do echo  OK: Claude Code %%i

:: Step 4: Claude Login
echo.
echo  [4/6] Checking Claude subscription...
claude auth status 2>nul | findstr /C:"loggedIn" /C:"true" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Already logged in!
) else (
    echo.
    echo  You need to log in to your Claude account.
    echo  A browser window will open - sign in with your Max or Pro account.
    echo.
    pause
    call claude auth login
    if %errorlevel% neq 0 (
        echo  WARNING: Login may not have completed.
        echo  You can try again later with: claude auth login
    )
)

:: Step 5: Install AgelClaw
echo.
echo  [5/6] Installing AgelClaw...
pip install "git+https://github.com/sdrakos/AgelClaw.git" 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: AgelClaw installation failed.
    echo  Make sure you have internet and try again.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('agelclaw --version 2^>^&1') do echo  OK: %%i

:: Step 6: Initialize
echo.
echo  [6/6] Setting up AgelClaw...
agelclaw init
echo.

:: Create desktop shortcut
echo  Creating desktop shortcut...
set "DESKTOP=%USERPROFILE%\Desktop"
(
echo @echo off
echo title AgelClaw
echo agelclaw
echo pause
) > "%DESKTOP%\AgelClaw.bat"
echo  Shortcut created: %DESKTOP%\AgelClaw.bat

:: Done
echo.
echo  ==========================================
echo          Installation Complete!
echo  ==========================================
echo.
echo  What to do now:
echo.
echo    1. Run "agelclaw setup" to configure API keys
echo    2. Type "agelclaw" to start chatting
echo    3. Or double-click AgelClaw on your Desktop
echo.
echo  Need help? Visit: https://github.com/sdrakos/AgelClaw
echo.

set /p RUNSETUP="  Run setup wizard now? (Y/n): "
if /i "%RUNSETUP%" neq "n" (
    echo.
    agelclaw setup
)

echo.
echo  All done! Type "agelclaw" anytime to chat.
echo.
pause
