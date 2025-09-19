-- Ensure idempotency uniqueness for memories to support ON CONFLICT(user_id, idempotency_key)
CREATE UNIQUE INDEX IF NOT EXISTS uq_memories_user_idem
  ON memories(user_id, idempotency_key);