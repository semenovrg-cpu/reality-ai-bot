import os
import tempfile
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

# =========================
# API
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["object_texts"] = []
    context.user_data["analog_texts"] = []

    await update.message.reply_text(
        "🏠 Отправьте:\n\n"
        "1. Основной объект\n"
        "2. Затем аналоги\n\n"
        "После этого напишите:\n"
        "/report"
    )

# =========================
# СОХРАНЕНИЕ ТЕКСТА
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if "object_texts" not in context.user_data:
        context.user_data["object_texts"] = []

    if "analog_texts" not in context.user_data:
        context.user_data["analog_texts"] = []

    # Первый объект = основной
    if len(context.user_data["object_texts"]) == 0:

        context.user_data["object_texts"].append(text)

        await update.message.reply_text(
            "✅ Основной объект сохранён.\n\n"
            "Теперь отправьте аналоги."
        )

    else:

        context.user_data["analog_texts"].append(text)

        await update.message.reply_text(
            f"✅ Аналог #{len(context.user_data['analog_texts'])} сохранён."
        )

# =========================
# PDF
# =========================

def create_pdf_report(text):

    path = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    ).name

    # =========================
    # ШРИФТ
    # =========================

    font_path = "DejaVuSans.ttf"
    font_name = "DejaVuSans"

    try:
        pdfmetrics.registerFont(
            TTFont(font_name, font_path)
        )
    except:
        font_name = "Helvetica"

    # =========================
    # ДОК
    # =========================

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=18,
        leftMargin=18,
        topMargin=18,
        bottomMargin=18
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="C21Title",
        fontName=font_name,
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#B08D57"),
        alignment=TA_CENTER,
        spaceAfter=16
    ))

    styles.add(ParagraphStyle(
        name="C21Heading",
        fontName=font_name,
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#B08D57"),
        spaceBefore=14,
        spaceAfter=8
    ))

    styles["BodyText"].fontName = font_name
    styles["BodyText"].fontSize = 10
    styles["BodyText"].leading = 16

    elements = []

    # =========================
    # ЛОГО
    # =========================

    logo = Image(
        "Century-21-logo.png",
        width=40 * mm,
        height=16 * mm
    )

    # =========================
    # HEADER
    # =========================

    header = Table([
        [
            logo,
            Paragraph(
                "<b>CMA ОТЧЕТ</b><br/><br/>"
                "Анализ рыночной стоимости объекта",
                styles["BodyText"]
            )
        ]
    ], colWidths=[60 * mm, 110 * mm])

    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    elements.append(header)
    elements.append(Spacer(1, 12))

    # =========================
    # ВВОДНЫЙ БЛОК
    # =========================

    intro = Table([[
        Paragraph(
            "Правильная цена объекта напрямую влияет "
            "на количество обращений, срок продажи "
            "и итоговую стоимость сделки. "
            "Переоцененные объекты теряют интерес "
            "покупателей уже в первые недели рекламы.",
            styles["BodyText"]
        )
    ]], colWidths=[170 * mm])

    intro.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F5")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#DDDDDD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    elements.append(intro)
    elements.append(Spacer(1, 14))

    # =========================
    # ТЕКСТ
    # =========================

    sections = text.split("\n")

    for line in sections:

        line = line.strip()

        if not line:
            continue

        # Заголовки
        if (
            line.startswith("1.")
            or line.startswith("2.")
            or line.startswith("3.")
            or line.startswith("4.")
            or line.startswith("5.")
            or line.startswith("6.")
            or line.startswith("7.")
            or line.startswith("8.")
            or line.startswith("9.")
            or line.startswith("10.")
            or line.startswith("11.")
            or line.startswith("12.")
            or line.startswith("13.")
        ):

            elements.append(Spacer(1, 10))

            elements.append(
                Paragraph(
                    line.replace("**", ""),
                    styles["C21Heading"]
                )
            )

            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=1,
                    color=colors.HexColor("#B08D57")
                )
            )

            elements.append(Spacer(1, 6))

        # Буллеты
        elif line.startswith("-"):

            bullet = line.replace("-", "•", 1)

            elements.append(
                Paragraph(
                    bullet,
                    styles["BodyText"]
                )
            )

            elements.append(Spacer(1, 4))

        # Обычный текст
        else:

            elements.append(
                Paragraph(
                    line.replace("**", ""),
                    styles["BodyText"]
                )
            )

            elements.append(Spacer(1, 6))

    # =========================
    # FOOTER
    # =========================

    elements.append(Spacer(1, 18))

    footer = Paragraph(
        "Century 21 AI • Аналитический отчет сформирован автоматически",
        ParagraphStyle(
            "footer",
            fontName=font_name,
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
    )

    elements.append(footer)

    # =========================
    # BUILD PDF
    # =========================

    doc.build(elements)

    return path

# =========================
# REPORT
# =========================

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("object_texts"):

        await update.message.reply_text(
            "❌ Нет основного объекта."
        )
        return

    main_object = context.user_data["object_texts"][0]
    analogs = context.user_data["analog_texts"]

    analogs_text = "\n\n".join(analogs)

    prompt = f"""
Ты профессиональный аналитик рынка недвижимости и эксперт Century 21.

Сделай профессиональный CMA-анализ объекта недвижимости.

=== ОСНОВНОЙ ОБЪЕКТ ===
{main_object}

=== АНАЛОГИ ===
{analogs_text}

Сделай отчет строго по структуре:

1. Краткое резюме основного объекта
2. Таблица сравнения аналогов
3. Средняя цена за м²
4. Диапазон рыночной цены
5. Насколько объект переоценен или недооценен
6. Ликвидность
7. Прогноз срока продажи
8. Что мешает продаже
9. Что усиливает продажу
10. Что агенту сказать продавцу
11. Что можно показать клиенту простым языком
12. Рекомендация по цене
13. Что нужно уточнить для более точной оценки

Пиши профессионально.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Ты эксперт Century 21 по недвижимости."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    result = response.choices[0].message.content

    pdf_path = create_pdf_report(result)

    await update.message.reply_document(
        document=open(pdf_path, "rb"),
        filename="AI_Realty_CMA_Report.pdf"
    )

# =========================
# RUN
# =========================

app = ApplicationBuilder().token(
    TELEGRAM_BOT_TOKEN
).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("report", report))

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    )
)

print("BOT STARTED")

app.run_polling()
