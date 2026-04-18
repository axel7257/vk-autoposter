import streamlit as st
import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
os.environ["PATH"] = f"{os.path.expanduser('~/bin')}:{os.environ.get('PATH', '')}"

# Sync Streamlit secrets → os.environ so all modules can use os.getenv()
for _k in ["ANTHROPIC_API_KEY", "REPLICATE_API_TOKEN", "SUPABASE_URL", "SUPABASE_KEY"]:
    if _k not in os.environ:
        try:
            if _k in st.secrets:
                os.environ[_k] = st.secrets[_k]
        except Exception:
            pass

from generate_post import generate_post, suggest_topics, PLATFORMS, GOALS, TONE_INSTRUCTIONS
from content_plan import generate_plan, generate_topics_for_plan, GOAL_LABELS, PLATFORM_LABELS
from image_generator import generate_image, apply_overlay, STYLES, OVERLAY_OPTIONS, IMAGE_SIZES, PLATFORM_DEFAULT_SIZE, STYLE_DEFAULT_REALISM
from storage import (load_history, save_to_history, update_history_image, clear_history,
                     load_plan_data, save_plan_data, save_and_upload_image, image_exists, load_image_bytes)

st.set_page_config(
    page_title="Контент-студия",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

PLATFORM_INFO = {
    "vk_personal": {"label": "ВК — личная страница", "icon": "👤", "note": "Личный экспертный голос · 400–700 слов"},
    "vk_group":    {"label": "ВК — группа",          "icon": "👥", "note": "Структурированно · 500–900 слов"},
    "telegram":    {"label": "Telegram",              "icon": "✈️", "note": "Ёмко и плотно · 200–400 слов"},
    "dzen":        {"label": "Яндекс Дзен",           "icon": "📰", "note": "Статья с заголовками · 800–1200 слов"},
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* { font-family: 'Inter', sans-serif !important; }

/* Основной фон */
.stApp { background: #f8f8f6; }
.main .block-container {
    padding: 2.5rem 2rem 2rem 2rem;
    max-width: 900px;
}

/* Сайдбар */
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e8e8e4;
}
section[data-testid="stSidebar"] * {
    color: #1a1a1a !important;
}

/* Заголовки */
h1, h2, h3 { color: #1a1a1a !important; letter-spacing: -0.3px; }
h1 { font-size: 1.5rem !important; font-weight: 700 !important; }
h2 { font-size: 1.15rem !important; font-weight: 600 !important; }

/* Весь обычный текст */
p, label { color: #1a1a1a; }
div:not([class*="arrow"]) { color: #1a1a1a; }

/* Скрываем внутренние служебные элементы Streamlit (стрелка экспандера) */
[class*="_arrow_"] { font-size: 0 !important; color: transparent !important; }
details > summary > span:first-child { font-size: 0 !important; color: transparent !important; width: 20px !important; display: inline-block !important; }

/* Поле ввода */
div[data-testid="stTextInput"] input {
    background: #ffffff !important;
    border: 1.5px solid #d0d0cc !important;
    border-radius: 10px !important;
    color: #1a1a1a !important;
    font-size: 1rem !important;
    padding: 0.7rem 1rem !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #6c63ff !important;
    box-shadow: 0 0 0 3px rgba(108,99,255,0.1) !important;
}
div[data-testid="stTextInput"] input::placeholder { color: #999 !important; }

/* Textarea */
div[data-testid="stTextArea"] textarea {
    background: #ffffff !important;
    border: 1.5px solid #d0d0cc !important;
    border-radius: 10px !important;
    color: #1a1a1a !important;
    font-size: 0.95rem !important;
    line-height: 1.8 !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border-color: #6c63ff !important;
}

/* Селект */
div[data-testid="stSelectbox"] > div > div {
    background: #ffffff !important;
    border: 1.5px solid #d0d0cc !important;
    border-radius: 10px !important;
    color: #1a1a1a !important;
}

/* Radio */
div[data-testid="stRadio"] label { color: #1a1a1a !important; font-size: 0.92rem !important; }
div[data-testid="stRadio"] { gap: 4px; }

/* Кнопки */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1rem !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    width: 100% !important;
    transition: all 0.15s ease !important;
}
button[kind="primary"] {
    background: #6c63ff !important;
    border: none !important;
    color: #ffffff !important;
}
button[kind="primary"]:hover {
    background: #5a52e0 !important;
    box-shadow: 0 4px 12px rgba(108,99,255,0.3) !important;
    transform: translateY(-1px) !important;
}
button[kind="secondary"] {
    background: #ffffff !important;
    border: 1.5px solid #d0d0cc !important;
    color: #1a1a1a !important;
}
button[kind="secondary"]:hover {
    border-color: #6c63ff !important;
    color: #6c63ff !important;
}

/* Вкладки */
div[data-baseweb="tab-list"] {
    background: #efefec !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
}
div[data-baseweb="tab"] {
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #666 !important;
    padding: 6px 18px !important;
}
div[aria-selected="true"] {
    background: #ffffff !important;
    color: #1a1a1a !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
}

/* Expander */
div[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e8e8e4 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}
div[data-testid="stExpander"] summary {
    color: #1a1a1a !important;
    font-weight: 500 !important;
    padding: 1rem 1.2rem !important;
}

/* Download кнопка */
div[data-testid="stDownloadButton"] button {
    background: #ffffff !important;
    border: 1.5px solid #d0d0cc !important;
    color: #1a1a1a !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    white-space: nowrap !important;
}

/* Info/Alert */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
    background: #f0eeff !important;
    border-color: #c4beff !important;
    color: #3a3060 !important;
}

/* Code block */
div[data-testid="stCode"] {
    border-radius: 10px !important;
    background: #f3f3f0 !important;
}
div[data-testid="stCode"] pre { color: #1a1a1a !important; }

/* Разделитель */
hr { border-color: #e8e8e4 !important; }

/* Caption */
div[data-testid="stCaptionContainer"] p { color: #888 !important; font-size: 0.8rem !important; }

/* Spinner */
div[data-testid="stSpinner"] p { color: #666 !important; }

/* Скрыть футер Streamlit */
footer { display: none !important; }
#MainMenu { display: none !important; }
header { display: none !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_notebooks():
    try:
        result = subprocess.run(
            ["notebooklm", "list", "--json"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": f"{os.path.expanduser('~/bin')}:{os.environ.get('PATH', '')}"}
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            notebooks = {"— без материалов —": None}
            for nb in data.get("notebooks", []):
                notebooks[nb["title"]] = nb["id"]
            return notebooks
    except Exception:
        pass
    return {"— без материалов —": None}



# ========================
# САЙДБАР
# ========================
with st.sidebar:
    st.markdown("## ✦ Контент-студия")
    st.markdown("Психотерапия и консультирование")
    st.divider()

    st.markdown("**Площадка**")
    platform_key = st.radio(
        "",
        options=list(PLATFORM_INFO.keys()),
        format_func=lambda k: f"{PLATFORM_INFO[k]['icon']}  {PLATFORM_INFO[k]['label']}",
        label_visibility="collapsed"
    )
    st.caption(PLATFORM_INFO[platform_key]["note"])

    st.divider()

    st.markdown("**База знаний (NotebookLM)**")
    with st.spinner("Загружаю..."):
        notebooks = load_notebooks()

    nb_name = st.selectbox("", options=list(notebooks.keys()), label_visibility="collapsed")
    notebook_id = notebooks[nb_name]

    if notebook_id:
        st.caption("⏱ Запрос займёт около 2 минут")

    st.divider()

    st.markdown("**Цель поста**")
    goal_options = {"— не задана —": None} | {label: key for key, (label, _) in GOALS.items()}
    goal_label = st.selectbox("", options=list(goal_options.keys()), label_visibility="collapsed")
    goal_key = goal_options[goal_label]

    if goal_key:
        _, goal_hint = GOALS[goal_key]
        st.caption(goal_hint)

    st.divider()

    st.markdown("**Тон поста**")
    tone = st.select_slider(
        "",
        options=[0, 1, 2, 3],
        format_func=lambda x: ["Серьёзный", "Нейтральный", "Лёгкий", "Юмористический"][x],
        value=0,
        label_visibility="collapsed"
    )

    st.divider()
    st.caption("v0.3")


# ========================
# ОСНОВНАЯ ЧАСТЬ
# ========================
tab_create, tab_plan, tab_history = st.tabs(["✦  Создать пост", "📅  Контент-план", "🕐  История"])

with tab_create:
    st.markdown("## Новый пост")

    # Блок предложения тем
    sc1, sc2, _ = st.columns([1, 1, 2])
    with sc1:
        suggest_btn = st.button("💡 Предложить темы", key="suggest_topics_btn")
    with sc2:
        more_btn = st.button("🔄 Другие темы", key="suggest_more_btn")

    if suggest_btn:
        with st.spinner("Ищу актуальные темы..."):
            topics = suggest_topics(platform_key)
            if topics:
                st.session_state["suggested_topics"] = topics
                st.session_state["shown_topics"] = [t["topic"] for t in topics]
            else:
                st.warning("Не удалось найти темы, попробуй ещё раз.")

    if more_btn:
        with st.spinner("Ищу другие темы..."):
            exclude = st.session_state.get("shown_topics", [])
            topics = suggest_topics(platform_key, exclude=exclude)
            if topics:
                st.session_state["suggested_topics"] = topics
                st.session_state["shown_topics"] = exclude + [t["topic"] for t in topics]
            else:
                st.warning("Не удалось найти темы, попробуй ещё раз.")

    if st.session_state.get("suggested_topics"):
        st.markdown("**Актуальные темы — выбери или введи свою:**")
        for item in st.session_state["suggested_topics"]:
            col_btn, col_why = st.columns([2, 3])
            with col_btn:
                if st.button(f"📌 {item['topic']}", key=f"st_{item['topic'][:30]}"):
                    st.session_state["topic_input_val"] = item["topic"]
                    st.rerun()
            with col_why:
                st.caption(item.get("why", ""))
        st.markdown("")

    topic = st.text_input(
        "Тема",
        placeholder="Например: почему мы боимся просить о помощи",
        key="topic_input_val",
    )

    st.markdown("")
    generate_btn = st.button("Сгенерировать →", type="primary", disabled=not topic.strip())

    if generate_btn:
        msg = "Запрашиваю материал из NotebookLM..." if notebook_id else "Генерирую пост..."
        with st.spinner(msg):
            try:
                post = generate_post(topic.strip(), platform_key, notebook_id=notebook_id, goal=goal_key, tone=tone)
                st.session_state["last_post"] = post
                st.session_state["last_topic"] = topic.strip()
                st.session_state["last_platform"] = platform_key
                st.session_state["last_nb_name"] = nb_name
                st.session_state["last_goal"] = goal_label
                # Обновляем textarea и сбрасываем старую картинку
                st.session_state["create_post_textarea"] = post
                st.session_state.pop("last_image_path", None)
                st.session_state.pop("last_flux_prompt", None)
                entry_id = save_to_history(topic.strip(), platform_key, PLATFORM_INFO[platform_key]["label"], PLATFORM_INFO[platform_key]["icon"], nb_name, post)
                st.session_state["last_history_id"] = entry_id
            except Exception as e:
                st.error(f"Ошибка: {e}")

    if "last_post" in st.session_state:
        st.divider()

        pi = PLATFORM_INFO[st.session_state["last_platform"]]
        goal_display = st.session_state.get("last_goal", "—")
        st.caption(
            f"{pi['icon']} {pi['label']}  ·  "
            f"🎯 {goal_display}  ·  "
            f"📚 {st.session_state['last_nb_name']}  ·  "
            f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        edited = st.text_area(
            "Редактируй прямо здесь",
            value=st.session_state["last_post"],
            height=500,
            key="create_post_textarea",
            label_visibility="collapsed"
        )

        c1, c2, c3 = st.columns([2, 2, 3])
        with c1:
            st.download_button(
                "📥 Скачать",
                data=edited,
                file_name=f"post_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
        with c2:
            if st.button("🔄 Другой вариант", key="retry"):
                with st.spinner("Генерирую..."):
                    try:
                        post = generate_post(
                            st.session_state["last_topic"],
                            st.session_state["last_platform"],
                            notebook_id=notebook_id,
                            goal=goal_key,
                            tone=tone
                        )
                        st.session_state["last_post"] = post
                        st.session_state["create_post_textarea"] = post
                        st.session_state.pop("last_image_path", None)
                        st.session_state.pop("last_flux_prompt", None)
                        lp = st.session_state["last_platform"]
                        entry_id = save_to_history(
                            st.session_state["last_topic"],
                            lp,
                            PLATFORM_INFO[lp]["label"],
                            PLATFORM_INFO[lp]["icon"],
                            st.session_state["last_nb_name"],
                            post
                        )
                        st.session_state["last_history_id"] = entry_id
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

        st.markdown("**Скопировать:**")
        st.code(edited, language=None)

        st.divider()
        st.markdown("## Картинка к посту")

        col_img1, col_img2, col_img3, col_img4 = st.columns([1, 1, 1, 1])
        with col_img1:
            style_key = st.selectbox(
                "Стиль",
                options=list(STYLES.keys()),
                format_func=lambda k: STYLES[k]["label"],
                key="create_style_key"
            )
        with col_img2:
            default_size = PLATFORM_DEFAULT_SIZE.get(platform_key, "1:1")
            if st.session_state.get("_create_last_platform") != platform_key:
                st.session_state["_create_last_platform"] = platform_key
                st.session_state["create_size_key"] = default_size
            size_key = st.selectbox(
                "Размер",
                options=list(IMAGE_SIZES.keys()),
                index=list(IMAGE_SIZES.keys()).index(default_size),
                format_func=lambda k: IMAGE_SIZES[k][3],
                key="create_size_key"
            )
        with col_img3:
            overlay_type = st.selectbox(
                "Текст на картинке",
                options=list(OVERLAY_OPTIONS.keys()),
                format_func=lambda k: OVERLAY_OPTIONS[k],
                key="create_overlay_type"
            )
        with col_img4:
            overlay_position = st.selectbox(
                "Расположение текста",
                options=["bottom", "top", "center"],
                format_func=lambda k: {"bottom": "Снизу", "top": "Сверху", "center": "По центру"}[k],
                key="create_overlay_pos"
            )

        # Бегунок реалистичности — автодефолт по стилю, сбрасывается при смене стиля
        if st.session_state.get("_create_last_style") != style_key:
            st.session_state["_create_last_style"] = style_key
            st.session_state["create_realism"] = STYLE_DEFAULT_REALISM.get(style_key, 5)
        realism = st.slider(
            "Реалистичность",
            min_value=0, max_value=10,
            key="create_realism",
            help="0 — абстракция и метафора · 10 — фото реальность. Фантазийные элементы из уточнений рисуются реалистично."
        )
        st.caption(
            ["Абстракция", "Абстракция", "Метафора", "Метафора", "Символизм",
             "Баланс", "Близко к реальности", "Близко к реальности",
             "Реализм", "Фотореализм", "Фотореализм"][realism]
        )

        overlay_text = ""
        if overlay_type == "title":
            first_line = edited.strip().split("\n")[0]
            overlay_text = first_line
            st.caption(f"Заголовок: {first_line}")
        elif overlay_type == "custom":
            overlay_text = st.text_input("Текст для наложения", placeholder="Введи текст")
        elif overlay_type == "author":
            overlay_text = st.text_input("Имя / должность", placeholder="Например: Антон · Психотерапевт")
        elif overlay_type == "hashtags":
            last_line = edited.strip().split("\n")[-1]
            overlay_text = last_line
            st.caption(f"Хэштеги: {last_line}")

        img_comment = st.text_input(
            "Уточнения для картинки",
            placeholder="Например: покажи одинокую фигуру у окна, тёплые тона, без людей, акцент на руках...",
            key="create_img_comment"
        )

        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            generate_img_btn = st.button("🎨 Сгенерировать картинку", type="primary")
        with btn_col2:
            regen_img_btn = st.button("🔄 Другой вариант картинки",
                                      disabled="last_image_path" not in st.session_state)

        if generate_img_btn or regen_img_btn:
            with st.spinner("Генерирую картинку... (~20 секунд)"):
                try:
                    img, flux_prompt = generate_image(st.session_state["last_topic"], style_key, size_key, post_text=edited, tone=tone, user_comment=img_comment, realism=realism)
                    img = apply_overlay(img, overlay_type, overlay_text, position=overlay_position)
                    img_path = save_and_upload_image(img, st.session_state["last_topic"])
                    st.session_state["last_image_path"] = img_path
                    st.session_state["last_flux_prompt"] = flux_prompt
                    update_history_image(str(img_path), st.session_state.get("last_history_id"))
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")

        if "last_image_path" in st.session_state and image_exists(st.session_state["last_image_path"]):
            try:
                st.image(st.session_state["last_image_path"], use_container_width=True)
                st.download_button(
                    "📥 Скачать картинку",
                    data=load_image_bytes(st.session_state["last_image_path"]),
                    file_name="post_image.jpg",
                    mime="image/jpeg"
                )
                if "last_flux_prompt" in st.session_state:
                    with st.expander("🔍 Промпт для картинки"):
                        st.text(st.session_state["last_flux_prompt"])
            except Exception:
                pass


with tab_plan:
    st.markdown("## Контент-план")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("**Площадки и частота (постов в неделю)**")
        freq_vk_personal = st.slider("👤 ВК — личная страница", 0, 7, 3)
        freq_vk_group    = st.slider("👥 ВК — группа",          0, 7, 4)
        freq_telegram    = st.slider("✈️ Telegram",              0, 7, 3)
        freq_dzen        = st.slider("📰 Яндекс Дзен",           0, 7, 0)

    with col_right:
        st.markdown("**Параметры плана**")
        period = st.radio("Период", ["1 неделя", "1 месяц"], horizontal=True)
        period_days = 7 if period == "1 неделя" else 30

        start_option = st.radio("Начало", ["С завтрашнего дня", "Выбрать дату"], horizontal=True)
        if start_option == "Выбрать дату":
            start_date_input = st.date_input("Дата начала")
            start_date = datetime.combine(start_date_input, datetime.min.time())
        else:
            start_date = None

        plan_tone = st.select_slider(
            "Тон постов",
            options=[0, 1, 2, 3],
            format_func=lambda x: ["Серьёзный", "Нейтральный", "Лёгкий", "Юмористический"][x],
            value=0,
            key="plan_tone_slider"
        )

        PRESET_THEMES = [
            "— без тематического блока —",
            "Тревога и тревожные расстройства",
            "Травма и ПТСР",
            "Отношения и привязанность",
            "Самооценка и самопринятие",
            "Депрессия и апатия",
            "Страхи и фобии",
            "Перфекционизм и синдром самозванца",
            "Границы в отношениях",
            "Эмоциональное выгорание",
            "Детские травмы и их влияние на взрослую жизнь",
            "Бизнес-психология / психология бизнеса",
            "✏️  Своя тема...",
        ]

        st.markdown("**База знаний (NotebookLM)**")
        plan_nb_name = st.selectbox("", options=list(notebooks.keys()),
                                    label_visibility="collapsed", key="plan_nb")
        plan_nb_id = notebooks[plan_nb_name]
        if plan_nb_id:
            st.caption("⏱ Каждый пост будет запрашивать ~2 мин")

        st.markdown("**Тематический блок**")
        theme_choice = st.selectbox("", options=PRESET_THEMES, label_visibility="collapsed")

        if theme_choice == "✏️  Своя тема...":
            theme = st.text_input("", placeholder="Опиши тему своими словами — например: работа с горем и потерей", label_visibility="collapsed")
        elif theme_choice == "— без тематического блока —":
            theme = ""
        else:
            theme = theme_choice

    st.markdown("")
    if st.button("📅 Сгенерировать план", type="primary"):
        platforms = {}
        if freq_vk_personal > 0: platforms["vk_personal"] = freq_vk_personal
        if freq_vk_group > 0:    platforms["vk_group"]    = freq_vk_group
        if freq_telegram > 0:    platforms["telegram"]    = freq_telegram
        if freq_dzen > 0:        platforms["dzen"]        = freq_dzen

        if not platforms:
            st.warning("Выбери хотя бы одну площадку с частотой больше 0.")
        else:
            plan = generate_plan(platforms, period_days, start_date=start_date, theme=theme)
            if theme:
                with st.spinner(f"Подбираю темы постов по блоку «{theme}»..."):
                    plan = generate_topics_for_plan(plan, theme)
            save_plan_data(plan)
            st.session_state["content_plan"] = plan
            st.session_state["plan_version"] = st.session_state.get("plan_version", 0) + 1
            topics_set = sum(1 for p in plan if p.get("topic"))
            st.success(f"План готов — {len(plan)} постов, тем подобрано: {topics_set}")

    plan = st.session_state.get("content_plan") or load_plan_data()

    if plan:
        st.divider()
        st.markdown(f"**Всего постов: {len(plan)}**")

        pv = st.session_state.get("plan_version", 0)
        for i, item in enumerate(plan):
            topic_preview = f"  ·  {item['topic']}" if item.get("topic") else "  ·  тема не задана"
            status = item.get("status", "не готов")
            status_icon = {"не готов": "○", "готов": "✓", "опубликован": "✦"}.get(status, "○")
            label = f"{status_icon}  {item['date']} {item['time']}  ·  {item['platform_label']}  ·  {item['goal_label']}{topic_preview}"

            with st.expander(label):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    new_topic = st.text_input("Тема поста", value=item.get("topic", ""), key=f"plan_topic_{i}_v{pv}",
                                              placeholder="Введи тему или оставь пустым")
                with c2:
                    new_goal = st.selectbox("Цель поста", options=list(GOAL_LABELS.keys()),
                                            format_func=lambda k: GOAL_LABELS[k],
                                            index=list(GOAL_LABELS.keys()).index(item["goal"]) if item["goal"] in GOAL_LABELS else 0,
                                            key=f"plan_goal_{i}_v{pv}")
                with c3:
                    status_options = ["не готов", "готов", "опубликован"]
                    current_status = item.get("status", "не готов")
                    selected_status = st.selectbox(
                        "Статус",
                        options=status_options,
                        index=status_options.index(current_status),
                        key=f"plan_status_{i}_v{pv}"
                    )
                    if selected_status != current_status:
                        plan[i]["status"] = selected_status
                        save_plan_data(plan)
                        st.session_state["content_plan"] = plan
                        st.rerun()

                if plan_nb_id:
                    st.caption(f"База знаний: {plan_nb_name}")
                if item.get("theme") and not new_topic.strip():
                    st.caption(f"Тема блока: {item['theme']} — будет использована как контекст")

                post_tone = st.select_slider(
                    "Тон",
                    options=[0, 1, 2, 3],
                    format_func=lambda x: ["Серьёзный", "Нейтральный", "Лёгкий", "Юмористический"][x],
                    value=plan_tone,
                    key=f"plan_post_tone_{i}_v{pv}"
                )

                pbg, pbr = st.columns([1, 1])
                with pbg:
                    gen_post_btn = st.button("✦ Сгенерировать пост", key=f"plan_gen_{i}_v{pv}", type="primary")
                with pbr:
                    regen_post_btn = st.button("🔄 Другой вариант текста", key=f"plan_regen_{i}_v{pv}",
                                               disabled=not item.get("post_text"))

                if gen_post_btn or regen_post_btn:
                    topic_to_use = new_topic.strip() or item.get("theme") or "психотерапия"
                    nb_id = plan_nb_id
                    with st.spinner("Генерирую..."):
                        try:
                            post_text = generate_post(topic_to_use, item["platform"], notebook_id=nb_id, goal=new_goal, tone=post_tone)
                            plan[i]["post_text"] = post_text
                            plan[i]["topic"] = topic_to_use
                            plan[i]["goal"] = new_goal
                            plan[i]["status"] = "готов"
                            save_plan_data(plan)
                            st.session_state["content_plan"] = plan
                            entry_id = save_to_history(topic_to_use, item["platform"], item["platform_label"], PLATFORM_INFO.get(item["platform"], {}).get("icon", "📝"), plan_nb_name if plan_nb_id else "— без материалов —", post_text)
                            st.session_state[f"plan_history_id_{i}"] = entry_id
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка: {e}")

                if item.get("post_text"):
                    edited_plan = st.text_area("Текст поста", value=item["post_text"], height=350, key=f"plan_text_{i}_v{pv}")
                    st.download_button("📥 Скачать", data=edited_plan,
                                       file_name=f"plan_{item['date'].replace('.','_')}_{item['platform']}.txt",
                                       mime="text/plain", key=f"plan_dl_{i}_v{pv}")
                    st.code(edited_plan, language=None)

                    st.markdown("**Картинка к посту**")
                    ci1, ci2, ci3, ci4 = st.columns([1, 1, 1, 1])
                    with ci1:
                        plan_style = st.selectbox("Стиль", options=list(STYLES.keys()),
                                                  format_func=lambda k: STYLES[k]["label"], key=f"plan_style_{i}_v{pv}")
                    with ci2:
                        plan_default_size = PLATFORM_DEFAULT_SIZE.get(item["platform"], "1:1")
                        plan_size = st.selectbox("Размер", options=list(IMAGE_SIZES.keys()),
                                                 index=list(IMAGE_SIZES.keys()).index(plan_default_size),
                                                 format_func=lambda k: IMAGE_SIZES[k][3], key=f"plan_size_{i}_v{pv}")
                    with ci3:
                        plan_overlay = st.selectbox("Текст", options=list(OVERLAY_OPTIONS.keys()),
                                                    format_func=lambda k: OVERLAY_OPTIONS[k], key=f"plan_overlay_{i}_v{pv}")
                    with ci4:
                        plan_position = st.selectbox("Расположение",
                                                     options=["bottom", "top", "center"],
                                                     format_func=lambda k: {"bottom": "Снизу", "top": "Сверху", "center": "По центру"}[k],
                                                     key=f"plan_pos_{i}_v{pv}")

                    plan_overlay_text = ""
                    if plan_overlay == "title":
                        plan_overlay_text = item["post_text"].strip().split("\n")[0]
                    elif plan_overlay == "author":
                        plan_overlay_text = st.text_input("Имя / должность", key=f"plan_author_{i}_v{pv}",
                                                          placeholder="Антон · Психотерапевт")
                    elif plan_overlay == "custom":
                        plan_overlay_text = st.text_input("Текст для наложения", key=f"plan_custom_{i}_v{pv}")
                    elif plan_overlay == "hashtags":
                        plan_overlay_text = item["post_text"].strip().split("\n")[-1]

                    plan_img_comment = st.text_input(
                        "Уточнения для картинки",
                        placeholder="Например: покажи одинокую фигуру у окна, тёплые тона, без людей...",
                        key=f"plan_img_comment_{i}_v{pv}"
                    )

                    plan_realism_key = f"plan_realism_{i}_v{pv}"
                    plan_realism_style_key = f"_plan_last_style_{i}"
                    if st.session_state.get(plan_realism_style_key) != plan_style:
                        st.session_state[plan_realism_style_key] = plan_style
                        st.session_state[plan_realism_key] = STYLE_DEFAULT_REALISM.get(plan_style, 5)
                    plan_realism = st.slider(
                        "Реалистичность",
                        min_value=0, max_value=10,
                        key=plan_realism_key,
                        help="0 — абстракция · 10 — фотореализм"
                    )
                    st.caption(
                        ["Абстракция", "Абстракция", "Метафора", "Метафора", "Символизм",
                         "Баланс", "Близко к реальности", "Близко к реальности",
                         "Реализм", "Фотореализм", "Фотореализм"][plan_realism]
                    )

                    plan_img_key = f"plan_img_path_{i}"
                    plan_prompt_key = f"plan_flux_prompt_{i}"
                    pb1, pb2 = st.columns([1, 1])
                    with pb1:
                        gen_plan_img = st.button("🎨 Сгенерировать картинку", key=f"plan_img_{i}_v{pv}", type="primary")
                    with pb2:
                        regen_plan_img = st.button("🔄 Другой вариант", key=f"plan_img_regen_{i}_v{pv}",
                                                   disabled=plan_img_key not in st.session_state)

                    if gen_plan_img or regen_plan_img:
                        with st.spinner("Генерирую картинку... (~20 секунд)"):
                            try:
                                topic_for_img = item.get("topic") or item.get("theme") or "психотерапия"
                                img, flux_prompt = generate_image(topic_for_img, plan_style, plan_size, post_text=edited_plan, tone=post_tone, user_comment=plan_img_comment, realism=plan_realism)
                                img = apply_overlay(img, plan_overlay, plan_overlay_text, position=plan_position)
                                img_path = save_and_upload_image(img, topic_for_img)
                                st.session_state[plan_img_key] = img_path
                                st.session_state[plan_prompt_key] = flux_prompt
                                history_id = st.session_state.get(f"plan_history_id_{i}")
                                if history_id:
                                    update_history_image(str(img_path), history_id)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ошибка: {e}")

                    if plan_img_key in st.session_state:
                        try:
                            st.image(st.session_state[plan_img_key], use_container_width=True)
                            st.download_button("📥 Скачать картинку",
                                               data=load_image_bytes(st.session_state[plan_img_key]),
                                               file_name=f"image_{item['date'].replace('.','_')}.jpg",
                                               mime="image/jpeg", key=f"plan_img_dl_{i}_v{pv}")
                            if plan_prompt_key in st.session_state:
                                with st.expander("🔍 Промпт для картинки"):
                                    st.text(st.session_state[plan_prompt_key])
                        except Exception:
                            pass


with tab_history:
    history = load_history()

    if not history:
        st.info("История пустая — сгенерируй первый пост.")
    else:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"## История · {len(history)} постов")
        with col2:
            st.markdown("")
            if st.button("Очистить", key="clear_history"):
                clear_history()
                st.rerun()

        for i, item in enumerate(history):
            has_image = image_exists(item.get("image_path", ""))
            img_icon = "🖼️ " if has_image else ""
            label = f"{item.get('platform_icon','📝')}  {img_icon}{item['topic']}  ·  {item['date']}"
            with st.expander(label):
                st.caption(f"{item['platform']}  ·  {item['notebook']}")

                if has_image:
                    col_text, col_img = st.columns([3, 2])
                    with col_text:
                        edited_h = st.text_area(
                            "",
                            value=item["text"],
                            height=360,
                            key=f"h_{i}",
                            label_visibility="collapsed"
                        )
                    with col_img:
                        st.image(item["image_path"], use_container_width=True)
                        st.download_button(
                            "📥 Скачать картинку",
                            data=load_image_bytes(item["image_path"]),
                            file_name=f"image_{i+1}.jpg",
                            mime="image/jpeg",
                            key=f"dl_img_{i}"
                        )
                else:
                    edited_h = st.text_area(
                        "",
                        value=item["text"],
                        height=360,
                        key=f"h_{i}",
                        label_visibility="collapsed"
                    )

                cola, colb = st.columns([1, 4])
                with cola:
                    st.download_button(
                        "📥 Скачать текст",
                        data=edited_h,
                        file_name=f"post_{i+1}.txt",
                        mime="text/plain",
                        key=f"dl_{i}"
                    )
                st.code(item["text"], language=None)
