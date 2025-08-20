"""
Memoria Integration Library
A simple Python client for the Memoria memory system.

Usage:
    from memoria_integration import MemoriaIntegration
    
    client = MemoriaIntegration("your-api-key")
    response = client.send_message_with_memory("user123", "chat456", "Hello!")
"""

import requests
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Memory:
    """Represents a single memory entry."""
    id: str
    content: str
    conversation_id: str
    created_at: datetime
    updated_at: datetime

@dataclass
class Insight:
    """Represents an AI-generated insight."""
    id: str
    content: str
    created_at: datetime

class MemoriaIntegration:
    """Main client for interacting with the Memoria memory system."""
    
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        """
        Initialize the Memoria client.
        
        Args:
            api_key: Your Memoria API key
            base_url: Base URL for the Memoria server
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        })
    
    def _make_request(self, method: str, endpoint: str, user_id: str = None, **kwargs) -> Dict[str, Any]:
        """Internal method to make HTTP requests."""
        headers = kwargs.pop('headers', {})
        if user_id:
            headers['X-User-Id'] = user_id
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Memoria API error: {str(e)}")
    
    def send_message_with_memory(self, user_id: str, conversation_id: str, message: str) -> Dict[str, Any]:
        """
        Send a message and get AI response with memory context.
        
        Args:
            user_id: Unique identifier for the user
            conversation_id: Unique identifier for the conversation
            message: The message content
            
        Returns:
            Dictionary containing the AI response and metadata
        """
        # Submit async task
        task_response = self._make_request(
            'POST',
            '/chat/async',
            user_id=user_id,
            json={
                'conversation_id': conversation_id,
                'message': {'content': message}
            }
        )
        
        task_id = task_response['task_id']
        
        # Poll for completion
        max_wait = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = self._make_request(
                'GET',
                f'/tasks/{task_id}',
                user_id=user_id
            )
            
            if status_response['status'] == 'completed':
                return {
                    'assistant_text': status_response['result']['assistant_text'],
                    'cited_ids': status_response['result']['cited_ids'],
                    'assistant_message_id': status_response['result']['assistant_message_id'],
                    'task_id': task_id
                }
            elif status_response['status'] == 'failed':
                raise Exception(f"Task failed: {status_response.get('error', 'Unknown error')}")
            
            time.sleep(0.5)
        
        raise TimeoutError("Request timed out")
    
    def send_message_sync(self, user_id: str, conversation_id: str, message: str) -> Dict[str, Any]:
        """
        Send a message synchronously (legacy endpoint).
        
        Args:
            user_id: Unique identifier for the user
            conversation_id: Unique identifier for the conversation
            message: The message content
            
        Returns:
            Dictionary containing the AI response
        """
        return self._make_request(
            'POST',
            '/chat',
            user_id=user_id,
            json={
                'conversation_id': conversation_id,
                'message': {'content': message}
            }
        )
    
    def get_user_memories(self, user_id: str, conversation_id: str = None) -> Dict[str, List[Memory]]:
        """
        Get all memories for a user.
        
        Args:
            user_id: Unique identifier for the user
            conversation_id: Optional conversation ID to filter memories
            
        Returns:
            Dictionary containing list of memories
        """
        params = {}
        if conversation_id:
            params['conversation_id'] = conversation_id
        
        response = self._make_request(
            'GET',
            '/memories',
            user_id=user_id,
            params=params
        )
        
        # Convert to Memory objects
        memories = []
        for mem in response.get('memories', []):
            memories.append(Memory(
                id=mem['id'],
                content=mem['content'],
                conversation_id=mem['conversation_id'],
                created_at=datetime.fromisoformat(mem['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(mem['updated_at'].replace('Z', '+00:00'))
            ))
        
        return {'memories': memories}
    
    def get_insights(self, user_id: str) -> Dict[str, List[Insight]]:
        """
        Get AI-generated insights for a user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Dictionary containing list of insights
        """
        response = self._make_request(
            'GET',
            '/insights',
            user_id=user_id
        )
        
        # Convert to Insight objects
        insights = []
        for ins in response.get('insights', []):
            insights.append(Insight(
                id=ins['id'],
                content=ins['content'],
                created_at=datetime.fromisoformat(ins['created_at'].replace('Z', '+00:00'))
            ))
        
        return {'insights': insights}
    
    def correct_memory(self, user_id: str, memory_id: str, new_text: str) -> Dict[str, Any]:
        """
        Correct an existing memory.
        
        Args:
            user_id: Unique identifier for the user
            memory_id: ID of the memory to correct
            new_text: New text to replace the memory content
            
        Returns:
            Dictionary containing task information
        """
        return self._make_request(
            'POST',
            '/correction/async',
            user_id=user_id,
            json={
                'memory_id': memory_id,
                'replacement_text': new_text
            }
        )
    
    def generate_insights(self, user_id: str, conversation_id: str = None) -> Dict[str, Any]:
        """
        Generate new insights for a user.
        
        Args:
            user_id: Unique identifier for the user
            conversation_id: Optional conversation ID to focus insights
            
        Returns:
            Dictionary containing task information
        """
        payload = {}
        if conversation_id:
            payload['conversation_id'] = conversation_id
        
        return self._make_request(
            'POST',
            '/insights/async',
            user_id=user_id,
            json=payload
        )
    
    def get_task_status(self, user_id: str, task_id: str) -> Dict[str, Any]:
        """
        Check the status of an async task.
        
        Args:
            user_id: Unique identifier for the user
            task_id: ID of the task to check
            
        Returns:
            Dictionary containing task status and result
        """
        return self._make_request(
            'GET',
            f'/tasks/{task_id}',
            user_id=user_id
        )
    
    def health_check(self) -> Dict[str, str]:
        """
        Check if the Memoria service is healthy.
        
        Returns:
            Dictionary containing health status
        """
        return self._make_request('GET', '/healthz')
    
    def wait_for_task(self, user_id: str, task_id: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Wait for an async task to complete.
        
        Args:
            user_id: Unique identifier for the user
            task_id: ID of the task to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            Dictionary containing the task result
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_task_status(user_id, task_id)
            
            if status['status'] == 'completed':
                return status['result']
            elif status['status'] == 'failed':
                raise Exception(f"Task failed: {status.get('error', 'Unknown error')}")
            
            time.sleep(0.5)
        
        raise TimeoutError("Task timed out")


# Convenience functions for quick usage
def quick_chat(api_key: str, user_id: str, conversation_id: str, message: str) -> str:
    """
    Quick one-liner to send a message and get response.
    
    Args:
        api_key: Your Memoria API key
        user_id: Unique identifier for the user
        conversation_id: Unique identifier for the conversation
        message: The message content
        
    Returns:
        The AI response text
    """
    client = MemoriaIntegration(api_key)
    response = client.send_message_with_memory(user_id, conversation_id, message)
    return response['assistant_text']


# Example usage
if __name__ == "__main__":
    # Quick test
    try:
        client = MemoriaIntegration("test123")
        
        # Test health check
        health = client.health_check()
        print(f"Health: {health}")
        
        # Test chat
        response = client.send_message_with_memory(
            user_id="demo_user",
            conversation_id="demo_chat",
            message="I love Python programming"
        )
        print(f"Response: {response['assistant_text']}")
        
        # Test getting memories
        memories = client.get_user_memories("demo_user")
        print(f"Memories: {len(memories['memories'])}")
        
    except Exception as e:
        print(f"Error: {e}")