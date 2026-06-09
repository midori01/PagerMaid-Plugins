import contextlib
import platform
import tarfile
import json

from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
from json import loads
from PIL import Image
from os import makedirs
from os.path import exists

from pagermaid.listener import listener
from pagermaid.enums import Client, Message, AsyncClient
from pagermaid.utils import lang, safe_remove

speedtest_path = "/var/lib/pagermaid/plugins/speedtest"
speedtest_json = "/var/lib/pagermaid/plugins/speedtest.json"
speedtest_version = "1.2.0"

def get_default_server():
    if exists(speedtest_json):
        with open(speedtest_json, "r") as f:
            return json.load(f).get("default_server_id", None)
    return None

def save_default_server(server_id=None):
    with open(speedtest_json, "w") as f:
        json.dump({"default_server_id": server_id}, f)

def remove_default_server():
    if exists(speedtest_json):
        safe_remove(speedtest_json)

async def update_cli(request: AsyncClient):
    try:
        await download_cli(request)
        return f"> **⚡️SPEEDTEST by OOKLA**\n`Speedtest® CLI has been updated to the latest version.`"
    except Exception as e:
        return f"> **⚡️SPEEDTEST by OOKLA**\n`Failed to update Speedtest® CLI: {e}`"
        
async def download_cli(request):
    machine = platform.machine()
    machine = "x86_64" if machine == "AMD64" else machine
    filename = f"ookla-speedtest-{speedtest_version}-linux-{machine}.tgz"
    path = "/var/lib/pagermaid/plugins/"
    if not exists(path):
        makedirs(path)
    data = await request.get(f"https://install.speedtest.net/app/cli/{filename}")
    with open(path + filename, mode="wb") as f:
        f.write(data.content)

    try:
        tar = tarfile.open(path + filename, "r:gz")
        tar.extractall(path)
        tar.close()
        safe_remove(path + filename)
        safe_remove(f"{path}speedtest.5")
        safe_remove(f"{path}speedtest.md")
    except tarfile.TarError as e:
        return "Error extracting tar file", None

    proc = await create_subprocess_shell(
        f"chmod +x {speedtest_path}", stdout=PIPE, stderr=PIPE, stdin=PIPE
    )
    await proc.communicate()
    return path if exists(f"{path}speedtest") else None

def decode_output(output):
    try:
        return output.decode().strip()
    except UnicodeDecodeError:
        return output.decode("gbk").strip()

def get_interface_traffic(interface):
    try:
        with open(f"/sys/class/net/{interface}/statistics/rx_bytes", "r") as f:
            rx_bytes = int(f.read())
        with open(f"/sys/class/net/{interface}/statistics/tx_bytes", "r") as f:
            tx_bytes = int(f.read())
        with open(f"/sys/class/net/{interface}/mtu", "r") as f:
            mtu = int(f.read().strip())
        return rx_bytes, tx_bytes, mtu
    except Exception as e:
        return 0, 0, 0

async def start_speedtest(command):
    proc = await create_subprocess_shell(command, stdout=PIPE, stderr=PIPE, stdin=PIPE)
    stdout, stderr = await proc.communicate()
    return decode_output(stdout), decode_output(stderr), proc.returncode

async def unit_convert(byte, is_bytes=False):
    power = 1000 if is_bytes else 1000
    zero = 0
    units = {0: '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'} if is_bytes else {0: '', 1: 'Kbps', 2: 'Mbps', 3: 'Gbps', 4: 'Tbps'}
    if not is_bytes:
        byte *= 8
    while byte > power:
        byte /= power
        zero += 1
    return f"{round(byte, 2)}{units[zero]}"

async def get_ip_api(request: AsyncClient, ip: str):
    try:
        response = await request.get(f"http://ip-api.com/json/{ip}?fields=as,country,countryCode")
        data = response.json()
        as_info = data.get('as', '').split()[0]
        cc_name = "Netherlands" if "Netherlands" in data.get('country', '') else data.get('country', '')
        cc_code = data.get('countryCode', '')
        cc_flag = ''.join([chr(127397 + ord(c)) for c in cc_code.upper()]) if cc_code else ''
        cc_link = f"https://www.submarinecablemap.com/country/{'china' if cc_name in ['Hong Kong', 'Macao', 'Macau'] else cc_name.lower().replace(' ', '-')}"
        return as_info, cc_name, cc_code, cc_flag, cc_link
    except Exception:
        return '', '', '', '', ''
        
async def save_speedtest_image(request, url):
    data = await request.get(url + '.png')
    with open("speedtest.png", mode="wb") as f:
        f.write(data.content)
    with contextlib.suppress(Exception):
        img = Image.open("speedtest.png")
        c = img.crop((17, 11, 727, 389))
        c.save("speedtest.png")
    return "speedtest.png" if exists("speedtest.png") else None

async def run_speedtest(request: AsyncClient, message: Message):
    if not exists(speedtest_path):
        await download_cli(request)

    server_id = message.arguments if message.arguments.isdigit() else get_default_server()
    command = f"sudo {speedtest_path} --accept-license --accept-gdpr -f json" + (f" -s {server_id}" if server_id else "")
    outs, errs, code = await start_speedtest(command)

    if code == 0:
        result = loads(outs)
    elif loads(errs).get('message') == "Configuration - No servers defined (NoServersException)":
        return "Unable to connect to the specified server", None
    else:
        return lang('speedtest_ConnectFailure'), None
        
    as_info, cc_name, cc_code, cc_flag, cc_link = await get_ip_api(request, result['interface']['externalIp'])
    rx_bytes, tx_bytes, mtu = get_interface_traffic(result['interface']['name'])
    
    des = (
        f"> **⚡️SPEEDTEST by OOKLA [@{cc_code}{cc_flag}]({cc_link})**\n"
        f"`Name``  ``{result['isp']}`` `[{as_info}](https://bgp.tools/{as_info})\n"
        f"`Node``  ``{result['server']['id']}` - `{result['server']['name']}` - `{result['server']['location']}`\n"
        f"`Conn``  ``{'IPv6' if ':' in result['interface']['externalIp'] else 'IPv4'}` - `{result['interface']['name']}` - `MTU` `{mtu}`\n"
        f"`Ping``  `⇔`{result['ping']['latency']}ms`` `±`{result['ping']['jitter']}ms`\n"
        f"`Rate``  `↓`{await unit_convert(result['download']['bandwidth'])}`` `↑`{await unit_convert(result['upload']['bandwidth'])}`\n"
        f"`Data``  `↓`{await unit_convert(result['download']['bytes'], is_bytes=True)}`` `↑`{await unit_convert(result['upload']['bytes'], is_bytes=True)}`\n"
        f"`Stat``  `RX `{await unit_convert(rx_bytes, is_bytes=True)}`` `TX `{await unit_convert(tx_bytes, is_bytes=True)}`\n"
        f"`Time``  ``{result['timestamp'].replace('T', ' ').split('.')[0].replace('Z', '')}`"
    )

    photo = await save_speedtest_image(request, result["result"]["url"]) if result["result"]["url"] else None
    return des, photo

async def get_all_ids(request):
    if not exists(speedtest_path):
        await download_cli(request)
    outs, errs, code = await start_speedtest(f"sudo {speedtest_path} -f json -L")
    result = loads(outs) if code == 0 else None

    return (
        (
            "> **⚡️SPEEDTEST by OOKLA**\n"
            + "\n".join(f"`{i['id']}` - `{i['name']}` - `{i['location']}`" for i in result['servers']),
            None
        )
        if result
        else ("No Server Available", None)
    )

@listener(command="s",
          need_admin=True,
          description=lang('speedtest_des'),
          parameters="(ID/list/set/clear/config/update)")
async def speedtest(client: Client, message: Message, request: AsyncClient):
    msg = message
    if message.arguments == "list":
        des, photo = await get_all_ids(request)
    elif message.arguments.startswith("set"):
        server_id = message.arguments.split()[1]
        save_default_server(server_id)
        return await msg.edit(f"> **⚡️SPEEDTEST by OOKLA**\n`Default server has been set to {server_id}.`")
    elif message.arguments == "clear":
        remove_default_server()
        return await msg.edit(f"> **⚡️SPEEDTEST by OOKLA**\n`Default server has been cleared.`")
    elif message.arguments == "config":
        server_id = get_default_server() or "Auto"
        return await msg.edit(f"> **⚡️SPEEDTEST by OOKLA**\n`Default Server: {server_id}\nSpeedtest® CLI: {speedtest_version}`")
    elif message.arguments == "update":
        result = await update_cli(request)
        return await msg.edit(result)
    elif len(message.arguments) == 0 or message.arguments.isdigit():
        msg: Message = await message.edit(lang('speedtest_processing'))
        des, photo = await run_speedtest(request, message)
    else:
        return await msg.edit(lang('arg_error'))

    if not photo:
        return await msg.edit(des)

    try:
        if message.reply_to_message:
            await message.reply_to_message.reply_photo(photo, caption=des)
        else:
            await message.reply_photo(photo, caption=des, quote=False, reply_to_message_id=message.reply_to_top_message_id)
    except Exception:
        return await msg.edit(des)
    finally:
        await msg.safe_delete()
        safe_remove(photo)
