"""
Load testing script for Memoria async system using Locust
Tests the performance improvements of async vs sync processing
"""

import time
import random
import json
from locust import HttpUser, task, between, events
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging

setup_logging("INFO")

class MemoriaUser(HttpUser):
    """Simulates a user interacting with the Memoria system"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Initialize user session"""
        self.user_id = f"user_{random.randint(1000, 9999)}"
        self.conversation_id = f"conv_{random.randint(1000, 9999)}"
        self.api_key = "test-key"  # Assume test key for load testing
        
    @task(3)
    def chat_async(self):
        """Test async chat endpoint"""
        headers = {
            "X-Api-Key": self.api_key,
            "X-User-Id": self.user_id
        }
        message = {
            "conversation_id": self.conversation_id,
            "message": {"content": f"Test message about topic {random.choice(['AI', 'ML', 'Data', 'Python', 'FastAPI'])}"}
        }
        
        with self.client.post(
            "/chat/async",
            json=message,
            headers=headers,
            catch_response=True,
            name="/chat/async"
        ) as response:
            if response.status_code == 200:
                response.success()
                task_data = response.json()
                if "task_id" in task_data:
                    self.poll_task_status(task_data["task_id"], headers)
            else:
                response.failure(f"Failed to submit chat: {response.status_code}")
    
    @task(2)
    def get_memories(self):
        """Test memory retrieval endpoint"""
        headers = {
            "X-Api-Key": self.api_key,
            "X-User-Id": self.user_id
        }
        with self.client.get(
            "/memories",
            headers=headers,
            catch_response=True,
            name="/memories"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get memories: {response.status_code}")
    
    @task(1)
    def get_insights(self):
        """Test insights endpoint"""
        headers = {
            "X-Api-Key": self.api_key,
            "X-User-Id": self.user_id
        }
        with self.client.get(
            "/insights",
            headers=headers,
            catch_response=True,
            name="/insights"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get insights: {response.status_code}")
    
    @task(1)
    def get_memory_insights(self):
        """Test memory insights endpoint"""
        with self.client.get(
            f"/api/memory/{self.user_id}/insights",
            catch_response=True,
            name="/api/memory/[user_id]/insights"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get insights: {response.status_code}")
    
    def poll_task_status(self, task_id: str, headers: dict):
        """Poll task status until completion"""
        max_polls = 10
        for _ in range(max_polls):
            with self.client.get(
                f"/tasks/{task_id}",
                headers=headers,
                catch_response=True,
                name="/tasks/{task_id}"
            ) as response:
                if response.status_code == 200:
                    status_data = response.json()
                    if status_data["status"] == "completed":
                        response.success()
                        break
                    elif status_data["status"] == "failed":
                        response.failure("Task failed")
                        break
                else:
                    response.failure(f"Failed to poll task: {response.status_code}")
            time.sleep(0.5)
        else:
            self.environment.events.request_failure.fire(
                request_type="GET",
                name="/tasks/{task_id}",
                response_time=0,
                response_length=0,
                exception=Exception("Task poll timeout")
            )

class MemoryStressTest(HttpUser):
    """High-load testing for memory operations"""
    
    wait_time = between(0.1, 0.5)  # Very fast requests
    
    def on_start(self):
        self.user_id = f"stress_user_{random.randint(1000, 9999)}"
        self.api_key = "test-key"
    
    @task(5)
    def rapid_chat_submission(self):
        """Rapid chat submission for stress testing"""
        headers = {
            "X-Api-Key": self.api_key,
            "X-User-Id": self.user_id
        }
        messages = [
            {
                "conversation_id": f"conv_{i}",
                "message": {"content": f"Stress test message {i}"}
            }
            for i in range(10)
        ]
        
        for message in messages:
            self.client.post(
                "/chat/async",
                json=message,
                headers=headers,
                name="/chat/async (stress)"
            )

class BatchMemoryTest(HttpUser):
    """Test batch memory operations"""
    
    wait_time = between(2, 5)
    
    def on_start(self):
        self.user_id = f"batch_user_{random.randint(1000, 9999)}"
        self.api_key = "test-key"
    
    @task(1)
    def batch_chat_submission(self):
        """Submit multiple chats in sequence (simulating batch)"""
        headers = {
            "X-Api-Key": self.api_key,
            "X-User-Id": self.user_id
        }
        conversation_id = f"batch_conv_{random.randint(1000, 9999)}"
        messages = [
            {"conversation_id": conversation_id, "message": {"content": f"Batch message {i} about AI"}}
            for i in range(5)  # Smaller batch for load test
        ]
        
        for message in messages:
            with self.client.post(
                "/chat/async",
                json=message,
                headers=headers,
                catch_response=True,
                name="/chat/async (batch)"
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Batch chat failed: {response.status_code}")

class SyncComparisonTest(HttpUser):
    """Test for comparing sync vs async performance"""
    
    wait_time = between(1, 2)
    
    def on_start(self):
        self.user_id = f"sync_user_{random.randint(1000, 9999)}"
        self.api_key = "test-key"
    
    @task(1)
    def sync_chat(self):
        """Test synchronous chat (for comparison)"""
        headers = {
            "X-Api-Key": self.api_key,
            "X-User-Id": self.user_id
        }
        conversation_id = f"sync_conv_{random.randint(1000, 9999)}"
        message = {
            "conversation_id": conversation_id,
            "message": {"content": "Sync test message"}
        }
        
        with self.client.post(
            "/chat",
            json=message,
            headers=headers,
            catch_response=True,
            name="/chat (sync)"
        ) as response:
            if response.status_code == 200:
                response_time = response.elapsed.total_seconds() * 1000
                response.success()
                # Log sync response time for comparison
                events.request.fire(
                    request_type="POST",
                    name="/chat (sync response_time)",
                    response_time=response_time,
                    response_length=len(response.content)
                )
            else:
                response.failure(f"Sync chat failed: {response.status_code}")

# Custom events for performance tracking
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    print("Starting Memoria async system load test...")
    print("Test scenarios:")
    print("- Normal user behavior (chat async, poll tasks, get memories/insights)")
    print("- Stress testing (rapid chat submissions)")
    print("- Batch chat submissions")
    print("- Sync vs async comparison")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    print("\nLoad test completed!")
    print("Check the Locust web interface for detailed results")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Log requests"""
    if exception is not None:
        print(f"❌ Request failed: {name} - {exception}")
    elif "store" in name and response_time < 500:
        print(f"✅ Fast async response: {response_time:.2f}ms")

# Performance benchmarks
class PerformanceBenchmark:
    """Static performance benchmarks"""
    
    @staticmethod
    def get_expected_performance():
        """Return expected performance metrics"""
        return {
            "async_chat_response_time": {
                "target": "< 200ms (task submission)",
                "acceptable": "< 500ms",
                "current": "Testing..."
            },
            "sync_chat_response_time": {
                "target": "2-6 seconds (baseline)",
                "acceptable": "< 10 seconds",
                "current": "Testing..."
            },
            "throughput": {
                "target": "1000+ requests/minute",
                "acceptable": "500+ requests/minute",
                "current": "Testing..."
            },
            "concurrent_users": {
                "target": "1000+ users",
                "acceptable": "500+ users",
                "current": "Testing..."
            }
        }

# Test configuration
def get_test_config():
    """Get test configuration based on environment"""
    return {
        "host": "http://localhost:8000",
        "users": {
            "normal": 50,
            "stress": 100,
            "batch": 20,
            "sync": 10
        },
        "spawn_rate": 10,
        "run_time": "5m"
    }

if __name__ == "__main__":
    # Run specific test scenarios
    import sys
    
    if len(sys.argv) > 1:
        scenario = sys.argv[1]
        
        if scenario == "normal":
            # Normal user behavior test
            print("Running normal user behavior test...")
            # This would be run via: locust -f tests/load_test.py --host http://localhost:8000
        elif scenario == "stress":
            # Stress test
            print("Running stress test...")
        elif scenario == "benchmark":
            # Performance benchmark
            print("Running performance benchmark...")
            benchmark = PerformanceBenchmark()
            print(json.dumps(benchmark.get_expected_performance(), indent=2))
    else:
        print("Usage: python tests/load_test.py [normal|stress|benchmark]")
        print("Or run: locust -f tests/load_test.py --host http://localhost:8000")