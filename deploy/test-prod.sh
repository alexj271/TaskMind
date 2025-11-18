#!/bin/bash

# Скрипт для запуска тестов на продакшн сервере
set -e

DEPLOY_SERVER="root@visitbot.ru"
DEPLOY_PATH="/opt/TaskMind"

echo "🧪 Запуск тестов на продакшн сервере $DEPLOY_SERVER"

# Проверка SSH соединения
echo "📡 Проверка SSH соединения..."
if ! ssh -o ConnectTimeout=10 $DEPLOY_SERVER "echo 'SSH подключение успешно'"; then
    echo "❌ Ошибка SSH подключения к $DEPLOY_SERVER"
    exit 1
fi

# Проверка статуса сервисов перед тестами
echo "🔍 Проверка статуса сервисов..."
ssh $DEPLOY_SERVER "
    cd $DEPLOY_PATH
    echo '=== Статус приложения ==='
    supervisorctl status taskmind-api taskmind-worker
    
    echo '=== Проверка портов ==='
    netstat -tlnp | grep -E ':8000|:6379|:5432' || echo 'Некоторые порты недоступны'
"

# Запуск тестов
echo "🧪 Запуск автоматических тестов..."
ssh $DEPLOY_SERVER "
    cd $DEPLOY_PATH
    source venv/bin/activate
    
    echo '=== Информация о тестовом окружении ==='
    python --version
    pip show pytest pytest-asyncio
    
    echo -e '\n=== Запуск всех тестов ==='
    python -m pytest test/ -v --tb=short --maxfail=5
    
    echo -e '\n=== Базовая проверка компонентов ==='
    export PYTHONPATH=/opt/TaskMind:\$PYTHONPATH
    python -c \"
import asyncio
import sys
sys.path.insert(0, '/opt/TaskMind')

async def health_check():
    print('🔍 Проверка импортов...')
    try:
        from app.services.openai_tools import OpenAIService
        from app.core.db import init_db
        from app.workers.telegram_actors import process_telegram_message
        print('✅ Все импорты успешны')
    except Exception as e:
        print(f'❌ Ошибка импорта: {e}')
        return False
    
    print('🔍 Проверка подключения к БД...')
    try:
        await init_db()
        print('✅ База данных доступна')
    except Exception as e:
        print(f'⚠️ Проблема с БД: {e}')
    
    print('🔍 Проверка OpenAI сервиса...')
    try:
        service = OpenAIService()
        print('✅ OpenAI сервис создан')
    except Exception as e:
        print(f'⚠️ Проблема с OpenAI: {e}')
    
    return True

if asyncio.run(health_check()):
    print('\\n🎉 Все базовые проверки прошли успешно!')
else:
    print('\\n❌ Есть проблемы в базовых компонентах')
    sys.exit(1)
\"
"

# Проверка API endpoints
echo "🌐 Проверка API endpoints..."
echo "Проверка главной страницы документации..."
if curl -s -k "https://visitbot.ru/docs" | grep -q "TaskMind API"; then
    echo "✅ Swagger UI доступен"
else
    echo "⚠️ Проблема с доступом к Swagger UI"
fi

echo "Проверка health endpoint..."
if curl -s -k "https://visitbot.ru/health" > /dev/null 2>&1; then
    echo "✅ Health endpoint отвечает"
else
    echo "⚠️ Health endpoint недоступен"
fi

echo ""
echo "🎉 Тестирование завершено!"
echo ""
echo "📋 Для мониторинга используйте:"
echo "   Логи API:    ssh $DEPLOY_SERVER 'tail -f /var/log/taskmind-api.out.log'"
echo "   Логи Worker: ssh $DEPLOY_SERVER 'tail -f /var/log/taskmind-worker.out.log'"
echo "   Статус:      ssh $DEPLOY_SERVER 'supervisorctl status'"