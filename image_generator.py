import os
import re
import textwrap
from pathlib import Path
from io import BytesIO

import requests
import replicate
import anthropic
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()
os.environ["REPLICATE_API_TOKEN"] = os.getenv("REPLICATE_API_TOKEN", "")
_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

OUTPUT_DIR = Path(__file__).parent / "generated_images"
OUTPUT_DIR.mkdir(exist_ok=True)

STYLES = {
    "minimalism": {
        "label": "Минимализм",
        "prompt": "minimalist design, clean simple shapes, lots of white space, soft pastel colors, abstract concept visualization, no text, no people, elegant and calm, professional",
        "flux_prefix": "minimalist art style, clean white background, simple geometric shapes, soft pastel palette,",
        "flux_suffix": "minimalism, no clutter, elegant, calm",
    },
    "watercolor": {
        "label": "Акварель",
        "prompt": "watercolor painting style, soft blended warm colors, artistic brushstrokes, emotional and gentle, abstract mood illustration, no text, beautiful artistic quality",
        "flux_prefix": "watercolor painting, soft watercolor brushstrokes, blended colors, paper texture,",
        "flux_suffix": "watercolor art style, artistic, painterly",
    },
    "cinematic": {
        "label": "Кинематографический",
        "prompt": "cinematic film still, dramatic moody lighting, deep shadows and highlights, rich dark color palette, atmospheric fog or bokeh, anamorphic lens look, professional movie scene composition, emotional and intense, no text",
        "flux_prefix": "cinematic film still, dramatic moody lighting, deep shadows, dark rich palette, anamorphic lens,",
        "flux_suffix": "cinematic photography, movie scene, atmospheric",
    },
    "abstract": {
        "label": "Абстракция",
        "prompt": "abstract art, symbolic geometric shapes, metaphorical composition, bold thoughtful colors, conceptual depth, no text, gallery quality",
        "flux_prefix": "abstract art, symbolic geometric shapes, bold colors, conceptual illustration,",
        "flux_suffix": "abstract painting, gallery quality, no realistic elements",
    },
    "flat_illustration": {
        "label": "Плоская иллюстрация",
        "prompt": "flat vector illustration style, modern editorial design, clean shapes, contemporary magazine aesthetic, professional, no text",
        "flux_prefix": "flat design illustration, vector art style, clean shapes, modern editorial,",
        "flux_suffix": "flat illustration, 2D design, no gradients, no shadows",
    },
    "photorealism": {
        "label": "Фотореализм",
        "prompt": "ultra photorealistic photography, shot on Sony A7R V, 85mm f/1.4 lens, natural ambient light, shallow depth of field, lifelike skin texture, cinematic color grading, hyperrealistic details, professional portrait or scene photography, no illustration, no painting, no drawing",
        "flux_prefix": "ultra photorealistic photography, Sony A7R V camera, 85mm lens, shallow depth of field, natural light,",
        "flux_suffix": "hyperrealistic, professional photography, no illustration, no painting",
    },
}

OVERLAY_OPTIONS = {
    "title":    "Заголовок поста",
    "custom":   "Свой текст",
    "author":   "Имя / должность",
    "hashtags": "Хэштеги",
    "none":     "Без текста",
}

# Форматы: (ширина, высота, _, описание)
IMAGE_SIZES = {
    "1:1":   (1024, 1024,  "", "1:1 — квадрат (ВК, Telegram)"),
    "16:9":  (1344, 768,   "", "16:9 — горизонталь (Дзен, обложки)"),
    "9:16":  (768,  1344,  "", "9:16 — вертикаль (сторис)"),
    "4:5":   (896,  1120,  "", "4:5 — портрет (лента ВК)"),
}

# Рекомендуемый размер по площадке
PLATFORM_DEFAULT_SIZE = {
    "vk_personal": "4:5",
    "vk_group":    "1:1",
    "telegram":    "1:1",
    "dzen":        "16:9",
}


TONE_MOOD = {
    0: "serious, thoughtful, professional atmosphere",
    1: "calm, neutral, accessible atmosphere",
    2: "warm, light, slightly playful atmosphere",
    3: "humorous, ironic, whimsical, unexpected and funny atmosphere",
}


STYLE_VISUAL_RULES = {
    "minimalism":       "Use only simple geometric shapes and abstract forms. No people, no realistic objects. Pure symbolic abstraction.",
    "watercolor":       "Painterly, soft, slightly impressionistic. Realistic subjects rendered in loose artistic brushwork. No cartoon elements.",
    "cinematic":        "Realistic photographic scene with dramatic lighting. Real people or objects, no cartoons, no illustrations.",
    "abstract":         "Fully abstract — shapes, colors, forms, no recognizable objects or people. Pure visual metaphor.",
    "flat_illustration": "Flat 2D vector-style illustration. Simple stylized characters and objects, clean lines, no gradients, no realism.",
    "photorealism":     "Strictly photorealistic. Real-world scene as if photographed. No cartoons, no illustrations, no fantasy elements, no text on objects.",
}

# Дефолтный уровень реалистичности (0=абстракция, 10=фото) для каждого стиля
STYLE_DEFAULT_REALISM = {
    "abstract":          0,
    "minimalism":        1,
    "flat_illustration": 3,
    "watercolor":        5,
    "cinematic":         8,
    "photorealism":      10,
}


def _realism_instruction(level: int) -> str:
    """Возвращает инструкцию для Claude в зависимости от уровня реалистичности."""
    if level <= 1:
        return (
            "REALISM LEVEL: 0 — pure abstraction. Depict nothing literally. "
            "Use only shapes, colors, and composition to convey emotion and meaning. "
            "No recognizable objects, people, or places."
        )
    elif level <= 3:
        return (
            "REALISM LEVEL: low — symbolic and metaphorical. "
            "Subjects may be suggested but should not be realistically rendered. "
            "Prioritize visual metaphor and stylized representation over literal depiction."
        )
    elif level <= 6:
        return (
            "REALISM LEVEL: medium — artistic balance. "
            "Subjects are recognizable and tied directly to the post content, "
            "but rendered with artistic interpretation, not photographic precision."
        )
    elif level <= 8:
        return (
            "REALISM LEVEL: high — close to reality. "
            "Depict subjects clearly and recognizably, directly tied to the post's specific situation. "
            "Minimize metaphor — show what the post is actually about. "
            "CRITICAL: if the user's clarification contains fantastical elements "
            "(e.g. 'walking cockroaches on a leash') — render them as if they were real: "
            "an actual person, actual cockroaches, actual leashes — believable and naturalistic."
        )
    else:
        return (
            "REALISM LEVEL: maximum — photorealistic. "
            "Every element must look as if it could be photographed in real life. "
            "Show the exact scene the post describes — no metaphors, no symbols, no abstractions. "
            "CRITICAL: fantastical elements from user clarifications must be rendered with "
            "full photorealistic detail as if they physically exist — hyper-detailed and completely believable. "
            "The image should feel like a documentary photograph of the post's subject matter."
        )


def _extract_visual_concept(post_text: str, tone: int = 0, style_key: str = "minimalism", user_comment: str = "", realism: int = 5) -> str:
    """Claude Sonnet читает пост и создаёт визуальный концепт строго в рамках выбранного стиля."""
    mood = TONE_MOOD.get(tone, TONE_MOOD[0])
    style_rule = STYLE_VISUAL_RULES.get(style_key, "")
    style_label = STYLES[style_key]["label"]
    realism_rule = _realism_instruction(realism)

    import time as _time
    kwargs = dict(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=(
            "You are an expert art director creating image generation prompts. "
            "Your prompts are specific, vivid, and directly tied to the post content. "
            "You strictly follow the visual style constraints given to you — never mix styles. "
            "You strictly follow the realism level instruction — it overrides style defaults when they conflict. "
            "You never describe text, signs, labels, or written words on objects in the image."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Post text (Russian):\n{post_text[:8000]}\n\n"
                f"---\n"
                f"STEP 1 — Understand the post:\n"
                f"- What is the specific psychological concept, mechanism, or situation this post is about?\n"
                f"- What exact metaphor or analogy does the author use in the post text (if any)?\n"
                f"- What is the emotional core — what should the reader feel?\n\n"
                f"STEP 2 — Create the visual prompt:\n"
                f"Use the answer from Step 1 as the foundation. "
                f"If the author uses a specific metaphor in the post — visualize THAT metaphor, not a new one. "
                f"Apply the mood ({mood}) as a modifier to the scene, not as a replacement for the post's meaning. "
                f"The final image must be so specific that a reader of this post would immediately say: 'yes, this is exactly what the post is about.'\n\n"
                f"Visual style: {style_label}. Style constraints: {style_rule}\n\n"
                f"Realism instruction (MANDATORY — follow precisely): {realism_rule}\n\n"
                + (f"User clarifications (follow strictly, they override defaults):\n{user_comment}\n\n" if user_comment.strip() else "")
                + f"Output format: first write 'CONCEPT: [1 sentence — what the post is about]', "
                f"then write 'PROMPT: [4-5 sentences — the detailed visual description in English]'. "
                f"No text, signs, or labels on any object in the scene."
            )
        }],
    )
    for attempt in range(3):
        try:
            response = _claude.messages.create(**kwargs)
            break
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                if attempt < 2:
                    _time.sleep(20 * (attempt + 1))
                    continue
            raise e

    text = response.content[0].text.strip()
    # Извлекаем только часть PROMPT:
    if "PROMPT:" in text:
        return text.split("PROMPT:")[-1].strip()
    return text


def generate_image(topic: str, style_key: str, size_key: str = "1:1", post_text: str = "", tone: int = 0, user_comment: str = "", realism: int = 5) -> tuple:
    """Генерирует картинку через Flux 1.1 Pro."""
    style = STYLES[style_key]
    w, h, _, _ = IMAGE_SIZES.get(size_key, IMAGE_SIZES["1:1"])
    no_text = "no letters, no words, no text, no watermarks, no signs anywhere in the image"
    people_rule = "if any people appear: light-skinned European appearance only"
    mood = TONE_MOOD.get(tone, TONE_MOOD[0])

    # Flux-суффикс реалистичности
    if realism <= 2:
        realism_flux = "purely abstract, no recognizable objects"
    elif realism <= 5:
        realism_flux = "stylized, artistic interpretation"
    elif realism <= 7:
        realism_flux = "realistic and naturalistic depiction"
    else:
        realism_flux = "photorealistic, hyper-detailed, lifelike"

    if post_text.strip():
        concept = _extract_visual_concept(post_text, tone, style_key, user_comment, realism)
        prompt = (
            f"{style['flux_prefix']} "
            f"{concept} "
            f"{style['flux_suffix']}, {realism_flux}, {people_rule}, {no_text}."
        )
    else:
        comment_part = f" {user_comment}." if user_comment.strip() else ""
        prompt = (
            f"{style['flux_prefix']} "
            f"Psychology and psychotherapy concept about: {topic}, {mood}.{comment_part} "
            f"{style['flux_suffix']}, {realism_flux}, {people_rule}, {no_text}."
        )

    import time as _time
    for attempt in range(4):
        try:
            output = replicate.run(
                "black-forest-labs/flux-1.1-pro",
                input={
                    "prompt": prompt,
                    "width": w,
                    "height": h,
                    "output_format": "jpg",
                    "output_quality": 92,
                    "safety_tolerance": 4,
                }
            )

            if hasattr(output, 'url'):
                img_data = requests.get(output.url, timeout=120).content
            elif isinstance(output, str):
                img_data = requests.get(output, timeout=120).content
            else:
                img_data = output.read()

            img = Image.open(BytesIO(img_data)).convert("RGBA")
            if img.size != (w, h):
                from PIL import ImageOps
                img = ImageOps.fit(img, (w, h), Image.LANCZOS)
            return img, prompt

        except Exception as e:
            is_rate_limit = "429" in str(e) or "throttled" in str(e).lower()
            if is_rate_limit and attempt < 3:
                _time.sleep(15 * (attempt + 1))  # 15s, 30s, 45s
                continue
            if not is_rate_limit and attempt == 0:
                continue
            raise e


def _get_font(size: int, bold: bool = False):
    """Загружает шрифт с поддержкой кириллицы (macOS и Linux)."""
    font_paths = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Arial.ttf",
        # Linux (Ubuntu/Debian — Streamlit Cloud)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in font_paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def apply_overlay(
    image: Image.Image,
    overlay_type: str,
    overlay_text: str = "",
    position: str = "bottom",
) -> Image.Image:
    """Накладывает текст поверх картинки — центрирование, гармоничное расположение."""
    if overlay_type == "none" or not overlay_text.strip():
        return image.convert("RGB")

    img = image.copy().convert("RGBA")
    w, h = img.size

    # Параметры шрифта
    is_title = overlay_type == "title"
    font_size = int(w * 0.045) if is_title else int(w * 0.032)
    font_size = max(font_size, 24)
    font = _get_font(font_size, bold=True)

    # Перенос текста с учётом ширины
    margin = int(w * 0.08)
    max_chars = int((w - margin * 2) / (font_size * 0.52))
    lines = textwrap.wrap(overlay_text, width=max_chars)[:4]

    line_h = int(font_size * 1.35)
    total_text_h = len(lines) * line_h
    pad_v = int(h * 0.04)

    # Высота подложки
    bar_h = total_text_h + pad_v * 2

    # Позиция подложки
    if position == "bottom":
        bar_y = h - bar_h
        bar_y2 = h
    elif position == "top":
        bar_y = 0
        bar_y2 = bar_h
    else:  # center
        bar_y = (h - bar_h) // 2
        bar_y2 = bar_y + bar_h

    # Рисуем градиентную подложку
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if position in ("bottom", "top"):
        # Градиент: постепенное затемнение
        steps = bar_h
        for step in range(steps):
            alpha = int(180 * (step / steps)) if position == "bottom" else int(180 * (1 - step / steps))
            y = bar_y + step if position == "bottom" else bar_y + step
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    else:
        draw.rectangle([(0, bar_y), (w, bar_y2)], fill=(0, 0, 0, 150))

    # Рисуем текст — по центру горизонтально
    draw_text = ImageDraw.Draw(overlay)
    text_y = bar_y + pad_v

    for line in lines:
        # Вычисляем ширину строки для центрирования
        try:
            bbox = draw_text.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
        except Exception:
            text_w = len(line) * font_size * 0.55
        text_x = (w - text_w) // 2

        # Тень для читаемости
        draw_text.text((text_x + 2, text_y + 2), line, font=font, fill=(0, 0, 0, 180))
        # Основной текст
        draw_text.text((text_x, text_y), line, font=font, fill=(255, 255, 255, 245))
        text_y += line_h

    combined = Image.alpha_composite(img, overlay)
    return combined.convert("RGB")


def save_image(image: Image.Image, topic: str) -> Path:
    """Сохраняет картинку и возвращает путь."""
    safe_name = re.sub(r"[^\w\s-]", "", topic)[:40].strip().replace(" ", "_")
    from datetime import datetime
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}.jpg"
    path = OUTPUT_DIR / filename
    image.save(path, "JPEG", quality=92)
    return path
