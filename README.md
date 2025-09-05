# PR Documentation Agent

An intelligent Flask webhook service that analyzes GitHub pull requests to determine if documentation (README files) should be updated based on code changes. Uses OpenAI to provide smart analysis of diffs against existing documentation.

## Features

- 🔍 **Automatic PR Analysis**: Fetches PR diffs and repository README files
- 🤖 **AI-Powered Analysis**: Uses OpenAI to determine if documentation needs updates
- 📝 **Smart Suggestions**: Provides specific recommendations for README improvements
- ⚡ **Real-time Processing**: Processes webhooks as PRs are opened/reopened
- 🔄 **Queue Management**: Background worker processes PRs efficiently

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

### 4. Set Up OpenAI API Key

#### Get Your OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click "Create new secret key" 
4. Give it a name (e.g., "PR Doc Agent")
5. Copy the key (starts with `sk-...`)

#### Configure Environment Variables
Create a `.env` file in the project root:
```bash
touch .env
```

Add your API key to the `.env` file:
```env
OPENAI_API_KEY=sk-your-actual-api-key-here
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

When a pull request is opened or reopened, the service:

1. **Receives Webhook**: GitHub sends PR data to your webhook endpoint
2. **Fetches PR Diff**: Downloads the actual code changes from GitHub
3. **Fetches README**: Gets the current repository README file
4. **AI Analysis**: Sends both to OpenAI GPT-3.5-turbo with a specialized prompt
5. **Returns Results**: Provides analysis on whether README should be updated

### Example Response
```json
{
  "message": "PR webhook received and queued",
  "pr_url": "https://api.github.com/repos/user/repo/pulls/123",
  "diff_fetched": true,
  "diff_size": 245,
  "readme_fetched": true,
  "readme_filename": "README.md",
  "llm_analyzed": true,
  "readme_should_update": true,
  "llm_reasoning": "The PR adds a new API endpoint that should be documented in the usage section",
  "status": "enqueued"
}
```

## Webhook Configuration

Set up your GitHub webhook URL to point to your tunnel URL:

![Webhook Setup](https://github.com/user-attachments/assets/7e68d67b-8104-4424-ad61-9e0c1d6888a7)

![Webhook URL Configuration](https://github.com/user-attachments/assets/24cc2cbf-5645-4a24-997e-4bb218a3879b)

## Testing

Create a pull request in your repository and check the service logs to verify the webhook is working correctly.

### Service Endpoints
- `GET /` - Simple health check
- `POST /webhook` - Main webhook endpoint for GitHub PR events
- `GET https://pr-doc-bot.loca.lt/stats` - Shows recently processed PRs and queue status

### Debug Mode
The service runs with Flask debug mode enabled, which provides:
- Automatic reloading when code changes
- Detailed error pages with interactive debugger
- Better logging and error reporting

## Dependencies

This project uses the following key libraries:

- **Flask**: Web framework for handling webhooks
- **requests**: HTTP client for calling GitHub and OpenAI APIs  
- **openai**: Official OpenAI Python client
- **python-dotenv**: Loads environment variables from `.env` files
- **localtunnel**: Exposes local development server to internet (npm package)

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'flask'"**
- Make sure your virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

**"OPENAI_API_KEY environment variable not set"**
- Ensure your `.env` file exists and contains your API key
- Restart the Flask application after creating/updating `.env`
- Check that `.env` is in the project root directory

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

