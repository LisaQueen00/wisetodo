param([Parameter(Mandatory = $true)][int]$AppProcessId)
$ErrorActionPreference = 'Stop'
# Read-only snapshot of the explicitly selected app and its descendants.
$appProcess = Get-Process -Id $AppProcessId
if ($appProcess.ProcessName -ne 'wisetodo') { throw 'Choose the wisetodo.exe process ID.' }
$snapshot = @(Get-CimInstance Win32_Process)
$selected = [System.Collections.Generic.HashSet[int]]::new()
[void]$selected.Add($AppProcessId)
do {
    $added = $false
    foreach ($entry in $snapshot) {
        if ($selected.Contains([int]$entry.ParentProcessId) -and $selected.Add([int]$entry.ProcessId)) {
            $added = $true
        }
    }
} while ($added)
$rows = foreach ($processIdValue in $selected) {
    $entry = Get-Process -Id $processIdValue -ErrorAction SilentlyContinue
    if ($null -ne $entry) {
        [pscustomobject]@{
            Id = $entry.Id
            Name = $entry.ProcessName
            PrivateMiB = [math]::Round($entry.PrivateMemorySize64 / 1MB, 2)
            WorkingSetMiB = [math]::Round($entry.WorkingSet64 / 1MB, 2)
        }
    }
}
$rows | Format-Table
[pscustomobject]@{
    ProcessCount = @($rows).Count
    TotalPrivateMiB = ($rows | Measure-Object PrivateMiB -Sum).Sum
    # Working sets can share pages; do not interpret their sum as unique physical memory.
    SampleTime = (Get-Date).ToString('o')
}
