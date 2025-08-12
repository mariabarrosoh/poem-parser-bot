# 📝 Poem Parser Bot & API

This project enables you to extract structured poem information—such as the title and poem text in Markdown format—from images. You can interact with it in three main ways:

- ✅ Through a Telegram bot, which lets you upload, edit, and delete poems directly via chat commands.

- 🌐 Via a REST API that allows uploading poem data to the database or deleting existing poems.

- 📄 Through web views that display saved poems by author and title, providing a user-friendly interface to browse the poem collection.


## 🚀 Features

### Telegram Bot (main.py)
- Command-based interface to manage poems directly from Telegram.
- Commands to upload images, edit title, poem content, and author.
- Save poems to the database.
- Delete poems, authors, or all poems.
- Key commands include `/start`, `/done`, `/edittitle`, `/editpoem`, `/editauthor`, `/save`, `/deletepoem`, `/deleteauthor`, `/deleteall`, `/reset`, and `/help`.

### Flask Application (app.py)
- Provides web HTML views to display saved poems by author and title.
- Allows browsing all poems by a user, by author, or viewing a specific poem.
- Offers REST API endpoints to save poems, delete poems, delete authors, or delete all poems for a user.
- Includes basic validation and authorization via user_id.


## 🔑 Required API Tokens

### ✅ Groq API Key
1. Visit https://console.groq.com/keys.
2. Sign in or create a free Groq account.
3. Click "Create API Key".
4. Copy the token (starts with gsk_...) and paste it into .env as GROQ_API_KEY.

```env
GROQ_API_KEY=your_groq_api_key
MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct  # Or your preferred model
```

💡 You can use any of the supported models.

### ✅ Telegram Bot Token (Only for Telegram Bot)
1. Open [@BotFather](https://t.me/BotFather) on Telegram.
2. Run the `/newbot` command and follow the steps.
3. Copy the token you receive.
4. Add it to your `.env` as:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```


## 🛠️ Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/mariabarrosoh/poem-parser-bot
cd poem-parser-bot
```

### 2. Install Dependencies
This project requires **Python 3.12.0** to ensure compatibility.
We recommend using a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create a .env File
Edit the .env file with your credentials:
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token              # Telegram bot token from @BotFather
GROQ_API_KEY=your_groq_api_key                          # API key for the Groq service
MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct    # Or your preferred model name
DATA_DIR=data                                           # Directory for temporary user image and output files
DB_DIR=db                                               # Directory where the poem database is stored
TEMP_DIR=temp                                           # Temporary directory for intermediate files
MAX_IMAGES=5                                            # Maximum number of images allowed per upload
POEM_DOMAIN=http://localhost:8080                       # Poem Domain for local, https://poem-parser.onrender.com for production
ALLOWED_USER_ID=your_user_telegram_id                   # Comma-separated Telegram user IDs authorized to use the app (e.g., 123456789,987654321)
PYTHON_VERSION=3.10.18
```

## 🤖 Run the Telegram Bot in local
```bash
python main.py
```

Open Telegram and talk to your bot. Try sending 1–3 poem images, then use /done to receive the HTML.

## 🌐 Run the API in local
Start the Flask app with Gunicorn:
```
gunicorn app:app --bind 0.0.0.0:8080
```

Or for development/testing:
```
python app.py
```

The API will be available at:
http://localhost:8080/


## 📁 Project Structure

```bash
poem-parser-bot/
├── main.py               # Telegram bot entry point
├── app.py                # Flask API entry point
├── process.py            # Core processing logic
├── utils/
│   ├── logging_config.py # Logs configuration
│   ├── db_utils.py       # DB interaction logic
│   ├── llm_utils.py      # LLM interaction logic
│   └── utils.py          # Helper functions (image encoding, etc.)
├── prompts/
│   └── poem_extractor.txt
├── temp/                 # Temporary user image and output files
├── db/                   # DB with user poems
├── templates/            # API templates
├── .env                  # Secrets (not committed)
├── .gitignore
└── requirements.txt
```


## ❌ Limitations
- Only .jpg, .jpeg, and .png formats are supported.
- Large images or too many images may exceed model token limits.

## 📄 License
MIT License. See the LICENSE file.

## 👤 Author
Made with ❤️ by Maria
