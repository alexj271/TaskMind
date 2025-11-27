from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" UUID NOT NULL PRIMARY KEY,
    "telegram_id" BIGINT NOT NULL UNIQUE,
    "chat_id" BIGINT,
    "username" VARCHAR(100),
    "timezone" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "tasks" (
    "id" UUID NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "description" TEXT,
    "scheduled_at" TIMESTAMPTZ,
    "reminder_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "dialog_sessions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "summary" TEXT,
    "last_messages" JSONB NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "cities" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(200) NOT NULL,
    "timezone" VARCHAR(50),
    "country_code" VARCHAR(2),
    "population" INT,
    "latitude" DOUBLE PRECISION NOT NULL,
    "longitude" DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_city_name" ON "cities" ("name");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztmv1v2jgYx/8VlJ9aaVd1AUrvdDqJAt24tTDxcjdtmiI3McFq4mSJc4Wr+N/PNglxnJ"
    "cBbQ7Y8ksLj/0k9scvz9fmeVZsx4CWfzH1oaf8VntWMLAh/ZCwv6kpwHVjKzMQ8GDxigGt"
    "wS3gwSce0Ak1zoDlQ2oyoK97yCXIwdSKA8tiRkenFRE2Y1OA0bcAasQxIZnzhnz5Ss0IG3"
    "AB/eir+6jNELSMRDuRwd7N7RpZutw2nfa7t7wme92DpjtWYOO4trskcwdvqgcBMi6YDysz"
    "IYYeINAQusFaGXY3Mq1bTA3EC+CmqUZsMOAMBBaDofw+C7DOGNT4m9ifxh/KDnh0BzO0CB"
    "PG4nm17lXcZ25V2Ks679ujs/rVOe+l4xPT44WciLLijoCAtSvnGoMk0IKmB2wti+gNMvuY"
    "ZDOVHCW4tNHlYI1w7ceQNoj+++VXVa3XW+pl/eq62Wi1mteX17Qub1K6qFUA/qb/rj+YsJ"
    "46dA2sVwYzMOYxY30OyM58Bae92IbkNmijKjHbeLmeMly2EfHPKbqdOfCy2Yo+ElzaoeOE"
    "a4OFZkFskjn9+vbysgDcX+0R3xForfMkvkFYpK7LkiQJsuG/Dt6JpOhzkiSb24Bs5nNspj"
    "DqHmTd1QBJg+zSEoYsZ8knPCWcRuh6EX3YZ3/9H+jSPhhDbC3DsS2gO+nf98aT9v1H1hPb"
    "979ZHFF70mMlKrcuJevZlTQSm4fU/u5P3tfY19rn4aAnh8JNvclnhbUJBMTRsPOkAUOIM5"
    "E1ArNiAmT2KEROZngA+uMT8AwtUSIsJOA/+hm7feh2+2EELcDBpoc5FGAT+ojjHOBVNGsj"
    "azzQMQEf+j597gshdBGwHHO8ftaJ0WDzxFGdvJmTLrJVW7YADEzeavZu9iZxcmSo9mjS5K"
    "v2zcysVPtpq3ZErB3jdOiwV5A+RBxJRGm12dwiTNNauXGalyUDtdiyFMoJXOQIc8ntRFRP"
    "URzufZokQnBE7ey+/ek8EYbvhoN3UXWBcudueCPB9fU5NAJrLx0k+76CEjou4EckfKJup5"
    "SPOJgetBkob4+xlFyroTzwUFankx/odCLfg2ReMuULLMHlNVXWQRfkd0RV6jyXBJimd+t4"
    "EJn4A1xyhn3aDoD1LCklXZ0fLbXUWYWaPfC0kevitKDdo52CZK0u2+NOu9tTVvln4DJPPc"
    "nTYMbxJ3VczD8HGbyqJh5TqxPRSZ+I/MC2gbfcRcgLLpWIzxTxFvCJZtNFQldkxl3On+Ph"
    "IBttylECPMW0518MpJM3NQv55GtZO6Ywex8CZBGE/Qv2wpImMCNSPAoycGmmswfIoxC4xp"
    "6SLelZSbaDSrbUJWklxX+Ica2keCXFfzIp3kFkqWQocG4vFN46IgiWr7eflbgn60ayCnDh"
    "epHiD31iHb7QaNuWWpQWEE0lhfvRlvIvq52EfG5ux7ZpHeGUOIKMGfVto9W4rl81NrkcG0"
    "tRCkeUrpGv23dN3XhR2sbhf8fYKm9DLcjbUKu8jbLyNpwAE29JIRk7oZT9ThKnus20zJ+U"
    "MkvXcYP41/0td8Wk02klvb1wfxSP3ASRIGsG3loOyCEnOkncZszrOLfGAi7d4fTmrlf7OO"
    "p1+uN+eKbeSHxeyEzUgNaCaNRr38kkHWzugVL0+qlZ7pD6VKbWbEMP6XMlQ22GJYV6E8R1"
    "juZ+t5KF35eF/0DPz4we+XFYcDlRcVhGkgtbGjtADKufJsBSsqLpGwnEGVd0+bffgsuh7r"
    "1LiyavdsN90PCy+g91nwBe"
)
