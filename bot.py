import os
import json
import base64
import tempfile
from datetime import datetime
from html import escape
 
import requests
import replicate
 
from openai import OpenAI
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
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
 
if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
 
client = OpenAI(api_key=OPENAI_API_KEY)
 
 
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["📊 CMA / оценка объекта"],
        ["🖼 Улучшить фото объекта"],
        ["👔 Деловой аватар агента"],
        ["✍️ Описание объявления"],
        ["💬 Скрипт для продавца"],
        ["🧹 Очистить сессию"],
    ],
    resize_keyboard=True
)
 
PHOTO_MENU = ReplyKeyboardMarkup(
    [
        ["✨ Улучшить фото"],
        ["🧹 Легкая очистка фото"],
        ["⬅️ Назад в меню"],
    ],
    resize_keyboard=True
)
 
AVATAR_MENU = ReplyKeyboardMarkup(
    [
        ["👔 Классический деловой стиль"],
        ["🏢 Century 21 стиль"],
        ["📸 Премиум бизнес-портрет"],
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
    context.user_data.setdefault("avatar_style", None)
 
 
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
        cleaned = text.replace("```json", "").replace("```", "").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        return json.loads(cleaned[start:end])
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
        [logo, Paragraph("CMA ОТЧЕТ<br/>Анализ рыночной стоимости объекта", styles["Body"])]
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
    story.append(Paragraph(
        "Правильная цена — ключевой фактор быстрой и выгодной продажи. "
        "Завышенная цена снижает интерес покупателей, объявление теряет позиции, "
        "просмотры падают, а срок продажи увеличивается. Рыночная цена привлекает больше "
        "заинтересованных покупателей и повышает вероятность сделки.",
        styles["Body"]
    ))
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
Ultra realistic professional real estate photo editing.
 
CRITICAL RULES:
- Keep the exact same room.
- Keep the same layout.
- Keep the same walls, windows, doors, floor, ceiling and furniture.
- Do not redesign the room.
- Do not remove large furniture.
- Do not change geometry.
- Do not create a new interior.
- The result must look like the same real property photo.
 
Goal: make the photo cleaner, brighter and more suitable for a real estate listing.
"""
 
    if task == "light":
        return base + """
Improve only:
- brightness
- white balance
- contrast
- sharpness
- color correction
- natural HDR look
 
Do not remove objects.
Do not change furniture.
Make it look like a professional real estate photo.
"""
 
    if task == "soft_clean":
        return base + """
Do light cleanup only:
- reduce visual mess
- make the desk and surfaces look neater
- remove or minimize small distracting items where possible
- slightly clean cables and small clutter
 
Do not remove large objects.
Do not remove furniture.
Do not change the room.
If an object is too large or complex, leave it unchanged.
"""
 
    return base
 
 
def avatar_prompt(style):
    base = """
Create a professional business portrait from the provided photo.

ABSOLUTE IDENTITY PRESERVATION RULES:
- Preserve the exact same real person.
- Preserve the person's gender exactly.
- Preserve the person's age range exactly.
- Preserve the exact facial identity.
- Preserve face shape, jawline, cheekbones and forehead.
- Preserve the same eyes, eye shape, eyebrows and gaze direction.
- Preserve the same nose, lips, mouth shape and natural expression.
- Preserve the same skin tone, natural skin texture, moles, scars and unique facial features.
- Preserve the same hairstyle, hair color, hairline and facial hair.
- Do not make the person more feminine or more masculine.
- Do not make the person younger or older.
- Do not beautify, glamorize, slim, reshape or redesign the face.
- Do not replace the person with another person.
- Do not create a model-like or stock-photo face.
- The output must be clearly recognizable as the same person from the input photo.

ALLOWED CHANGES ONLY:
- Business clothing.
- Background.
- Lighting.
- Framing.
- Slight professional photo polish.

PHOTO STYLE:
- Photorealistic corporate portrait.
- Natural realistic skin texture.
- Professional real estate agent profile photo.
- Clean, premium, trustworthy business look.
- No cartoon, no AI-art look, no glamour retouching.
"""

    if style == "classic":
        return base + """
STYLE VARIANT:
Classic business portrait.
Neutral clean background.
Dark business suit or smart business jacket.
White or light business shirt.
No tie unless it looks natural.
Realistic office / studio lighting.
Keep the same person and same face at all costs.
"""

    if style == "c21":
        return base + """
STYLE VARIANT:
Century 21 real estate agent portrait.
Premium black and gold corporate aesthetic.
Elegant business outfit.
Clean luxury office background.
Subtle Century 21 mood, but do not add fake logos or unreadable text.
Keep the same person and same face at all costs.
"""

    if style == "premium":
        return base + """
STYLE VARIANT:
High-end LinkedIn / business portrait.
Premium studio lighting.
Clean neutral background.
Dark suit or premium business jacket.
Confident but natural expression.
Sharp, realistic, professional.
Keep the same person and same face at all costs.
"""

    return base
 
 
def download_replicate_output(output):
    if isinstance(output, list):
        output = output[0]
 
    if hasattr(output, "read"):
        return output.read()
 
    output_str = str(output)
 
    if output_str.startswith("http"):
        r = requests.get(output_str, timeout=120)
        r.raise_for_status()
        return r.content
 
    raise ValueError(f"Не удалось получить файл результата от Replicate: {output_str}")
 
 
def run_flux_edit(input_path, prompt):
    with open(input_path, "rb") as image_file:
        try:
            return replicate.run(
                "black-forest-labs/flux-kontext-pro",
                input={
                    "input_image": image_file,
                    "prompt": prompt,
                    "output_format": "png"
                }
            )
        except Exception:
            image_file.seek(0)
            return replicate.run(
                "black-forest-labs/flux-kontext-pro",
                input={
                    "image": image_file,
                    "prompt": prompt,
                    "output_format": "png"
                }
            )
 
 
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
 
    if text == "👔 Деловой аватар агента":
        context.user_data["mode"] = "avatar"
        context.user_data["avatar_style"] = None
        await update.message.reply_text("Выбери стиль аватара:", reply_markup=AVATAR_MENU)
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
        "✨ Улучшить фото": "light",
        "🧹 Легкая очистка фото": "soft_clean",
    }
 
    if text in photo_tasks:
        context.user_data["mode"] = "photo"
        context.user_data["photo_task"] = photo_tasks[text]
        await update.message.reply_text("Теперь отправь фото объекта.", reply_markup=PHOTO_MENU)
        return
 
    avatar_tasks = {
        "👔 Классический деловой стиль": "classic",
        "🏢 Century 21 стиль": "c21",
        "📸 Премиум бизнес-портрет": "premium",
    }
 
    if text in avatar_tasks:
        context.user_data["mode"] = "avatar"
        context.user_data["avatar_style"] = avatar_tasks[text]
        await update.message.reply_text(
            "Теперь отправь фото агента.\n\n"
            "Важно: лучше фото анфас, хорошее освещение, лицо хорошо видно.",
            reply_markup=AVATAR_MENU
        )
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
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты пишешь сильные продающие описания недвижимости."},
                {"role": "user", "content": f"Сделай продающее описание объявления:\n{text}"}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
        return
 
    if mode == "script":
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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
 
        if not REPLICATE_API_TOKEN:
            await update.message.reply_text("Не найден REPLICATE_API_TOKEN в Railway Variables.")
            return
 
        await update.message.reply_text("Фото принято. Обрабатываю 30–120 секунд...")
 
        input_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
 
        with open(input_path, "wb") as f:
            f.write(image_bytes)
 
        try:
            output = run_flux_edit(input_path, photo_prompt(task))
            result_bytes = download_replicate_output(output)
 
            with open(output_path, "wb") as f:
                f.write(result_bytes)
 
            await update.message.reply_document(
                document=open(output_path, "rb"),
                filename="C21_AI_photo_ready.png",
                caption="Готово. Фото обработано."
            )
 
        except Exception as e:
            await update.message.reply_text(f"Ошибка обработки фото: {e}")
        return
 
    if mode == "avatar":
        style = context.user_data.get("avatar_style")
 
        if not style:
            await update.message.reply_text("Сначала выбери стиль аватара.", reply_markup=AVATAR_MENU)
            return
 
        if not REPLICATE_API_TOKEN:
            await update.message.reply_text("Не найден REPLICATE_API_TOKEN в Railway Variables.")
            return
 
        await update.message.reply_text("Фото принято. Делаю деловой аватар 30–120 секунд...")
 
        input_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
 
        with open(input_path, "wb") as f:
            f.write(image_bytes)
 
        try:
            output = run_flux_edit(input_path, avatar_prompt(style))
            result_bytes = download_replicate_output(output)
 
            with open(output_path, "wb") as f:
                f.write(result_bytes)
 
            await update.message.reply_document(
                document=open(output_path, "rb"),
                filename="C21_AI_business_avatar.png",
                caption="Готово. Проверь, что лицо и узнаваемость агента сохранены."
            )
 
        except Exception as e:
            await update.message.reply_text(f"Ошибка создания аватара: {e}")
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
            model="gpt-4o-mini",
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
