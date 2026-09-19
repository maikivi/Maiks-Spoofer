$ErrorActionPreference = "Stop"

Write-Host "Building Spoofer.exe..."
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --console --name Spoofer --distpath . spoof.py

Write-Host ""
Write-Host "Built: Spoofer.exe"