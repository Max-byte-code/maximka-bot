import discord
from discord.ext import commands, tasks
import asyncio
import os
import random
import sys
import re
from datetime import datetime
import pytz
from dotenv import load_dotenv

# === ТОКЕН ТОЛЬКО ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("ОШИБКА: Переменная BOT_TOKEN не найдена! Укажи её в настройках хостинга.")
    sys.exit(1)

# === НАСТРОЙКИ ===
VOICE_CHANNEL_ID = 1439315533395792046
TEXT_CHANNEL_ID = 1148735325410185257
AUDIO_FILE = 'loop.mp3'
PHRASES_FILE = 'phrases.txt'

# === РАСПИСАНИЕ (МСК) ===
SEND_TIMES = [(10,30),(11,0),(11,30),(12,0),(15,0),(18,0),(18,35),(20,0),(22,0)]

# === БАЗОВЫЕ ФРАЗЫ (будут дополняться обучением) ===
RESPONSES = [
    "А Кексик что на это скажет?", "чушпан-баран", "Опа на пенис прыгнул",
    "Лошара", "Я нормальный пацан", "ты петух кстати", "Ну сосёшь ты и что?"
    # ← остальные фразы можно добавить сюда или они будут приходить от обучения
]

# === БУФЕР ===
MESSAGES_BUFFER_SIZE = 4
message_buffer = []

# === ID юзера: учимся + всегда отвечаем ===
TARGET_USER_ID = 509732478047485952

# === ИНТЕНТЫ ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# === ПРОВЕРКА ФАЙЛОВ (только локально) ===
if not os.path.exists(AUDIO_FILE):
    print(f"Предупреждение: {AUDIO_FILE} не найден (на хостинге будет без музыки)")

if not os.path.exists(PHRASES_FILE):
    print(f"Предупреждение: {PHRASES_FILE} не найден — расписание не будет работать")

def load_phrases():
    if not os.path.exists(PHRASES_FILE):
        return []
    with open(PHRASES_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

daily_phrases = load_phrases()

# === ГОЛОС + МУЗЫКА (без падений и спама) ===
voice_client = None

async def ensure_voice_connection():
    global voice_client
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if not channel:
        print("Голосовой канал не найден — музыка отключена")
        return

    while True:
        if not voice_client or not voice_client.is_connected():
            try:
                voice_client = await channel.connect(reconnect=True, timeout=10)
                print(f"Подключился к голосовому: {channel.name}")
                bot.loop.create_task(music_loop(voice_client))
            except Exception as e:
                print(f"Не удалось подключиться к голосу: {e}")
                await asyncio.sleep(15)
        await asyncio.sleep(10)

async def music_loop(vc):
    while True:
        if vc.is_connected() and not vc.is_playing():
            try:
                if not os.path.exists(AUDIO_FILE):
                    await asyncio.sleep(30)
                    continue
                source = discord.FFmpegPCMAudio(
                    AUDIO_FILE,
                    before_options="-stream_loop -1 -re",
                    options="-vn -b:a 128k"
                )
                vc.play(source)
                print("Музыка запущена и зациклена")
            except Exception as e:
                print(f"FFmpeg не найден или ошибка: {e}")
                await asyncio.sleep(60)  # не спамим
        await asyncio.sleep(5)

# === РАСПИСАНИЕ ===
@tasks.loop(seconds=30)
async def scheduled_messages():
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if not channel or not daily_phrases:
        return

    now = datetime.now(pytz.timezone('Europe/Moscow'))
    if (now.hour, now.minute) in SEND_TIMES:
        key = now.strftime("%Y-%m-%d-%H-%M")
        if not hasattr(scheduled_messages, "sent"):
            scheduled_messages.sent = set()
        if key not in scheduled_messages.sent:
            phrase = random.choice(daily_phrases)
            await channel.send(phrase)
            print(f"[РАСПИСАНИЕ] {now.strftime('%H:%M')} → {phrase}")
            scheduled_messages.sent.add(key)

@scheduled_messages.before_loop
async def before_scheduled():
    await bot.wait_until_ready()

# === ON READY ===
@bot.event
async def on_ready():
    print(f"Бот {bot.user} успешно запущен!")
    print(f"Обучаюсь и всегда отвечаю юзеру с ID: {TARGET_USER_ID}")
    bot.loop.create_task(ensure_voice_connection())
    scheduled_messages.start()

# === ОСНОВНАЯ ЛОГИКА СООБЩЕНИЙ ===
@bot.event
async def on_message(message):
    if message.author == bot.user or message.channel.id != TEXT_CHANNEL_ID:
        return await bot.process_commands(message)

    text = message.content.strip()

    # 1. Обучение
    if message.author.id == TARGET_USER_ID:
        if text and text not in RESPONSES and len(text) <= 500 and not text.startswith('!'):
            RESPONSES.append(text)
            print(f"ВЫУЧЕНО → {text} | Всего фраз: {len(RESPONSES)}")

        # 2. Всегда отвечаем этому юзеру
        response = random.choice(RESPONSES)
        try:
            await message.reply(response)
        except:
            await message.channel.send(response)

    # 3. Буфер для всех
    message_buffer.append(message)
    if len(message_buffer) > MESSAGES_BUFFER_SIZE:
        message_buffer.pop(0)

    if len(message_buffer) == MESSAGES_BUFFER_SIZE:
        target = random.choice(message_buffer)
        resp = random.choice(RESPONSES)
        try:
            await target.reply(resp)
        except:
            await message.channel.send(resp)
        message_buffer.clear()
        print("[БУФЕР] Сработал — ответ отправлен")

    await bot.process_commands(message)

# === КОНСОЛЬ БЕЗ СПАМА EOF (работает и на Railway) ===
async def console_loop():
    await bot.wait_until_ready()
    print("Консоль отключена на хостинге (это нормально)")

# === ЗАПУСК ===
print("Запускаю бота...")
bot.loop.create_task(console_loop())  # просто заглушка, чтобы не было EOF-спама
bot.run(TOKEN)
