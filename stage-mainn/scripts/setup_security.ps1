# ============================================
# Security Setup Script
# ============================================
# Run this to configure security for the app

param(
    [string]$Action = "setup"
)

function Generate-ApiKey {
    Write-Host "🔐 Generating secure API key..." -ForegroundColor Cyan
    
    $key = python -c "import secrets; print(secrets.token_urlsafe(32))"
    Write-Host "✅ Generated API key (keep this safe!):" -ForegroundColor Green
    Write-Host $key
    Write-Host ""
    Write-Host "Store this in .env.local:" -ForegroundColor Yellow
    Write-Host "API_KEYS=$key"
    Write-Host ""
    
    return $key
}

function Setup-Environment {
    Write-Host "🔧 Setting up security environment..." -ForegroundColor Cyan
    
    # Check if .env.local exists
    if (-not (Test-Path ".env.local")) {
        Write-Host "📄 Creating .env.local from .env.example" -ForegroundColor Yellow
        Copy-Item ".env.example" ".env.local"
        Write-Host "✅ Created .env.local" -ForegroundColor Green
    }
    
    # Generate API key if needed
    $apiKey = Generate-ApiKey
    
    # Update .env.local
    Write-Host "📝 Updating .env.local with API key..." -ForegroundColor Cyan
    
    $envContent = Get-Content ".env.local" -Raw
    $envContent = $envContent -replace "API_KEYS=.*", "API_KEYS=$apiKey"
    $envContent | Set-Content ".env.local"
    
    Write-Host "✅ Updated .env.local" -ForegroundColor Green
    
    # Ensure .gitignore entries
    Write-Host "🚫 Updating .gitignore..." -ForegroundColor Cyan
    $gitignore = ".gitignore"
    
    $entries = @(
        ".env.local",
        ".encryption_key",
        "*.pyc",
        "__pycache__/",
        ".pytest_cache/",
        "*.log"
    )
    
    foreach ($entry in $entries) {
        if (-not (Select-String -Path $gitignore -Pattern $entry -Quiet)) {
            Add-Content $gitignore $entry
        }
    }
    
    Write-Host "✅ Updated .gitignore" -ForegroundColor Green
}

function Install-Dependencies {
    Write-Host "📦 Installing security dependencies..." -ForegroundColor Cyan
    
    pip install cryptography python-dotenv safety
    
    Write-Host "✅ Installed dependencies" -ForegroundColor Green
}

function Test-Security {
    Write-Host "🧪 Running security tests..." -ForegroundColor Cyan
    
    # Check API authentication
    Write-Host "Testing API authentication..." -ForegroundColor Yellow
    
    # Load API keys from environment
    $apiKeys = $env:API_KEYS
    if (-not $apiKeys) {
        Write-Host "⚠️  API_KEYS environment variable not set" -ForegroundColor Yellow
        Write-Host "Run: `$env:API_KEYS = 'your-key-here'" -ForegroundColor Cyan
        return
    }
    
    $validKey = ($apiKeys -split ",")[0].Trim()
    
    Write-Host "✅ API key found: $($validKey.Substring(0,8))..." -ForegroundColor Green
    
    # Check if audit.log exists
    if (Test-Path "data/audit.log") {
        Write-Host "✅ Audit log configured" -ForegroundColor Green
        Get-Content "data/audit.log" -Tail 5
    } else {
        Write-Host "⚠️  Audit log not created yet (will be created on first API call)" -ForegroundColor Yellow
    }
    
    # Run safety check
    Write-Host ""
    Write-Host "Checking for vulnerable dependencies..." -ForegroundColor Cyan
    safety check
}

function Encrypt-Sensitive-Files {
    Write-Host "🔐 Encrypting sensitive files..." -ForegroundColor Cyan
    
    $files = Get-ChildItem "data/input" -Filter "*.csv" -ErrorAction SilentlyContinue
    
    if ($files.Count -eq 0) {
        Write-Host "⚠️  No CSV files found in data/input" -ForegroundColor Yellow
        return
    }
    
    foreach ($file in $files) {
        Write-Host "Encrypting $($file.Name)..." -ForegroundColor Yellow
        
        python -c "
from core.encryption import encrypt_file
from pathlib import Path
encrypt_file(Path('$($file.FullName)'))
"
        
        Write-Host "✅ Encrypted $($file.Name)" -ForegroundColor Green
    }
}

# Main
Write-Host ""
Write-Host "╔════════════════════════════════════════╗"
Write-Host "║       SECURITY SETUP SCRIPT            ║"
Write-Host "╚════════════════════════════════════════╝"
Write-Host ""

switch ($Action) {
    "setup" {
        Setup-Environment
        Install-Dependencies
    }
    "test" {
        Test-Security
    }
    "encrypt" {
        Encrypt-Sensitive-Files
    }
    "all" {
        Setup-Environment
        Install-Dependencies
        Test-Security
        Encrypt-Sensitive-Files
    }
    default {
        Write-Host "Available actions:" -ForegroundColor Cyan
        Write-Host "  .\scripts\setup_security.ps1 setup      # Setup environment and dependencies"
        Write-Host "  .\scripts\setup_security.ps1 test       # Test security configuration"
        Write-Host "  .\scripts\setup_security.ps1 encrypt    # Encrypt sensitive CSV files"
        Write-Host "  .\scripts\setup_security.ps1 all        # Run all setup, test, and encrypt"
    }
}

Write-Host ""
Write-Host "✅ Done!" -ForegroundColor Green
