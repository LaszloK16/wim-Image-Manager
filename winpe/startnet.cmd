@echo off
setlocal EnableExtensions EnableDelayedExpansion

wpeinit

if exist X:\Windows\System32\winpe-config.cmd call X:\Windows\System32\winpe-config.cmd

if "%DEPLOY_SERVER%"=="" set DEPLOY_SERVER=SERVER_IP_OR_HOSTNAME
if "%DEPLOY_SHARE%"=="" set DEPLOY_SHARE=osshare
if "%SMB_USER%"=="" set SMB_USER=imaging
if "%SMB_PASS%"=="" set SMB_PASS=change-me
if "%PUBLISHED_WIM%"=="" set PUBLISHED_WIM=install.wim
if "%IMAGE_INDEX%"=="" set IMAGE_INDEX=1
if "%DISK_INDEX%"=="" set DISK_INDEX=0
if "%BOOT_MODE%"=="" set BOOT_MODE=UEFI
if "%TAG%"=="" set TAG=LaszloK

echo.
echo ========================================
echo   %TAG% DEPLOYMENT TOOL
echo ========================================
echo.
echo 1 - Install image from server
echo 2 - Capture current system to image
echo.
set /p CHOICE=Select option:

if "%CHOICE%"=="1" goto INSTALL
if "%CHOICE%"=="2" goto CAPTURE

echo Invalid choice
ping -n 3 127.0.0.1 >nul
goto :eof

:INSTALL
wpeinit

echo Waiting for network...
ping -n 6 127.0.0.1 >nul

echo Mapping deployment share...
net use Z: \\%DEPLOY_SERVER%\%DEPLOY_SHARE% /user:%SMB_USER% %SMB_PASS%
if errorlevel 1 (
    echo ERROR: Could not map network share
    pause
    exit /b 1
)

set IMAGE=Z:\%PUBLISHED_WIM%
if not exist "%IMAGE%" (
    echo ERROR: image not found: %IMAGE%
    pause
    exit /b 1
)

if /I "%BOOT_MODE%"=="BIOS" (
  set DPKT=X:\Windows\System32\diskpart_bios.txt
) else (
  set DPKT=X:\Windows\System32\diskpart_uefi.txt
)

echo WARNING: This will wipe Disk %DISK_INDEX% using %BOOT_MODE% layout.
ping -n 4 127.0.0.1 >nul

diskpart /s %DPKT%
if errorlevel 1 (
    echo ERROR: disk preparation failed
    pause
    exit /b 1
)

dism /apply-image /imagefile:%IMAGE% /index:%IMAGE_INDEX% /applydir:C:\
if errorlevel 1 (
    echo ERROR: image apply failed
    pause
    exit /b 1
)

bcdboot C:\Windows /s S: /f %BOOT_MODE%
if errorlevel 1 (
    echo ERROR: bcdboot failed
    pause
    exit /b 1
)

echo Done. Rebooting...
ping -n 6 127.0.0.1 >nul
wpeutil reboot

:CAPTURE
call X:\Windows\System32\capture.cmd
goto :eof
