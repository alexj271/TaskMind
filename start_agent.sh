#!/bin/bash
# Простой bash скрипт для запуска Agent Worker

# Переходим в корневую директорию проекта
cd "$(dirname "$0")"

# Активируем виртуальное окружение если есть
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Активировано виртуальное окружение .venv"
fi

# Запускаем Agent Worker
echo "Запуск TaskMind Agent Worker..."
python app/run_agent_worker.py "$@"