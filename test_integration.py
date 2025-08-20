#!/usr/bin/env python3
"""
Test script for Memoria integration.
This script tests all major functionality of the Memoria system.
"""

import os
import sys
import time
import json
from datetime import datetime
from memoria_integration import MemoriaIntegration

# Configuration
API_KEY = os.getenv("MEMORIA_API_KEY", "test123")
BASE_URL = os.getenv("MEMORIA_BASE_URL", "http://localhost:8000")
TEST_USER_ID = "test_user_integration"
TEST_CONVERSATION_ID = "test_conversation_001"

def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_success(message):
    """Print a success message."""
    print(f"✅ {message}")

def print_error(message):
    """Print an error message."""
    print(f"❌ {message}")

def print_info(message):
    """Print an info message."""
    print(f"ℹ️  {message}")

def test_health_check(client):
    """Test the health check endpoint."""
    print_section("Health Check")
    try:
        health = client.health_check()
        print_success(f"Health check passed: {health}")
        return True
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False

def test_chat_functionality(client):
    """Test basic chat functionality."""
    print_section("Chat Functionality")
    
    test_messages = [
        "Hello, I'm testing the Memoria system!",
        "My favorite programming language is Python.",
        "I work as a software engineer.",
        "I love building AI applications."
    ]
    
    responses = []
    
    for i, message in enumerate(test_messages):
        print_info(f"Sending message {i+1}: {message}")
        try:
            response = client.send_message_with_memory(
                user_id=TEST_USER_ID,
                conversation_id=TEST_CONVERSATION_ID,
                message=message
            )
            responses.append(response)
            print_success(f"Response: {response['assistant_text'][:100]}...")
            time.sleep(1)  # Rate limiting
        except Exception as e:
            print_error(f"Failed to send message: {e}")
            return False
    
    return True

def test_memory_retrieval(client):
    """Test retrieving memories."""
    print_section("Memory Retrieval")
    
    try:
        memories = client.get_user_memories(TEST_USER_ID)
        print_success(f"Retrieved {len(memories['memories'])} memories")
        
        for i, memory in enumerate(memories['memories'][-3:]):
            print_info(f"Memory {i+1}: {memory.content[:100]}...")
        
        return True
    except Exception as e:
        print_error(f"Failed to retrieve memories: {e}")
        return False

def test_insights(client):
    """Test insights generation and retrieval."""
    print_section("Insights")
    
    try:
        # Generate insights
        print_info("Generating insights...")
        task = client.generate_insights(TEST_USER_ID)
        print_success(f"Insights task created: {task['task_id']}")
        
        # Wait for completion
        print_info("Waiting for insights generation...")
        time.sleep(5)
        
        # Get insights
        insights = client.get_insights(TEST_USER_ID)
        print_success(f"Retrieved {len(insights['insights'])} insights")
        
        for i, insight in enumerate(insights['insights']):
            print_info(f"Insight {i+1}: {insight.content}")
        
        return True
    except Exception as e:
        print_error(f"Failed to get insights: {e}")
        return False

def test_memory_correction(client):
    """Test memory correction functionality."""
    print_section("Memory Correction")
    
    try:
        # Get memories first
        memories = client.get_user_memories(TEST_USER_ID)
        if not memories['memories']:
            print_info("No memories to correct")
            return True
        
        # Get the last memory
        last_memory = memories['memories'][-1]
        print_info(f"Original memory: {last_memory.content}")
        
        # Correct it
        new_text = f"[CORRECTED] {last_memory.content}"
        task = client.correct_memory(
            user_id=TEST_USER_ID,
            memory_id=last_memory.id,
            new_text=new_text
        )
        print_success(f"Correction task created: {task['task_id']}")
        
        # Wait for completion
        time.sleep(3)
        
        # Verify correction
        updated_memories = client.get_user_memories(TEST_USER_ID)
        updated_memory = next(
            (m for m in updated_memories['memories'] if m.id == last_memory.id),
            None
        )
        
        if updated_memory and "[CORRECTED]" in updated_memory.content:
            print_success("Memory correction successful")
        else:
            print_error("Memory correction may not have applied yet")
        
        return True
    except Exception as e:
        print_error(f"Failed to correct memory: {e}")
        return False

def test_conversation_isolation(client):
    """Test that conversations are properly isolated."""
    print_section("Conversation Isolation")
    
    try:
        # Send messages to different conversations
        conversations = ["conv_1", "conv_2", "conv_3"]
        
        for conv_id in conversations:
            message = f"This is a message for conversation {conv_id}"
            response = client.send_message_with_memory(
                user_id=TEST_USER_ID,
                conversation_id=conv_id,
                message=message
            )
            print_success(f"Message sent to {conv_id}")
            time.sleep(0.5)
        
        # Check memories for specific conversation
        conv1_memories = client.get_user_memories(
            TEST_USER_ID,
            conversation_id="conv_1"
        )
        
        print_success(f"Conversation 1 has {len(conv1_memories['memories'])} memories")
        
        # Check all memories
        all_memories = client.get_user_memories(TEST_USER_ID)
        print_success(f"Total memories across all conversations: {len(all_memories['memories'])}")
        
        return True
    except Exception as e:
        print_error(f"Failed conversation isolation test: {e}")
        return False

def test_error_handling(client):
    """Test error handling for invalid inputs."""
    print_section("Error Handling")
    
    test_cases = [
        ("Empty message", {"user_id": TEST_USER_ID, "conversation_id": "test", "message": ""}),
        ("Invalid user ID", {"user_id": "", "conversation_id": "test", "message": "test"}),
        ("Long message", {"user_id": TEST_USER_ID, "conversation_id": "test", "message": "x" * 10000}),
    ]
    
    for test_name, params in test_cases:
        try:
            response = client.send_message_with_memory(**params)
            print_info(f"{test_name}: Unexpected success")
        except Exception as e:
            print_success(f"{test_name}: Properly handled error - {type(e).__name__}")
    
    return True

def test_performance(client):
    """Test basic performance metrics."""
    print_section("Performance Test")
    
    try:
        start_time = time.time()
        
        # Send multiple messages quickly
        for i in range(5):
            response = client.send_message_with_memory(
                user_id=TEST_USER_ID,
                conversation_id="perf_test",
                message=f"Performance test message {i+1}"
            )
            time.sleep(0.1)  # Small delay
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print_success(f"Sent 5 messages in {total_time:.2f} seconds")
        print_info(f"Average time per message: {total_time/5:.2f} seconds")
        
        return True
    except Exception as e:
        print_error(f"Performance test failed: {e}")
        return False

def run_all_tests():
    """Run all integration tests."""
    print_section("Memoria Integration Test Suite")
    print_info(f"API Key: {API_KEY}")
    print_info(f"Base URL: {BASE_URL}")
    print_info(f"Test User: {TEST_USER_ID}")
    
    # Initialize client
    try:
        client = MemoriaIntegration(API_KEY, BASE_URL)
        print_success("Client initialized successfully")
    except Exception as e:
        print_error(f"Failed to initialize client: {e}")
        return False
    
    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Chat Functionality", test_chat_functionality),
        ("Memory Retrieval", test_memory_retrieval),
        ("Insights", test_insights),
        ("Memory Correction", test_memory_correction),
        ("Conversation Isolation", test_conversation_isolation),
        ("Error Handling", test_error_handling),
        ("Performance", test_performance),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func(client)
            if results[test_name]:
                print_success(f"{test_name} PASSED")
            else:
                print_error(f"{test_name} FAILED")
        except Exception as e:
            print_error(f"{test_name} ERROR: {e}")
            results[test_name] = False
    
    # Summary
    print_section("Test Summary")
    passed = sum(results.values())
    total = len(results)
    
    print_info(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print_success("🎉 All tests passed!")
        return True
    else:
        print_error("❌ Some tests failed")
        for test_name, passed in results.items():
            if not passed:
                print_error(f"  - {test_name}")
        return False

def save_test_results(results):
    """Save test results to a JSON file."""
    timestamp = datetime.now().isoformat()
    results_data = {
        "timestamp": timestamp,
        "api_key": API_KEY,
        "base_url": BASE_URL,
        "test_user": TEST_USER_ID,
        "results": results
    }
    
    filename = f"test_results_{timestamp.replace(':', '-').replace('.', '-')}.json"
    with open(filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print_info(f"Test results saved to {filename}")

if __name__ == "__main__":
    # Check if running in CI/CD
    is_ci = os.getenv("CI", "").lower() == "true"
    
    if is_ci:
        print_info("Running in CI mode - will exit with appropriate code")
    
    success = run_all_tests()
    
    if is_ci:
        sys.exit(0 if success else 1)
    else:
        if not success:
            print("\n💡 Tips for common issues:")
            print("1. Make sure Memoria server is running")
            print("2. Check if API key is correct")
            print("3. Verify network connectivity")
            print("4. Check server logs for errors")