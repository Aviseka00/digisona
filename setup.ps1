param([switch]$CpuOnly,[switch]$BootstrapOnly)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (![Environment]::Is64BitOperatingSystem) { throw 'Digisona requires 64-bit Windows.' }
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$taskRuntime=Join-Path $PSScriptRoot '.runtime'
$taskBootstrap=Join-Path $taskRuntime 'bootstrap'
New-Item -ItemType Directory -Force -Path $taskBootstrap | Out-Null
$env:UV_PYTHON_INSTALL_DIR=Join-Path $taskRuntime 'python'
$env:UV_CACHE_DIR=Join-Path $PSScriptRoot '.cache/uv'
function Invoke-Checked {
    param([string]$Executable,[string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Installation failed: $Executable $($Arguments -join ' '). Rerun install.cmd to retry." }
}
function Download-Checked {
    param([string]$Url,[string]$Destination)
    for ($attempt=1;$attempt -le 3;$attempt++) {
        try { Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile "$Destination.partial"; Move-Item -LiteralPath "$Destination.partial" -Destination $Destination -Force; return }
        catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds 2 }
    }
}
$taskUv=Join-Path $taskBootstrap 'uv.exe'
if (!(Test-Path -LiteralPath $taskUv)) {
    Write-Host '[1/7] Downloading the local Python installer (uv 0.13.0)...'
    $taskArchive=Join-Path $taskBootstrap 'uv.zip'
    Download-Checked 'https://github.com/astral-sh/uv/releases/download/0.13.0/uv-x86_64-pc-windows-msvc.zip' $taskArchive
    $taskExpected='088962f9e7b7bd9ea740c04c650b2a21c8928c345bd99ac24350dc924dba656c'
    if ((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskExpected) { throw 'uv download checksum mismatch. Installation stopped.' }
    Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskBootstrap -Force
}
Write-Host '[2/7] Installing private Python 3.11 and 3.8 runtimes...'
Invoke-Checked $taskUv @('python','install','3.11','3.8','--no-bin','--no-registry')
if (!(Test-Path '.venv/Scripts/python.exe')) { Invoke-Checked $taskUv @('venv','--python','3.11','--managed-python','--seed','.venv') }
if (!(Test-Path '.venv-sad/Scripts/python.exe')) { Invoke-Checked $taskUv @('venv','--python','3.8','--managed-python','--seed','.venv-sad') }
if ($BootstrapOnly) { Write-Host 'Python bootstrap verified. Models were not installed.'; exit 0 }
if (!(Test-Path 'config.json')) { Copy-Item -LiteralPath 'config.example.json' -Destination 'config.json' }
$taskConfig=Get-Content 'config.json' -Raw | ConvertFrom-Json
$taskCpu=$CpuOnly -or !(Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$taskConfig | Add-Member -NotePropertyName render_device -NotePropertyValue $(if ($taskCpu) {'cpu'} else {'auto'}) -Force
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'config.json'),($taskConfig | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
Write-Host '[3/7] Fetching the pinned face-engine source...'
if (!(Test-Path 'models/SadTalker/inference.py')) {
    $taskCommit='cd4c0465ae0b54a6f85af57f5c65fec9fe23e7f8'
    $taskSource=Join-Path $taskBootstrap 'sadtalker.zip'
    Download-Checked "https://github.com/OpenTalker/SadTalker/archive/$taskCommit.zip" $taskSource
    Expand-Archive -LiteralPath $taskSource -DestinationPath $taskBootstrap -Force
    New-Item -ItemType Directory -Force -Path 'models/SadTalker' | Out-Null
    Copy-Item -Path (Join-Path $taskBootstrap "SadTalker-$taskCommit/*") -Destination 'models/SadTalker' -Recurse -Force
}
Write-Host '[4/7] Installing voice packages...'
Invoke-Checked '.venv/Scripts/python.exe' @('-m','pip','install','pip==25.0.1','setuptools==69.5.1','wheel')
Invoke-Checked '.venv/Scripts/python.exe' @('-m','pip','install','-r','requirements-voice.txt')
Write-Host '[5/7] Installing face packages...'
Invoke-Checked '.venv-sad/Scripts/python.exe' @('-m','pip','install','pip==25.0.1','setuptools==69.5.1','wheel')
if ($taskCpu) {
    Invoke-Checked '.venv-sad/Scripts/python.exe' @('-m','pip','install','torch==1.12.1+cpu','torchvision==0.13.1+cpu','torchaudio==0.12.1','--extra-index-url','https://download.pytorch.org/whl/cpu')
} else {
    Invoke-Checked '.venv-sad/Scripts/python.exe' @('-m','pip','install','torch==1.12.1+cu113','torchvision==0.13.1+cu113','torchaudio==0.12.1','--extra-index-url','https://download.pytorch.org/whl/cu113')
}
Invoke-Checked '.venv-sad/Scripts/python.exe' @('-m','pip','install','-r','requirements-face.txt')
Write-Host '[6/7] Downloading face weights and local FFmpeg...'
Invoke-Checked '.venv/Scripts/python.exe' @('download_assets.py')
Write-Host '[7/7] Downloading voice weights and verifying model loading...'
Invoke-Checked '.venv/Scripts/python.exe' @('verify_install.py')
Write-Host 'Digisona is installed. Double-click start.cmd.'
