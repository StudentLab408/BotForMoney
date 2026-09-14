WELCOME_NEW = (
    "👋 <b>Добро пожаловать в бот учёта надбавок!</b>\n\n"
    "Здесь можно зарегистрироваться и подавать заявки на надбавку "
    "за участие в конференциях и мероприятиях.\n\n"
    "Для начала укажите свою <b>Фамилию</b>."
)

WELCOME_BACK = "👋 С возвращением, <b>{full_name}</b>!"

ASK_LAST_NAME = "Укажите <b>Фамилию</b>."
ASK_FIRST_NAME = "Отлично. Теперь укажите <b>Имя</b>."
ASK_MIDDLE_NAME = "Теперь укажите <b>Отчество</b>."
ASK_GROUP = "И последнее — номер вашей <b>учебной группы</b>."

REGISTRATION_CONFIRM = (
    "✅ <b>Проверьте данные:</b>\n\n👤 {last_name} {first_name} {middle_name}\n🎓 Группа: {group_number}\n\nВсё верно?"
)

REGISTRATION_DONE = "🎉 Регистрация завершена! Добро пожаловать, {full_name}."
REGISTRATION_RESTART = "Хорошо, начнём заново. Укажите <b>Фамилию</b>."
PROFILE_EDIT_START = "✏️ Обновим данные профиля. Укажите <b>Фамилию</b>."
PROFILE_UPDATED = "✅ Данные профиля обновлены."

MAIN_MENU_STUDENT = "📋 <b>Личный кабинет</b>\n\nВыберите действие:"
MAIN_MENU_ADMIN = "🛠 <b>Панель администратора</b>\n\nВыберите раздел:"
MENU_NOT_REGISTERED = "😕 Вы ещё не зарегистрированы. Отправьте /start, чтобы начать."

HELP_TEXT = (
    "ℹ️ <b>Справка</b>\n\n"
    "/start — регистрация или главное меню\n"
    "/menu — быстрый переход в главное меню из любого места\n"
    "/help — эта справка\n\n"
    "В личном кабинете можно подать заявку на надбавку за конференцию или "
    "мероприятие и посмотреть статус своих заявок. Админы дополнительно видят панель управления."
)

INPUT_NOT_TEXT = "✍️ Отправьте, пожалуйста, ответ обычным текстом."
INPUT_TOO_LONG = "⚠️ Слишком длинно — не больше {max_len} символов."
ACTION_EXPIRED = "⚠️ Это действие уже неактуально. Откройте меню: /menu"
FALLBACK_REGISTERED = "🤔 Не понял сообщение. Выберите действие в меню:"
FALLBACK_UNREGISTERED = "👋 Чтобы начать, отправьте /start"
FALLBACK_CALLBACK = "⚠️ Кнопка устарела или недоступна."

PROFILE_CARD = "👤 <b>{full_name}</b>\n🎓 Группа: {group_number}\n🏷 Роль: {role_label}"

MY_SUBMISSIONS_TITLE = "📜 <b>Мои заявки</b> (последние {limit})"
MY_SUBMISSIONS_EMPTY = "📭 У вас пока нет заявок. Подать заявку можно в главном меню."

SUBMISSION_CHOOSE_TYPE = "За что подаём заявку на надбавку?"

ASK_CONFERENCE_NAME = "📝 Укажите <b>название конференции</b>."
ASK_CONFERENCE_PROJECT = "📝 Укажите <b>название проекта</b>, с которым выступали."
ASK_EVENT_NAME = "📝 Укажите <b>название мероприятия</b>."
ASK_EVENT_WHAT_DID = "📝 Опишите, <b>что вы делали</b> на мероприятии."

SUBMISSION_CONFIRM_CONFERENCE = (
    "✅ <b>Проверьте заявку — Конференция</b>\n\n"
    "🏛 Конференция: {conference_name}\n"
    "📁 Проект: {project_name}\n\n"
    "Отправить админам на подтверждение?"
)

SUBMISSION_CONFIRM_EVENT = (
    "✅ <b>Проверьте заявку — Мероприятие</b>\n\n"
    "🎪 Мероприятие: {event_name}\n"
    "🙋 Что делал(а): {what_did}\n\n"
    "Отправить админам на подтверждение?"
)

SUBMISSION_SENT = "📨 Заявка отправлена админам на рассмотрение. Мы уведомим вас о результате."

ADMIN_NEW_CONFERENCE_CARD = (
    "🆕 <b>Новая заявка — Конференция</b>\n\n"
    "👤 {full_name} ({group_number})\n"
    "🏛 Конференция: {conference_name}\n"
    "📁 Проект: {project_name}"
)

ADMIN_NEW_EVENT_CARD = (
    "🆕 <b>Новая заявка — Мероприятие</b>\n\n"
    "👤 {full_name} ({group_number})\n"
    "🎪 Мероприятие: {event_name}\n"
    "🙋 Что делал(а): {what_did}"
)

CARD_PROCESSED_APPROVED = "\n\n✅ <b>Одобрено, {amount} BYN</b> — {admin_name}, {date}"
CARD_PROCESSED_REJECTED = "\n\n❌ <b>Отклонено</b> — {admin_name}, {date}{reason_part}"
CARD_ALREADY_PROCESSED_ALERT = "⚠️ Заявка уже обработана."
INVALID_AMOUNT_ALERT = "⚠️ Некорректная сумма."
APPROVED_ALERT = "✅ Одобрено"

STUDENT_NOTIFY_APPROVED = "✅ Ваша заявка «{title}» одобрена! Начислено {amount} BYN."
STUDENT_NOTIFY_REJECTED = "❌ Ваша заявка «{title}» отклонена.{reason_part}"

ASK_REJECT_REASON = "✍️ Укажите причину отказа или нажмите «Пропустить»."
REJECT_DONE = "❌ Заявка отклонена."

ADMIN_ASK_STUDENT_SEARCH = "🔎 Введите фамилию студента (можно часть)."
ADMIN_STUDENT_NOT_FOUND = "😕 Никого не найдено. Попробуйте ещё раз."
ADMIN_CHOOSE_STUDENT = "👥 Выберите студента:"
ADMIN_ASK_PROJECT_NAME = "📝 Укажите <b>название проекта</b>."
ADMIN_ASK_REGALIA = "📝 Укажите <b>регалии</b> (достижения по проекту)."

ADMIN_PROJECT_CONFIRM = (
    "✅ <b>Проверьте начисление — Проектная надбавка</b>\n\n"
    "👤 {full_name} ({group_number})\n"
    "📁 Проект: {project_name}\n"
    "🏅 Регалии: {regalia}\n"
    "💰 Сумма: {amount} BYN\n\n"
    "Начислить?"
)

ADMIN_PROJECT_DONE = "🎉 Проектная надбавка начислена студенту {full_name}."

ADMIN_LIST_TITLE = "👑 <b>Администраторы</b>\n\nНажмите на админа, чтобы снять права."
ADMIN_LIST_EMPTY = "👑 <b>Администраторы</b>\n\nПока никто не назначен."
ADMIN_ASK_PROMOTE_TARGET = (
    "➕ Перешлите сообщение от пользователя, которого хотите сделать админом, или отправьте его Telegram ID."
)
ADMIN_PROMOTE_NOT_FOUND = "😕 Не удалось определить пользователя или он ещё не зарегистрирован в боте."
ADMIN_ALREADY_ADMIN = "ℹ️ {full_name} уже администратор."
ADMIN_PROMOTE_CONFIRM = "Назначить <b>{full_name}</b> администратором?"
ADMIN_PROMOTE_DONE = "✅ {full_name} назначен(а) администратором."
ADMIN_DEMOTE_DONE = "➖ {full_name} больше не администратор."

REPORT_CHOOSE_MONTH = "📅 За какой период сформировать отчёт?"
EXPORT_CHOOSE_MONTH = "📅 За какой период сформировать списки?"
ASK_CUSTOM_MONTH = "Введите месяц в формате <b>ММ.ГГГГ</b>, например <code>09.2026</code>."
INVALID_MONTH_FORMAT = "⚠️ Не удалось распознать месяц."

EXPORT_EMPTY = "📭 За {month_name} {year} нет ни одного студента с начислениями."
EXPORT_SENT = "📄 Списки за {month_name} {year} отправлены выше."
EXPORT_CAPTION_OFFICIAL = "📄 Официальный список надбавок за {month_name} {year}"
EXPORT_CAPTION_INTERNAL = "🗂 Внутренний список за {month_name} {year} (с основаниями и 25% в лабу)"
AUTO_EXPORT_PREFIX = "🤖 Автоматическая рассылка\n"

CANCEL_BUTTON = "❌ Отмена"
SKIP_BUTTON = "⏭ Пропустить"
CONFIRM_BUTTON = "✅ Подтвердить"
RETRY_BUTTON = "🔄 Начать заново"
BACK_BUTTON = "⬅️ Назад"
MAIN_MENU_BUTTON = "⬅️ В главное меню"
