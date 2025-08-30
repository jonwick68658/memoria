# Memoria Quick Start - 5 Minutes to Memory

Get persistent memory for your LLM app in **5 minutes** with this copy-paste guide.

## 🚀 30-Second Test

### 1. Start Memoria (if not running)
```bash
# Using Docker (fastest)
docker run -p 8000:8000 -e GATEWAY_API_KEY=test123 memoria/memoria:latest

# OR using source
python -m app.main
```

### 2. Test Connection
```bash
curl -X POST http://localhost:8000/chat/async \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: test123" \
  -H "X-User-Id: demo_user" \
  -d '{"conversation_id": "demo_1", "message": {"content": "I love Python"}}'
```

**Expected:** `{"task_id": "...", "status": "submitted"}`

### 3. Check Result
```bash
# Replace TASK_ID with the task_id from above
curl http://localhost:8000/tasks/TASK_ID \
  -H "X-Api-Key: test123"
```

---

## 🎯 Integration in Your App

### Python (Copy-Paste)
```python
import requests
import time

class MemoriaMemory:
    def __init__(self, api_key="test123", base_url="http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
    
    def chat_with_memory(self, user_id, conversation_id, message):
        """One-liner: send message, get response with memory"""
        # Submit
        task = requests.post(
            f"{self.base_url}/chat/async",
            headers={"X-Api-Key": self.api_key, "X-User-Id": user_id, "Content-Type": "application/json"},
            json={"conversation_id": conversation_id, "message": {"content": message}}
        ).json()
        
        # Wait for result
        while True:
            status = requests.get(
                f"{self.base_url}/tasks/{task['task_id']}",
                headers={"X-Api-Key": self.api_key}
            ).json()
            if status["status"] == "completed":
                return status["result"]["assistant_text"]
            time.sleep(0.5)

# Usage
memory = MemoriaMemory()
response = memory.chat_with_memory("user123", "chat_456", "I love Python")
print(response)  # AI response with memory context
```

### JavaScript (Copy-Paste)
```javascript
const axios = require('axios');

class MemoriaMemory {
    constructor(apiKey = "test123", baseUrl = "http://localhost:8000") {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
    }

    async chatWithMemory(userId, conversationId, message) {
        // Submit
        const { data: task } = await axios.post(
            `${this.baseUrl}/chat/async`,
            { conversation_id: conversationId, message: { content: message } },
            { headers: { "X-Api-Key": this.apiKey, "X-User-Id": userId, "Content-Type": "application/json" } }
        );

        // Wait for result
        while (true) {
            const { data: status } = await axios.get(
                `${this.baseUrl}/tasks/${task.task_id}`,
                { headers: { "X-Api-Key": this.apiKey } }
            );
            if (status.status === "completed") return status.result.assistant_text;
            await new Promise(r => setTimeout(r, 500));
        }
    }
}

// Usage
const memory = new MemoriaMemory();
memory.chatWithMemory("user123", "chat_456", "I love Python")
    .then(response => console.log(response));
```

---

## 🏗️ Add to Your Existing LLM App

### Before (No Memory)
```python
def chat_with_llm(user_message):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": user_message}]
    )
    return response.choices[0].message.content
```

### After (With Memory)
```python
def chat_with_llm(user_id, conversation_id, user_message):
    memory = MemoriaMemory()
    
    # Get AI response WITH memory context
    response = memory.chat_with_memory(user_id, conversation_id, user_message)
    
    return response
```

---

## 📊 Real Example: Chatbot

### Complete Working Example
```python
from flask import Flask, request, jsonify
from memoria_memory import MemoriaMemory  # Use the class above

app = Flask(__name__)
memory = MemoriaMemory()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data['user_id']
    conversation_id = data['conversation_id']
    message = data['message']
    
    # Get AI response with memory
    response = memory.chat_with_memory(user_id, conversation_id, message)
    
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)
```

**Test it:**
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "conversation_id": "support_123", "message": "I need help with Python"}'
```

---

## 🔍 Check What's Stored

### View Memories
```bash
# Get all memories for a user
curl http://localhost:8000/memories \
  -H "X-Api-Key: test123" \
  -H "X-User-Id: alice"
```

### View Insights
```bash
# Get AI-generated insights
curl http://localhost:8000/insights \
  -H "X-Api-Key: test123" \
  -H "X-User-Id: alice"
```

---

## ⚡ Production Checklist

- [ ] Change `test123` to your real API key
- [ ] Update `localhost:8000` to your server URL
- [ ] Add error handling
- [ ] Add webhook support (optional)
- [ ] Monitor response times
- [ ] **Configure custom embedding provider** (see EXAMPLES.md)

---

## 🆘 Troubleshooting

### "Connection refused"
```bash
# Check if Memoria is running
curl http://localhost:8000/healthz
```

### "Unauthorized"
- Check your `X-Api-Key` header
- Verify API key matches your `.env` file

### "User not found"
- Any string works for `X-User-Id`
- Use your existing user IDs

---

## 🎉 You're Done!

Your LLM app now has **persistent memory** that:
- Remembers user preferences
- Maintains conversation context
- Learns from interactions
- Provides personalized responses

**Next:** Check [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for advanced features.