import logging
import json
import asyncio
from web import keep_alive
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, ChatMemberUpdatedFilter
from aiogram.types import ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN, ADMIN_ID, ADMIN_USERNAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Загрузка данных
def load_links():
    try:
        with open("links.json", "r") as f:
            return json.load(f)
    except:
        return {}


def save_links(links):
    with open("links.json", "w") as f:
        json.dump(links, f, indent=2)


def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except:
        return {"required_channels": []}


def save_config(config):
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)


# Инициализация данных
links = load_links()
config = load_config()
required_channels = config.get("required_channels", [])

bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# Проверка подписки на каналы
async def check_subscriptions(user_id: int):
    if not required_channels:
        return True

    for channel in required_channels:
        try:
            member = await bot.get_chat_member(chat_id=channel,
                                               user_id=user_id)
            if member.status not in [
                    types.ChatMemberStatus.MEMBER,
                    types.ChatMemberStatus.ADMINISTRATOR,
                    types.ChatMemberStatus.CREATOR
            ]:
                return False
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            continue
    return True


# ========= ОБРАБОТЧИКИ ДЛЯ ГРУПП =========
@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_message_handler(message: types.Message):
    if await check_subscriptions(message.from_user.id):
        return

    await message.delete()
    await message.answer(
        f"❌ {message.from_user.mention_html()}, подпишитесь на все каналы!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Подписаться",
                                     callback_data="check_subscription")
            ],
                             [
                                 InlineKeyboardButton(
                                     text="Актуальные ссылки",
                                     callback_data="show_links")
                             ]]))


@dp.chat_join_request()
async def approve_join_request(chat_join: ChatJoinRequest):
    await chat_join.approve()
    await bot.send_message(
        chat_id=chat_join.from_user.id,
        text="Добро пожаловать! Для доступа к чату:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"Канал {i+1}", url=url)
        ] for i, url in enumerate(required_channels)] + [[
            InlineKeyboardButton(text="✅ Проверить подписку",
                                 callback_data="check_subscription")
        ], [InlineKeyboardButton(text="Ссылки", callback_data="show_links")]]))


# ========= ОСНОВНЫЕ КОМАНДЫ =========
@dp.message(Command("start"))
async def start_command(message: types.Message):
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Актуальные ссылки",
                                 callback_data="show_links")
        ],
                         [
                             InlineKeyboardButton(text="Связаться с админом",
                                                  url=f"t.me/{ADMIN_USERNAME}")
                         ]])
    await message.answer("👋 Я бот-хранитель. Выберите действие:",
                         reply_markup=markup)


# ========= CALLBACK HANDLERS =========
@dp.callback_query(F.data == "show_links")
async def show_links_handler(callback: types.CallbackQuery):
    if not links:
        return await callback.answer("Ссылок пока нет!", show_alert=True)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=name, url=url)]
                         for name, url in links.items()])

    msg = await callback.message.answer("🔗 Актуальные ссылки:",
                                        reply_markup=markup)
    await asyncio.sleep(30)
    await msg.delete()
    await callback.answer()


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: types.CallbackQuery):
    if await check_subscriptions(callback.from_user.id):
        await callback.answer("Доступ разрешён! ✅")
        await callback.message.delete()
    else:
        await callback.answer("Подпишитесь на все каналы! ❌", show_alert=True)


# ========= АДМИН-КОМАНДЫ =========
@dp.message(Command("links"))
async def admin_links(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = "Сохранённые ссылки:\n" + "\n".join(f"{k}: {v}"
                                               for k, v in links.items())
    await message.answer(text or "Ссылок нет")


@dp.message(Command("add_channel"))
async def add_channel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    if len(message.text.split()) > 1:
        channel = message.text.split()[1]
        if channel not in required_channels:
            required_channels.append(channel)
            config["required_channels"] = required_channels
            save_config(config)
            await message.answer(f"Канал {channel} добавлен")


@dp.message(F.chat.type == ChatType.PRIVATE)
async def handle_admin_links(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    if " - " in message.text:
        try:
            name, url = message.text.split(" - ", 1)
            links[name.strip()] = url.strip()
            save_links(links)
            await message.answer("Ссылка сохранена! ✅")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
