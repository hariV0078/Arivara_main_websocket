# Test Chatbot API Script
# Make sure your server is running: python run.py

# # Configuration - Replace with your values
# $SUPABASE_URL = "https://lmwqvjubseutlvrufehb.supabase.co"
# $ANON_KEY = "your-anon-key-here"  # Get from Supabase Dashboard → Settings → API
# $API_URL = "http://localhost:8000/api"
# $TEST_EMAIL = "thanusiksaravanan582003@gmail.com"
# $TEST_PASSWORD = "your-password-here"

Write-Host "=== Step 1: Getting JWT Token ===" -ForegroundColor Green

# Sign in to get JWT token
$loginBody = @{
    email = $TEST_EMAIL
    password = $TEST_PASSWORD
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod -Uri "$SUPABASE_URL/auth/v1/token?grant_type=password" `
        -Method POST `
        -Headers @{
            "apikey" = $ANON_KEY
            "Content-Type" = "application/json"
        } `
        -Body $loginBody
    
    $JWT_TOKEN = $loginResponse.access_token.Trim()
    Write-Host "✓ JWT Token obtained" -ForegroundColor Green
    Write-Host "Token (first 50 chars): $($JWT_TOKEN.Substring(0, 50))..." -ForegroundColor Gray
} catch {
    Write-Host "✗ Failed to get JWT token: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit
}

Write-Host "`n=== Step 2: Testing Health Endpoint ===" -ForegroundColor Green
try {
    $health = Invoke-RestMethod -Uri "$API_URL/health" -Method GET
    Write-Host "✓ Health check passed: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "✗ Health check failed: $_" -ForegroundColor Red
    exit
}

Write-Host "`n=== Step 3: Sending First Message ===" -ForegroundColor Green

# Create request body
$messageBody = @{
    chat_id = $null
    message = "Hello! Explain what artificial intelligence is in simple terms."
    enable_web_scraping = $true
} | ConvertTo-Json -Compress

# Create headers
$headers = @{
    "Authorization" = "Bearer $JWT_TOKEN"
    "Content-Type" = "application/json"
}

try {
    Write-Host "Sending request..." -ForegroundColor Yellow
    $response = Invoke-RestMethod -Uri "$API_URL/chat" `
        -Method POST `
        -Headers $headers `
        -Body $messageBody `
        -ContentType "application/json"
    
    Write-Host "✓ Message sent successfully!" -ForegroundColor Green
    Write-Host "`nChat ID: $($response.data.chat_id)" -ForegroundColor Cyan
    Write-Host "`nBot Response:" -ForegroundColor Yellow
    Write-Host $response.data.message -ForegroundColor White
    
    if ($response.metadata -and $response.metadata.web_scraping_used) {
        Write-Host "`nWeb scraping was used. Sources:" -ForegroundColor Cyan
        if ($response.metadata.sources) {
            $response.metadata.sources | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
        }
    }
    
    $CHAT_ID = $response.data.chat_id
} catch {
    Write-Host "✗ Failed to send message" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    Write-Host "`nMake sure:" -ForegroundColor Yellow
    Write-Host "  1. Server is running (python run.py)" -ForegroundColor Yellow
    Write-Host "  2. JWT token is valid" -ForegroundColor Yellow
    Write-Host "  3. Supabase database is set up" -ForegroundColor Yellow
    exit
}

Write-Host "`n=== Step 4: Sending Follow-up Message ===" -ForegroundColor Green

$followUpBody = @{
    chat_id = $CHAT_ID
    message = "Give me a real-world example of AI."
    enable_web_scraping = $false
} | ConvertTo-Json -Compress

try {
    $response2 = Invoke-RestMethod -Uri "$API_URL/chat" `
        -Method POST `
        -Headers $headers `
        -Body $followUpBody `
        -ContentType "application/json"
    
    Write-Host "✓ Follow-up message sent!" -ForegroundColor Green
    Write-Host "`nBot Response:" -ForegroundColor Yellow
    Write-Host $response2.data.message -ForegroundColor White
} catch {
    Write-Host "✗ Failed to send follow-up: $_" -ForegroundColor Red
}

Write-Host "`n=== Test Complete! ===" -ForegroundColor Green
