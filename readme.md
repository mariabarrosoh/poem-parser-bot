# 📝 Poem Parser Bot & API

This project enables you to extract structured poem information—such as the title and poem text in Markdown format—from images. You can interact with it in three main ways:

- ✅ Through a Telegram bot, which lets you upload, edit, and delete poems directly via chat commands.

- 🌐 Via a REST API that allows uploading poem data to the database or deleting existing poems.

- 📄 Through web views that display saved poems by author and title, providing a user-friendly interface to browse the poem collection.


## 🚀 Features

### Telegram Bot (bot/main.py)
- Command-based interface to manage poems directly from Telegram.
- Commands to upload images, edit title, poem content, and author.
- Save poems to the database.
- Delete poems, authors, or all poems.

### Flask Application (api/app.py)
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


💡 You can use any of the supported models.

### ✅ Telegram Bot Token (Only for Telegram Bot)
1. Open [@BotFather](https://t.me/BotFather) on Telegram.
2. Run the `/newbot` command and follow the steps.
3. Copy the token you receive.
4. Add it to your `.env` and paste it into .env as TELEGRAM_BOT_TOKEN.


## 🛠️ Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/mariabarrosoh/poem-parser-bot
cd poem-parser-bot
```

### 2. Install Dependencies
This project requires **Python 3.10.18** to ensure compatibility.
We recommend using a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create a .env File
Edit the .env file with your credentials:
```bash
# app environent variables
APP_NAME=your_app_name
PYTHON_VERSION=3.10.18
ALLOWED_USER_ID=your_users_id_separated_by_commas
MAIN_USER_ID=your_main_id
DATABASE_URL=your_db_url


# bot environent variables
BOT_NAME=your_bot_name
PYTHON_VERSION=3.10.18
ALLOWED_USER_ID=our_users_id_separated_by_commas
MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct
GROQ_API_KEY=your_groq_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
MAX_IMAGES=10
TEMP_DIR=temp
API_DOMAIN=your_api_domain
BOT_DOMAIN=your_bot_domain
```

## 🤖 Run the Telegram Bot in local
```bash
cd bot
python main.py
```

Open Telegram and talk to your bot.

## 🌐 Run the API in local
Start the Flask app with Gunicorn:
```bash
cd api
gunicorn app:app --bind 0.0.0.0:8080
```

Or for development/testing:
```bash
cd api
python app.py
```

The API will be available at:
http://localhost:8080/


## 📁 Project Structure

```bash
poem-parser-bot
├── api
│ ├── app.py
│ ├── requirements.txt
│ ├── templates
│ │ ├── poem.html
│ │ ├── poems_author_list.html
│ │ └── poems_list.html
│ └── utils
│ │ ├── db_utils.py
│ │ ├── logging_config.py
│ │ └── utils.py
├── bot
│ ├── main.py
│ ├── msg.json
│ ├── process.py
│ ├── prompts
│ │ └── poem_extractor.txt
│ ├── requirements.txt
│ └── utils
│ │ ├── llm_utils.py
│ │ ├── logging_config.py
│ │ └──  utils.py
├── LICENSE
└── readme.md
```


## ❌ Limitations
- Only .jpg, .jpeg, and .png formats are supported.
- Large images or too many images may exceed model token limits.

## 📄 License
MIT License. See the LICENSE file.

## 👤 Author
Made with ❤️ by Maria
