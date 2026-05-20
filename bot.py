import os
import re
import base64
import tempfile
from datetime import datetime
from html import escape

from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


def init_session(context):
    if "mode" not in context.user_data:
        context.user_data["mode"] = None
    if "object_texts" not in context.user_data:
        context.user_data["object_texts"] = []
    if "analog_texts" not in context.user_data:
        context.user_data["analog_texts"] = []
    if "object_images" not in context.user_data:
        context.user_data["object_images"] = []
    if "analog_images" not in context.user_data:
        context.user_data["analog_images"] = []


def create_pdf_report(text):
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font_name = "DejaVuSans"

    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
    except Exception:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    styles = getSampleStyleSheet()

    styles["Normal"].fontName = font_name
    styles["Normal"].fontSize = 10
    styles["Normal"].leading = 14

    styles["Title"].fontName = font_name
    styles["Title"].fontSize = 16
    styles["Title"].leading = 20

    story = []
    story.append(Paragraph("AI-отчет по объекту недвижимости", styles["Title"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(datetime.now().strftime("%d.%m.%Y %H:%M"), styles["Normal"]))
    story.append(Spacer(1, 14))

    for line in text.split("\n"):
        line = line.strip()
        if line:
            story.append(Paragraph(escape(line), styles["Normal"]))
            story.append(Spacer(1, 5))

    doc.build(story)
    return path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    await update.message.reply_text(
        "Привет. Я AI-аналитик недвижимости.\n\n"
        "Работаем так:\n\n"
        "/object — загрузить основной объект\n"
        "/analog — загрузить аналоги\n"
        "/report — сформировать отчет\n"
        "/clear — очистить сессию\n\n"
        "Можно отправлять текст, ссылки и скриншоты."
    )


async def object_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    context.user_data["mode"] = "object"
    await update.message.reply_text(
        "Режим основного объекта включен.\n\n"
        "Отправь описание, ссылку или скриншоты основного объекта."
    )


async def analog_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    context.user_data["mode"] = "analog"
    await update.message.reply_text(
        "Режим аналогов включен.\n\n"
        "Отправь 3–10 аналогов: текстом, ссылками или скриншотами."
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    init_session(context)
    await update.message.reply_text("Сессия очищена. Начни заново с /object")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    mode = context.user_data.get("mode")
    text = update.message.text

    if mode == "object":
        context.user_data["object_texts"].append(text)
        await update.message.reply_text("Основной объект добавлен. Можно добавить еще данные или перейти к /analog")
    elif mode == "analog":
        context.user_data["analog_texts"].append(text)
        await update.message.reply_text(
            f"Аналог добавлен. Всего аналогов текстом: {len(context.user_data['analog_texts'])}. "
            "Можно добавить еще или нажать /report"
        )
    else:
        await update.message.reply_text(
            "Сначала выбери режим:\n/object — основной объект\n/analog — аналоги"
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    mode = context.user_data.get("mode")

    if mode not in ["object", "analog"]:
        await update.message.reply_text("Сначала выбери режим: /object или /analog")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{image_base64}"

    if mode == "object":
        context.user_data["object_images"].append(image_url)
        await update.message.reply_text("Скриншот основного объекта добавлен.")
    else:
        context.user_data["analog_images"].append(image_url)
        await update.message.reply_text(
            f"Скриншот аналога добавлен. Всего скриншотов аналогов: {len(context.user_data['analog_images'])}"
        )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)

    object_texts = context.user_data.get("object_texts", [])
    analog_texts = context.user_data.get("analog_texts", [])
    object_images = context.user_data.get("object_images", [])
    analog_images = context.user_data.get("analog_images", [])

    if not object_texts and not object_images:
        await update.message.reply_text("Нет основного объекта. Нажми /object и отправь объект.")
        return

    await update.message.reply_text("Формирую сравнительный анализ и PDF-отчет...")

    prompt = f"""
Ты ТОП-аналитик рынка недвижимости России и помощник сильного агента.

Задача:
Сравнить основной объект с аналогами, определить адекватность цены, ликвидность и дать рекомендации для агента и клиента.

Основной объект, текстовые данные:
{chr(10).join(object_texts)}

Аналоги, текстовые данные:
{chr(10).join(analog_texts)}

Сделай отчет:

1. Краткое резюме основного объекта
2. Таблица сравнения аналогов:
   - объект
   - цена
   - площадь
   - цена за м²
   - состояние
   - локация
   - сильные/слабые стороны
3. Средняя цена за м² по аналогам
4. Диапазон рыночной цены:
   - цена для быстрой продажи
   - рыночная цена
   - максимальная цена
5. Насколько основной объект переоценен или недооценен
6. Ликвидность: высокая / средняя / низкая
7. Прогноз срока продажи
8. Что мешает продаже
9. Что усиливает продажу
10. Что агенту сказать продавцу
11. Что можно показать клиенту простым языком
12. Рекомендация по цене
13. Что нужно уточнить для более точной оценки

Пиши жестко, конкретно, без воды.
Если данных по аналогам мало — честно напиши, что точный CMA невозможен, но сделай предварительную оценку.
"""

    content = [{"type": "text", "text": prompt}]

    for img in object_images:
        content.append({"type": "image_url", "image_url": {"url": img}})

    for img in analog_images:
        content.append({"type": "image_url", "image_url": {"url": img}})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты профессиональный аналитик недвижимости. Пиши по-русски, конкретно и практично."
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=2500
        )

        answer = response.choices[0].message.content

        for i in range(0, len(answer), 3500):
            await update.message.reply_text(answer[i:i + 3500])

        pdf_path = create_pdf_report(answer)
        await update.message.reply_document(
            document=open(pdf_path, "rb"),
            filename="AI_Realty_CMA_Report.pdf"
        )

    except Exception as e:
        await update.message.reply_text(f"Ошибка формирования отчета: {e}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("object", object_mode))
    app.add_handler(CommandHandler("analog", analog_mode))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("clear", clear))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
