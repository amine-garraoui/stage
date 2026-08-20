# ============================================
# Security Test Script
# ============================================
# Usage: .\scripts\test_security.ps1

param(
    [switch]$Full = $false,
    [switch]$Silent = $false
)

function Write-Header {
    param([string]$Text)
    if (-not $Silent) {
        Write-Host ""
        Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
        Write-Host "║ $($Text.PadRight(38)) ║" -ForegroundColor Cyan
        Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
    }
}

function Test-Pass {
    param([string]$Text)
    if (-not $Silent) {
        Write-Host "✅ $Text" -ForegroundColor Green
    }
}

function Test-Fail {
    param([string]$Text)
    Write-Host "❌ $Text" -ForegroundColor Red
}

function Test-Warn {
    param([string]$Text)
    Write-Host "⚠️  $Text" -ForegroundColor Yellow
}

# Main tests
$failures = @()
$warnings = @()

Write-Header "🔒 SECURITY TESTS"

# Test 1: .env.local exists
Write-Host ""
if (Test-Path ".env.local") {
    Test-Pass ".env.local exists"
} else {
    Test-Fail ".env.local does not exist"
    $failures += ".env.local missing - copy from .env.example"
}

# Test 2: API_KEYS environment variable
$apiKeys = $env:API_KEYS
if ($apiKeys) {
    Test-Pass "API_KEYS environment variable is set"
    $keyCount = ($apiKeys -split ",").Count
    Write-Host "      Found $keyCount key(s)" -ForegroundColor Gray
} else {
    Test-Warn "API_KEYS environment variable not set"
    $warnings += "Set API_KEYS: `$env:API_KEYS = 'your-key-here'"
}

# Test 3: .gitignore has .env.local
Write-Host ""
if (Test-Path ".gitignore") {
    $gitignore = Get-Content ".gitignore" -Raw
    if ($gitignore -match "\.env\.local") {
        Test-Pass ".env.local in .gitignore"
    } else {
        Test-Fail ".env.local NOT in .gitignore"
        $failures += "Add '.env.local' to .gitignore"
    }
    
    if ($gitignore -match "\.encryption_key") {
        Test-Pass ".encryption_key in .gitignore"
    } else {
        Test-Warn ".encryption_key NOT in .gitignore"
    }
} else {
    Test-Warn ".gitignore not found"
}

# Test 4: Security modules exist
Write-Host ""
if (Test-Path "core/encryption.py") {
    Test-Pass "core/encryption.py exists"
} else {
    Test-Fail "core/encryption.py missing"
    $failures += "core/encryption.py not found"
}

if (Test-Path "core/audit.py") {
    Test-Pass "core/audit.py exists"
} else {
    Test-Fail "core/audit.py missing"
    $failures += "core/audit.py not found"
}

# Test 5: API has audit logging
Write-Host ""
if (Test-Path "api/main.py") {
    $apiCode = Get-Content "api/main.py" -Raw
    if ($apiCode -match "from core.audit import") {
        Test-Pass "api/main.py imports audit module"
    } else {
        Test-Warn "api/main.py does not import audit module"
        $warnings += "Add audit logging to api/main.py"
    }
    
    if ($apiCode -match "verify_api_key") {
        Test-Pass "api/main.py has authentication"
    } else {
        Test-Fail "api/main.py missing authentication"
        $failures += "Add verify_api_key to API"
    }
} else {
    Test-Warn "api/main.py not found"
}

# Test 6: Anonymisation module exists
Write-Host ""
if (Test-Path "core/anonymisation.py") {
    Test-Pass "core/anonymisation.py exists"
    $anonCode = Get-Content "core/anonymisation.py" -Raw
    if ($anonCode -match "drop_columns") {
        Test-Pass "Anonymisation drops sensitive columns"
    } else {
        Test-Warn "No column dropping found in anonymisation"
    }
} else {
    Test-Fail "core/anonymisation.py missing"
}

# Test 7: Security documentation
Write-Host ""
foreach ($doc in @("SECURITY.md", "SECURITY_QUICK_START.md", "SECURITY_CHECKLIST.md")) {
    if (Test-Path $doc) {
        Test-Pass "$doc exists"
    } else {
        Test-Warn "$doc missing"
    }
}

# Test 8: No hardcoded secrets in code
Write-Host ""
$hasSecrets = $false
foreach ($file in @("api/main.py", "dashboard/app.py", "app.py")) {
    if (Test-Path $file) {
        $content = Get-Content $file -Raw
        if ($content -match "API_KEY\s*=\s*['\"]") {
            Test-Fail "Hardcoded API key found in $file"
            $failures += "Remove hardcoded secrets from $file"
            $hasSecrets = $true
        }
        if ($content -match "PASSWORD\s*=\s*['\"]") {
            Test-Fail "Hardcoded password found in $file"
            $failures += "Remove hardcoded password from $file"
            $hasSecrets = $true
        }
    }
}
if (-not $hasSecrets) {
    Test-Pass "No hardcoded secrets found"
}

# Test 9: Tests exist and pass
Write-Host ""
if (Test-Path "tests/test_security.py") {
    Test-Pass "test_security.py exists"
} else {
    Test-Warn "test_security.py missing"
}

# Summary
Write-Header "SUMMARY"

Write-Host ""
if ($failures.Count -eq 0) {
    Write-Host "🎉 ALL CRITICAL TESTS PASSED!" -ForegroundColor Green
} else {
    Write-Host "🚨 $($failures.Count) CRITICAL ISSUE(S) FOUND:" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "   - $failure"
    }
}

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️  $($warnings.Count) WARNING(S):" -ForegroundColor Yellow
    foreach ($warning in $warnings) {
        Write-Host "   - $warning"
    }
}

Write-Host ""

# Full test option
if ($Full) {
    Write-Header "RUNNING FULL TESTS"
    
    Write-Host ""
    Write-Host "Running pytest..." -ForegroundColor Cyan
    & .venv\Scripts\python.exe -m pytest tests/test_security.py -v
}

# Exit code
if ($failures.Count -gt 0) {
    exit 1
} else {
    exit 0
}
