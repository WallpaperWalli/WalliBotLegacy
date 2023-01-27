import asyncio
import os
import sys
import urllib.parse
from datetime import datetime
from io import BytesIO
from random import choices, randint
from shutil import rmtree
from string import ascii_letters
from time import time
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PIL import Image, ImageFile
from pyrogram import Client, filters, idle
from pyrogram.errors import PhotoInvalidDimensions, PhotoSaveFileInvalid
from VarFile import *

app = Client(bot_name, api_id, api_hash, bot_token=token, in_memory=True)
files_list = []
aio_session = None
post_list = []
#recent_users = []
scheduler = AsyncIOScheduler()

@app.on_message(
    (filters.command("start", prefixes="/") | filters.photo) & ~filters.channel
)
async def start(client, message):
    """ Check if a user sent a photo or start command and respond accordingly """
    if message.photo:
        await message.reply("Please send the image as a file.", quote=True)
    else:
        user = message.from_user
        name, id, username = (
            user.first_name,
            user.id,
            f"@[{user.username}]" if user.username else "",
        )
        printlog(f"{name} {username} [{id}] started the bot.")
        # Send a greeting message to the user
        await message.reply(
            "Hello! Send me a wallpaper that you want to submit as a document.", quote=True
        )

@app.on_message(filters.document & ~filters.channel)
async def handle_document(client, message):
    """ User information """
    user = message.from_user
    u_name, u_id, username = (
        user.first_name,
        user.id,
        f"[@{user.username}]" if user.username else "",
    )

    """ Stop execution if user is in ignore list """
    if u_id in ignore_list:
        await asyncio.sleep(randint(1, 5))
        await message.reply(
            f"Sorry for the inconvenience. You are not allowed to send wallpapers. If you think this is a mistake, you can appeal in {group_username}", quote=True
        )
        return

    """ Anti-Spam Check to process one file at a time from one user """
    #if u_id in recent_users:
        #await asyncio.sleep(4)
        #return await message.reply("Send one wallpaper at a time.", quote=True)
    #else:
        #recent_users.append(u_id)

    printlog(f"{u_name} {username} [{u_id}] sent a document.")
    await asyncio.sleep(randint(1,8))
    response = await message.reply("Added to queue. Please wait.", quote=True)

    """ Check if the user has Admin privileges """
    if u_id in admin_list:
        isadmin = True
    else:
        isadmin = False

    if message.document.file_name in files_list:
        if not isadmin:
            await response.edit(
                "This wallpaper cannot be posted because it is already posted. If you think this is a mistake, you can change it's file name and send it again."
            )
            return
    else:
        files_list.append(message.document.file_name)

    """ If the user is Admin then queue the post otherwise send the document for verification """
    if isadmin:
        file_name = message.document.file_name
        download_path = os.path.join("downloads", str(time()))
        file_path = os.path.join(download_path, file_name)
        await message.download(file_path)
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        img = Image.open(file_path)
        if img.width > img.height:
            tag = "#desktop"
        elif img.width < img.height:
            tag = "#mobile"
        else:
            tag = "#universal"
        await response.edit("Processing...")
        post_list.append(
            {
                "response": response,
                "path": download_path,
                "file_path": file_path,
                "caption": tag,
                "document": message,
                "file_name": file_name
            }
        )
        printlog(f"{u_name} {username} [{u_id}] posted a wallpaper.")

    else:
        # upload = await gofiles(file_path)
        # if upload == "failed":
        # return await response.edit(
        # "An error occurred with Gofile.io.\nPlease try again."
        # )
        await asyncio.sleep(2)
        await message.copy(
            chat_id=request_id, caption=f"Check the wallpaper and resend to bot."
        )
        await asyncio.sleep(2)
        await response.edit(
            "Thank you for your submission. Please wait for the verification."
        )
        printlog(f"{u_name} {username} [{u_id}] made a wallpaper request.")
    #recent_users.remove(u_id)


@app.on_message(filters.command("restart", prefixes="/") & filters.user(admin_list))
async def restart(client, message):
    """ Stop Scheduler and Restart bot when an Admin sends a restart command. """
    scheduler.shutdown()
    os.execl(sys.executable, sys.executable, __file__)


async def poster():
    """ The logic function to handle posts without getting interrupted from other submissions """
    if len(post_list) > 0:
        upload, resize = None, None
        data = post_list[0]
        file_path, file_name, download_path, caption, response, document = (
            data["file_path"],
            data["file_name"],
            data["path"],
            data["caption"],
            data["response"],
            data["document"],
        )
        try:
            await app.send_photo(chat_id=post_id, photo=file_path, caption=caption)
            await asyncio.sleep(3)
        except (PhotoInvalidDimensions, PhotoSaveFileInvalid):
            resize = await resizer(file=file_path,name=file_name)
            await app.send_photo(chat_id=post_id, photo=resize, caption=caption)
            await asyncio.sleep(3)
        await document.copy(chat_id=post_id)
        await response.edit("Wallpaper posted.")
        if os.path.exists(download_path):
            rmtree(download_path)
        post_list.pop(0)

async def resizer(file, name):
    """ Resize Photo to fit Telegram's size restrictions """
    img = Image.open(file).convert("RGB")
    comp_file = BytesIO()
    if img.width > img.height:
        tag = "#desktop"
        if img.width > 3840:
            aspect_ratio = img.width / img.height
            img = img.resize((3840, int(3840 / aspect_ratio)), Image.LANCZOS)
        img.save(comp_file, format="JPEG", optimize=True, quality=95)
    elif img.width < img.height:
        tag = "#mobile"
        if img.height > 3840:
            aspect_ratio = img.height / img.width
            img = img.resize((int(3840 / aspect_ratio), 3840), Image.LANCZOS)
        img.save(comp_file, format="JPEG", optimize=True, quality=95)
    else:
        tag = "#universal"
        if img.width > 3840 or img.height > 3840:
            img = img.resize((3840, 3840), Image.LANCZOS)
        img.save(comp_file, format="JPEG", optimize=True, quality=95)
    comp_file.name = name + ".jpeg"
    return comp_file


"""
async def gofiles(file_path):
    try:
          async with aio_session.request("GET", url="https://api.gofile.io/getServer") as session:
              status = loads(await session.text())
          with open(file_path,"rb") as up_file:
              async with aio_session.request("POST",url=f"https://{status['data']['server']}.gofile.io/uploadFile",data={"key": up_file},) as post_session:
                  post_link = loads(await post_session.text())["data"]["downloadPage"]
    except Exception:
        post_link = "failed"
    return post_link
"""


async def boot():
    """ Start bot, setup client session for gofile requests
        Start Scheduler to call post function every 30 seconds
       Wait idle to receive commands / submissions
    """
    printlog("Client initialized..")
    await app.start()
    #global aio_session
    #aio_session = aiohttp.ClientSession()
    scheduler.add_job(poster, "interval", seconds=10)
    scheduler.start()
    printlog("Client Started, Idling....")
    await idle()


def is_valid_link(link):
    try:
        result = urllib.parse.urlparse(link)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def printlog(message):
    print(message)
    current_time = datetime.now().strftime("%H:%M:%S")
    current_date = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists("logs"):
        os.makedirs("logs")
    # Open log file to write log, if file doesn't exist, create one.
    with open((os.path.join("logs", f"{current_date}.log")), "a+") as log:
        log.write(f"[{current_time}] {message}\n")

""" To prevent accidental startup of bot. """
if __name__ == "__main__":
    app.run(boot())
