# nadbavkiBot

Telegram-бот учёта надбавок к стипендии (проекты, конференции, мероприятия).
Подробное описание бизнес-логики — в `/Users/bytemainvoid/.claude/plans/stateless-zooming-penguin.md`.

## Настройка

1. Скопируйте `.env.example` в `.env` и заполните:
   - `BOT_TOKEN` — токен бота от @BotFather.
   - `SUPER_ADMIN_ID` — ваш Telegram ID (узнать можно, например, у @userinfobot). Супер-админ определяется только этим значением в конфиге, никаких дополнительных действий не требуется.
2. Остальные переменные (`TIMEZONE`, `WITHHOLD_RATE`, `PROJECT_AMOUNT`, `MONTHLY_CAP`, `AUTO_SEND_DAY`, `AUTO_SEND_HOUR`) можно оставить по умолчанию.

## Запуск локально

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

База данных SQLite создаётся автоматически по пути из `DB_PATH` (по умолчанию `./data/nadbavki.db`).

## Запуск в Docker

```bash
cp .env.example .env   # заполните BOT_TOKEN и SUPER_ADMIN_ID
docker compose up -d --build
```

Данные (`nadbavki.db`) сохраняются в `./data` на хосте — переживают пересборку и рестарт контейнера.

## Тесты

```bash
pip install -r requirements.txt
pytest
```

## Первый запуск

1. Напишите боту `/start` от аккаунта с `SUPER_ADMIN_ID` и пройдите короткую регистрацию (ФИО + группа — как у любого пользователя; это разовый шаг, чтобы у бота появилась запись о вас). После этого в главном меню сразу появится кнопка «🛠 Админ-панель» — доступ к ней определяется вашим Telegram ID из конфига, а не ролью в базе.
2. Через «👑 Управление админами» назначьте остальных админов (перешлите их сообщение боту или укажите Telegram ID — они должны быть уже зарегистрированы в боте, то есть уже хотя бы раз написали `/start` и прошли регистрацию).
3. Остальные студенты регистрируются самостоятельно через `/start`.
