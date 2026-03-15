# 🚀 Деплой на Fly.io — АЙСАФИ бот

## Шаг 1 — Установи flyctl

Windows (в PowerShell):
```
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

## Шаг 2 — Регистрация
```
flyctl auth signup
```
Или логин если уже есть аккаунт:
```
flyctl auth login
```

## Шаг 3 — Инициализация (в папке с ботом)
```
flyctl launch
```
Когда спросит:
- App name: `aisafi-bot` (или любое)
- Region: выбери ближайший (Frankfurt — ams)
- Would you like to deploy now: **No**

## Шаг 4 — Добавь секреты (env переменные)
```
flyctl secrets set BOT_TOKEN=твой_токен
flyctl secrets set GROQ_API_KEY=твой_ключ
flyctl secrets set OWNER_CHAT_ID=твой_id
flyctl secrets set SPREADSHEET_ID=id_таблицы
```

## Шаг 5 — Деплой
```
flyctl deploy
```

## Шаг 6 — Получи URL и добавь WEBHOOK_URL
После деплоя Fly.io даст URL вида: `https://aisafi-bot.fly.dev`
```
flyctl secrets set WEBHOOK_URL=https://aisafi-bot.fly.dev
flyctl deploy
```

## Готово! 🎉

Проверить статус:
```
flyctl status
```

Логи:
```
flyctl logs
```

## Важно — Fly.io бесплатный план:
- 3 shared-cpu-1x 256MB машины бесплатно
- Не засыпает (в отличие от Render Free)
- Нужна карта для регистрации (не снимают деньги)
