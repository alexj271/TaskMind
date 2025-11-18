#!/bin/bash

# TaskMind Production Deployment Script
# Автоматическое развертывание на продакшн сервере visitbot.ru

set -e  # Остановка при ошибке

# Конфигурация
DEPLOY_SERVER="root@visitbot.ru"
DEPLOY_PATH="/opt/TaskMind"
APP_NAME="taskmind"
BACKUP_PATH="/opt/backups/TaskMind"

echo "🚀 Начинаю развертывание TaskMind на $DEPLOY_SERVER"

# Проверка SSH соединения
echo "📡 Проверка SSH соединения..."
if ! ssh -o ConnectTimeout=10 $DEPLOY_SERVER "echo 'SSH подключение успешно'"; then
    echo "❌ Ошибка SSH подключения к $DEPLOY_SERVER"
    exit 1
fi

# Создание резервной копии (если приложение уже развернуто)
echo "💾 Создание резервной копии..."
ssh $DEPLOY_SERVER "
    if [ -d '$DEPLOY_PATH' ]; then
        mkdir -p $BACKUP_PATH
        cp -r $DEPLOY_PATH $BACKUP_PATH/backup-\$(date +%Y%m%d-%H%M%S)
        echo '✅ Резервная копия создана'
    else
        echo '📝 Первое развертывание, резервная копия не нужна'
    fi
"

# Подготовка директории
echo "📁 Подготовка директории развертывания..."
ssh $DEPLOY_SERVER "
    mkdir -p $DEPLOY_PATH
    cd $DEPLOY_PATH
"

# Копирование файлов проекта
echo "📤 Копирование файлов проекта..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.venv' \
    --exclude='deploy/' \
    --exclude='*.log' \
    --exclude='.coverage' \
    --exclude='htmlcov/' \
    ../ $DEPLOY_SERVER:$DEPLOY_PATH/

# Проверка успешного копирования ключевых файлов
echo "🔍 Проверка скопированных файлов..."
ssh $DEPLOY_SERVER "
    cd $DEPLOY_PATH
    echo 'Содержимое корневой директории:'
    ls -la
    echo '---'
    echo 'Проверка requirements.txt:'
    [ -f requirements.txt ] && echo '✅ requirements.txt найден' || echo '❌ requirements.txt НЕ найден'
    echo '---'
    echo 'Проверка app/ директории:'
    [ -d app ] && echo '✅ app/ директория найдена' || echo '❌ app/ директория НЕ найдена'
"

# Копирование production конфигурации
echo "⚙️ Настройка production конфигурации..."
scp .env $DEPLOY_SERVER:$DEPLOY_PATH/.env

# Установка зависимостей и настройка окружения
echo "🔧 Установка зависимостей на сервере..."
ssh $DEPLOY_SERVER "
    cd $DEPLOY_PATH
    
    # Проверка наличия requirements.txt
    if [ ! -f 'requirements.txt' ]; then
        echo '❌ Файл requirements.txt не найден!'
        exit 1
    fi
    echo '📝 Найден requirements.txt:'
    head -5 requirements.txt
    
    # Обновление системы
    apt update && apt upgrade -y
    
    # Установка Python и зависимостей
    apt install -y python3 python3-pip python3-venv postgresql redis-server nginx supervisor
    
    # Создание виртуального окружения
    rm -rf venv  # Удаляем старое окружение если есть
    python3 -m venv venv
    source venv/bin/activate
    
    # Проверка активации окружения
    which python
    which pip
    
    # Установка Python зависимостей
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Проверка установки uvicorn
    pip show uvicorn || echo '❌ uvicorn не установлен!'
    
    echo '✅ Зависимости установлены'
"

# Настройка базы данных
echo "🗄️ Настройка PostgreSQL..."
ssh $DEPLOY_SERVER "
    # Создание пользователя и базы данных
    sudo -u postgres psql -c \"CREATE USER taskmind WITH PASSWORD 'password';\" || echo 'Пользователь уже существует'
    sudo -u postgres psql -c \"CREATE DATABASE taskmind OWNER taskmind;\" || echo 'База данных уже существует'
    sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE taskmind TO taskmind;\"
    
    echo '✅ База данных настроена'
"

# Настройка Nginx
echo "🌐 Настройка Nginx..."

# Копирование конфигурационных файлов
scp nginx.conf $DEPLOY_SERVER:/etc/nginx/sites-available/taskmind
scp nginx-http.conf $DEPLOY_SERVER:/tmp/nginx-http-snippet.conf

ssh $DEPLOY_SERVER "
    # Добавление rate limiting в основную конфигурацию nginx
    if ! grep -q 'webhook_limit' /etc/nginx/nginx.conf; then
        sed -i '/http {/r /tmp/nginx-http-snippet.conf' /etc/nginx/nginx.conf
    fi
    
    # Активация конфигурации сайта
    ln -sf /etc/nginx/sites-available/taskmind /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Проверка и перезагрузка
    nginx -t && systemctl reload nginx
    
    # Очистка временного файла
    rm -f /tmp/nginx-http-snippet.conf
    
    echo '✅ Nginx настроен'
"

# Настройка Supervisor для управления процессами
echo "👨‍💼 Настройка Supervisor..."
ssh $DEPLOY_SERVER "
    cat > /etc/supervisor/conf.d/taskmind.conf << 'EOF'
[program:taskmind-api]
command=$DEPLOY_PATH/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
directory=$DEPLOY_PATH
user=root
autostart=true
autorestart=true
stderr_logfile=/var/log/taskmind-api.err.log
stdout_logfile=/var/log/taskmind-api.out.log
environment=PATH=\"$DEPLOY_PATH/venv/bin\"

[program:taskmind-worker]
command=$DEPLOY_PATH/venv/bin/python -m dramatiq app.workers.telegram_actors
directory=$DEPLOY_PATH
user=root
autostart=true
autorestart=true
stderr_logfile=/var/log/taskmind-worker.err.log
stdout_logfile=/var/log/taskmind-worker.out.log
environment=PATH=\"$DEPLOY_PATH/venv/bin\"
EOF

    # Обновление конфигурации Supervisor
    supervisorctl reread
    supervisorctl update
    
    echo '✅ Supervisor настроен'
"

# Запуск сервисов
echo "🏃 Запуск сервисов..."
ssh $DEPLOY_SERVER "
    # Запуск Redis
    systemctl enable redis-server
    systemctl start redis-server
    
    # Запуск PostgreSQL
    systemctl enable postgresql
    systemctl start postgresql
    
    # Запуск Nginx
    systemctl enable nginx
    systemctl start nginx
    
    # Запуск приложения через Supervisor
    supervisorctl start taskmind-api
    supervisorctl start taskmind-worker
    
    echo '✅ Все сервисы запущены'
"

# Проверка статуса
echo "🔍 Проверка статуса развертывания..."
ssh $DEPLOY_SERVER "
    echo '=== Статус сервисов ==='
    systemctl is-active nginx redis-server postgresql
    
    echo '=== Статус приложения ==='
    supervisorctl status
    
    echo '=== Проверка портов ==='
    netstat -tlnp | grep -E ':80|:8000|:6379|:5432'
"

# Запуск тестов на продакшене
echo "🧪 Запуск тестов на продакшене..."
ssh $DEPLOY_SERVER "
    cd $DEPLOY_PATH
    source venv/bin/activate
    
    echo 'Запуск быстрых тестов (исключая медленные интеграционные тесты)...'
    python -m pytest test/ -v --tb=short -x -m 'not slow' || echo 'Некоторые тесты не прошли, но деплой продолжается'
    
    echo 'Проверка критически важных компонентов...'
    export PYTHONPATH=$DEPLOY_PATH:\$PYTHONPATH
    python -c \"
import asyncio
import sys
sys.path.insert(0, '$DEPLOY_PATH')
from app.services.openai_tools import OpenAIService
from app.core.db import init_db
print('✅ Импорты успешны')

async def test_basic():
    try:
        await init_db()
        print('✅ База данных подключена')
    except Exception as e:
        print(f'⚠️ Проблема с БД: {e}')
        
    try:
        service = OpenAIService()
        print('✅ OpenAI сервис инициализирован')
    except Exception as e:
        print(f'⚠️ Проблема с OpenAI: {e}')

asyncio.run(test_basic())
\" || echo 'Проблемы с базовой проверкой'
"

# Финальная проверка API
echo "🌐 Тестирование API через HTTP..."
sleep 5  # Ждем запуска
if curl -s -k "https://visitbot.ru/docs" > /dev/null; then
    echo "✅ API успешно отвечает на https://visitbot.ru/docs"
elif curl -s "http://visitbot.ru/docs" > /dev/null; then
    echo "✅ API отвечает на HTTP (SSL может настраиваться)"
else
    echo "⚠️ API может быть еще не готов, проверьте логи"
fi

echo ""
echo "🎉 Развертывание TaskMind завершено!"
echo ""
echo "📋 Полезные команды для управления:"
echo "   Статус:      ssh $DEPLOY_SERVER 'supervisorctl status'"
echo "   Перезапуск:  ssh $DEPLOY_SERVER 'supervisorctl restart all'"
echo "   Логи API:    ssh $DEPLOY_SERVER 'tail -f /var/log/taskmind-api.out.log'"
echo "   Логи Worker: ssh $DEPLOY_SERVER 'tail -f /var/log/taskmind-worker.out.log'"
echo ""
echo "🌐 Приложение доступно по адресу: https://visitbot.ru"
echo "📚 Документация API: https://visitbot.ru/docs"
echo "🔗 Telegram Webhook: https://visitbot.ru/webhook/telegram"