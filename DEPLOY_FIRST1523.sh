#!/bin/bash
# Скрипт деплоя новой версии ТОЛЬКО для @first1523

echo "🚀 Деплой отдельной версии для @first1523..."

# Подключаемся к серверу
ssh root@150.241.66.53 << 'SSH_EOF'
  echo "=== Подключено к серверу ==="

  cd /opt/ventura-vpn-robot

  # 1. Останавливаем старый бот (если он работает)
  echo "⏹ Остановка старого бота..."
  pm2 stop ventura-bot || true
  pm2 delete ventura-bot || true

  # 2. Pull последних изменений из GitHub
  echo "📥 Получение последних изменений..."
  git pull origin main

  # 3. Запускаем НОВУЮ версию только для @first1523
  echo "▶️ Запуск bot_first1523.py..."
  pm2 start bot_first1523.py --name ventura-bot-first1523
  pm2 save

  # 4. Проверяем статус
  echo ""
  echo "=== Статус процессов ==="
  pm2 status

  echo ""
  echo "=== Логи нового бота ==="
  pm2 logs ventura-bot-first1523 --lines 10

  echo ""
  echo "✅ Деплой завершен!"
  echo "Теперь @first1523 должен видеть новые сообщения"
SSH_EOF

if [ $? -eq 0 ]; then
  echo "✅ Деплой выполнен успешно"
else
  echo "❌ Ошибка деплоя"
fi
