#!/usr/bin/env python3
"""
Comprehensive performance testing for Memoria async system
Tests sync vs async performance, throughput, and scalability
"""

import asyncio
import aiohttp
import requests
import time
import json
import statistics
import concurrent.futures
from pathlib import Path
import logging
from typing import List, Dict, Any, Tuple
import argparse
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PerformanceTester:
    """Comprehensive performance testing for Memoria async system"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "sync": {},
            "async": {},
            "comparison": {},
            "timestamp": datetime.now().isoformat()
        }
        
    def test_sync_performance(self, num_requests: int = 100) -> Dict[str, Any]:
        """Test synchronous memory storage performance"""
        logger.info(f"Testing sync performance with {num_requests} requests...")
        
        response_times = []
        errors = 0
        
        start_time = time.time()
        
        for i in range(num_requests):
            try:
                request_start = time.time()
                
                response = requests.post(
                    f"{self.base_url}/api/memory/store/sync",
                    json={
                        "user_id": f"sync_user_{i}",
                        "conversation_id": f"sync_conv_{i}",
                        "message": f"Sync test message {i}",
                        "timestamp": time.time()
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    response_time = time.time() - request_start
                    response_times.append(response_time * 1000)  # Convert to ms
                else:
                    errors += 1
                    
            except Exception as e:
                logger.error(f"Sync request failed: {e}")
                errors += 1
        
        total_time = time.time() - start_time
        
        sync_results = {
            "total_requests": num_requests,
            "successful_requests": len(response_times),
            "failed_requests": errors,
            "total_time_seconds": total_time,
            "requests_per_second": len(response_times) / total_time if total_time > 0 else 0,
            "response_times_ms": {
                "min": min(response_times) if response_times else 0,
                "max": max(response_times) if response_times else 0,
                "mean": statistics.mean(response_times) if response_times else 0,
                "median": statistics.median(response_times) if response_times else 0,
                "p95": self.calculate_percentile(response_times, 95) if response_times else 0,
                "p99": self.calculate_percentile(response_times, 99) if response_times else 0
            }
        }
        
        self.results["sync"] = sync_results
        logger.info(f"Sync test completed: {sync_results['requests_per_second']:.2f} req/s")
        
        return sync_results
    
    async def test_async_performance(self, num_requests: int = 100) -> Dict[str, Any]:
        """Test asynchronous memory storage performance"""
        logger.info(f"Testing async performance with {num_requests} requests...")
        
        response_times = []
        task_ids = []
        errors = 0
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Submit all async requests
            tasks = []
            for i in range(num_requests):
                task = self.async_store_request(session, i)
                tasks.append(task)
            
            # Execute all requests concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    errors += 1
                    logger.error(f"Async request failed: {result}")
                else:
                    response_time, task_id = result
                    response_times.append(response_time)
                    task_ids.append(task_id)
        
        total_time = time.time() - start_time
        
        async_results = {
            "total_requests": num_requests,
            "successful_requests": len(response_times),
            "failed_requests": errors,
            "total_time_seconds": total_time,
            "requests_per_second": len(response_times) / total_time if total_time > 0 else 0,
            "response_times_ms": {
                "min": min(response_times) if response_times else 0,
                "max": max(response_times) if response_times else 0,
                "mean": statistics.mean(response_times) if response_times else 0,
                "median": statistics.median(response_times) if response_times else 0,
                "p95": self.calculate_percentile(response_times, 95) if response_times else 0,
                "p99": self.calculate_percentile(response_times, 99) if response_times else 0
            },
            "task_ids": task_ids
        }
        
        self.results["async"] = async_results
        logger.info(f"Async test completed: {async_results['requests_per_second']:.2f} req/s")
        
        return async_results
    
    async def async_store_request(self, session: aiohttp.ClientSession, index: int) -> Tuple[float, str]:
        """Single async store request"""
        start_time = time.time()
        
        async with session.post(
            f"{self.base_url}/api/memory/store",
            json={
                "user_id": f"async_user_{index}",
                "conversation_id": f"async_conv_{index}",
                "message": f"Async test message {index}",
                "timestamp": time.time()
            }
        ) as response:
            if response.status == 202:
                data = await response.json()
                response_time = (time.time() - start_time) * 1000
                return response_time, data.get("task_id", "")
            else:
                raise Exception(f"HTTP {response.status}")
    
    def test_concurrent_users(self, max_users: int = 100) -> Dict[str, Any]:
        """Test system under concurrent user load"""
        logger.info(f"Testing concurrent users: {max_users}")
        
        # Use ThreadPoolExecutor for concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_users) as executor:
            futures = []
            
            start_time = time.time()
            
            # Submit concurrent requests
            for i in range(max_users):
                future = executor.submit(self.single_user_session, i)
                futures.append(future)
            
            # Collect results
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        concurrent_results = {
            "total_users": max_users,
            "successful_sessions": sum(1 for r in results if r["success"]),
            "failed_sessions": sum(1 for r in results if not r["success"]),
            "total_time_seconds": total_time,
            "users_per_second": max_users / total_time,
            "average_session_time": statistics.mean([r["duration"] for r in results]),
            "session_details": results
        }
        
        return concurrent_results
    
    def single_user_session(self, user_id: int) -> Dict[str, Any]:
        """Simulate a single user session"""
        session_start = time.time()
        
        try:
            # Store a memory
            store_response = requests.post(
                f"{self.base_url}/api/memory/store",
                json={
                    "user_id": f"concurrent_user_{user_id}",
                    "conversation_id": f"session_{user_id}",
                    "message": f"Concurrent test message {user_id}",
                    "timestamp": time.time()
                }
            )
            
            if store_response.status_code == 202:
                task_id = store_response.json().get("task_id")
                
                # Wait for task completion (poll)
                max_wait = 30
                waited = 0
                while waited < max_wait:
                    status_response = requests.get(f"{self.base_url}/api/task/{task_id}")
                    if status_response.status_code == 200:
                        status = status_response.json().get("status")
                        if status == "SUCCESS":
                            break
                    time.sleep(1)
                    waited += 1
                
                # Retrieve memories
                get_response = requests.get(f"{self.base_url}/api/memory/concurrent_user_{user_id}")
                
                return {
                    "success": get_response.status_code == 200,
                    "duration": time.time() - session_start,
                    "user_id": user_id
                }
                
        except Exception as e:
            logger.error(f"User session failed: {e}")
            return {"success": False, "duration": time.time() - session_start, "user_id": user_id}
    
    def calculate_percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not data:
            return 0
        
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def generate_comparison_report(self) -> Dict[str, Any]:
        """Generate detailed comparison report"""
        sync = self.results["sync"]
        async = self.results["async"]
        
        if sync and async:
            speedup = sync["requests_per_second"] / async["requests_per_second"]
            response_time_improvement = (
                sync["response_times_ms"]["mean"] / async["response_times_ms"]["mean"]
            )
            
            comparison = {
                "speedup_factor": speedup,
                "response_time_improvement": response_time_improvement,
                "throughput_increase": f"{((async['requests_per_second'] - sync['requests_per_second']) / sync['requests_per_second'] * 100):.1f}%",
                "latency_reduction": f"{((sync['response_times_ms']['mean'] - async['response_times_ms']['mean']) / sync['response_times_ms']['mean'] * 100):.1f}%",
                "winner": "async" if async["requests_per_second"] > sync["requests_per_second"] else "sync"
            }
            
            self.results["comparison"] = comparison
            
            return comparison
        
        return {}
    
    def save_results(self, filename: str = None):
        """Save test results to file"""
        if filename is None:
            filename = f"performance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        results_path = Path("tests/results")
        results_path.mkdir(exist_ok=True)
        
        with open(results_path / filename, "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Results saved to {results_path / filename}")
    
    def print_summary(self):
        """Print performance summary"""
        print("\n" + "="*60)
        print("MEMORIA PERFORMANCE TEST SUMMARY")
        print("="*60)
        
        if self.results["sync"]:
            sync = self.results["sync"]
            print(f"\n📊 SYNC PERFORMANCE:")
            print(f"   Requests: {sync['successful_requests']}/{sync['total_requests']}")
            print(f"   Throughput: {sync['requests_per_second']:.2f} req/s")
            print(f"   Avg Response: {sync['response_times_ms']['mean']:.2f}ms")
            print(f"   P95 Response: {sync['response_times_ms']['p95']:.2f}ms")
        
        if self.results["async"]:
            async = self.results["async"]
            print(f"\n⚡ ASYNC PERFORMANCE:")
            print(f"   Requests: {async['successful_requests']}/{async['total_requests']}")
            print(f"   Throughput: {async['requests_per_second']:.2f} req/s")
            print(f"   Avg Response: {async['response_times_ms']['mean']:.2f}ms")
            print(f"   P95 Response: {async['response_times_ms']['p95']:.2f}ms")
        
        if self.results["comparison"]:
            comp = self.results["comparison"]
            print(f"\n🏆 IMPROVEMENTS:")
            print(f"   Speedup: {comp['speedup_factor']:.2f}x")
            print(f"   Throughput: {comp['throughput_increase']}")
            print(f"   Latency: {comp['latency_reduction']} reduction")
        
        print("="*60)

async def main():
    """Main testing function"""
    parser = argparse.ArgumentParser(description="Test Memoria async performance")
    parser.add_argument("--requests", type=int, default=100, help="Number of requests per test")
    parser.add_argument("--users", type=int, default=50, help="Number of concurrent users")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    tester = PerformanceTester(args.url)
    
    try:
        # Test sync performance
        tester.test_sync_performance(args.requests)
        
        # Test async performance
        await tester.test_async_performance(args.requests)
        
        # Test concurrent users
        concurrent_results = tester.test_concurrent_users(args.users)
        tester.results["concurrent"] = concurrent_results
        
        # Generate comparison
        tester.generate_comparison_report()
        
        # Save results
        tester.save_results(args.output)
        
        # Print summary
        tester.print_summary()
        
    except KeyboardInterrupt:
        logger.info("Testing interrupted by user")
    except Exception as e:
        logger.error(f"Testing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())