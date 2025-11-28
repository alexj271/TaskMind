#!/bin/bash
# Альтернативный скрипт запуска интеграционных тестов
# Использует --env-file опцию docker-compose

set -e

echo "🐳 Запуск интеграционных тестов через Docker Compose (с --env-file)"

# Переходим в директорию интеграционных тестов
cd "$(dirname "$0")"

# Проверяем наличие .env файла в родительской директории
ENV_FILE="../.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Файл .env не найден в $(dirname "$ENV_FILE"). Создайте его на основе .env.example"
    exit 1
fi

echo "📄 Используем переменные окружения из: $ENV_FILE"

# Создаем директории для отчетов и тестовых данных
mkdir -p reports test_data

# Проверяем, нужно ли пересобирать образы
BUILD_FLAG=""
if [ "$1" = "--build" ] || [ "$1" = "-b" ]; then
    echo "🔨 Будут пересобраны Docker образы"
    BUILD_FLAG="--build"
fi

# Запускаем сервисы и тесты с --env-file
echo "🚀 Запуск Docker Compose с тестами..."
OPENAI_API_KEY="$(grep '^OPENAI_API_KEY=' "$ENV_FILE" | cut -d'=' -f2-)" \
OPENAI_BASE_URL="$(grep '^OPENAI_BASE_URL=' "$ENV_FILE" | cut -d'=' -f2-)" \
docker-compose -f docker-compose.test.yml --env-file "$ENV_FILE" --profile test up $BUILD_FLAG --abort-on-container-exit

# Проверяем результат
if [ $? -eq 0 ]; then
    echo "✅ Интеграционные тесты прошли успешно"

    # Показываем последние отчеты
    echo "📊 Последние отчеты:"
    ls -la reports/ | tail -5

    # Показываем сводку последнего отчета
    LATEST_REPORT=$(ls -t reports/integration_test_report_*.json | head -1)
    if [ -f "$LATEST_REPORT" ]; then
        echo "📈 Сводка последнего теста:"
        python3 -c "
import json
with open('$LATEST_REPORT', 'r', encoding='utf-8') as f:
    data = json.load(f)
    summary = data['summary']
    print(f\"  • Сценариев: {summary['total_scenarios']}\")
    print(f\"  • Успешных: {summary['successful_scenarios']}\")
    print(f\"  • Вебхуков: {summary['total_webhooks_sent']}\")
    print(f\"  • Сообщений: {summary['total_messages_sent']}\")
        "
    fi
else
    echo "❌ Интеграционные тесты провалились"

    # Показываем логи контейнеров для диагностики
    echo "🔍 Логи последнего запуска:"
    docker-compose -f docker-compose.test.yml logs --tail=50 integration-tests

    exit 1
fi