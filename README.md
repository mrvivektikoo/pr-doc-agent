# PR Documentation Agent

A simple Flask webhook listener for processing GitHub pull request events.

## Prerequisites

- Python 3.x
- Node.js (for localtunnel)

## Installation

### 1. Install Python Dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Install LocalTunnel
```bash
npm install -g localtunnel
```

## Usage

### Option 1: Use the Start Script
```bash
./startBot.sh
```

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

## Webhook Configuration

Set up your GitHub webhook URL to point to your tunnel URL:

![Webhook Setup](https://github.com/user-attachments/assets/7e68d67b-8104-4424-ad61-9e0c1d6888a7)

![Webhook URL Configuration](https://github.com/user-attachments/assets/24cc2cbf-5645-4a24-997e-4bb218a3879b)

## Testing

Create a pull request in your repository and check the service logs to verify the webhook is working correctly.
