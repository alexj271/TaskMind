# Тестирование эмбеддингов

Этот файл содержит тесты для проверки работы с pgvector эмбеддингами в PostgreSQL.

## Перед запуском тестов

1. **Установите расширение pgvector в PostgreSQL:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

2. **Примените миграцию для добавления поля эмбеддинга:**
```bash
psql -h localhost -U your_user -d taskmind -f migrations/manual_add_embedding.sql
```

3. **Установите numpy для тестов:**
```bash
pip install numpy
```

## Запуск тестов

```bash
# Все тесты эмбеддингов
pytest test/test_embeddings.py -v

# Конкретный тест
pytest test/test_embeddings.py::test_embedding_vector_search -v

# С детальным выводом
pytest test/test_embeddings.py -v -s
```

## Что тестируется

1. **test_task_embedding_creation** - Создание задач с эмбеддингами
2. **test_embedding_vector_search** - Поиск по сходству через cosine distance
3. **test_embedding_hnsw_index_performance** - Производительность HNSW индекса
4. **test_embedding_validation** - Валидация размерности векторов
5. **test_embedding_null_handling** - Обработка NULL значений

## Требования

- PostgreSQL с расширением pgvector
- Поле embedding_bge_small типа vector(384) в таблице tasks
- HNSW индекс для быстрого поиска
- numpy для генерации тестовых векторов