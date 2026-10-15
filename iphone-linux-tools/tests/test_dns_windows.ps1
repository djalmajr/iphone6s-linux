param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$Case,
    [string]$Mutation,
    [switch]$RunMutations
)
$ErrorActionPreference = 'Stop'

$mutations = @(
    @{Name='standard-port-denied'; Case='standard-port'; Old='(options.Port != 53 && options.Port < 1024)'; New='options.Port < 1024'},
    @{Name='reserved-port-open'; Case='reserved-port'; Old='(options.Port != 53 && options.Port < 1024)'; New='options.Port < 0'},
    @{Name='identity'; Case='identity'; Old='id != query.Message[0] * 256 + query.Message[1]'; New='false'},
    @{Name='flags'; Case='rcode'; Old='(flags & 0x8000) == 0 || (flags & 0x7a4f) != 0 || (flags & 0x0100) != 0'; New='false'},
    @{Name='question-count'; Case='question-count'; Old='questions != 1 || answers + authority + additional > 64'; New='answers + authority + additional > 64'},
    @{Name='record-count'; Case='record-count'; Old='questions != 1 || answers + authority + additional > 64'; New='questions != 1'},
    @{Name='question-name'; Case='question-name'; Old='reader.Name(message.Length) != query.Name'; New='reader.Name(message.Length) == null'},
    @{Name='question-type'; Case='question-type'; Old='reader.U16() != 1 || reader.U16() != 1'; New='reader.U16() < 0 || reader.U16() != 1'},
    @{Name='question-class'; Case='question-class'; Old='reader.U16() != 1 || reader.U16() != 1'; New='reader.U16() != 1 || reader.U16() < 0'},
    @{Name='owner'; Case='owner'; Old='name != context.Query.Name'; New='false'},
    @{Name='address'; Case='address'; Old='!new IPAddress(address).Equals(context.Query.Expected)'; New='false'},
    @{Name='record-class'; Case='record-class'; Old='type != 41 && group != 1'; New='false'},
    @{Name='a-size'; Case='rdlength-long'; Old='length != 4'; New='length < 0'},
    @{Name='trailing'; Case='trailing'; Old='context.Matches == 0 || reader.Offset != message.Length'; New='context.Matches == 0'},
    @{Name='missing-answer'; Case='no-answer'; Old='context.Matches == 0 || reader.Offset != message.Length'; New='reader.Offset != message.Length'},
    @{Name='compression'; Case='pointer-forward'; Old='target < 12 || target >= start || !labels.Contains(target)'; New='false'},
    @{Name='message-limit'; Case='oversized'; Old='message.Length < 12 || message.Length > MaximumMessage'; New='message.Length < 12'},
    @{Name='deadline'; Case='tcp-drip'; Old='DeadlineMilliseconds - (int)clock.ElapsedMilliseconds'; New='DeadlineMilliseconds'},
    @{Name='random-id'; Case='query-id'; Old='random.GetBytes(id);'; New='GC.KeepAlive(random);'},
    @{Name='private-range'; Case='private-address'; Old='!(b[0] == 10 || b[0] == 172 && b[1] >= 16 && b[1] <= 31 ||'; New='b.Length == 0 && !(b[0] == 10 || b[0] == 172 && b[1] >= 16 && b[1] <= 31 ||'}
)

function Invoke-TestChild([hashtable]$Options) {
    $tool = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $signature = Get-AuthenticodeSignature -LiteralPath $tool
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') {
        throw 'Native PowerShell signature verification failed.'
    }
    $testPath = Join-Path $PSScriptRoot 'test_dns_windows.ps1'
    if ($testPath.Contains('"') -or $Root.Contains('"')) { throw 'Invalid test path.' }
    $arguments = '-NoProfile -NonInteractive -File "' + $testPath + '" -Root "' + $Root + '"'
    if ($Options.Mutation) { $arguments += ' -Case "' + $Options.Case + '" -Mutation "' + $Options.Mutation + '"' }
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $tool
    $info.Arguments = $arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    try {
        if (-not $process.Start()) { throw 'Test child did not start.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(90000)) {
            $process.Kill()
            $process.WaitForExit()
            throw 'Test child deadline exceeded.'
        }
        return @{Exit=$process.ExitCode; Output=$stdout.GetAwaiter().GetResult(); Error=$stderr.GetAwaiter().GetResult()}
    } finally {
        $process.Dispose()
    }
}

try {
    if ($RunMutations) {
        $baseline = Invoke-TestChild @{}
        if ($baseline.Exit -ne 0 -or $baseline.Output -notmatch 'DNS_CLIENT_BASELINE_PASS cases=') {
            throw ('Baseline failed: ' + $baseline.Output + $baseline.Error)
        }
        Write-Output $baseline.Output.Trim()
        foreach ($item in $mutations) {
            $result = Invoke-TestChild @{Mutation=$item.Name; Case=$item.Case}
            if ($result.Exit -ne 1 -or $result.Output -notmatch ('DNS_TEST_ASSERTION ' + [regex]::Escape($item.Case) + ':')) {
                throw ('Mutation survived or did not fail by assertion: ' + $item.Name + ' ' + $result.Output + $result.Error)
            }
            Write-Output ('DNS_MUTATION_REJECTED ' + $item.Name)
        }
        Write-Output ('DNS_MUTATIONS_PASS count=' + $mutations.Count)
        exit 0
    }
    $helper = Join-Path $Root 'scripts\host\dns-check-windows.ps1'
    $tokens = $null
    $parseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw 'Helper PowerShell syntax failed.' }
    $source = [IO.File]::ReadAllText((Join-Path $Root 'scripts\host\dns_windows.cs'))
    if ($Mutation) {
        $selected = @($mutations | Where-Object { $_.Name -ceq $Mutation })
        if ($selected.Count -ne 1 -or $selected[0].Case -cne $Case) { throw 'Unknown mutation or wrong target case.' }
        $item = $selected[0]
        if ([regex]::Matches($source, [regex]::Escape($item.Old)).Count -ne 1) { throw 'Mutation anchor is not unique.' }
        $source = $source.Replace($item.Old, $item.New)
    }
    $fixture = [IO.File]::ReadAllText((Join-Path $Root 'tests\dns_windows_fixture.cs'))
    Add-Type -TypeDefinition ($source + [Environment]::NewLine + $fixture) -Language CSharp -ErrorAction Stop
    $cases = if ($Case) { @($Case) } else { @([IphoneDns.DnsHarness]::Cases()) }
    foreach ($name in $cases) {
        if ([IphoneDns.DnsHarness]::Cases() -cnotcontains $name) { throw 'Unknown test case.' }
        [IphoneDns.DnsHarness]::RunOne($name)
    }
    Write-Output ('DNS_CLIENT_BASELINE_PASS cases=' + $cases.Count)
} catch {
    $cause = $_.Exception
    while ($cause.InnerException) { $cause = $cause.InnerException }
    if ($cause.GetType().FullName -eq 'IphoneDns.DnsAssertionException') {
        Write-Output ('DNS_TEST_ASSERTION ' + $Case + ': ' + $cause.Message)
        exit 1
    }
    Write-Output ('DNS_TEST_ERROR ' + $cause.GetType().Name + ': ' + $cause.Message)
    exit 2
}
