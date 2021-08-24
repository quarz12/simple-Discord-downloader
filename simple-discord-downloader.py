from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from time import mktime
import datetime
from typing import List
from tqdm import tqdm
import requests
from PIL import Image
from io import BytesIO
from json import loads

token=""



def timestampToSnowflake(timestamp):
    # Multiply the timestamp by 1000 to approximate the UNIX epoch to the nearest millisecond.
    timestamp *= 1000
    # Subtract the UNIX epoch of January 1, 2015 from the timestamp as this is the minimum timestamp that Discord supports because Discord has only been around since May 2015.
    timestamp -= 1420070400000
    # Return the timestamp value bitshifted to the left by 22 bits.
    return int(timestamp) << 22


def process_json(json) -> List[Message]:
    messages=[]
    try:
        for message in json:
            if len(message["attachments"])!=0:
                filename=message["attachments"][0]["filename"]
                img_url=message["attachments"][0]["url"]
            else :
                filename= None
                img_url=None
            messages.append(Message(message["id"],message["content"],filename if filename else None,img_url if img_url else None))
        return messages
    except Exception as error:
        print(json)
        print(error)

class Scraper:
    def __init__(self,token=token):
        self.session = requests.Session()
        self.download_session=requests.Session()
        self.session.headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) discord/0.0.309 Chrome/83.0.4103.122 Electron/9.3.5 Safari/537.36",
            'Authorization': f"{token}"
        }
        self.snowflake_first_message= timestampToSnowflake(mktime((2015, 1, 2, 0, 0, 0, -1, -1, -1))) #Make snowflake of first possible discord message
        self.snowflake_now= timestampToSnowflake(time.time()) #Make snowflake off current time
        self.apiversion="v9"
        self.query="has=image"
        self.channels=[]

    def get_messages(self,channelid):
        return self.get_Messages(self.snowflake_first_message,channelid)

    def get_Messages(self, snowflake,channelid)->List[Message]:
        response = self.session.get(f'https://discord.com/api/{self.apiversion}/channels/{channelid}/messages?after={snowflake}&limit=25&{self.query}')
        if response.status_code==429:
            print(response.content)
            timeout=loads(response.content).get("retry-after",1)
            print(f"too many requests, retrying after {timeout}")
            time.sleep(timeout+2)
            return self.get_Messages(snowflake,channelid)
        json=response.content
        json=loads(json)
        messages=process_json(json)
        messages.reverse()
        if len(messages)==0:
            return messages
        messages.extend(self.get_Messages(messages[-1].snowflake,channelid))
        return messages

    def download_images(self):
        for channel in self.channels:
            c=self.get_channel(channel)
            s=self.get_server(c.server_id)
            path=f"downloads/{s.name}/{c.name}"
            make_folder(path)
            dl_id=1
            for message in tqdm(self.get_messages(channel),desc=f"processing channel: {c.name} of server: {s.name}"):
                if not message.file_url is None:
                    with open(f"{path}/{dl_id} - {message.file_name}","wb") as file:
                        #print(f"url={message.file_url}",end="\r\r")
                        response=self.download_session.get(message.file_url)
                        if response.status_code==200:
                            file.write(response.content)
                            dl_id+=1
                        else:
                            print(response.content)

    def queue_channel(self, channelids):
        self.channels.append(channelids)

    def get_channel(self, id):
        tmp=loads(self.session.get(f'https://discord.com/api/v9/channels/{id}').content)
        return Channel(id, tmp.get("guild_id"),tmp.get("name"))

    def get_server(self, id):
        tmp=loads(self.session.get(f'https://discord.com/api/v9/guilds/{id}').content)
        return Server(id, tmp.get("name"))

@dataclass
class Channel:
    id: int
    server_id: int
    name: str

@dataclass
class Server:
    id: int
    name: str

def make_folder(path):
    p=Path(path)
    if not p.exists():
        p.mkdir(parents=True)

@dataclass
class Message:
    snowflake: str
    text : str
    file_name: str = None
    file_url :str = None

def main(args:List):
    scraper = Scraper()
    for channel in args:
        scraper.queue_channel(channel)
    scraper.download_images()

if __name__=="__main__":
    main(sys.argv[1:])
