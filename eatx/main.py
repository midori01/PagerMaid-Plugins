from PIL import Image
from os.path import exists
from os import sep
from random import randint

from pyrogram import Client
from pyrogram.enums import MessageEntityType
from pyrogram.errors import UsernameNotOccupied, UsernameInvalid
from pyrogram.types import User, Chat

from pagermaid.dependence import sqlite, client
from pagermaid.enums import Message
from pagermaid.listener import listener
from pagermaid.utils import lang, safe_remove

from collections import defaultdict
import json

git_source = "https://repo.lvlv.lv/"
positions = {
    "1": [297, 288],
    "2": [85, 368],
    "3": [127, 105],
    "4": [76, 325],
    "5": [256, 160],
    "6": [298, 22],
}
notifyStrArr = {
    "6": "踢人",
}
extensionConfig = {}
max_number = len(positions)
configFilePath = f"plugins{sep}eat{sep}config.json"
configFileRemoteUrlKey = "eat.configFileRemoteUrl"

async def eat_it(context, user, base, mask, photo, number, layer=0):
    mask_size = mask.size
    photo_size = photo.size
    if mask_size[0] < photo_size[0] and mask_size[1] < photo_size[1]:
        scale = photo_size[1] / mask_size[1]
        photo = photo.resize(
            (int(photo_size[0] / scale), int(photo_size[1] / scale)), Image.LANCZOS
        )
    photo = photo.crop((0, 0, mask_size[0], mask_size[1]))
    mask1 = Image.new("RGBA", mask_size)
    mask1.paste(photo, mask=mask)
    numberPosition = positions[str(number)]
    isSwap = False
    try:
        isSwap = extensionConfig[str(number)]["isSwap"]
    except:
        pass
    if isSwap:
        photoBg = Image.new("RGBA", base.size)
        photoBg.paste(mask1, (numberPosition[0], numberPosition[1]), mask1)
        photoBg.paste(base, (0, 0), base)
        base = photoBg
    else:
        base.paste(mask1, (numberPosition[0], numberPosition[1]), mask1)

    isContinue = len(numberPosition) > 2 and layer == 0
    if isContinue:
        await context._client.download_media(
            user.photo.big_file_id, f"plugins{sep}eat{sep}{str(user.id)}.jpg"
        )
        try:
            markImg = Image.open(f"plugins{sep}eat{sep}{str(user.id)}.jpg")
            maskImg = Image.open(
                f"plugins{sep}eat{sep}mask{str(numberPosition[2])}.png"
            ).convert("RGBA")
        except:
            await context.edit(f"图片模版加载出错，请检查并更新配置：mask{str(numberPosition[2])}.png")
            return base
        base = await eat_it(
            context, user, base, maskImg, markImg, numberPosition[2], layer + 1
        )
    temp = base.size[0] if base.size[0] > base.size[1] else base.size[1]
    if temp != 512:
        scale = 512 / temp
        base = base.resize(
            (int(base.size[0] * scale), int(base.size[1] * scale)), Image.LANCZOS
        )
    return base

async def updateConfig(context):
    if configFileRemoteUrl := sqlite.get(configFileRemoteUrlKey, ""):
        if downloadFileFromUrl(configFileRemoteUrl, configFilePath) == 0:
            return await loadConfigFile(context, True)
        sqlite[configFileRemoteUrlKey] = configFileRemoteUrl
        return -1
    return 0

async def downloadFileFromUrl(url, filepath):
    try:
        re = await client.get(url)
        with open(filepath, "wb") as ms:
            ms.write(re.content)
    except:
        return -1
    return 0

async def loadConfigFile(context, forceDownload=False):
    global positions, notifyStrArr, extensionConfig
    try:
        with open(configFilePath, "r", encoding="utf8") as cf:
            remoteConfigJson = json.load(cf)
            positionsStr = json.dumps(remoteConfigJson["positions"])
            data = json.loads(positionsStr)
            positions = mergeDict(positions, data)
            data = json.loads(json.dumps(remoteConfigJson["notifies"]))
            notifyStrArr = mergeDict(notifyStrArr, data)
            try:
                data = json.loads(json.dumps(remoteConfigJson["extensionConfig"]))
                extensionConfig = mergeDict(extensionConfig, data)
            except:
                pass
            data = json.loads(json.dumps(remoteConfigJson["needDownloadFileList"]))
            for file_url in data:
                try:
                    fsplit = file_url.split("/")
                    filePath = f"plugins{sep}eat{sep}{fsplit[len(fsplit) - 1]}"
                    if not exists(filePath) or forceDownload:
                        await downloadFileFromUrl(file_url, filePath)
                except:
                    await context.edit(f"下载文件异常，url：{file_url}")
                    return -1
    except:
        return -1
    return 0

def mergeDict(d1, d2):
    dd = defaultdict(list)
    for d in (d1, d2):
        for key, value in d.items():
            dd[key] = value
    return dict(dd)

async def downloadFileByIds(ids, context):
    idsStr = f',{",".join(ids)},'
    try:
        with open(configFilePath, "r", encoding="utf8") as cf:
            remoteConfigJson = json.load(cf)
            data = json.loads(json.dumps(remoteConfigJson["needDownloadFileList"]))
            sucSet = set()
            failSet = set()
            for file_url in data:
                try:
                    fsplit = file_url.split("/")
                    fileFullName = fsplit[len(fsplit) - 1]
                    fileName = (
                        fileFullName.split(".")[0]
                        .replace("eat", "")
                        .replace("mask", "")
                    )
                    if f",{fileName}," in idsStr:
                        filePath = f"plugins{sep}eat{sep}{fileFullName}"
                        if (await downloadFileFromUrl(file_url, filePath)) == 0:
                            sucSet.add(fileName)
                        else:
                            failSet.add(fileName)
                except:
                    failSet.add(fileName)
                    await context.edit(f"下载文件异常，url：{file_url}")
            notifyStr = "更新模版完成"
            if sucSet:
                notifyStr = f'{notifyStr}\n成功模版如下：{"，".join(sucSet)}'
            if failSet:
                notifyStr = f'{notifyStr}\n失败模版如下：{"，".join(failSet)}'
            await context.edit(notifyStr)
    except:
        await context.edit("更新下载模版图片失败，请确认配置文件是否正确")

@listener(
    is_plugin=True,
    outgoing=True,
    command="x",
    description="生成一张 吃头像 图片\n"
    "可选：当第二个参数是数字时，读取预存的配置；\n\n"
    "当第二个参数是 . 开头时，头像旋转 180°，并且判断 . 后面是数字则读取对应的配置生成\n\n"
    "当第二个参数是 / 开头时，在 / 后面加 URL 则从该地址下载配置文件保存到本地，如果就一个 /，则直接更新配置文件，删除则是 /delete；或者 / 后面加模版 id 可以手动更新指定模版配置\n\n"
    "当第二个参数是 - 开头时，在-后面加上模版 id，即可设置默认模版，删除默认模版是 ,x -\n\n"
    "当第二个参数是 ! 开头时，列出当前可用模版",
    parameters="[username/uid] [随意内容]",
)
async def eat(client_: Client, context: Message):
    if len(context.parameter) > 2:
        await context.edit("出错了呜呜呜 ~ 无效的参数。")
        return
    diu_round = False
    if context.from_user:
        from_user_id = context.from_user.id
    else:
        from_user_id = context.sender_chat.id
    if context.reply_to_message:
        if context.reply_to_message.from_user:
            user = context.reply_to_message.from_user
        else:
            user = context.reply_to_message.sender_chat
    else:
        if len(context.parameter) == 1:
            user = context.parameter[0]
            if user.isdigit():
                user = int(user)
        else:
            user = context.from_user if context.from_user else context.sender_chat
        if isinstance(user, str):
            if user.startswith(".") or user.startswith("/") or user.startswith("-") or user.startswith("!"):
                user = context.from_user if context.from_user else context.sender_chat
            else:
                try:
                    user = await client_.get_users(user)
                except Exception:
                    return await context.edit(f"{lang('error_prefix')}{lang('profile_e_nou')}")
    target_user_id = user.id
    if not user.photo:
        return await context.edit("出错了呜呜呜 ~ 此用户无头像。")
    photo = await client_.download_media(
        user.photo.big_file_id,
        f"plugins{sep}eat{sep}" + str(target_user_id) + ".jpg",
    )
    reply_to = context.reply_to_message.id if context.reply_to_message else None
    if exists(f"plugins{sep}eat{sep}" + str(target_user_id) + ".jpg"):
        for num in range(1, max_number + 1):
            if not exists(f"plugins{sep}eat{sep}eat" + str(num) + ".png"):
                re = await client.get(f"{git_source}eat/eat" + str(num) + ".png")
                with open(f"plugins{sep}eat{sep}eat" + str(num) + ".png", "wb") as bg:
                    bg.write(re.content)
            if not exists(f"plugins{sep}eat{sep}mask" + str(num) + ".png"):
                re = await client.get(f"{git_source}eat/mask" + str(num) + ".png")
                with open(f"plugins{sep}eat{sep}mask" + str(num) + ".png", "wb") as ms:
                    ms.write(re.content)
        number = randint(1, max_number)
        try:
            p1 = 0
            p2 = 0
            if len(context.parameter) == 1:
                p1 = context.parameter[0]
                if p1[0] == ".":
                    diu_round = True
                    if len(p1) > 1:
                        try:
                            p2 = int("".join(p1[1:]))
                        except:
                            p2 = "".join(p1[1:])
                elif p1[0] == "-":
                    if len(p1) > 1:
                        try:
                            p2 = int("".join(p1[1:]))
                        except:
                            p2 = "".join(p1[1:])
                    if p2:
                        sqlite["eat.default-config"] = p2
                        await context.edit(f"已经设置默认配置为：{p2}")
                    else:
                        del sqlite["eat.default-config"]
                        await context.edit(f"已经清空默认配置")
                    return
                elif p1[0] == "/":
                    await context.edit(f"正在更新远程配置文件")
                    if len(p1) > 1:
                        p2 = "".join(p1[1:])
                        if p2 == "delete":
                            del sqlite[configFileRemoteUrlKey]
                            await context.edit(f"已清空远程配置文件url")
                            return
                        if p2.startswith("http"):
                            if (await downloadFileFromUrl(p2, configFilePath)) != 0:
                                await context.edit(f"下载配置文件异常，请确认url是否正确")
                                return
                            else:
                                sqlite[configFileRemoteUrlKey] = p2
                                if await loadConfigFile(context, True) != 0:
                                    await context.edit(f"加载配置文件异常，请确认从远程下载的配置文件格式是否正确")
                                    return
                                else:
                                    await context.edit(f"下载并加载配置文件成功")
                        else:
                            splitStr = "，"
                            if "," in p2:
                                splitStr = ","
                            ids = p2.split(splitStr)
                            if len(ids) > 0:
                                configFileRemoteUrl = sqlite.get(
                                    configFileRemoteUrlKey, ""
                                )
                                if configFileRemoteUrl:
                                    if (
                                        await downloadFileFromUrl(
                                            configFileRemoteUrl, configFilePath
                                        )
                                    ) != 0:
                                        await context.edit(f"下载配置文件异常，请确认url是否正确")
                                        return
                                    else:
                                        if await loadConfigFile(context) != 0:
                                            await context.edit(
                                                f"加载配置文件异常，请确认从远程下载的配置文件格式是否正确"
                                            )
                                            return
                                        else:
                                            await downloadFileByIds(ids, context)
                                else:
                                    await context.edit(f"你没有订阅远程配置文件，更新个🔨")
                    else:
                        if await updateConfig(context) != 0:
                            await context.edit(
                                f"更新配置文件异常，请确认是否订阅远程配置文件，或从远程下载的配置文件格式是否正确"
                            )
                            return
                        else:
                            await context.edit(f"从远程更新配置文件成功")
                    return
                elif p1[0] == "！" or p1[0] == "!":
                    if exists(configFilePath):
                        if await loadConfigFile(context) != 0:
                            await context.edit(f"加载配置文件异常，请确认从远程下载的配置文件格式是否正确")
                            return
                    txt = ""
                    if len(positions) > 0:
                        noShowList = []
                        for key in positions:
                            txt = f"{txt}，{key}"
                            if len(positions[key]) > 2:
                                noShowList.append(positions[key][2])
                        for key in noShowList:
                            txt = txt.replace(f"，{key}", "")
                        if txt != "":
                            txt = txt[1:]
                    await context.edit(f"目前已有的模版列表如下：\n{txt}")
                    return
            defaultConfig = sqlite.get("eat.default-config", "")
            if isinstance(p2, str):
                number = p2
            elif isinstance(p2, int) and p2 > 0:
                number = int(p2)
            elif not diu_round and (
                (isinstance(p1, int) and int(p1) > 0) or isinstance(p1, str)
            ):
                try:
                    number = int(p1)
                except:
                    number = p1
            elif defaultConfig:
                try:
                    defaultConfig = defaultConfig.decode()
                    number = int(defaultConfig)
                except:
                    number = str(defaultConfig)
                    if number.startswith("."):
                        diu_round = True
                        number = number[1:]
        except:
            number = randint(1, max_number)

        if exists(configFilePath):
            if await loadConfigFile(context) != 0:
                await context.edit(f"加载配置文件异常，请确认从远程下载的配置文件格式是否正确")
                return
        try:
            notifyStr = notifyStrArr[str(number)]
        except:
            notifyStr = "吃头像"
        final_msg = await context.edit(f"正在生成 {notifyStr} 图片中 . . .")
        markImg = Image.open(f"plugins{sep}eat{sep}" + str(target_user_id) + ".jpg")
        try:
            eatImg = Image.open(f"plugins{sep}eat{sep}eat" + str(number) + ".png")
            maskImg = Image.open(
                f"plugins{sep}eat{sep}mask" + str(number) + ".png"
            ).convert("RGBA")
        except:
            await context.edit(f"图片模版加载出错，请检查并更新配置：{str(number)}")
            return
        if diu_round:
            markImg = markImg.rotate(180)
        try:
            number = str(number)
        except:
            pass
        result = await eat_it(
            context, context.from_user, eatImg, maskImg, markImg, number
        )
        result.save(f"plugins{sep}eat{sep}eat.webp")
        safe_remove(f"plugins{sep}eat{sep}" + str(target_user_id) + ".jpg")
        safe_remove(f"plugins{sep}eat{sep}" + str(target_user_id) + ".png")
        safe_remove(f"plugins{sep}eat{sep}" + str(from_user_id) + ".jpg")
        safe_remove(f"plugins{sep}eat{sep}" + str(from_user_id) + ".png")
    else:
        return await context.edit("此用户未设置头像或头像对您不可见。")
    if reply_to:
        try:
            await client_.send_document(
                context.chat.id,
                f"plugins{sep}eat{sep}eat.webp",
                reply_to_message_id=reply_to,
            )
            await final_msg.safe_delete()
        except TypeError:
            await final_msg.edit("此用户未设置头像或头像对您不可见。")
        except:
            await final_msg.edit("此群组无法发送贴纸。")
    else:
        try:
            await client_.send_document(
                context.chat.id,
                f"plugins{sep}eat{sep}eat.webp",
                message_thread_id=context.message_thread_id,
            )
            await final_msg.safe_delete()
        except TypeError:
            await final_msg.edit("此用户未设置头像或头像对您不可见。")
        except:
            await final_msg.edit("此群组无法发送贴纸。")
    safe_remove(f"plugins{sep}eat{sep}eat.webp")
    safe_remove(photo)