param(
    [Parameter(Mandatory=$true)][string]$ServerAddress,
    [string]$ExpectedAddress = '172.16.42.1',
    [string]$Name = 'iphone-usb.home.arpa',
    [ValidateRange(53,65535)][int]$Port = 1053
)
$ErrorActionPreference = 'Stop'

$sourcePath = Join-Path $PSScriptRoot 'dns_windows.cs'
$sourceBytes = [IO.File]::ReadAllBytes($sourcePath)
$hash = [Security.Cryptography.SHA256]::Create()
try {
    $digest = [BitConverter]::ToString($hash.ComputeHash($sourceBytes)).Replace('-', '')
} finally {
    $hash.Dispose()
}
$source = [Text.Encoding]::UTF8.GetString($sourceBytes)
if ('IphoneDns.Client' -as [type]) {
    if (-not ('IphoneDns.SourceRevision' -as [type]) -or [IphoneDns.SourceRevision]::Value -cne $digest) {
        throw 'DNS source changed or was loaded elsewhere; start a new PowerShell session.'
    }
} else {
    $revision = 'namespace IphoneDns { public static class SourceRevision { public const string Value = "' + $digest + '"; } }'
    Add-Type -TypeDefinition ($source + [Environment]::NewLine + $revision) -Language CSharp -ErrorAction Stop
}
$options = New-Object IphoneDns.QueryOptions
$options.ServerAddress = $ServerAddress
$options.ExpectedAddress = $ExpectedAddress
$options.Name = $Name
$options.Port = $Port
[IphoneDns.Client]::Check($options, $false)
Write-Output 'IPHONE_DNS_UDP_OK'
[IphoneDns.Client]::Check($options, $true)
Write-Output 'IPHONE_DNS_TCP_OK'
