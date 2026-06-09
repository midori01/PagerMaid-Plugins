""" Module to automate message deletion. """

import traceback
from datetime import datetime, timedelta, timezone
from pagermaid.dependence import scheduler
from pagermaid.services import bot
from pagermaid.utils import logs

def get_status_emoji(hour):
    if 1 <= hour < 6:
        return "💤"
    elif 6 <= hour < 7:
        return "☀️"
    elif 7 <= hour < 8:
        return "💄"
    elif 8 <= hour < 9:
        return "🍳"
    elif 9 <= hour < 10:
        return "🪞"
    elif 10 <= hour < 11:
        return "🐟"
    elif 11 <= hour < 12:
        return "💅"
    elif 12 <= hour < 13:
        return "🍚"
    elif 13 <= hour < 14:
        return "🥱"
    elif 14 <= hour < 15:
        return "🧹"
    elif 15 <= hour < 16:
        return "🛍️"
    elif 16 <= hour < 17:
        return "🍰"
    elif 17 <= hour < 18:
        return "🥗"
    elif 18 <= hour < 19:
        return "🥘"
    elif 19 <= hour < 20:
        return "🍓"
    elif 20 <= hour < 21:
        return "🧸"
    elif 21 <= hour < 22:
        return "🛁"
    elif 22 <= hour < 23:
        return "🧴"
    else:
        return "🌙"

def get_time_period(hour):
    if 0 <= hour < 5:
        return "凌晨"
    elif 5 <= hour < 8:
        return "早晨"
    elif 8 <= hour < 11:
        return "上午"
    elif 11 <= hour < 13:
        return "中午"
    elif 13 <= hour < 17:
        return "下午"
    elif 17 <= hour < 19:
        return "傍晚"
    else:
        return "晚上"

@scheduler.scheduled_job("cron", second=0, id="autochangename")
async def change_name_auto():
    try:
        dt = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        hour = dt.strftime("%-I")
        minu = dt.strftime("%M")
        period = get_time_period(dt.hour)
        emoji = get_status_emoji(dt.hour)
        _last_name = f"{period}{hour}:{minu} {emoji}"
        await bot.update_profile(last_name=_last_name)
        me = await bot.get_me()
        if me.last_name != _last_name:
            raise Exception("修改 last_name 失败")
    except Exception as e:
        trac = "\n".join(traceback.format_exception(e))
        await logs.info(f"更新失败! \n{trac}")
