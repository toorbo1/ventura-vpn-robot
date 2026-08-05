#!/bin/bash
# Скрипт деплоя на сервер mail.venturavpn.club (144.31.25.159)

echo "🚀 Деплой на mail.venturavpn.club..."

# Подключаемся к правильному серверу
ssh root@144.31.25.159 << 'SSH_EOF'
  echo "=== Подключено к mail.venturavpn.club ==="

  # Ищем где находится бот
  if [ -d "/root/bot" ]; then
    BOT_DIR="/root/bot"
  elif [ -d "/opt/ventura-vpn-robot" ]; then
    BOT_DIR="/opt/ventura-vpn-robot"
  elif [ -d "/home/ventura/bot" ]; then
    BOT_DIR="/home/ventura/bot"
  else
    echo "❌ Не могу найти директорию бота!"
    ls -la /root/ | grep -i bot
    ls -la /opt/ | grep -i ventura
    exit 1
  fi

  echo "✅ Найдена директория бота: $BOT_DIR"
  cd $BOT_DIR

  # Pull последних изменений
  echo "📥 Получение изменений из GitHub..."
  git pull origin main || echo "⚠️ Git pull не удался, продолжаем..."

  # Останавливаем старый бот
  echo "⏹ Остановка текущего бота..."
  pm2 list | grep -E "bot|ventura" || true
  pm2 delete all || true

  # Запускаем новую версию для @first1523
  echo "▶️ Запуск bot_first1523.py..."
  pm2 start bot_first1523.py --name ventura-bot-first1523
  pm2 save

  # Проверяем статус
  echo ""
  echo "=== Статус ==="
  pm2 status

  echo ""
  echo "=== Логи ==="
  pm2 logs ventura-bot-first1523 --lines 10

  echo ""
  echo "✅ Готово!"
SSH_EOF

if [ $? -eq 0 ]; then
  echo "✅ Деплой выполнен успешно!"
else
  echo "❌ Ошибка при деплое"
fi
