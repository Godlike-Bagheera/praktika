@echo off
REM ============================================================
REM forum setup for Windows host (VirtualBox VM, NAT port-forward)
REM Kladite etot skript ryadom s forum_backup_*.tar.gz i zapustite.
REM Trebuyutsya: VirtualBox (VBoxManage v PATH) + ssh/scp (Windows 10+).
REM Peremennye okruzheniya: VM_NAME, USER, VM_PASS
REM ============================================================
setlocal enabledelayedexpansion
set VM_NAME=%VM_NAME%
if "%VM_NAME%"=="" set /p VM_NAME=Imya VM v VirtualBox: 
set SSH_USER=%SSH_USER%
if "%SSH_USER%"=="" set /p SSH_USER=Linux-user v VM (naprimer user): 
set SSH_PORT=2222

echo [1/5] Proverka VirtualBox...
where VBoxManage >nul 2>&1 || (echo NET VBoxManage v PATH. Ispolzyuyte polny put: "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" & exit /b 1)

echo [2/5] Zapusk VM...
VBoxManage showvminfo "%VM_NAME%" --machinereadable | findstr /^VMState=/ | findstr running >nul 2>&1
if errorlevel 1 (
  echo   VM ne zapushchena - vpislyayu...
  set /p VM_PASS=Parol dlya %SSH_USER%@VM: 
  VBoxManage startvm "%VM_NAME%" --type headless
  echo   Zhdu zapuska (30 sek)...
  timeout /t 30 /nobreak >nul
)

echo [3/5] Probros porta 8084 (NAT forum)...
VBoxManage showvminfo "%VM_NAME%" --machinereadable | findstr /c:"natpf1 \"forum\"" >nul 2>&1
if errorlevel 1 VBoxManage controlvm "%VM_NAME%" natpf1 "forum,tcp,,8084,,8084"

echo [4/5] Skladivayu setup.sh v VM...
scp -P %SSH_PORT% setup.sh %SSH_USER%@10.0.2.15:setup.sh 2>nul
if errorlevel 1 (
  echo   Net setup.sh ryadom. Snachala: git clone https://github.com/Godlike-Bagheera/praktika
  echo   ili peredayte faily iz arkhiva békapa.
)

echo [5/5] Razvertyvanie na VM...
echo   Vypolnite VTORIM OKONOM (ili pravym klikom v Git Bash):
echo     ssh -p %SSH_PORT% %SSH_USER%@10.0.2.15
echo     cd praktika ^&^& bash scripts/setup.sh forum_backup_*.tar.gz
echo.
echo Gotovyy sayt budet po adresu: http://localhost:8084
pause
