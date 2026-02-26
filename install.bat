@echo off
setlocal enabledelayedexpansion
title AgelClaw Installer
color 0A
chcp 65001 >nul 2>&1

echo.
echo  ==========================================
echo       AgelClaw - One-Click Installer
echo   Self-evolving AI Agent for your desktop
echo  ==========================================
echo.
echo  This will install everything you need.
echo.

:: ============================================
:: Step 0: Choose installation folder (GUI)
:: ============================================
set "DEFAULT_DIR=%USERPROFILE%\.agelclaw"

echo  Choose where to install AgelClaw.
echo  Default: %DEFAULT_DIR%
echo.
echo  A folder picker window will open now...
echo.

:: Use PowerShell to show a FolderBrowserDialog
for /f "delims=" %%F in ('powershell -NoProfile -Command ^
  "Add-Type -AssemblyName System.Windows.Forms; ^
   $dlg = New-Object System.Windows.Forms.FolderBrowserDialog; ^
   $dlg.Description = 'Choose AgelClaw installation folder'; ^
   $dlg.RootFolder = 'MyComputer'; ^
   $dlg.SelectedPath = '%DEFAULT_DIR%'; ^
   $dlg.ShowNewFolderButton = $true; ^
   $result = $dlg.ShowDialog(); ^
   if ($result -eq 'OK') { $dlg.SelectedPath } else { 'CANCELLED' }"') do set "INSTALL_DIR=%%F"

if "%INSTALL_DIR%"=="CANCELLED" (
    echo.
    echo  Installation cancelled by user.
    echo.
    pause
    exit /b 0
)

if "%INSTALL_DIR%"=="" set "INSTALL_DIR=%DEFAULT_DIR%"

echo  Install folder: %INSTALL_DIR%
echo.

:: Create install dir if needed
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Set environment variable so agelclaw init uses this folder
set "AGELCLAW_HOME=%INSTALL_DIR%"

:: ============================================
:: Step 1: Check Python
:: ============================================
echo  [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Python is not installed.
    echo  Installing via winget...
    echo.
    winget install Python.Python.3.13 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo  ===========================================
        echo  Could not install Python automatically.
        echo  Please download it manually from:
        echo.
        echo    https://www.python.org/downloads/
        echo.
        echo  IMPORTANT: Check "Add Python to PATH"
        echo  during installation!
        echo  ===========================================
        echo.
        echo  After installing Python, run this installer again.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  ===========================================
    echo  Python was installed successfully!
    echo  BUT you need to restart this installer
    echo  so it picks up the new PATH.
    echo.
    echo  Please CLOSE this window and
    echo  DOUBLE-CLICK install.bat again.
    echo  ===========================================
    echo.
    pause
    exit /b 0
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo  OK: %%i

:: ============================================
:: Step 2: Check Node.js
:: ============================================
echo.
echo  [2/6] Checking Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Node.js is not installed.
    echo  Installing via winget...
    echo.
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo  ===========================================
        echo  Could not install Node.js automatically.
        echo  Please download it manually from:
        echo.
        echo    https://nodejs.org/
        echo  ===========================================
        echo.
        echo  After installing Node.js, run this installer again.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  ===========================================
    echo  Node.js was installed successfully!
    echo  BUT you need to restart this installer
    echo  so it picks up the new PATH.
    echo.
    echo  Please CLOSE this window and
    echo  DOUBLE-CLICK install.bat again.
    echo  ===========================================
    echo.
    pause
    exit /b 0
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo  OK: Node.js %%i

:: ============================================
:: Step 3: Install Claude Code
:: ============================================
echo.
echo  [3/6] Installing Claude Code...
echo  (this may take a minute)
echo.
call npm install -g @anthropic-ai/claude-code 2>nul
claude --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ===========================================
    echo  Claude Code could not be installed.
    echo  Try running this as Administrator:
    echo    Right-click install.bat - Run as administrator
    echo  ===========================================
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('claude --version 2^>^&1') do echo  OK: Claude Code %%i

:: ============================================
:: Step 4: Claude Login
:: ============================================
echo.
echo  [4/6] Checking Claude subscription...
echo.
claude auth status 2>nul | findstr /C:"loggedIn" /C:"true" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Already logged in to Claude!
) else (
    echo  You need to log in to your Claude account.
    echo  A browser window will open now.
    echo  Sign in with your Claude Max or Pro account.
    echo.
    echo  Press any key to open the login page...
    pause >nul
    call claude auth login
    if %errorlevel% neq 0 (
        echo.
        echo  Login may not have completed.
        echo  You can try again later with: claude auth login
    )
)

:: ============================================
:: Step 5: Install AgelClaw
:: ============================================
echo.
echo  [5/6] Installing AgelClaw package...
echo  (downloading from GitHub, may take a minute)
echo.
pip install "git+https://github.com/sdrakos/AgelClaw.git" 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ===========================================
    echo  AgelClaw installation failed.
    echo  Make sure you have internet and try again.
    echo  ===========================================
    echo.
    pause
    exit /b 1
)
echo.
for /f "tokens=*" %%i in ('agelclaw --version 2^>^&1') do echo  OK: %%i

:: ============================================
:: Step 6: Initialize project in chosen folder
:: ============================================
echo.
echo  [6/6] Setting up AgelClaw in: %INSTALL_DIR%
echo.
agelclaw init "%INSTALL_DIR%"

:: ============================================
:: Create desktop shortcut
:: ============================================
echo.
echo  Creating desktop shortcut...
set "DESKTOP=%USERPROFILE%\Desktop"
(
echo @echo off
echo title AgelClaw - AI Agent
echo set "AGELCLAW_HOME=%INSTALL_DIR%"
echo echo.
echo echo  Starting AgelClaw...
echo echo  Type 'quit' to exit.
echo echo.
echo agelclaw
echo pause
) > "%DESKTOP%\AgelClaw.bat"

:: ============================================
:: Save install path for future reference
:: ============================================
echo %INSTALL_DIR%> "%INSTALL_DIR%\.install_path"

:: ============================================
:: Final summary
:: ============================================
echo.
echo.
echo  ==========================================
echo       Installation Complete!
echo  ==========================================
echo.
echo  What was installed:
echo.
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo    - %%i
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo    - Node.js %%i
for /f "tokens=*" %%i in ('claude --version 2^>^&1') do echo    - Claude Code %%i
for /f "tokens=*" %%i in ('agelclaw --version 2^>^&1') do echo    - %%i
echo.
echo  ==========================================
echo  Installed to:
echo    %INSTALL_DIR%
echo.
echo  Desktop shortcut:
echo    %DESKTOP%\AgelClaw.bat
echo  ==========================================
echo.
echo  HOW TO USE:
echo.
echo    Option 1: Double-click "AgelClaw" on your Desktop
echo    Option 2: Open CMD and type "agelclaw"
echo    Option 3: Type "agelclaw telegram" for Telegram bot
echo.
echo  ==========================================
echo.

set /p RUNSETUP="  Configure API keys now? (Y/n): "
if /i "%RUNSETUP%" neq "n" (
    echo.
    agelclaw setup
)

echo.
echo  ==========================================
echo  All done! You can close this window.
echo  To chat, double-click AgelClaw on Desktop.
echo  ==========================================
echo.
pause
