
# E-sim python library

[![Flag Counter](https://s01.flagcounter.com/mini/5j6R/bg_FFFFFF/txt_000000/border_CCCCCC/flags_0/)](https://info.flagcounter.com/5j6R)


If you appreciate my hard word, please consider [buying me a coffee](https://www.buymeacoffee.com/RipEsim). Thanks :)

#### Table of Content:
1. [Introduction](https://github.com/akiva0003/eSim#introduction)
2. [Installation](https://github.com/akiva0003/eSim#installation)
3. [Setup](https://github.com/akiva0003/eSim#setup)

## Introduction
The E-sim Python Library is a collection of open-source scripts that enables users to play e-sim using discord commands.  

This provides a convenient way to control multiple accounts simultaneously by creating a group of close partners or VPS bots.

The library is easy to use and is a great tool for those who want to play e-sim using discord commands.  

With clear instructions, users should have no difficulty in setting it up and using it.  

Here's what you get when you type `.help `:

![demo](https://img001.prntscr.com/file/img001/c-2JiXkqTPCeWzH4iliMqQ.jpeg)  
![demo](https://img001.prntscr.com/file/img001/D7uhlwo-QXGBbmpdl71gNQ.jpeg)  

`.help auto_fight`  
![demo](https://img001.prntscr.com/file/img001/NVo-7jMmQmGsGa018yKZ6w.jpeg)

## Installation:
1. Download and Install [python 3.6+](https://www.python.org/downloads/) and [add to path](http://prntscr.com/uwvy5z). 
2. Download the e-sim library as a zip file ([Code -> download ZIP](https://github.com/akiva0003/eSim/archive/refs/heads/main.zip)) and extract it, If you can't extract, [download WinRAR](https://www.rarlab.com/) first.
3. Open your CMD (Command Line) from the Start Menu, and paste this line there: `pip install discord.py==1.7.3 lxml pytz`.  
   Then, press enter and wait for the external packages to get installed on your computer.

## Setup:
1. [Get your discord token](https://devsjournal.com/how-to-get-your-discord-token.html) (check all intents and make it private)  
   invite the bot to your server, and name the channels as the e-sim servers (channels names might be #secura, #alpha, etc)  
   Invite link: https://discordapp.com/api/oauth2/authorize?client_id=YOUR_BOT_ID_HERE&permissions=8&scope=bot (replace `YOUR_BOT_ID_HERE`)
2. Fill your details on [config.json](https://github.com/akiva0003/eSim/blob/main/config.json)  
   - Get the `TOKEN` form the previous step.
   - Note: if you have a different nick in other servers, add lines to this file as follows: `"server": "your nick",`  
   The same goes for different password: `"server_password": "123456",`  
   Example: `"suna": "Admin", "suna_password": "12345678",`   
   - Google "my user agent", and replace the `headers` with the result.  
   > **IMPORTANT**:  By default, anyone in your channel can use the command `execute` (including revealing your password).  
   > If you want to change it, add to your config file thr pair: `"trusted_users_ids": [00000, 11111]` ("Copy User ID" within Discord).  
   > Only users in that list will be able to use `execute` (you can leave it empty)
3. Run `bot.py` (double-click on it and press F5, or type in your CMD `python3 PATH/TO/CURRENT/FOLDER/bot.py`)

  

Optional: Create an account at https://www.mongodb.com/ and get a base_url with your credentials:  
   - Click "connect" (or "connect to your cluster").
   - Connect your application.
   - Driver = Python, and now just copy the base_url and replace the <password> with your mongoDB password.  
   (The base_url should look similar to this one: `mongodb+srv://YOUR_NICK:YOUR_PASSWORD@cluster0-SOME_ID.mongodb.net/database?retryWrites=true&w=majority`)  
   It's also recommended adding the IP `0.0.0.0/0` at the "Network Access" tab.   
   - add `"database_url": "YOUR DATABASE base_url",` at [config.json](https://github.com/akiva0003/eSim/blob/main/config.json)


# Good luck & have fun!
