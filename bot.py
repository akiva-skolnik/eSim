from asyncio import sleep
from json import load
from os import environ
from traceback import format_exception

from aiohttp import ClientSession, ClientTimeout
from discord.ext import commands
from discord.ext.commands import BadArgument, Bot
from lxml.html import fromstring
from motor.motor_asyncio import AsyncIOMotorClient

bot = Bot(command_prefix=".", case_insensitive=True)

with open("config.json", 'r') as file:
    environ.update(load(file))

for extension in ("Eco", "Mix", "Social", "War"):
    bot.load_extension(extension)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)


async def create_session():
    return ClientSession(timeout=ClientTimeout(total=100), headers={"headers": environ["headers"]})


bot.VERSION = "07/07/2021"
bot.session = bot.loop.run_until_complete(create_session())
bot.cookies = {}
bot.client = (AsyncIOMotorClient(environ['database_url']))["database"]
cookies_database = bot.client["cookies"]


async def inner_get_content(link, data=None, return_url=False, return_type=""):
    method = "get" if data is None else "post"
    if not return_type:
        return_type = "json" if "api" in link else "html"
    server = link.split("#")[0].replace("http://", "https://").split("https://")[1].split(".e-sim.org")[0]
    if bot.session.closed:
        bot.session = await create_session()
    for _ in range(5):
        try:
            async with bot.session.get(link, cookies=bot.cookies.get(server), ssl=True) if method == "get" else \
                    bot.session.post(link, cookies=bot.cookies.get(server), data=data, ssl=True) as respond:
                if "google.com" in str(respond.url) or respond.status == 403:
                    await sleep(5)
                    continue

                if any(t in str(respond.url) for t in ("notLoggedIn", "error")):
                    raise BadArgument(f"you are not logged in")

                if respond.status == 200:
                    if method == "post":
                        if "fight" in link:
                            try:
                                return fromstring(await respond.text(encoding='utf-8')), respond.status
                            except:
                                return fromstring((await respond.text(encoding='utf-8'))[1:]), respond.status
                        try:
                            return str(respond.url) if not return_url else fromstring(
                                await respond.text(encoding='utf-8'))
                        except:
                            return str(respond.url) if not return_url else fromstring(
                                (await respond.text(encoding='utf-8'))[1:])
                    if return_type == "json":
                        try:
                            api = await respond.json(content_type=None)
                        except:
                            await sleep(5)
                            continue
                        if "error" in api:
                            raise BadArgument(api["error"])
                        return api if "apiBattles" not in link else api[0]
                    else:
                        try:
                            return fromstring(await respond.text(encoding='utf-8')) if not return_url else str(
                                respond.url)
                        except:
                            return fromstring((await respond.text(encoding='utf-8'))[1:]) if not return_url else str(
                                respond.url)
                else:
                    await sleep(5)
        except Exception as e:
            if type(e) in (BadArgument, OSError):
                raise e
            await sleep(5)

    raise OSError(link)


async def get_content(link, login_first=False, data=None, return_url=False, return_type=""):
    nick = environ['nick']
    link = link.split("#")[0].replace("http://", "https://")
    server = link.split("https://", 1)[1].split(".e-sim.org", 1)[0]
    if not bot.cookies:
        bot.cookies = await cookies_database.find_one({"_id": nick}, {"_id": 0}) or {}
    URL = f"https://{server}.e-sim.org/"
    notLoggedIn = False
    if server in bot.cookies:
        try:
            if not login_first:
                tree = await inner_get_content(link, data, return_url, return_type)
            else:
                tree = await inner_get_content(URL + "storage.html", None, return_url, return_type)
        except BadArgument as e:
            if "you are not logged in" not in str(e):
                raise e
            else:
                notLoggedIn = True
    if notLoggedIn or server not in bot.cookies:
        await bot.session.close()
        bot.session = await create_session()

        payload = {'login': environ.get(server, environ['nick']),
                   'password': environ.get(server+"_pw", environ['pw']), "submit": "Login"}
        async with bot.session.get(URL, ssl=True) as _:
            async with bot.session.post(URL + "login.html", data=payload, ssl=True) as r:
                if "index.html?act=login" not in str(r.url):
                    print(r.url)
                    raise BadArgument("Failed to login")
                bot.cookies.update({server: {cookie.key: cookie.value for cookie in bot.session.cookie_jar}})
        await cookies_database.replace_one({"_id": nick}, bot.cookies, True)
        tree = await inner_get_content(link, data, return_url, return_type)
    if login_first and not notLoggedIn:
        tree = await inner_get_content(link, data, return_url, return_type)
    return tree


@bot.event
async def on_message(message):
    """allow other bots to invoke commands"""
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    error = getattr(error, 'original', error)
    if isinstance(error, RuntimeError):
        return
    if isinstance(error, commands.NoPrivateMessage):
        return await ctx.send("Sorry, you can't use this command in a private message!")
    if isinstance(error, commands.CommandNotFound):
        return

    last_msg = str(list(await ctx.channel.history(limit=1).flatten())[0].content)
    error_msg = f"```{''.join(format_exception(type(error), error, error.__traceback__))}```"
    if error_msg != last_msg:
        # Don't send from all users.
        try:
            await ctx.send(error_msg)
        except:
            await ctx.send(error)


bot.get_content = get_content
bot.run(environ["TOKEN"])
# todo: more converters (k - 000 f.e)
# todo: default nick command.
