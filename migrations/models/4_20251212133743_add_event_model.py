from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "events" (
    "id" UUID NOT NULL PRIMARY KEY,
    "title" VARCHAR(200) NOT NULL,
    "description" TEXT,
    "event_type" VARCHAR(9) NOT NULL DEFAULT 'general',
    "start_date" TIMESTAMPTZ,
    "end_date" TIMESTAMPTZ,
    "location" VARCHAR(500),
    "participants" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "creator_id" UUID REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_event_title" ON "events" ("title");
CREATE INDEX IF NOT EXISTS "idx_event_type" ON "events" ("event_type");
CREATE INDEX IF NOT EXISTS "idx_event_start_date" ON "events" ("start_date");
CREATE INDEX IF NOT EXISTS "idx_event_creator" ON "events" ("creator_id");
COMMENT ON COLUMN "events"."title" IS 'Название события';
COMMENT ON COLUMN "events"."description" IS 'Описание события';
COMMENT ON COLUMN "events"."event_type" IS 'Тип события';
COMMENT ON COLUMN "events"."start_date" IS 'Дата и время начала';
COMMENT ON COLUMN "events"."end_date" IS 'Дата и время окончания';
COMMENT ON COLUMN "events"."location" IS 'Место проведения';
COMMENT ON COLUMN "events"."participants" IS 'Список участников';
COMMENT ON TABLE "events" IS 'Модель события для планирования и организации';
        ALTER TABLE "tasks" ADD "event_id" UUID;
        ALTER TABLE "tasks" ADD "completed" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "tasks" ADD "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE "tasks" ADD "priority" VARCHAR(20) NOT NULL DEFAULT 'medium';
        COMMENT ON COLUMN "tasks"."event_id" IS 'ID связанного события';
COMMENT ON COLUMN "tasks"."completed" IS 'Статус выполнения';
COMMENT ON COLUMN "tasks"."priority" IS 'Приоритет задачи';
        CREATE INDEX IF NOT EXISTS "idx_task_event" ON "tasks" ("event_id");
        CREATE INDEX IF NOT EXISTS "idx_task_priority" ON "tasks" ("priority");
        CREATE INDEX IF NOT EXISTS "idx_task_completed" ON "tasks" ("completed");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_task_completed";
        DROP INDEX IF EXISTS "idx_task_priority";
        DROP INDEX IF EXISTS "idx_task_event";
        ALTER TABLE "tasks" DROP COLUMN "event_id";
        ALTER TABLE "tasks" DROP COLUMN "completed";
        ALTER TABLE "tasks" DROP COLUMN "updated_at";
        ALTER TABLE "tasks" DROP COLUMN "priority";
        DROP TABLE IF EXISTS "events";"""


MODELS_STATE = (
    "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"
)
