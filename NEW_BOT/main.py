import asyncio
from flask import Flask, render_template
from bot import bot, dp, main as bot_main 

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route("/")
def index():
    return render_template('index.html')

async def run_flask():

    from werkzeug.serving import run_simple
    await asyncio.get_event_loop().run_in_executor(None, lambda: run_simple("0.0.0.0", 80, app))

async def main():
    # Запускаем Flask и бота параллельно
    flask_task = asyncio.create_task(run_flask())
    bot_task = asyncio.create_task(bot_main())  
    await asyncio.gather(flask_task, bot_task)

if __name__ == "__main__":
    asyncio.run(main())