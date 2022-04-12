from asyncio import sleep
from datetime import datetime
from os import environ
from random import randint, uniform
import re
from time import time
from traceback import format_exception
from typing import Optional

from discord.ext.commands import Cog, command
from pytz import timezone

from Converters import Dmg, Id, IsMyNick, Product, Quality, Side
import utils


class War(Cog):
    """War Commands"""

    def __init__(self, bot):
        self.bot = bot

    async def get_battle_id(self, nick, server, battle_id, prioritize_my_country=True):
        URL = f"https://{server}.e-sim.org/"
        apiCitizen = await self.bot.get_content(f"{URL}apiCitizenByName.html?name={nick.lower()}")
        occupantId = 0
        for row in await self.bot.get_content(f'{URL}apiMap.html'):
            if row['regionId'] == apiCitizen['currentLocationRegionId']:
                occupantId = row['occupantId']
                break
        try:
            if apiCitizen["level"] < 15:
                raise  # PRACTICE_BATTLE
            if battle_id == "event":
                tree = await self.bot.get_content(
                    f"{URL}battles.html?countryId={apiCitizen['citizenshipId']}&filter=EVENT", return_tree=True)
                for link in tree.xpath("//tr[position()<12]//td[1]//div[2]//a/@href"):
                    link_id = link.split('=')[1]
                    apiBattles = await self.bot.get_content(f"{URL}apiBattles.html?battleId={link_id}")
                    if apiCitizen['citizenshipId'] in (apiBattles['attackerId'], apiBattles['defenderId']):
                        battle_id = link_id
                        break

            else:
                tree = await self.bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=NORMAL", return_tree=True)
                battle_id = tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/@href')
            if not battle_id:
                tree = await self.bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=RESISTANCE", return_tree=True)
                battle_id = tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/@href')
        except:
            tree = await self.bot.get_content(f"{URL}battles.html?filter=PRACTICE_BATTLE", return_tree=True)
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

    @classmethod
    async def random_sleep(cls, restores_left=1):
        if restores_left:
            now = datetime.now()
            minutes = int(now.strftime("%M"))
            sec = int(now.strftime("%S"))
            roundup = round(minutes + 5.1, -1)  # round up to the next ten minutes (00:10, 00:20 etc)
            random_number = randint(30, 570)  # getting random number
            sleep_time = random_number + (roundup - minutes) * 60 - sec
            print(f"Sleeping for {sleep_time} seconds.")
            await sleep(sleep_time)

    async def location(self, nick, server):
        """getting current location"""
        return (await self.bot.get_content(f"https://{server}.e-sim.org/apiCitizenByName.html?name={nick.lower()}")
                )['currentLocationRegionId']

    async def fighting(self, ctx, server, battle_id, side, wep):
        URL = f"https://{server}.e-sim.org/"
        tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}', return_tree=True)
        fight_url, data = await self.get_fight_data(URL, tree, wep, side)
        for x in range(1, 20):  # hits until you have 0 health.
            try:
                Health = tree.xpath("//*[@id='healthUpdate']/text()") or tree.xpath('//*[@id="actualHealth"]/text()')
                if Health:
                    Health = float(Health[0].split()[0])
                else:
                    tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}', return_tree=True)
                    Health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)

                if Health == 0:
                    break
                data["value"] = "Berserk" if Health >= 50 else ""

                tree = await self.bot.get_content(fight_url, data=data, return_tree=True)

                await sleep(randint(1, 2))
            except Exception as error:
                print(error)
                await ctx.send(
                    f"**{environ.get(server, environ['nick'])}** ```{''.join(format_exception(type(error), error, error.__traceback__))}```")
                await sleep(randint(2, 5))

    @command()
    async def auto_fight(self, ctx, nick: IsMyNick, restores: int = 100, battle_id: int = 0,
                         side: Side = "attacker", wep: int = 0, food: int = 5, gift: int = 0, ticket_quality: int = 1):
        """Dumping health at a random time every restore

        If `nick` contains more than 1 word - it must be within quotes.
        If you want to skip a parameter, you should write the default value.
        Example: `.add "My Nick" 100 0 attacker 0 5` - write 0 to `battle_id` in order to change `food`"""

        CHANCE_TO_SKIP_RESTORE = 15  # You can change this number however you like.
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        specific_battle = (battle_id != 0)
        await ctx.send(f"**{nick}** Ok sir! If you want to stop it, type `.hold {nick}`")

        if specific_battle and 1 <= ticket_quality <= 5:
            api = await self.bot.get_content(f"{URL}apiBattles.html?battleId={battle_id}")
            if api['type'] == "ATTACK":
                if side == "attacker":
                    try:
                        neighboursId = [region['neighbours'] for region in await self.bot.get_content(
                            f'{URL}apiRegions.html') if region["id"] == api['regionId']][0]
                        aBonus = [i for region in await self.bot.get_content(f'{URL}apiMap.html') for i in neighboursId
                                  if i == region['regionId'] and region['occupantId'] == api['attackerId']]
                    except:
                        aBonus = [api['attackerId'] * 6]
                    await ctx.invoke(self.bot.get_command("fly"), aBonus[0], ticket_quality, nick=nick)
                elif side == "defender":
                    await ctx.invoke(self.bot.get_command("fly"), api['regionId'], ticket_quality, nick=nick)
            elif api['type'] == "RESISTANCE":
                await ctx.invoke(self.bot.get_command("fly"), api['regionId'], ticket_quality, nick=nick)

        self.bot.hold_fight = False
        while restores > 0 and not self.bot.hold_fight:
            restores -= 1
            if randint(1, 100) <= CHANCE_TO_SKIP_RESTORE:
                await sleep(600)
            if not battle_id:
                battle_id = await self.get_battle_id(str(nick), server, battle_id)
            await ctx.send(f'**{nick}** <{URL}battle.html?id={battle_id}> side: {side}')
            if not battle_id:
                await ctx.send(
                    f"**{nick}** WARNING: I can't fight in any battle right now, but I will check again after the next restore")
                await self.random_sleep(restores)
                continue
            tree = await self.bot.get_content(URL, return_tree=True)
            check = tree.xpath('//*[@id="taskButtonWork"]//@href')  # checking if you can work
            if check and randint(1, 4) == 2:  # Don't work as soon as you can (suspicious)
                current_loc = await self.location(nick, server)
                await ctx.invoke(self.bot.get_command("work"), nick=nick)
                await ctx.invoke(self.bot.get_command("fly"), current_loc, ticket_quality, nick=nick)
            apiBattles = await self.bot.get_content(f"{URL}apiBattles.html?battleId={battle_id}")
            if 8 in (apiBattles['attackerScore'], apiBattles['defenderScore']):
                if specific_battle:
                    return await ctx.send(f"**{nick}** Battle has finished.")
                else:
                    await ctx.send(f"**{nick}** Searching for the next battle...")
                    battle_id = await self.get_battle_id(str(nick), server, battle_id)

            tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}', return_tree=True)
            fight_ability = tree.xpath("//*[@id='newFightView']//div[3]//div[3]//div//text()[1]")
            if any("You can't fight in this battle from your current location." in s for s in fight_ability):
                return await ctx.send(f"**{nick}** ERROR: You can't fight in this battle from your current location.")
            await self.fighting(ctx, server, battle_id, side, wep)
            if food:
                await self.bot.get_content(f"{URL}eat.html", data={'quality': food})
            if gift:
                await self.bot.get_content(f"{URL}gift.html", data={'quality': gift})
            if food or gift:
                await self.fighting(ctx, server, battle_id, side, wep)
            await self.random_sleep(restores)

    @command()
    async def BO(self, ctx, battle: Id, side: Side, *, nick: IsMyNick):
        """
        Set battle order.
        You can use battle link/id.
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'action': "SET_ORDERS",
                   'battleId': f"{battle}_{'true' if side == 'attacker' else 'false'}",
                   'submit': "Set orders"}
        url = await self.bot.get_content(URL + "militaryUnitsActions.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["buffs"])
    async def buff(self, ctx, buffs_names, *, nick: IsMyNick):
        """Buy and use buffs.
        The buff names should be formal (can be found via F12), but here are some shortcuts:
        VAC = EXTRA_VACATIONS, SPA = EXTRA_SPA, SEWER = SEWER_GUIDE, STR = STEROIDS
        More examples: BANDAGE_SIZE_C and CAMOUFLAGE_II"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"

        results = []
        for buff_name in buffs_names.split(","):
            buff_name = buff_name.strip().upper()
            if buff_name == "VAC":
                buff_name = "EXTRA_VACATIONS"
            elif buff_name == "SPA":
                buff_name = "EXTRA_SPA"
            elif buff_name == "SEWER":
                buff_name = "SEWER_GUIDE"
            elif "STR" in buff_name:
                buff_name = "STEROIDS"

            actions = ("BUY", "USE")
            for Index, action in enumerate(actions):
                if action == "USE":
                    payload = {'item': buff_name, 'storageType': "SPECIAL_ITEM", 'action': action, 'submit': 'Use'}
                else:
                    payload = {'itemType': buff_name, 'storageType': "SPECIAL_ITEM", 'action': action, "quantity": 1}
                url = await self.bot.get_content(URL + "storage.html", data=payload)
                results.append(f"{buff_name}: <{url}>")
                if "error" in url.lower():
                    results.append(f"ERROR: No such buff ({buff_name})")
                if "MESSAGE_OK" in url and buff_name in ("STEROIDS", "TANK", "SEWER", "BUNKER"):
                    data = await utils.find_one(server, "info", nick)
                    now = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%Y-%m-%d %H:%M:%S")
                    data["Buffed at"] = now
                    await utils.replace_one(server, "info", nick, data)
        await ctx.send(f"**{nick}**\n" + "\n".join(results))

    @command(aliases=["travel"])
    async def fly(self, ctx, region_id: Id, ticket_quality: Optional[int] = 5, *, nick: IsMyNick):
        """traveling to a region"""
        if 1 <= ticket_quality <= 5:
            URL = f"https://{ctx.channel.name}.e-sim.org/"
            payload = {'countryId': region_id // 6 + 1, 'regionId': region_id, 'ticketQuality': ticket_quality}
            url = await self.bot.get_content(f"{URL}travel.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @classmethod
    def convert_to_dict(cls, s):
        s_list = s.split("&")
        s_list[0] = f"ip={s_list[0]}"
        return dict([a.split("=") for a in s_list])

    @classmethod
    async def get_fight_data(cls, URL, tree, wep, side, value="Berserk"):
        fight_page_id = re.sub("[\"\']*", "", re.findall('url: (\".*fight.*.html\")', tree.text_content())[0])
        hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value
        data = {"weaponQuality": wep, "battleRoundId": hidden_id, "side": side, "value": value}
        data.update(cls.convert_to_dict("".join(tree.xpath("//script[3]/text()")).split("&ip=")[1].split("'")[0]))
        return f"{URL}{fight_page_id}", data

    @command()
    async def fight(self, ctx, nick: IsMyNick, link: Id, side: Side, weapon_quality: int = 5,
                    dmg_or_hits: Dmg = 100000000, ticket_quality: int = 5):
        """
        Dumping limits at a specific battle.

        * It will auto fly to bonus region.
        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.


        If `nick` contains more than 1 word - it must be within quotes.
        If you want to skip a parameter, you should write the default value.
        Example: `.fight "My Nick" 100 "" attacker 0 5` - skip `battle_id` in order to change `food`
        - You can't stop it after it started to fight, so be careful with the `dmg_or_hits` parameter
        """

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        link = f"{URL}battle.html?id={link}"
        dmg = dmg_or_hits
        api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        tree = await self.bot.get_content(link, return_tree=True)
        Health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)
        food_storage = int((tree.xpath('//*[@id="sfoodQ5"]/text()') or [0])[0])
        gift_storage = int((tree.xpath('//*[@id="sgiftQ5"]/text()') or [0])[0])
        food_limit = int(float(tree.xpath('//*[@id="foodLimit2"]')[0].text))
        gift_limit = int(float(tree.xpath('//*[@id="giftLimit2"]')[0].text))
        wep = weapon_quality if not weapon_quality else int(
            tree.xpath(f'//*[@id="Q{weapon_quality}WeaponStock"]/text()')[0])

        if 1 <= ticket_quality <= 5:
            if api['type'] == "ATTACK":
                if side == "attacker":
                    try:
                        neighboursId = [region['neighbours'] for region in await self.bot.get_content(
                            f'{URL}apiRegions.html') if region["id"] == api['regionId']][0]
                        aBonus = [i for region in await self.bot.get_content(f'{URL}apiMap.html') for i in neighboursId if
                                  i == region['regionId'] and region['occupantId'] == api['attackerId']]
                    except:
                        aBonus = [api['attackerId'] * 6]
                    await ctx.invoke(self.bot.get_command("fly"), aBonus[0], ticket_quality, nick=nick)
                elif side == "defender":
                    await ctx.invoke(self.bot.get_command("fly"), api['regionId'], ticket_quality, nick=nick)
            elif api['type'] == "RESISTANCE":
                await ctx.invoke(self.bot.get_command("fly"), api['regionId'], ticket_quality, nick=nick)
        output = f"**{nick}** Limits: {food_limit}/{gift_limit}. Storage: {food_storage}/{gift_storage}/{wep} Q{weapon_quality} weps.\n" \
                 f"If you want me to stop, type `.hold {nick}`"
        msg = await ctx.send(output)
        damage_done = 0
        update = 0
        fight_url, data = await self.get_fight_data(URL, tree, weapon_quality, side, value=("Berserk" if dmg >= 5 else ""))
        hits_or_dmg = "hits" if dmg < 1000 else "dmg"
        round_ends = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
        start = time()
        self.bot.hold_fight = False
        while not self.bot.hold_fight and damage_done < dmg and (time() - start < round_ends):
            if weapon_quality and not wep:
                await ctx.send(f"**{nick}** Done {damage_done:,} {hits_or_dmg}\nERROR: 0 Q{weapon_quality} weps in storage")
                break
            if Health < 50:
                if food_storage == 0 and gift_storage == 0:
                    output += f"\nERROR: 0 food and gift in storage"
                    break
                elif food_limit == 0 and gift_limit == 0:
                    break
                elif food_storage == 0 or gift_storage == 0:
                    output += f"\nWARNING: 0 {'food' if food_storage == 0 else 'gift'} in storage"

                use = None
                if food_limit > 20:  # use gifts limits first (save motivates limits)
                    if gift_storage > 0 and gift_limit > 0:
                        use = "gift"
                        gift_limit -= 1
                        gift_storage -= 1
                    elif food_storage > 0 and food_limit > 0:
                        use = "eat"
                        food_limit -= 1
                        food_storage -= 1
                else:
                    if food_storage > 0 and food_limit > 0:
                        use = "eat"
                        food_limit -= 1
                        food_storage -= 1
                    elif gift_storage > 0 and gift_limit > 0:
                        use = "gift"
                        gift_limit -= 1
                        gift_storage -= 1
                if use:
                    await self.bot.get_content(f"{URL}{use}.html", data={'quality': 5})
                    Health += 50

            try:
                tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
                if not tree.xpath("//*[@id='healthUpdate']/text()"):
                    if "Slow down a bit!" in tree.text_content():
                        await sleep(1)
                        continue
                    elif "No health left" in tree.text_content():
                        Health = 0
                        continue
                    elif "Round is closed" in tree.text_content():
                        break
                if weapon_quality:
                    wep -= 5 if dmg >= 5 else 1
                Health = float(tree.xpath("//*[@id='healthUpdate']")[0].text.split()[0])
                if dmg < 5:
                    damage_done += 1
                elif dmg < 1000:
                    damage_done += 5
                else:
                    damage_done += int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
                update += 1
                await sleep(uniform(0.3, 0.55))
            except Exception as error:
                await ctx.send(f"**{nick}** ERROR: {error}")
                await sleep(2)
            if update % 4 == 0:
                # dmg update every 4 berserks.
                output += f"\n{hits_or_dmg.title()} done so far: {damage_done:,}"
                await msg.edit(content=output)
        if damage_done:
            await msg.edit(content=output)
            await ctx.send(f"**{nick}** Done {damage_done:,} {hits_or_dmg}, reminding limits: {food_limit}/{gift_limit}")

    @command(hidden=True)
    async def hold(self, ctx, *, nick: IsMyNick):
        self.bot.hold_fight = True
        await ctx.send(f"**{nick}** done.")

    @command()
    async def hunt(self, ctx, nick: IsMyNick, max_dmg_for_bh: Dmg = 1, weapon_quality: int = 5, start_time: int = 30,
                   ticket_quality: int = 5):
        """Auto hunt BHs (attack and RWs)
        If `nick` contains more than 1 word - it must be within quotes."""
        dead_servers = ["primera", "secura", "suna"]
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        await ctx.send(f"**{nick}** Starting to hunt at {server}.")
        apiCitizen = await self.bot.get_content(f"{URL}apiCitizenByName.html?name={str(nick).lower()}")
        apiRegions = await self.bot.get_content(URL + "apiRegions.html")
        for _ in range(100):
            battles_time = {}
            apiMap = await self.bot.get_content(f'{URL}apiMap.html')
            for row in apiMap:
                if "battleId" in row:
                    apiBattles = await self.bot.get_content(f'{URL}apiBattles.html?battleId={row["battleId"]}')
                    round_ends = apiBattles["hoursRemaining"] * 3600 + apiBattles["minutesRemaining"] * 60 + apiBattles[
                        "secondsRemaining"]
                    battles_time[row["battleId"]] = round_ends

            for battle_id, round_ends in sorted(battles_time.items(), key=lambda x: x[1]):
                apiBattles = await self.bot.get_content(f'{URL}apiBattles.html?battleId={battle_id}')
                if apiBattles['frozen']:
                    continue
                time_to_sleep = apiBattles["hoursRemaining"] * 3600 + apiBattles["minutesRemaining"] * 60 + apiBattles[
                    "secondsRemaining"]
                round_time = 7000 if server in ("primera", "secura", "suna") else 3400
                if time_to_sleep > round_time:
                    break
                await ctx.send(f"**{nick}** Seconds till next battle: {time_to_sleep}")
                try:
                    await sleep(time_to_sleep - start_time)
                except:
                    pass
                apiFights = await self.bot.get_content(
                    f'{URL}apiFights.html?battleId={battle_id}&roundId={apiBattles["currentRound"]}')
                defender, attacker = {}, {}
                for hit in apiFights:
                    side = defender if hit['defenderSide'] else attacker
                    if hit['citizenId'] in side:
                        side[hit['citizenId']] += hit['damage']
                    else:
                        side[hit['citizenId']] = hit['damage']

                neighboursId = [region['neighbours'] for region in apiRegions if region["id"] == apiBattles['regionId']]
                if not neighboursId:
                    continue  # Not an attack / RW.
                aBonus = [neighbour for region in apiMap for neighbour in neighboursId[0] if
                          neighbour == region['regionId'] and region['occupantId'] == apiBattles['attackerId']]

                async def fight(side, damage_done):
                    tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}', return_tree=True)
                    Health = float(str(tree.xpath("//*[@id='actualHealth']")[0].text))
                    hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value
                    food = int(tree.xpath('//*[@id="foodLimit2"]')[0].text)
                    gift = int(tree.xpath('//*[@id="giftLimit2"]')[0].text)
                    if Health < 50:
                        use = "eat" if food else "gift"
                        await self.bot.get_content(f"{URL}{use}.html", data={'quality': 5})
                        Health += 50
                    battleScore = await self.bot.get_content(
                        f'{URL}battleScore.html?id={hidden_id}&at={apiCitizen["id"]}&ci={apiCitizen["citizenshipId"]}&premium=1',
                        return_type="json")
                    Damage = 0
                    if server in dead_servers:
                        value = "Berserk" if battleScore["spectatorsOnline"] != 1 and Health >= 50 else ""
                    else:
                        value = "Berserk"
                    fight_url, data = await self.get_fight_data(URL, tree, weapon_quality, side, value)
                    for _ in range(5):
                        try:
                            tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
                            Damage = int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
                            Health = tree.xpath("//*[@id='healthUpdate']/text()") or tree.xpath(
                                '//*[@id="actualHealth"]/text()')
                            if Health:
                                Health = float(Health[0].split()[0])
                            else:
                                Health = 0
                            await sleep(0.3)
                            break
                        except:
                            await sleep(2)
                    try:
                        damage_done += Damage
                    except:
                        await ctx.send(f"**{nick}** ERROR: Couldn't hit")
                    if food == 0 and gift == 0 and Health == 0:
                        await ctx.send(f"**{nick}** Done limits")
                        damage_done = 0
                    return damage_done

                async def check(side, damage_done, should_continue):
                    tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}', return_tree=True)
                    hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value

                    try:
                        top1Name = tree.xpath(f"//*[@id='top{side}1']//div//a[1]/text()")[0].strip()
                        top1dmg = int(str(tree.xpath(f'//*[@id="top{side}1"]/div/div[2]')[0].text).replace(",", ""))
                    except:
                        top1Name, top1dmg = "None", 0
                    battleScore = await self.bot.get_content(
                        f'{URL}battleScore.html?id={hidden_id}&at={apiCitizen["id"]}&ci={apiCitizen["citizenshipId"]}&premium=1',
                        return_type="json")
                    # condition - You are top 1 / did more dmg than your limit / refresh problem
                    condition = (top1Name == nick or
                                 damage_done > max_dmg_for_bh or
                                 damage_done > top1dmg)
                    if battleScore["remainingTimeInSeconds"] > start_time:
                        return False
                    elif battleScore['spectatorsOnline'] == 1:
                        return top1dmg <= max_dmg_for_bh and not condition
                    else:
                        if top1dmg < max_dmg_for_bh and condition:
                            if not should_continue:
                                food = int(tree.xpath('//*[@id="foodLimit2"]')[0].text)
                                use = "eat" if food else "gift"
                                await self.bot.get_content(f"{URL}{use}.html", data={'quality': 5})
                                try:
                                    await sleep(battleScore["remainingTimeInSeconds"] - 13)
                                except:
                                    pass
                                battleScore = await self.bot.get_content(
                                    f'{URL}battleScore.html?id={hidden_id}&at={apiCitizen["id"]}&ci={apiCitizen["citizenshipId"]}&premium=1',
                                    return_type="json")
                                if battleScore[f"{side.lower()}sOnline"]:
                                    await fight(side, damage_done)
                            return False
                        return True

                async def hunting(side, side_dmg, should_continue):
                    damage_done = 0
                    c = await check(side.title(), damage_done, should_continue)
                    while c:
                        damage_done = await fight(side, damage_done)
                        if not damage_done:  # Done limits or error
                            break
                        if damage_done > side_dmg:
                            c = await check(side.title(), damage_done, should_continue)

                try:
                    aDMG = sorted(attacker.items(), key=lambda x: x[1], reverse=True)[0][1]
                except:
                    aDMG = 0
                try:
                    dDMG = sorted(defender.items(), key=lambda x: x[1], reverse=True)[0][1]
                except:
                    dDMG = 0
                if aDMG < max_dmg_for_bh or dDMG < max_dmg_for_bh:
                    await ctx.send(
                        f"**{nick}** Fighting at: <{URL}battle.html?id={battle_id}&round={apiBattles['currentRound']}>")
                    if apiBattles['type'] == "ATTACK":
                        if aDMG < max_dmg_for_bh:
                            try:
                                await ctx.invoke(self.bot.get_command("fly"), aBonus[0], ticket_quality, nick=nick)
                            except:
                                await ctx.send(f"**{nick}** ERROR: I couldn't find the bonus region")
                                continue
                            await hunting("attacker", aDMG, dDMG < max_dmg_for_bh)

                        if dDMG < max_dmg_for_bh:
                            await ctx.invoke(self.bot.get_command("fly"), apiBattles['regionId'], ticket_quality,
                                             nick=nick)
                            await hunting("defender", dDMG, aDMG < max_dmg_for_bh)

                    elif apiBattles['type'] == "RESISTANCE":
                        await ctx.invoke(self.bot.get_command("fly"), apiBattles['regionId'], ticket_quality, nick=nick)
                        if aDMG < max_dmg_for_bh:
                            await hunting("attacker", aDMG, dDMG < max_dmg_for_bh)

                        if dDMG < max_dmg_for_bh:
                            await hunting("defender", dDMG, aDMG < max_dmg_for_bh)
                    else:
                        continue

    @command()
    async def hunt_battle(self, ctx, nick: IsMyNick, link, side: Side, dmg_or_hits_per_bh: Dmg = 1, weapon_quality: int = 0, food: int = 5, gift: int = 5):
        """Hunting BH at a specific battle.
        (Good for practice battle / leagues / civil war)

        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        If `nick` contains more than 1 word - it must be within quotes."""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        dmg = dmg_or_hits_per_bh
        hits_or_dmg = "hits" if dmg < 1000 else "dmg"
        self.bot.hold_fight = False
        while not self.bot.hold_fight:  # For each round
            api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
            if 8 in (api['defenderScore'], api['attackerScore']):
                break
            seconds_till_round_end = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
            seconds_till_hit = randint(10, seconds_till_round_end - 10)
            await ctx.send(f"**{nick}** {seconds_till_hit} seconds from now, I will hit {dmg} {hits_or_dmg} at <{link}> for the {side} side.\n"
                           f"If you want to cancel it, type `.hold {nick}`")
            await sleep(seconds_till_hit)
            tree = await self.bot.get_content(link, return_tree=True)
            side_dmg = int(str(tree.xpath(f'//*[@id="{side}Score"]/text()')[0]).replace(",", "").strip())
            if side_dmg != 0 and dmg_or_hits_per_bh == 1:
                await ctx.send(f"**{nick}** someone else already fought in this round.")
                await sleep(seconds_till_round_end - seconds_till_hit + 15)
                continue
            food_limit = int(tree.xpath('//*[@id="foodLimit2"]')[0].text)
            food_storage = int((tree.xpath('//*[@id="sfoodQ5"]/text()') or [0])[0])
            gift_limit = int(tree.xpath('//*[@id="giftLimit2"]')[0].text)
            gift_storage = int((tree.xpath('//*[@id="sgiftQ5"]/text()') or [0])[0])
            damage_done = 0
            fight_url, data = await self.get_fight_data(URL, tree, weapon_quality, side, value=("Berserk" if dmg >= 5 else ""))

            while damage_done < dmg and not self.bot.hold_fight:
                Health = tree.xpath('//*[@id="actualHealth"]/text()') or tree.xpath("//*[@id='healthUpdate']/text()")
                if Health:
                    Health = float(Health[0].split()[0])
                else:
                    tree = await self.bot.get_content(link, return_tree=True)
                    Health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)
                if (dmg < 5 and Health < 10) or (dmg >= 5 and Health < 50):
                    if (not food or food_storage == 0) and (not gift or gift_storage == 0):
                        return await ctx.send(f"**{nick}** ERROR: food/gift storage error")
                    elif (not food or food_limit == 0) and (not gift or gift_limit == 0):
                        return await ctx.send(f"**{nick}** ERROR: food/gift limits error")
                    elif food and food_storage > 0 and food_limit > 0:
                        food_storage -= 1
                        food_limit -= 1
                        await self.bot.get_content(f"{URL}eat.html", data={'quality': 5})
                    elif gift and gift_storage > 0 and gift_limit > 0:
                        gift_storage -= 1
                        gift_limit -= 1
                        await self.bot.get_content(f"{URL}gift.html", data={'quality': 5})
                    else:
                        return await ctx.send(f"**{nick}** ERROR: I couldn't restore health.")
                    Health += 50
                for _ in range(5):
                    tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
                    if not tree.xpath('//*[@id="DamageDone"]'):
                        if "Slow down a bit!" in tree.text_content():
                            await sleep(1)
                            continue
                        elif "No health left" in tree.text_content():
                            break
                        elif "Round is closed" in tree.text_content():
                            return
                        else:
                            continue
                    damage_done += int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
                    break
                await sleep(randint(0, 2))
            if not self.bot.hold_fight:
                await ctx.send(f"**{nick}** done {damage_done} dmg at <{link}>")
                await sleep(seconds_till_round_end - seconds_till_hit + 15)
        if not self.bot.hold_fight:
            await ctx.send(f"**{nick}** <{link}> is over")

    @command(aliases=["motivates"])
    async def motivate(self, ctx, *, nick):
        """
        Send motivates.
        * checking first 200 new citizens only.
        * If you do not have Q3 food / Q3 gift / Q1 weps when it starts - it will try to take some from your MU storage.

        If you want to send motivates with a specific type only, write in this format:
        .motivate My Nick, wep
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if "," in nick:
            nick, Type = nick.split(",")
            Type = Type.strip()
        else:
            Type = "all"
        await IsMyNick().convert(ctx, nick.strip())

        tree = await self.bot.get_content(URL + 'storage.html?storageType=PRODUCT', return_tree=True)

        def get_storage(tree, Type):
            food = int(tree.xpath('//*[@id="foodQ3"]/text()')[0])
            gift = int(tree.xpath('//*[@id="giftQ3"]/text()')[0])
            weps = 0
            for num in range(2, 52):
                try:
                    item = str(tree.xpath(f'//*[@id="resourceInput"]/option[{num}]')[0].text).strip()
                    item = item.replace("(available", "").replace(")", "").split(":")
                    while "  " in item[0]:
                        item[0] = item[0].replace("  ", "")
                    if item[0] == "Q1 Weapon":
                        weps = int(item[1])
                except:
                    break

            storage = []
            if Type in ("all", "wep") and weps >= 15:
                storage.append(1)

            if Type in ("all", "food") and food >= 10:
                storage.append(2)

            if Type in ("all", "gift") and gift >= 5:
                storage.append(3)
            return storage

        storage = get_storage(tree, Type)
        if not storage:
            await ctx.invoke(self.bot.get_command("supply"), 15, "Q1", "wep", nick=nick)
            await ctx.invoke(self.bot.get_command("supply"), 10, "Q3", "food", nick=nick)
            await ctx.invoke(self.bot.get_command("supply"), 5, "Q3", "gift", nick=nick)
            storage = get_storage(tree, Type)

        newCitizens_tree = await self.bot.get_content(URL + 'newCitizens.html?countryId=0', return_tree=True)
        citizenId = int(newCitizens_tree.xpath("//tr[2]//td[1]/a/@href")[0].split("=")[1])
        checking = list()
        sent_count = 0
        for i in range(200):  # newest 200 players
            try:
                if sent_count == 5:
                    return await ctx.send(
                        f"**{nick}**\n" + "\n".join(checking) + "\n- Successfully motivated 5 players.")
                tree = await self.bot.get_content(f'{URL}profile.html?id={citizenId}', return_tree=True)
                today = int(tree.xpath('//*[@class="sidebar-clock"]/b/text()')[-1].split()[-1])
                birthday = int(
                    tree.xpath(f'//*[@class="profile-row" and span = "Birthday"]/span/text()')[0].split()[-1])
                if today - birthday > 3:
                    return await ctx.send(f"**{nick}** Checked all new players")
                checking.append(f"Checking <{URL}profile.html?id={citizenId}>")
                if tree.xpath('//*[@id="motivateCitizenButton"]'):
                    for num in storage:
                        payload = {'type': num, "submit": "Motivate", "id": citizenId}
                        url = await self.bot.get_content(f"{URL}motivateCitizen.html?id={citizenId}", data=payload)
                        if "&actionStatus=SUCCESFULLY_MOTIVATED" in url:
                            checking.append(f"<{url}>")
                            sent_count += 1
                            break
                citizenId -= 1
            except Exception as error:
                await ctx.send(f"**{nick}** ERROR: {error}")
            if (i + 1) % 10 == 0 and checking:
                await ctx.send(f"**{nick}**\n" + "\n".join(checking))
                checking.clear()
        await ctx.send(f"**{nick}** I checked the first 200 players - and now I gave up!")

    @command(aliases=["dow", "mpp"])
    async def attack(self, ctx, country_or_region_id: Id, delay_or_battle_link="0", *, nick):
        """
        Propose MPP / Declaration of war / Attack region.
        Possible after certain delay / after certain battle.
        `delay_or_battle_link` - optional
        """
        if not delay_or_battle_link.isdigit():
            nick = delay_or_battle_link + " " + nick
            delay_or_battle_link = ""
        await IsMyNick().convert(ctx, nick)
        action = ctx.invoked_with.lower()
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if ".e-sim.org/battle.html?id=" in delay_or_battle_link:
            api = await self.bot.get_content(
                delay_or_battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
            defender_score, attacker_score = api['defenderScore'], api['attackerScore']
            while 8 not in (defender_score, attacker_score):
                api = await self.bot.get_content(delay_or_battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
                defender_score, attacker_score = api['defenderScore'], api['attackerScore']
                await sleep(api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"])

        elif delay_or_battle_link:
            await sleep(int(delay_or_battle_link))

        if action == "attack":
            payload = {'action': "ATTACK_REGION", 'regionId': country_or_region_id, 'attackButton': "Attack"}
        elif action == "mpp":
            payload = {'action': "PROPOSE_ALLIANCE", 'countryId': country_or_region_id, 'submit': "Propose alliance"}
        elif action == "dow":
            payload = {'action': "DECLARE_WAR", 'countryId': country_or_region_id, 'submit': "Declare war"}
        else:
            return await ctx.send(f"**{nick}** ERROR: parameter 'action' must be one of those: mpp/dow/attack (not {action})")

        url = await self.bot.get_content(URL + "countryLaws.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def medkit(self, ctx, *, nick: IsMyNick):
        url = await self.bot.get_content(
            f"https://{ctx.channel.name}.e-sim.org/medkit.html", data={})
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["upgrade"])
    async def reshuffle(self, ctx, eq_id_or_link: Id, parameter, *, nick: IsMyNick):
        """
        Reshuffle/upgrade a specific parameter.
        Parameter example: Increase chance to avoid damage by 7.08%
        If it's not working, you can try writing "first" or "last" as a parameter.

        it's recommended to copy and paste the parameter, but you can also write first/last
        """
        action = ctx.invoked_with
        if action.lower() not in ("reshuffle", "upgrade"):
            return await ctx.send(f"**{nick}** ERROR: 'action' parameter can be reshuffle/upgrade only (not {action})")
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        link = f"{URL}showEquipment.html?id={eq_id_or_link}"
        tree = await self.bot.get_content(link, return_tree=True)
        eq = tree.xpath('//*[@id="esim-layout"]//div/div[4]/div/h4/text()')
        parameter_id = tree.xpath('//*[@id="esim-layout"]//div/div[4]/div/h3/text()')
        if parameter in eq[0].replace("by  ", "by ") or parameter == "first":
            parameter_id = parameter_id[0].split("#")[1]
        elif parameter in eq[1].replace("by  ", "by ") or parameter == "last":
            parameter_id = parameter_id[1].split("#")[1]
        else:
            return await ctx.send(
                f"**{nick}** ERROR: I did not find the parameter {parameter} at <{link}>. Try copy & paste.")
        payload = {'parameterId': parameter_id, 'action': f"{action.upper()}_PARAMETER", "submit": action.capitalize()}
        url = await self.bot.get_content(URL + "equipmentAction.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def rw(self, ctx, region_id_or_link: Id, ticket_quality: Optional[int] = 5, *, nick: IsMyNick):
        """
        Open RW.
        Note: region can be link or id.
        * It will auto fly to that region."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        region_link = f"{URL}region.html?id={region_id_or_link}"
        await ctx.invoke(self.bot.get_command("fly"), region_id_or_link, ticket_quality, nick=nick)
        tree = await self.bot.get_content(region_link, data={"submit": "Start resistance"}, return_tree=True)
        result = tree.xpath("//*[@id='esim-layout']//div[2]/text()")[0]
        await ctx.send(f"**{nick}** {result}")

    @command()
    async def supply(self, ctx, amount: int, quality: Optional[Quality], product: Product, *, nick: IsMyNick):
        """Taking a specific product from MU storage."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL, return_tree=True)
        my_id = str(tree.xpath('//*[@id="userName"]/@href')[0]).split("=")[1]
        payload = {'product': f"{quality}-{product}" if quality else product, 'quantity': amount,
                   "reason": " ", "citizen1": my_id, "submit": "Donate"}
        url = await self.bot.get_content(URL + "militaryUnitStorage.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["gift"])
    async def food(self, ctx, quality: Optional[int] = 5, *, nick: IsMyNick):
        """Using food or gift"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        url = await self.bot.get_content(f"{URL}{ctx.invoked_with.lower().replace('food', 'eat')}.html", data={'quality': quality})
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def watch(self, ctx, nick: IsMyNick, link: Id, side: Side, start_time: int = 60,
                    keep_wall: Dmg = 3000000, let_overkill: Dmg = 10000000, weapon_quality: int = 5, ticket_quality: int = 5):
        """
        Fight at the last minutes of every round in a given battle.

        Examples:
        when link="https://alpha.e-sim.org/battle.html?id=1" and side="defender"
        In this example, it will start fighting at t1, it will keep a 3kk wall (checking every 10 sec),
        and if enemies did more than 10kk it will pass this round.
        (rest args have a default value)

        link="https://alpha.e-sim.org/battle.html?id=1", side="defender", start_time=120, keep_wall="5kk", let_overkill="15kk")
        In this example, it will start fighting at t2 (120 sec), it will keep 5kk wall (checking every 10 sec),
        and if enemies did more than 15kk it will pass this round.
        * It will auto fly to bonus region (with Q5 ticket)
        * If `nick` contains more than 1 word - it must be within quotes.
        """
        server = ctx.channel.name
        link = f"https://{server}.e-sim.org/battle.html?id={link}"
        URL = f"https://{server}.e-sim.org/"

        r = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        if r['type'] == "ATTACK":
            if side == "attacker":
                try:
                    neighboursId = [z['neighbours'] for z in await self.bot.get_content(
                        f"{URL}apiRegions.html") if z["id"] == r['regionId']][0]
                    aBonus = [i for z in await self.bot.get_content(f'{URL}apiMap.html') for i in neighboursId if
                              i == z['regionId'] and z['occupantId'] == r['attackerId']]
                except:
                    aBonus = r['attackerId']
                try:
                    await ctx.invoke(self.bot.get_command("fly"), aBonus, ticket_quality, nick=nick)
                except:
                    return await ctx.send("**{nick}** ERROR: I couldn't find the bonus region")
            elif side == "defender":
                await ctx.invoke(self.bot.get_command("fly"), r['regionId'], ticket_quality, nick=nick)
        elif r['type'] == "RESISTANCE":
            await ctx.invoke(self.bot.get_command("fly"), r['regionId'], ticket_quality, nick=nick)

        while 8 not in (r['defenderScore'], r['attackerScore']):
            r = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
            time_till_round_end = r["hoursRemaining"] * 3600 + r["minutesRemaining"] * 60 + r[
                "secondsRemaining"] - start_time
            await ctx.send(f"**{nick}** Sleeping for {time_till_round_end} seconds :zzz:")
            await sleep(time_till_round_end)
            start = time()
            tree = await self.bot.get_content(link, return_tree=True)
            food_limit = tree.xpath('//*[@id="foodLimit2"]')[0].text
            gift_limit = tree.xpath('//*[@id="giftLimit2"]')[0].text
            food_storage = (tree.xpath('//*[@id="sfoodQ5"]/text()') or [0])[0]
            gift_storage = (tree.xpath('//*[@id="sgiftQ5"]/text()') or [0])[0]
            await ctx.send(f"**{nick}** <{link}&round={r['currentRound']}>\nStarting to hit {food_limit} food "
                           f"and {gift_limit} gift ({food_storage}/{gift_storage}) in storage) limits.")

            if time() - start > start_time:
                break
            if side == "attacker":
                mySide = int(str(tree.xpath('//*[@id="attackerScore"]/text()')[0]).replace(",", "").strip())
                enemySide = int(str(tree.xpath('//*[@id="defenderScore"]/text()')[0]).replace(",", "").strip())
            else:
                mySide = int(str(tree.xpath('//*[@id="defenderScore"]/text()')[0]).replace(",", "").strip())
                enemySide = int(str(tree.xpath('//*[@id="attackerScore"]/text()')[0]).replace(",", "").strip())
            if enemySide - mySide > int(let_overkill):
                await sleep(10)
                continue
            if mySide - enemySide > int(keep_wall):
                await sleep(10)
                continue
            Health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)
            if Health < 50:
                if int(food_limit) == 0 and int(gift_limit) == 0:
                    return await ctx.send(f"**{nick}** Done limits")
                elif int(food_storage) > 0 and int(food_limit) > 0:
                    await self.bot.get_content(f"{URL}eat.html", data={'quality': 5})
                elif int(food_storage) > 0 and int(food_limit) > 0:
                    await self.bot.get_content(f"{URL}gift.html", data={'quality': 5})
                else:
                    return await ctx.send(f"**{nick}** ERROR: I couldn't refresh health")
                Health += 50
            fight_url, data = await self.get_fight_data(URL, tree, weapon_quality, side)
            await self.bot.get_content(fight_url, data=data)
            await sleep(0.5)

    @command(aliases=["unwear"])
    async def wear(self, ctx, ids, *, nick: IsMyNick):
        """
        Wear/take off a specific EQ IDs.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        ids = [int(x.replace("#", "").strip()) for x in ids.split(",") if x.strip()]
        for Index, ID in enumerate(ids):
            payload = {'action': "PUT_OFF" if ctx.invoked_with.lower() == "unwear" else "EQUIP",
                       'itemId': ID.replace("#", "").replace(f"{URL}showEquipment.html?id=", "")}
            url = await self.bot.get_content(f"{URL}equipmentAction.html", data=payload)
            await sleep(randint(1, 2))
            if url == "http://www.google.com/":
                # e-sim error
                await sleep(randint(2, 5))
            results.append(f"ID {ID} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))


def setup(bot):
    bot.add_cog(War(bot))
