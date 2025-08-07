# 📝 Poem Parser Bot & API

This project allows you to extract structured poem information (title, clean HTML, and Markdown) from images. It supports interaction through:

- ✅ A **Telegram bot**.
- 🌐 A **REST API** with Swagger documentation.


## 🚀 Features

### Telegram Bot
- 📷 Send one or more poem images.
- 🧠 Uses LLMs to extract a clean HTML version of the poem.
- 📄 Returns the HTML file and Markdown text.
- ✅ Use `/done` to process images.
- 🔁 Use `/reset` to discard current session.
- 🧹 Cleans up user files after each session.

### REST API
- 📤 `/api/parse` endpoint accepts multiple image uploads.
- 📄 Returns poem title, HTML, and Markdown.
- 🔐 Uses the same credentials as the bot.
- ⚙️ Swagger documentation available at `/apidocs`.
- 🧪 Can be tested using `test_app.py`.


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

## 🤖 Run the Telegram Bot
```bash
python main.py
```

Open Telegram and talk to your bot. Try sending 1–3 poem images, then use /done to receive the HTML.

## 🌐 Run the API
Start the Flask app with Gunicorn:
```
gunicorn app:app --bind 0.0.0.0:8080
```

Or for development/testing:
```
python app.py
```

The API will be available at:
http://localhost:8080/api/parse

You can test the API using **Swagger UI** or the included **Python script**.

### 🔍 Swagger UI
Access the documentation at: http://localhost:8080/apidocs

You can upload an image using the file input.

Review the result and download HTML/Markdown content.

###  Python Script
Edit the image paths in the test_app.py script to specify which images to process, then run:

bash
Copiar
Editar
```
python test_app.py
```


## 📁 Project Structure

```bash
poem-html-bot/
├── main.py               # Telegram bot entry point
├── app.py                # Flask API entry point
├── process.py            # Core processing logic
├── test_app.py           # Script to test the API
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


## ❌ Limitations
- Only .jpg, .jpeg, and .png formats are supported.
- Large images or too many images may exceed model token limits.

## 📄 License
MIT License. See the LICENSE file.

## 👤 Author
Made with ❤️ by Maria
