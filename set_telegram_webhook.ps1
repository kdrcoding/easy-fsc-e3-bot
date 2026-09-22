$token = Read-Host "Paste NEW Telegram bot token"
$url = Read-Host "Paste Vercel webhook URL, example https://your-project.vercel.app/telegram"
$secret = Read-Host "Paste TELEGRAM_WEBHOOK_SECRET value"

$result = Invoke-RestMethod `
  -Method Post `
  -Uri "https://api.telegram.org/bot$token/setWebhook" `
  -Body @{
    url = $url
    secret_token = $secret
    drop_pending_updates = "true"
  }

$result | Format-List

Write-Host ""
Write-Host "Checking webhook info..."
Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getWebhookInfo" | Format-List
