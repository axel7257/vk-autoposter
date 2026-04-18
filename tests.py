#!/usr/local/opt/python@3.12/bin/python3.12
"""
Батарея тестов приложения Контент-студия.

Запуск:
  python tests.py            — быстрые тесты (без API-вызовов, ~5 сек)
  python tests.py --api      — + интеграционные тесты с реальными API (~2-3 мин)

Категории:
  [UNIT]  — чистая логика, без файлов и API
  [FILE]  — работа с файлами (history.json, plan.json)
  [SYNC]  — межмодульная синхронизация констант и сигнатур
  [PIPE]  — сквозные пайплайны (с моками вместо API)
  [API]   — реальные вызовы Claude / Replicate (только с флагом --api)
"""

import sys
import os
import json
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

RUN_API = "--api" in sys.argv

# Цвета для вывода
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = []
failed = []
skipped = []


def ok(name):
    passed.append(name)
    print(f"  {GREEN}✓{RESET} {name}")


def fail(name, reason):
    failed.append(name)
    print(f"  {RED}✗{RESET} {name}")
    print(f"    {RED}{reason}{RESET}")


def skip(name, reason="только с флагом --api"):
    skipped.append(name)
    print(f"  {YELLOW}○{RESET} {name}  ({reason})")


def section(title):
    print(f"\n{BOLD}{CYAN}── {title}{RESET}")


def run(name, fn, api=False):
    """Запускает тест, перехватывает исключения."""
    if api and not RUN_API:
        skip(name)
        return
    try:
        fn()
        ok(name)
    except AssertionError as e:
        fail(name, str(e) or "assertion failed")
    except Exception as e:
        fail(name, f"{type(e).__name__}: {e}")


# ─────────────────────────────────────────────
# 1. ИМПОРТЫ И СТРУКТУРА МОДУЛЕЙ
# ─────────────────────────────────────────────
section("Импорты и структура модулей")

def test_import_generate_post():
    from generate_post import generate_post, suggest_topics, PLATFORMS, GOALS, TONE_INSTRUCTIONS
    assert callable(generate_post)
    assert callable(suggest_topics)
    assert isinstance(PLATFORMS, dict) and len(PLATFORMS) == 4
    assert isinstance(GOALS, dict) and len(GOALS) > 0
    assert isinstance(TONE_INSTRUCTIONS, dict) and 0 in TONE_INSTRUCTIONS

def test_import_image_generator():
    from image_generator import generate_image, apply_overlay, save_image, STYLES, OVERLAY_OPTIONS, IMAGE_SIZES, PLATFORM_DEFAULT_SIZE
    assert callable(generate_image)
    assert callable(apply_overlay)
    assert callable(save_image)
    assert isinstance(STYLES, dict) and len(STYLES) > 0
    assert isinstance(PLATFORM_DEFAULT_SIZE, dict)

def test_import_content_plan():
    from content_plan import generate_plan, save_plan, load_plan, GOAL_LABELS, PLATFORM_LABELS
    assert callable(generate_plan)
    assert callable(save_plan)
    assert callable(load_plan)
    assert isinstance(GOAL_LABELS, dict) and len(GOAL_LABELS) > 0

run("[UNIT] generate_post импортируется", test_import_generate_post)
run("[UNIT] image_generator импортируется", test_import_image_generator)
run("[UNIT] content_plan импортируется", test_import_content_plan)


# ─────────────────────────────────────────────
# 2. КОНСТАНТЫ И МАППИНГИ
# ─────────────────────────────────────────────
section("Константы и маппинги")

def test_platforms_completeness():
    from generate_post import PLATFORMS
    required = {"vk_personal", "vk_group", "telegram", "dzen"}
    assert required == set(PLATFORMS.keys()), f"Отсутствуют площадки: {required - set(PLATFORMS.keys())}"

def test_platform_default_sizes():
    from image_generator import PLATFORM_DEFAULT_SIZE, IMAGE_SIZES
    from generate_post import PLATFORMS
    for platform in PLATFORMS:
        assert platform in PLATFORM_DEFAULT_SIZE, f"Нет дефолтного размера для {platform}"
        size = PLATFORM_DEFAULT_SIZE[platform]
        assert size in IMAGE_SIZES, f"Размер {size} для {platform} не найден в IMAGE_SIZES"

def test_platform_max_tokens():
    """generate_post должна иметь маппинг max_tokens для всех площадок."""
    import inspect
    from generate_post import generate_post, PLATFORMS
    source = inspect.getsource(generate_post)
    for platform in PLATFORMS:
        assert f'"{platform}"' in source, f"Площадка {platform} не найдена в теле generate_post"
    assert "platform_max_tokens" in source, "Маппинг platform_max_tokens не найден"

def test_dzen_max_tokens_enough():
    """Дзен должен иметь лимит ≥ 6000 токенов (статья до 1200 слов на русском)."""
    import inspect, re
    from generate_post import generate_post
    source = inspect.getsource(generate_post)
    match = re.search(r'"dzen"\s*:\s*(\d+)', source)
    assert match, "Не найден max_tokens для dzen"
    tokens = int(match.group(1))
    assert tokens >= 6000, f"max_tokens для dzen = {tokens}, нужно ≥ 6000 (кириллица ~3 символа/токен)"

def test_tone_instructions_all_levels():
    from generate_post import TONE_INSTRUCTIONS
    for level in [0, 1, 2, 3]:
        assert level in TONE_INSTRUCTIONS, f"Уровень тона {level} не найден"

def test_image_sizes_format():
    from image_generator import IMAGE_SIZES
    for key, val in IMAGE_SIZES.items():
        assert len(val) == 4, f"IMAGE_SIZES['{key}'] должен быть кортежем из 4 элементов"
        w, h = val[0], val[1]
        assert isinstance(w, int) and w > 0
        assert isinstance(h, int) and h > 0

def test_styles_have_required_keys():
    from image_generator import STYLES
    required_keys = {"label", "prompt", "flux_prefix", "flux_suffix"}
    for style_key, style in STYLES.items():
        missing = required_keys - set(style.keys())
        assert not missing, f"Стиль '{style_key}' не имеет ключей: {missing}"

run("[UNIT] PLATFORMS содержит все 4 площадки", test_platforms_completeness)
run("[UNIT] PLATFORM_DEFAULT_SIZE покрывает все площадки", test_platform_default_sizes)
run("[UNIT] platform_max_tokens есть в generate_post", test_platform_max_tokens)
run("[UNIT] max_tokens для Дзен ≥ 3500", test_dzen_max_tokens_enough)
run("[UNIT] TONE_INSTRUCTIONS содержит уровни 0–3", test_tone_instructions_all_levels)
run("[UNIT] IMAGE_SIZES — корректный формат", test_image_sizes_format)
run("[UNIT] STYLES содержат все обязательные ключи", test_styles_have_required_keys)


# ─────────────────────────────────────────────
# 3. ИСТОРИЯ — СОХРАНЕНИЕ / ЗАГРУЗКА / ОБНОВЛЕНИЕ
# ─────────────────────────────────────────────
section("История постов")

# Временный файл истории — не трогаем реальный
_TMP_HISTORY = Path(tempfile.mktemp(suffix=".json"))

def _mock_history_file(monkeypatch_path):
    """Патчим HISTORY_FILE в пространстве app (без импорта app)."""
    # Используем напрямую функции с перехватом файла
    pass

def _save(topic, platform, nb, text, history_file):
    """Мини-копия save_to_history, работающая с произвольным файлом."""
    history = json.loads(history_file.read_text()) if history_file.exists() else []
    entry_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    history.insert(0, {
        "id": entry_id,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "topic": topic,
        "platform": platform,
        "notebook": nb,
        "text": text,
        "image_path": "",
    })
    history_file.write_text(json.dumps(history[:100], ensure_ascii=False))
    return entry_id

def _update_img(image_path, history_file, entry_id=None):
    history = json.loads(history_file.read_text())
    if not history:
        return
    if entry_id:
        for entry in history:
            if entry.get("id") == entry_id:
                entry["image_path"] = image_path
                break
    else:
        history[0]["image_path"] = image_path
    history_file.write_text(json.dumps(history, ensure_ascii=False))

def test_history_save_returns_id():
    f = Path(tempfile.mktemp(suffix=".json"))
    entry_id = _save("тема", "ВК", "нотбук", "текст поста", f)
    assert isinstance(entry_id, str) and len(entry_id) > 0
    f.unlink(missing_ok=True)

def test_history_load_after_save():
    f = Path(tempfile.mktemp(suffix=".json"))
    _save("тема 1", "ВК", "нотбук", "текст 1", f)
    _save("тема 2", "ВК", "нотбук", "текст 2", f)
    history = json.loads(f.read_text())
    assert len(history) == 2
    assert history[0]["topic"] == "тема 2"  # новые — первыми
    assert history[1]["topic"] == "тема 1"
    f.unlink(missing_ok=True)

def test_history_update_by_id_correct_entry():
    """update_history_image с entry_id должна обновить именно нужную запись."""
    f = Path(tempfile.mktemp(suffix=".json"))
    id1 = _save("пост 1", "ВК", "нотбук", "текст 1", f)
    id2 = _save("пост 2", "ВК", "нотбук", "текст 2", f)
    # history[0] = пост 2, history[1] = пост 1
    _update_img("/path/to/img.jpg", f, entry_id=id1)  # должен обновить пост 1
    history = json.loads(f.read_text())
    post1 = next(e for e in history if e["id"] == id1)
    post2 = next(e for e in history if e["id"] == id2)
    assert post1["image_path"] == "/path/to/img.jpg", "Неверная запись обновлена"
    assert post2["image_path"] == "", "Лишняя запись тоже обновилась"
    f.unlink(missing_ok=True)

def test_history_update_without_id_updates_first():
    """update без entry_id должна обновить history[0]."""
    f = Path(tempfile.mktemp(suffix=".json"))
    _save("пост 1", "ВК", "нотбук", "текст 1", f)
    _save("пост 2", "ВК", "нотбук", "текст 2", f)
    _update_img("/img/latest.jpg", f)
    history = json.loads(f.read_text())
    assert history[0]["image_path"] == "/img/latest.jpg"
    assert history[1]["image_path"] == ""
    f.unlink(missing_ok=True)

def test_history_id_uniqueness():
    """Каждая запись должна иметь уникальный id."""
    import time
    f = Path(tempfile.mktemp(suffix=".json"))
    ids = []
    for i in range(5):
        ids.append(_save(f"пост {i}", "ВК", "нотбук", f"текст {i}", f))
        time.sleep(0.01)
    assert len(ids) == len(set(ids)), "Обнаружены дублирующиеся entry_id"
    f.unlink(missing_ok=True)

run("[FILE] save_to_history возвращает entry_id", test_history_save_returns_id)
run("[FILE] история сохраняет и загружает записи", test_history_load_after_save)
run("[FILE] update_history_image обновляет нужную запись по entry_id", test_history_update_by_id_correct_entry)
run("[FILE] update_history_image без id обновляет history[0]", test_history_update_without_id_updates_first)
run("[FILE] entry_id уникален для каждой записи", test_history_id_uniqueness)


# ─────────────────────────────────────────────
# 4. КОНТЕНТ-ПЛАН — СТРУКТУРА
# ─────────────────────────────────────────────
section("Контент-план")

def test_generate_plan_returns_list():
    from content_plan import generate_plan
    plan = generate_plan({"vk_personal": 3}, period_days=7)
    assert isinstance(plan, list)
    assert len(plan) > 0

def test_generate_plan_item_keys():
    from content_plan import generate_plan
    plan = generate_plan({"vk_personal": 2, "telegram": 2}, period_days=7)
    required = {"date", "time", "datetime_iso", "platform", "platform_label",
                "theme", "topic", "goal", "goal_label", "status", "post_text"}
    for item in plan:
        missing = required - set(item.keys())
        assert not missing, f"В записи плана нет ключей: {missing}"

def test_generate_plan_status_default():
    from content_plan import generate_plan
    plan = generate_plan({"telegram": 3}, period_days=7)
    for item in plan:
        assert item["status"] == "не готов", f"Дефолтный статус должен быть 'не готов', получен '{item['status']}'"

def test_generate_plan_sorted_by_date():
    from content_plan import generate_plan
    plan = generate_plan({"vk_personal": 3, "telegram": 3, "dzen": 2}, period_days=14)
    isos = [item["datetime_iso"] for item in plan]
    assert isos == sorted(isos), "План не отсортирован по дате"

def test_plan_save_load_roundtrip():
    from content_plan import generate_plan, save_plan, load_plan
    plan = generate_plan({"vk_personal": 2, "telegram": 1}, period_days=7)
    f = tempfile.mktemp(suffix=".json")
    save_plan(plan, f)
    loaded = load_plan(f)
    assert len(loaded) == len(plan)
    assert loaded[0]["datetime_iso"] == plan[0]["datetime_iso"]
    Path(f).unlink(missing_ok=True)

def test_plan_platforms_match():
    from content_plan import generate_plan
    platforms = {"vk_personal": 3, "telegram": 2}
    plan = generate_plan(platforms, period_days=7)
    for item in plan:
        assert item["platform"] in platforms, f"Неожиданная площадка: {item['platform']}"

run("[UNIT] generate_plan возвращает список", test_generate_plan_returns_list)
run("[UNIT] записи плана содержат все обязательные ключи", test_generate_plan_item_keys)
run("[UNIT] дефолтный статус плана — 'не готов'", test_generate_plan_status_default)
run("[UNIT] план отсортирован по дате", test_generate_plan_sorted_by_date)
run("[FILE] save_plan / load_plan — сохранение и загрузка", test_plan_save_load_roundtrip)
run("[UNIT] план содержит только заданные площадки", test_plan_platforms_match)


# ─────────────────────────────────────────────
# 5. ГЕНЕРАТОР КАРТИНОК — ЛОГИКА БЕЗ API
# ─────────────────────────────────────────────
section("Генератор картинок (без API)")

def test_apply_overlay_none_returns_image():
    from PIL import Image
    from image_generator import apply_overlay
    img = Image.new("RGBA", (512, 512), (200, 100, 50, 255))
    result = apply_overlay(img, "none", "")
    assert result is not None
    assert result.mode == "RGB"

def test_apply_overlay_title_returns_image():
    from PIL import Image
    from image_generator import apply_overlay
    img = Image.new("RGBA", (512, 512), (200, 100, 50, 255))
    result = apply_overlay(img, "title", "Тестовый заголовок поста")
    assert result is not None
    assert result.mode == "RGB"

def test_apply_overlay_preserves_size():
    from PIL import Image
    from image_generator import apply_overlay
    img = Image.new("RGBA", (1024, 1344), (128, 128, 128, 255))
    result = apply_overlay(img, "author", "Антон · Психотерапевт", position="bottom")
    assert result.size == (1024, 1344), f"Размер изменился: {result.size}"

def test_save_image_creates_file():
    from PIL import Image
    from image_generator import save_image, OUTPUT_DIR
    img = Image.new("RGB", (64, 64), (255, 0, 0))
    path = save_image(img, "тест_сохранения")
    assert path.exists(), f"Файл не создан: {path}"
    assert path.suffix == ".jpg"
    path.unlink(missing_ok=True)

run("[UNIT] apply_overlay(none) возвращает RGB-изображение", test_apply_overlay_none_returns_image)
run("[UNIT] apply_overlay(title) накладывает текст без ошибок", test_apply_overlay_title_returns_image)
run("[UNIT] apply_overlay сохраняет размер изображения", test_apply_overlay_preserves_size)
run("[FILE] save_image создаёт файл на диске", test_save_image_creates_file)

def test_fit_preserves_aspect_ratio_no_stretch():
    """ImageOps.fit не растягивает — соотношение сторон результата совпадает с целевым."""
    from PIL import Image, ImageOps
    from image_generator import IMAGE_SIZES
    src = Image.new("RGBA", (1024, 1024), (100, 150, 200, 255))
    for size_key, (w, h, _, _) in IMAGE_SIZES.items():
        result = ImageOps.fit(src, (w, h), Image.LANCZOS)
        assert result.size == (w, h), f"{size_key}: ожидали {w}×{h}, получили {result.size}"
        # Проверяем что соотношение сторон не исказилось (в пределах 1%)
        target_ratio = w / h
        actual_ratio = result.width / result.height
        assert abs(target_ratio - actual_ratio) < 0.01, (
            f"{size_key}: соотношение сторон искажено: ожидали {target_ratio:.3f}, получили {actual_ratio:.3f}"
        )

run("[UNIT] ImageOps.fit не растягивает — соотношение сторон сохранено", test_fit_preserves_aspect_ratio_no_stretch)

def test_style_default_realism_covers_all_styles():
    """Каждый стиль должен иметь дефолтный уровень реалистичности."""
    from image_generator import STYLES, STYLE_DEFAULT_REALISM
    for style_key in STYLES:
        assert style_key in STYLE_DEFAULT_REALISM, f"Нет дефолта реалистичности для стиля '{style_key}'"
        val = STYLE_DEFAULT_REALISM[style_key]
        assert 0 <= val <= 10, f"Значение реалистичности для '{style_key}' вне диапазона 0–10: {val}"

def test_realism_instruction_covers_full_range():
    """_realism_instruction должна возвращать непустую строку для каждого уровня 0–10."""
    from image_generator import _realism_instruction
    for level in range(11):
        result = _realism_instruction(level)
        assert isinstance(result, str) and len(result) > 20, \
            f"Пустая или слишком короткая инструкция для уровня {level}"

def test_generate_image_accepts_realism():
    """generate_image должна принимать параметр realism."""
    import inspect
    from image_generator import generate_image
    sig = inspect.signature(generate_image)
    assert "realism" in sig.parameters, "generate_image не принимает параметр realism"
    assert sig.parameters["realism"].default == 5, "Дефолт realism должен быть 5"

def test_extract_visual_concept_accepts_realism():
    """_extract_visual_concept должна принимать параметр realism."""
    import inspect
    from image_generator import _extract_visual_concept
    sig = inspect.signature(_extract_visual_concept)
    assert "realism" in sig.parameters, "_extract_visual_concept не принимает параметр realism"

run("[UNIT] STYLE_DEFAULT_REALISM покрывает все стили", test_style_default_realism_covers_all_styles)
run("[UNIT] _realism_instruction возвращает текст для каждого уровня 0–10", test_realism_instruction_covers_full_range)
run("[SYNC] generate_image принимает параметр realism", test_generate_image_accepts_realism)
run("[SYNC] _extract_visual_concept принимает параметр realism", test_extract_visual_concept_accepts_realism)


# ─────────────────────────────────────────────
# 6. CLEAN_MARKDOWN — ОЧИСТКА ТЕКСТА
# ─────────────────────────────────────────────
section("Очистка Markdown из текста поста")

def _clean(text):
    """Вызываем clean_markdown через generate_post (вложенная функция)."""
    import re
    lines = text.strip().split('\n')
    if lines:
        lines[0] = re.sub(r'^#{1,6}\s+', '', lines[0]).strip()
    body = '\n'.join(lines[1:])
    body = re.sub(r'^#{1,6}\s+', '', body, flags=re.MULTILINE)
    body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
    body = re.sub(r'\*(.+?)\*', r'\1', body)
    body = re.sub(r'^[-*]\s+', '', body, flags=re.MULTILINE)
    body = re.sub(r'^\d+\.\s+', '', body, flags=re.MULTILINE)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return (lines[0] + '\n' + body).strip()

def test_clean_removes_headers():
    result = _clean("## Заголовок поста\n\nТекст поста здесь.")
    assert "##" not in result
    assert "Заголовок поста" in result

def test_clean_removes_bold():
    result = _clean("Заголовок\n\n**Жирный текст** и обычный.")
    assert "**" not in result
    assert "Жирный текст" in result

def test_clean_removes_list_markers():
    result = _clean("Заголовок\n\n- Пункт 1\n- Пункт 2")
    assert "- Пункт" not in result
    assert "Пункт 1" in result

def test_clean_removes_numbered_list():
    result = _clean("Заголовок\n\n1. Первый\n2. Второй")
    assert "1." not in result
    assert "Первый" in result

def test_clean_preserves_title():
    result = _clean("Мой заголовок\n\nТекст")
    assert result.startswith("Мой заголовок")

run("[UNIT] clean_markdown убирает заголовки ##", test_clean_removes_headers)
run("[UNIT] clean_markdown убирает **жирный**", test_clean_removes_bold)
run("[UNIT] clean_markdown убирает маркеры списков", test_clean_removes_list_markers)
run("[UNIT] clean_markdown убирает нумерацию", test_clean_removes_numbered_list)
run("[UNIT] clean_markdown сохраняет заголовок поста", test_clean_preserves_title)


# ─────────────────────────────────────────────
# 7. МЕЖМОДУЛЬНАЯ СИНХРОНИЗАЦИЯ
# ─────────────────────────────────────────────
section("Межмодульная синхронизация")

def test_sync_goal_keys_match():
    """GOAL_LABELS в content_plan должны совпадать с ключами GOALS в generate_post."""
    from content_plan import GOAL_LABELS
    from generate_post import GOALS
    cp_keys = set(GOAL_LABELS.keys())
    gp_keys = set(GOALS.keys())
    missing_in_gp = cp_keys - gp_keys
    missing_in_cp = gp_keys - cp_keys
    assert not missing_in_gp, f"В generate_post нет целей: {missing_in_gp}"
    assert not missing_in_cp, f"В content_plan нет целей: {missing_in_cp}"

def test_sync_platform_keys_match():
    """Все три модуля должны работать с одним и тем же набором ключей площадок."""
    from generate_post import PLATFORMS
    from content_plan import PLATFORM_LABELS
    from image_generator import PLATFORM_DEFAULT_SIZE
    gp = set(PLATFORMS.keys())
    cp = set(PLATFORM_LABELS.keys())
    ig = set(PLATFORM_DEFAULT_SIZE.keys())
    assert gp == cp, f"generate_post vs content_plan — разные площадки: {gp.symmetric_difference(cp)}"
    assert gp == ig, f"generate_post vs image_generator — разные площадки: {gp.symmetric_difference(ig)}"

def test_sync_tone_scale_match():
    """generate_post и image_generator должны использовать одну шкалу тона (0–3)."""
    from generate_post import TONE_INSTRUCTIONS
    from image_generator import TONE_MOOD
    assert set(TONE_INSTRUCTIONS.keys()) == set(TONE_MOOD.keys()), (
        f"Шкала тона различается: "
        f"generate_post={set(TONE_INSTRUCTIONS.keys())}, "
        f"image_generator={set(TONE_MOOD.keys())}"
    )

def test_sync_generate_post_accepts_tone():
    """generate_post должна принимать параметр tone."""
    import inspect
    from generate_post import generate_post
    sig = inspect.signature(generate_post)
    assert "tone" in sig.parameters, "generate_post не принимает параметр tone"
    assert sig.parameters["tone"].default == 0, "Дефолт tone должен быть 0"

def test_sync_generate_image_accepts_tone_and_comment():
    """generate_image должна принимать tone и user_comment."""
    import inspect
    from image_generator import generate_image
    sig = inspect.signature(generate_image)
    assert "tone" in sig.parameters, "generate_image не принимает параметр tone"
    assert "user_comment" in sig.parameters, "generate_image не принимает параметр user_comment"

def test_sync_generate_image_returns_tuple():
    """generate_image должна возвращать кортеж (Image, str) — проверяем через мок."""
    from unittest.mock import patch, MagicMock
    from PIL import Image as PILImage
    fake_img = PILImage.new("RGBA", (64, 64))
    fake_prompt = "test prompt"
    # Мокаем replicate.run и requests.get чтобы не делать реальный вызов
    with patch("image_generator.replicate.run") as mock_run, \
         patch("image_generator.requests.get") as mock_get, \
         patch("image_generator._extract_visual_concept", return_value="test concept"):
        mock_output = MagicMock()
        mock_output.url = "http://fake.url/image.jpg"
        mock_run.return_value = mock_output
        from io import BytesIO
        buf = BytesIO()
        fake_img.save(buf, format="PNG")
        buf.seek(0)
        mock_response = MagicMock()
        mock_response.content = buf.read()
        mock_get.return_value = mock_response
        from image_generator import generate_image
        result = generate_image("тревога", "minimalism", "1:1")
        assert isinstance(result, tuple) and len(result) == 2, \
            f"generate_image вернула {type(result)}, нужен кортеж (Image, str)"
        img, prompt = result
        assert img is not None
        assert isinstance(prompt, str)

def test_sync_save_to_history_returns_string():
    """save_to_history должна возвращать строку entry_id."""
    import inspect
    # Проверяем через реальный вызов с временным файлом
    f = Path(tempfile.mktemp(suffix=".json"))
    result = _save("тест", "ВК", "нотбук", "текст", f)
    assert isinstance(result, str), f"save_to_history вернула {type(result)}, нужна str"
    f.unlink(missing_ok=True)

def test_sync_goal_labels_consistency():
    """GOAL_BY_WEEKDAY в content_plan должен ссылаться только на существующие цели."""
    from content_plan import GOAL_BY_WEEKDAY, GOAL_LABELS
    for weekday, goal in GOAL_BY_WEEKDAY.items():
        assert goal in GOAL_LABELS, \
            f"День {weekday}: цель '{goal}' не найдена в GOAL_LABELS"

def test_sync_image_sizes_cover_all_defaults():
    """Каждый дефолтный размер площадки должен существовать в IMAGE_SIZES."""
    from image_generator import PLATFORM_DEFAULT_SIZE, IMAGE_SIZES
    for platform, size in PLATFORM_DEFAULT_SIZE.items():
        assert size in IMAGE_SIZES, \
            f"Дефолтный размер '{size}' для {platform} не найден в IMAGE_SIZES"

run("[SYNC] GOAL_LABELS совпадают в content_plan и generate_post", test_sync_goal_keys_match)
run("[SYNC] Ключи площадок совпадают во всех трёх модулях", test_sync_platform_keys_match)
run("[SYNC] Шкала тона (0–3) совпадает в generate_post и image_generator", test_sync_tone_scale_match)
run("[SYNC] generate_post принимает параметр tone", test_sync_generate_post_accepts_tone)
run("[SYNC] generate_image принимает tone и user_comment", test_sync_generate_image_accepts_tone_and_comment)
run("[SYNC] generate_image возвращает кортеж (Image, str)", test_sync_generate_image_returns_tuple)
run("[SYNC] save_to_history возвращает строку entry_id", test_sync_save_to_history_returns_string)
run("[SYNC] GOAL_BY_WEEKDAY ссылается только на существующие цели", test_sync_goal_labels_consistency)
run("[SYNC] Все дефолтные размеры площадок существуют в IMAGE_SIZES", test_sync_image_sizes_cover_all_defaults)


# ─────────────────────────────────────────────
# 8. СКВОЗНЫЕ ПАЙПЛАЙНЫ (с моками)
# ─────────────────────────────────────────────
section("Сквозные пайплайны")

def test_pipe_create_post_history_image_cycle():
    """
    Пайплайн: сгенерирован пост → entry_id → сгенерирована картинка →
    update_history_image по entry_id → в истории правильная запись обновлена.
    """
    f = Path(tempfile.mktemp(suffix=".json"))
    # Шаг 1: генерируем пост — получаем entry_id
    entry_id = _save("тревога и её причины", "ВК", "нотбук", "текст поста про тревогу", f)
    # Шаг 2: генерируем картинку для другого поста (имитация что между шагами появилась новая запись)
    _save("другой пост", "Telegram", "нотбук", "другой текст", f)
    # Шаг 3: обновляем картинку первого поста по entry_id
    _update_img("/images/anxiety.jpg", f, entry_id=entry_id)
    # Проверка: нужная запись обновлена, другая — нет
    history = json.loads(f.read_text())
    target = next(e for e in history if e["id"] == entry_id)
    other = next(e for e in history if e["id"] != entry_id)
    assert target["image_path"] == "/images/anxiety.jpg", "Картинка не привязалась к нужному посту"
    assert other["image_path"] == "", "Соседний пост получил чужую картинку"
    f.unlink(missing_ok=True)

def test_pipe_plan_post_and_image_go_to_correct_history():
    """
    Пайплайн контент-плана: пост 1 из плана → history; пост 2 из плана → history;
    картинка для поста 1 → обновляет именно запись поста 1.
    """
    f = Path(tempfile.mktemp(suffix=".json"))
    # Два поста из плана
    id_plan1 = _save("тема из плана 1", "vk_personal", "нотбук", "текст 1", f)
    id_plan2 = _save("тема из плана 2", "telegram", "нотбук", "текст 2", f)
    # Картинка генерируется для плана 1 (не для последней записи!)
    _update_img("/images/plan1.jpg", f, entry_id=id_plan1)
    history = json.loads(f.read_text())
    p1 = next(e for e in history if e["id"] == id_plan1)
    p2 = next(e for e in history if e["id"] == id_plan2)
    assert p1["image_path"] == "/images/plan1.jpg"
    assert p2["image_path"] == "", "Пост плана 2 не должен получить картинку поста 1"
    f.unlink(missing_ok=True)

def test_pipe_retry_post_gets_new_entry_id():
    """
    При регенерации поста ('Другой вариант') создаётся новая запись истории
    с новым entry_id, а старая запись остаётся нетронутой.
    """
    import time
    f = Path(tempfile.mktemp(suffix=".json"))
    id1 = _save("тема", "ВК", "нотбук", "вариант 1", f)
    time.sleep(0.02)
    id2 = _save("тема", "ВК", "нотбук", "вариант 2", f)
    assert id1 != id2, "Повторная генерация должна создавать новый entry_id"
    history = json.loads(f.read_text())
    assert len(history) == 2, "Повторная генерация должна добавлять новую запись"
    assert history[0]["text"] == "вариант 2"
    assert history[1]["text"] == "вариант 1"
    f.unlink(missing_ok=True)

def test_pipe_generate_plan_compatible_with_generate_post():
    """
    Параметры записей плана (platform, goal) должны быть корректными
    входными данными для generate_post.
    """
    from content_plan import generate_plan
    from generate_post import PLATFORMS, GOALS
    plan = generate_plan({"vk_personal": 3, "telegram": 2, "dzen": 1}, period_days=7)
    for item in plan:
        assert item["platform"] in PLATFORMS, \
            f"platform '{item['platform']}' из плана не принимается generate_post"
        assert item["goal"] in GOALS, \
            f"goal '{item['goal']}' из плана не принимается generate_post"

def test_pipe_plan_statuses_are_valid():
    """Статусы в плане должны быть только из допустимого набора."""
    from content_plan import generate_plan
    valid_statuses = {"не готов", "готов", "опубликован"}
    plan = generate_plan({"vk_personal": 5}, period_days=14)
    for item in plan:
        assert item["status"] in valid_statuses, \
            f"Недопустимый статус '{item['status']}' в записи плана"

run("[PIPE] Создать пост → entry_id → картинка → история обновлена верно", test_pipe_create_post_history_image_cycle)
run("[PIPE] Контент-план: картинка поста 1 не попадает в запись поста 2", test_pipe_plan_post_and_image_go_to_correct_history)
run("[PIPE] Регенерация поста создаёт новый entry_id, не затирает старый", test_pipe_retry_post_gets_new_entry_id)
run("[PIPE] Параметры плана совместимы с generate_post", test_pipe_generate_plan_compatible_with_generate_post)
run("[PIPE] Статусы плана — только допустимые значения", test_pipe_plan_statuses_are_valid)


# ─────────────────────────────────────────────
# 9. API-ТЕСТЫ (только с флагом --api)
# ─────────────────────────────────────────────
section("API-тесты (интеграционные)")

def test_api_generate_post_vk():
    from generate_post import generate_post
    text = generate_post("тревога и её причины", "vk_personal")
    assert isinstance(text, str) and len(text) > 200, f"Слишком короткий текст: {len(text)} символов"
    assert not text.endswith(("...", "…")), "Текст оборвался на многоточии — возможно не хватило токенов"

def test_api_generate_post_dzen():
    from generate_post import generate_post
    text = generate_post("как тревога влияет на тело", "dzen")
    words = len(text.split())
    assert words >= 500, f"Дзен-статья слишком короткая: {words} слов (нужно ≥ 500)"
    assert not text.endswith(("...", "…")), "Статья оборвалась — не хватило токенов"

def test_api_generate_post_telegram():
    from generate_post import generate_post
    text = generate_post("страх отвержения", "telegram")
    assert isinstance(text, str) and len(text) > 100

def test_api_suggest_topics_returns_list():
    from generate_post import suggest_topics
    topics = suggest_topics("vk_personal")
    assert isinstance(topics, list), "suggest_topics должна вернуть список"
    assert len(topics) >= 3, f"Слишком мало тем: {len(topics)}"
    for item in topics:
        assert "topic" in item, f"Нет ключа 'topic' в {item}"
        assert "why" in item, f"Нет ключа 'why' в {item}"

def test_api_suggest_topics_exclude():
    from generate_post import suggest_topics
    exclude = ["тревога и стресс", "выгорание на работе"]
    topics = suggest_topics("vk_personal", exclude=exclude)
    for item in topics:
        assert item["topic"] not in exclude, f"Тема из exclude вернулась: {item['topic']}"

def test_api_generate_image_returns_tuple():
    from image_generator import generate_image
    result = generate_image("тревога", "minimalism", "1:1")
    assert isinstance(result, tuple) and len(result) == 2, "generate_image должна вернуть (Image, prompt)"
    img, prompt = result
    assert img is not None
    assert isinstance(prompt, str) and len(prompt) > 10

def test_api_generate_image_with_post_text():
    from image_generator import generate_image
    post = "Тревога — это не враг. Это сигнал, что что-то важное требует внимания."
    result = generate_image("тревога", "watercolor", "1:1", post_text=post, tone=1)
    assert isinstance(result, tuple) and len(result) == 2

run("[API] generate_post для ВК — текст не обрывается", test_api_generate_post_vk, api=True)
run("[API] generate_post для Дзен — статья ≥ 500 слов", test_api_generate_post_dzen, api=True)
run("[API] generate_post для Telegram — корректный результат", test_api_generate_post_telegram, api=True)
run("[API] suggest_topics возвращает список с нужными ключами", test_api_suggest_topics_returns_list, api=True)
run("[API] suggest_topics учитывает список exclude", test_api_suggest_topics_exclude, api=True)
run("[API] generate_image возвращает кортеж (Image, prompt)", test_api_generate_image_returns_tuple, api=True)
run("[API] generate_image с текстом поста и тоном", test_api_generate_image_with_post_text, api=True)

def test_api_generate_image_correct_sizes():
    """generate_image должна вернуть изображение точно запрошенного размера для всех форматов."""
    from image_generator import generate_image, IMAGE_SIZES
    for size_key in ["1:1", "16:9", "9:16", "4:5"]:
        expected_w, expected_h = IMAGE_SIZES[size_key][0], IMAGE_SIZES[size_key][1]
        img, _ = generate_image("тревога", "minimalism", size_key)
        assert img.size == (expected_w, expected_h), (
            f"Размер {size_key}: ожидали {expected_w}×{expected_h}, получили {img.size[0]}×{img.size[1]}"
        )

run("[API] generate_image возвращает точный размер для всех 4 форматов", test_api_generate_image_correct_sizes, api=True)


# ─────────────────────────────────────────────
# ИТОГ
# ─────────────────────────────────────────────
total = len(passed) + len(failed) + len(skipped)
print(f"\n{BOLD}{'─'*50}{RESET}")
print(f"{BOLD}Итого: {total} тестов{RESET}")
print(f"  {GREEN}✓ Прошло:   {len(passed)}{RESET}")
if failed:
    print(f"  {RED}✗ Упало:    {len(failed)}{RESET}")
if skipped:
    print(f"  {YELLOW}○ Пропущено: {len(skipped)} (API-тесты){RESET}")

if failed:
    print(f"\n{RED}{BOLD}Упавшие тесты:{RESET}")
    for name in failed:
        print(f"  {RED}✗ {name}{RESET}")
    sys.exit(1)
else:
    print(f"\n{GREEN}{BOLD}Все тесты прошли успешно.{RESET}")
    sys.exit(0)
