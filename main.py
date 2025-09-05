#!/usr/bin/env python3
"""
Simple Flask app to test LocalTunnel setup
Just basic endpoints to verify tunnel is working
"""

import json
import base64
import os
import re
import requests
from flask import Flask, request, jsonify
from datetime import datetime
from worker import PRWorker
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create Flask app
app = Flask(__name__)

pr_worker = PRWorker()

def fetch_pr_diff(diff_url):
    """
    Fetch the diff content from GitHub's API.
    
    In Node.js, you might use fetch() or axios. In Python, we use the requests library.
    This is similar to: const response = await fetch(diff_url)
    
    Args:
        diff_url (str): The GitHub diff URL from the webhook payload
    
    Returns:
        str: The diff content, or None if the request failed
    """
    try:
        print(f"🔍 Fetching diff from: {diff_url}")
        
        # Make GET request to GitHub (similar to fetch() in Node.js)
        response = requests.get(diff_url, timeout=30)
        
        # Check if request was successful (status code 200-299)
        response.raise_for_status()
        
        print(f"✅ Successfully fetched diff ({len(response.text)} characters)")
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch diff: {e}")
        return None

def fetch_repo_readme(repo_full_name):
    """
    Fetch the README file content from a GitHub repository.
    
    Uses GitHub's Contents API which automatically finds README.md, README.txt, etc.
    This is similar to: fetch(`https://api.github.com/repos/${owner}/${repo}/readme`)
    
    Args:
        repo_full_name (str): Repository name in format "owner/repo" (e.g., "facebook/react")
    
    Returns:
        dict: Contains 'content' (decoded README text) and 'filename', or None if failed
    """
    try:
        # GitHub's API endpoint for README - automatically finds README.md, README.txt, etc.
        api_url = f"https://api.github.com/repos/{repo_full_name}/readme"
        print(f"📖 Fetching README from: {api_url}")
        
        # Add headers for better API experience (GitHub recommends this)
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'PR-Doc-Agent'
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        readme_data = response.json()
        
        # GitHub returns README content base64-encoded, so we need to decode it
        content_base64 = readme_data.get('content', '')
        # Remove newlines from base64 string before decoding
        content_base64_clean = content_base64.replace('\n', '')
        readme_content = base64.b64decode(content_base64_clean).decode('utf-8')
        
        print(f"✅ Successfully fetched README: {readme_data.get('name')} ({len(readme_content)} characters)")
        
        return {
            'content': readme_content,
            'filename': readme_data.get('name', 'README'),
            'size': len(readme_content)
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch README (API error): {e}")
        return None
    except (json.JSONDecodeError, base64.binascii.Error, UnicodeDecodeError) as e:
        print(f"❌ Failed to decode README content: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error fetching README: {e}")
        return None

def analyze_readme_with_llm(readme_content, diff_content, repo_name):
    """
    Use OpenAI to analyze if the README should be updated based on the PR diff.
    
    This is similar to calling any REST API, but we're sending a structured prompt
    to analyze code changes and documentation alignment.
    
    Args:
        readme_content (str): Current README content
        diff_content (str): Git diff from the PR
        repo_name (str): Repository name for context
    
    Returns:
        dict: Contains 'should_update' (bool), 'reasoning' (str), 'suggestions' (str)
              or None if analysis failed
    """
    try:
        # Get API key from environment
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            print("❌ OPENAI_API_KEY environment variable not set")
            return None
        
        # Initialize OpenAI client with explicit parameters only
        try:
            client = OpenAI(api_key=api_key)
        except TypeError as e:
            if "proxies" in str(e):
                print(f"❌ OpenAI client initialization error (likely version issue): {e}")
                print("💡 Try: pip install --upgrade openai")
                return None
            else:
                raise e
        
        print(f"🤖 Analyzing README relevance for changes in {repo_name}")
        
        # Craft a focused prompt for README analysis
        prompt = f"""
You are a technical documentation expert. Analyze this Pull Request to determine if the README should be updated and provide specific update suggestions.

REPOSITORY: {repo_name}

CURRENT README:
```
{readme_content[:3000]}  # Limit to first 3000 chars to avoid token limits
```

PR CHANGES (git diff):
```
{diff_content[:2000]}  # Limit diff to 2000 chars
```

Analyze the changes and respond with a JSON object containing:
1. "should_update": boolean - true if README needs updating
2. "reasoning": string - brief explanation of your decision
3. "specific_updates": array of objects, each containing:
   - "section": string - which README section needs updating (e.g., "Installation", "Usage", "API Reference")
   - "current_content": string - the current content that should be changed
   - "suggested_content": string - the new content that should replace it
   - "reason": string - why this specific change is needed
4. "priority": string - "high", "medium", or "low" based on impact to users

Consider these factors:
- New features that users need to know about
- Changed APIs or usage patterns  
- New dependencies or requirements
- Installation or setup changes
- Breaking changes
- New endpoints or configuration options

If should_update is false, set specific_updates to an empty array.

IMPORTANT: 
- Respond ONLY with valid JSON
- Do NOT include markdown code blocks (```json)
- Do NOT include trailing commas
- Use double quotes for all strings
- Ensure proper JSON syntax
"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # More cost-effective than GPT-4 for this task
            messages=[
                {
                    "role": "system", 
                    "content": "You are a helpful assistant that analyzes code changes and documentation. Always respond with valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,  # Increased for more detailed suggestions
            temperature=0.1  # Low temperature for consistent, analytical responses
        )
        
        # Parse the LLM response
        llm_response = response.choices[0].message.content.strip()
        
        # Clean up common JSON issues from LLM responses
        cleaned_response = clean_llm_json(llm_response)
        
        try:
            analysis = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse cleaned LLM response: {e}")
            print(f"Original response: {llm_response[:300]}...")
            print(f"Cleaned response: {cleaned_response[:300]}...")
            return None
        
        print(f"✅ LLM Analysis complete: Should update = {analysis.get('should_update', False)}")
        return analysis
        
    except json.JSONDecodeError as e:
        # This catch block is now redundant but keeping for safety
        print(f"❌ Failed to parse LLM response as JSON: {e}")
        print(f"Raw response: {llm_response[:200] if 'llm_response' in locals() else 'No response captured'}...")
        return None
    except Exception as e:
        print(f"❌ Error calling OpenAI API: {e}")
        return None

def clean_llm_json(json_string):
    """
    Clean up common JSON formatting issues from LLM responses.
    
    LLMs often generate JSON with trailing commas, extra whitespace, or markdown
    code blocks that need to be cleaned before parsing.
    
    Args:
        json_string (str): The raw JSON string from the LLM
        
    Returns:
        str: Cleaned JSON string that should be valid
    """
    try:
        # Remove markdown code blocks if present
        if '```json' in json_string:
            json_string = json_string.split('```json')[1].split('```')[0]
        elif '```' in json_string:
            # Handle generic code blocks
            parts = json_string.split('```')
            if len(parts) >= 3:
                json_string = parts[1]
        
        # Strip whitespace
        json_string = json_string.strip()
        
        # Remove trailing commas before closing braces/brackets
        # Remove trailing comma before }
        json_string = re.sub(r',(\s*})', r'\1', json_string)
        # Remove trailing comma before ]
        json_string = re.sub(r',(\s*])', r'\1', json_string)
        
        # Fix common quote issues (replace smart quotes with regular quotes)
        json_string = json_string.replace('"', '"').replace('"', '"')
        json_string = json_string.replace(''', "'").replace(''', "'")
        
        return json_string
        
    except Exception as e:
        print(f"⚠️ Error cleaning JSON: {e}")
        return json_string  # Return original if cleaning fails

def post_pr_comment(pr_url, analysis, repo_full_name):
    """
    Post a comment on the bot's PR with README update suggestions.
    
    Uses GitHub's REST API to comment directly on the pull request.
    This is similar to: POST /repos/{owner}/{repo}/issues/{issue_number}/comments
    
    Args:
        pr_url (str): The GitHub API URL for the PR (e.g., https://api.github.com/repos/user/repo/pulls/123)
        analysis (dict): The LLM analysis result with specific_updates
        repo_full_name (str): Repository name in format "owner/repo"
        
    Returns:
        bool: True if comment was posted successfully, False otherwise
    """
    try:
        if not analysis or not analysis.get('should_update'):
            print("📝 No README updates needed, skipping comment")
            return True
        
        # Extract PR number from the PR URL
        # URL format: https://api.github.com/repos/owner/repo/pulls/123
        pr_number = pr_url.split('/')[-1]
        
        # GitHub API endpoint for posting comments
        comment_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
        
        # Format the comment content
        comment_body = format_readme_comment(analysis)
        
        # Get GitHub token from environment
        github_token = os.getenv('GITHUB_TOKEN')
        
        if not github_token:
            print("❌ GITHUB_TOKEN environment variable not set - cannot post comments")
            return False
        
        # Prepare the API request with authentication
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'PR-Doc-Agent',
            'Authorization': f'Bearer {github_token}'
        }
        
        payload = {
            'body': comment_body
        }
        
        print(f"💬 Posting README update suggestions to PR #{pr_number}")
        
        # Make the API request
        response = requests.post(comment_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 201:
            print(f"✅ Successfully posted comment to PR #{pr_number}")
            return True
        else:
            print(f"❌ Failed to post comment: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error posting PR comment: {e}")
        return False

def format_readme_comment(analysis):
    """
    Format the LLM analysis into a nice GitHub comment.
    
    Args:
        analysis (dict): The LLM analysis with specific_updates array
        
    Returns:
        str: Formatted markdown comment for GitHub
    """
    priority_emoji = {
        'high': '🔴',
        'medium': '🟡', 
        'low': '🟢'
    }
    
    priority = analysis.get('priority', 'medium')
    emoji = priority_emoji.get(priority, '🔵')
    
    comment = f"""## 🤖 DocAssist Bot - README Update Suggestions {emoji}

> **🔍 AI Analysis Result** | Priority: **{priority.upper()}**

**📋 Analysis Summary:** {analysis.get('reasoning', 'No reasoning provided')}

"""
    
    specific_updates = analysis.get('specific_updates', [])
    if specific_updates:
        comment += "### Recommended Changes:\n\n"
        
        for i, update in enumerate(specific_updates, 1):
            section = update.get('section', 'Unknown Section')
            reason = update.get('reason', 'No reason provided')
            current = update.get('current_content', 'Not specified')
            suggested = update.get('suggested_content', 'Not specified')
            
            comment += f"""#### {i}. {section}

**Why this change:** {reason}

**Current content:**
```
{current[:200]}{'...' if len(current) > 200 else ''}
```

**Suggested content:**
```
{suggested[:300]}{'...' if len(suggested) > 300 else ''}
```

---

"""
    
    comment += """
---

🤖 **This comment was automatically generated by DocAssist Bot**  
*An AI-powered documentation assistant that analyzes code changes and suggests README updates*

### 📝 Next Steps:
- [ ] Review the suggestions above
- [ ] Update your README accordingly  
- [ ] Consider if other documentation needs updating
- [ ] Re-run tests after documentation updates

*Have feedback? Let us know how we can improve these suggestions!* 💬

"""
    
    return comment

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
        # GitHub webhooks provide a diff_url - this points directly to the diff content
        diff_url = data.get("pull_request", {}).get("diff_url", "")

        if not pr_url:
            return jsonify({"error": "No PR URL found in webhook"}), 400
        
        if not diff_url:
            return jsonify({"error": "No diff URL found in webhook"}), 400
        
        # Fetch the actual diff content from GitHub
        diff_content = fetch_pr_diff(diff_url)
        
        # Get repository info and fetch README
        repo_full_name = data.get("repository", {}).get("full_name", "")
        readme_data = None
        if repo_full_name:
            readme_data = fetch_repo_readme(repo_full_name)
        
        # Analyze with LLM if we have both diff and README content
        llm_analysis = None
        if diff_content and readme_data and readme_data.get('content'):
            llm_analysis = analyze_readme_with_llm(
                readme_data['content'], 
                diff_content, 
                repo_full_name
            )
        
        # Post comment to PR if we have analysis results
        comment_posted = False
        if llm_analysis and llm_analysis.get('should_update'):
            comment_posted = post_pr_comment(pr_url, llm_analysis, repo_full_name)
        
        pr_data = {
            "pr_url": pr_url,
            "diff_url": diff_url,
            "diff_content": diff_content,  # This will be None if fetch failed
            "readme_data": readme_data,  # Dict with content, filename, size or None
            "llm_analysis": llm_analysis,  # Dict with should_update, reasoning, suggestions or None
            "comment_posted": comment_posted,  # Whether comment was successfully posted
            "received_at": datetime.now().isoformat(),
            "repo": repo_full_name,
            "action": data.get("action", "unknown"),
            "pr_number": data.get("pull_request", {}).get("number", "unknown")
        }

        # Print to console  
        print(f"📨 Received webhook data : {pr_data}")
        
        # Enqueue the PR (we already filtered for opened/reopened actions above)
        pr_worker.enqueue_pr(pr_data)
        print(f"📨 Enqueued PR: {pr_url}")
        print(f"📊 Queue size: {pr_worker.get_pr_size()}")
        return jsonify({
            "message": "PR webhook received and queued",
            "pr_url": pr_url,
            "diff_url": diff_url,
            "diff_fetched": diff_content is not None,
            "diff_size": len(diff_content) if diff_content else 0,
            "readme_fetched": readme_data is not None,
            "readme_filename": readme_data.get("filename") if readme_data else None,
            "readme_size": readme_data.get("size", 0) if readme_data else 0,
            "llm_analyzed": llm_analysis is not None,
            "readme_should_update": llm_analysis.get("should_update") if llm_analysis else None,
            "llm_reasoning": llm_analysis.get("reasoning") if llm_analysis else None,
            "priority": llm_analysis.get("priority") if llm_analysis else None,
            "specific_updates_count": len(llm_analysis.get("specific_updates", [])) if llm_analysis else 0,
            "comment_posted": comment_posted,
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
    app.run(host='0.0.0.0', port=8000, debug=True)
except KeyboardInterrupt:
    print("🛑 Shutting down...")   
    pr_worker.stop_worker()
finally:
    print("🛑 Shutting down...")   
    pr_worker.stop_worker()