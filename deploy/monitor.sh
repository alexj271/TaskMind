#!/bin/bash

# TaskMind Monitoring Script
# Мониторинг состояния приложения и автоматический перезапуск при необходимости

DEPLOY_SERVER="root@visitbot.ru"
WEBHOOK_URL="https://visitbot.ru/docs"
LOG_FILE="/var/log/taskmind-monitor.log"

# Функция логирования
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# Проверка API
check_api() {
    if curl -s -k --connect-timeout 10 "$WEBHOOK_URL" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Проверка сервисов
check_services() {
    ssh $DEPLOY_SERVER "
        systemctl is-active nginx redis-server postgresql > /dev/null 2>&1 &&
        supervisorctl status taskmind-api taskmind-worker | grep -q RUNNING
    "
}

# Перезапуск сервисов
restart_services() {
    log_message "🔄 Перезапуск сервисов TaskMind..."
    ssh $DEPLOY_SERVER "
        supervisorctl restart taskmind-api
        supervisorctl restart taskmind-worker
        systemctl reload nginx
    "
}

# Отправка уведомления (можно настроить Telegram/email)
send_notification() {
    local message="$1"
    log_message "📢 $message"
    # Здесь можно добавить отправку в Telegram или email
}

# Основная проверка
main_check() {
    log_message "🔍 Начинаю проверку состояния TaskMind..."
    
    if check_api; then
        log_message "✅ API отвечает нормально"
        return 0
    else
        log_message "❌ API не отвечает, проверяю сервисы..."
        
        if check_services; then
            log_message "⚠️ Сервисы работают, но API недоступен. Перезапускаю..."
            restart_services
            sleep 10
            
            if check_api; then
                log_message "✅ API восстановлен после перезапуска"
                send_notification "TaskMind восстановлен автоматически"
                return 0
            else
                log_message "❌ API все еще недоступен после перезапуска!"
                send_notification "КРИТИЧНО: TaskMind не удалось восстановить!"
                return 1
            fi
        else
            log_message "❌ Системные сервисы не работают!"
            send_notification "КРИТИЧНО: Системные сервисы TaskMind не работают!"
            return 1
        fi
    fi
}

# Запуск проверки
main_check