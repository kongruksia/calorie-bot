import os
import anthropic
import base64
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# In-memory storage
user_data = {}

def get_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "goal": 2000,
            "today": [],
            "history": [],
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    u = user_data[user_id]
    today = datetime.now().strftime("%Y-%m-%d")
    if u["date"] != today:
        if u["today"]:
            u["history"].append({"date": u["date"], "meals": u["today"]})
        u["today"] = []
        u["date"] = today
    return u

def main_menu():
    keyboard = [
        [KeyboardButton("📊 Today's Summary"), KeyboardButton("🎯 Set Calorie Goal")],
        [KeyboardButton("📅 Meal History"), KeyboardButton("💡 Tips")],
        [KeyboardButton("🔄 Reset Today")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"🌟 *สวัสดี {name}! / Hello {name}!*\n\n"
        f"🍽️ ยินดีต้อนรับสู่ Calorie Counter Bot!\n"
        f"Welcome to your personal Calorie Counter!\n\n"
        f"📸 *วิธีใช้ / How to use:*\n"
        f"• ส่งรูปอาหาร → วิเคราะห์แคลอรี่\n"
        f"• Send a food photo → get calorie analysis\n\n"
        f"Let's crush your goals today! 💪🔥",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text("🔍 กำลังวิเคราะห์อาหารของคุณ... / Analyzing your food... 🤖✨")
    
    photo = await update.message.photo[-1].get_file()
    file_bytes = await photo.download_as_bytearray()
    b64 = base64.standard_b64encode(file_bytes).decode()
    
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": """Analyze this food image and respond in BOTH English and Thai.
Format exactly like this:

🍽️ FOOD DETECTED / อาหารที่พบ:
• [item] - [calories] kcal (P:[g]g C:[g]g F:[g]g)

📊 TOTAL / รวม:
• Calories: [X] kcal
• Protein: [X]g | Carbs: [X]g | Fat: [X]g

💬 ENCOURAGEMENT:
[One fun motivating message in both Thai and English with emojis]"""}
            ]
        }]
    )
    
    result_text = response.content[0].text
    
    # Try to extract calories
    try:
        lines = result_text.split('\n')
        for line in lines:
            if 'Calories:' in line and 'kcal' in line:
                cal_str = line.split('Calories:')[1].split('kcal')[0].strip()
                calories = int(''.join(filter(str.isdigit, cal_str)))
                u["today"].append({
                    "time": datetime.now().strftime("%H:%M"),
                    "calories": calories,
                    "text": result_text[:50]
                })
                break
    except:
        pass
    
    total_today = sum(m["calories"] for m in u["today"])
    goal = u["goal"]
    remaining = goal - total_today
    bar = "🟩" * min(10, int(total_today/goal*10)) + "⬜" * max(0, 10-int(total_today/goal*10))
    
    await update.message.reply_text(result_text, parse_mode=None)
    await update.message.reply_text(
        f"📈 *วันนี้ / Today's Progress:*\n"
        f"{bar}\n"
        f"🔥 {total_today} / {goal} kcal\n"
        f"{'✅ เป้าหมายสำเร็จ! Goal reached! 🎉' if remaining <= 0 else f'⚡ เหลืออีก / Remaining: {remaining} kcal'}",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    u = get_user(update.effective_user.id)
    
    if text == "📊 Today's Summary":
        if not u["today"]:
            await update.message.reply_text(
                "🍽️ ยังไม่มีมื้ออาหารวันนี้!\nNo meals logged today!\n\n📸 Send a food photo to get started! 💪",
                reply_markup=main_menu()
            )
        else:
            total = sum(m["calories"] for m in u["today"])
            goal = u["goal"]
            remaining = goal - total
            bar = "🟩" * min(10, int(total/goal*10)) + "⬜" * max(0, 10-int(total/goal*10))
            meals_text = "\n".join([f"• {m['time']} - {m['calories']} kcal" for m in u["today"]])
            await update.message.reply_text(
                f"📊 *สรุปวันนี้ / Today's Summary*\n\n"
                f"{meals_text}\n\n"
                f"{bar}\n"
                f"🔥 Total: {total} / {goal} kcal\n"
                f"{'🎉 Goal reached!' if remaining <= 0 else f'⚡ Remaining: {remaining} kcal'}",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )

    elif text == "🎯 Set Calorie Goal":
        await update.message.reply_text(
            f"🎯 เป้าหมายปัจจุบัน / Current goal: *{u['goal']} kcal*\n\n"
            f"พิมพ์ตัวเลขแคลอรี่ที่ต้องการ\nType your new calorie goal (e.g. 1800):",
            parse_mode="Markdown"
        )
        context.user_data["setting_goal"] = True

    elif text == "📅 Meal History":
        if not u["history"]:
            await update.message.reply_text("📅 ยังไม่มีประวัติ / No history yet!\n\nKeep logging your meals! 💪", reply_markup=main_menu())
        else:
            history_text = ""
            for day in u["history"][-5:]:
                total = sum(m["calories"] for m in day["meals"])
                history_text += f"📅 {day['date']}: {total} kcal ({len(day['meals'])} meals)\n"
            await update.message.reply_text(f"📅 *Meal History:*\n\n{history_text}", parse_mode="Markdown", reply_markup=main_menu())

    elif text == "💡 Tips":
        await update.message.reply_text(
            "💡 *Healthy Tips / เคล็ดลับสุขภาพ* 🌿\n\n"
            "1. 💧 ดื่มน้ำก่อนกิน / Drink water before eating\n"
            "2. 🥗 กินผักให้มาก / Eat more vegetables\n"
            "3. 🍚 ลดข้าวขาว / Reduce white rice\n"
            "4. 🏃 ออกกำลังกาย 30 นาที/วัน / Exercise 30 min/day\n"
            "5. 😴 นอนหลับให้เพียงพอ / Sleep enough\n\n"
            "You got this! 💪🔥",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

    elif text == "🔄 Reset Today":
        u["today"] = []
        await update.message.reply_text("🔄 รีเซ็ตวันนี้แล้ว / Today's log has been reset! ✅", reply_markup=main_menu())

    elif context.user_data.get("setting_goal"):
        try:
            new_goal = int(text)
            u["goal"] = new_goal
            context.user_data["setting_goal"] = False
            await update.message.reply_text(
                f"✅ ตั้งเป้าหมายใหม่แล้ว!\nGoal set to *{new_goal} kcal* 🎯\n\nLet's go! 💪🔥",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        except:
            await update.message.reply_text("❌ กรุณาพิมพ์ตัวเลข / Please type a number (e.g. 1800)")
    else:
        await update.message.reply_text(
            "📸 ส่งรูปอาหารเพื่อวิเคราะห์แคลอรี่!\nSend a food photo to analyze calories! 🍽️",
            reply_markup=main_menu()
        )

if __name__ == "__main__":
    app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()
