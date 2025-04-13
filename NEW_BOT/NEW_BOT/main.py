from flask import Flask, render_template
import threading
import asyncio
import bot  # Импортируем bot.py как модуль

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route("/")
def index():
    return render_template('index.html')

# Запуск aiogram-бота в отдельном потоке
def run_bot():
    asyncio.run(bot.main())  # bot.main() — это корутина, которую ты уже написал

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()  # Фоновый запуск бота
    app.run(debug=True, host="0.0.0.0", port=80)
