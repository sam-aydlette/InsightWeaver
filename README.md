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
   - `ANTHROPIC_API_KEY` (authenticating to a Claude API account)

2. The workflow runs daily at 8 AM UTC automatically

## News Sources

The system collects from a comprehensive range of reputable sources:

### Western/US Perspective
- **Reuters** - International news and analysis
- **AP International** - Associated Press global coverage
- **BBC World** - British Broadcasting Corporation world news
- **Foreign Policy** - International affairs magazine
- **Foreign Affairs** - Global affairs and policy analysis
- **CFR** - Council on Foreign Relations publications
- **CSIS** - Center for Strategic and International Studies
- **The Economist World** - International news and analysis
- **Chatham House** - UK-based international affairs think tank
- **Carnegie Endowment** - Global policy research
- **International Crisis Group** - Conflict prevention and resolution

### Non-Western Perspectives
- **Al Jazeera** - Middle Eastern and international news
- **SCMP** - South China Morning Post (Hong Kong/China focus)
- **The Hindu International** - Indian perspective on global affairs
- **Deutsche Welle** - German international broadcaster
- **France24** - French international news
- **Americas Quarterly** - Latin American affairs
- **Council on Hemispheric Affairs** - Western Hemisphere analysis
- **AllAfrica** - African news and perspectives
- **ISS Africa** - Institute for Security Studies Africa
- **The Diplomat** - Asia-Pacific affairs
- **East Asia Forum** - Regional Asian analysis
- **Arab News** - Middle Eastern perspectives
- **Haaretz English** - Israeli news and analysis

### Cybersecurity & Technology
- **Krebs Security** - Cybersecurity investigations and analysis
- **Hacker News** - Technology and security discussions
- **Threatpost** - Cybersecurity threat intelligence
- **Bellingcat** - Open source investigations
- **CISA Alerts** - US Cybersecurity and Infrastructure Security Agency
- **CISA News** - Government cybersecurity updates

### Defense & Military
- **Defense News** - Military and defense industry coverage
- **Military.com** - Military affairs and news
- **Jane's Defence** - Defense intelligence and analysis
- **CSBA** - Center for Strategic and Budgetary Assessments

### Alternative Analysis
- **Carnegie Moscow** - Russian perspectives and analysis
- **PONARS Eurasia** - Post-Soviet and Eurasian studies
- **Quincy Institute** - Responsible statecraft and diplomacy
- **CNAS** - Center for a New American Security

### Institutional Sources
- **UN News** - United Nations official news
- **World Bank** - Global development and economic analysis

### Economic Intelligence
- **Financial Times World** - Global financial and economic news

## Database

Articles are stored in SQLite with automatic deduplication. The system keeps the last 30 days of articles.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. Free to use with attribution.
