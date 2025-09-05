# PR Documentation Agent

An intelligent Flask webhook service that analyzes GitHub pull requests to determine if documentation (README files) should be updated based on code changes. Uses OpenAI to provide smart analysis of diffs against existing documentation.

## Features

- 🔍 **Automatic PR Analysis**: Fetches PR diffs and repository README files
- 🤖 **AI-Powered Analysis**: Uses OpenAI GPT-3.5-turbo to determine if documentation needs updates
- 📝 **Intelligent Comments**: Posts detailed, actionable suggestions directly on PRs
- ⚡ **Fast Webhook Response**: Immediate response (~10ms) with background processing
- 🔄 **Queue Management**: Reliable background worker processes PRs asynchronously
- 📊 **Real-time Monitoring**: Live processing stats and comprehensive logging
- 🎯 **Smart Filtering**: Only processes "opened" and "reopened" PR actions
- 🔒 **Production Ready**: Robust error handling, retry logic, and scalable architecture

## Prerequisites

- Python 3.x (tested with Python 3.13+)
- Node.js (for localtunnel)
- OpenAI API key

## Installation

### 1. Clone and Navigate to Repository
```bash
git clone <your-repo-url>
cd pr-doc-agent
```

### 2. Set Up Python Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up API Keys

#### Get Your OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click "Create new secret key" 
4. Give it a name (e.g., "PR Doc Agent")
5. Copy the key (starts with `sk-...`)

#### Get Your GitHub Personal Access Token
1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Give it a name (e.g., "PR Doc Agent")
4. Select scopes:
   - ✅ `public_repo` (for public repositories)
   - ✅ `repo` (if you need access to private repositories)
5. Copy the token (starts with `ghp_...` or `github_pat_...`)

**Pro Tip**: For a cleaner bot identity, create a dedicated GitHub account for your bot (e.g., `docassist-bot`) and generate the token from that account.

#### Configure Environment Variables
Create a `.env` file in the project root:
```bash
touch .env
```

Add your API keys to the `.env` file:
```env
# OpenAI API Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here

# GitHub API Configuration  
GITHUB_TOKEN=ghp_your-github-token-here
```

**Important**: Never commit your `.env` file to git. It's already included in `.gitignore`.

### 5. Install LocalTunnel
```bash
npm install -g localtunnel
```

## Usage

**Important**: Always make sure your virtual environment is activated before running the service:
```bash
source venv/bin/activate  # You should see (venv) in your terminal prompt
```

### Option 1: Use the Start Script (Recommended)
```bash
chmod +x startBot.sh  # Make script executable (first time only)
./startBot.sh
```

This script will:
- Start the Flask webhook service on port 8000
- Start LocalTunnel to expose your service to the internet
- Handle cleanup when you stop it (Ctrl+C)

### Option 2: Manual Setup
1. Start the Flask application:
```bash
python3 main.py
```

2. In a separate terminal, start the tunnel:
```bash
lt --port 8000 --subdomain pr-doc-{YOUR_NAME}
```
Example:
```bash
lt --port 8000 --subdomain pr-doc-bot
```

This will output your tunnel URL: `https://pr-doc-bot.loca.lt`

## How It Works

### Architecture Overview

The service uses a **background processing architecture** for optimal performance:

1. **`main.py`**: Lightweight webhook handler
   - Validates incoming webhooks
   - Filters for "opened" and "reopened" PR actions only
   - Enqueues valid PRs for background processing
   - Returns immediate response (no waiting for API calls)

2. **`worker.py`**: Background processing engine
   - Processes PRs from queue asynchronously
   - Handles all heavy operations (GitHub API, OpenAI API)
   - Posts intelligent comments to PRs when updates are needed

### Processing Flow

When a pull request is **opened** or **reopened**:

1. **⚡ Fast Webhook Response**: GitHub webhook → Immediate validation and queuing (~10ms)
2. **🔄 Background Processing**: Worker picks up PR from queue and:
   - **Fetches PR Diff**: Downloads actual code changes from GitHub
   - **Fetches README**: Gets current repository README file  
   - **AI Analysis**: Sends both to OpenAI GPT-3.5-turbo for analysis
   - **Smart Commenting**: Posts detailed suggestions as PR comment (if updates needed)

### API Endpoints

- **`POST /webhook`** - Main GitHub webhook endpoint
- **`GET /stats`** - View processing statistics and recent PRs
- **`GET /processed`** - View all processed PRs history  

### Example Webhook Response
```json
{
  "message": "PR webhook received and queued for processing",
  "pr_url": "https://api.github.com/repos/user/repo/pulls/123",
  "repo": "user/repo",
  "pr_number": 123,
  "action": "opened",
  "queue_position": 1,
  "status": "enqueued",
  "note": "Processing will happen in background - check /stats for progress"
}
```

### Example Bot Comment

When analysis determines README updates are needed, the bot posts detailed comments:

```markdown
## 🤖 DocAssist Bot - README Update Suggestions 🟡

> **🔍 AI Analysis Result** | Priority: **MEDIUM**

**📋 Analysis Summary:** The PR adds new API endpoints that should be documented

### Recommended Changes:

#### 1. API Reference
**Why this change:** New /webhook endpoint needs documentation
**Current content:** Basic usage examples  
**Suggested content:** Add webhook endpoint documentation with examples

### 📝 Next Steps:
- [ ] Review the suggestions above
- [ ] Update your README accordingly
- [ ] Consider if other documentation needs updating
```

## Setup GitHub Integration

### 1. Add Bot to Repository

If using a dedicated bot account, add it as a collaborator:

1. Go to your repository → **Settings** → **Collaborators**
2. Click **"Add people"** 
3. Search for your bot username (e.g., `docassist-bot`)
4. Select **"Write"** permission level (required for posting comments)
5. Bot account must accept the invitation

### 2. Webhook Configuration

Set up your GitHub webhook URL to point to your tunnel URL:

![Webhook Setup](https://github.com/user-attachments/assets/7e68d67b-8104-4424-ad61-9e0c1d6888a7)

![Webhook URL Configuration](https://github.com/user-attachments/assets/24cc2cbf-5645-4a24-997e-4bb218a3879b)

## Testing

Create a pull request in your repository and check the service logs to verify the webhook is working correctly.

### Service Endpoints
- **`GET /`** - Simple health check
- **`POST /webhook`** - Main webhook endpoint for GitHub PR events  
- **`GET /stats`** - Processing statistics and recently processed PRs
- **`GET /processed`** - Complete history of all processed PRs

### Monitoring Background Processing

Since processing happens asynchronously, use these endpoints to monitor progress:

**Check Processing Status:**
```bash
curl https://your-tunnel-url.loca.lt/stats
```

**Example Stats Response:**
```json
{
  "stats": {
    "total_received": 15,
    "total_processed": 12,
    "queue_size": 3
  },
  "recently_processed": [
    {
      "pr_url": "https://api.github.com/repos/user/repo/pulls/123", 
      "repo": "user/repo",
      "status": "success",
      "processing_time": 4.2,
      "comment_posted": true
    }
  ],
  "worker_status": "running"
}
```

**Watch Live Processing:**
Monitor your Flask app console for real-time processing logs:
```
📨 Enqueued PR: https://api.github.com/repos/user/repo/pulls/123
📝 Processing PR: 123 from user/repo
   🔍 Fetching diff...
   📖 Fetching README...
   🤖 Analyzing with AI...  
   💬 Posting comment...
✅ Finished processing PR (4.2s)
```

### Debug Mode
The service runs with Flask debug mode enabled, which provides:
- Automatic reloading when code changes
- Detailed error pages with interactive debugger  
- Better logging and error reporting
- Background worker monitoring in console

## Dependencies

This project uses the following key libraries:

- **Flask**: Web framework for handling webhooks (main.py)
- **requests**: HTTP client for calling GitHub and OpenAI APIs (worker.py)
- **openai**: Official OpenAI Python client v1.106.1+ (worker.py)
- **python-dotenv**: Loads environment variables from `.env` files
- **threading & queue**: Background processing and job queuing (worker.py)
- **localtunnel**: Exposes local development server to internet (npm package)

### Architecture Components

- **`main.py`**: 90 lines - Lightweight Flask webhook handler
- **`worker.py`**: 550+ lines - Background processing engine with full AI integration
- **`.env`**: Environment variables for API keys (OpenAI + GitHub)
- **`requirements.txt`**: Python dependencies with exact versions

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'flask'"**
- Make sure your virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

**"OPENAI_API_KEY environment variable not set"**
- Ensure your `.env` file exists and contains your API key
- Restart the Flask application after creating/updating `.env`
- Check that `.env` is in the project root directory

**"GITHUB_TOKEN environment variable not set - cannot post comments"**
- Ensure your `.env` file contains `GITHUB_TOKEN=your-token-here`
- Restart the Flask application after updating `.env`
- Check that your GitHub token has correct permissions (repo/public_repo scope)

**GitHub API 401 "Requires authentication" / 403 "Forbidden"**
- **401**: Token is invalid or not being read - check `.env` file format
- **403**: Token lacks permissions - ensure bot account has Write access to repository
- Add bot as collaborator: Repository → Settings → Collaborators → Add people

**"Failed to parse LLM response as JSON"**  
- This is handled automatically by JSON cleaning, but if persistent:
- Check OpenAI API key validity and account credits
- Monitor worker logs for detailed error messages

**"Permission denied: ./startBot.sh"**
- Make the script executable: `chmod +x startBot.sh`

**"Port 8000 is already in use"**
- Stop any existing instances: `lsof -i :8000` then `kill <PID>`
- Or use a different port by modifying `main.py`

**"Bad interpreter: /bin/bash^M"**
- Fix line endings: `tr -d '\r' < startBot.sh > temp && mv temp startBot.sh`
- Make executable again: `chmod +x startBot.sh`

### Costs and Rate Limits

- **OpenAI API**: Uses GPT-3.5-turbo (~$0.001-0.005 per analysis)
- **GitHub API**: Free tier allows 5,000 requests/hour
- Input is limited to 3,000 chars (README) + 2,000 chars (diff) to control costs

### Development Tips

- Monitor console output for detailed processing logs
- Use Flask's debug mode to set breakpoints and inspect variables
- Test with small PRs first to verify the integration works
- Check GitHub webhook delivery logs if events aren't being received

