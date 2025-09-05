#!/usr/bin/env python3
"""
PR Processing Worker
Handles background processing of PR URLs from the queue
"""

import time
import threading
from datetime import datetime
from queue import Queue, Empty

class PRWorker:
    def __init__(self):
        self.processed_prs = []
        self.stats = {
            "total_received": 0,
            "total_processed": 0,
            "queue_size": 0
        }
        self.is_running = False
        self.worker_thread = None
    
    def start_worker(self):
        """Start the background worker thread"""
        self.pr_queue = Queue()
        self.is_running = True
        
        self.worker_thread = threading.Thread(
            target=self._worker_loop, 
            daemon=True,
            name="PR-Worker"
        )
        self.worker_thread.start()
        print("🔄 Started PR processing worker")
    
    def stop_worker(self):
        """Stop the background worker"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            print("⏹️  Stopped PR processing worker")
    
    def _worker_loop(self):
        """Main worker loop - processes PRs from queue (FIFO)"""
        while self.is_running:
            try:
                # Get next PR from queue (FIFO - First In, First Out)
                pr_data = self.pr_queue.get(timeout=1)
                
                print(f"📝 Processing PR: {pr_data['pr_url']}")
                
                # Process the PR
                result = self._process_single_pr(pr_data)
                
                # Update stats and tracking
                self._update_after_processing(pr_data, result)
                
                # Mark queue task as done
                self.pr_queue.task_done()
                
            except Empty:
                # No items in queue, continue waiting
                continue
            except Exception as e:
                print(f"❌ Worker error: {e}")
                continue
    
    def _process_single_pr(self, pr_data):
        """Process a single PR (replace this with your actual logic)"""
        start_time = datetime.now()
        
        # TODO: Replace this with your actual PR processing logic
        # For now, just simulate processing
        print(f"   📊 Analyzing PR {pr_data.get('pr_number', 'unknown')}")
        print(f"   📝 Generating documentation suggestions...")
        
        # Simulate processing time
        time.sleep(2)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"✅ Finished processing PR: {pr_data['pr_url']} ({processing_time:.1f}s)")
        
        return {
            "status": "success",
            "processing_time": processing_time,
            "processed_at": end_time.isoformat()
        }
    
    def _update_after_processing(self, pr_data, result):
        """Update tracking after processing a PR"""
        processed_entry = {
            "pr_url": pr_data["pr_url"],
            "received_at": pr_data["received_at"],
            "processed_at": result["processed_at"],
            "repo": pr_data.get("repo", "unknown"),
            "pr_number": pr_data.get("pr_number", "unknown"),
            "processing_time": result.get("processing_time", 0),
            "status": result.get("status", "unknown")
        }
        
        self.processed_prs.append(processed_entry)
        self.stats["total_processed"] += 1
        self.stats["queue_size"] = self.pr_queue.qsize()
        
        # Keep only last 100 processed items to avoid memory issues
        if len(self.processed_prs) > 100:
            self.processed_prs = self.processed_prs[-100:]
    
    def get_stats(self):
        """Get current processing statistics"""
        return {
            "stats": self.stats,
            "recently_processed": self.processed_prs[-5:] if self.processed_prs else [],
            "worker_status": "running" if self.is_running else "stopped"
        }
    
    def get_all_processed(self):
        """Get all processed PRs"""
        return {
            "total_processed": len(self.processed_prs),
            "processed_prs": self.processed_prs
        }
    
    def enqueue_pr(self, pr_data):
        """Helper method to enqueue a PR and update stats"""
        self.pr_queue.put(pr_data)
        self.stats["total_received"] += 1
        self.stats["queue_size"] = self.pr_queue.qsize()
    
    def get_pr_size(self):
        return self.pr_queue.qsize()

# You can also add specific processing functions here
def process_pr_documentation(pr_url):
    """
    Future: Add your actual PR processing logic here
    This could include:
    - Fetching PR diff from GitHub API
    - Analyzing code changes  
    - Generating documentation suggestions
    - Posting comments back to GitHub
    """
    pass

def analyze_code_changes(pr_diff):
    """
    Future: Add code analysis logic here
    """
    pass

def generate_doc_suggestions(code_changes):
    """
    Future: Add documentation suggestion logic here
    """
    pass