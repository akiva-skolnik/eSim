"""bot.py"""
import importlib
import json
import os
from asyncio import sleep
from traceback import format_exception

from aiohttp import ClientSession
from discord import Intents
from discord.ext import commands
from discord.ext.commands import Bot, errors
from lxml.html import fromstring

import utils
import Converters

config_file = "config.json"
if config_file in os.listdir():
    with open(config_file, 'r', encoding="utf-8") as file:
        for k, v in json.load(file).items():
            if k and k not in os.environ:
                os.environ[k] = v

utils.initiate_db()
bot = Bot(command_prefix=".", case_insensitive=True, intents=Intents.default())
bot.VERSION = "23/06/2023"
bot.config_file = config_file
bot.sessions = {}
bot.should_break_dict = {}  # format: {server: {command: True if it should be canceled, else False if it's running}}
categories = ("Eco", "Mix", "Social", "War", "Info")


async def create_session() -> ClientSession:
    """create session"""
    return ClientSession(headers={"User-Agent": os.environ["headers"]})


async def get_session(server: str) -> ClientSession:
    """get session"""
    if server not in bot.sessions:
        bot.sessions[server] = await create_session()
    return bot.sessions[server]


async def close_session(server: str) -> None:
    """close session"""
    if server in bot.sessions:
        await bot.sessions[server].close()
        del bot.sessions[server]


async def start():
    """start function"""
    await bot.wait_until_ready()
    bot.allies = await utils.find_one("allies", "list", os.environ["nick"])
    bot.enemies = await utils.find_one("enemies", "list", os.environ["nick"])
    for extension in categories:
        bot.load_extension(extension)
    bot.sessions["incognito"] = await create_session()
    print('Logged in as')
    print(bot.user.name)
    print(f"Invite: https://discordapp.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot")

    # you should change the following line in all your accounts (except for 1) to
    # `"help": ""` https://github.com/akiva0003/eSim/blob/main/config.json#L9
    # this way the bot will send only one help commands.
    if not await utils.is_helper():
        bot.remove_command("help")

    # restart saved long functions
    for d in (await utils.find_one("auto", "work", os.environ['nick'])).values():
        if isinstance(d, list):  # old version
            d = d[0]
        channel = bot.get_channel(int(d["channel_id"]))
        message = await channel.fetch_message(int(d["message_id"]))
        ctx = await bot.get_context(message)
        bot.loop.create_task(ctx.invoke(
            bot.get_command("auto_work"), d["work_sessions"], d["chance_to_skip_work"], nick=d["nick"]))

    for d in (await utils.find_one("auto", "motivate", os.environ['nick'])).values():
        if isinstance(d, list):  # old version
            d = d[0]
        channel = bot.get_channel(int(d["channel_id"]))
        message = await channel.fetch_message(int(d["message_id"]))
        ctx = await bot.get_context(message)
        bot.loop.create_task(ctx.invoke(bot.get_command("auto_motivate"), d["chance_to_skip_a_day"], nick=d["nick"]))

    for d1 in (await utils.find_one("auto", "fight", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("auto_fight"), d["nick"], d["restores"], d["battle_id"],
                d["side"], d["wep"], d["food"], d["gift"], d["ticket_quality"], d["chance_to_skip_restore"]))

    for d1 in (await utils.find_one("auto", "hunt", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("hunt"), d["nick"], d["max_dmg_for_bh"], d["weapon_quality"], d["start_time"],
                d["ticket_quality"], d.get("consume_first", "none")))

    for d1 in (await utils.find_one("auto", "hunt_battle", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("hunt_battle"), d["nick"], d["link"], d["side"], d["dmg_or_hits_per_bh"],
                d["weapon_quality"], d["food"], d["gift"], d["start_time"]))

    for d1 in (await utils.find_one("auto", "watch", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("watch"), d["nick"], d["battle"], d["side"], d["start_time"], d["keep_wall"],
                d["let_overkill"], d["weapon_quality"], d["ticket_quality"], d["consume_first"], d.get("medkits", 0)))


async def inner_get_content(link: str, server: str, data=None, return_tree=False):
    """inner get content"""
    method = "get" if data is None else "post"
    return_type = "json" if "api" in link or "battleScore" in link else "html"
    session = await get_session(server)
    for _ in range(5):
        try:
            async with session.get(link, ssl=True) if method == "get" else \
                    session.post(link, data=data, ssl=True) as respond:
                if "google.com" in str(respond.url) or respond.status == 403:
                    await sleep(5)
                    continue

                if any(t in str(respond.url) for t in ("notLoggedIn", "error")):
                    raise ConnectionError("notLoggedIn")

                if respond.status == 200:
                    if return_type == "json":
                        try:
                            api = await respond.json(content_type=None)
                        except Exception:
                            await sleep(5)
                            continue
                        if "error" in api:
                            raise ConnectionError(api["error"])
                        return api if "apiBattles" not in link else api[0]
                    try:
                        tree = fromstring(await respond.text(encoding='utf-8'))
                    except Exception:
                        tree = fromstring(await respond.text(encoding='utf-8'))[1:]
                    logged = tree.xpath('//*[@id="command"]')
                    if server != "incognito" and any("login.html" in x.action for x in logged):
                        raise ConnectionError("notLoggedIn")
                    if isinstance(return_tree, str):
                        return tree, str(respond.url)
                    return tree if return_tree else str(respond.url)
                await sleep(5)
        except Exception as exc:
            if isinstance(exc, ConnectionError):
                raise exc
            await sleep(5)

    raise ConnectionError(link)


async def get_content(link, data=None, return_tree=False, incognito=False):
    """get content"""
    link = link.split("#")[0].replace("http://", "https://")
    server = "incognito" if incognito else link.split("https://", 1)[1].split(".e-sim.org", 1)[0]
    nick = utils.my_nick(server)
    url = f"https://{server}.e-sim.org/"
    not_logged_in = False
    tree = None
    try:
        tree = await inner_get_content(link, server, data, return_tree)
    except ConnectionError as exc:
        if "notLoggedIn" != str(exc):
            raise exc
        not_logged_in = True
    if not_logged_in and not incognito:
        await close_session(server)

        payload = {'login': nick, 'password': os.environ.get(server + "_password", os.environ.get('password')), "submit": "Login"}
        async with (await get_session(server)).get(url, ssl=True) as _:
            async with (await get_session(server)).post(url + "login.html", data=payload, ssl=True) as r:
                print(r.url)
                if "index.html?act=login" not in str(r.url):
                    raise ConnectionError(f"{nick} - Failed to login {r.url}")
        tree = await inner_get_content(link, server, data, return_tree)
    if tree is None:
        tree = await inner_get_content(link, server, data, return_tree)
    return tree


@bot.event
async def on_message(message):
    """Allow other bots to invoke commands"""
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.invoke(ctx)


@bot.before_invoke
async def add_command(ctx):
    utils.add_command(ctx)


@bot.after_invoke
async def remove_finished_command(ctx):
    utils.remove_finished_command(ctx)


@bot.command()
async def update(ctx, *, nick: Converters.IsMyNick):
    """Updates the code from the source.
    You can also use `.update ALL`"""
    server = ctx.channel.name
    async with (await get_session(server)).get(
            "https://api.github.com/repos/akiva0003/eSim/git/trees/main") as main:
        for file in (await main.json())["tree"]:
            file_name = file["path"]
            if not file_name.endswith(".py"):
                continue
            async with (await get_session(server)).get(
                    f"https://raw.githubusercontent.com/akiva0003/eSim/main/{file_name}") as r:
                with open(file_name, "w", encoding="utf-8", newline='') as f:
                    f.write(await r.text())
    async with (await get_session(server)).get("https://api.github.com/repos/akiva0003/eSim/branches/main") as r:
        bot.VERSION = (await r.json())["commit"]["commit"]["author"]["date"]
    importlib.reload(utils)
    importlib.reload(Converters)
    utils.initiate_db()  # global variable reloaded
    for extension in categories:
        bot.reload_extension(extension)

    await ctx.send(f"**{nick}** updated. Running commands won't be affected.")


@bot.event
async def on_command_error(ctx, error):
    """on command error"""
    error = getattr(error, 'original', error)
    if isinstance(error, commands.NoPrivateMessage):
        return await ctx.send("ERROR: you can't use this command in a private message!")
    if isinstance(error, (commands.CommandNotFound, errors.CheckFailure)):
        return
    if isinstance(error, (errors.MissingRequiredArgument, errors.BadArgument)):
        if await utils.is_helper():
            await ctx.reply(f"```{''.join(format_exception(type(error), error, error.__traceback__))}```"[:1950])
        return
    last_msg = str(list(await ctx.channel.history(limit=1).flatten())[0].content)
    nick = utils.my_nick(ctx.channel.name)
    error_msg = f"**{nick}** ```{''.join(format_exception(type(error), error, error.__traceback__))}```"[:1950]
    if error_msg != last_msg:
        # Don't send from all users.
        try:
            await ctx.reply(error_msg)
        except Exception:
            await ctx.reply(error)

bot.get_content = get_content
if os.environ["TOKEN"] != "PASTE YOUR TOKEN HERE":
    bot.loop.create_task(start())  # startup function
    bot.run(os.environ["TOKEN"])
else:
    print("ERROR: please follow those instructions: https://github.com/akiva0003/eSim#setup")
