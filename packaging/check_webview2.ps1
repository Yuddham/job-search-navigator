# Installs the Microsoft Edge WebView2 Runtime if it isn't already present.
# Windows 11 ships with WebView2 as a core OS component in the vast majority
# of cases, so this is a defensive fallback, not the common path. Fetches
# Microsoft's small (~2MB) official Evergreen bootstrapper at install time
# rather than bundling a third-party binary in this repo.

$clientId = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
$paths = @(
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$clientId",
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$clientId",
    "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$clientId"
)

$installed = $false
foreach ($path in $paths) {
    if (Test-Path $path) {
        $installed = $true
        break
    }
}

if ($installed) {
    exit 0
}

$bootstrapper = Join-Path $env:TEMP "MicrosoftEdgeWebview2Setup.exe"
try {
    Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $bootstrapper -UseBasicParsing
    Start-Process -FilePath $bootstrapper -ArgumentList "/silent", "/install" -Wait
} catch {
    # Non-fatal: if this fails (e.g. no internet at install time), Navigrad
    # will simply fail to open its window until WebView2 is installed some
    # other way -- don't block the rest of setup over it.
    exit 0
} finally {
    Remove-Item -Path $bootstrapper -ErrorAction SilentlyContinue
}
