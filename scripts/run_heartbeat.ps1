# NetOps AI - 每日心跳自检脚本
# 配置为每天 09:00 自动运行

Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        NetOps AI - Daily Heartbeat Check                 ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 切换到项目目录
Set-Location "Z:\netops-ai"

# 运行主动监控脚本
python scripts/proactive_monitor.py

# 输出完成消息
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ 心跳检查完成" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⚠️  心跳检查发现问题，请查看输出" -ForegroundColor Yellow
}
