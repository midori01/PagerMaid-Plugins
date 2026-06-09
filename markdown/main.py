from pagermaid.listener import listener
from pagermaid.enums import Message, Client

format_options = {
    "quote": "> {}",
    "spoiler": "||{}||",
    "bold": "**{}**",
    "italic": "__{}__",
    "monospace": "`{}`",
    "strikethrough": "~~{}~~",
    "underline": "<u>{}</u>",
    "code": "```{}```",
}

current_format = None

@listener(command="m", description="设置 Markdown 格式。\n可选：quote, spoiler, bold, italic, monospace, strikethrough, underline, code",
          parameters="<set|message>")
async def set_format_or_send(message: Message):
    global current_format
    args = message.arguments.strip().split(maxsplit=1)

    if args[0] == "set":
        if len(args) < 2:
            await message.edit("请提供一个格式名。\n可选：quote, spoiler, bold, italic, monospace, strikethrough, underline, code")
            return
        format_name = args[1].strip()
        
        if format_name not in format_options:
            available_formats = ', '.join(format_options.keys())
            await message.edit(f"无效的格式名，请设置以下格式之一：{available_formats}")
            return
        
        current_format = format_options[format_name]
        await message.edit(f"Markdown 格式已设定为：{format_name}")
    
    else:
        if not current_format:
            await message.edit("请先设置 Markdown 格式。")
            return
        
        if not message.arguments:
            await message.edit("请提供要发送的消息内容。")
            return
        
        formatted_message = current_format.format(message.arguments)
        await message.edit(formatted_message)
