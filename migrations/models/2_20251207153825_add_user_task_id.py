from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    # Сначала добавляем поле как nullable
    await db.execute_query("""ALTER TABLE "tasks" ADD "user_task_id" INT;""")
    
    # Заполняем user_task_id для существующих записей
    # Используем ROW_NUMBER() для генерации последовательных номеров для каждого пользователя
    await db.execute_query("""
        WITH numbered_tasks AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at) as task_num
            FROM tasks
            WHERE user_task_id IS NULL
        )
        UPDATE tasks 
        SET user_task_id = nt.task_num
        FROM numbered_tasks nt
        WHERE tasks.id = nt.id;
    """)
    
    # Теперь делаем поле NOT NULL
    await db.execute_query("""ALTER TABLE "tasks" ALTER COLUMN "user_task_id" SET NOT NULL;""")
    
    return """
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_tasks_user_id_26e287" ON "tasks" ("user_id", "user_task_id");
        CREATE INDEX IF NOT EXISTS "idx_task_created" ON "tasks" ("created_at");
        CREATE INDEX IF NOT EXISTS "idx_task_user" ON "tasks" ("user_id");
        CREATE INDEX IF NOT EXISTS "idx_user_task_id" ON "tasks" ("user_id", "user_task_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_user_task_id";
        DROP INDEX IF EXISTS "idx_task_user";
        DROP INDEX IF EXISTS "idx_task_created";
        DROP INDEX IF EXISTS "uid_tasks_user_id_26e287";
        ALTER TABLE "tasks" DROP COLUMN "user_task_id";"""


MODELS_STATE = (
    "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"
)
