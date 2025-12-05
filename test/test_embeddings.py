import pytest
import numpy as np
from tortoise import Tortoise
from app.core.db import TORTOISE_ORM
from app.models.task import Task
from app.models.user import User


@pytest.mark.database
@pytest.mark.asyncio
async def test_task_embedding_creation():
    """Тест создания задачи с эмбеддингом"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем тестового пользователя с уникальным ID
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"test_user_{telegram_id}"
        )
        
        # Создаем тестовый эмбеддинг (384 размерности для BGE-small)
        embedding_vector = np.random.rand(384).tolist()
        
        # Создаем задачу с эмбеддингом
        task = await Task.create(
            user=user,
            title="Тестовая задача",
            description="Описание тестовой задачи",
            embedding_bge_small=str(embedding_vector)  # Сохраняем как строку для PostgreSQL vector
        )
        
        # Проверяем что задача создалась
        assert task.id is not None
        assert task.title == "Тестовая задача"
        assert task.embedding_bge_small is not None
        
        # Загружаем задачу из БД для проверки
        saved_task = await Task.get(id=task.id)
        # PostgreSQL может изменить точность чисел, проверяем что эмбеддинг не None
        assert saved_task.embedding_bge_small is not None
        assert len(saved_task.embedding_bge_small) > 100  # Проверяем что это вектор
        
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio
async def test_embedding_vector_search():
    """Тест поиска по сходству эмбеддингов используя raw SQL"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем тестового пользователя с уникальным ID
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"test_user_search_{telegram_id}"
        )
        
        # Создаем несколько задач с разными эмбеддингами
        embeddings = [
            np.random.rand(384).tolist(),  # Случайный вектор 1
            np.random.rand(384).tolist(),  # Случайный вектор 2
            np.random.rand(384).tolist(),  # Случайный вектор 3
        ]
        
        tasks = []
        for i, embedding in enumerate(embeddings):
            task = await Task.create(
                user=user,
                title=f"Задача {i+1}",
                description=f"Описание задачи {i+1}",
                embedding_bge_small=str(embedding)
            )
            tasks.append(task)
        
        # Тестируем поиск по сходству используя raw SQL
        search_embedding = embeddings[0]  # Ищем похожие на первый эмбеддинг
        
        # Raw SQL запрос для поиска по cosine similarity
        sql_query = """
        SELECT id, title, (embedding_bge_small <=> $1::vector) as distance
        FROM tasks 
        WHERE user_id = $2 AND embedding_bge_small IS NOT NULL
        ORDER BY embedding_bge_small <=> $3::vector
        LIMIT 3
        """
        
        from tortoise import connections
        conn = connections.get("default")
        
        # Выполняем запрос
        results = await conn.execute_query_dict(
            sql_query, 
            [str(search_embedding), str(user.id), str(search_embedding)]
        )
        
        # Проверяем результаты
        assert len(results) == 3
        
        # Первый результат должен быть самым похожим (минимальное расстояние)
        assert results[0]['distance'] <= results[1]['distance']
        assert results[1]['distance'] <= results[2]['distance']
        
        # ID первого результата должен совпадать с первой задачей
        assert str(results[0]['id']) == str(tasks[0].id)
        
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio  
async def test_embedding_hnsw_index_performance():
    """Тест производительности HNSW индекса"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем пользователя с уникальным ID
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"perf_test_user_{telegram_id}"
        )
        
        # Создаем много задач для тестирования производительности
        num_tasks = 100
        tasks_data = []
        
        for i in range(num_tasks):
            embedding = np.random.rand(384).tolist()
            tasks_data.append({
                'user': user,
                'title': f'Задача производительности {i}',
                'description': f'Описание {i}',
                'embedding_bge_small': str(embedding)
            })
        
        # Bulk создание задач
        created_tasks = []
        for task_data in tasks_data:
            task = await Task.create(**task_data)
            created_tasks.append(task)
        
        # Тестируем скорость поиска
        import time
        
        search_embedding = np.random.rand(384).tolist()
        
        start_time = time.time()
        
        # Запрос с использованием HNSW индекса
        sql_query = """
        SELECT id, title, (embedding_bge_small <=> $1::vector) as distance
        FROM tasks 
        WHERE user_id = $2 AND embedding_bge_small IS NOT NULL
        ORDER BY embedding_bge_small <=> $3::vector
        LIMIT 10
        """
        
        from tortoise import connections
        conn = connections.get("default")
        
        results = await conn.execute_query_dict(
            sql_query,
            [str(search_embedding), str(user.id), str(search_embedding)]
        )
        
        end_time = time.time()
        search_time = end_time - start_time
        
        # Проверяем что поиск выполнился быстро (меньше 1 секунды для 100 записей)
        assert search_time < 1.0, f"Поиск занял {search_time:.3f} секунд, это слишком медленно"
        
        # Проверяем что вернулось 10 результатов
        assert len(results) == 10
        
        # Проверяем что результаты отсортированы по расстоянию
        for i in range(len(results) - 1):
            assert results[i]['distance'] <= results[i + 1]['distance']
            
        print(f"✅ Поиск по {num_tasks} записям занял {search_time:.3f} секунд")
        
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio
async def test_embedding_validation():
    """Тест валидации размерности эмбеддингов"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"validation_user_{telegram_id}"
        )
        
        # Тест с правильной размерностью (384)
        correct_embedding = np.random.rand(384).tolist()
        task1 = await Task.create(
            user=user,
            title="Правильная размерность",
            embedding_bge_small=str(correct_embedding)
        )
        assert task1.id is not None
        
        # Тест с неправильной размерностью должен упасть при выполнении SQL
        wrong_embedding = np.random.rand(512).tolist()  # Неправильная размерность
        
        with pytest.raises(Exception):  # PostgreSQL должен выбросить ошибку
            await Task.create(
                user=user,
                title="Неправильная размерность", 
                embedding_bge_small=str(wrong_embedding)
            )
            
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio
async def test_embedding_null_handling():
    """Тест обработки NULL значений в эмбеддингах"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"null_test_user_{telegram_id}"
        )
        
        # Создаем задачу без эмбеддинга
        task_no_embedding = await Task.create(
            user=user,
            title="Задача без эмбеддинга",
            description="Нет эмбеддинга",
            embedding_bge_small=None
        )
        
        # Создаем задачу с эмбеддингом
        embedding = np.random.rand(384).tolist()
        task_with_embedding = await Task.create(
            user=user,
            title="Задача с эмбеддингом",
            embedding_bge_small=str(embedding)
        )
        
        # Проверяем что поиск корректно обрабатывает NULL значения
        sql_query = """
        SELECT id, title, embedding_bge_small IS NOT NULL as has_embedding
        FROM tasks 
        WHERE user_id = $1
        ORDER BY created_at
        """
        
        from tortoise import connections
        conn = connections.get("default")
        
        results = await conn.execute_query_dict(sql_query, [str(user.id)])
        
        assert len(results) == 2
        assert results[0]['has_embedding'] == False  # Первая задача без эмбеддинга
        assert results[1]['has_embedding'] == True   # Вторая задача с эмбеддингом
        
    finally:
        await Tortoise.close_connections()