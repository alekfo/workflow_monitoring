"""
i_AM_ready.py — скрипт самодиагностики перед изменением базы.
"""

import sys
import random
import time

BANNER = r"""
 ____  ____     _    __  __   ____  _____    _    ______   __
|  _ \| __ )   / \  |  \/  | |  _ \| ____|  / \  |  _ \ \ / /
| | | |  _ \  / _ \ | |\/| | | |_) |  _|   / _ \ | | | \ V /
| |_| | |_) |/ ___ \| |  | | |  _ <| |___ / ___ \| |_| || |
|____/|____//_/   \_\_|  |_| |_| \_\_____/_/   \_\____/ |_|

  workflow_monitoring — и снова в бой!
"""

MOTIVATIONAL_PHRASES = [
    "Миграции не страшны. Страшно когда их нет.",
    "git commit -m 'надеюсь это не сломает прод'",
    "null=True, blank=True — лучшие друзья разработчика.",
    "ALTER TABLE — звучит как заклинание.",
    "Backup? Мы это делаем... иногда.",
    "Каждая миграция — это маленький шаг к production.",
    "В любой непонятной ситуации — makemigrations.",
    "SQLite сегодня, PostgreSQL завтра. Может быть.",
]

MODELS = {
    "Station": ["name", "road", "description", "latitude", "longitude", "created_by"],
    "Task": ["station", "description", "status", "responsible_organization", "responsible_user", "due_date"],
    "Comment": ["task", "user", "body"],
    "Attachment": ["task", "file", "description"],
    "AlarmInfo": ["number", "description", "explanation"],
    "Knowledge": ["title", "description", "file", "external_link"],
    "Link": ["user", "title", "url", "description"],
}


def loading_bar(label: str, steps: int = 20, delay: float = 0.03) -> None:
    print(f"\n  {label}")
    bar = ""
    for i in range(steps + 1):
        bar = "#" * i + "-" * (steps - i)
        pct = int(i / steps * 100)
        print(f"\r  [{bar}] {pct}%", end="", flush=True)
        time.sleep(delay)
    print()


def inspect_models() -> None:
    print("\n  Известные модели в signal1520:\n")
    for model, fields in MODELS.items():
        print(f"    {model:15s} — {len(fields)} поля/полей: {', '.join(fields)}")


def self_check() -> bool:
    checks = [
        ("Python версии 3.8+",   sys.version_info >= (3, 8)),
        ("Мозг подключён",        True),
        ("Кофе в наличии",        random.choice([True, True, True, False])),
        ("Бэкап базы сделан",     random.choice([True, False])),
        ("Тесты написаны",        False),
    ]

    print("\n  Самодиагностика перед миграцией:\n")
    all_ok = True
    for name, status in checks:
        icon = "OK" if status else "!!"
        print(f"    [{icon}]  {name}")
        if not status:
            all_ok = False
    return all_ok


def main() -> None:
    print(BANNER)

    loading_bar("Загружаю энтузиазм...", steps=30, delay=0.02)
    loading_bar("Проверяю готовность к миграциям...", steps=25, delay=0.025)

    inspect_models()
    ready = self_check()

    print(f"\n  Случайная мудрость дня:\n  \"{random.choice(MOTIVATIONAL_PHRASES)}\"\n")

    if ready:
        print("  *** Всё зелёно. Можно трогать базу! ***\n")
    else:
        print("  *** Не всё идеально, но кого это останавливало? Вперёд! ***\n")


if __name__ == "__main__":
    main()
