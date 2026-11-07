# ==============================================================================
# ShadowFix AI - Production Deployment Script (Windows PowerShell)
# ==============================================================================

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "         SHADOWFIX AI - PRODUCTION DEPLOYMENT ENGINE             " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker Desktop is not installed or not in PATH." -ForegroundColor Red
    Exit 1
}

# 2. Check or Generate .env
if (-not (Test-Path .env)) {
    Write-Host "==> Generating fresh production .env configuration..." -ForegroundColor Yellow
    $postgresPass = [System.Guid]::NewGuid().ToString("N").Substring(0, 16)
    $adminKey = [System.Guid]::NewGuid().ToString("N")
    $superadminPass = [System.Guid]::NewGuid().ToString("N").Substring(0, 12)

    @"
# ── ShadowFix Production Environment ──
SHADOWFIX_ENV=production
ADMIN_API_KEY=$adminKey
SUPERADMIN_EMAIL=admin@shadowfix.ai
SUPERADMIN_PASSWORD=$superadminPass

# ── PostgreSQL Database ──
POSTGRES_DB=shadowfix_prod
POSTGRES_USER=shadowfix
POSTGRES_PASSWORD=$postgresPass
DATABASE_URL=postgresql://shadowfix:${postgresPass}@shadowfix-postgres:5432/shadowfix_prod

# ── Redis Cache & Queues ──
REDIS_URL=redis://shadowfix-redis:6379/0

# ── Qdrant Vector Engine ──
QDRANT_MODE=disk

# ── Payment Gateways ──
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_PAYMENT_LINK=https://razorpay.me/@shivamkumar98
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_MODE=sandbox
"@ | Out-File -FilePath .env -Encoding utf8

    Write-Host "✓ Production .env created with random credentials." -ForegroundColor Green
    Write-Host "SuperAdmin Login: admin@shadowfix.ai" -ForegroundColor Yellow
    Write-Host "SuperAdmin Pass:  $superadminPass" -ForegroundColor Yellow
}

# 3. Launch Docker Compose
Write-Host "==> Starting Docker Compose cluster..." -ForegroundColor Cyan
docker compose -f docker-compose.prod.yml down --remove-orphans
docker compose -f docker-compose.prod.yml up -d --build

Write-Host "==> Waiting for containers to initialize..." -ForegroundColor Cyan
Start-Sleep -Seconds 8
docker compose -f docker-compose.prod.yml ps

Write-Host "`n✓ Deployment Complete! Access dashboard at: http://localhost:8000" -ForegroundColor Green
