import os
import logging
import json
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.enums import ContentType
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import Habit, Base, UserSettings  
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


BOT_TOKEN = "7730868913:AAGeQU-rSu0IpoXJqWt5qtjbQRDrcZ-OVks"
WEBAPP_URL = "https://habbiten-broker.amvera.io/"
TIMEZONE = "Europe/Moscow"


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=timezone(TIMEZONE))
engine = create_engine("sqlite:///habits.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Функция отправки напоминания
async def send_reminder(user_id: int, habit_id: int):
    session = Session()
    try:
        habit = session.get(Habit, habit_id)
        if habit and habit.enabled:
            user_settings = session.query(UserSettings).filter_by(user_id=str(user_id)).first()
            if user_settings and not user_settings.notifications_enabled:
                logging.info(f"Уведомления отключены для пользователя {user_id}")
                return

            kb = InlineKeyboardBuilder()
            kb.button(
                text="✅ Выполнено",
                web_app=types.WebAppInfo(url=WEBAPP_URL) 
            )
            kb.button(
                text="⏰ Отложить на 15 мин",
                callback_data=f"snooze_{habit_id}"
            )

            await bot.send_message(
                chat_id=user_id,
                text=f"⏰ Напоминание: {habit.name}",
                reply_markup=kb.as_markup()
            )
            logging.info(f"Напоминание отправлено пользователю {user_id} для привычки {habit.name}")
        else:
            logging.warning(f"Привычка {habit_id} не найдена или отключена")
    except Exception as e:
        logging.error(f"Ошибка отправки напоминания: {e}")
    finally:
        session.close()


async def schedule_habits(user_id: str):
    session = Session()
    try:
        for job in scheduler.get_jobs():
            if job.id.startswith(f"habit_{user_id}_"):
                job.remove()

        habits = session.query(Habit).filter(
            Habit.user_id == user_id,
            Habit.enabled == True
        ).all()

        for habit in habits:
            dt = datetime.datetime.combine(datetime.date.today(), habit.time)
            aware_dt = timezone(TIMEZONE).localize(dt)

            scheduler.add_job(
                send_reminder,
                'cron',
                hour=aware_dt.hour,
                minute=aware_dt.minute,
                args=[int(user_id), habit.id],
                id=f"habit_{user_id}_{habit.id}",  
                replace_existing=True
            )
            logging.info(f"Запланировано напоминание для {habit.name} в {aware_dt}")
    except Exception as e:
        logging.error(f"Ошибка планирования привычек: {e}")
    finally:
        session.close()


@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    session = Session()
    try:
        if not session.query(UserSettings).filter_by(user_id=user_id).first():
            session.add(UserSettings(user_id=user_id))
            session.commit()

        builder = ReplyKeyboardBuilder()
        builder.add(types.KeyboardButton(
            text="📊 Мои привычки",
            web_app=types.WebAppInfo(url=WEBAPP_URL)
        ))
        builder.add(types.KeyboardButton(text="⚙️ Настройки"))

        await message.answer(
            "Привет! Я помогу тебе сформировать полезные привычки.\n\n"
            "Нажми кнопку ниже, чтобы открыть трекер:",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )

        await schedule_habits(user_id)
    finally:
        session.close()


@dp.message(F.text == "⚙️ Настройки")
async def settings(message: types.Message):
    user_id = str(message.from_user.id)
    session = Session()
    try:
        settings = session.query(UserSettings).filter_by(user_id=user_id).first()

        builder = InlineKeyboardBuilder()
        builder.button(
            text=f"🔔 Уведомления: {'Вкл' if settings.notifications_enabled else 'Выкл'}",
            callback_data="toggle_notifications"
        )
        builder.button(
            text="🕒 Изменить часовой пояс",
            callback_data="change_timezone"
        )
        builder.adjust(1)

        await message.answer(
            "⚙️ Настройки трекера привычек:",
            reply_markup=builder.as_markup()
        )
    finally:
        session.close()


@dp.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    session = Session()
    try:
        settings = session.query(UserSettings).filter_by(user_id=user_id).first()
        settings.notifications_enabled = not settings.notifications_enabled
        session.commit()

        builder = InlineKeyboardBuilder()
        builder.button(
            text=f"🔔 Уведомления: {'Вкл' if settings.notifications_enabled else 'Выкл'}",
            callback_data="toggle_notifications"
        )
        builder.button(
            text="🕒 Изменить часовой пояс",
            callback_data="change_timezone"
        )
        builder.adjust(1)

        await callback.answer(f"Уведомления {'включены' if settings.notifications_enabled else 'выключены'}")
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    finally:
        session.close()


@dp.callback_query(F.data.startswith("done_"))
async def mark_as_done(callback: types.CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    user_id = str(callback.from_user.id)
    session = Session()
    try:
        habit = session.get(Habit, habit_id)
        if habit:
            habit.completed_count += 1
            habit.last_completed = datetime.datetime.now()
            session.commit()

            await callback.answer("Привычка отмечена как выполненная!")
            await callback.message.delete()
    finally:
        session.close()

@dp.message(Command("sync"))
async def sync_habits(message: types.Message):
    user_id = str(message.from_user.id)
    session = Session()
    try:
        habits = session.query(Habit).filter_by(user_id=user_id).all()
        habits_data = [
            {
                "id": habit.id,
                "name": habit.name,
                "time": habit.time.strftime("%H:%M"),
                "progress": habit.completed_count
            }
            for habit in habits
        ]
        await message.answer(
            text="Синхронизация завершена",
            web_app=types.WebAppInfo(url=f"{WEBAPP_URL}?sync={json.dumps(habits_data)}")
        )
    finally:
        session.close()


@dp.callback_query(F.data.startswith("snooze_"))
async def snooze_reminder(callback: types.CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    user_id = str(callback.from_user.id)

    await callback.answer("Напоминание отложено на 15 минут")
    await callback.message.delete()

    scheduler.add_job(
        send_reminder,
        'date',
        run_date=datetime.datetime.now() + datetime.timedelta(minutes=15),
        args=[int(user_id), habit_id],
        id=f"snoozed_{habit_id}_{user_id}_{datetime.datetime.now().timestamp()}"
    )


@dp.message(lambda message: message.content_type == ContentType.WEB_APP_DATA)
async def handle_web_app_data(message: types.Message):
    logging.info(f"Получены данные из Web App: {message.web_app_data.data}")
    user_id = str(message.from_user.id)
    session = Session()
    try:
        data = json.loads(message.web_app_data.data)

        session.query(Habit).filter(Habit.user_id == user_id).delete()
        for habit_data in data:
            habit = Habit(
                user_id=user_id,
                name=habit_data["name"],
                time=datetime.datetime.strptime(habit_data["time"], "%H:%M").time(),
                enabled=True
            )
            session.add(habit)

        session.commit()
        await message.answer("✅ Привычки успешно сохранены! Буду напоминать вовремя :)")

        await schedule_habits(user_id)
    except Exception as e:
        logging.error(f"Ошибка обработки данных из Web App: {e}")
        await message.answer("❌ Произошла ошибка при сохранении привычек.")
    finally:
        session.close()

async def on_startup():
    if not scheduler.running:
        scheduler.start()
        logging.info("Scheduler started")

async def on_shutdown():
    if scheduler.running:
        scheduler.shutdown()
        logging.info("Scheduler stopped")

async def main():
    await on_startup()
    await dp.start_polling(bot)
    await on_shutdown()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())