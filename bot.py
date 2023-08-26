"""bot.py"""
import importlib
import json
import os
from traceback import format_exception

from discord import Intents, Message
from discord.ext import commands
from discord.ext.commands import Bot, Context, errors

import Converters
import utils
import bot_utils

config_file = "config.json"
if config_file in os.listdir():
    with open(config_file, 'r', encoding="utf-8") as file:
        for k, v in json.load(file).items():
            if k and k not in os.environ:
                os.environ[k] = v

utils.initiate_db()
bot = Bot(command_prefix=".", case_insensitive=True, intents=Intents.default())
bot_utils_inst = bot_utils.BotUtils(bot)
bot.VERSION = "27/08/2023"
bot.config_file = config_file
bot.sessions = {}
bot.should_break_dict = {}  # format: {server: {command: True if it should be canceled, else False if it's running}}
categories = ("Eco", "Mix", "Social", "War", "Info")


async def start() -> None:
    """start function"""
    await bot.wait_until_ready()
    bot.allies = await utils.find_one("allies", "list", os.environ["nick"])
    bot.enemies = await utils.find_one("enemies", "list", os.environ["nick"])
    bot.friends = await utils.find_one("friends", "list", os.environ["nick"])
    for extension in categories:
        bot.load_extension(extension)
    bot.sessions["incognito"] = await bot_utils_inst.create_session()
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


@bot.event
async def on_message(message: Message) -> None:
    """Override original on_message, to allow other bots to invoke commands"""
    ctx = await bot.get_context(message)
    if ctx.valid:
        if "allowed_servers" in os.environ and str(ctx.guild.id) not in os.environ["allowed_servers"]:
            if "logs_channel_id" in os.environ:
                logs = bot.get_channel(int(os.environ["logs_channel_id"]))
                await logs.send(
                    f"**WARNING**: {ctx.author.mention} tried to invoke `{ctx.command}` in a forbidden guild named `{ctx.guild.name}` (ID `{ctx.guild.id}`) "
                    f"on channel named `{ctx.channel.name}`.\n"
                    f"Full message: `{message.content}`\nMore details:\n\n```{message}```")
            return
        await bot.invoke(ctx)


@bot.before_invoke
async def add_command(ctx: Context) -> None:
    utils.add_command(ctx)


@bot.after_invoke
async def remove_finished_command(ctx: Context) -> None:
    utils.remove_finished_command(ctx)


@bot.command()
async def update(ctx: Context, *, nick: Converters.IsMyNick) -> None:
    """Updates the code from the source.
    You can also use `.update ALL`"""
    session = await bot_utils_inst.get_session("incognito")
    async with session.get("https://api.github.com/repos/akiva0003/eSim/git/trees/main") as main:
        for file in (await main.json())["tree"]:
            file_name = file["path"]
            if not file_name.endswith(".py"):
                continue
            async with session.get(f"https://raw.githubusercontent.com/akiva0003/eSim/main/{file_name}") as r:
                with open(file_name, "w", encoding="utf-8", newline='') as f:
                    f.write(await r.text())
    async with session.get("https://api.github.com/repos/akiva0003/eSim/branches/main") as r:
        bot.VERSION = (await r.json())["commit"]["commit"]["author"]["date"]
    importlib.reload(utils)
    importlib.reload(bot_utils)
    bot.get_content = bot_utils.BotUtils(bot).get_content
    importlib.reload(Converters)
    utils.initiate_db()  # global variable reloaded
    for extension in categories:
        bot.reload_extension(extension)

    await ctx.send(f"**{nick}** updated. Running commands won't be affected.")


@bot.event
async def on_command_error(ctx: Context, error: Exception) -> None:
    """on command error"""
    error = getattr(error, 'original', error)
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("ERROR: you can't use this command in a private message!")
        return
    if isinstance(error, (commands.CommandNotFound, errors.CheckFailure)):
        return
    if isinstance(error, (errors.MissingRequiredArgument, errors.BadArgument)):
        if await utils.is_helper():
            await ctx.reply(f"```{''.join(format_exception(type(error), error, error.__traceback__))}```"[:1950])
        return
    if error.args and str(error.args[0]) == "message" and isinstance(error.args[1], dict):
        await ctx.reply(**error.args[1])
        return
    try:
        last_msg = str(list(await ctx.channel.history(limit=1).flatten())[0].content)
    except IndexError:
        print(f"I can't read the channel history. Please give me Admin role and check here all intents https://discord.com/developers/applications/{bot.user.id}/bot")
        return
    nick = utils.my_nick(ctx.channel.name)
    error_msg = f"**{nick}** ```{''.join(format_exception(type(error), error, error.__traceback__))}```"[:1950]
    if error_msg != last_msg:
        # Don't send from all users.
        try:
            await ctx.reply(error_msg)
        except Exception:
            await ctx.reply(error)

bot.get_content = bot_utils_inst.get_content
if os.environ["TOKEN"] != "PASTE YOUR TOKEN HERE":
    bot.loop.create_task(start())  # startup function
    bot.run(os.environ["TOKEN"])
else:
    print("ERROR: please follow those instructions: https://github.com/akiva0003/eSim#setup")
