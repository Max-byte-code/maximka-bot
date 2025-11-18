import discord
from discord.ext import commands, tasks
import asyncio
import os
import random
import sys
import re
from datetime import datetime, timedelta
import pytz

# === НАСТРОЙКИ ===
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("ОШИБКА: Токен не найден! Укажи BOT_TOKEN в переменных окружения.")
    exit()

VOICE_CHANNEL_ID = 1439315533395792046
TEXT_CHANNEL_ID = 1148735325410185257
AUDIO_FILE = 'loop.mp3'
PHRASES_FILE = 'phrases.txt'

# === ВРЕМЯ ОТПРАВКИ (по МСК) ===
SEND_TIMES = [
    (10, 30),
    (11, 0),
    (11, 30),
    (12, 0),
    (15, 0),
    (18, 0),
    (18, 35),
    (20, 0),
    (22, 0),
]

# === ФРАЗЫ ДЛЯ АВТООТВЕТЧИКА (ДИНАМИЧЕСКИЙ СПИСОК) ===
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

# === АВТООТВЕТЧИК: БУФЕР ===
MESSAGES_BUFFER_SIZE = 4
message_buffer = []
messages_count = 0

# === ТЕПЕРЬ ОБУЧАЕТСЯ ТОЛЬКО ОТ ЭТОГО ЮЗЕРА ===
LEARNING_USER_ID = 509732478047485952  # ← ИСПРАВЛЕНО: теперь учится от него

# === ТОТ ЖЕ ЮЗЕР — ВСЕГДА ПОЛУЧАЕТ ОТВЕТ (игнорируя буфер) ===
ALWAYS_REPLY_USER_ID = 509732478047485952  # ← один и тот же

# === ИНТЕНТЫ ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# === ПРОВЕРКА ФАЙЛОВ ===
if not os.path.exists(AUDIO_FILE):
    print(f"ОШИБКА: {AUDIO_FILE} не найден!")
    input("Нажми Enter...")
    exit()

if not os.path.exists(PHRASES_FILE):
    print(f"ОШИБКА: {PHRASES_FILE} не найден!")
    with open(PHRASES_FILE, 'w', encoding='utf-8') as f:
        f.write("Привет, это из phrases.txt!\n")
    print(f"Создан {PHRASES_FILE}. Добавь фразы!")
    input("Нажми Enter...")
    exit()

# === ЗАГРУЗКА ФРАЗ ДЛЯ РАСПИСАНИЯ ===
def load_phrases():
    with open(PHRASES_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

daily_phrases = load_phrases()

# === ГОЛОСОВОЙ КОНТРОЛЛЕР ===
voice_client = None

async def ensure_voice_connection():
    global voice_client
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if not channel:
        print("Ошибка: голосовой канал не найден!")
        return

    while True:
        if voice_client is None or not voice_client.is_connected():
            try:
                print("Подключаюсь к голосовому...")
                voice_client = await channel.connect(timeout=10, reconnect=True)
                print(f"Подключён: {channel.name}")
                bot.loop.create_task(music_loop(voice_client))
            except Exception as e:
                print(f"Ошибка: {e}")
                await asyncio.sleep(5)
        else:
            await asyncio.sleep(5)

async def music_loop(vc):
    while True:
        if vc.is_connected() and not vc.is_playing():
            try:
                audio = discord.FFmpegPCMAudio(
                    AUDIO_FILE,
                    before_options="-stream_loop -1 -re",
                    options="-vn -b:a 128k"
                )
                vc.play(audio)
                print("Музыка зациклена")
            except Exception as e:
                print(f"Ошибка воспроизведения: {e}")
        await asyncio.sleep(3)

# === РАСПИСАНИЕ (phrases.txt) ===
@tasks.loop(seconds=30)
async def scheduled_messages():
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if not channel:
        return

    msk = pytz.timezone('Europe/Moscow')
    now = datetime.now(msk)
    current_time = (now.hour, now.minute)

    if current_time in SEND_TIMES:
        today_key = now.strftime("%Y-%m-%d-%H-%M")
        if not hasattr(scheduled_messages, "sent_times"):
            scheduled_messages.sent_times = set()

        if today_key not in scheduled_messages.sent_times:
            if not daily_phrases:
                await channel.send("Фразы закончились!")
            else:
                phrase = random.choice(daily_phrases)
                await channel.send(phrase)
                print(f"[РАСПИСАНИЕ] {now.strftime('%H:%M')} МСК: {phrase}")
            scheduled_messages.sent_times.add(today_key)

@scheduled_messages.before_loop
async def before_scheduled():
    await bot.wait_until_ready()
    print("Расписание активно: 10:30, 11:00, 11:30, 12:00, 15:00, 18:00, 18:35, 20:00, 22:00 МСК")
    scheduled_messages.sent_times = set()

# === ON READY ===
@bot.event
async def on_ready():
    print(f'Бот {bot.user} онлайн!')
    text_channel = bot.get_channel(TEXT_CHANNEL_ID)
    print(f"Чат: {text_channel.name if text_channel else 'ID неверный!'}")
    print(f"Учусь на сообщениях от пользователя с ID: {LEARNING_USER_ID}")
    print(f"ВСЕГДА отвечаю пользователю с ID: {ALWAYS_REPLY_USER_ID}")

    bot.loop.create_task(ensure_voice_connection())
    bot.loop.create_task(console_loop())
    scheduled_messages.start()

# === АВТООТВЕТЧИК + ОБУЧЕНИЕ + ВСЕГДА ОТВЕТ ===
@bot.event
async def on_message(message):
    global messages_count, message_buffer

    if message.author == bot.user or message.channel.id != TEXT_CHANNEL_ID:
        await bot.process_commands(message)
        return

    # === 1. ОБУЧЕНИЕ: берём ВСЁ от нужного юзера ===
    if message.author.id == LEARNING_USER_ID:
        text = message.content.strip()
        if text and text not in RESPONSES and len(text) <= 500 and not text.startswith('!'):
            RESPONSES.append(text)
            print(f"ОБУЧЕНИЕ → Добавлена фраза: \"{text}\"")
            print(f"Всего фраз в RESPONSES: {len(RESPONSES)}")

    # === 2. ВСЕГДА отвечаем этому же юзеру (игнорируя буфер) ===
    if message.author.id == ALWAYS_REPLY_USER_ID:
        response = random.choice(RESPONSES)
        try:
            await message.reply(response)
            print(f"ВСЕГДА ОТВЕТ → {message.author}: {response}")
        except:
            await message.channel.send(response)

    # === 3. Обычный буфер (работает для всех, включая его) ===
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

# === КОНСОЛЬНЫЙ ВВОД (оставил как был) ===
def extract_id(text):
    match = re.search(r'(\d{17,19})', text)
    if match:
        try:
            return int(match.group(1))
        except:
            return None
    return None

async def console_loop():
    await bot.wait_until_ready()
    text_channel = bot.get_channel(TEXT_CHANNEL_ID)
    if not text_channel:
        return

    print("КОНСОЛЬ: !id <ID> текст | @ник | !буфер 5 | exit")

    while not bot.is_closed():
        try:
            msg = await asyncio.to_thread(input, "")
            if not msg.strip(): continue
            if msg.lower() == 'exit':
                print("Выключаю бота...")
                await bot.close()
                break

            if msg.lower().startswith('!буфер '):
                try:
                    new_size = int(msg[7:].strip())
                    if 1 <= new_size <= 100:
                        global MESSAGES_BUFFER_SIZE
                        MESSAGES_BUFFER_SIZE = new_size
                        message_buffer.clear()
                        messages_count = 0
                        print(f"[БУФЕР] Установлен: {MESSAGES_BUFFER_SIZE} сообщений")
                    else:
                        print("Ошибка: значение от 1 до 100")
                except ValueError:
                    print("Использование: !буфер 5")

            elif msg.lower().startswith('!id '):
                parts = msg[4:].strip().split(' ', 1)
                raw_id = parts[0]
                text = parts[1] if len(parts) > 1 else ""
                user_id = extract_id(raw_id)
                if user_id:
                    member = text_channel.guild.get_member(user_id)
                    if member:
                        await text_channel.send(f"{member.mention} {text}".strip())
                    else:
                        await text_channel.send(f"ID `{user_id}` не найден.")
                else:
                    await text_channel.send("ID не распознан!")

            elif msg.startswith('@'):
                username = msg[1:].strip()
                member = discord.utils.find(
                    lambda m: m.name.lower() == username.lower() or m.display_name.lower() == username.lower(),
                    text_channel.guild.members
                )
                if member:
                    await text_channel.send(member.mention)
                else:
                    await text_channel.send(msg)

            else:
                await text_channel.send(msg)

        except Exception as e:
            print(f"Ошибка: {e}")
        await asyncio.sleep(0.1)

# === ЗАПУСК ===
print("Запускаю бота...")
bot.run(TOKEN)