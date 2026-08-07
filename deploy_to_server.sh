#!/bin/bash
# Скрипт деплоя на сервер 150.241.66.53

echo "🚀 Деплой изменений в ventura-vpn-robot..."

# Подключение к серверу
ssh root@150.241.66.53 << 'SSH_EOF'
  echo "Подключено к серверу"

  cd /opt/ventura-vpn-robot

  # Сохраняем бекап
  BACKUP_DIR="/opt/ventura-vpn-robot/backups/deploy_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$BACKUP_DIR"
  cp bot.py "$BACKUP_DIR/" 2>/dev/null || true
  echo "✅ Бэкап создан: $BACKUP_DIR"

  # Pull последних изменений (если есть доступ к GitHub)
  if git pull origin main 2>/dev/null; then
    echo "✅ Изменения получены из GitHub"
  else
    echo "⚠️ GitHub недоступен, изменения уже на сервере"
  fi

  # Перезапуск бота
  pm2 restart ventura-bot
  echo "✅ Бот перезапущен"

  # Проверка логов
  echo "📋 Последние логи:"
  pm2 logs ventura-bot --lines 5

  echo ""
  echo "🎉 Деплой завершен!"
  echo "Теперь @first1523 увидит новые приветственные сообщения"
SSH_EOF

if [ $? -eq 0 ]; then
  echo "✅ Деплой выполнен успешно"
else
  echo "❌ Ошибка деплоя. Проверьте SSH доступ."
fi
