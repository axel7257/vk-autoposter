#!/bin/bash
# ВСПОМИНАЛКА: загружает память в начале сессии

MEMORY_DIR="$HOME/.claude/projects/-Users-anton-vk-autoposter/memory"
LOG_DIR="$MEMORY_DIR/logs"

echo "=== ПАМЯТЬ ПРОЕКТА ==="

# Читаем индекс памяти
if [ -f "$MEMORY_DIR/MEMORY.md" ]; then
    echo "--- Индекс памяти ---"
    cat "$MEMORY_DIR/MEMORY.md"
fi

# Читаем последний дневной лог если есть
if [ -d "$LOG_DIR" ]; then
    LAST_LOG=$(ls -t "$LOG_DIR"/*.md 2>/dev/null | head -1)
    if [ -n "$LAST_LOG" ]; then
        echo ""
        echo "--- Последний лог ($(basename $LAST_LOG)) ---"
        cat "$LAST_LOG"
    fi
fi

echo "=== КОНЕЦ ПАМЯТИ ==="
