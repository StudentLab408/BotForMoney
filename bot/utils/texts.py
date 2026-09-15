KIND_TEXT = {
    "conference": {
        "icon": "🏛",
        "label": "Конференция",
        "plural": "Конференции",
        "acc": "конференцию",
        "gen": "конференции",
    },
    "event": {
        "icon": "🎪",
        "label": "Мероприятие",
        "plural": "Мероприятия",
        "acc": "мероприятие",
        "gen": "мероприятия",
    },
}
KIND_BY_CODE = {"c": "conference", "e": "event"}
CODE_BY_KIND = {kind: code for code, kind in KIND_BY_CODE.items()}

# --- Common -------------------------------------------------------------------------------------------------------

WELCOME_NEW = (
    "👋 <b>Добро пожаловать в бот учёта надбавок!</b>\n\n"
    "Здесь можно зарегистрироваться и подавать заявки на надбавку "
    "за участие в конференциях и мероприятиях.\n\n"
    "Для начала укажите свою <b>Фамилию</b>."
)
WELCOME_BACK = "👋 С возвращением, <b>{full_name}</b>!"
ARCHIVED_BLOCKED = "🗄 Ваш профиль в архиве. Если это ошибка, обратитесь к администратору лаборатории."

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
    "мероприятие, посмотреть статус своих заявок и отозвать заявку, пока она на рассмотрении."
)
HELP_ADMIN_SUFFIX = (
    "\n\n🛠 <b>Команды админа</b>\n"
    "/admin — админ-панель\n"
    "/requests — заявки на рассмотрении\n"
    "/students — студенты\n"
    "/projects — проекты\n"
    "/events — конференции и мероприятия\n"
    "/report — отчёт за месяц\n"
    "/export — сформировать списки\n"
    "/admins — администраторы (только супер-админ)"
)

INPUT_NOT_TEXT = "✍️ Отправьте, пожалуйста, ответ обычным текстом."
INPUT_TOO_LONG = "⚠️ Слишком длинно — не больше {max_len} символов."
INVALID_DATE = "⚠️ Не удалось распознать дату."
ACTION_EXPIRED = "⚠️ Это действие уже неактуально. Откройте меню: /menu"
FALLBACK_REGISTERED = "🤔 Не понял сообщение. Выберите действие в меню:"
FALLBACK_UNREGISTERED = "👋 Чтобы начать, отправьте /start"
FALLBACK_CALLBACK = "⚠️ Кнопка устарела или недоступна."
NOTHING_FOUND = "😕 Ничего не найдено."

# --- Student ------------------------------------------------------------------------------------------------------

PROFILE_CARD = "👤 <b>{full_name}</b>\n🎓 Группа: {group_number}\n🏷 Роль: {role_label}\n📁 Проекты: {projects}"

MY_SUBMISSIONS_TITLE = "📜 <b>Мои заявки</b>"
MY_SUBMISSIONS_EMPTY = "📭 У вас пока нет заявок. Подать заявку можно в главном меню."
WITHDRAW_CONFIRM = "↩️ Отозвать заявку «{title}»?"
WITHDRAW_DONE = "↩️ Заявка отозвана."

SUBMISSION_CHOOSE_TYPE = "За что подаём заявку на надбавку?"
PICK_EVENT = "{icon} Выберите {acc} из списка или добавьте новую."
PICK_EVENT_EMPTY = "{icon} Список пока пуст — добавьте {acc}."
ASK_EVENT_SEARCH = "🔎 Введите часть названия."
ASK_NEW_EVENT_NAME = "📝 Название {gen}:"
ASK_NEW_EVENT_DATE = "📅 Дата проведения в формате <b>ДД.ММ.ГГГГ</b>, например <code>12.09.2026</code>."
ASK_CONFERENCE_PROJECT = "📁 С каким проектом выступали? Выберите или напишите название."
ASK_EVENT_WHAT_DID = "🙋 Опишите, <b>что вы делали</b> на мероприятии."
SUBMISSION_CONFIRM = (
    "✅ <b>Проверьте заявку — {label}</b>\n\n{event_line}\n{details}\n\nОтправить админам на подтверждение?"
)
SUBMISSION_DUPLICATE = "⚠️ По «{name}» у вас уже есть заявка — на рассмотрении или одобренная."
SUBMISSION_SENT = "📨 Заявка отправлена админам на рассмотрение. Мы уведомим вас о результате."

# --- Request cards and notifications ------------------------------------------------------------------------------

REQUEST_CARD = (
    "🆕 <b>Заявка — {label}</b>\n\n👤 {full_name} ({group_number})\n{event_line}\n{details}\n🕒 Подана: {submitted}"
)
EVENT_LINE = "{icon} {name} · {date}"
UNVERIFIED_MARK = " ❔"
DETAIL_PROJECT = "📁 Проект: {value}"
DETAIL_WHAT_DID = "🙋 Что делал(а): {value}"
DETAIL_NONE = "—"

CARD_PROCESSED_APPROVED = "\n\n✅ <b>Одобрено, {amount} BYN</b> — {admin_name}, {date}"
CARD_PROCESSED_REJECTED = "\n\n❌ <b>Отклонено</b> — {admin_name}, {date}{reason_part}"
CARD_WITHDRAWN = "\n\n↩️ <b>Отозвана студентом</b> — {date}"
CARD_STUDENT_ARCHIVED = "\n\n🗄 <b>Студент перенесён в архив</b> — {date}"
CARD_DELETED = "\n\n🗑 <b>Заявка удалена</b> — {date}"
CARD_ALREADY_PROCESSED_ALERT = "⚠️ Заявка уже обработана."
INVALID_AMOUNT_ALERT = "⚠️ Некорректная сумма."
APPROVED_ALERT = "✅ Одобрено"
REASON_PART = "\nПричина: {reason}"

STUDENT_NOTIFY_APPROVED = "✅ Ваша заявка «{title}» одобрена! Начислено {amount} BYN."
STUDENT_NOTIFY_REJECTED = "❌ Ваша заявка «{title}» отклонена.{reason_part}"
STUDENT_NOTIFY_AWARD = "✅ Вам начислено {amount} BYN за «{title}»."
STUDENT_NOTIFY_CANCELLED = "🚫 Начисление за «{title}» отменено.{reason_part}"
STUDENT_NOTIFY_AMOUNT_CHANGED = "✏️ Сумма за «{title}» изменена: {amount} BYN."
STUDENT_NOTIFY_PROJECT_ADDED = "📁 Вы добавлены в проект «{name}»."
STUDENT_NOTIFY_PROJECT_REMOVED = "📁 Вы больше не участник проекта «{name}»."

# --- Admin: requests ----------------------------------------------------------------------------------------------

QUEUE_TITLE = "📥 <b>Заявки на рассмотрении</b>: {count}\nСначала самые старые."
QUEUE_EMPTY = "📥 Заявок на рассмотрении нет 🎉"
ASK_REJECT_REASON = "✍️ Укажите причину отказа или нажмите «Пропустить»."
REJECT_DONE = "❌ Заявка отклонена."
APPROVE_DONE = "✅ Заявка одобрена: {amount} BYN."

# --- Admin: students ----------------------------------------------------------------------------------------------

STUDENTS_TITLE = "👥 <b>Студенты</b> — {label}: {count}\n📁 проект · ✅ одобрено · ⏳ на рассмотрении · 👑 админ"
FILTER_LABELS = {
    "all": "все",
    "proj": "в проектах",
    "conf": "с конференциями",
    "idle": "без активности",
    "arch": "архив",
    "grp": "группа {group}",
    "q": "поиск «{query}»",
}
ASK_STUDENT_SEARCH = "🔎 Введите фамилию, имя или группу."
GROUPS_TITLE = "🎓 Выберите группу:"

STUDENT_HISTORY_TITLE = "📜 <b>История: {name}</b>"
STUDENT_HISTORY_EMPTY = "Заявок и начислений пока нет."
ASK_CANCEL_REASON = "✍️ Причина отмены начисления — или нажмите «Пропустить»."
CANCEL_DONE = "🚫 Начисление отменено."
PICK_NEW_AMOUNT = "✏️ Выберите новую сумму:"
AMOUNT_CHANGED = "✏️ Сумма изменена: {amount} BYN."

PICK_PROJECT_FOR_STUDENT = "📁 В какой проект добавить {name}?"
NO_PROJECTS = "📁 Проектов пока нет — создайте проект в разделе «Проекты»."
PROJECT_MEMBER_ADDED = "📁 {name} в проекте «{project}», оплата с месяца {period}."
PROJECT_MEMBER_EXISTS = "ℹ️ {name} уже участник «{project}»."
PICK_MEMBERSHIP_TO_END = "➖ Из какого проекта убрать {name}?"
CONFIRM_END_MEMBERSHIP = "➖ Убрать {name} из «{project}»?\n\nМесяц {period} уже не будет оплачен."
MEMBERSHIP_ENDED = "➖ {name} больше не в «{project}»."

AWARD_PICK_EVENT = "{icon} За какую {acc} начислить {name}? Выберите или добавьте новую."
AWARD_ASK_PROJECT = "📁 С каким проектом выступал(а)? Выберите, напишите или пропустите."
AWARD_ASK_WHAT_DID = "🙋 Что делал(а) на мероприятии? Напишите или пропустите."
AWARD_PICK_AMOUNT = "💰 Выберите сумму для {name}:"
AWARD_CONFIRM = "✅ <b>Начислить {amount} BYN?</b>\n\n👤 {student}\n{event_line}\n{details}\n📅 Месяц: {period}"
AWARD_DONE = "✅ Начислено {amount} BYN за «{event}»."

ROLE_CONFIRM_PROMOTE = "👑 Назначить <b>{name}</b> администратором?"
ROLE_CONFIRM_DEMOTE = "👑 Снять права администратора у <b>{name}</b>?"
ROLE_PROMOTED = "👑 {name} теперь администратор."
ROLE_DEMOTED = "👑 {name} больше не администратор."

ARCHIVE_CONFIRM = (
    "🗄 Перенести <b>{name}</b> в архив?\n\n"
    "Студент будет заблокирован в боте и выбудет из проектов (текущий месяц уже не оплачивается), "
    "заявки на рассмотрении будут отозваны. История сохранится, из архива можно вернуть."
)
ARCHIVED_DONE = "🗄 {name} в архиве."
UNARCHIVED_DONE = "♻️ {name} возвращён(а) из архива."

DELETE_UNDO_NOTE = (
    "\n\nОтменить нельзя — вернуть данные можно только из ночной копии базы. "
    "Чтобы просто скрыть запись, используйте архив."
)
DELETE_STUDENT_CONFIRM = (
    "🗑 <b>Удалить {name} навсегда?</b>\n\n"
    "Вместе со студентом удалятся заявки и начисления: {supplements} (одобренных — {approved}), "
    "участия в проектах: {memberships}. Суммы в отчётах и списках за прошлые месяцы изменятся."
)
DELETE_ADMIN_NOTE = "\nОтметки о том, кто одобрял заявки других студентов, сохранятся."
DELETE_PROJECT_CONFIRM = (
    "🗑 <b>Удалить проект «{name}» навсегда?</b>\n\n"
    "Вместе с проектом удалятся все участия в нём: {memberships}. "
    "Проектные надбавки за прошлые месяцы пропадут из отчётов и списков."
)
DELETE_EVENT_CONFIRM = (
    "🗑 <b>Удалить «{name}» навсегда?</b>\n\n"
    "Вместе с записью удалятся все заявки и начисления по ней: {supplements} (одобренных — {approved}). "
    "Суммы в отчётах и списках за прошлые месяцы изменятся."
)
STUDENT_DELETED = "🗑 {name} удалён(а)."
PROJECT_DELETED = "🗑 Проект «{name}» удалён."
EVENT_DELETED = "🗑 «{name}» удалено."

# --- Admin: catalogs ----------------------------------------------------------------------------------------------

PROJECTS_TITLE = "📁 <b>Проекты</b>: {count}"
ASK_PROJECT_NAME = "📝 Название проекта:"
ASK_PROJECT_REGALIA = "🏅 Регалии проекта (награды, достижения) — или нажмите «Пропустить»."
PROJECT_SAVED = "✅ Проект сохранён."
PICK_STUDENT_FOR_PROJECT = "👥 Кого добавить в «{project}»?"
PICK_MEMBER_TO_REMOVE = "➖ Кого убрать из «{project}»?"
PROJECT_ARCHIVE_CONFIRM = "🗄 Архивировать «{name}»?\n\nВсе участники выбудут, месяц {period} уже не оплачивается."
PROJECT_ARCHIVED = "🗄 Проект «{name}» в архиве."
PROJECT_RESTORED = "♻️ Проект «{name}» восстановлен."

EVENTS_TITLE = "{icon} <b>{plural}</b>: {count}\n❔ — добавлено студентом и ещё не подтверждено · 🗄 — в архиве"
ASK_EVENT_RENAME = "📝 Новое название:"
EVENT_SAVED = "✅ Запись сохранена."
EVENT_MERGE_PICK = "🔀 С какой записью объединить «{name}»?\n\nВсе заявки перейдут в выбранную, эта уйдёт в архив."
EVENT_MERGE_CONFIRM = "🔀 Перенести все заявки из «{source}» в «{target}» и архивировать «{source}»?"
EVENT_MERGED = "🔀 Объединено с «{name}»."
EVENT_MERGE_DUPLICATES = "\n⚠️ Закрыто дублей: {count} — у этих студентов уже была заявка в выбранной записи."

# --- Admin: reports, lists, admins, backups -----------------------------------------------------------------------

REPORT_CHOOSE_MONTH = "📅 За какой период сформировать отчёт?"
EXPORT_CHOOSE_MONTH = "📅 За какой период сформировать списки?"
ASK_CUSTOM_MONTH = "Введите месяц в формате <b>ММ.ГГГГ</b>, например <code>09.2026</code>."
INVALID_MONTH_FORMAT = "⚠️ Не удалось распознать месяц."

EXPORT_EMPTY = "📭 За {month_name} нет ни одного студента с начислениями."
EXPORT_SENT = "📄 Списки за {month_name} отправлены выше."
EXPORT_CAPTION_OFFICIAL = "📄 Официальный список надбавок за {month_name}"
EXPORT_CAPTION_INTERNAL = "🗂 Внутренний список за {month_name} (с основаниями и 25% в лабу)"
AUTO_EXPORT_PREFIX = "🤖 Автоматическая рассылка\n"

ADMIN_LIST_TITLE = "👑 <b>Администраторы</b>\n\nНазначить или снять админа можно в карточке студента."
ADMIN_LIST_EMPTY = "👑 <b>Администраторы</b>\n\nПока никто не назначен. Назначить можно в карточке студента."

BACKUP_CAPTION = "💾 Еженедельная копия базы данных за {date}"

# --- Buttons ------------------------------------------------------------------------------------------------------

CANCEL_BUTTON = "❌ Отмена"
SKIP_BUTTON = "⏭ Пропустить"
CONFIRM_BUTTON = "✅ Подтвердить"
RETRY_BUTTON = "🔄 Начать заново"
BACK_BUTTON = "⬅️ Назад"
MAIN_MENU_BUTTON = "⬅️ В главное меню"
SEARCH_BUTTON = "🔎 Поиск"
ADD_NEW_BUTTON = "➕ Добавить новую"
DELETE_BUTTON = "🗑 Удалить"
DELETE_CONFIRM_BUTTON = "🗑 Да, удалить навсегда"
