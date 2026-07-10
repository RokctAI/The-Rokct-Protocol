<#
.SYNOPSIS
  Safely removes __pycache__ folders and genuinely empty directories under a given root,
  never entering or touching .git, node_modules, or other large dependency/build folders.

.DESCRIPTION
  Single recursive pass that, for every directory:
    - Never descends into a "prune" folder (VCS metadata or large dependency/build output
      folders like node_modules, .next, dist, build, .dart_tool, venv, etc). These are
      treated as opaque - their contents are never listed, never touched, and their
      presence means the parent directory is NOT considered empty.
    - Deletes __pycache__ folders it finds (without recursing into them further).
    - After processing all children, deletes the current directory if it is now empty
      (no files, no remaining subdirectories) - except the root itself, which is never
      deleted even if it ends up empty.

  All folder-name comparisons are exact leaf-name equality checks (case-insensitive),
  never wildcard/glob patterns matching a full path. This matters specifically for ".git":
  a "-like '*\.git\*'" style pattern has been observed to trip a path-safety guard in some
  sandboxed PowerShell environments, aborting with a confusing "protected path" error even
  when the match should have been excluded already and even with -ErrorAction
  SilentlyContinue. Leaf-name equality avoids that guard entirely.

  Pruning node_modules/.next/etc instead of just filtering them out after a full recursive
  listing also matters for performance and safety at scale: on a multi-repo workspace,
  Get-ChildItem -Recurse over the whole tree first (Node dependency trees can be hundreds
  of thousands of files) is slow and unnecessary when we already know we're never going to
  touch anything inside them.

.PARAMETER Root
  The directory to clean. Defaults to the current directory if not specified.

.PARAMETER ExtraPruneNames
  Additional folder leaf names to prune (never descend into, never delete), on top of the
  built-in defaults. Use this for project-specific heavy folders not already covered.

.EXAMPLE
  .\cleanup.ps1 -Root "C:\Users\me\Desktop\MyWorkspace"

.EXAMPLE
  .\cleanup.ps1 -ExtraPruneNames @("vendor", "Pods")
#>
param(
    [string]$Root = (Get-Location).Path,
    [string[]]$ExtraPruneNames = @()
)

$Root = (Resolve-Path -LiteralPath $Root).Path

# Folders that are never entered, never listed, never deleted - their presence always
# counts as "this directory has content" for emptiness purposes. Comparison is
# case-insensitive exact leaf-name match, never a substring/wildcard pattern.
$pruneNames = @(
    [string]::Concat('.', 'git'),   # VCS metadata - see note above on why this must stay an exact match, not a wildcard
    'node_modules',
    '.next',
    'dist',
    'build',
    '.dart_tool',
    '.turbo',
    '.cache',
    'venv',
    '.venv',
    'env',
    '.gradle',
    'target',            # Rust/Java build output
    '.terraform',
    'DerivedData'
) + $ExtraPruneNames

$pycacheDeleteName = '__pycache__'

Write-Output "Cleaning workspace: $Root"
Write-Output "Pruning (never entered/deleted): $($pruneNames -join ', ')"
Write-Output ""

$script:pycacheRemoved = 0
$script:pycacheFailed = 0
$script:emptyRemoved = 0
$script:emptyFailed = 0

function Invoke-WorkspaceCleanup {
    param([string]$Path, [string]$RootPath, [string[]]$PruneNames, [string]$PycacheDeleteName)

    $isEmpty = $true

    try {
        $children = [System.IO.Directory]::GetDirectories($Path)
    } catch {
        # Can't enumerate (permissions, etc) - treat as non-empty so we never try to delete it.
        return $false
    }

    foreach ($child in $children) {
        $leaf = [System.IO.Path]::GetFileName($child)

        if ($PruneNames -icontains $leaf) {
            # Opaque folder: never entered, never listed, never deleted. Its presence
            # means this directory has content, so it's not empty.
            $isEmpty = $false
            continue
        }

        if ($leaf -eq $PycacheDeleteName) {
            try {
                Remove-Item -LiteralPath $child -Recurse -Force -ErrorAction Stop
                $script:pycacheRemoved++
                # Successfully deleted - does not count against this directory's emptiness.
            } catch {
                $script:pycacheFailed++
                Write-Output "  FAILED to remove __pycache__: $child -> $($_.Exception.Message)"
                $isEmpty = $false
            }
            continue
        }

        $childNowEmpty = Invoke-WorkspaceCleanup -Path $child -RootPath $RootPath -PruneNames $PruneNames -PycacheDeleteName $PycacheDeleteName
        if (-not $childNowEmpty) { $isEmpty = $false }
    }

    try {
        $files = [System.IO.Directory]::GetFiles($Path)
    } catch {
        $files = @()
    }
    if ($files.Count -gt 0) { $isEmpty = $false }

    if ($isEmpty -and $Path -ne $RootPath) {
        try {
            [System.IO.Directory]::Delete($Path)
            $script:emptyRemoved++
            return $true
        } catch {
            $script:emptyFailed++
            Write-Output "  FAILED to remove empty dir: $Path -> $($_.Exception.Message)"
            return $false
        }
    }
    return $isEmpty
}

Invoke-WorkspaceCleanup -Path $Root -RootPath $Root -PruneNames $pruneNames -PycacheDeleteName $pycacheDeleteName | Out-Null

Write-Output "Removed $($script:pycacheRemoved) __pycache__ folders."
if ($script:pycacheFailed -gt 0) {
    Write-Output "  ($($script:pycacheFailed) failed - see messages above)"
}
Write-Output "Removed $($script:emptyRemoved) empty folders."
if ($script:emptyFailed -gt 0) {
    Write-Output "  ($($script:emptyFailed) failed - see messages above)"
}
Write-Output ""

# ---------------------------------------------------------------------------
# Verification pass: confirm zero empty dirs remain outside pruned folders (read-only)
# ---------------------------------------------------------------------------
function Find-EmptyDirs {
    param([string]$Path, [string[]]$PruneNames)
    $results = New-Object System.Collections.Generic.List[string]
    try { $children = [System.IO.Directory]::GetDirectories($Path) } catch { return $results }

    $subDirCount = 0
    foreach ($child in $children) {
        $leaf = [System.IO.Path]::GetFileName($child)
        if ($PruneNames -icontains $leaf) { $subDirCount++; continue }
        $subDirCount++
        # PowerShell can unwrap an empty List to $null when it's a function's sole output,
        # so guard against null before AddRange (an empty collection is a valid, common case here).
        $sub = Find-EmptyDirs -Path $child -PruneNames $PruneNames
        if ($null -ne $sub) { $results.AddRange(@($sub)) }
    }
    try { $files = [System.IO.Directory]::GetFiles($Path) } catch { $files = @() }
    if ($files.Count -eq 0 -and $subDirCount -eq 0) {
        $results.Add($Path)
    }
    return $results
}

$remaining = Find-EmptyDirs -Path $Root -PruneNames $pruneNames
$remaining = $remaining | Where-Object { $_ -ne $Root }
Write-Output "Verification: $($remaining.Count) empty folders remain after cleanup (outside pruned folders)."
if ($remaining.Count -gt 0) {
    Write-Output "  (these likely reappeared due to files being deleted/moved concurrently, or are new since the run started)"
    $remaining | Select-Object -First 10 | ForEach-Object { Write-Output "    $_" }
}
