@echo off
setlocal EnableExtensions EnableDelayedExpansion

wpeinit

if exist X:\Windows\System32\winpe-config.cmd call X:\Windows\System32\winpe-config.cmd

if "%DEPLOY_SERVER%"=="" set DEPLOY_SERVER=SERVER_IP_OR_HOSTNAME
if "%DEPLOY_SHARE%"=="" set DEPLOY_SHARE=osshare
if "%SMB_USER%"=="" set SMB_USER=imaging
if "%SMB_PASS%"=="" set SMB_PASS=change-me
if "%DISK_INDEX%"=="" set DISK_INDEX=0
if "%WINDOWS_VOLUME_INDEX%"=="" set WINDOWS_VOLUME_INDEX=0

echo Waiting for network...
ping -n 6 127.0.0.1 >nul

echo Mapping NAS...
net use Z: \\%DEPLOY_SERVER%\%DEPLOY_SHARE% /user:%SMB_USER% %SMB_PASS%
if errorlevel 1 (
    echo ERROR: Cannot map NAS
    pause
    exit /b 1
)

echo.
echo Volumes:
diskpart /s X:\Windows\System32\findwin.txt

echo.
echo Assigning drive letter to Windows partition...
(
 echo select disk %DISK_INDEX%
 echo select volume %WINDOWS_VOLUME_INDEX%
 echo assign letter=W
 echo exit
) | diskpart

set WINVOL=W:
if not exist %WINVOL%\Windows\System32 (
    echo ERROR: %WINVOL%\Windows\System32 not found
    pause
    exit /b 1
)

for /f "tokens=1-4 delims=/.- " %%a in ("%date%") do (
    set D1=%%a
    set D2=%%b
    set D3=%%c
    set D4=%%d
)
for /f "tokens=1-3 delims=:." %%a in ("%time%") do (
    set HH=%%a
    set MN=%%b
    set SS=%%c
)

set HH=%HH: =0%
set TS=%D1%_%D2%_%D3%_%D4%_%HH%%MN%%SS%
set IMAGE=Z:\captured\new_image_%TS%.wim

echo Capturing %WINVOL% to WIM...
echo Saving to: %IMAGE%

dism /capture-image ^
  /imagefile:%IMAGE% ^
  /capturedir:%WINVOL%\ ^
  /name:"Captured Image %TS%" ^
  /compress:max ^
  /checkintegrity

if errorlevel 1 (
    echo ERROR: Capture failed
    pause
    exit /b 1
)

echo Capture complete!
echo %IMAGE%
pause
