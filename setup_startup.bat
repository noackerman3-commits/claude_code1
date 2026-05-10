@echo off
title Setup Startup Shortcut
cd /d "%~dp0"

echo Creating startup shortcut for Rental Agent...

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $startup = $ws.SpecialFolders('Startup'); ^
   $sc = $ws.CreateShortcut($startup + '\RentalAgent.lnk'); ^
   $sc.TargetPath = '%~dp0start_agent.bat'; ^
   $sc.WorkingDirectory = '%~dp0'; ^
   $sc.Description = 'Rental Agent Bot'; ^
   $sc.Save(); ^
   Write-Host 'Done.'"

echo.
echo Shortcut created! The agent will now start automatically on login.
echo You can also run start_agent.bat manually at any time.
pause
