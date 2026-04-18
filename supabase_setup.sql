-- Выполни этот SQL в Supabase → SQL Editor один раз

-- Таблица истории постов
CREATE TABLE IF NOT EXISTS post_history (
    id TEXT PRIMARY KEY,
    date TEXT,
    topic TEXT,
    platform TEXT,
    platform_label TEXT,
    platform_icon TEXT,
    notebook TEXT,
    post_text TEXT,
    image_url TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица контент-плана (один текущий план)
CREATE TABLE IF NOT EXISTS content_plans (
    id TEXT PRIMARY KEY DEFAULT 'current',
    plan_data JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bucket для картинок: создай вручную в Supabase → Storage → New bucket
-- Название: post-images
-- Тип: Public
