import pyrogram
from PIL import Image, ImageFile
from time import sleep
import os
import requests
from json import loads
from shutil import rmtree
from random import choices, randint
from string import ascii_letters
from VarFile import *
import urllib.parse
from datetime import datetime

def printlog(message):
    print(message)
    current_time = datetime.now().strftime("%H:%M:%S")
    current_date = datetime.now().strftime("%Y-%m-%d")
    with open((os.path.join("logs", f"{current_date}.log")), "a") as log:
        log.write(f"[{current_time}] {message}\n")

# Initialize client
app = pyrogram.Client(bot_name, api_id, api_hash, bot_token=token)
printlog("Client initialized. Waiting for updates...\n")

def is_valid_link(link):
    try:
        result = urllib.parse.urlparse(link)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

@app.on_message(pyrogram.filters.command("start") & ~pyrogram.filters.channel)
def start(client, message):

    try:
        printlog(f"{app.get_users(message.from_user.id).first_name} [@{app.get_users(message.from_user.id).username}][{message.from_user.id}] started the bot.")
    except Exception:
        printlog(f"{message.from_user.id} started the bot.")

    # Send a greeting message to the user
    message.reply("Hello! Send me a wallpaper that you want to submit.")

@app.on_message(pyrogram.filters.photo & ~pyrogram.filters.channel)
def handle_photo(client, message):
    message.reply("Please send the image as a file.")

@app.on_message(pyrogram.filters.document & ~pyrogram.filters.channel)
def handle_document(client, message):      

    # Check if user is in ignored list
    if message.from_user.id in ignore_list:
        sleep(5)
        message.reply(f"Sorry for the inconvenience. You are not allowed to send wallpapers. If you think this is a mistake, you can appeal in {group_username}")
        return
    
    try:
        printlog(f"{app.get_users(message.from_user.id).first_name} [@{app.get_users(message.from_user.id).username}][{message.from_user.id}] sent a document.")
    except Exception:
        printlog(f"{message.from_user.id} sent a document.")

    sleep(5)
    messagePost = message.reply("Added to queue. Please wait.").id

    if message.document.file_name in os.listdir("downloads"):
        if message.from_user.id not in admin_list:
            message.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="This wallpaper cannot be posted because it is already posted. If you think this is a mistake, you can change it's file name and send it again.")
            return
        else:
            compression = False
    else:
        compression = True

    # File info
    file_id = message.document.file_id
    if compression == True:
        file_name = ''.join(choices(ascii_letters, k=10)) + f"-{watermark}" + os.path.splitext(message.document.file_name)[1]  
    else:
        file_name = message.document.file_name   

    # The buggiest part of code, don't mess this one up
    if os.path.exists("downloads"):
        while True:
            if len(os.listdir("downloads")) == 0:
                file_path = app.download_media(file_id, file_name=file_name)
                break
            elif len(os.listdir("downloads")) > 0:
                sleep(randint(1, 10))
                if os.path.exists("done.txt"):
                    sleep(5)
                    try:
                        rmtree("downloads", ignore_errors=True)
                        os.mkdir("downloads")
                        os.remove("done.txt")
                    except Exception:
                        continue
                else:
                    sleep(10)
    else:
        file_path = app.download_media(file_id, file_name=file_name)

    ImageFile.LOAD_TRUNCATED_IMAGES=True

    if compression == True:
        # Open the image, upload it to cloud, check its orientation and scale the image if needed
        img = Image.open(file_path)
        status = loads(requests.get("https://api.gofile.io/getServer").text)
        upload = loads(requests.post(f"https://{status['data']['server']}.gofile.io/uploadFile", files = {'file': open(file_path ,'rb')}).text)['data']['downloadPage']

        img = Image.open(file_path).convert("RGB")
        if img.width > img.height:
            tag = "#desktop"
            if img.width > 3840:
                aspect_ratio = img.width / img.height
                img = img.resize((3840, int(3840/aspect_ratio)), Image.LANCZOS)
            img.save((os.path.splitext(file_path)[0] + ".jpeg"), "JPEG", optimize = True, quality = 95)
        elif img.width < img.height:
            tag = "#mobile"
            if img.height > 3840:      
                aspect_ratio = img.height/img.width
                img = img.resize((int(3840/aspect_ratio), 3840), Image.LANCZOS)
            img.save((os.path.splitext(file_path)[0] + ".jpeg"), "JPEG", optimize = True, quality = 95)
        else:
            tag = "#universal"
            if img.width > 3840 or img.height > 3840:         
                img = img.resize((3840, 3840), Image.LANCZOS)
            img.save((os.path.splitext(file_path)[0] + ".jpeg"), "JPEG", optimize = True, quality = 95)
    else:
        img = Image.open(file_path)
        if img.width > img.height:
            tag = "#desktop"
        elif img.width < img.height:
            tag = "#mobile"
        else:
            tag = "#universal"      

    # Check if user is in admin list and send to verification if not
    if message.from_user.id not in admin_list:
        try:
            app.send_photo(chat_id=-1001701702872, photo=(os.path.splitext(file_path)[0] + ".jpeg"), caption=f"Check the wallpaper and repost the link\n\n{upload}")
        except Exception:
            app.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="An error occured. Please try again later.")
            return
        app.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="Thank you for your submission. Please wait for the verification.")
        try:
            printlog(f"{app.get_users(message.from_user.id).first_name} [@{app.get_users(message.from_user.id).username}][{message.from_user.id}] made a wallpaper request.")
        except Exception:
            printlog(f"{message.from_user.id} made a wallpaper request.")
        myFile = open("done.txt", "w+")
        myFile.close()
        return

    try:
        app.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="Processing.")
        app.send_photo(
            chat_id=post_id,
            photo=(os.path.splitext(file_path)[0] + ".jpeg"),
            caption=tag
        )

        app.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="Processing..")
        sleep(10)
        if compression == True:
            # Post the image as a file to channel
            app.send_document(
                chat_id=post_id,
                document=(os.path.splitext(file_path)[0] + ".jpeg"),
                caption=f'<a href="{upload}">Full resolution</a>'
            )
        else:
            app.send_document(
                chat_id=post_id,
                document=(os.path.splitext(file_path)[0] + ".jpeg"),
            )

        app.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="Processing...")
        sleep(5)

        app.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="Wallpaper posted.")
        try:
            printlog(f"{app.get_users(message.from_user.id).first_name} [@{app.get_users(message.from_user.id).username}][{message.from_user.id}] posted a wallpaper.")
        except Exception:
            printlog(f"{message.from_user.id} posted a wallpaper.")
            
    except Exception:
        app.edit_message_text(chat_id=message.chat.id, message_id=messagePost, text="An error occured. Please try again later.")
        try:
            printlog(f"{app.get_users(message.from_user.id).first_name} [@{app.get_users(message.from_user.id).username}][{message.from_user.id}] had an error.")
        except Exception:
            printlog(f"{message.from_user.id} had an error.")

    myFile = open("done.txt", "w+")
    myFile.close()

app.run()
