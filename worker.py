#!/usr/bin/env python3
"""
PR Processing Worker
Handles background processing of PR URLs from the queue
"""

import time
import threading
import json
import base64
import os
import re
import requests
from datetime import datetime
from queue import Queue, Empty
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fetch_pr_diff(diff_url):
    """
    Fetch the diff content from GitHub's API.
    
    Args:
        diff_url (str): The GitHub diff URL from the webhook payload
    
    Returns:
        str: The diff content, or None if the request failed
    """
    try:
        print(f"🔍 Fetching diff from: {diff_url}")
        
        # Make GET request to GitHub
        response = requests.get(diff_url, timeout=30)
        response.raise_for_status()
        
        print(f"✅ Successfully fetched diff ({len(response.text)} characters)")
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch diff: {e}")
        return None

def fetch_repo_readme(repo_full_name):
    """
    Fetch the README file content from a GitHub repository.
    
    Args:
        repo_full_name (str): Repository name in format "owner/repo"
    
    Returns:
        dict: Contains 'content' (decoded README text) and 'filename', or None if failed
    """
    try:
        # GitHub's API endpoint for README
        api_url = f"https://api.github.com/repos/{repo_full_name}/readme"
        print(f"📖 Fetching README from: {api_url}")
        
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'PR-Doc-Agent'
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        readme_data = response.json()
        
        # GitHub returns README content base64-encoded
        content_base64 = readme_data.get('content', '')
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

def clean_llm_json(json_string):
    """
    Clean up common JSON formatting issues from LLM responses.
    
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
            parts = json_string.split('```')
            if len(parts) >= 3:
                json_string = parts[1]
        
        # Strip whitespace
        json_string = json_string.strip()
        
        # Remove trailing commas before closing braces/brackets
        json_string = re.sub(r',(\s*})', r'\1', json_string)
        json_string = re.sub(r',(\s*])', r'\1', json_string)
        
        # Fix common quote issues
        json_string = json_string.replace('"', '"').replace('"', '"')
        json_string = json_string.replace(''', "'").replace(''', "'")
        
        return json_string
        
    except Exception as e:
        print(f"⚠️ Error cleaning JSON: {e}")
        return json_string

def analyze_readme_with_llm(readme_content, diff_content, repo_name):
    """
    Use OpenAI to analyze if the README should be updated based on the PR diff.
    
    Args:
        readme_content (str): Current README content
        diff_content (str): Git diff from the PR
        repo_name (str): Repository name for context
    
    Returns:
        dict: Contains 'should_update' (bool), 'reasoning' (str), 'specific_updates' (array)
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
{readme_content[:3000]}
```

PR CHANGES (git diff):
```
{diff_content[:2000]}
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
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a helpful assistant that analyzes code changes and documentation. Always respond with valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.1
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
        print(f"❌ Failed to parse LLM response as JSON: {e}")
        print(f"Raw response: {llm_response[:200] if 'llm_response' in locals() else 'No response captured'}...")
        return None
    except Exception as e:
        print(f"❌ Error calling OpenAI API: {e}")
        return None

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

def post_pr_comment(pr_url, analysis, repo_full_name):
    """
    Post a comment on the GitHub PR with README update suggestions.
    
    Args:
        pr_url (str): The GitHub API URL for the PR
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
        """Process a single PR with full analysis and comment posting"""
        start_time = datetime.now()
        
        try:
            print(f"   📊 Processing PR {pr_data.get('pr_number', 'unknown')} from {pr_data.get('repo', 'unknown')}")
            
            # Extract required data
            diff_url = pr_data.get('diff_url')
            repo_full_name = pr_data.get('repo')
            pr_url = pr_data.get('pr_url')
            
            if not diff_url or not repo_full_name or not pr_url:
                return {
                    "status": "error",
                    "error": "Missing required PR data (diff_url, repo, or pr_url)",
                    "processing_time": 0,
                    "processed_at": datetime.now().isoformat()
                }
            
            # Step 1: Fetch PR diff
            print(f"   🔍 Fetching diff...")
            diff_content = fetch_pr_diff(diff_url)
            
            if not diff_content:
                return {
                    "status": "error", 
                    "error": "Failed to fetch PR diff",
                    "processing_time": (datetime.now() - start_time).total_seconds(),
                    "processed_at": datetime.now().isoformat()
                }
            
            # Step 2: Fetch README
            print(f"   📖 Fetching README...")
            readme_data = fetch_repo_readme(repo_full_name)
            
            if not readme_data:
                return {
                    "status": "error",
                    "error": "Failed to fetch README", 
                    "processing_time": (datetime.now() - start_time).total_seconds(),
                    "processed_at": datetime.now().isoformat()
                }
            
            # Step 3: Analyze with LLM
            print(f"   🤖 Analyzing with AI...")
            analysis = analyze_readme_with_llm(
                readme_data['content'], 
                diff_content, 
                repo_full_name
            )
            
            comment_posted = False
            if analysis and analysis.get('should_update'):
                # Step 4: Post comment if needed
                print(f"   💬 Posting comment...")
                comment_posted = post_pr_comment(pr_url, analysis, repo_full_name)
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            print(f"✅ Finished processing PR: {pr_data['pr_url']} ({processing_time:.1f}s)")
            
            return {
                "status": "success",
                "processing_time": processing_time,
                "processed_at": end_time.isoformat(),
                "diff_fetched": True,
                "diff_size": len(diff_content),
                "readme_fetched": True,
                "readme_filename": readme_data.get('filename'),
                "llm_analyzed": analysis is not None,
                "should_update": analysis.get('should_update') if analysis else False,
                "comment_posted": comment_posted,
                "priority": analysis.get('priority') if analysis else None,
                "specific_updates_count": len(analysis.get('specific_updates', [])) if analysis else 0
            }
            
        except Exception as e:
            print(f"❌ Error processing PR: {e}")
            return {
                "status": "error",
                "error": str(e),
                "processing_time": (datetime.now() - start_time).total_seconds(),
                "processed_at": datetime.now().isoformat()
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