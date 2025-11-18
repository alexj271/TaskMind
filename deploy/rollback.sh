#!/bin/bash

# TaskMind Rollback Script
# Откат к предыдущей версии в случае проблем

set -e

DEPLOY_SERVER="root@visitbot.ru"
DEPLOY_PATH="/opt/TaskMind"
BACKUP_PATH="/opt/backups/TaskMind"

echo "🔄 Начинаю откат TaskMind на $DEPLOY_SERVER"

# Список доступных резервных копий
echo "📋 Доступные резервные копии:"
ssh $DEPLOY_SERVER "ls -la $BACKUP_PATH/ | grep backup-"

# Выбор резервной копии (берем последнюю)
LATEST_BACKUP=$(ssh $DEPLOY_SERVER "ls -t $BACKUP_PATH/ | grep backup- | head -1")

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ Резервные копии не найдены!"
    exit 1
fi

echo "🔄 Выполняю откат к резервной копии: $LATEST_BACKUP"

# Остановка сервисов
echo "⏹️ Остановка сервисов..."
ssh $DEPLOY_SERVER "
    supervisorctl stop taskmind-api
    supervisorctl stop taskmind-worker
"

# Восстановление из резервной копии
echo "📦 Восстановление файлов..."
ssh $DEPLOY_SERVER "
    rm -rf $DEPLOY_PATH
    cp -r $BACKUP_PATH/$LATEST_BACKUP $DEPLOY_PATH
"

# Запуск сервисов
echo "▶️ Запуск сервисов..."
ssh $DEPLOY_SERVER "
    supervisorctl start taskmind-api
    supervisorctl start taskmind-worker
"

# Проверка статуса
echo "✅ Откат завершен. Проверка статуса:"
ssh $DEPLOY_SERVER "supervisorctl status"

echo "🎉 Откат к версии $LATEST_BACKUP успешно выполнен!"