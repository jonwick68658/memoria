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
        
    @task(3)
    def store_memory(self):
        """Test memory storage endpoint"""
        message = {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "message": f"Test message about topic {random.choice(['AI', 'ML', 'Data', 'Python', 'FastAPI'])}",
            "timestamp": time.time()
        }
        
        with self.client.post(
            "/api/memory/store",
            json=message,
            catch_response=True,
            name="/api/memory/store"
        ) as response:
            if response.status_code == 202:
                response.success()
                # Store task ID for later checking
                task_data = response.json()
                if "task_id" in task_data:
                    self.check_task_status(task_data["task_id"])
            else:
                response.failure(f"Failed to store memory: {response.status_code}")
    
    @task(2)
    def get_memories(self):
        """Test memory retrieval endpoint"""
        with self.client.get(
            f"/api/memory/{self.user_id}",
            catch_response=True,
            name="/api/memory/[user_id]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get memories: {response.status_code}")
    
    @task(1)
    def get_memory_summary(self):
        """Test memory summary endpoint"""
        with self.client.get(
            f"/api/memory/{self.user_id}/summary",
            catch_response=True,
            name="/api/memory/[user_id]/summary"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get summary: {response.status_code}")
    
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
    
    def check_task_status(self, task_id: str):
        """Check the status of an async task"""
        # This would check task completion in a real scenario
        pass

class MemoryStressTest(HttpUser):
    """High-load testing for memory operations"""
    
    wait_time = between(0.1, 0.5)  # Very fast requests
    
    def on_start(self):
        self.user_id = f"stress_user_{random.randint(1000, 9999)}"
    
    @task(5)
    def rapid_memory_storage(self):
        """Rapid memory storage for stress testing"""
        messages = [
            {"user_id": self.user_id, "conversation_id": f"conv_{i}", "message": f"Stress test message {i}"}
            for i in range(10)
        ]
        
        for message in messages:
            self.client.post(
                "/api/memory/store",
                json=message,
                name="/api/memory/store (stress)"
            )

class BatchMemoryTest(HttpUser):
    """Test batch memory operations"""
    
    wait_time = between(2, 5)
    
    def on_start(self):
        self.user_id = f"batch_user_{random.randint(1000, 9999)}"
    
    @task(1)
    def batch_memory_store(self):
        """Store multiple memories in batch"""
        batch_data = {
            "user_id": self.user_id,
            "conversation_id": f"batch_conv_{random.randint(1000, 9999)}",
            "messages": [
                {"content": f"Message {i} about AI", "timestamp": time.time() + i}
                for i in range(50)
            ]
        }
        
        with self.client.post(
            "/api/memory/batch/store",
            json=batch_data,
            catch_response=True,
            name="/api/memory/batch/store"
        ) as response:
            if response.status_code == 202:
                response.success()
            else:
                response.failure(f"Batch store failed: {response.status_code}")

class SyncComparisonTest(HttpUser):
    """Test for comparing sync vs async performance"""
    
    wait_time = between(1, 2)
    
    def on_start(self):
        self.user_id = f"sync_user_{random.randint(1000, 9999)}"
    
    @task(1)
    def sync_memory_store(self):
        """Test synchronous memory storage (for comparison)"""
        message = {
            "user_id": self.user_id,
            "conversation_id": f"sync_conv_{random.randint(1000, 9999)}",
            "message": "Sync test message",
            "timestamp": time.time()
        }
        
        with self.client.post(
            "/api/memory/store/sync",
            json=message,
            catch_response=True,
            name="/api/memory/store/sync"
        ) as response:
            if response.status_code == 200:
                response_time = response.elapsed.total_seconds() * 1000
                response.success()
                # Log sync response time for comparison
                events.request.fire(
                    request_type="POST",
                    name="/api/memory/store/sync (response_time)",
                    response_time=response_time,
                    response_length=len(response.content)
                )
            else:
                response.failure(f"Sync store failed: {response.status_code}")

# Custom events for performance tracking
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    print("Starting Memoria async system load test...")
    print("Test scenarios:")
    print("- Normal user behavior (store, retrieve, summarize)")
    print("- Stress testing (rapid requests)")
    print("- Batch operations")
    print("- Sync vs async comparison")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    print("\nLoad test completed!")
    print("Check the Locust web interface for detailed results")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Log successful requests"""
    if exception is not None:
        return
    if "store" in name and response_time < 500:
        print(f"✅ Fast async response: {response_time:.2f}ms")

@events.request_failure.add_listener
def on_request_failure(request_type, name, response_time, exception, **kwargs):
    """Log failed requests"""
    print(f"❌ Request failed: {name} - {exception}")

# Performance benchmarks
class PerformanceBenchmark:
    """Static performance benchmarks"""
    
    @staticmethod
    def get_expected_performance():
        """Return expected performance metrics"""
        return {
            "async_store_response_time": {
                "target": "< 200ms",
                "acceptable": "< 500ms",
                "current": "Testing..."
            },
            "sync_store_response_time": {
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