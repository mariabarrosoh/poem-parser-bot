# 📝 Poem Parser Extractor Telegram Bot

This Telegram bot allows users to send one or more poem images and receive a clean, validated HTML file of the poem, including its title and text.


## 🚀 Features

- 📷 Upload one or more images (in order).
- 🧠 LLM extracts a clean HTML version of the poem.
- 📄 Sends HTML file directly to the user.
- 🔁 `/reset` to discard current session.
- ✅ `/done` to process and receive the extracted data and HTML file.
- 🧹 Cleans up user files after each session.


## 🔑 How to Get the Required API Tokens
### ✅ Telegram Bot Token
1. Go to @BotFather in Telegram.
2. Run the command /newbot.
3. Follow the prompts:
    - Choose a name (PoemParserBot)
    - Choose a username (must end in bot, e.g., PoemParserBot).

4. You'll receive a token like this:
    ```makefile
    123456789:ABCDefGhIJKlmNoPQRstuVWXyz123456789
    ```
5. Copy it and set it as TELEGRAM_BOT_TOKEN in .env.

### ✅ Groq API Key
1. Visit https://console.groq.com/keys.
2. Sign in or create a free Groq account.
3. Click "Create API Key".
4. Copy the token (starts with gsk_...) and paste it into .env as GROQ_API_KEY.

💡 You can use any of the supported models.

## 🛠️ Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/mariabarrosoh/poem-parser-bot
cd poem-html-bot
```

### 2. Install Dependencies
We recommend using a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create a .env File
Edit the .env file with your credentials:
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct  # Or your preferred model
DATA_DIR=data
MAX_IMAGES=5
```

### 4. Run the Bot
```bash
python main.py
```

Open Telegram and talk to your bot. Try sending 1–3 poem images, then use /done to receive the HTML.

### 5. Run without Telegram
Change the variables in the main program and run it to test the functionality.

```bash
python process.py
```


## ☁️ Deploying to Railway
1. Go to Railway and create an account.
2. Click "New Project" → "Deploy from GitHub Repo".
3. Connect this repository.
4. Add your .env variables from above in the Railway dashboard.
5. In the Settings > Start Command, set:

```bash
python main.py
```
6. Click "Deploy". Your Telegram bot is now live!

## 📁 Project Structure

```bash
poem-html-bot/
├── main.py               # Telegram handlers and entrypoint
├── process.py            # Handles image → HTML pipeline
├── utils/
│   ├── logging_config.py # Logs configuration
│   ├── llm_utils.py      # LLM interaction logic
│   └── utils.py          # Helper functions (image encoding, etc.)
├── prompts/
│   ├── html_extractor.txt
│   ├── html_validator.txt
│   └── title_md_extractor.txt
.txt
├── data/                 # Temporary user image and output files
├── .env                  # Secrets (not committed)
├── .gitignore
└── requirements.txt
```

## 🧹 Cleanup Behavior
Each user gets a separate data/{request_id}/ folder.

This is auto-deleted after /done or /reset.

The bot avoids reusing old images if the user restarts a session.

## ❌ Limitations
Only .jpg, .jpeg, and .png formats are supported.
Large images or too many images (MAX 10) may exceed model token limits.

## 📄 License
MIT License. See the LICENSE file.

## 👤 Author
Made with ❤️ by Maria
