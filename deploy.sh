#!/bin/bash

# Скрипт развертывания корпоративного бота
# Использование: ./deploy.sh [install|update|restart|status|logs]

set -e

# Конфигурация
BOT_DIR="/opt/corporate-bot"
SERVICE_NAME="corporate-bot"
USER="bot-user"
GROUP="bot-group"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав администратора
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Этот скрипт должен выполняться с правами root"
        exit 1
    fi
}

# Установка зависимостей системы
install_system_deps() {
    log_info "Установка системных зависимостей..."
    
    # Обновление пакетов
    apt update
    
    # Установка необходимых пакетов
    apt install -y python3 python3-pip python3-venv git nginx supervisor curl wget
    
    log_success "Системные зависимости установлены"
}

# Создание пользователя
create_user() {
    log_info "Создание пользователя для бота..."
    
    if ! id "$USER" &>/dev/null; then
        useradd -r -s /bin/bash -d "$BOT_DIR" -m "$USER"
        usermod -aG sudo "$USER"
        log_success "Пользователь $USER создан"
    else
        log_warning "Пользователь $USER уже существует"
    fi
}

# Клонирование/обновление репозитория
setup_repository() {
    log_info "Настройка репозитория..."
    
    if [ ! -d "$BOT_DIR" ]; then
        mkdir -p "$BOT_DIR"
        chown "$USER:$GROUP" "$BOT_DIR"
        log_info "Директория $BOT_DIR создана"
    fi
    
    # Если это первая установка, клонируем репозиторий
    if [ ! -d "$BOT_DIR/.git" ]; then
        log_info "Клонирование репозитория..."
        # Замените на ваш репозиторий
        # git clone https://github.com/your-username/corporate-bot.git "$BOT_DIR"
        log_warning "Пожалуйста, скопируйте файлы проекта в $BOT_DIR вручную"
    else
        log_info "Обновление репозитория..."
        cd "$BOT_DIR"
        git pull origin main
    fi
    
    chown -R "$USER:$GROUP" "$BOT_DIR"
}

# Настройка виртуального окружения
setup_venv() {
    log_info "Настройка виртуального окружения..."
    
    cd "$BOT_DIR"
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "Виртуальное окружение создано"
    fi
    
    # Активация и установка зависимостей
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log_success "Зависимости установлены"
}

# Настройка переменных окружения
setup_env() {
    log_info "Настройка переменных окружения..."
    
    cd "$BOT_DIR"
    
    if [ ! -f ".env" ]; then
        if [ -f "env_example.txt" ]; then
            cp env_example.txt .env
            log_warning "Файл .env создан из примера. Пожалуйста, отредактируйте его!"
        else
            log_error "Файл env_example.txt не найден!"
            exit 1
        fi
    else
        log_warning "Файл .env уже существует"
    fi
    
    chown "$USER:$GROUP" .env
    chmod 600 .env
}

# Настройка systemd сервиса
setup_service() {
    log_info "Настройка systemd сервиса..."
    
    # Копирование файла сервиса
    cp corporate-bot.service /etc/systemd/system/
    
    # Замена путей в файле сервиса
    sed -i "s|/path/to/bot_office|$BOT_DIR|g" /etc/systemd/system/corporate-bot.service
    sed -i "s|your-user|$USER|g" /etc/systemd/system/corporate-bot.service
    sed -i "s|your-group|$GROUP|g" /etc/systemd/system/corporate-bot.service
    
    # Перезагрузка systemd
    systemctl daemon-reload
    
    # Включение автозапуска
    systemctl enable corporate-bot
    
    log_success "Systemd сервис настроен"
}

# Настройка Nginx (опционально)
setup_nginx() {
    log_info "Настройка Nginx..."
    
    # Создание конфигурации Nginx
    cat > /etc/nginx/sites-available/corporate-bot << EOF
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Активация сайта
    ln -sf /etc/nginx/sites-available/corporate-bot /etc/nginx/sites-enabled/
    
    # Проверка конфигурации
    nginx -t
    
    # Перезапуск Nginx
    systemctl restart nginx
    
    log_success "Nginx настроен"
}

# Установка
install() {
    log_info "Начинаем установку корпоративного бота..."
    
    check_root
    install_system_deps
    create_user
    setup_repository
    setup_venv
    setup_env
    setup_service
    
    log_success "Установка завершена!"
    log_info "Следующие шаги:"
    log_info "1. Отредактируйте файл $BOT_DIR/.env"
    log_info "2. Запустите бота: systemctl start corporate-bot"
    log_info "3. Проверьте статус: systemctl status corporate-bot"
}

# Обновление
update() {
    log_info "Обновление корпоративного бота..."
    
    check_root
    
    # Остановка сервиса
    systemctl stop corporate-bot
    
    # Обновление кода
    setup_repository
    
    # Обновление зависимостей
    setup_venv
    
    # Запуск сервиса
    systemctl start corporate-bot
    
    log_success "Обновление завершено!"
}

# Перезапуск
restart() {
    log_info "Перезапуск корпоративного бота..."
    
    check_root
    systemctl restart corporate-bot
    log_success "Бот перезапущен!"
}

# Статус
status() {
    log_info "Статус корпоративного бота:"
    systemctl status corporate-bot --no-pager -l
}

# Логи
logs() {
    log_info "Логи корпоративного бота:"
    journalctl -u corporate-bot -f
}

# Основная логика
case "${1:-}" in
    install)
        install
        ;;
    update)
        update
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Использование: $0 {install|update|restart|status|logs}"
        echo ""
        echo "Команды:"
        echo "  install  - Первоначальная установка"
        echo "  update   - Обновление кода и зависимостей"
        echo "  restart  - Перезапуск сервиса"
        echo "  status   - Показать статус сервиса"
        echo "  logs     - Показать логи в реальном времени"
        exit 1
        ;;
esac 