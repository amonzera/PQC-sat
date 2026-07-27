<#
Prepara e inicia o PQC-SAT nativamente no Windows.

Uso (PowerShell, na raiz do repositório):
  Set-ExecutionPolicy -Scope Process Bypass
  .\tools\run_windows.ps1
  .\tools\run_windows.ps1 -Port COM3
  .\tools\run_windows.ps1 -Port COM3 -UploadFirmware

O upload é opt-in porque grava a flash da BlackBoard Wisdom.
#>
[CmdletBinding()]
param(
    [string]$Port,
    [switch]$UploadFirmware,
    [switch]$Windowed,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Find-PythonLauncher {
    foreach ($candidate in @('3.14', '3')) {
        & py "-$candidate" --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @('py', "-$candidate")
        }
    }
    throw 'Python 3 não foi encontrado. Instale-o em https://www.python.org/downloads/windows/ e marque "Add python.exe to PATH".'
}

$pythonLauncher = Find-PythonLauncher
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Host 'Criando ambiente virtual .venv...'
    & $pythonLauncher[0] $pythonLauncher[1] -m venv .venv
}

if (-not $SkipInstall) {
    Write-Host 'Instalando dependências do jogo e hardware...'
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt -r requirements-hardware.txt
}

Write-Host "`nPortas seriais detectadas pelo Windows:"
$ports = [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object
if ($ports.Count -eq 0) {
    throw @'
Nenhuma porta COM foi criada pelo Windows.
Conecte a Wisdom diretamente a uma porta USB (cabo de dados, não apenas carga) e instale o driver Silicon Labs CP210x:
https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
Depois desconecte/reconecte a placa e rode este script novamente.
'@
}
$ports | ForEach-Object { Write-Host "  $_" }

if (-not $Port) {
    if ($ports.Count -eq 1) {
        $Port = $ports[0]
        Write-Host "Usando a única porta encontrada: $Port"
    } else {
        Write-Host "Mais de uma porta encontrada; o dashboard vai identificar a Wisdom por HELLO."
    }
} elseif ($ports -notcontains $Port) {
    throw "A porta solicitada ($Port) não existe. Use uma das portas mostradas acima."
}

if ($UploadFirmware) {
    if (-not $Port) {
        throw '-UploadFirmware requer -Port COMx explícita para evitar gravar o dispositivo errado.'
    }
    Write-Host "`nCompilando e gravando firmware em $Port..."
    & $venvPython tools/firmware_deploy.py --upload --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Falha no build ou upload do firmware.' }
}

Write-Host "`nVerificando a identidade da Wisdom..."
$diagnosticArgs = @('tools/stand_diagnostics.py', '--check-only')
if ($Port) { $diagnosticArgs += @('--port', $Port) }
& $venvPython @diagnosticArgs
if ($LASTEXITCODE -ne 0) {
    throw 'A porta existe, mas não respondeu como a Wisdom com o firmware STAGED_V1/FAIR_V1 atual. Veja a mensagem acima; para gravar o firmware use -UploadFirmware.'
}

Write-Host "`nIniciando PQC-SAT..."
$dashboardArgs = @('dashboard.py')
if ($Port) { $dashboardArgs += @('--port', $Port) }
if ($Windowed) { $dashboardArgs += '--windowed' }
& $venvPython @dashboardArgs
