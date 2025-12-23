param(
  [string]$VersionTag = ""
)

$ErrorActionPreference = "Stop"

python scripts/build.py
