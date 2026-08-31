import os
import re
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from geopy.distance import geodesic

TOKEN = "8856238823:AAF8y5wp5kSSSMeHu-xyXTGW6yt7a8LDdQg"
MAX_DISTANCE_METERS = 30.0


async def extract_coords_from_url(url: str):
    """تتبع الروابط المختصرة لـ Google Maps واستخراج الإحداثيات منها بشكل لامتزامن"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, allow_redirects=True, timeout=10) as response:
                final_url = str(response.url)
                html_text = await response.text()

        match = re.search(r'([@-]?\d+\.\d+)[,\s]+([@-]?\d+\.\d+)', final_url)
        if match:
            lat = float(match.group(1).replace('@', ''))
            lon = float(match.group(2).replace('@', ''))
            return lat, lon

        text_match = re.search(r'\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]', html_text)
        if text_match:
            lat = float(text_match.group(1))
            lon = float(text_match.group(2))
            return lat, lon
    except Exception as e:
        print(f"❌ حدث خطأ أثناء فك رابط الخريطة: {e}")

    return None, None


def clean_fat_info(raw_text: str) -> str:
    """استخراج وتنظيف بيانات FBG و FAT"""
    if not raw_text:
        return "غير محدد"

    fbg_match = re.search(r'FBG[-_]?\d+', raw_text, re.IGNORECASE)
    fbg = fbg_match.group(0).upper() if fbg_match else ""

    fat_match = re.search(r'FAT\s*[\d\\[\]/-]+', raw_text, re.IGNORECASE)
    fat = ""
    if fat_match:
        fat = fat_match.group(0).upper().replace(" ", "")
    else:
        alt_fat = re.search(r'FAT\d+', raw_text, re.IGNORECASE)
        if alt_fat:
            fat = alt_fat.group(0).upper()

    if fbg and fat:
        return f"{fbg} ── {fat}"
    elif fbg:
        return fbg
    elif fat:
        return fat

    clean = re.sub(r'[/\\].*?[/\\]', ' ', raw_text)
    clean = re.sub(r'\.kml', '', clean, flags=re.IGNORECASE).strip()
    return clean if clean else "غير محدد"


def load_poles_from_kml(kml_file_path: str = "poles.kml") -> list:
    poles = []
    if not os.path.exists(kml_file_path):
        print(f"⚠️ الملف '{kml_file_path}' غير موجود!")
        return poles

    try:
        with open(kml_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        placemarks = re.findall(r"<Placemark.*?>.*?</Placemark>", content, re.DOTALL)

        for pm in placemarks:
            coords_match = re.search(r"<coordinates>(.*?)</coordinates>", pm, re.DOTALL)

            if coords_match:
                coords_text = coords_match.group(1).strip()
                first_coord = coords_text.split()[0]
                parts = first_coord.split(",")
                if len(parts) >= 2:
                    lon = float(parts[0])
                    lat = float(parts[1])

                    formatted_name = clean_fat_info(pm)
                    poles.append({"name": formatted_name, "lat": lat, "lon": lon, "raw_data": pm})
    except Exception as e:
        print(f"❌ حدث خطأ أثناء قراءة ملف KML: {e}")

    return poles


poles_data = load_poles_from_kml("poles.kml")
print(f"✅ تم تحميل {len(poles_data)} نقطة من ملف الخريطة بنجاح.")


def get_keyboard():
    keyboard = [
        [KeyboardButton("📍 مشاركة موقعي الحالي", request_location=True)],
        [KeyboardButton("ℹ️ تعليمات الاستخدام")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "أهلاً بك في بوت استعلام كابينات وأعمدة الألياف الضوئية! 🛰️\n\n"
        "يمكنك إرسال **موقعك**، **رابط خريطة**، **إحداثيات**، أو **اسم الكابينة/الفات** للبحث المباشر.\n\n"
        "اضغط على **ℹ️ تعليمات الاستخدام** بالأسفل لقراءة دليل الاستخدام المفصل."
    )
    await update.message.reply_text(
        welcome_msg, parse_mode="Markdown", reply_markup=get_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **دليل وتعليمات استخدام البوت:**\n\n"
        "1️⃣ **البحث بالموقع المباشر:**\n"
        "• اضغط على زر **'📍 مشاركة موقعي الحالي'** لمعرفة أقرب كابينة لك ضمن نطاق 30 متراً.\n\n"
        "2️⃣ **البحث برابط خرائط جوجل:**\n"
        "• أرسل أي رابط من Google Maps مثل:\n"
        "  `https://maps.app.goo.gl/aY2eZQMmhYT5cpJa9`\n\n"
        "3️⃣ **البحث بالإحداثيات المباشرة:**\n"
        "• أرسل الإحداثيات مثل:\n"
        "  `33.408272, 44.391286`\n\n"
        "4️⃣ **البحث باسم الكابينة أو الفات:**\n"
        "• يمكنك كتابة الكلمات مقسمة أو في أسطر متعددة مثل:\n"
        "  `FBG790` أو `FBG0790` أو `FAT10`\n"
        "  أو إرسالها معاً في رسالة واحدة."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_keyboard())


async def process_location(update: Update, target_lat: float, target_lon: float):
    if not poles_data:
        await update.message.reply_text("❌ لم يتم العثور على أي نقاط داخل ملف الخريطة.", reply_markup=get_keyboard())
        return

    target_loc = (target_lat, target_lon)
    closest_pole = None
    min_distance = float("inf")

    for pole in poles_data:
        pole_loc = (pole["lat"], pole["lon"])
        dist = geodesic(target_loc, pole_loc).meters
        if dist < min_distance:
            min_distance = dist
            closest_pole = pole

    if closest_pole and min_distance <= MAX_DISTANCE_METERS:
        dist_str = f"{min_distance:.1f} متر"
        maps_link = f"https://www.google.com/maps?q={closest_pole['lat']},{closest_pole['lon']}"

        response = (
            f"📍 **أقرب نقطة تغذية:**\n\n"
            f"🏷️ **البيانات:** `{closest_pole['name']}`\n"
            f"📏 **المسافة:** {dist_str}\n"
            f"🌐 **الإحداثيات:** `{closest_pole['lat']}, {closest_pole['lon']}`\n\n"
            f"🔗 [فتح الموقع على Google Maps]({maps_link})"
        )
        await update.message.reply_text(
            response, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=get_keyboard()
        )
    else:
        distance_info = f" (أقرب كابينة تبعد {min_distance:.1f} متر)" if closest_pole else ""
        await update.message.reply_text(
            f"⚠️ **لا توجد كابينة ضمن نطاق 30 متراً من موقعك.**{distance_info}",
            parse_mode="Markdown",
            reply_markup=get_keyboard()
        )


async def search_by_name(update: Update, text_query: str):
    tokens = [t.strip().upper() for t in re.split(r'[\s\n\r,]+', text_query) if t.strip()]

    if not tokens:
        return

    matched_results = []

    for pole in poles_data:
        pole_text = (pole["name"] + " " + pole["raw_data"]).upper()

        match_all = True
        for token in tokens:
            if token.startswith("FBG"):
                num_part = token.replace("FBG", "").strip("-_")
                if num_part.isdigit():
                    num_val = int(num_part)
                    pattern = rf'FBG[-_]?0*{num_val}\b'
                    if not re.search(pattern, pole_text, re.IGNORECASE):
                        match_all = False
                        break
                elif token not in pole_text:
                    match_all = False
                    break
            elif token not in pole_text:
                match_all = False
                break

        if match_all:
            matched_results.append(pole)

    if not matched_results:
        await update.message.reply_text(
            f"❌ لم يتم العثور على أي نتائج تطابق:\n`{text_query}`", parse_mode="Markdown", reply_markup=get_keyboard()
        )
        return

    count = len(matched_results)
    response = f"🔍 **تم العثور على {count} نتيجة:**\n\n"

    for pole in matched_results[:5]:
        maps_link = f"https://www.google.com/maps?q={pole['lat']},{pole['lon']}"
        response += (
            f"🏷️ **البيانات:** `{pole['name']}`\n"
            f"🌐 **الإحداثيات:** `{pole['lat']}, {pole['lon']}`\n"
            f"🔗 [عرض على Google Maps]({maps_link})\n"
            f"───────────────\n"
        )

    if count > 5:
        response += f"⚠️ تم عرض أول 5 نتائج فقط من أصل {count}."

    await update.message.reply_text(
        response, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=get_keyboard()
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_lat = update.message.location.latitude
    target_lon = update.message.location.longitude
    await process_location(update, target_lat, target_lon)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # 1. التعرف المباشر على التعليمات عند كتابة أي من هذه الكلمات
    if any(k in text.lower() for k in ["تعليمات", "استخدام", "شرح", "help", "مساعدة", "تعليمات الاستخدام"]):
        await help_command(update, context)
        return

    # 2. فحص روابط الخرائط
    if "goo.gl" in text or "google.com/maps" in text or "maps" in text:
        url_match = re.search(r'https?://[^\s]+', text)
        if url_match:
            url = url_match.group(0)
            await update.message.reply_text("⏳ جاري تحليل رابط الموقع واستخراج الإحداثيات...")
            lat, lon = await extract_coords_from_url(url)
            if lat and lon:
                await process_location(update, lat, lon)
                return
            else:
                await update.message.reply_text("❌ تعذر استخراج الإحداثيات من الرابط المرسل.", reply_markup=get_keyboard())
                return

    # 3. فحص الإحداثيات النصية
    coords_match = re.match(r'^[-+]?\d+\.\d+[\s,]+[-+]?\d+\.\d+$', text)
    if coords_match:
        parts = text.replace(",", " ").split()
        lat = float(parts[0])
        lon = float(parts[1])
        await process_location(update, lat, lon)
        return

    # 4. البحث بالمسميات
    await search_by_name(update, text)


def main():
    print("🚀 جاري بدء تشغيل البوت...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
