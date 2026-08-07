#!/bin/bash
# Script to check if bot is running on server
echo "Checking VenturaVPN Robot deployment..."
ssh root@150.241.66.53 << 'EOF'
echo "=== Process Status ==="
ps aux | grep bot.py | grep -v grep
echo ""
echo "=== Last Bot Output ==="
tail -20 /root/bot/nohup.out 2>/dev/null || echo "No output file found"
echo ""
echo "=== Bot Files ==="
ls -la /root/bot/
EOF
