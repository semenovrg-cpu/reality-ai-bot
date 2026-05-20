import os
import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


def extract_links(text):
    return re.findall(r"https?://\S+", text)


def get_page_text(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string if soup.title else ""
        description = ""

        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            description = meta.get("content")

        text = soup.get_text(" ", strip=True)
        text = text[:5000]

        return f"Заголовок страницы: {title}\nОписание: {description}\nТекст страницы: {text}"

    except Exception as e:
        return f"Не удалось прочитать ссылку автоматически. Ошибка: {e}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я AI-аналитик недвижимости.\n\n"
        "Пришли описание объекта или ссылку на Авито / ЦИАН / Домклик.\n\n"
        "Лучше всего: город, район, тип, площадь, цена, этаж, состояние."
    )


async def analyze_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    links = extract_links(user_text)

    link_data = ""

    if links:
        await update.message.reply_text("Вижу ссылку. Пробую прочитать объявление...")
        for link in links:
            link_data += f"\n\nСсылка: {link}\n{get_page_text(link)}"

    prompt = f"""
Ты профессиональный аналитик рынка недвижимости и помощник агента.

Пользователь прислал данные объекта:

{user_text}

Дополнительные данные из ссылки, если удалось получить:

{link_data}

Сделай анализ в формате:

1. Краткое резюме объекта
2. Сильные стороны
3. Слабые стороны
4. Предварительная оценка ликвидности
5. Что нужно уточнить у собственника
6. Рекомендации по цене
7. Риски объекта
8. Что сказать агенту
9. Текст для клиента простым языком
10. Какие данные нужны для более точной оценки

Важно:
- Если данных мало, не выдумывай.
- Если ссылка не прочиталась, честно напиши, что нужен текст объявления или скрин.
- Не называй точную рыночную цену без базы аналогов.
- Давай практичные рекомендации для агента.
"""

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt
        )

        answer = response.output_text

        if len(answer) > 3900:
            for i in range(0, len(answer), 3900):
                await update.message.reply_text(answer[i:i + 3900])
        else:
            await update.message.reply_text(answer)

    except Exception as e:
        await update.message.reply_text(
            f"Ошибка при анализе: {e}\n\n"
            "Проверь OpenAI API ключ и баланс аккаунта."
        )


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_object))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()


