# Пошаговая инструкция по ручному деплою

## Шаг 1: Подключись к серверу
Открой терминал (PowerShell/CMD/Git Bash) и выполни:
```bash
ssh root@150.241.66.53
```
(введи пароль когда попросит)

## Шаг 2: Перейди в директорию бота
```bash
cd /root/bot
```

## Шаг 3: Сделай бекап текущей версии
```bash
cp bot.py bot.py.backup.$(date +%Y%m%d_%H%M%S)
```

## Шаг 4: Скачай новый bot.py из репозитория
Вариант A — через git pull:
```bash
cd /opt/ventura-vpn-robot
git pull origin main
cp bot.py /root/bot/bot.py
```

Вариант B — скопируй файл с локального компьютера:
```bash
# На своём компьютере (не на сервере):
scp C:\Users\User\Desktop\ventura-vpn-robot\bot.py root@150.241.66.53:/root/bot/bot.py
```

## Шаг 5: Проверь синтаксис
```bash
python3 -c "import py_compile; py_compile.compile('bot.py', doraise=True)"
```
Должно вывести `OK`

## Шаг 6: Перезапусти бота
```bash
# Останови старый процесс
pkill -f bot.py

# Запусти новый
cd /root/bot && nohup python3 bot.py > bot.log 2>&1 &

# Проверь что работает
ps aux | grep bot.py
```

Или если используешь pm2/systemd:
```bash
pm2 restart ventura-bot
# или
systemctl restart ventura-bot
```

## Шаг 7: Проверь логи
```bash
tail -f /root/bot/bot.log
# или
pm2 logs ventura-bot --lines 20
```

## Шаг 8: Протестируй в Telegram
1. Открой @VenturaVpnRobot
2. Нажми /start
3. Должно появиться новое сообщение Каролины со стикером
4. Кнопки должны быть: "Подписка", "Тест-драйв VPN", "Есть код?", "зови друзей"

## Если что-то сломалось — откат:
```bash
ls /root/bot/bot.py.backup.*
# выбери последний бекап
cp /root/bot/bot.py.backup.20260807_XXX /root/bot/bot.py
pkill -f bot.py
cd /root/bot && nohup python3 bot.py > bot.log 2>&1 &
```
