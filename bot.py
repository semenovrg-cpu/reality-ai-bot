import os
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я AI-аналитик недвижимости.\n\n"
        "Пришли описание объекта:\n"
        "город, район, тип, площадь, цена, этаж, состояние."
    )


async def analyze_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    prompt = f"""
Ты профессиональный аналитик рынка недвижимости и помощник агента.

Пользователь прислал объект:

{user_text}

Сделай анализ в формате:

1. Краткое резюме объекта
2. Сильные стороны
3. Слабые стороны
4. Предварительная оценка ликвидности
5. Что нужно уточнить у собственника
6. Рекомендации по цене
7. Текст для агента
8. Текст для клиента простым языком

Если данных не хватает — честно напиши какие именно.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Ты сильный аналитик недвижимости и помощник агента."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response.choices[0].message.content

    await update.message.reply_text(answer)


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            analyze_object
        )
    )

    print("Бот запущен...")

    app.run_polling()


if __name__ == "__main__":
    main()
