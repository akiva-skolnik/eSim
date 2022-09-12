from asyncio import sleep
from datetime import datetime
import json
import os
from random import randint

client = None


def initiate_db():
    global client
    if "database_url" in os.environ:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ['database_url'])
        except:
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "dnspython"])
            subprocess.check_call([sys.executable, "-m", "pip", "install", "motor"])
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ['database_url'])
    else:
        client = None


async def find(server: str, collection: str) -> list:
    if client is not None:
        database = client[server][collection]
        return await database.find().to_list(50)
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r") as file:
                return [{**v, **{"_id": k}} for k, v in json.load(file).items()][:50]
        else:
            return list()


async def find_one(server: str, collection: str, ID: str) -> dict:
    if client is not None:
        database = client[server][collection]
        return await database.find_one({"_id": ID.lower()}, {"_id": 0}) or {}
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r") as file:
                return json.load(file).get(ID.lower(), {})
        else:
            return dict()


async def replace_one(server: str, collection: str, ID: str, data: dict) -> None:
    if client is not None:
        database = client[server][collection]
        await database.replace_one({'_id': ID.lower()}, data, True)
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r") as file:
                big_dict = json.load(file)
        else:
            big_dict = dict()
        big_dict[ID.lower()] = data
        with open(filename, "w") as file:
            json.dump(big_dict, file)


def get_region_and_country_names(api_regions, api_countries, region_id):
    for region in api_regions:
        if region["id"] == region_id:
            for country in api_countries:
                if country["id"] == region["homeCountry"]:
                    return region['name'], country['name']


async def is_helper(ctx=None):
    return "ignore" in os.environ.get("help", "")


async def get_battle_id(bot, nick, server, battle_id, prioritize_my_country=True):
    URL = f"https://{server}.e-sim.org/"
    apiCitizen = await bot.get_content(f"{URL}apiCitizenByName.html?name={nick.lower()}")
    occupantId = 0
    for row in await bot.get_content(f'{URL}apiMap.html'):
        if row['regionId'] == apiCitizen['currentLocationRegionId']:
            occupantId = row['occupantId']
            break
    try:
        if apiCitizen["level"] < 15:
            raise  # PRACTICE_BATTLE
        if battle_id == "event":
            tree = await bot.get_content(
                f"{URL}battles.html?countryId={apiCitizen['citizenshipId']}&filter=EVENT", return_tree=True)
            for link_id in get_ids_from_path(tree, "//tr[position()<12]//td[1]//div[2]//a"):
                apiBattles = await bot.get_content(f"{URL}apiBattles.html?battleId={link_id}")
                if apiCitizen['citizenshipId'] in (apiBattles['attackerId'], apiBattles['defenderId']):
                    battle_id = link_id
                    break

        else:
            tree = await bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=NORMAL", return_tree=True)
            battle_id = get_ids_from_path(tree, '//tr//td[1]//div//div[2]//div[2]/a')
        if not battle_id:
            tree = await bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=RESISTANCE", return_tree=True)
            battle_id = get_ids_from_path(tree, '//tr//td[1]//div//div[2]//div[2]/a')
    except:
        tree = await bot.get_content(f"{URL}battles.html?filter=PRACTICE_BATTLE", return_tree=True)
        battle_id = get_ids_from_path(tree, '//tr[2]//td[1]//a')
    if not battle_id:
        battle_id = [""]

    if prioritize_my_country:
        sides = [x.replace("xflagsMedium xflagsMedium-", "").replace("-", " ").lower() for x in
                 tree.xpath('//tr//td[1]//div//div//div/@class') if "xflagsMedium" in x]
        for _id, sides in zip(battle_id, sides):
            if apiCitizen["citizenship"].lower() in sides:
                return _id.replace("battle.html?id=", "")
    return battle_id[0].replace("battle.html?id=", "") or None


async def random_sleep(restores_left=1):
    if restores_left:
        now = datetime.now()
        minutes = int(now.strftime("%M"))
        sec = int(now.strftime("%S"))
        roundup = round(minutes + 5.1, -1)  # round up to the next ten minutes (00:10, 00:20 etc)
        random_number = randint(30, 570)  # getting random number
        sleep_time = random_number + (roundup - minutes) * 60 - sec
        await sleep(sleep_time)


async def location(bot, nick, server):
    """getting current location"""
    return (await bot.get_content(f"https://{server}.e-sim.org/apiCitizenByName.html?name={nick.lower()}")
            )['currentLocationRegionId']


async def get_bonus_region(bot, URL: str, side: str, api_battles: dict) -> int:
    if api_battles['type'] == "ATTACK":
        if side == "attacker":
            neighboursId = [z['neighbours'] for z in await bot.get_content(
                f"{URL}apiRegions.html") if z["id"] == api_battles['regionId']][0]
            api_map = await bot.get_content(f'{URL}apiMap.html')
            aBonus = [i for z in api_map for i in neighboursId if
                      i == z['regionId'] and z['occupantId'] == api_battles['attackerId']]
            if not aBonus:
                aBonus = [z['regionId'] for z in api_map if z['occupantId'] == api_battles['attackerId']]
            return aBonus[0]
        else:
            return api_battles['regionId']
    elif api_battles['type'] == "RESISTANCE":
        return api_battles['regionId']
    else:
        return 0


def get_parameter(parameter_string) -> (float, str):
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
    for parameter in all_parameters:
        if parameter in parameter_string.lower():
            try:
                value = float(parameter_string.split(" ")[-1].replace("%", "").strip())
                return value, parameter
            except:
                pass
    return 0, ""


def my_nick(server):
    return os.environ.get(server, os.environ['nick'])


def get_limits(tree):
    try:
        food_limit = tree.xpath('//*[@class="foodLimit"]')[0].text
    except IndexError:
        food_limit = tree.xpath('//*[@id="foodLimit2"]')[0].text

    try:
        gift_limit = tree.xpath('//*[@class="giftLimit"]')[0].text
    except IndexError:
        gift_limit = tree.xpath('//*[@id="giftLimit2"]')[0].text
    return int(food_limit), int(gift_limit)


def get_storage(tree, q=5):
    try:
        food_storage = tree.xpath(f'//*[@id="foodQ{q}"]/text()')[0]
        gift_storage = tree.xpath(f'//*[@id="giftQ{q}"]/text()')[0]
    except IndexError:
        food_storage = tree.xpath(f'//*[@id="sfoodQ{q}"]/text()')[0]
        gift_storage = tree.xpath(f'//*[@id="sgiftQ{q}"]/text()')[0]
    return int(food_storage), int(gift_storage)


def get_id(string):
    return string.split("(")[-1].split(")")[0].split("=")[-1].split("&")[0].strip()


def get_ids_from_path(tree, path):
    # temp function
    ids = tree.xpath(path + "/@href")
    if ids and "#" in ids[0]:
        ids = [get_id(x) for x in tree.xpath(path + "/@onclick")]
    else:
        ids = [x.split("=")[-1].split("&")[0].strip() for x in ids]
    return ids
