# Memoria API Reference

Complete REST API documentation with examples and response schemas.

## Base URL
```
http://localhost:8000
```

## Authentication
All endpoints require:
- `X-Api-Key` header: Your gateway API key
- `X-User-Id` header: User identifier (any string)

---

## Core Endpoints

### POST /chat/async
Submit a chat message for async processing with memory context.

**Request:**
```json
{
  "conversation_id": "string",
  "message": {
    "content": "string"
  }
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "message": "Chat processing started in background"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/chat/async \
  -H "X-Api-Key: your-key" \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "chat_456",
    "message": {"content": "I love Python programming"}
  }'
```

---

### GET /tasks/{task_id}
Check the status of an async task.

**Response:**
```json
{
  "task_id": "string",
  "status": "pending|completed|failed",
  "result": {
    "assistant_text": "string",
    "cited_ids": ["mem_123", "mem_456"],
    "assistant_message_id": "msg_789"
  },
  "error": "string (if failed)",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Example:**
```bash
curl http://localhost:8000/tasks/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-Api-Key: your-key"
```

---

### POST /correction/async
Submit a memory correction for async processing.

**Request:**
```json
{
  "memory_id": "string",
  "replacement_text": "string"
}
```

**Response:**
```json
{
  "task_id": "string",
  "status": "submitted",
  "message": "Correction processing started"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/correction/async \
  -H "X-Api-Key: your-key" \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "memory_id": "mem_123",
    "replacement_text": "I love Python and JavaScript"
  }'
```

---

### POST /insights/async
Generate insights from user memories.

**Request:**
```json
{
  "conversation_id": "string (optional)"
}
```

**Response:**
```json
{
  "task_id": "string",
  "status": "submitted",
  "message": "Insight generation started"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/insights/async \
  -H "X-Api-Key: your-key" \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Legacy Endpoints (Synchronous)

### POST /chat
**⚠️ Deprecated**: Use `/chat/async` for production.

**Request:** Same as `/chat/async`

**Response:**
```json
{
  "assistant_text": "string",
  "cited_ids": ["mem_123"],
  "assistant_message_id": "msg_456"
}
```

---

### GET /memories
List memories for a user (synchronous, lightweight).

**Query Parameters:**
- `conversation_id` (optional): Filter by conversation

**Response:**
```json
{
  "memories": [
    {
      "id": "mem_123",
      "content": "I love Python programming",
      "conversation_id": "chat_456",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z"
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/memories?conversation_id=chat_456 \
  -H "X-Api-Key: your-key" \
  -H "X-User-Id: user123"
```

---

### GET /insights
Get insights for a user (synchronous, lightweight).

**Response:**
```json
{
  "insights": [
    {
      "id": "ins_123",
      "content": "User is interested in Python and machine learning",
      "created_at": "2024-01-01T12:00:00Z"
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/insights \
  -H "X-Api-Key: your-key" \
  -H "X-User-Id: user123"
```

---

## Utility Endpoints

### GET /tasks
List active tasks for a user.

**Response:**
```json
{
  "message": "Task listing requires additional monitoring setup",
  "active_tasks": []
}
```

---

### GET /healthz
Basic health check.

**Response:**
```json
{
  "status": "ok",
  "db": "ok"
}
```

---

### GET /healthz/detailed
Detailed health check including Celery workers.

**Response:**
```json
{
  "status": "ok",
  "db": "ok",
  "celery": {
    "workers": 2,
    "active_tasks": 5
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request format"
}
```

### 401 Unauthorized
```json
{
  "detail": "Unauthorized"
}
```

### 429 Too Many Requests
```json
{
  "detail": "Rate limit exceeded"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limits

- **Default**: 10 requests per second per API key
- **Configurable**: Set `RATE_LIMIT_RPS` in environment
- **Headers**: Check `Retry-After` on 429 responses

---

## Webhook Support (Advanced)

Configure webhooks to receive task completion notifications:

**Webhook Payload:**
```json
{
  "task_id": "string",
  "status": "completed|failed",
  "result": {...},
  "error": "string (if failed)",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Configuration:**
Set `WEBHOOK_URL` in environment variables.

---

## SDK Examples

### Python
```python
import requests

class MemoriaClient:
    def __init__(self, api_key, base_url="http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
    
    def chat_async(self, user_id, conversation_id, message):
        return requests.post(
            f"{self.base_url}/chat/async",
            headers={"X-Api-Key": self.api_key, "X-User-Id": user_id},
            json={"conversation_id": conversation_id, "message": {"content": message}}
        ).json()
    
    def get_task_status(self, task_id):
        return requests.get(
            f"{self.base_url}/tasks/{task_id}",
            headers={"X-Api-Key": self.api_key}
        ).json()
```

### JavaScript
```javascript
const axios = require('axios');

class MemoriaClient {
    constructor(apiKey, baseUrl = 'http://localhost:8000') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
    }

    async chatAsync(userId, conversationId, message) {
        const response = await axios.post(
            `${this.baseUrl}/chat/async`,
            { conversation_id: conversationId, message: { content: message } },
            { headers: { 'X-Api-Key': this.apiKey, 'X-User-Id': userId } }
        );
        return response.data;
    }

    async getTaskStatus(taskId) {
        const response = await axios.get(
            `${this.baseUrl}/tasks/${taskId}`,
            { headers: { 'X-Api-Key': this.apiKey } }
        );
        return response.data;
    }
}
```

---

## Testing Your Integration

### Test Script
```bash
#!/bin/bash
API_KEY="test123"
USER_ID="test_user"
CONV_ID="test_conv"

# Test chat
echo "Testing chat..."
TASK_ID=$(curl -s -X POST http://localhost:8000/chat/async \
  -H "X-Api-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\": \"$CONV_ID\", \"message\": {\"content\": \"Hello, I love Python\"}}" | jq -r .task_id)

echo "Task ID: $TASK_ID"

# Check status
echo "Checking status..."
curl -s http://localhost:8000/tasks/$TASK_ID \
  -H "X-Api-Key: $API_KEY" | jq .

# List memories
echo "Listing memories..."
curl -s http://localhost:8000/memories \
  -H "X-Api-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" | jq .
```

Save as `test_api.sh` and run: `chmod +x test_api.sh && ./test_api.sh`