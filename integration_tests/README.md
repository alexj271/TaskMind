# Integration Tests

Этот каталог содержит интеграционные тесты для TaskMind системы.

## Обзор

Интеграционные тесты запускают полную систему TaskMind (FastAPI API + Dramatiq воркеры) в изолированной Docker среде. Тесты эмулируют Telegram вебхуки и проверяют корректность обработки сообщений.

### Ключевые особенности

- **Полная изоляция**: Docker Compose обеспечивает изолированную среду
- **База данных**: SQLite файл для каждого тестового запуска
- **Перехват сообщений**: Telegram API полностью замокан
- **Асинхронная обработка**: Тесты корректно ждут завершения асинхронных операций
- **Детальные отчеты**: JSON отчеты с метриками и результатами

## Быстрый старт

### Через Docker Compose (рекомендуемый способ)

```bash
cd integration_tests
./run_docker_tests.sh
```

### Опции запуска

**Основной скрипт (`run_docker_tests.sh`):**
```bash
./run_docker_tests.sh              # Пересборка + запуск (по умолчанию)
./run_docker_tests.sh --no-build   # Запуск без пересборки (быстрее)
./run_docker_tests.sh --build      # Явная пересборка
```

**Альтернативный скрипт (`run_docker_tests_alt.sh`):**
```bash
./run_docker_tests_alt.sh          # Запуск без пересборки
./run_docker_tests_alt.sh --build  # С пересборкой
```

### Локальный запуск (для разработки)

```bash
cd /home/alex/project/vscode/TaskMind
source .venv/bin/activate
python integration_tests/run_integration_tests.py
```

### Быстрый тест функциональности

```bash
cd /home/alex/project/vscode/TaskMind
source .venv/bin/activate
python integration_tests/quick_test.py
```

## Конфигурация

### Переменные окружения

Создайте `.env` файл в корне проекта на основе `.env.example`:

```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
TELEGRAM_TOKEN=TEST_TOKEN
```

**Обязательные переменные:**
- `OPENAI_API_KEY` - API ключ для OpenAI (необходим для AI функций)
- `OPENAI_BASE_URL` - Базовый URL для OpenAI API

**Опциональные переменные:**
- `TELEGRAM_TOKEN` - Токен Telegram бота (по умолчанию: TEST_TOKEN)

### Параметры тестов

Файл `test_config.ini` содержит настройки таймаутов и сценариев.

## Архитектура

### Компоненты системы

1. **API сервис** (`api-test`): FastAPI приложение на порту 8000 внутри сети
2. **Dramatiq воркеры** (`dramatiq-test`): Асинхронные обработчики сообщений  
3. **Redis** (`redis-test`): Очередь сообщений на порту 6382
4. **Тестовый контейнер** (`integration-tests`): Запускает тесты и генерирует отчеты

### Сетевые взаимодействия

```
Тестовый контейнер → API (http://api-test:8000)
API → Redis (redis://redis-test:6379/1)
Воркеры → Redis (redis://redis-test:6379/1)
Воркеры → Telegram API (замокан)
```

## Тестовые сценарии

### 1. timezone_setup
**Цель**: Проверка установки часового пояса пользователя
- **Вход**: "Я из Москвы"
- **Ожидание**: Установка таймзоны, подтверждение в Telegram

### 2. task_creation  
**Цель**: Проверка создания задач через AI
- **Вход**: "Создай задачу: встреча завтра в 10 утра"
- **Ожидание**: Создание задачи в БД, подтверждение в Telegram

### 3. chat_message
**Цель**: Проверка обработки обычных сообщений
- **Вход**: "Привет, как дела?"
- **Ожидание**: Ответ от AI чат-бота

## Структура файлов

```
integration_tests/
├── docker-compose.test.yml    # Docker Compose конфигурация
├── Dockerfile.test           # Образ для тестового контейнера
├── run_integration_tests.py  # Основной скрипт тестов
├── quick_test.py             # Быстрый тест функциональности
├── run_docker_tests.sh       # Скрипт запуска через Docker
├── run_tests.sh              # Локальный запуск
├── test_config.ini           # Конфигурация параметров
├── .env.test                 # Тестовые переменные
├── README.md                 # Документация
└── reports/                  # Сгенерированные отчеты
```

## Troubleshooting

### Проблема: Docker образ не собирается
**Решение**: Проверьте наличие всех файлов и правильность Dockerfile

### Проблема: Redis порт занят
**Решение**: Измените порт в `docker-compose.test.yml`

### Проблема: Тесты падают с таймаутом
**Решение**: Увеличьте `MESSAGE_PROCESSING_DELAY` в конфигурации

### Проблема: OpenAI API недоступен
**Решение**: Установите корректные API ключи или замокайте AI вызовы
