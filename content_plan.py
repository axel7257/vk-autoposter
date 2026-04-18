from datetime import datetime, timedelta
import json
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Оптимальное время публикации по площадкам
BEST_TIMES = {
    "vk_personal":  ["19:00", "21:00", "12:00"],
    "vk_group":     ["19:00", "20:00", "12:00", "09:00"],
    "telegram":     ["08:00", "20:00", "12:00"],
    "dzen":         ["09:00", "19:00", "14:00"],
}

# Оптимальное чередование целей по дням недели
# Понедельник=0 ... Воскресенье=6
GOAL_BY_WEEKDAY = {
    0: "informing",       # Понедельник — полезное знание, хороший старт недели
    1: "teaching",        # Вторник — практический инструмент
    2: "reflection",      # Среда — остановиться и подумать
    3: "positioning",     # Четверг — экспертный пост
    4: "engagement",      # Пятница — вовлечение, вопрос к аудитории
    5: "viral",           # Суббота — лёгкий вирусный пост
    6: "soft_sell",       # Воскресенье — мягкая продажа
}

GOAL_LABELS = {
    "informing":    "Информирование",
    "teaching":     "Обучение",
    "reflection":   "Размышление",
    "engagement":   "Вовлечение",
    "positioning":  "Экспертное позиционирование",
    "soft_sell":    "Мягкая продажа",
    "viral":        "Вирусный / развлекательный",
}

PLATFORM_LABELS = {
    "vk_personal": "ВК — личная страница",
    "vk_group":    "ВК — группа",
    "telegram":    "Telegram",
    "dzen":        "Яндекс Дзен",
}


def generate_plan(
    platforms: dict[str, int],  # {"vk_personal": 3, "telegram": 5, ...}
    period_days: int,            # 7 или 30
    start_date: datetime = None,
    theme: str = "",             # необязательный тематический блок
) -> list[dict]:
    """
    Генерирует контент-план.
    Возвращает список записей: дата, время, площадка, тема (пустая), цель поста.
    """
    if start_date is None:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # начинаем со следующего дня
        start_date += timedelta(days=1)

    plan = []

    for platform, posts_per_week in platforms.items():
        if posts_per_week == 0:
            continue

        times = BEST_TIMES.get(platform, ["12:00"])
        time_index = 0

        # Вычисляем на какие дни недели ставить посты
        weekdays = _spread_weekdays(posts_per_week)

        current_date = start_date
        week_num = 0

        while current_date < start_date + timedelta(days=period_days):
            weekday = current_date.weekday()
            if weekday in weekdays:
                post_time = times[time_index % len(times)]
                time_index += 1
                goal = GOAL_BY_WEEKDAY[weekday]
                hour, minute = map(int, post_time.split(":"))
                post_datetime = current_date.replace(hour=hour, minute=minute)

                plan.append({
                    "date": post_datetime.strftime("%d.%m.%Y"),
                    "time": post_time,
                    "datetime_iso": post_datetime.isoformat(),
                    "platform": platform,
                    "platform_label": PLATFORM_LABELS[platform],
                    "theme": theme,
                    "topic": "",       # пользователь заполнит или оставит пустым
                    "goal": goal,
                    "goal_label": GOAL_LABELS[goal],
                    "status": "не готов",  # не готов / готов / опубликован
                    "post_text": "",
                })

            current_date += timedelta(days=1)

    # Сортируем по дате и времени
    plan.sort(key=lambda x: x["datetime_iso"])
    return plan


def _spread_weekdays(posts_per_week: int) -> set[int]:
    """Равномерно распределяет посты по дням недели."""
    all_days = [0, 2, 4, 1, 3, 5, 6]  # пн, ср, пт, вт, чт, сб, вс
    return set(all_days[:min(posts_per_week, 7)])


def generate_topics_for_plan(plan: list[dict], theme: str) -> list[dict]:
    """
    Для каждого поста в плане генерирует конкретную тему,
    связанную с тематическим блоком.
    """
    if not theme or not plan:
        return plan

    # Собираем список постов для которых нужны темы
    entries = []
    for i, item in enumerate(plan):
        entries.append(
            f"{i+1}. Площадка: {item['platform_label']}, Цель: {item['goal_label']}"
        )

    prompt = f"""Ты помощник психотерапевта, который ведёт соцсети.
Тематический блок на период: «{theme}».

Придумай темы постов для каждого поста ниже. Требования:
- Темы должны быть связаны между собой и образовывать логическую серию: от общего к частному, или от проблемы к решению, или по нарастающей глубине
- Каждая тема короткая (5–10 слов), живая, конкретная — не академическая
- Тема точно соответствует цели поста и площадке
- Вместе темы рассказывают историю или разворачивают тему с разных сторон

Посты:
{chr(10).join(entries)}

Ответь строго в формате — по одной теме на строку, без нумерации, без пояснений:
тема 1
тема 2
...
"""

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    topics = [line.strip() for line in response.content[0].text.strip().split("\n") if line.strip()]

    for i, item in enumerate(plan):
        if i < len(topics):
            item["topic"] = topics[i]

    return plan


def save_plan(plan: list[dict], path: str = "content_plan.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def load_plan(path: str = "content_plan.json") -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)
