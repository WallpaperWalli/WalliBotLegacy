import asyncio
import json
import os
import sys
from datetime import datetime
from io import BytesIO
from random import randint
from shutil import rmtree
from time import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from PIL import Image, ImageFile
from pyrogram import Client, filters, idle
from pyrogram.errors import PhotoInvalidDimensions, PhotoSaveFileInvalid

if os.path.isfile("VarFile.env"):
    load_dotenv("VarFile.env")

app = Client(
    name=os.environ.get("BOT_NAME"),
    api_id=int(os.environ.get("API_ID")),
    api_hash=os.environ.get("API_HASH"),
    bot_token=os.environ.get("BOT_TOKEN"),
    in_memory=True,
)
files_list = []
post_list = []
users_dict = {}
scheduler = AsyncIOScheduler()
post_id = int(os.environ.get("POST_ID"))
admin_list = list(map(int, os.environ.get("ADMIN_LIST","").split()))
ignore_list = list(map(int, os.environ.get("IGNORE_LIST","").split()))
group_username = os.environ.get("GROUP_USERNAME", "")

# User Section 


@app.on_message(filters.command("start", prefixes="/") & ~filters.channel)
async def start(client, message):
    user = message.from_user
    name, id, username = (user.first_name, user.id, f"@{user.username}" if user.username else "")

    printlog(f"{name} {username} [{id}] started the bot.")

    # Send a greeting message to the user
    await message.reply("Hello! Send me a wallpaper that you want to submit as a document.", quote=True)


@app.on_message(filters.document & ~filters.channel & ~filters.user(admin_list))
async def handle_document(client, message):
    """Don't respond if the document is not a picture"""
    if not message.document.file_name.lower().endswith((".png", ".jpg", ".jpeg", ".jfif")):
        return

    """ User information """
    user = message.from_user
    user_name, user_id, username = (user.first_name, user.id, f"[@{user.username}]" if user.username else "")

    """ Stop execution if user is in ignore list """
    if user_id in ignore_list:
        await asyncio.sleep(randint(1, 5))
        await message.reply(
            f"Sorry for the inconvenience. You are not allowed to send wallpapers. If you think this is a mistake, you can appeal in @{group_username}",
            quote=True,
        )
        return

    if user_id not in users_dict:
        add_user(user_id)
    check_user = check_perm(user_id)
    if not check_user:
        return await message.reply("You've already submitted 5 posts today.\nWait 24 hours before you can send more")
    users_dict[user_id]["counter"] += 1
    if message.document.file_name in files_list:
        await message.reply(
            "This wallpaper cannot be posted because it is already posted. If you think this is a mistake, you can change it's file name and send it again.",
            quote=True,
        )
        return
    else:
        files_list.append(message.document.file_name)
    await message.copy(
        chat_id=int(os.environ.get("REQUEST_ID")),
        caption=f"Check the wallpaper and resend to bot.\n\nSent By [ <a href='tg://user?id={user_id}'>{user_id}</a> ]",
    )
    await asyncio.sleep(randint(1, 8))
    await message.reply("Thank you for your submission. Please wait for the verification.", quote=True)
    printlog(f"{user_name} {username} [{user_id}] made a wallpaper request.")


def add_user(user):
    users_dict[user] = {}
    users_dict[user]["time"] = datetime.now()
    users_dict[user]["counter"] = 0


def check_perm(user):
    day = (datetime.now() - users_dict[user]["time"]).days
    if day >= 1:
        users_dict[user]["counter"] = 0
        users_dict[user]["time"] = datetime.now()
    if users_dict[user]["counter"] == 5:
        return False
    return True


# Admin section


@app.on_message(filters.command("restart", prefixes="/") & filters.user(admin_list))
async def restart(client, message):
    """Stop Scheduler and Restart bot when an Admin sends a restart command."""
    scheduler.shutdown()
    os.execl(sys.executable, sys.executable, __file__)


@app.on_message(filters.command("post", prefixes="/") & filters.user(admin_list))
async def add_post(app, message):
    reply = message.reply_to_message
    if reply and message.text == "/post":
        docs = await app.get_messages(chat_id=message.chat.id, message_ids=[i for i in range(reply.id, message.id)])
        [
            post_list.append({"document": msg})
            for msg in docs
            if msg.document and msg.document.file_name.lower().endswith((".png", ".jpg", ".jpeg", ".jfif"))
        ]
    else:
        return await message.reply("Reply to a document.")
    await message.reply("Added to Queue")
    user = message.from_user
    user_name, user_id, username = (user.first_name, user.id, f"@{user.username}" if user.username else "")
    printlog(f"{user_name} {username} [{user_id}] posted a wallpaper.")


async def poster():
    """The logic function to handle posts without getting interrupted from other submissions"""
    if len(post_list) > 0:
        upload, resize = None, None
        data = post_list[0]["document"]
        file_name = data.document.file_name
        download_path = os.path.join("downloads", str(time()))
        file_path = os.path.join(download_path, file_name)
        await data.download(file_path)
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        with Image.open(file_path) as img:
            if img.width > img.height:
                caption = "#desktop"
            elif img.width < img.height:
                caption = "#mobile"
            else:
                caption = "#universal"
        try:
            await app.send_photo(chat_id=post_id, photo=file_path, caption=caption)
            await asyncio.sleep(3)
        except (PhotoInvalidDimensions, PhotoSaveFileInvalid):
            resize = await resizer(file=file_path, name=file_name)
            await app.send_photo(chat_id=post_id, photo=resize, caption=caption)
            await asyncio.sleep(3)
        await data.copy(chat_id=post_id, caption="")
        if os.path.exists(download_path):
            rmtree(download_path)
        post_list.pop(0)


async def resizer(file, name):
    """Resize Photo to fit Telegram's size restrictions"""
    with Image.open(file).convert("RGB") as img:
        comp_file = BytesIO()
        if img.width > img.height:
            if img.width > 3840:
                aspect_ratio = img.width / img.height
                img = img.resize((3840, int(3840 / aspect_ratio)), Image.LANCZOS)
            img.save(comp_file, format="JPEG", optimize=True, quality=95)
        elif img.width < img.height:
            if img.height > 3840:
                aspect_ratio = img.height / img.width
                img = img.resize((int(3840 / aspect_ratio), 3840), Image.LANCZOS)
            img.save(comp_file, format="JPEG", optimize=True, quality=95)
        else:
            if img.width > 3840 or img.height > 3840:
                img = img.resize((3840, 3840), Image.LANCZOS)
            img.save(comp_file, format="JPEG", optimize=True, quality=95)
        comp_file.name = name + ".jpeg"
        return comp_file


#Bot section


async def boot():
    #Start bot
    #Start Scheduler to call post function every 30 seconds
    #Wait idle to receive commands / submissions
    printlog("Client initialized..")
    await app.start()
    scheduler.add_job(poster, "interval", seconds=30)
    scheduler.start()
    printlog("Client Started, Idling....")
    await idle()


def printlog(message):
    print(message)
    current_time = datetime.now().strftime("%H:%M:%S")
    current_date = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists("logs"):
        os.makedirs("logs")
    # Open log file to write log, if file doesn't exist, create one.
    with open((os.path.join("logs", f"{current_date}.log")), "a+", encoding="utf-8") as log:
        log.write(f"[{current_time}] {message}\n")


# To prevent accidental startup of bot.
if __name__ == "__main__":
    app.run(boot())
