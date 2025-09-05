#!/usr/bin/env python3
"""
Simple Flask app to test LocalTunnel setup
Just basic endpoints to verify tunnel is working
"""

import json
from flask import Flask, request, jsonify
from datetime import datetime
from worker import PRWorker

# Create Flask app
app = Flask(__name__)

pr_worker = PRWorker()

@app.route("/")
def hello():
    return 'Hello World!'

@app.route("/webhook", methods=["POST"])
def fake_webhook():
    """Fake webhook to test POST requests"""
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        pr_url = data.get("pull_request", {}).get("url", "")

        if not pr_url:
            return jsonify({"error": "No PR URL found in webhook"}), 400
        
        pr_data = {
            "pr_url": pr_url,
            "received_at": datetime.now().isoformat(),
            "repo": data.get("repository", {}).get("full_name", "unknown"),
            "action": data.get("action", "unknown"),
            "pr_number": data.get("pull_request", {}).get("number", "unknown")
        }

        # Print to console
        print(f"📨 Received webhook data : {pr_data}")
        if pr_data["action"] == "opened" or pr_data["action"] == "reopened":
            pr_worker.enqueue_pr(pr_data)
            print(f"📨 Enqueued PR: {pr_url}")
        else:
            print(f"📨 Skipping PR: {pr_url} because action is not opened")
        print(f"📊 Queue size: {pr_worker.get_pr_size()}")
        return jsonify({
            "message": "PR webhook received and queued",
            "pr_url": pr_url,
            "queue_position": pr_worker.get_pr_size(),
            "status": "enqueued"
        })
    
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({
            "error": "Failed to process webhook",
            "message": str(e)
        }), 400    

pr_worker.start_worker()
   
print('Starting simple Flask test...')
try:
    app.run(host='0.0.0.0', port=8000)
except KeyboardInterrupt:
    print("🛑 Shutting down...")   
    pr_worker.stop_worker()
finally:
    print("🛑 Shutting down...")   
    pr_worker.stop_worker()