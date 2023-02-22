"""utils.py"""
import json
import os
from asyncio import sleep
from datetime import datetime
from random import randint

client = None


def initiate_db() -> None:
    """initiate db"""
    global client
    if "database_url" in os.environ:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ['database_url'])
        except Exception:
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "dnspython"])
            subprocess.check_call([sys.executable, "-m", "pip", "install", "motor"])
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ['database_url'])
    else:
        client = None


async def find(server: str, collection: str) -> list:
    """find first 50 documents"""
    if client is not None:
        database = client[server][collection]
        return await database.find().to_list(50)
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r", encoding='utf-8', errors='ignore') as file:
                return [{**v, **{"_id": k}} for k, v in json.load(file).items()][:50]
        return []


async def find_one(server: str, collection: str, document: str) -> dict:
    """find one document"""
    if client is not None:
        database = client[server][collection]
        return await database.find_one({"_id": document.lower()}, {"_id": 0}) or {}
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r", encoding='utf-8', errors='ignore') as file:
                return json.load(file).get(document.lower(), {})
        return {}


async def replace_one(server: str, collection: str, document: str, data: dict) -> None:
    """replace one document"""
    if client is not None:
        database = client[server][collection]
        await database.replace_one({'_id': document.lower()}, data, True)
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r", encoding='utf-8', errors='ignore') as file:
                big_dict = json.load(file)
        else:
            big_dict = {}
        big_dict[document.lower()] = data
        with open(filename, "w", encoding='utf-8', errors='ignore') as file:
            json.dump(big_dict, file)


def get_region_and_country_names(api_regions: list, api_countries: list, region_id: int) -> (str, str):
    """get region and country names"""
    for region in api_regions:
        if region["id"] == region_id:
            for country in api_countries:
                if country["id"] == region["homeCountry"]:
                    return region['name'], country['name']
    return "", ""


async def is_helper(ctx=None):
    """is helper"""
    return "help" not in os.environ


async def get_battle_id(bot, nick: str, server: str, battle_ids, prioritize_my_country: bool = True) -> str:
    """get battle id"""
    base_url = f"https://{server}.e-sim.org/"
    api_citizen = await bot.get_content(f"{base_url}apiCitizenByName.html?name={nick.lower()}")
    occupant_id = 0
    for row in await bot.get_content(f'{base_url}apiMap.html'):
        if row['regionId'] == api_citizen['currentLocationRegionId']:
            occupant_id = row['occupantId']
            break
    try:
        if api_citizen["level"] < 15:
            raise  # PRACTICE_BATTLE
        if battle_ids == "event":
            tree = await bot.get_content(
                f"{base_url}battles.html?countryId={api_citizen['citizenshipId']}&filter=EVENT", return_tree=True)
            for link_id in get_ids_from_path(tree, '//*[@class="battleHeader"]//a'):
                api_battles = await bot.get_content(f"{base_url}apiBattles.html?battleId={link_id}")
                if api_citizen['citizenshipId'] in (api_battles['attackerId'], api_battles['defenderId']):
                    battle_ids = link_id
                    break

        else:
            tree = await bot.get_content(f"{base_url}battles.html?countryId={occupant_id}&filter=NORMAL", return_tree=True)
            battle_ids = get_ids_from_path(tree, '//*[@class="battleHeader"]//a')
        if not battle_ids:
            tree = await bot.get_content(f"{base_url}battles.html?countryId={occupant_id}&filter=RESISTANCE", return_tree=True)
            battle_ids = get_ids_from_path(tree, '//*[@class="battleHeader"]//a')
    except Exception:
        tree = await bot.get_content(f"{base_url}battles.html?filter=PRACTICE_BATTLE", return_tree=True)
        battle_ids = get_ids_from_path(tree, '//*[@class="battleHeader"]//a')
    if not battle_ids:
        battle_ids = [""]

    if prioritize_my_country:
        sides = tree.xpath('//*[@class="battleHeader"]//em/text()')
        for battle_id, sides in zip(battle_ids, sides):
            if api_citizen["citizenship"].lower() in sides.lower():
                return battle_id.replace("battle.html?id=", "")
    return battle_ids[0].replace("battle.html?id=", "") or None


async def random_sleep(restores_left: int = 1) -> None:
    """random sleep"""
    if restores_left:
        now = datetime.now()
        minutes = int(now.strftime("%M"))
        sec = int(now.strftime("%S"))
        roundup = round(minutes + 5.1, -1)  # round up to the next ten minutes (00:10, 00:20 etc)
        random_number = randint(30, 570)  # getting random number
        sleep_time = random_number + (roundup - minutes) * 60 - sec
        await sleep(sleep_time)


async def location(bot, nick: str, server: str) -> int:
    """getting current location"""
    return (await bot.get_content(f"https://{server}.e-sim.org/apiCitizenByName.html?name={nick.lower()}")
            )['currentLocationRegionId']


async def get_bonus_region(bot, base_url: str, side: str, api_battles: dict) -> int:
    """get bonus region"""
    if api_battles['type'] == "ATTACK":
        if side == "attacker":
            neighbours_id = [z['neighbours'] for z in await bot.get_content(
                f"{base_url}apiRegions.html") if z["id"] == api_battles['regionId']][0]
            api_map = await bot.get_content(f'{base_url}apiMap.html')
            a_bonus = [i for z in api_map for i in neighbours_id if
                       i == z['regionId'] and z['occupantId'] == api_battles['attackerId']]
            if not a_bonus:
                a_bonus = [z['regionId'] for z in api_map if z['occupantId'] == api_battles['attackerId']]
            return a_bonus[0]
        else:
            return api_battles['regionId']
    elif api_battles['type'] == "RESISTANCE":
        return api_battles['regionId']
    else:
        return 0


def get_parameter(parameter_string: str) -> (float, str):
    """get parameter"""
    all_parameters = {"avoid": "Chance to avoid damage",
                      "max": "Increased maximum damage",
                      "crit": "Increased critical hit chance",
                      "damage": "Increased damage", "dmg": "Increased damage",
                      "miss": "Miss chance reduction",
                      "flight": "Chance for free flight",
                      "consume": "Save ammunition",
                      "eco": "Increased economy skill",
                      "str": "Increased strength",
                      "hit": "Increased hit",
                      "less": "Less weapons for Berserk",
                      "find": "Find a weapon",
                      "split": "Improved split",
                      "production": "Bonus * production",
                      "merging": "Merge bonus",
                      "merge": "Reduced equipment merge price",
                      "restore": "Restoration",
                      "increase": "Increase other parameters"}

    parameter_string = parameter_string.strip().lower()
    for parameter in all_parameters:
        if parameter in parameter_string:
            try:
                value = float(parameter_string.split(" ")[-1].replace("%", "").strip())
                return value, parameter
            except Exception:
                pass
    return 0, ""


def my_nick(server: str = "") -> str:
    """Get my nick"""
    return os.environ.get(server, os.environ['nick'])


def get_limits(tree) -> (int, int):
    """get limits"""
    try:
        food_limit = tree.xpath('//*[@class="foodLimit"]')[0].text
    except IndexError:
        food_limit = tree.xpath('//*[@id="foodLimit2"]')[0].text

    try:
        gift_limit = tree.xpath('//*[@class="giftLimit"]')[0].text
    except IndexError:
        gift_limit = tree.xpath('//*[@id="giftLimit2"]')[0].text
    return int(food_limit), int(gift_limit)


def get_storage(tree, q: int = 5) -> (int, int):
    try:
        food_storage = tree.xpath(f'//*[@id="foodQ{q}"]/text()')[0]
        gift_storage = tree.xpath(f'//*[@id="giftQ{q}"]/text()')[0]
    except IndexError:
        food_storage = tree.xpath(f'//*[@id="sfoodQ{q}"]/text()')[0]
        gift_storage = tree.xpath(f'//*[@id="sgiftQ{q}"]/text()')[0]
    return int(food_storage), int(gift_storage)


def get_id(string: str) -> str:
    return "".join(x for x in string.split("=")[-1].split("&")[0] if x.isdigit())


def get_ids_from_path(tree, path: str) -> list:
    """get ids from path"""
    ids = tree.xpath(path + "/@href")
    if ids and all("#" == x for x in ids):
        ids = [get_id([y for y in x.values() if "Utils" in y][0]) for x in tree.xpath(path)]
    else:
        ids = [x.split("=")[-1].split("&")[0].strip() for x in ids]
    return ids


async def save_command(ctx, server: str, collection: str, info: dict) -> bool:
    """returns True if the command is already running"""
    data = await find_one(server, collection, os.environ['nick'])
    new_dict = {"channel_id": str(ctx.channel.id), "message_id": str(ctx.message.id), "nick": my_nick(ctx.channel.name)}
    new_dict.update(info)

    if new_dict != data.get(ctx.channel.name):
        data[ctx.channel.name] = new_dict
        await replace_one(server, collection, os.environ['nick'], data)
        await ctx.send(f"**{my_nick(ctx.channel.name)}** Alright.")
        if ctx.bot.should_break_dict.get(ctx.channel.name, {}).get(str(ctx.command)) is False:
            return True
    return False


async def remove_command(ctx, server: str, collection: str) -> None:
    """remove command"""
    data = await find_one(server, collection, os.environ['nick'])
    if ctx.channel.name in data:
        del data[ctx.channel.name]
        await replace_one(server, collection, os.environ['nick'], data)


async def get_nicks(server: str, nicks: str) -> iter:
    """get nicks"""
    for nick in (x.strip() for x in nicks.replace('"', "").replace("'", "").split(",") if x.strip()):
        if nick.lower() == "all":
            nick = my_nick(server)
            await sleep(randint(1, 20))

        if nick.lower() != my_nick(server).lower():
            continue
        yield nick
