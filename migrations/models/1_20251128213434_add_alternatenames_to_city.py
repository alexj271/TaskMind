from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "message_history" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "update_id" INT NOT NULL UNIQUE,
    "user_id" INT NOT NULL,
    "chat_id" INT NOT NULL,
    "message_text" TEXT NOT NULL,
    "user_name" VARCHAR(255),
    "timestamp" TIMESTAMPTZ NOT NULL,
    "message_type" VARCHAR(50),
    "ai_response" TEXT,
    "function_called" VARCHAR(255),
    "summary" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_message_history_user_id" ON "message_history" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_message_history_timestamp" ON "message_history" ("timestamp");
COMMENT ON COLUMN "message_history"."update_id" IS 'ID обновления от Telegram';
COMMENT ON COLUMN "message_history"."user_id" IS 'ID пользователя Telegram';
COMMENT ON COLUMN "message_history"."chat_id" IS 'ID чата Telegram';
COMMENT ON COLUMN "message_history"."message_text" IS 'Текст сообщения';
COMMENT ON COLUMN "message_history"."user_name" IS 'Имя пользователя';
COMMENT ON COLUMN "message_history"."timestamp" IS 'Время получения сообщения';
COMMENT ON COLUMN "message_history"."message_type" IS 'Тип сообщения (task/chat/timezone)';
COMMENT ON COLUMN "message_history"."ai_response" IS 'Ответ от AI';
COMMENT ON COLUMN "message_history"."function_called" IS 'Вызванная функция AI';
COMMENT ON COLUMN "message_history"."summary" IS 'Саммари сообщения';
COMMENT ON TABLE "message_history" IS 'История сообщений от пользователей';
        ALTER TABLE "cities" ADD "alternatenames" TEXT;
        CREATE INDEX IF NOT EXISTS "idx_city_alternatenames" ON "cities" ("alternatenames");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_city_alternatenames";
        ALTER TABLE "cities" DROP COLUMN "alternatenames";
        DROP TABLE IF EXISTS "message_history";"""


MODELS_STATE = (
    "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"
    "l5/h/Vn0lU"
)
