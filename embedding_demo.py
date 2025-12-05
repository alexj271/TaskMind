"""
Пример использования системы эмбеддингов TaskMind

Этот файл демонстрирует как использовать эмбеддинги для семантического поиска задач.
Запускать этот файл можно только при наличии установленного sentence-transformers.
"""
import asyncio
import uuid
from tortoise import Tortoise
from app.core.db import TORTOISE_ORM
from app.models.user import User
from app.repositories.task_repository import TaskRepository


async def embedding_demo():
    """Демонстрация работы с эмбеддингами"""
    # Инициализируем базу данных
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        print("🚀 Демонстрация системы эмбеддингов TaskMind")
        print("=" * 50)
        
        # Создаем тестового пользователя
        user = await User.create(
            telegram_id=12345,
            chat_id=12345,
            username="demo_user"
        )
        print(f"✅ Создан пользователь: {user.username}")
        
        # Создаем репозиторий
        repo = TaskRepository()
        
        # Создаем несколько тестовых задач
        tasks_data = [
            ("Купить молоко", "Сходить в магазин за молоком"),
            ("Встреча с клиентом", "Обсудить новый проект в офисе"),
            ("Приготовить ужин", "Сделать пасту с томатным соусом"),
            ("Позвонить маме", "Узнать как дела, поздравить с праздником"),
            ("Заплатить за интернет", "Оплатить счет до конца месяца"),
            ("Купить продукты", "Хлеб, масло, яйца в супермаркете"),
        ]
        
        print(f"\n📝 Создаем {len(tasks_data)} тестовых задач...")
        created_tasks = []
        
        for title, description in tasks_data:
            task = await repo.create(
                user_id=user.id,
                title=title,
                description=description,
                scheduled_at=None,
                reminder_at=None
            )
            created_tasks.append(task)
            print(f"   ✅ {title}")
        
        # Демонстрируем семантический поиск
        print(f"\n🔍 Тестируем семантический поиск:")
        print("-" * 30)
        
        search_queries = [
            "еда и готовка",
            "покупки в магазине", 
            "работа и бизнес",
            "семья и родственники"
        ]
        
        for query in search_queries:
            print(f"\nЗапрос: '{query}'")
            results = await repo.search_by_similarity(user.id, query, limit=3)
            
            if results:
                for i, task in enumerate(results, 1):
                    distance = getattr(task, 'similarity_distance', 'N/A')
                    print(f"  {i}. {task.title} (расстояние: {distance:.3f})")
            else:
                print("  Результаты не найдены")
        
        print(f"\n✨ Демонстрация завершена успешно!")
        print("🎯 Эмбеддинги позволяют находить семантически похожие задачи")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("💡 Убедитесь что установлен sentence-transformers:")
        print("   pip install sentence-transformers")
        
    finally:
        # Очистка (удаляем тестовые данные)
        try:
            if 'user' in locals():
                await repo.delete_all_for_user(user.id)
                await user.delete()
                print(f"\n🧹 Тестовые данные удалены")
        except:
            pass
        
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(embedding_demo())