#!/bin/bash

# SSL Certificate Management Script
# Управление SSL сертификатами Let's Encrypt

DEPLOY_SERVER="root@visitbot.ru"
DOMAIN="visitbot.ru"

show_help() {
    echo "TaskMind SSL Certificate Management"
    echo ""
    echo "Использование: ./ssl.sh [команда]"
    echo ""
    echo "Команды:"
    echo "  status    - Проверить статус сертификата"
    echo "  renew     - Обновить сертификат"
    echo "  install   - Установить certbot (если не установлен)"
    echo "  auto      - Настроить автоматическое обновление"
    echo "  test      - Тестовое обновление (dry-run)"
}

check_ssl_status() {
    echo "🔍 Проверка статуса SSL сертификата для $DOMAIN..."
    
    ssh $DEPLOY_SERVER "
        echo '=== Статус сертификата ==='
        certbot certificates
        echo ''
        echo '=== Проверка срока действия ==='
        openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -dates
        echo ''
        echo '=== Проверка HTTPS соединения ==='
        curl -I https://$DOMAIN/ 2>/dev/null | head -1
    "
}

renew_certificate() {
    echo "🔄 Обновление SSL сертификата..."
    
    ssh $DEPLOY_SERVER "
        echo 'Остановка Nginx...'
        systemctl stop nginx
        
        echo 'Обновление сертификата...'
        certbot renew --force-renewal
        
        echo 'Запуск Nginx...'
        systemctl start nginx
        
        echo 'Проверка статуса...'
        systemctl status nginx
        
        echo 'Тестирование HTTPS...'
        curl -I https://$DOMAIN/ 2>/dev/null | head -1
    "
}

install_certbot() {
    echo "📦 Установка Certbot..."
    
    ssh $DEPLOY_SERVER "
        apt update
        apt install -y certbot python3-certbot-nginx
        
        echo 'Certbot установлен. Версия:'
        certbot --version
    "
}

setup_auto_renewal() {
    echo "⏰ Настройка автоматического обновления..."
    
    ssh $DEPLOY_SERVER "
        # Создание скрипта обновления
        cat > /usr/local/bin/ssl-renew.sh << 'EOF'
#!/bin/bash
certbot renew --quiet --nginx
systemctl reload nginx
EOF
        
        chmod +x /usr/local/bin/ssl-renew.sh
        
        # Добавление в crontab
        (crontab -l 2>/dev/null; echo '0 2 * * 1 /usr/local/bin/ssl-renew.sh') | crontab -
        
        echo 'Автоматическое обновление настроено (каждый понедельник в 2:00)'
        crontab -l | grep ssl-renew
    "
}

test_renewal() {
    echo "🧪 Тестовое обновление сертификата (dry-run)..."
    
    ssh $DEPLOY_SERVER "
        certbot renew --dry-run
    "
}

case "$1" in
    "status")
        check_ssl_status
        ;;
    "renew")
        renew_certificate
        ;;
    "install")
        install_certbot
        ;;
    "auto")
        setup_auto_renewal
        ;;
    "test")
        test_renewal
        ;;
    *)
        show_help
        ;;
esac