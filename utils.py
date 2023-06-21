"""utils.py"""
import json
import os
from asyncio import sleep
from datetime import datetime
from random import choice, randint, uniform

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


async def find(database: str, collection: str) -> list:
    """find first 50 documents"""
    if client is not None:
        database = client[database][collection]
        return await database.find().to_list(50)
    else:
        filename = f"{database}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r", encoding='utf-8', errors='ignore') as file:
                return [{**v, **{"_id": k}} for k, v in json.load(file).items()][:50]
        return []


async def find_one(database: str, collection: str, document: str) -> dict:
    """find one document"""
    if client is not None:
        database = client[database][collection]
        return await database.find_one({"_id": document.lower()}, {"_id": 0}) or {}
    else:
        filename = f"{database}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r", encoding='utf-8', errors='ignore') as file:
                return json.load(file).get(document.lower(), {})
        return {}


async def replace_one(database: str, collection: str, document: str, data: dict) -> None:
    """replace one document"""
    if client is not None:
        database = client[database][collection]
        await database.replace_one({'_id': document.lower()}, data, True)
    else:
        filename = f"{database}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r", encoding='utf-8', errors='ignore') as file:
                big_dict = json.load(file)
        else:
            big_dict = {}
        big_dict[document.lower()] = data
        with open(filename, "w", encoding='utf-8', errors='ignore') as file:
            json.dump(big_dict, file)


async def chunker(seq: list, size: int) -> iter:
    """list to sub lists"""
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


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


def get_products(tree) -> dict:
    products = {}
    for item in tree.xpath("//div[@class='storage']"):
        name = item.xpath("div[2]/img/@src")[0].replace("//cdn.e-sim.org//img/productIcons/", "").replace(
            "Rewards/", "").replace(".png", "")
        if name.lower() in ["iron", "grain", "diamonds", "oil", "stone", "wood"]:
            quality = ""
        else:
            quality = item.xpath("div[2]/img/@src")[1].replace(
                "//cdn.e-sim.org//img/productIcons/", "").replace(".png", "")
        products[f"{quality.title()} {name}"] = int(item.xpath("div[1]/text()")[0].strip())
    return products


async def random_sleep(restores_left: int = 1) -> None:
    """random sleep"""
    if restores_left:
        now = datetime.now()
        minutes = int(now.strftime("%M"))
        sec = int(now.strftime("%S"))
        roundup = round(minutes + 5.1, -1)  # round up to the next ten minutes (00:10, 00:20 etc)
        random_number = uniform(30, 570)  # getting random number
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


async def update_info(server: str, nick: str, d: dict) -> None:
    """update limits"""
    data = await find_one(server, "info", nick)
    changed = False
    for k, v in d.items():
        if data.get(k) != v:
            data[k] = v
            changed = True
    if changed:
        await replace_one(server, "info", nick, data)


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


def add_command(ctx):
    server = ctx.channel.name
    cmd = str(ctx.command)
    if server not in ctx.bot.should_break_dict:
        ctx.bot.should_break_dict[server] = {}
    ctx.bot.should_break_dict[server][cmd] = False


def remove_finished_command(ctx):
    server = ctx.channel.name
    if str(ctx.command) in ctx.bot.should_break_dict.get(server, {}):
        del ctx.bot.should_break_dict[server][str(ctx.command)]


async def save_command(ctx, server: str, collection: str, info: dict) -> None:
    """saves the command in the database, so that it can be re-invoked after reboot"""
    cmd = str(ctx.command)
    data = await find_one(server, collection, os.environ['nick'])
    new_dict = {"channel_id": str(ctx.channel.id), "message_id": str(ctx.message.id),
                "nick": my_nick(ctx.channel.name), "command":cmd}
    new_dict.update(info)
    if ctx.channel.name not in data:
        data[ctx.channel.name] = []
    if not isinstance(data[ctx.channel.name], list):  # old version
        data[ctx.channel.name] = [data[ctx.channel.name]]
    if new_dict not in data[ctx.channel.name]:
        data[ctx.channel.name].append(new_dict)
        await replace_one(server, collection, os.environ['nick'], data)
    add_command(ctx)
    if "-" in cmd and cmd.split("-")[0] in ctx.bot.should_break_dict.get(server, {}):
        del ctx.bot.should_break_dict[server][cmd.split("-")[0]]


async def remove_command(ctx, database: str, collection: str) -> None:
    """remove command"""
    remove_finished_command(ctx)
    data = await find_one(database, collection, os.environ['nick'])
    if ctx.channel.name in data:
        if not isinstance(data[ctx.channel.name], list):  # old version
            data[ctx.channel.name] = [data[ctx.channel.name]]
        for command in data[ctx.channel.name][:]:
            # the get is for old version which has no "command" in it
            if command.get("command", str(ctx.command)) == str(ctx.command):
                data[ctx.channel.name].remove(command)
        await replace_one(database, collection, os.environ['nick'], data)


def fix_elixir(elixir: str) -> str:
    """fix elixir"""
    tier_lookup = {"q1": "mili", "q2": "mini", "q3": "standard", "q4": "major", "q5": "huge", "q6": "exceptional"}
    elixir_lookup = {"blue": "jinxed", "green": "finese", "red": "bloody_mess", "yellow": "lucky",
                     "finesse": "finese", "bloody": "bloody_mess", "mess": "bloody_mess"}
    tier, elixir = [x.strip() for x in elixir.lower().split("_")[:2]]
    tier = tier_lookup.get(tier if not tier.isdigit() else "q"+tier, tier)
    elixir = elixir_lookup.get(elixir, elixir)
    return f"{tier}_{elixir}_ELIXIR".upper()


async def idle(bot, links: list) -> None:
    """keep the bot online for a while"""
    for _ in range(randint(3, 7)):
        await sleep(uniform(25, 35))
        await bot.get_content(choice(links), return_tree=True)


def should_break(ctx) -> bool:
    """returns whether the user wants to stop the command"""
    server = ctx.channel.name
    cmd = str(ctx.command)
    return ctx.bot.should_break_dict.get(server, {}).get(cmd)


async def get_battles(bot, base_url: str, country_id: int = 0, normal_battles: bool = True) -> list[dict]:
    """Get battles data"""
    battles = []
    link = f'{base_url}battles.html?countryId={country_id}'
    tree = await bot.get_content(link, return_tree=True, incognito=True)
    last_page = int((get_ids_from_path(tree, "//ul[@id='pagination-digg']//li[last()-1]/") or ['1'])[0])
    for page in range(1, last_page+1):
        if page != 1:
            tree = await bot.get_content(link + f'&page={page}', return_tree=True, incognito=True)
        total_dmg = tree.xpath('//*[@class="battleTotalDamage"]/text()')
        progress_attackers = [float(x.replace("%", "")) for x in tree.xpath('//*[@id="attackerScoreInPercent"]/text()')]
        attackers_dmg = tree.xpath('//*[@id="attackerDamage"]/text()')
        defenders_dmg = tree.xpath('//*[@id="defenderDamage"]/text()')
        counters = [i.split(");\n")[0] for i in tree.xpath('//*[@id="battlesTable"]//div//div//script/text()') for i in
                    i.split("() + ")[1:]]
        counters = [f'{int(x[0]):02d}:{int(x[1]):02d}:{int(x[2]):02d}' for x in await chunker(counters, 3)]
        sides = tree.xpath('//*[@class="battleHeader"]//em/text()')
        battle_ids = tree.xpath('//*[@class="battleHeader"]//a/@href')
        battle_regions = tree.xpath('//*[@class="battleHeader"]//a/text()')
        scores = tree.xpath('//*[@class="battleFooterScore hoverText"]/text()')

        types = tree.xpath('//*[@class="battleHeader"]//i/@data-hover')
        for i, (dmg, progress_attacker, counter, sides, battle_id, battle_region, score, battle_type) in enumerate(zip(
                total_dmg, progress_attackers, counters, sides, battle_ids, battle_regions, scores, types)):
            if battle_type == "Practice Battle" or \
                    (normal_battles and battle_type not in ('Normal battle', 'Resistance war')) or (
                    not normal_battles and battle_type in ('Normal battle', 'Resistance war')):
                continue
            defender, attacker = sides.split(" vs ")
            battles.append(
                {"total_dmg": dmg, "time_reminding": counter,
                 "battle_id": int(battle_id.split("=")[-1]), "region": battle_region,
                 "defender": {"name": defender, "score": int(score.strip().split(":")[0]),
                              "bar": round(100 - progress_attacker, 2)},
                 "attacker": {"name": attacker, "score": int(score.strip().split(":")[1]),
                              "bar": progress_attacker}})
            if attackers_dmg:  # some servers do not show current dmg
                try:
                    battles[-1]["defender"]["dmg"] = int(defenders_dmg[i].replace(",", ""))
                    battles[-1]["attacker"]["dmg"] = int(attackers_dmg[i].replace(",", ""))
                except Exception:
                    pass
    return battles
