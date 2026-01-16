# Getting Started with InsightWeaver

This guide walks you through downloading, installing, and running InsightWeaver on your computer.

---

## What You Need

1. **A computer** (Windows, Mac, or Linux)
2. **Python 3.10 or newer** - [Download Python](https://www.python.org/downloads/)
3. **An Anthropic API key** - [Get one here](https://console.anthropic.com/) (requires account)

---

## Step 1: Download InsightWeaver

**Option A: Download ZIP** (easiest)
1. Click the green "Code" button on this page
2. Click "Download ZIP"
3. Extract the ZIP file to a folder (e.g., your Documents folder)

**Option B: Using Git** (if you have it installed)
```
git clone https://github.com/YOUR_USERNAME/InsightWeaver.git
```

---

## Step 2: Open a Terminal

**Windows:**
1. Press `Windows + R`
2. Type `cmd` and press Enter
3. Navigate to the InsightWeaver folder:
   ```
   cd Documents\InsightWeaver
   ```

**Mac:**
1. Open Spotlight (`Cmd + Space`)
2. Type `Terminal` and press Enter
3. Navigate to the InsightWeaver folder:
   ```
   cd ~/Documents/InsightWeaver
   ```

**Linux:**
1. Open your terminal application
2. Navigate to the InsightWeaver folder:
   ```
   cd ~/Documents/InsightWeaver
   ```

---

## Step 3: Install InsightWeaver

Run these commands one at a time:

```
python -m venv venv
```

**Activate the virtual environment:**

Windows:
```
venv\Scripts\activate
```

Mac/Linux:
```
source venv/bin/activate
```

**Install InsightWeaver:**
```
pip install -e .
```

---

## Step 4: Add Your API Key

1. Copy the example environment file:

   Windows:
   ```
   copy .env.example .env
   ```

   Mac/Linux:
   ```
   cp .env.example .env
   ```

2. Open the `.env` file in a text editor (Notepad, TextEdit, etc.)

3. Find the line that says:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```

4. Replace `your_key_here` with your actual API key from Anthropic

5. Save and close the file

---

## Step 5: Run the Setup Wizard

```
insightweaver setup
```

This opens a web page in your browser where you can:
- Enter your location (city and state)
- Select your profession/industry
- Choose topics you care about

Follow the on-screen instructions to complete setup.

---

## Step 6: Start InsightWeaver

```
insightweaver start
```

This opens the InsightWeaver dashboard in your web browser at `http://localhost:5000`.

---

## Using InsightWeaver

### The Dashboard

When you start InsightWeaver, you'll see a dashboard with three main features:

#### Generate Daily Brief
Click this to create a personalized news briefing. InsightWeaver will:
1. Fetch the latest news from hundreds of sources
2. Analyze what's relevant to your location and interests
3. Generate a summary report

This takes 2-5 minutes. When complete, click "View Full Report" to read your briefing.

#### Generate Forecast
Click this to get predictions about trends that may affect you. The forecast organizes predictions by confidence level:
- **Certain**: Things that are very likely to happen
- **Likely**: Evidence-based projections
- **Possible**: Weak signals worth watching

#### Ask AI
Type a question and get a fact-checked answer. InsightWeaver verifies the response against authoritative sources and checks for bias.

### Viewing Reports

All generated reports are saved automatically. You can find them in:
- `reports/briefings/` - Your daily briefings
- `reports/forecasts/` - Your forecasts
- `reports/trust/` - Your Q&A history

Reports are saved as HTML files you can open in any web browser.

---

## Starting InsightWeaver Each Day

After the initial setup, you only need two steps:

1. **Open a terminal** and navigate to your InsightWeaver folder

2. **Activate and start:**

   Windows:
   ```
   venv\Scripts\activate
   insightweaver start
   ```

   Mac/Linux:
   ```
   source venv/bin/activate
   insightweaver start
   ```

Your browser will open to the dashboard automatically.

---

## Troubleshooting

### "command not found" or "not recognized"

Make sure you've activated the virtual environment:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

You should see `(venv)` at the start of your command line.

### "No module named..." errors

Try reinstalling:
```
pip install -e .
```

### API key errors

1. Check that your `.env` file exists and contains your API key
2. Make sure there are no extra spaces around the `=` sign
3. Verify your API key is valid at [console.anthropic.com](https://console.anthropic.com/)

### Browser doesn't open automatically

Manually open your web browser and go to: `http://localhost:5000`

### Reports are empty or have errors

1. Check your internet connection
2. Make sure your API key has available credits
3. Try running `insightweaver brief health` to check system status

---

## Configuration

### User Profile

Your preferences are stored in `config/user_profile.json`. You can edit this file directly or use the setup wizard (`insightweaver setup`).

### Email Reports (Optional)

To receive reports via email, add these to your `.env` file:

```
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com
RECIPIENT_EMAIL=your_email@gmail.com
```

For Gmail, you'll need to create an "App Password" in your Google account settings.

### RSS Feeds

News sources are configured in the `config/feeds/` folder. Each JSON file contains a list of RSS feed URLs organized by category.

---

## Privacy

- All data is stored locally on your computer
- News articles are fetched directly from public RSS feeds
- Your questions and briefings are processed through the Anthropic API
- No data is shared with third parties
- You can delete all data by removing the `data/` folder

---

## Requirements

- **Python**: 3.10 or newer
- **Disk Space**: ~100MB for database and reports
- **Internet**: Required for fetching news and AI analysis
- **API Credits**: Anthropic API key with available credits (~$0.10-0.50 per briefing)

---

## Getting Help

If you run into problems:

1. Check the Troubleshooting section above
2. Run `insightweaver brief health` to diagnose issues
3. Report issues at: https://github.com/anthropics/claude-code/issues

---

## Next Steps

Once you're comfortable with the basics, you can explore:
- **[CLI Reference](docs/cli_reference.md)** - Command-line options for power users
- **[Configuration Guide](docs/configuration_guide.md)** - Customize your profile and feeds
- **[Scheduling Setup](deployment/SCHEDULING_SETUP.md)** - Automate daily briefings
