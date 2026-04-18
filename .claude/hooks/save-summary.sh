#!/bin/bash
# ЗАПИСЫВАЛКА: сохраняет краткий лог сессии при завершении

MEMORY_DIR="$HOME/.claude/projects/-Users-anton-vk-autoposter/memory"
LOG_DIR="$MEMORY_DIR/logs"
mkdir -p "$LOG_DIR"

DATE=$(date +"%Y-%m-%d")
TIME=$(date +"%H:%M")
LOG_FILE="$LOG_DIR/$DATE.md"

# Читаем данные сессии из stdin (Claude передаёт их при завершении)
SESSION_DATA=$(cat 2>/dev/null)

# Добавляем запись в лог дня
{
    if [ ! -f "$LOG_FILE" ]; then
        echo "# Лог $DATE"
        echo ""
    fi
    echo "## Сессия $TIME"
    echo ""
    if [ -n "$SESSION_DATA" ]; then
        echo "$SESSION_DATA" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    summary = data.get('summary', '')
    if summary:
        print(summary)
    else:
        print('Сессия завершена.')
except:
    print('Сессия завершена.')
" 2>/dev/null || echo "Сессия завершена."
    else
        echo "Сессия завершена."
    fi
    echo ""
} >> "$LOG_FILE"
