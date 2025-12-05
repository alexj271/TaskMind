-- Добавляем расширение pgvector если не установлено
CREATE EXTENSION IF NOT EXISTS vector;

-- Добавляем поле embedding_bge_small размерностью 384 для BGE-small модели
ALTER TABLE tasks ADD COLUMN embedding_bge_small vector(384);

-- Создаем HNSW индекс для быстрого поиска по косинусному сходству
-- HNSW (Hierarchical Navigable Small World) - самый быстрый алгоритм для ANN поиска
CREATE INDEX idx_task_embedding_bge_small_hnsw ON tasks 
USING hnsw (embedding_bge_small vector_cosine_ops);