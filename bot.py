import os
import json
import base64
import tempfile
from datetime import datetime
from html import escape

from openai import OpenAI
from PIL import Image as PILImage

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["📊 CMA / оценка объекта"],
        ["🖼 Улучшить фото объекта"],
        ["✍️ Описание объявления"],
        ["💬 Скрипт для продавца"],
        ["🧹 Очистить сессию"],
    ],
    resize_keyboard=True
)

PHOTO_MENU = ReplyKeyboardMarkup(
    [
        ["🧹 Убрать мусор и личные вещи"],
        ["💡 Улучшить свет и цвет"],
        ["🏡 Сделать фото продающим"],
        ["📱 Подготовить для Авито / ЦИАН"],
        ["⬅️ Назад в меню"],
    ],
    resize_keyboard=True
)


def init_session(context):
    context.user_data.setdefault("mode", "menu")
    context.user_data.setdefault("cma_stage", None)
    context.user_data.setdefault("object_texts", [])
    context.user_data.setdefault("analog_texts", [])
    context.user_data.setdefault("object_images", [])
    context.user_data.setdefault("analog_images", [])
    context.user_data.setdefault("photo_task", None)


def register_font():
    font_path = "DejaVuSans.ttf"
    font_name = "DejaVuSans"
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except Exception:
        return "Helvetica"


def safe_json_loads(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {
            "object_title": "Объект недвижимости",
            "object_summary": text,
            "recommended_price": "Недостаточно данных",
            "market_range": "Недостаточно данных",
            "sale_time": "Недостаточно данных",
            "price_per_m2": "Недостаточно данных",
            "liquidity": "Недостаточно данных",
            "analogs": [],
            "strengths": [],
            "weaknesses": [],
            "risks": [],
            "seller_message": "",
            "client_message": "",
            "final_recommendation": text
        }


def create_styled_pdf(data):
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    font = register_font()

    black = colors.HexColor("#111111")
    gold = colors.HexColor("#BEAF87")
    dark_gold = colors.HexColor("#9F854A")
    cream = colors.HexColor("#F7F4EE")
    light = colors.HexColor("#FFFFFF")
    gray = colors.HexColor("#666666")

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="C21Title", fontName=font, fontSize=20, leading=24, textColor=gold))
    styles.add(ParagraphStyle(name="Section", fontName=font, fontSize=13, leading=16, textColor=black, spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle(name="Body", fontName=font, fontSize=9.5, leading=13, textColor=black))
    styles.add(ParagraphStyle(name="Small", fontName=font, fontSize=8, leading=10, textColor=gray))
    styles.add(ParagraphStyle(name="Card", fontName=font, fontSize=9, leading=12, textColor=light))

    story = []

    if os.path.exists("Century-21-logo.png"):
        logo = Image("Century-21-logo.png", width=42 * mm, height=18 * mm)
    else:
        logo = Paragraph("CENTURY 21", styles["C21Title"])

    header = Table([
        [
            logo,
            Paragraph("CMA ОТЧЕТ<br/>Анализ рыночной стоимости объекта", styles["Body"])
        ]
    ], colWidths=[60 * mm, 110 * mm])

    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), black),
        ("TEXTCOLOR", (0, 0), (-1, -1), light),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(header)
    story.append(Spacer(1, 10))

    info = Table([
        [
            Paragraph(f"<b>Объект</b><br/>{escape(str(data.get('object_title', 'Объект')))}", styles["Body"]),
            Paragraph(f"<b>Цена за м²</b><br/>{escape(str(data.get('price_per_m2', '—')))}", styles["Body"]),
            Paragraph(f"<b>Дата отчета</b><br/>{datetime.now().strftime('%d.%m.%Y')}", styles["Body"]),
        ]
    ], colWidths=[75 * mm, 45 * mm, 45 * mm])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cream),
        ("BOX", (0, 0), (-1, -1), 0.5, gold),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, gold),
        ("PADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(info)

    story.append(Paragraph("Как цена влияет на привлечение покупателей", styles["Section"]))
    intro = (
        "Правильная цена — ключевой фактор быстрой и выгодной продажи. "
        "Завышенная цена снижает интерес покупателей, объявление теряет позиции, "
        "просмотры падают, а срок продажи увеличивается. Рыночная цена привлекает больше "
        "заинтересованных покупателей и повышает вероятность сделки."
    )
    story.append(Paragraph(intro, styles["Body"]))
    story.append(Spacer(1, 8))

    cards = Table([
        [
            Paragraph(f"РЕКОМЕНДУЕМАЯ ЦЕНА<br/><br/><b>{escape(str(data.get('recommended_price', '—')))}</b>", styles["Card"]),
            Paragraph(f"ДИАПАЗОН РЫНКА<br/><br/><b>{escape(str(data.get('market_range', '—')))}</b>", styles["Card"]),
            Paragraph(f"СРОК ПРОДАЖИ<br/><br/><b>{escape(str(data.get('sale_time', '—')))}</b>", styles["Body"]),
        ]
    ], colWidths=[55 * mm, 55 * mm, 55 * mm])
    cards.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), black),
        ("BACKGROUND", (1, 0), (1, 0), dark_gold),
        ("BACKGROUND", (2, 0), (2, 0), cream),
        ("BOX", (0, 0), (-1, -1), 0.5, gold),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cards)

    story.append(Paragraph("Краткое резюме объекта", styles["Section"]))
    story.append(Paragraph(escape(str(data.get("object_summary", ""))), styles["Body"]))

    analogs = data.get("analogs", [])
    if analogs:
        story.append(Paragraph("Анализ аналогов", styles["Section"]))
        table_data = [["№", "Объект", "Цена", "Площадь", "Цена за м²", "Комментарий"]]

        for i, a in enumerate(analogs[:10], 1):
            table_data.append([
                str(i),
                str(a.get("name", "Аналог")),
                str(a.get("price", "—")),
                str(a.get("area", "—")),
                str(a.get("price_per_m2", "—")),
                str(a.get("comment", "—")),
            ])

        analog_table = Table(table_data, colWidths=[9*mm, 38*mm, 28*mm, 24*mm, 28*mm, 38*mm])
        analog_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), black),
            ("TEXTCOLOR", (0, 0), (-1, 0), light),
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(analog_table)

    def bullet_block(title, items):
        if not items:
            return
        story.append(Paragraph(title, styles["Section"]))
        for item in items:
            story.append(Paragraph("• " + escape(str(item)), styles["Body"]))

    bullet_block("Сильные стороны", data.get("strengths", []))
    bullet_block("Слабые стороны", data.get("weaknesses", []))
    bullet_block("Риски", data.get("risks", []))

    story.append(Paragraph("Ликвидность", styles["Section"]))
    story.append(Paragraph(escape(str(data.get("liquidity", "—"))), styles["Body"]))

    story.append(Paragraph("Что сказать продавцу", styles["Section"]))
    story.append(Paragraph(escape(str(data.get("seller_message", "—"))), styles["Body"]))

    story.append(Paragraph("Текст для клиента простым языком", styles["Section"]))
    story.append(Paragraph(escape(str(data.get("client_message", "—"))), styles["Body"]))

    story.append(Paragraph("Итоговая рекомендация", styles["Section"]))
    story.append(Paragraph(escape(str(data.get("final_recommendation", "—"))), styles["Body"]))

    footer = Table([
        [Paragraph("Century 21 Russia · Ваша недвижимость — наша экспертиза", styles["Small"])]
    ], colWidths=[170 * mm])
    footer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), black),
        ("TEXTCOLOR", (0, 0), (-1, -1), gold),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(Spacer(1, 12))
    story.append(footer)

    doc.build(story)
    return path


def photo_prompt(task):
    base = """
Отредактируй фото недвижимости реалистично.
Не меняй планировку, окна, стены, двери, вид из окна, площадь, форму помещения и реальные свойства объекта.
Не добавляй несуществующую мебель.
Сохрани честный вид объекта.
"""

    if task == "clean":
        return base + "Убери мусор, пакеты, коробки, личные вещи, провода и лишние предметы."
    if task == "light":
        return base + "Улучши свет, цвет, баланс белого, резкость и общее качество фото."
    if task == "selling":
        return base + "Сделай фото более продающим: чище, светлее, аккуратнее, без визуального хаоса."
    if task == "listing":
        return base + "Подготовь фото для Авито, ЦИАН и Домклик: светлое, чистое, ровное, привлекательное."
    return base


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    await update.message.reply_text("Выбери функцию:", reply_markup=MAIN_MENU)


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    init_session(context)
    await update.message.reply_text("Сессия очищена.", reply_markup=MAIN_MENU)


async def object_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    context.user_data["mode"] = "cma"
    context.user_data["cma_stage"] = "object"
    await update.message.reply_text("Режим основного объекта. Отправь текст или скриншот объекта.")


async def analog_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    context.user_data["mode"] = "cma"
    context.user_data["cma_stage"] = "analog"
    await update.message.reply_text("Режим аналогов. Отправь 3–10 аналогов текстом или скриншотами.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)
    text = update.message.text

    if text == "📊 CMA / оценка объекта":
        context.user_data["mode"] = "cma"
        context.user_data["cma_stage"] = "object"
        await update.message.reply_text(
            "CMA включен.\n\n"
            "Шаг 1: отправь основной объект.\n"
            "Потом нажми /analog и отправь аналоги.\n"
            "Когда всё загрузишь — нажми /report."
        )
        return

    if text == "🖼 Улучшить фото объекта":
        context.user_data["mode"] = "photo"
        context.user_data["photo_task"] = None
        await update.message.reply_text("Выбери, что сделать с фото:", reply_markup=PHOTO_MENU)
        return

    if text == "✍️ Описание объявления":
        context.user_data["mode"] = "description"
        await update.message.reply_text("Пришли данные объекта — сделаю продающее описание.")
        return

    if text == "💬 Скрипт для продавца":
        context.user_data["mode"] = "script"
        await update.message.reply_text("Пришли ситуацию — сделаю скрипт для продавца.")
        return

    if text == "🧹 Очистить сессию":
        await clear(update, context)
        return

    if text == "⬅️ Назад в меню":
        context.user_data["mode"] = "menu"
        await update.message.reply_text("Главное меню:", reply_markup=MAIN_MENU)
        return

    photo_tasks = {
        "🧹 Убрать мусор и личные вещи": "clean",
        "💡 Улучшить свет и цвет": "light",
        "🏡 Сделать фото продающим": "selling",
        "📱 Подготовить для Авито / ЦИАН": "listing",
    }

    if text in photo_tasks:
        context.user_data["mode"] = "photo"
        context.user_data["photo_task"] = photo_tasks[text]
        await update.message.reply_text("Теперь отправь фото объекта.", reply_markup=PHOTO_MENU)
        return

    mode = context.user_data.get("mode")

    if mode == "cma":
        stage = context.user_data.get("cma_stage")
        if stage == "object":
            context.user_data["object_texts"].append(text)
            await update.message.reply_text("Основной объект добавлен. Теперь /analog")
        elif stage == "analog":
            context.user_data["analog_texts"].append(text)
            await update.message.reply_text(f"Аналог добавлен. Всего текстовых аналогов: {len(context.user_data['analog_texts'])}")
        else:
            await update.message.reply_text("Выбери /object или /analog")
        return

    if mode == "description":
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Ты пишешь сильные продающие описания недвижимости."},
                {"role": "user", "content": f"Сделай продающее описание объявления:\n{text}"}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
        return

    if mode == "script":
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Ты бизнес-тренер Century 21 и эксперт по переговорам с продавцами."},
                {"role": "user", "content": f"Сделай скрипт разговора с продавцом:\n{text}"}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
        return

    await update.message.reply_text("Выбери функцию:", reply_markup=MAIN_MENU)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)

    mode = context.user_data.get("mode")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    if mode == "cma":
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{image_base64}"

        if context.user_data.get("cma_stage") == "object":
            context.user_data["object_images"].append(image_url)
            await update.message.reply_text("Скриншот основного объекта добавлен. Теперь /analog")
        elif context.user_data.get("cma_stage") == "analog":
            context.user_data["analog_images"].append(image_url)
            await update.message.reply_text(f"Скриншот аналога добавлен. Всего: {len(context.user_data['analog_images'])}")
        else:
            await update.message.reply_text("Сначала выбери /object или /analog")
        return

    if mode == "photo":
        task = context.user_data.get("photo_task")
        if not task:
            await update.message.reply_text("Сначала выбери действие для фото.", reply_markup=PHOTO_MENU)
            return

        await update.message.reply_text("Фото принято. Обрабатываю 30–120 секунд...")

        input_jpg = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
        input_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        output_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name

        with open(input_jpg, "wb") as f:
            f.write(image_bytes)

        img = PILImage.open(input_jpg).convert("RGBA")
        img.save(input_png)

        try:
            result = client.images.edit(
                model="gpt-image-1",
                image=open(input_png, "rb"),
                prompt=photo_prompt(task),
                size="1024x1024"
            )

            result_bytes = base64.b64decode(result.data[0].b64_json)

            with open(output_png, "wb") as f:
                f.write(result_bytes)

            await update.message.reply_document(
                document=open(output_png, "rb"),
                filename="C21_AI_photo_ready.png",
                caption="Готово. Фото улучшено."
            )

        except Exception as e:
            await update.message.reply_text(f"Ошибка обработки фото: {e}")
        return

    await update.message.reply_text("Сначала выбери функцию:", reply_markup=MAIN_MENU)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_session(context)

    if not context.user_data.get("object_texts") and not context.user_data.get("object_images"):
        await update.message.reply_text("Нет основного объекта. Нажми /object и отправь объект.")
        return

    await update.message.reply_text("Формирую CMA-анализ и PDF...")

    object_texts = context.user_data.get("object_texts", [])
    analog_texts = context.user_data.get("analog_texts", [])
    object_images = context.user_data.get("object_images", [])
    analog_images = context.user_data.get("analog_images", [])

    prompt = f"""
Ты ТОП-аналитик рынка недвижимости России и эксперт Century 21.

На основе основного объекта и аналогов сделай CMA-анализ.

ВАЖНО:
- Не придумывай данные.
- Все расчеты делай только на основе переданных данных.
- Если данных недостаточно — так и пиши.
- Верни ответ строго в JSON.

Основной объект:
{chr(10).join(object_texts)}

Аналоги:
{chr(10).join(analog_texts)}

Структура JSON:
{{
  "object_title": "...",
  "object_summary": "...",
  "recommended_price": "...",
  "market_range": "...",
  "sale_time": "...",
  "price_per_m2": "...",
  "liquidity": "...",
  "analogs": [
    {{
      "name": "...",
      "price": "...",
      "area": "...",
      "price_per_m2": "...",
      "comment": "..."
    }}
  ],
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "risks": ["...", "..."],
  "seller_message": "...",
  "client_message": "...",
  "final_recommendation": "..."
}}
"""

    content = [{"type": "text", "text": prompt}]

    for img in object_images:
        content.append({"type": "image_url", "image_url": {"url": img}})

    for img in analog_images:
        content.append({"type": "image_url", "image_url": {"url": img}})

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Ты профессиональный CMA-аналитик недвижимости. Отвечай строго JSON."},
                {"role": "user", "content": content}
            ],
            max_tokens=3000
        )

        raw_answer = response.choices[0].message.content
        data = safe_json_loads(raw_answer)

        await update.message.reply_text(
            f"Рекомендованная цена: {data.get('recommended_price', '—')}\n"
            f"Диапазон рынка: {data.get('market_range', '—')}\n"
            f"Цена за м²: {data.get('price_per_m2', '—')}\n"
            f"Ликвидность: {data.get('liquidity', '—')}\n"
            f"Срок продажи: {data.get('sale_time', '—')}\n\n"
            f"Итог: {data.get('final_recommendation', '—')}"
        )

        pdf_path = create_styled_pdf(data)

        await update.message.reply_document(
            document=open(pdf_path, "rb"),
            filename="Century21_CMA_Report.pdf"
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

    print("BOT STARTED")
    app.run_polling()


if __name__ == "__main__":
    main()
