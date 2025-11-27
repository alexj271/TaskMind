#!/bin/bash

# TaskMind Logs Viewer
# Удобный просмотр логов приложения

DEPLOY_SERVER="root@visitbot.ru"

show_help() {
    echo "TaskMind Logs Viewer"
    echo ""
    echo "Использование: ./logs.sh [опция]"
    echo ""
    echo "Опции:"
    echo "  api       - Логи FastAPI сервера"
    echo "  worker    - Логи Dramatiq воркера"
    echo "  nginx     - Логи Nginx"
    echo "  postgres  - Логи PostgreSQL"
    echo "  redis     - Логи Redis"
    echo "  monitor   - Логи мониторинга"
    echo "  all       - Все логи"
    echo "  tail      - Следить за логами в реальном времени"
    echo "  errors    - Только ошибки"
}

case "$1" in
    "api")
        echo "📊 Логи FastAPI сервера:"
        ssh $DEPLOY_SERVER "tail -n 50 /var/log/taskmind-api.out.log"
        ;;
    "worker")
        echo "⚙️ Логи Dramatiq воркера:"
        ssh $DEPLOY_SERVER "tail -n 50 /var/log/taskmind-worker.err.log"
        ;;
    "nginx")
        echo "🌐 Логи Nginx:"
        ssh $DEPLOY_SERVER "tail -n 50 /var/log/nginx/access.log"
        ;;
    "postgres")
        echo "🗄️ Логи PostgreSQL:"
        ssh $DEPLOY_SERVER "tail -n 50 /var/log/postgresql/postgresql-*.log | head -50"
        ;;
    "redis")
        echo "🔴 Логи Redis:"
        ssh $DEPLOY_SERVER "tail -n 50 /var/log/redis/redis-server.log"
        ;;
    "monitor")
        echo "🔍 Логи мониторинга:"
        ssh $DEPLOY_SERVER "tail -n 50 /var/log/taskmind-monitor.log"
        ;;
    "all")
        echo "📋 Все логи TaskMind:"
        echo ""
        echo "=== API ==="
        ssh $DEPLOY_SERVER "tail -n 20 /var/log/taskmind-api.out.log"
        echo ""
        echo "=== Worker ==="
        ssh $DEPLOY_SERVER "tail -n 20 /var/log/taskmind-worker.out.log"
        echo ""
        echo "=== Nginx ==="
        ssh $DEPLOY_SERVER "tail -n 10 /var/log/nginx/access.log"
        ;;
    "tail")
        echo "👀 Следим за логами в реальном времени (Ctrl+C для выхода):"
        ssh $DEPLOY_SERVER "tail -f /var/log/taskmind-api.out.log /var/log/taskmind-worker.out.log"
        ;;
    "errors")
        echo "❌ Только ошибки:"
        ssh $DEPLOY_SERVER "
            echo '=== API Errors ==='
            tail -n 50 /var/log/taskmind-api.err.log
            echo ''
            echo '=== Worker Errors ==='
            tail -n 50 /var/log/taskmind-worker.err.log
            echo ''
            echo '=== Nginx Errors ==='
            tail -n 20 /var/log/nginx/error.log
        "
        ;;
    *)
        show_help
        ;;
esac