import asyncio
from pyrogram.errors import ChatAdminRequired
from pagermaid.listener import listener
from pagermaid.services import bot
from pagermaid.enums import Message


async def ban_user_and_notify(chat_id: int, user_id: int, message: Message, user_mention: str, chat_title: str):
    await bot.ban_chat_member(chat_id, user_id)
    await bot.delete_user_history(chat_id, user_id)
    text = f'用户 {user_mention} (`{user_id}`) 已在群组 {chat_title} (`{chat_id}`) 被封禁。'
    await message.edit(text)


@listener(
    command="nmsl",
    need_admin=True,
    groups_only=True,
)
async def super_ban(message: Message):
    reply = message.reply_to_message

    if not reply or not reply.from_user:
        await message.edit("必须回复目标消息")
        await asyncio.sleep(10)
        return await message.delete()

    uid = reply.from_user.id
    user_mention = reply.from_user.mention
    chat_title = message.chat.title

    try:
        await ban_user_and_notify(message.chat.id, uid, message, user_mention, chat_title)
    except ChatAdminRequired:
        await message.edit("没有足够的权限封禁用户")
    except Exception as e:
        await message.edit(f"出现错误：{e}")