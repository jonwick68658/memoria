# Memoria Examples & Use Cases

Real-world examples showing how to integrate Memoria into different types of applications.

## 🎯 Quick Examples by Use Case

### 1. Customer Support Bot
```python
from memoria_integration import MemoriaIntegration

class SupportBot:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def handle_support_ticket(self, user_id, ticket_id, user_message):
        """Handle support ticket with full memory context"""
        
        # Get AI response with memory of previous interactions
        response = self.memoria.send_message_with_memory(
            user_id=user_id,
            conversation_id=f"ticket_{ticket_id}",
            message=user_message
        )
        
        # Check if user has previous issues
        memories = self.memoria.get_user_memories(user_id)
        previous_issues = [m for m in memories["memories"] if "issue" in m["content"].lower()]
        
        if previous_issues:
            print(f"User has {len(previous_issues)} previous issues")
        
        return response["assistant_text"]

# Usage
bot = SupportBot("your-api-key")
response = bot.handle_support_ticket("user_123", "789", "My internet is down again")
```

### 2. Personal Assistant
```python
class PersonalAssistant:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def remember_preference(self, user_id, preference):
        """Store user preferences as memories"""
        return self.memoria.send_message_with_memory(
            user_id=user_id,
            conversation_id="preferences",
            message=f"Remember: {preference}"
        )
    
    def get_context(self, user_id):
        """Get all user context for personalization"""
        memories = self.memoria.get_user_memories(user_id)
        insights = self.memoria.get_insights(user_id)
        
        return {
            "memories": memories["memories"],
            "insights": insights["insights"]
        }

# Usage
assistant = PersonalAssistant("your-api-key")

# Store preferences
assistant.remember_preference("alice", "I prefer morning meetings")
assistant.remember_preference("alice", "My favorite programming language is Python")

# Get personalized context
context = assistant.get_context("alice")
```

### 3. Educational Tutor
```python
class TutorBot:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def teach_concept(self, student_id, concept, explanation):
        """Teach a concept and track student progress"""
        
        # Store what was taught
        self.memoria.send_message_with_memory(
            user_id=student_id,
            conversation_id="learning_session",
            message=f"Learned: {concept} - {explanation}"
        )
    
    def check_understanding(self, student_id, question):
        """Check understanding with context of what was taught"""
        
        response = self.memoria.send_message_with_memory(
            user_id=student_id,
            conversation_id="learning_session",
            message=f"Question: {question}"
        )
        
        return response["assistant_text"]

# Usage
tutor = TutorBot("your-api-key")
tutor.teach_concept("student_456", "Python lists", "Lists are ordered collections")
understanding = tutor.check_understanding("student_456", "Can you explain lists again?")
```

---

## 🏗️ Framework Integrations

### LangChain Integration
```python
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_openai import ChatOpenAI
from memoria_integration import MemoriaIntegration

class MemoriaLangChainMemory(ConversationBufferMemory):
    def __init__(self, api_key, user_id, conversation_id):
        super().__init__()
        self.memoria = MemoriaIntegration(api_key)
        self.user_id = user_id
        self.conversation_id = conversation_id
    
    def save_context(self, inputs, outputs):
        """Save to both LangChain and Memoria"""
        super().save_context(inputs, outputs)
        
        # Also save to Memoria for long-term storage
        user_message = inputs.get("input", "")
        ai_response = outputs.get("response", "")
        
        self.memoria.send_message_with_memory(
            user_id=self.user_id,
            conversation_id=self.conversation_id,
            message=user_message
        )
    
    def load_memory_variables(self, inputs):
        """Load from Memoria for long-term context"""
        # Get memories from Memoria
        memories = self.memoria.get_user_memories(self.user_id)
        
        # Format for LangChain
        history = "\n".join([m["content"] for m in memories["memories"][-10:]])
        
        return {"history": history}

# Usage
llm = ChatOpenAI()
memory = MemoriaLangChainMemory("api-key", "user123", "chat456")
chain = ConversationChain(llm=llm, memory=memory)

response = chain.predict(input="I love Python")
```

### FastAPI Integration
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from memoria_integration import MemoriaIntegration

app = FastAPI()
memoria = MemoriaIntegration("your-api-key")

class ChatRequest(BaseModel):
    user_id: str
    conversation_id: str
    message: str

@app.post("/chat")
async def chat_with_memory(request: ChatRequest):
    """Chat endpoint with memory integration"""
    try:
        response = memoria.send_message_with_memory(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            message=request.message
        )
        return {"response": response["assistant_text"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/memories")
async def get_user_memories(user_id: str):
    """Get all memories for a user"""
    memories = memoria.get_user_memories(user_id)
    return memories

# Run with: uvicorn app:app --reload
```

### Discord Bot Integration
```python
import discord
from memoria_integration import MemoriaIntegration

class MemoriaDiscordBot(discord.Client):
    def __init__(self, api_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.memoria = MemoriaIntegration(api_key)
    
    async def on_message(self, message):
        if message.author == self.user:
            return
        
        # Use Discord user ID and channel ID
        user_id = str(message.author.id)
        conversation_id = str(message.channel.id)
        
        # Get AI response with memory
        response = self.memoria.send_message_with_memory(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message.content
        )
        
        await message.channel.send(response["assistant_text"])

# Usage
intents = discord.Intents.default()
intents.message_content = True
bot = MemoriaDiscordBot("your-api-key", intents=intents)
bot.run("your-discord-token")
```

### 4. Custom Embedding Provider
```python
# src/memoria/embeddings.py (Current structure)
class EmbeddingProvider:
    def get_embedding(self, text: str) -> List[float]:
        # Default: OpenAI
        return openai.Embedding.create(input=text, model="text-embedding-ada-002")["data"][0]["embedding"]

# Developer's Custom Provider (What they'd implement)
class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_path: str):
        self.model = SentenceTransformer(model_path)
    
    def get_embedding(self, text: str) -> List[float]:
        return self.model.encode([text])[0].tolist()
```


## 📊 Analytics & Business Intelligence

### User Behavior Analysis
```python
class UserAnalytics:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def analyze_user_journey(self, user_id):
        """Analyze complete user journey"""
        memories = self.memoria.get_user_memories(user_id)
        
        # Extract patterns
        topics = {}
        for memory in memories["memories"]:
            words = memory["content"].lower().split()
            for word in words:
                if len(word) > 3:  # Filter short words
                    topics[word] = topics.get(word, 0) + 1
        
        # Get insights
        insights = self.memoria.get_insights(user_id)
        
        return {
            "total_interactions": len(memories["memories"]),
            "top_topics": sorted(topics.items(), key=lambda x: x[1], reverse=True)[:10],
            "ai_insights": insights["insights"]
        }

# Usage
analytics = UserAnalytics("api-key")
journey = analytics.analyze_user_journey("user_123")
```

### A/B Testing with Memory
```python
class ABTesting:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def test_response_style(self, user_id, test_group, message):
        """Test different response styles with memory"""
        
        # Add test context
        test_message = f"[Group {test_group}] {message}"
        
        response = self.memoria.send_message_with_memory(
            user_id=user_id,
            conversation_id=f"ab_test_{test_group}",
            message=test_message
        )
        
        return {
            "test_group": test_group,
            "response": response["assistant_text"],
            "memory_context": response["cited_memories"]
        }

# Usage
ab_test = ABTesting("api-key")
result_a = ab_test.test_response_style("user_123", "A", "How should I learn Python?")
result_b = ab_test.test_response_style("user_123", "B", "How should I learn Python?")
```

---

## 🔒 Security & Privacy Examples

### Data Isolation
```python
class MultiTenantApp:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def handle_tenant_request(self, tenant_id, user_id, conversation_id, message):
        """Ensure tenant data isolation"""
        
        # Use tenant-scoped user IDs
        tenant_user_id = f"{tenant_id}_{user_id}"
        tenant_conversation_id = f"{tenant_id}_{conversation_id}"
        
        response = self.memoria.send_message_with_memory(
            user_id=tenant_user_id,
            conversation_id=tenant_conversation_id,
            message=message
        )
        
        return response

# Usage
app = MultiTenantApp("api-key")
response = app.handle_tenant_request("acme_corp", "user_123", "chat_456", "Hello")
```

### GDPR Compliance
```python
class GDPRCompliantApp:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def export_user_data(self, user_id):
        """Export all user data for GDPR requests"""
        memories = self.memoria.get_user_memories(user_id)
        insights = self.memoria.get_insights(user_id)
        
        return {
            "user_id": user_id,
            "memories": memories["memories"],
            "insights": insights["insights"],
            "export_timestamp": datetime.now().isoformat()
        }
    
    def delete_user_data(self, user_id):
        """Delete all user data (requires admin endpoint)"""
        # This would require a DELETE endpoint
        # For now, use correction to anonymize
        memories = self.memoria.get_user_memories(user_id)
        for memory in memories["memories"]:
            self.memoria.correct_memory(
                user_id=user_id,
                memory_id=memory["id"],
                new_text="[REDACTED]"
            )

# Usage
gdpr = GDPRCompliantApp("api-key")
user_data = gdpr.export_user_data("user_123")
```

---

## 🎯 Advanced Patterns

### Memory-Driven Personalization
```python
class PersonalizedRecommender:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def recommend_content(self, user_id, content_type):
        """Recommend content based on memory"""
        
        # Get user memories
        memories = self.memoria.get_user_memories(user_id)
        
        # Extract interests
        interests = []
        for memory in memories["memories"]:
            if "like" in memory["content"].lower() or "love" in memory["content"].lower():
                interests.append(memory["content"])
        
        # Get AI recommendation
        prompt = f"Based on these interests: {interests}, recommend {content_type}"
        
        response = self.memoria.send_message_with_memory(
            user_id=user_id,
            conversation_id="recommendations",
            message=prompt
        )
        
        return response["assistant_text"]

# Usage
recommender = PersonalizedRecommender("api-key")
recommendation = recommender.recommend_content("user_123", "Python tutorials")
```

### Conversation Summarization
```python
class ConversationSummarizer:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def summarize_conversation(self, user_id, conversation_id):
        """Summarize an entire conversation"""
        
        # Get all memories for this conversation
        memories = self.memoria.get_user_memories(user_id)
        conversation_memories = [
            m for m in memories["memories"] 
            if m["conversation_id"] == conversation_id
        ]
        
        # Create summary prompt
        conversation_text = "\n".join([m["content"] for m in conversation_memories])
        summary_prompt = f"Summarize this conversation:\n{conversation_text}"
        
        # Get summary
        response = self.memoria.send_message_with_memory(
            user_id=user_id,
            conversation_id=f"{conversation_id}_summary",
            message=summary_prompt
        )
        
        return response["assistant_text"]

# Usage
summarizer = ConversationSummarizer("api-key")
summary = summarizer.summarize_conversation("user_123", "chat_456")
```

---

## 🚀 Getting Started with Examples

### 1. Choose Your Use Case
- **Customer Support**: Use the SupportBot example
- **Personal Assistant**: Use the PersonalAssistant example
- **Education**: Use the TutorBot example
- **Analytics**: Use the UserAnalytics example

### 2. Copy the Code
Each example is ready to use - just:
1. Replace `"your-api-key"` with your actual API key
2. Replace `"user_123"` with your user IDs
3. Run the code

### 3. Test with Real Data
```python
# Quick test
memoria = MemoriaIntegration("your-api-key")
response = memoria.send_message_with_memory("test_user", "test_chat", "Hello, I love Python")
print(response["assistant_text"])
```

---

## 📈 Performance Tips

### Batch Processing
```python
class BatchProcessor:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    def process_multiple_users(self, user_messages):
        """Process multiple users efficiently"""
        results = []
        for user_id, conversation_id, message in user_messages:
            try:
                response = self.memoria.send_message_with_memory(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message=message
                )
                results.append({"success": True, "response": response})
            except Exception as e:
                results.append({"success": False, "error": str(e)})
        
        return results

# Usage
processor = BatchProcessor("api-key")
messages = [
    ("user1", "chat1", "Hello"),
    ("user2", "chat2", "Hi there"),
    ("user3", "chat3", "Good morning")
]
results = processor.process_multiple_users(messages)
```

### Caching Strategy
```python
from functools import lru_cache
import hashlib

class CachedMemoria:
    def __init__(self, api_key):
        self.memoria = MemoriaIntegration(api_key)
    
    @lru_cache(maxsize=1000)
    def get_cached_memories(self, user_id):
        """Cache user memories"""
        return self.memoria.get_user_memories(user_id)
    
    def clear_cache(self, user_id):
        """Clear cache for specific user"""
        self.get_cached_memories.cache_clear()
```

---

## 🆘 Troubleshooting Examples

### Common Issues and Solutions

**Issue: Slow responses**
```python
# Solution: Use async processing and polling
import asyncio

async def handle_chat_async(user_id, conversation_id, message):
    task = memoria.submit_chat(user_id, conversation_id, message)
    
    # Non-blocking wait
    for _ in range(60):  # 30 seconds max
        status = memoria.get_task_status(task["task_id"])
        if status["status"] == "completed":
            return status["result"]
        await asyncio.sleep(0.5)
    
    raise TimeoutError("Request timed out")
```

**Issue: Memory not found**
```python
# Solution: Check if memories exist before processing
def safe_get_memories(user_id):
    try:
        memories = memoria.get_user_memories(user_id)
        if not memories["memories"]:
            return {"memories": [], "message": "No memories found"}
        return memories
    except Exception as e:
        return {"memories": [], "error": str(e)}
```

---

## 🎉 Next Steps

1. **Pick an example** that matches your use case
2. **Run the code** with your API key
3. **Customize** for your specific needs
4. **Scale up** to production

**Need more examples?** Check the [integration guide](INTEGRATION_GUIDE.md) or open an issue on GitHub.