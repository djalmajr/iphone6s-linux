param(
    [Parameter(Mandatory=$true)][string]$ServerAddress,
    [string]$ExpectedAddress = '172.16.42.1',
    [string]$Name = 'iphone-usb.home.arpa',
    [ValidateRange(1024,65535)][int]$Port = 1053
)
$ErrorActionPreference = 'Stop'

function Get-PrivateAddress([string]$Value) {
    $address = $null
    if (-not [Net.IPAddress]::TryParse($Value, [ref]$address) -or
        $address.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
        throw 'An explicit private IPv4 address is required.'
    }
    $octets = $address.GetAddressBytes()
    if (-not ($octets[0] -eq 10 -or
              ($octets[0] -eq 172 -and $octets[1] -ge 16 -and $octets[1] -le 31) -or
              ($octets[0] -eq 192 -and $octets[1] -eq 168))) {
        throw 'Public, wildcard and loopback addresses are refused.'
    }
    return $address.ToString()
}

function Invoke-DnsQuery([hashtable]$Query) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Query.Tool
    $info.Arguments = '-port=' + $Port + ' -timeout=2 -retry=1 -type=A ' +
                      $Query.Mode + ' ' + $Name + '. ' + $ServerAddress
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    try {
        if (-not $process.Start()) { throw 'nslookup did not start.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(15000)) {
            $process.Kill()
            $process.WaitForExit()
            throw 'nslookup exceeded its deadline.'
        }
        $text = $stdout.GetAwaiter().GetResult()
        $errors = $stderr.GetAwaiter().GetResult()
        $answer = [regex]::Match($text, '(?im)^(?:Name|Nome)\s*:\s*' +
                                 [regex]::Escape($Name) + '\.?\s*\r?$')
        if ($process.ExitCode -ne 0 -or -not $answer.Success) {
            throw ('Expected DNS name missing: ' + $text + $errors)
        }
        $records = $text.Substring($answer.Index + $answer.Length)
        if ($records -notmatch ('(?<![0-9.])' + [regex]::Escape($ExpectedAddress) + '(?![0-9.])')) {
            throw ('Expected address missing from answer section: ' + $records)
        }
        Write-Output ('IPHONE_DNS_' + $Query.Protocol + '_OK')
    } finally {
        $process.Dispose()
    }
}

$ServerAddress = Get-PrivateAddress $ServerAddress
$ExpectedAddress = Get-PrivateAddress $ExpectedAddress
$Name = $Name.ToLowerInvariant().TrimEnd('.')
if ($Name.Length -gt 253 -or $Name -notmatch '\.home\.arpa$' -or
    @($Name.Split('.') | Where-Object { $_ -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$' }).Count) {
    throw 'Only valid home.arpa names are accepted.'
}
$tool = Join-Path $env:SystemRoot 'System32\nslookup.exe'
$signature = Get-AuthenticodeSignature -LiteralPath $tool
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') {
    throw 'The native Microsoft nslookup signature could not be verified.'
}
Invoke-DnsQuery @{Tool=$tool; Mode='-novc'; Protocol='UDP'}
Invoke-DnsQuery @{Tool=$tool; Mode='-vc'; Protocol='TCP'}
