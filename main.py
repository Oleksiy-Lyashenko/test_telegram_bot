import asyncio
import os
import logging

from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, types
from openai import OpenAI

load_dotenv()

openai_token = os.environ.get("OPENAI_API_KEY")
bot_token = os.environ.get("API_TOKEN")

bot = Bot(token=bot_token)
dp = Dispatcher()

router = Router()

dp.include_router(router)

client = OpenAI(
  api_key=openai_token,
)

locations = [f"Локація {number}" for number in range(1, 6)]

checklist_items = [f"Пункт {number}" for number in range(1, 6)]

user_data = {}

messages = []


# Формує запит та відправляє в openai
def start_chat_gpt(request, messages):
    try:
        message = str(request)

        messages.append({"role": "user", "content": message})

        chat = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )

        answer = chat.choices[0].message.content

        messages.append({"role": "assistant", "content": answer})

        return answer
    except Exception as e:
        logging.error(e)


# Початкова стрічка /start, яка зразу дає змогу вибрати локацію зі списку
@router.message(CommandStart())
async def command_start_handler(message: Message):
    user_id = message.from_user.id

    user_data[user_id] = {"location": None, "checklist": None, "comment": None}

    await message.reply("Привіт! Я бот для проведення чек-листа. Оберіть локацію:",
                        reply_markup=types.ReplyKeyboardMarkup(
                            keyboard=[
                                [types.KeyboardButton(text=location) for location in locations]
                            ],
                            resize_keyboard=True
                        ))

# Після вибору локації записує в словник дані про неї і відображає на екрані
@router.message(lambda message: message.text in locations)
async def choose_location(message: types.Message):
    user_id = message.from_user.id
    location = message.text
    user_data[user_id]["location"] = location

    await message.reply(f"Ви обрали локацію: {location}. Тепер перейдемо до чек-листа.",
                        reply_markup=types.ReplyKeyboardRemove())

    # Далі дає змогу вибрати із чекліста пункти
    await send_checklist(message.from_user.id)


# Функція яка створює чекліст
async def send_checklist(user_id):

    await bot.send_message(user_id, "Оберіть стан для кожного пункту чек-листа:",
                           reply_markup=types.ReplyKeyboardMarkup(
                               keyboard=[
                                   [types.KeyboardButton(text=item) for item in checklist_items]
                               ],
                               resize_keyboard=True
                           ))


# В кожного чекліста є вибір між "Все чисто" та "Залишити коментар"
@router.message(lambda message: message.text in checklist_items)
async def process_checklist_item(message: types.Message):
    user_id = message.from_user.id
    item = message.text
    user_data[user_id]["checklist"] = item

    await bot.send_message(user_id, f"Виберіть стан для '{item}':",
                           reply_markup=types.ReplyKeyboardMarkup(
                               keyboard=[
                                    [types.KeyboardButton(text="Все чисто"),
                                     types.KeyboardButton(text="Залишити коментар")
                                     ]
                               ],
                               resize_keyboard=True
                           ))


# Обробляє запит в залежності від вибору
# Якщо все чисто то повертає до вибору пункт або залишає коментар
@router.message(lambda message: message.text in ["Все чисто", "Залишити коментар"])
async def process_checklist_status(message: types.Message):
    user_id = message.from_user.id

    if message.text == "Залишити коментар":
        await chat_handler()
    else:
        await send_checklist(user_id)


# Після того як залишаєте коментар формує загальний ордер, відправляє на openai, відправляє відповідь
@router.message()
async def chat_handler(message: Message = ""):
    try:
        user_id = message.from_user.id

        loading_info = await message.answer("Обробляється запит")

        location = user_data[user_id]['location']
        checklist = user_data[user_id]["checklist"]
        comment = user_data[user_id]["comment"] = message.text

        if location and checklist:
            text = f"Локація: {location}\n Пункт: {checklist}\n Коментар: {comment}"
            text_answer = start_chat_gpt(text, messages)
        else:
            text_answer = start_chat_gpt(message.text, messages)

        await message.answer(text_answer)
        await bot.delete_message(message.chat.id, loading_info.message_id)
    except Exception as e:
        logging.error(e)


async def main():
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Errors: {e}")
