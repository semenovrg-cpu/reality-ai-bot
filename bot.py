import os
import re
import base64
import tempfile
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


def extract_links(text):
    return re.findall(r"https?://\S+", text or "")


def get_page_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string if soup.title else ""
        meta = soup.find("meta", attrs={"name": "description"})
        description = meta.get("content") if meta else ""
        text = soup.get_text(" ", strip=True)[:4000]
        return f"Заголовок: {title}\nОписание: {description}\nТекст: {text}"
    except Exception:
        return "Страницу прочитать не удалось. Вероятно, площадка защищает объявление."


def search_analogs(query):
    if not SERPAPI_KEY:
        return "Автопоиск аналогов пока не подключен. Для этого нужно добавить SERPAPI_KEY в Railway Variables."

    try:
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": 5,
            "hl": "ru",
            "gl": "ru"
        }
        r = requests.get("https://serpapi.com/search", params=params, timeout=15)
        data = r.json()
        results = data.get("organic_results", [])[:5]

        if not results:
            return "Аналоги через поиск не найдены."

        text = ""
        for i, item in enumerate(results, 1):
            text += f"{i}. {item.get('title', '')}\n{item.get('snippet', '')}\n{item.get('link', '')}\n\n"
        return text
    except Exception as e:
        return f"Ошибка поиска аналогов: {e}"


def create_pdf_report(text):
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        font_name = "DejaVu"
    except Exception:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = font_name
    styles["Title"].fontName = font_name

    story = []
    story.append(Paragraph("AI-отчет по объекту недвижимости", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(datetime.now().strftime("%d.%m.%Y %H:%M"), styles["Normal"]))
    story.append(Spacer(1, 12))

    for block in text.split("\n"):
        if block.strip():
            story.append(Paragraph(block.replace("&", "&amp;"), styles["Normal"]))
            story.append(Spacer(1, 6))

    doc.build(story)
    return path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я AI-аналитик недвижимости.\n\n"
        "Пришли описание объекта, ссылку на Авито/ЦИАН/Домклик или скриншот объявления.\n"
        "Я сделаю анализ и PDF-отчет."
    )


async def analyze_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    links = extract_links(user_text)

    page_data = ""
    if links:
        await update.message.reply_text("Вижу ссылку. Пробую прочитать объявление...")
        for link in links:
            page_data += f"\nСсылка: {link}\n{get_page_text(link)}\n"

    analog_query = f"{user_text} аналоги недвижимость цена Иркутск Авито ЦИАН Домклик"
    analogs = search_analogs(analog_query)

    prompt = f"""
Ты ТОП-аналитик рынка недвижимости России.

Данные объекта:
{user_text}

Данные из ссылки:
{page_data}

Найденные аналоги или статус поиска:
{analogs}

Сделай профессиональный отчет:

1. Краткое резюме объекта
2. Тип объекта, площадь, цена, цена за м²
3. Сильные стороны
4. Слабые стороны
5. Анализ цены
6. Диапазон рыночной цены
7. Сравнение с аналогами
8. Ликвидность: высокая / средняя / низкая
9. Прогноз срока продажи
10. Риски объекта
11. Что агенту сказать продавцу
12. Что использовать в рекламе
13. Что уточнить у собственника
14. Итоговая рекомендация по цене

Пиши жестко, конкретно, без воды.
Если реальных аналогов нет — честно напиши, что точный CMA невозможен без базы аналогов.
"""

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt
        )

        answer = response.output_text

        for i in range(0, len(answer), 3500):
            await update.message.reply_text(answer[i:i + 3500])

        pdf_path = create_pdf_report(answer)
        await update.message.reply_document(document=open(pdf_path, "rb"), filename="AI_Realty_Report.pdf")

    except Exception as e:
        await update.message.reply_text(f"Ошибка анализа: {e}")


async def analyze_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("Принял скриншот. Анализирую объявление...")

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{image_base64}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """
Ты ТОП-аналитик недвижимости.

Проанализируй скриншот объявления.

Сделай:
1. Что за объект
2. Цена
3. Площадь
4. Цена за м²
5. Сильные стороны
6. Слабые стороны
7. Ликвидность
8. Риски
9. Насколько объявление продающее
10. Что агенту улучшить
11. Что сказать продавцу
12. Рекомендация по цене

Пиши конкретно, как эксперт рынка.
"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ],
            max_tokens=1600
        )

        answer = response.choices[0].message.content

        for i in range(0, len(answer), 3500):
            await update.message.reply_text(answer[i:i + 3500])

        pdf_path = create_pdf_report(answer)
        await update.message.reply_document(document=open(pdf_path, "rb"), filename="AI_Realty_Report.pdf")

    except Exception as e:
        await update.message.reply_text(f"Ошибка анализа фото: {e}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_text))
    app.add_handler(MessageHandler(filters.PHOTO, analyze_photo))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()


