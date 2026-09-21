[CmdletBinding()]
param(
    [ValidateSet('onefile', 'onedir')]
    [string]$Format = 'onefile'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Always build relative to this script, regardless of the caller's directory.
$ProjectRoot = $PSScriptRoot
$EntryPoint = Join-Path $ProjectRoot 'src\gui_entry.py'
$IconPath = Join-Path $ProjectRoot 'assets\favicon.ico'
$OutputDirectory = Join-Path $ProjectRoot 'dist'
$WorkDirectory = Join-Path $ProjectRoot 'build\pyinstaller'
$SpecDirectory = Join-Path $ProjectRoot 'build'
$Executable = Join-Path $OutputDirectory 'SteamControllerCalibration.exe'

# Use python from the already activated Conda environment. The executable path
# is printed so an accidental build from another interpreter is easy to spot.
$Python = (Get-Command python -ErrorAction Stop).Source
Write-Host "Packaging with: $Python"
$CondaPrefix = Split-Path -Parent $Python

# Windows PowerShell can promote a native program's stderr to a terminating
# NativeCommandError under Stop, so judge native tools by their exit codes.
$ErrorActionPreference = 'Continue'
& $Python -c 'import PyInstaller, sdl3' *> $null
$DependencyExitCode = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($DependencyExitCode -ne 0) {
    throw 'The active environment needs PyInstaller and PySDL3. Run: python -m pip install -r requirements-build.txt -r requirements.txt'
}

$BundleFlag = if ($Format -eq 'onedir') { '--onedir' } else { '--onefile' }
# Some newer Conda Python builds use Tcl/Tk 9 DLL names that PyInstaller's
# automatic hook cannot resolve. Add those runtime files explicitly so
# _tkinter can load in the packaged process.
$TkRuntimeArguments = @()
foreach ($DllName in @('tcl90.dll', 'tcl9tk90.dll', 'libtommath.dll', 'ffi.dll', 'libmpdec-4.dll')) {
    $DllPath = Join-Path $CondaPrefix "Library\bin\$DllName"
    if (Test-Path -LiteralPath $DllPath -PathType Leaf) {
        $TkRuntimeArguments += @('--add-binary', "$DllPath;.")
    }
}
foreach ($DataName in @('tcl9.0', 'tk9.0', 'tcl9')) {
    $DataPath = Join-Path $CondaPrefix "Library\lib\$DataName"
    if (Test-Path -LiteralPath $DataPath -PathType Container) {
        $TkRuntimeArguments += @('--add-data', "$DataPath;$DataName")
    }
}

$Arguments = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    $BundleFlag,
    '--name', 'SteamControllerCalibration',
    '--icon', $IconPath,
    '--paths', $ProjectRoot,
    '--collect-all', 'sdl3',
    '--add-data', "$(Join-Path $ProjectRoot 'assets');assets",
    '--distpath', $OutputDirectory,
    '--workpath', $WorkDirectory,
    '--specpath', $SpecDirectory
) + $TkRuntimeArguments + @($EntryPoint)

$ErrorActionPreference = 'Continue'
& $Python @Arguments
$BuildExitCode = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($BuildExitCode -ne 0) {
    throw "PyInstaller failed with exit code $BuildExitCode"
}

$ExpectedOutput = if ($Format -eq 'onedir') {
    Join-Path $OutputDirectory 'SteamControllerCalibration\SteamControllerCalibration.exe'
} else {
    $Executable
}
if (-not (Test-Path -LiteralPath $ExpectedOutput -PathType Leaf)) {
    throw "Packaging finished without producing the expected executable: $ExpectedOutput"
}

Write-Host "Created: $ExpectedOutput" -ForegroundColor Green
