import discord
from discord.ext import commands, tasks
import asyncio
import os
import random
import re
from datetime import datetime
import pytz
from dotenv import load_dotenv

# === ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ОШИБКА: Токен не найден! Укажи BOT_TOKEN в переменных окружения.")
    exit()

# === НАСТРОЙКИ ===
VOICE_CHANNEL_ID = 1439315533395792046
TEXT_CHANNEL_ID = 1148735325410185257
AUDIO_FILE = 'loop.mp3'
PHRASES_FILE = 'phrases.txt'

# === ВРЕМЯ ОТПРАВКИ (по МСК) — 100% ПРАВИЛЬНО ===
SEND_TIMES = [
    (10, 30),
    (11, 0),
    (11, 30),
    (12, 0),
    (15, 0),
    (18, 0),
    (18, 35),
    (20, 0),
    (20, 30),   # ← было (20:30) — это ломало весь бот
    (22, 0)
]

# === ВСЕ ТВОИ ФРАЗЫ — НИ ОДНА НЕ УДАЛЕНА ===
RESPONSES = [
    "А Кексик что на это скажет?", "чушпан-баран", "Опа на пенис прыгнул",
    "Со мной в постели стонать будешь", "Неплохо ты сосёшь", "А дрозд сын шлюхи кстати",
    "Я ебу тебя в очко потому что ты кличко", "мальчик ты кто такой? водочки нам налей мы домой летим",
    "А то что ты сосёшь, пацан это типа ничего?", "Маму проверь свою", "Кексик много что знает про тебя",
    "что ты за хуйню пишешь ебанат?", "У тебя вообще рот закрывается?", "А вы куда поехали вообще?",
    "я уже понял что вы лошки попущеные, пойду в гташке файтиться", "Ты даже срать не умеешь дебил",
    "Вы гомнососы вообще не зарывайтесь", "Чевойта", "Вот бы меня скорее в арене разбанили",
    "Маму дрозда шлюху в рот долблю", "ты петух кстати", "А почему у тебя во рту мой член",
    "А ты на пенисе", "Здарова пацан оближи мне пукан", "Кибер Максим и Кибер Кексик ебут тебя в сраку",
    "А почему я один в эту игру играю?", "А почему вы все бездарные твари ебаные?", " сосал?",
    "А Акиа петух например, понял?", "Ну сосёшь ты и что?", "Лошара", "Я нормальный пацан",
    "Узбеки спяяяяят", "Сегодня в Пермь еду", "Ты странно выёбываешься", "Что ты высираешь пацан",
    "Тебе надо компьютер выключать и спать ложиться", "Ты дебильный пацан", "А теперь в хуй мне это повтори",
    "Не выёбывайся я заболел", "Я его в рот ебал кстати", "А ты 5 правил кошерного еврея почитай"
]

# === БУФЕР ===
MESSAGES_BUFFER_SIZE = 4
message_buffer = []
messages_count = 0

# === ID ===
LEARNING_USER_ID = 509732478047485952
ALWAYS_REPLY_USER_ID = 509732478047485952

# === ИНТЕНТЫ (без voice_states — голос всё равно отключён) ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# === ЗАГРУЗКА ФРАЗ ИЗ ФАЙЛА ===
def load_phrases():
    if not os.path.exists(PHRASES_FILE):
        return []
    try:
        with open(PHRASES_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

daily_phrases = load_phrases()

# === ГОЛОС ОТКЛЮЧЁН НА RAILWAY (чтобы не было ошибки 4006) ===
# Если захочешь включить — просто раскомментируй на VPS
"""
async def ensure_voice_connection():
    ...
async def music_loop(vc):
    ...
"""

# === РАСПИСАНИЕ ===
@tasks.loop(seconds=30)
async def scheduled_messages():
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if not channel or not daily_phrases:
        return
    now = datetime.now(pytz.timezone('Europe/Moscow'))
    if (now.hour, now.minute) in SEND_TIMES:
        key = now.strftime("%Y-%m-%d-%H-%M")
        if not hasattr(scheduled_messages, "sent_times"):
            scheduled_messages.sent_times = set()
        if key not in scheduled_messages.sent_times:
            phrase = random.choice(daily_phrases)
            await channel.send(phrase)
            print(f"[РАСПИСАНИЕ] {now.strftime('%H:%M')} → {phrase}")
            scheduled_messages.sent_times.add(key)

@scheduled_messages.before_loop
async def before_scheduled():
    await bot.wait_until_ready()

# === ON READY ===
@bot.event
async def on_ready():
    print(f'Бот {bot.user} онлайн!')
    print(f"Учусь на сообщениях от пользователя с ID: {LEARNING_USER_ID}")
    print(f"ВСЕГДА отвечаю пользователю с ID: {ALWAYS_REPLY_USER_ID}")
    print("Голосовой канал отключён — Railway не поддерживает UDP (4006)")

    # bot.loop.create_task(ensure_voice_connection())  ← отключено навсегда на Railway
    scheduled_messages.start()

# === АВТООТВЕТЧИК + ОБУЧЕНИЕ + ВСЕГДА ОТВЕТ ===
@bot.event
async def on_message(message):
    global messages_count, message_buffer

    if message.author == bot.user or message.channel.id != TEXT_CHANNEL_ID:
        return await bot.process_commands(message)

    # 1. Обучение
    if message.author.id == LEARNING_USER_ID:
        text = message.content.strip()
        if text and text not in RESPONSES and len(text) <= 500 and not text.startswith('!'):
            RESPONSES.append(text)
            print(f"ОБУЧЕНИЕ → Добавлена фраза: \"{text}\"")
            print(f"Всего фраз в RESPONSES: {len(RESPONSES)}")

    # 2. Всегда отвечаем этому юзеру
    if message.author.id == ALWAYS_REPLY_USER_ID:
        response = random.choice(RESPONSES)
        try:
            await message.reply(response)
            print(f"ВСЕГДА ОТВЕТ → {message.author}: {response}")
        except:
            await message.channel.send(response)

    # 3. Буфер
    messages_count += 1
    message_buffer.append(message)
    if len(message_buffer) > MESSAGES_BUFFER_SIZE:
        message_buffer.pop(0)

    remaining = MESSAGES_BUFFER_SIZE - len(message_buffer)
    print(f"[СЧЁТЧИК] Сообщений: {len(message_buffer)} / {MESSAGES_BUFFER_SIZE} | Осталось: {remaining}")

    if len(message_buffer) == MESSAGES_BUFFER_SIZE:
        target = random.choice(message_buffer)
        response = random.choice(RESPONSES)
        try:
            await target.reply(response)
            print(f"[АВТООТВЕТ] → {target.author}: {response}")
        except:
            await message.channel.send(response)

        message_buffer.clear()
        messages_count = 0
        print("[СЧЁТЧИК] Буфер сброшен")

    await bot.process_commands(message)

# === ЗАПУСК ===
print("Запускаю бота...")
bot.run(TOKEN)
