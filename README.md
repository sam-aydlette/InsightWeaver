# InsightWeaver

An app that curates information from a wide range of reputable sources and creates custom daily reporting for me on events and trends that I care about.

## Features

- Collects articles from diverse, reputable news sources
- Automatic deduplication to avoid repeated stories
- Clean HTML email briefings delivered daily
- SQLite database for local storage
- Free operation using GitHub Actions

## Setup


1. Create virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure email settings:
   - Copy `.env.example` to `.env`
   - Set up Gmail App Password following [Google's instructions](https://support.google.com/accounts/answer/185833)
   - Update the environment variables in `.env`

3. Test locally:
   ```bash
   python briefing.py
   ```

## GitHub Actions Setup

1. In your GitHub repository settings, add these secrets:
   - `SMTP_SERVER` (smtp.gmail.com)
   - `SMTP_PORT` (587)
   - `EMAIL_USERNAME` (your Gmail address)
   - `EMAIL_PASSWORD` (your Gmail App Password)
   - `FROM_EMAIL` (your Gmail address)
   - `RECIPIENT_EMAIL` (where to send briefings)

2. The workflow runs daily at 8 AM UTC automatically

## News Sources

The system collects from reputable sources including:
- Reuters, AP, BBC (Western perspective)
- Al Jazeera, SCMP, Deutsche Welle (International perspectives)  
- Krebs Security (Cybersecurity focus)

## Database

Articles are stored in SQLite with automatic deduplication. The system keeps the last 30 days of articles.
