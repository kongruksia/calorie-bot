import os
import anthropic
import base64
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
        f"🌟 *Hello {name}!*\n\n"
        f"🍽️ Welcome to your personal Calorie Counter Bot!\n\n"
        f"📸 *How to use:*\n"
        f"• Send a food photo → get detailed calorie & nutrition analysis\n"
        f"• Track your daily intake\n"
        f"• Set your calorie goal\n"
        f"• View meal history\n\n"
        f"Let's crush your goals today! 💪🔥",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text("🔍 Analyzing your food... 🤖✨")

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
                {"type": "text", "text": """Analyze this food image in English only.
Format exactly like this:

🍽️ FOOD DETECTED:
• [item] - [calories] kcal (Protein:[g]g Carbs:[g]g Fat:[g]g)

📊 TOTAL NUTRITION:
• Calories: [X] kcal
• Protein: [X]g | Carbs: [X]g | Fat: [X]g
• Fiber: [X]g | Sugar: [X]g

💡 HEALTH TIPS:
• [specific tip about this meal]
• [e.g. high in sodium, good protein source, etc.]
• [one suggestion to make it healthier]

⭐ HEALTHINESS SCORE: [X]/10"""}
            ]
        }]
    )

    result_text = response.content[0].text

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

    await update.message.reply_text(result_text)
    await update.message.reply_text(
        f"📈 *Today's Progress:*\n"
        f"{bar}\n"
        f"🔥 {total_today} / {goal} kcal\n"
        f"{'✅ Goal reached! Amazing work! 🎉' if remaining <= 0 else f'⚡ Remaining: {remaining} kcal'}",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    u = get_user(update.effective_user.id)

    if text == "📊 Today's Summary":
        if not u["today"]:
            await update.message.reply_text(
                "🍽️ No meals logged today!\n\n📸 Send a food photo to get started! 💪",
                reply_markup=main_menu()
            )
        else:
            total = sum(m["calories"] for m in u["today"])
            goal = u["goal"]
            remaining = goal - total
            bar = "🟩" * min(10, int(total/goal*10)) + "⬜" * max(0, 10-int(total/goal*10))
            meals_text = "\n".join([f"• {m['time']} - {m['calories']} kcal" for m in u["today"]])
            await update.message.reply_text(
                f"📊 *Today's Summary*\n\n"
                f"{meals_text}\n\n"
                f"{bar}\n"
                f"🔥 Total: {total} / {goal} kcal\n"
                f"{'🎉 Goal reached!' if remaining <= 0 else f'⚡ Remaining: {remaining} kcal'}",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )

    elif text == "🎯 Set Calorie Goal":
        await update.message.reply_text(
            f"🎯 Current goal: *{u['goal']} kcal*\n\n"
            f"Type your new daily calorie goal (e.g. 1800):",
            parse_mode="Markdown"
        )
        context.user_data["setting_goal"] = True

    elif text == "📅 Meal History":
        if not u["history"]:
            await update.message.reply_text(
                "📅 No history yet!\n\nKeep logging your meals! 💪",
                reply_markup=main_menu()
            )
        else:
            history_text = ""
            for day in u["history"][-5:]:
                total = sum(m["calories"] for m in day["meals"])
                history_text += f"📅 {day['date']}: {total} kcal ({len(day['meals'])} meals)\n"
            await update.message.reply_text(
                f"📅 *Last 5 Days:*\n\n{history_text}",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )

    elif text == "💡 Tips":
        await update.message.reply_text(
            "💡 *Healthy Eating Tips* 🌿\n\n"
            "1. 💧 Drink water before every meal\n"
            "2. 🥗 Fill half your plate with vegetables\n"
            "3. 🍚 Choose whole grains over refined carbs\n"
            "4. 🥩 Get enough protein to stay full longer\n"
            "5. 🏃 Exercise burns extra calories\n"
            "6. 😴 Poor sleep increases hunger hormones\n"
            "7. 🍽️ Eat slowly — it takes 20 min to feel full\n\n"
            "You got this! 💪🔥",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

    elif text == "🔄 Reset Today":
        u["today"] = []
        await update.message.reply_text(
            "🔄 Today's log has been reset! ✅\n\nFresh start! 💪",
            reply_markup=main_menu()
        )

    elif context.user_data.get("setting_goal"):
        try:
            new_goal = int(text)
            u["goal"] = new_goal
            context.user_data["setting_goal"] = False
            await update.message.reply_text(
                f"✅ Goal set to *{new_goal} kcal* 🎯\n\nLet's go! 💪🔥",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        except:
            await update.message.reply_text("❌ Please type a number only (e.g. 1800)")
    else:
        await update.message.reply_text(
            "📸 Send a food photo to analyze calories! 🍽️",
            reply_markup=main_menu()
        )

if __name__ == "__main__":
    app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()
