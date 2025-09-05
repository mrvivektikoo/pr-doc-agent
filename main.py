#!/usr/bin/env python3
"""
Simple Flask app to test LocalTunnel setup
Lightweight webhook handler that enqueues PR data for background processing
"""

from flask import Flask, request, jsonify
from datetime import datetime
from worker import PRWorker

# Create Flask app
app = Flask(__name__)

# Create PR worker instance
pr_worker = PRWorker()

@app.route("/")
def hello():
    return 'Hello World!'

@app.route("/webhook", methods=["POST"])
def fake_webhook():
    """Lightweight webhook handler - validates data and enqueues for processing"""
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # Early exit: Only process "opened" or "reopened" PR actions
        action = data.get("action", "")
        if action not in ["opened", "reopened"]:
            print(f"📨 Skipping webhook - action '{action}' is not 'opened' or 'reopened'")
            return jsonify({
                "message": f"Webhook received but skipped - action '{action}' not processed",
                "action": action,
                "status": "skipped"
            }), 200

        pr_url = data.get("pull_request", {}).get("url", "")
        diff_url = data.get("pull_request", {}).get("diff_url", "")

        if not pr_url:
            return jsonify({"error": "No PR URL found in webhook"}), 400
        
        if not diff_url:
            return jsonify({"error": "No diff URL found in webhook"}), 400
        
        # Get repository info  
        repo_full_name = data.get("repository", {}).get("full_name", "")
        pr_number = data.get("pull_request", {}).get("number", "unknown")
        
        # Create lightweight PR data for the worker
        pr_data = {
            "pr_url": pr_url,
            "diff_url": diff_url,
            "repo": repo_full_name,
            "action": action,
            "pr_number": pr_number,
            "received_at": datetime.now().isoformat()
        }

        # Print to console  
        print(f"📨 Received webhook data : {pr_data}")
        
        # Enqueue the PR (we already filtered for opened/reopened actions above)
        pr_worker.enqueue_pr(pr_data)
        print(f"📨 Enqueued PR: {pr_url}")
        print(f"📊 Queue size: {pr_worker.get_pr_size()}")
        return jsonify({
            "message": "PR webhook received and queued for processing",
            "pr_url": pr_url,
            "repo": repo_full_name,
            "pr_number": pr_number,
            "action": action,
            "queue_position": pr_worker.get_pr_size(),
            "status": "enqueued",
            "note": "Processing will happen in background - check /stats for progress"
        })
    
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({
            "error": "Failed to process webhook",
            "message": str(e)
        }), 400

@app.route("/stats", methods=["GET"])
def get_stats():
    """Get processing statistics and recently processed PRs"""
    return jsonify(pr_worker.get_stats())

@app.route("/processed", methods=["GET"])
def get_all_processed():
    """Get all processed PRs"""
    return jsonify(pr_worker.get_all_processed())

# Start the worker and Flask app
pr_worker.start_worker()
   
print('Starting simple Flask test...')
try:
    app.run(host='0.0.0.0', port=8000, debug=True)
except KeyboardInterrupt:
    print("🛑 Shutting down...")   
    pr_worker.stop_worker()
finally:
    print("🛑 Shutting down...")   
    pr_worker.stop_worker()