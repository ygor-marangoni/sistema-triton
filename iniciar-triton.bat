@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-triton.ps1"
if errorlevel 1 (
  echo Nao foi possivel iniciar o Triton. Confira a mensagem acima.
  pause
)
