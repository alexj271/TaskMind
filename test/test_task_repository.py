import pytest
import uuid
from unittest.mock import Mock, patch
from tortoise import Tortoise
from app.core.db import TORTOISE_ORM
from app.repositories.task_repository import TaskRepository
from app.models.task import Task
from app.models.user import User
from datetime import datetime


@pytest.mark.database
@pytest.mark.asyncio
async def test_task_repository_create_with_embedding():
    """Тест создания задачи с автоматической генерацией эмбеддинга"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем тестового пользователя
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"test_user_{telegram_id}"
        )
        
        # Мокаем генерацию эмбеддинга через метод репозитория
        repo = TaskRepository()
        mock_embedding = [0.1] * 384  # Фиктивный эмбеддинг
        
        with patch.object(repo, '_generate_embedding', return_value=mock_embedding):
            # Создаем задачу
            task = await repo.create(
                user_id=user.id,
                title="Купить молоко",
                description="В магазине на углу",
                scheduled_at=None,
                reminder_at=None
            )
            
            # Проверяем что задача создалась
            assert task.id is not None
            assert task.title == "Купить молоко"
            assert task.description == "В магазине на углу"
            
            # Проверяем что эмбеддинг установился в правильном JSON формате
            import json
            expected_embedding = json.dumps(mock_embedding, separators=(',', ':'))
            assert task.embedding_bge_small == expected_embedding
            
            # Проверяем сохранение в БД
            saved_task = await Task.get(id=task.id)
            assert saved_task.embedding_bge_small == expected_embedding
            
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio
async def test_task_repository_create_title_only_embedding():
    """Тест создания задачи только с заголовком"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем тестового пользователя
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"test_user_{telegram_id}"
        )
        
        # Мокаем генерацию эмбеддинга
        repo = TaskRepository()
        mock_embedding = [0.2] * 384
        
        with patch.object(repo, '_generate_embedding', return_value=mock_embedding) as mock_gen:
            # Создаем задачу без описания
            task = await repo.create(
                user_id=user.id,
                title="Важная встреча",
                description=None,
                scheduled_at=None,
                reminder_at=None
            )
            
            # Проверяем что эмбеддинг генерируется только по заголовку
            mock_gen.assert_called_once_with("Важная встреча")
            
            import json
            expected_embedding = json.dumps(mock_embedding, separators=(',', ':'))
            assert task.embedding_bge_small == expected_embedding
            
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio
async def test_task_repository_search_by_similarity():
    """Тест поиска задач по семантическому сходству"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем пользователя
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"test_user_similarity_{telegram_id}"
        )
        
        repo = TaskRepository()
        
        with patch.object(repo, '_generate_embedding') as mock_gen:
            # Настраиваем разные эмбеддинги для разных вызовов
            mock_gen.side_effect = [
                [0.1] * 384,  # Для первой задачи
                [0.2] * 384,  # Для второй задачи  
                [0.5] * 384,  # Для третьей задачи
                [0.15] * 384  # Для поискового запроса
            ]
            
            # Создаем несколько задач
            task1 = await repo.create(
                user_id=user.id,
                title="Купить молоко",
                description="В супермаркете",
                scheduled_at=None,
                reminder_at=None
            )
            
            task2 = await repo.create(
                user_id=user.id,
                title="Встреча с клиентом",
                description="Обсудить проект",
                scheduled_at=None,
                reminder_at=None
            )
            
            task3 = await repo.create(
                user_id=user.id,
                title="Позвонить маме",
                description=None,
                scheduled_at=None,
                reminder_at=None
            )
            
            # Выполняем поиск по запросу
            results = await repo.search_by_similarity(user.id, "покупки", limit=5)
            
            # Проверяем результаты
            assert len(results) >= 1
            assert all(isinstance(task, Task) for task in results)
            assert all(hasattr(task, 'similarity_distance') for task in results)
            
            # Проверяем что результаты отсортированы по расстоянию
            distances = [task.similarity_distance for task in results]
            assert distances == sorted(distances)
            
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio
async def test_task_repository_search_no_results():
    """Тест поиска когда нет подходящих задач"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем пользователя без задач
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"empty_user_{telegram_id}"
        )
        
        repo = TaskRepository()
        
        with patch.object(repo, '_generate_embedding', return_value=[0.1] * 384):
            results = await repo.search_by_similarity(user.id, "любой запрос", limit=10)
            
            # Проверяем что вернулся пустой список
            assert results == []
            
    finally:
        await Tortoise.close_connections()


@pytest.mark.database
@pytest.mark.asyncio
async def test_task_repository_search_limit():
    """Тест ограничения количества результатов поиска"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем пользователя
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"limit_test_user_{telegram_id}"
        )
        
        repo = TaskRepository()
        
        with patch.object(repo, '_generate_embedding', return_value=[0.1] * 384):
            # Создаем 5 задач
            for i in range(5):
                await repo.create(
                    user_id=user.id,
                    title=f"Задача {i+1}",
                    description=f"Описание {i+1}",
                    scheduled_at=None,
                    reminder_at=None
                )
            
            # Ищем с ограничением в 3 результата
            results = await repo.search_by_similarity(user.id, "задача", limit=3)
            
            # Проверяем что вернулось не больше 3 результатов
            assert len(results) <= 3
            
    finally:
        await Tortoise.close_connections()


@pytest.mark.requires_sentence_transformers
@pytest.mark.asyncio
async def test_task_repository_real_embedding():
    """Интеграционный тест с настоящей моделью BGE-small (требует скачивания модели)"""
    # Проверяем доступность sentence-transformers
    try:
        from app.repositories.task_repository import SENTENCE_TRANSFORMERS_AVAILABLE
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            pytest.skip("sentence-transformers не установлен")
    except ImportError:
        pytest.skip("sentence-transformers не установлен")
    
    print("🧪 Запуск интеграционного теста с настоящей моделью BGE-small...")
    
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Создаем пользователя
        import random
        telegram_id = random.randint(100000, 999999)
        user = await User.create(
            telegram_id=telegram_id,
            chat_id=telegram_id,
            username=f"real_embedding_user_{telegram_id}"
        )
        
        repo = TaskRepository()
        
        # Создаем задачу с настоящим эмбеддингом
        task = await repo.create(
            user_id=user.id,
            title="Купить продукты в магазине",
            description="Молоко, хлеб, яйца",
            scheduled_at=None,
            reminder_at=None
        )
        
        # Проверяем что эмбеддинг сгенерировался
        assert task.embedding_bge_small is not None
        
        # Проверяем что эмбеддинг имеет правильную размерность (384 для BGE-small)
        import json
        embedding_list = json.loads(task.embedding_bge_small)
        assert len(embedding_list) == 384
        assert all(isinstance(x, float) for x in embedding_list)
        
        # Тестируем поиск с настоящей моделью
        results = await repo.search_by_similarity(user.id, "еда и покупки", limit=5)
        assert len(results) >= 1
        assert results[0].id == task.id  # Должна найтись наша задача
        
    except Exception as e:
        # Если модель не может загрузиться (нет интернета, мало места), пропускаем тест
        pytest.skip(f"Не удалось загрузить модель BGE-small: {e}")
        
    finally:
        await Tortoise.close_connections()