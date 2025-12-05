from app.models.task import Task
from typing import Optional, List
from datetime import datetime
import uuid

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

class TaskRepository:
    def __init__(self):
        # Инициализируем модель BGE-small для генерации эмбеддингов
        self._embedding_model = None
    
    def _get_embedding_model(self):
        """Ленивая инициализация модели эмбеддингов"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers не установлен. Установите с помощью: pip install sentence-transformers")
        
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer("BAAI/bge-small")
        return self._embedding_model
    
    def _generate_embedding(self, text: str) -> list:
        """Генерирует эмбеддинг для текста"""
        model = self._get_embedding_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    
    async def create(self, user_id: uuid.UUID, *, title: str, description: str | None, scheduled_at: datetime | None, reminder_at: datetime | None) -> Task:
        # Генерируем эмбеддинг на основе заголовка и описания
        text_for_embedding = title
        if description:
            text_for_embedding += " " + description
        embedding = self._generate_embedding(text_for_embedding)
        
        # Сохраняем эмбеддинг в компактном JSON формате
        import json
        embedding_json = json.dumps(embedding, separators=(',', ':'))
        
        return await Task.create(
            user_id=user_id, 
            title=title, 
            description=description, 
            embedding_bge_small=embedding_json,  # Сохраняем как JSON строку для PostgreSQL vector
            scheduled_at=scheduled_at, 
            reminder_at=reminder_at
        )

    async def get(self, task_id: uuid.UUID) -> Optional[Task]:
        return await Task.filter(id=task_id).first()

    async def list_for_user(self, user_id: uuid.UUID) -> List[Task]:
        return await Task.filter(user_id=user_id).all()

    async def delete(self, task_id: uuid.UUID) -> int:
        return await Task.filter(id=task_id).delete()

    async def delete_all_for_user(self, user_id: uuid.UUID) -> int:
        """Удаляет все задачи пользователя (для тестов и демо)"""
        return await Task.filter(user_id=user_id).delete()

    async def update_reminder(self, task_id: uuid.UUID, reminder_at: datetime | None) -> int:
        return await Task.filter(id=task_id).update(reminder_at=reminder_at)
    
    async def search_by_similarity(self, user_id: uuid.UUID, query: str, limit: int = 10) -> List[Task]:
        """Поиск задач по семантическому сходству с запросом"""
        # Генерируем эмбеддинг для поискового запроса
        query_embedding = self._generate_embedding(query)
        
        # Преобразуем эмбеддинг в JSON формат для PostgreSQL
        import json
        embedding_json = json.dumps(query_embedding, separators=(',', ':'))
        
        # Выполняем поиск по сходству с использованием pgvector
        from tortoise import connections
        conn = connections.get("default")
        
        sql_query = """
        SELECT id, title, description, scheduled_at, reminder_at, created_at, user_id,
               (embedding_bge_small <=> $1::vector) as distance
        FROM tasks 
        WHERE user_id = $2 AND embedding_bge_small IS NOT NULL
        ORDER BY embedding_bge_small <=> $3::vector
        LIMIT $4
        """
        
        results = await conn.execute_query_dict(
            sql_query, 
            [embedding_json, str(user_id), embedding_json, limit]
        )
        
        # Преобразуем результаты в объекты Task
        tasks = []
        for row in results:
            task = Task(
                id=row['id'],
                title=row['title'],
                description=row['description'],
                scheduled_at=row['scheduled_at'],
                reminder_at=row['reminder_at'],
                created_at=row['created_at'],
                user_id=row['user_id']
            )
            # Добавляем расстояние как дополнительное свойство
            task.similarity_distance = row['distance']
            tasks.append(task)
        
        return tasks
