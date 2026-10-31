#Requires -Version 5.1

<#
.SYNOPSIS
    导出 Windows 受信任根证书为 PEM CA bundle。

.DESCRIPTION
    用于修复 Docker 容器访问 HTTPS 外部服务时的证书信任链问题。
    脚本只导出公钥证书，不导出私钥。输出文件为 certs/ca-bundle.pem。
    如果处于企业代理环境，请先确认 Windows 已信任代理根证书。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/export_windows_ca.ps1
#>

[CmdletBinding()]
param(
    [string]$OutputPath = "certs/ca-bundle.pem"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputFile = Join-Path $projectRoot $OutputPath
$outputDir = Split-Path -Parent $outputFile

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$stores = @(
    "Cert:\CurrentUser\Root",
    "Cert:\LocalMachine\Root"
)

$seen = [System.Collections.Generic.HashSet[string]]::new()
$blocks = [System.Collections.Generic.List[string]]::new()

foreach ($storePath in $stores) {
    if (-not (Test-Path $storePath)) {
        continue
    }

    foreach ($certificate in Get-ChildItem $storePath) {
        if (-not $seen.Add($certificate.Thumbprint)) {
            continue
        }

        $raw = $certificate.Export(
            [System.Security.Cryptography.X509Certificates.X509ContentType]::Cert
        )
        $base64 = [Convert]::ToBase64String(
            $raw,
            [System.Base64FormattingOptions]::InsertLineBreaks
        )

        $blocks.Add("-----BEGIN CERTIFICATE-----")
        $blocks.Add($base64)
        $blocks.Add("-----END CERTIFICATE-----")
    }
}

if ($blocks.Count -eq 0) {
    throw "未找到可导出的 Windows 受信任根证书。"
}

Set-Content -Path $outputFile -Value ($blocks -join "`r`n") -Encoding ascii

Write-Host "已导出 CA bundle: $outputFile"
Write-Host "证书数量: $($seen.Count)"
Write-Host "请在 docker-compose.yml 中挂载该文件，并设置："
Write-Host "  SSL_CERT_FILE=/app/certs/ca-bundle.pem"
Write-Host "  REQUESTS_CA_BUNDLE=/app/certs/ca-bundle.pem"
