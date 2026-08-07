@echo off
echo Отправляю обновлённый bot.py на сервер...
scp bot.py root@150.241.66.53:/root/bot/bot.py
if %errorlevel% neq 0 (
    echo Ошибка подключения по SSH!
    pause
    exit /b 1
)
echo Файл отправлен. Перезапускаю бота...
ssh root@150.241.66.53 "pm2 restart ventura-bot && pm2 logs ventura-bot --lines 10"
echo Бот перезапущен!
pause
