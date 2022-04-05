
# E-sim python *improved* library

[![Flag Counter](https://s01.flagcounter.com/mini/5j6R/bg_FFFFFF/txt_000000/border_CCCCCC/flags_0/)](https://info.flagcounter.com/5j6R)

**(This is a better and up-to-date version of https://github.com/e-sim-python/scripts, is designed mainly for a group / VPS, 
but it's also good for those who wants to play e-sim using discord)**

If you appreciate my hard word, please consider [buying me a coffee](https://www.buymeacoffee.com/eSimPython). Thanks :)

#### Table of Content:
1. [Introduction](https://github.com/e-sim-python/eSim#introduction)
2. [Installation](https://github.com/e-sim-python/eSim#installation)
3. [Setup](https://github.com/e-sim-python/eSim#setup)

## Introduction
**This version is the right way, without workaround tricks to implement this library.**  
(which made in the first place to allow multiple usage cases)  
#### This implement should drastically reduce the number of bugs.


## Installation:
1. Download and Install [python 3.6+](https://www.python.org/downloads/) and [add to path](http://prntscr.com/uwvy5z). 
2. Download the e-sim library as a zip file ([Code -> download ZIP](https://github.com/e-sim-python/eSim/archive/refs/heads/main.zip)) and extract it, If you can't extract, [download WinRAR](https://www.rarlab.com/) first.
3. Open your CMD ( Command Line ), type `pip install -r C:/Users/YOUR_NAME/Downloads/eSim-main/requirements.txt` (or whatever the path is on your computer)  
   Alternatively, paste this line there: `pip install discord.py lxml pytz`.  
   Then, press enter and wait for the external packages to get installed on your computer.

## Setup:
1. [Get your discord token](https://devsjournal.com/how-to-get-your-discord-token.html)  
   invite the bot to your server, and name the channels as the e-sim servers (channels names might be #secura, #alpha, etc)
2. Fill your details on [config.json](https://github.com/e-sim-python/eSim/blob/main/config.json)  
Note: if you have a different nick in other servers, add lines to this file as follows: `"server": "your_nick",`  
   The same goes for different pw: `"server_pw": "123456",`  
   Example: `"aura": "Admin", "aura_pw": "12345678",`
3. Run `bot.py`.

  

Optional: Create an account at https://www.mongodb.com/ and get a URL with your credentials:  
   - Click "connect" (or "connect to your cluster").
   - Connect your application.
   - Driver = Python, and now just copy the URL and replace the <password> with your mongoDB password.  
   (The URL should look similar to this one: `mongodb+srv://YOUR_NICK:YOUR_PASSWORD@cluster0-SOME_ID.mongodb.net/database?retryWrites=true&w=majority`)  
   It's also recommended adding the IP `0.0.0.0/0` at the "Network Access" tab.   
   - add `"database_url": "YOUR DATABASE URL",` at [config.json](https://github.com/e-sim-python/eSim/blob/main/config.json)

# Good luck & have fun!
