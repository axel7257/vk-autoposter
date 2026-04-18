#!/bin/bash
# СТРАХОВКА: сохраняет состояние памяти перед сжатием контекста

MEMORY_DIR="$HOME/.claude/projects/-Users-anton-vk-autoposter/memory"
BACKUP_DIR="$MEMORY_DIR/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")

# Копируем все файлы памяти в бэкап
cp -r "$MEMORY_DIR"/*.md "$BACKUP_DIR/${TIMESTAMP}_backup/" 2>/dev/null
mkdir -p "$BACKUP_DIR/${TIMESTAMP}_backup/"
cp "$MEMORY_DIR"/*.md "$BACKUP_DIR/${TIMESTAMP}_backup/" 2>/dev/null

# Оставляем только последние 5 бэкапов
ls -t "$BACKUP_DIR" | tail -n +6 | xargs -I {} rm -rf "$BACKUP_DIR/{}" 2>/dev/null

echo "Состояние памяти сохранено: $TIMESTAMP"
