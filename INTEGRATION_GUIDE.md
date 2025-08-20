# Memoria Integration Guide - Step by Step

This guide provides **copy-paste ready** code for integrating Memoria into your existing LLM application.

## 🎯 Integration Goal
Add persistent memory to your LLM app in **under 10 minutes** using our REST API.

## 🔧 Prerequisites
- Your LLM app can make HTTP requests
- You have a user ID system (any string works)
- You have conversation/thread IDs (any string works)

---

## Method 1: REST API Integration (Any Language)

### Step 1: Test Your Setup (30 seconds)
```bash
# Replace with your actual API key and user ID
curl -X POST http://localhost:8000/chat/async \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-gateway-key" \
  -H "X-User-Id: user123" \
  -d '{
    "conversation_id": "test_conv_1",
    "message": {"content": "I love Python programming"}
  }'
```

**Expected Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "message": "Chat processing started in background"
}
```

### Step 2: Check Task Status
```bash
curl http://localhost:8000/tasks/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-Api-Key: your-gateway-key"
```

**Expected Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "assistant_text": "That's great! Python is excellent for AI development...",
    "cited_ids": ["mem_123", "mem_456"],
    "assistant_message_id": "msg_789"
  }
}
```

---

## Method 2: Python Integration (Complete Example)

### Step 1: Install Dependencies
```bash
pip install requests
```

### Step 2: Copy-Paste Integration Code
```python
import requests
import time
import json

class MemoriaIntegration:
    def __init__(self, api_key, base_url="http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def send_message_with_memory(self, user_id, conversation_id, user_message):
        """
        Send a message and get AI response with memory context
        
        Args:
            user_id: Your user identifier (string)
            conversation_id: Your conversation identifier (string)  
            user_message: The user's message (string)
            
        Returns:
            dict: Contains 'assistant_text' and 'cited_memories'
        """
        # Submit async task
        task_response = self._submit_chat(user_id, conversation_id, user_message)
        task_id = task_response["task_id"]
        
        # Poll for completion (production: use webhooks)
        while True:
            status = self._get_task_status(task_id)
            if status["status"] == "completed":
                return {
                    "assistant_text": status["result"]["assistant_text"],
                    "cited_memories": status["result"]["cited_ids"]
                }
            elif status["status"] == "failed":
                raise Exception(f"Task failed: {status.get('error', 'Unknown error')}")
            time.sleep(0.5)  # Poll every 500ms
    
    def _submit_chat(self, user_id, conversation_id, message):
        """Submit chat for async processing"""
        response = requests.post(
            f"{self.base_url}/chat/async",
            headers={**self.headers, "X-User-Id": user_id},
            json={
                "conversation_id": conversation_id,
                "message": {"content": message}
            }
        )
        response.raise_for_status()
        return response.json()
    
    def _get_task_status(self, task_id):
        """Check task status"""
        response = requests.get(
            f"{self.base_url}/tasks/{task_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_user_memories(self, user_id):
        """Get all memories for a user"""
        response = requests.get(
            f"{self.base_url}/memories",
            headers={**self.headers, "X-User-Id": user_id}
        )
        response.raise_for_status()
        return response.json()
    
    def correct_memory(self, user_id, memory_id, new_text):
        """Correct an existing memory"""
        response = requests.post(
            f"{self.base_url}/correction/async",
            headers={**self.headers, "X-User-Id": user_id},
            json={
                "memory_id": memory_id,
                "replacement_text": new_text
            }
        )
        response.raise_for_status()
        return response.json()

# Usage Example
if __name__ == "__main__":
    # Initialize
    memoria = MemoriaIntegration("your-gateway-key")
    
    # Example conversation
    user_id = "user_123"
    conversation_id = "conv_456"
    
    # Send message
    response = memoria.send_message_with_memory(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message="I love Python programming and machine learning"
    )
    
    print("AI Response:", response["assistant_text"])
    print("Used memories:", response["cited_memories"])
    
    # Get all memories for this user
    memories = memoria.get_user_memories(user_id)
    print("Total memories:", len(memories["memories"]))
```

---

## Method 3: JavaScript/Node.js Integration

### Step 1: Install Dependencies
```bash
npm install axios
```

### Step 2: Copy-Paste Integration Code
```javascript
const axios = require('axios');

class MemoriaIntegration {
    constructor(apiKey, baseUrl = 'http://localhost:8000') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'X-Api-Key': apiKey,
            'Content-Type': 'application/json'
        };
    }

    async sendMessageWithMemory(userId, conversationId, userMessage) {
        // Submit async task
        const taskResponse = await this.submitChat(userId, conversationId, userMessage);
        const taskId = taskResponse.task_id;

        // Poll for completion
        while (true) {
            const status = await this.getTaskStatus(taskId);
            if (status.status === 'completed') {
                return {
                    assistantText: status.result.assistant_text,
                    citedMemories: status.result.cited_ids
                };
            } else if (status.status === 'failed') {
                throw new Error(`Task failed: ${status.error || 'Unknown error'}`);
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }

    async submitChat(userId, conversationId, message) {
        const response = await axios.post(
            `${this.baseUrl}/chat/async`,
            {
                conversation_id: conversationId,
                message: { content: message }
            },
            { headers: { ...this.headers, 'X-User-Id': userId } }
        );
        return response.data;
    }

    async getTaskStatus(taskId) {
        const response = await axios.get(
            `${this.baseUrl}/tasks/${taskId}`,
            { headers: this.headers }
        );
        return response.data;
    }

    async getUserMemories(userId) {
        const response = await axios.get(
            `${this.baseUrl}/memories`,
            { headers: { ...this.headers, 'X-User-Id': userId } }
        );
        return response.data;
    }

    async correctMemory(userId, memoryId, newText) {
        const response = await axios.post(
            `${this.baseUrl}/correction/async`,
            {
                memory_id: memoryId,
                replacement_text: newText
            },
            { headers: { ...this.headers, 'X-User-Id': userId } }
        );
        return response.data;
    }
}

// Usage Example
async function example() {
    const memoria = new MemoriaIntegration('your-gateway-key');
    
    const userId = 'user_123';
    const conversationId = 'conv_456';
    
    try {
        const response = await memoria.sendMessageWithMemory(
            userId,
            conversationId,
            'I love Python programming and machine learning'
        );
        
        console.log('AI Response:', response.assistantText);
        console.log('Used memories:', response.citedMemories);
        
        const memories = await memoria.getUserMemories(userId);
        console.log('Total memories:', memories.memories.length);
        
    } catch (error) {
        console.error('Error:', error.message);
    }
}

// Run example
example();
```

---

## Method 4: Integration with Popular LLM Frameworks

### LangChain Integration
```python
from langchain_core.messages import HumanMessage, AIMessage
from memoria_integration import MemoriaIntegration  # Use the class above

class MemoriaLangChainMemory:
    def __init__(self, api_key, user_id, conversation_id):
        self.memoria = MemoriaIntegration(api_key)
        self.user_id = user_id
        self.conversation_id = conversation_id
    
    def add_message(self, message):
        """Add a message to memory"""
        if isinstance(message, HumanMessage):
            response = self.memoria.send_message_with_memory(
                self.user_id,
                self.conversation_id,
                message.content
            )
            return AIMessage(content=response["assistant_text"])
    
    def get_memories(self):
        """Get all memories for context"""
        return self.memoria.get_user_memories(self.user_id)
```

### OpenAI API Integration
```python
import openai
from memoria_integration import MemoriaIntegration

class MemoriaOpenAI:
    def __init__(self, openai_key, memoria_key):
        openai.api_key = openai_key
        self.memoria = MemoriaIntegration(memoria_key)
    
    def chat_with_memory(self, user_id, conversation_id, user_message):
        # Get memories for context
        memories = self.memoria.get_user_memories(user_id)
        memory_context = "\n".join([m["content"] for m in memories["memories"]])
        
        # Build prompt with memory
        prompt = f"""Based on the following memories about this user:
{memory_context}

User: {user_message}
Assistant:"""
        
        # Call OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Store interaction in Memoria
        self.memoria.send_message_with_memory(
            user_id, 
            conversation_id, 
            user_message
        )
        
        return response.choices[0].message.content
```

---

## 🚀 Quick Integration Checklist

- [ ] **Test API connectivity**: Run the curl command above
- [ ] **Choose integration method**: REST, Python, or JavaScript
- [ ] **Copy integration code**: Use the provided classes
- [ ] **Test with real data**: Use your actual user/conversation IDs
- [ ] **Add error handling**: Handle network errors gracefully
- [ ] **Monitor performance**: Check response times

---

## 📊 Production Considerations

### Error Handling
```python
try:
    response = memoria.send_message_with_memory(user_id, conv_id, message)
except requests.exceptions.ConnectionError:
    # Fallback to memory-less response
    return get_llm_response_without_memory(message)
except Exception as e:
    # Log error and continue
    logger.error(f"Memoria error: {e}")
    return get_llm_response_without_memory(message)
```

### Webhook Integration (Advanced)
Instead of polling, you can set up webhooks to receive task completion notifications.

### Rate Limiting
The API has built-in rate limiting. Handle 429 responses:
```python
if response.status_code == 429:
    time.sleep(1)  # Retry after delay
```

---

## 🎯 Next Steps

1. **Test the integration** with your existing app
2. **Add memory correction** for user feedback
3. **Implement memory browsing** for users
4. **Add memory insights** for analytics
5. **Scale with multiple workers** as needed

**Need help?** Check the [troubleshooting section](#troubleshooting) or open an issue on GitHub.