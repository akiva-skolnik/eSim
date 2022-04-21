import json
import os
from asyncio import sleep
from datetime import datetime
from random import randint

if "database_url" in os.environ:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except:
        import pip
        pip.main(['install', "dnspython"])
        pip.main(['install', "motor"])
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
    return os.environ.get("help", "") == "ignore"


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
            for link in tree.xpath("//tr[position()<12]//td[1]//div[2]//a/@href"):
                link_id = link.split('=')[1]
                apiBattles = await bot.get_content(f"{URL}apiBattles.html?battleId={link_id}")
                if apiCitizen['citizenshipId'] in (apiBattles['attackerId'], apiBattles['defenderId']):
                    battle_id = link_id
                    break

        else:
            tree = await bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=NORMAL", return_tree=True)
            battle_id = tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/@href')
        if not battle_id:
            tree = await bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=RESISTANCE", return_tree=True)
            battle_id = tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/@href')
    except:
        tree = await bot.get_content(f"{URL}battles.html?filter=PRACTICE_BATTLE", return_tree=True)
        battle_id = tree.xpath('//tr[2]//td[1]//a/@href')
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


def get_parameter(parameter_string):
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


def my_nick(server):
    return os.environ.get(server, os.environ['nick'])
