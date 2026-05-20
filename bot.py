import os
import requests
from bs4 import BeautifulSoup

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# СТАРТ
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я AI-аналитик недвижимости.\n\n"
        "Отправь:\n"
        "- описание объекта\n"
        "- ссылку на Авито/ЦИАН/Домклик\n"
        "- или скриншоты объявления"
    )

# ОБРАБОТКА ТЕКСТА
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_text = update.message.text

    prompt = f"""
Ты профессиональный аналитик недвижимости.

Проанализируй объект недвижимости.

Данные:
{user_text}

Сделай:
1. Оценку объекта
2. Плюсы
3. Минусы
4. Насколько цена адекватна
5. Для кого подойдет
6. Риски при продаже
7. Советы агенту
8. Прогноз ликвидности

Пиши профессионально и конкретно.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты лучший AI аналитик недвижимости."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        answer = response.choices[0].message.content

        await update.message.reply_text(answer)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ОБРАБОТКА ФОТО
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        photo = update.message.photo[-1]

        file = await context.bot.get_file(photo.file_id)

        image_url = file.file_path

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """
Проанализируй скриншот объявления недвижимости.

Определи:
1. Что это за объект
2. Адекватность цены
3. Плюсы объекта
4. Минусы объекта
5. Ликвидность
6. Что агенту стоит улучшить
7. Есть ли признаки переоценки
8. Насколько объявление продающее
"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )

        answer = response.choices[0].message.content

        await update.message.reply_text(answer)

    except Exception as e:
        await update.message.reply_text(f"Ошибка анализа фото: {e}")

# ЗАПУСК
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
)

app.add_handler(
    MessageHandler(filters.PHOTO, handle_photo)
)

print("Бот запущен...")

app.run_polling()
