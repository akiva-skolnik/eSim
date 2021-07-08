import re
from asyncio import sleep
from datetime import datetime
from random import randint
from time import time
from typing import Optional

from discord import Embed
from discord.ext.commands import Cog, command

from Converters import IsMyNick


class War(Cog):
    """War Commands"""

    def __init__(self, bot):
        self.bot = bot

    async def get_battle_id(self, nick, server, battle_id, prioritize_my_country=False):
        URL = f"https://{server}.e-sim.org/"
        apiCitizen = await self.bot.get_content(f"{URL}apiCitizenByName.html?name={nick.lower()}")
        for row in await self.bot.get_content(f'{URL}apiMap.html'):
            if row['regionId'] == apiCitizen['currentLocationRegionId']:
                occupantId = row['occupantId']
                break
        await self.bot.login(server)
        try:
            if apiCitizen["level"] < 15:
                raise  # PRACTICE_BATTLE
            if battle_id == "event":
                tree = await self.bot.get_content(
                    f"{URL}battles.html?countryId={apiCitizen['citizenshipId']}&filter=EVENT")
                for link in tree.xpath("//tr[position()<12]//td[1]//div[2]//a/@href"):
                    link_id = link.split('=')[1]
                    apiBattles = await self.bot.get_content(f"{URL}apiBattles.html?battleId={link_id}")
                    if apiCitizen['citizenshipId'] in (apiBattles['attackerId'], apiBattles['defenderId']):
                        battle_id = link_id
                        break

            else:
                tree = await self.bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=NORMAL")
                battle_id = tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/@href')
            if not battle_id:
                tree = await self.bot.get_content(f"{URL}battles.html?countryId={occupantId}&filter=RESISTANCE")
                battle_id = tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/@href')
        except:
            tree = await self.bot.get_content(f"{URL}battles.html?filter=PRACTICE_BATTLE")
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

    async def random_sleep(self, restores_left=1):
        # Functions: datetime (datetime), randint (random), time
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
        URL = f"https://{server}.e-sim.org/"
        await sleep(randint(1, 2))
        apiCitizen = await self.bot.get_content(f"{URL}apiCitizenByName.html?name={nick.lower()}")
        return apiCitizen['currentLocationRegionId']

    async def fighting(self, server, battle_id, side, wep):
        URL = f"https://{server}.e-sim.org/"

        for x in range(1, 20):  # hitting until you have 0 health.
            try:
                tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}')
                Health = int(float(tree.xpath('//*[@id="actualHealth"]')[0].text))
                if not Health:
                    break
                value = "Berserk" if Health >= 50 else ""
                _, status_code = await self.bot.send_fight_request(URL, tree, wep, side, value)
                if status_code != 200:
                    await self.bot.login(server, clear_cookies=True)
                print(f"Hit {x}")
                await sleep(randint(1, 2))
            except Exception as e:
                print(e)
                await sleep(randint(2, 5))

    @command()
    async def auto_fight(self, ctx, nick: IsMyNick, restores: int = 100, battle_id: int = 0,
                         side="attacker", wep: int = 0, food: int = 5, gift: int = 0):
        """Dumping health at a random time every restore
        
        If `nick` containing more than 1 word - it must be within quotes.
        If you want to skip a parameter, you should write the default value.
        Example: `.add "My Nick" 100 0 attacker 0 5` - write 0 to `battle_id` in order to change `food`"""
        if side.lower() not in ("attacker", "defender"):
            return await ctx.send(f"'side' parameter must be attacker/defender only (not {side})")
        await ctx.send("Ok sir!")
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        restores_left = int(restores)
        for _ in range(int(restores)):
            restores_left -= 1
            if not str(battle_id).replace("0", "").isdigit():
                battle_id = await self.get_battle_id(nick, server, battle_id)
            await ctx.send(f'{URL}battle.html?id={battle_id} side: {side}')
            if not battle_id:
                await ctx.send("Can't fight in any battle. i will check again after the next restore")
                await self.random_sleep(restores_left)
                continue
            tree = await self.bot.get_content(URL, login_first=True)
            check = tree.xpath('//*[@id="taskButtonWork"]//@href')  # checking if you can work
            A = randint(1, 4)
            if check and A == 2:  # Don't work as soon as you can (suspicious)
                current_loc = await self.location(nick, server)
                await ctx.invoke(self.bot.get_command("work"), nick=nick)
                await ctx.invoke(self.bot.get_command("fly"), current_loc, 1, nick=nick)
            apiBattles = await self.bot.get_content(f"{URL}apiBattles.html?battleId={battle_id}")
            if 8 in (apiBattles['attackerScore'], apiBattles['defenderScore']):
                await ctx.send("Battle has finished, i will search for another one")
                battle_id = await self.get_battle_id(nick, server, battle_id)

            tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}')
            fight_ability = tree.xpath("//*[@id='newFightView']//div[3]//div[3]//div//text()[1]")
            if any("You can't fight in this battle from your current location." in s for s in fight_ability):
                await ctx.send("You can't fight in this battle from your current location.")
                return
            await self.fighting(server, battle_id, side, wep)
            if food:
                await self.bot.get_content(f"{URL}eat.html", data={'quality': food})
            if gift:
                await self.bot.get_content(f"{URL}gift.html", data={'quality': gift})
            if food or gift:
                await self.fighting(server, battle_id, side, wep)
            await self.random_sleep(restores_left)

    async def BO(self, ctx, battle_link, side, *, nick: IsMyNick):
        """
        Set battle order.
        You can use battle link/id.
        """
        if side.lower() not in ("attacker", "defender"):
            await ctx.send(f"'side' parameter can be attacker/defender only (not{side})")
            return
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        battle_id = battle_link.split('=')[1].split('&')[0] if 'http' in battle_link else battle_link
        payload = {'action': "SET_ORDERS",
                   'battleId': f"{battle_id}_{'true' if side.lower() == 'attacker' else 'false'}",
                   'submit': "Set orders"}
        url = await self.bot.get_content(URL + "militaryUnitsActions.html", data=payload, login_first=True)
        await ctx.send(url)

    @command(aliases=["buffs"])
    async def buff(self, ctx, buffs_names, *, nick: IsMyNick):
        """Buy and use buffs."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

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
                payload = {'itemType': buff_name, 'storageType': "SPECIAL_ITEM", 'action': action, "quantity": 1}
                if action == "USE":
                    payload = {'item': buff_name, 'storageType': "SPECIAL_ITEM", 'action': action, 'submit': 'Use'}
                url = await self.bot.get_content(URL + "storage.html", data=payload, login_first=not Index)
                results.append(f"{buff_name}: {url}\n")
                if "error" in str(url):
                    results.append(f"No such buff ({buff_name})\n")
                    continue
        await ctx.send("".join(results))

    @command(aliases=["travel"])
    async def fly(self, ctx, region_link_or_id, ticket_quality: Optional[int] = 5, *, nick: IsMyNick):
        """traveling to a region"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        region_id = region_link_or_id
        if "http" in str(region_id):
            region_id = region_id.split("=")[1]
        payload = {'countryId': int(int(region_id) / 6) + (int(region_id) % 6 > 0), 'regionId': region_id,
                   'ticket_quality': ticket_quality}
        url = await self.bot.get_content(f"{URL}travel.html", data=payload, login_first=True)
        await ctx.send(url)

    @staticmethod
    def fight395791_(r: str):
        fg_re = 'url: (\".*fight.*.html\")'
        return re.sub("[\"\']*", "", re.findall(fg_re, r)[0])

    @staticmethod
    def convert_to_dict(s):
        s_list = s.split("&")
        s_list[0] = f"ip={s_list[0]}"
        return dict([a.split("=") for a in s_list])

    async def send_fight_request(self, URL, tree, wep, side, value="Berserk"):
        hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value
        fight395791 = self.fight395791_(tree.text_content())
        data = {"weaponQuality": wep, "battleRoundId": hidden_id, "side": side, "value": value}
        data.update(self.convert_to_dict("".join(tree.xpath("//script[3]/text()")).split("&ip=")[1].split("'")[0]))
        return await self.bot.get_content(f"{URL}{fight395791}", data=data)

    @command()
    async def fight(self, ctx, nick: IsMyNick, link, side, weapon_quality: int = 5,
                    dmg_or_hits="100kk", ticket_quality: int = 5):
        """
        Dumping limits at specific battle.
        
        * It will auto fly to bonus region.
        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        
        
        If `nick` containing more than 1 word - it must be within quotes.
        If you want to skip a parameter, you should write the default value.
        Example: `.fight "My Nick" 100 "" attacker 0 5` - skip `battle_id` in order to change `food`
        - You can't stop it after it started to fight, so be careful with `dmg_or_hits` parameter
        """

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        link = link if link.startswith("http") else f"{URL}battle.html?id={link}"
        if side.lower() not in ("defender", "attacker"):
            return await ctx.send(f'side must be "defender" or "attacker" (not {side})')

        dmg = int(dmg_or_hits.replace("k", "000"))
        api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))

        main_tree = await self.bot.get_content(link, login_first=True)
        Health = int(float(main_tree.xpath('//*[@id="actualHealth"]')[0].text))
        food_limit = main_tree.xpath('//*[@id="sfoodQ5"]/text()')[0]
        gift_limit = main_tree.xpath('//*[@id="sgiftQ5"]/text()')[0]
        food = int(float(main_tree.xpath('//*[@id="foodLimit2"]')[0].text))
        gift = int(float(main_tree.xpath('//*[@id="giftLimit2"]')[0].text))
        if int(weapon_quality):
            wep = main_tree.xpath(f'//*[@id="Q{weapon_quality}WeaponStock"]/text()')[0]
        else:
            wep = "unlimited"

        if api['type'] == "ATTACK":
            if side.lower() == "attacker":
                try:
                    neighboursId = [region['neighbours'] for region in await self.bot.get_content(
                        f'{URL}apiRegions.html') if region["id"] == api['regionId']][0]
                    aBonus = [i for region in await self.bot.get_content(f'{URL}apiMap.html') for i in neighboursId if
                              i == region['regionId'] and region['occupantId'] == api['attackerId']]
                except:
                    aBonus = [api['attackerId'] * 6]
                await ctx.invoke(self.bot.get_command("fly"), aBonus[0], ticket_quality, nick=nick)
            elif side.lower() == "defender":
                await ctx.invoke(self.bot.get_command("fly"), api['regionId'], ticket_quality, nick=nick)
        elif api['type'] == "RESISTANCE":
            await ctx.invoke(self.bot.get_command("fly"), api['regionId'], ticket_quality, nick=nick)
        msg = await ctx.send(f"Limits: {food}/{gift}. Storage: {food_limit}/{gift_limit}/{wep} Q{weapon_quality} weps.")
        damage_done = 0
        start_time = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
        start = time()
        update = 0
        Damage = 0
        for _ in range(100):
            if time() - start > int(start_time):
                break  # round is over
            if Health < 50:
                if (not food or not int(food_limit)) and (not gift or not int(gift_limit)):
                    await msg.edit("\ndone limits")
                    break
                if gift and int(gift_limit):
                    # use gifts limits first (save motivates limits)
                    use = "gift"
                    gift -= 1
                elif not food or not int(food_limit):
                    use = "gift"
                    gift -= 1
                else:
                    use = "eat"
                    food -= 1
                await self.bot.get_content(f"{URL}{use}.html", data={'quality': 5})
            for _ in range(5):
                try:
                    tree, status = await self.send_fight_request(URL, main_tree, weapon_quality, side)
                    Damage += int(str(tree.xpath('//*[@id="damage_done"]')[0].text).replace(",", ""))
                    Health = float(tree.xpath("//*[@id='healthUpdate']")[0].text.split()[0])
                    if dmg < 1000:
                        Damage += 5  # Berserk
                    update += 1
                    break
                except:
                    # "Slow down"
                    delete = tree.xpath('//img/@src')
                    if delete and "delete.png" in delete[0]:
                        break
                    await msg.edit("\nSlow down")
                    await sleep(2)
            if not update:  # Error
                break
            damage_done += Damage
            hits_or_dmg = "hits" if dmg < 1000 else "dmg"
            if update % 4 == 0:
                # dmg update every 4 berserks.
                await msg.edit(f"\n{hits_or_dmg.title()} done so far: {damage_done}")
            if damage_done >= dmg:
                await msg.edit(f"\nDone {damage_done} {hits_or_dmg}")
                break
            if not food and not gift and not Health:
                use_medkit = input(f"Done limits. use medkit and continue (y/n)?")
                if use_medkit == "y":
                    await self.bot.get_content(f"{URL}medkit.html", data={})
                else:
                    break
            await sleep(1)

    @command()
    async def hunt(self, ctx, nick: IsMyNick, max_dmg_for_bh="500k", weapon_quality: int = 5, start_time: int = 60):
        """Auto hunt BHs (attack and RWs)
        If `nick` containing more than 1 word - it must be within quotes."""
        dead_servers = ["primera", "secura", "suna"]
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        max_dmg_for_bh, start_time = int(max_dmg_for_bh.replace("k", "000")), int(start_time)
        await ctx.send(f"Starting to hunt at {server}.")
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
                await ctx.send("Seconds till next battle:", time_to_sleep)
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
                    tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}')
                    Health = int(float(str(tree.xpath("//*[@id='actualHealth']")[0].text)))
                    hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value
                    food = int(tree.xpath('//*[@id="foodLimit2"]')[0].text)
                    gift = int(tree.xpath('//*[@id="giftLimit2"]')[0].text)
                    if Health < 50:
                        use = "eat" if food else "gift"
                        await self.bot.get_content(f"{URL}{use}.html", data={'quality': 5})
                    battleScore = await self.bot.get_content(
                        f'{URL}battleScore.html?id={hidden_id}&at={apiCitizen["id"]}&ci={apiCitizen["citizenshipId"]}&premium=1')
                    Damage = 0
                    if server in dead_servers:
                        value = "Berserk" if battleScore["spectatorsOnline"] != 1 and Health >= 50 else ""
                    else:
                        value = "Berserk"
                    for _ in range(5):
                        try:
                            tree, _ = await self.send_fight_request(URL, tree, weapon_quality, side, value)
                            Damage = int(str(tree.xpath('//*[@id="damage_done"]')[0].text).replace(",", ""))
                            await sleep(0.3)
                            break
                        except:
                            await sleep(2)
                    try:
                        damage_done += Damage
                    except:
                        await ctx.send("Couldn't hit")
                    if not food and not gift and not Health:
                        await ctx.send("done limits")
                        damage_done = 0
                    return damage_done

                async def check(side, damage_done, should_continue):
                    tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}')
                    hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value

                    try:
                        top1Name = tree.xpath(f"//*[@id='top{side}1']//div//a[1]/text()")[0].strip()
                        top1dmg = int(str(tree.xpath(f'//*[@id="top{side}1"]/div/div[2]')[0].text).replace(",", ""))
                    except:
                        top1Name, top1dmg = "None", 0
                    battleScore = await self.bot.get_content(
                        f'{URL}battleScore.html?id={hidden_id}&at={apiCitizen["id"]}&ci={apiCitizen["citizenshipId"]}&premium=1')
                    # condition - You are top 1 / did more dmg than your limit / refresh problem
                    condition = (top1Name == nick or
                                 damage_done > max_dmg_for_bh or
                                 damage_done > top1dmg)
                    if battleScore["remainingTimeInSeconds"] > start_time:
                        return False
                    elif battleScore['spectatorsOnline'] == 1:
                        if top1dmg > max_dmg_for_bh or condition:
                            return False
                        else:
                            return True
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
                                    f'{URL}battleScore.html?id={hidden_id}&at={apiCitizen["id"]}&ci={apiCitizen["citizenshipId"]}&premium=1')
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
                    await ctx.send(f"Fighting at: {URL}battle.html?id={battle_id}&round={apiBattles['currentRound']}")
                    await self.bot.get_content(URL, login_first=True)
                    if apiBattles['type'] == "ATTACK":
                        if aDMG < max_dmg_for_bh:
                            try:
                                await ctx.invoke(self.bot.get_command("fly"), aBonus[0], 5, nick=nick)
                            except:
                                await ctx.send("I couldn't find the bonus region")
                                continue
                            await hunting("attacker", aDMG, dDMG < max_dmg_for_bh)

                        if dDMG < max_dmg_for_bh:
                            await ctx.invoke(self.bot.get_command("fly"), apiBattles['regionId'], 5, nick=nick)
                            await hunting("defender", dDMG, aDMG < max_dmg_for_bh)

                    elif apiBattles['type'] == "RESISTANCE":
                        await ctx.invoke(self.bot.get_command("fly"), apiBattles['regionId'], 5, nick=nick)
                        if aDMG < max_dmg_for_bh:
                            await hunting("attacker", aDMG, dDMG < max_dmg_for_bh)

                        if dDMG < max_dmg_for_bh:
                            await hunting("defender", dDMG, aDMG < max_dmg_for_bh)
                    else:
                        continue

    @command()
    async def hunt_battle(self, ctx, nick: IsMyNick, link, side="attacker", max_dmg_for_bh: int = 1,
                          weapon_quality: int = 0):
        """
        Hunting BH at specific battle.
        (Good for practice / leagues / CW)
        If `nick` containing more than 1 word - it must be within quotes.
        [Might be bugged]"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        if side.lower() not in ("defender", "attacker"):
            return await ctx.send(f'"side" must be "defender" or "attacker" (not {side})')
        r = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        while 8 not in (r['defenderScore'], r['attackerScore']):
            r = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
            time_till_round_end = r["hoursRemaining"] * 3600 + r["minutesRemaining"] * 60 + r[
                "secondsRemaining"] - randint(15, 45)
            await ctx.send(f"Hunting at {link} ({side}). sleeping for {time_till_round_end} seconds.")
            await sleep(time_till_round_end)
            main_tree = await self.bot.get_content(link, login_first=True)
            damage_done = 0
            while damage_done < int(max_dmg_for_bh):
                Health = int(float(str(main_tree.xpath("//*[@id='actualHealth']")[0].text)))
                food = main_tree.xpath('//*[@id="foodLimit2"]')[0].text
                food_limit = main_tree.xpath('//*[@id="sfoodQ5"]/text()')[0]
                gift = main_tree.xpath('//*[@id="giftLimit2"]')[0].text
                if Health < 50:
                    if int(food) and int(food_limit):
                        await self.bot.get_content(f"{URL}eat.html", data={'quality': 5})
                    else:
                        await self.bot.get_content(f"{URL}gift.html", data={'quality': 5})
                Damage = 0
                for _ in range(5):
                    try:
                        tree, status = await self.send_fight_request(URL, main_tree, weapon_quality, side)
                        Damage = int(str(tree.xpath('//*[@id="damage_done"]')[0].text).replace(",", ""))
                        break
                    except:
                        Damage = 0
                        await sleep(2)
                damage_done += Damage
                if damage_done >= int(max_dmg_for_bh):
                    break
                if int(food) == 0 and int(gift) == 0 and Health == 0:
                    await ctx.send("done limits")
                    return
                await sleep(randint(0, 2))

    @command(aliases=["motivates"])
    async def motivate(self, ctx, *, nick):
        """
        Send motivates.
        * checking first 200 new citizens only.
        * If you not have Q3 food / Q3 gift / Q1 weps when it start - it will try to take some from your MU storage.
        
        If you want to send motivates with specific type only, write in this format:
        .motivate My Nick, wep
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if "," in nick:
            nick, Type = nick.split(",")
            Type = Type.strip()
        else:
            Type = "all"
        await IsMyNick().convert(ctx, nick.strip())

        tree = await self.bot.get_content(URL + 'storage.html?storageType=PRODUCT', login_first=True)

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
            await ctx.invoke(self.bot.get_command("supply"), 15, 1, "wep", nick=nick)
            await ctx.invoke(self.bot.get_command("supply"), 10, 3, "food", nick=nick)
            await ctx.invoke(self.bot.get_command("supply"), 5, 3, "gift", nick=nick)
            storage = get_storage(tree, Type)

        newCitizens_tree = await self.bot.get_content(URL + 'newCitizens.html?countryId=0')
        start_food = int(newCitizens_tree.xpath('//*[@id="foodLimit2"]')[0].text)
        citizenId = int(newCitizens_tree.xpath("//tr[2]//td[1]/a/@href")[0].split("=")[1])
        checking = list()
        for _ in range(200):  # newest 200 players
            try:
                if len(checking) >= 5:
                    break
                tree = await self.bot.get_content(f'{URL}profile.html?id={citizenId}')
                current_food = int(tree.xpath('//*[@id="foodLimit2"]')[0].text)
                if current_food - start_food == 5:
                    await ctx.send("You have sent too many motivates today!")
                    break
                today = int(tree.xpath('//*[@class="sidebar-clock"]/b/text()')[-1].split()[-1])
                birthday = int(
                    tree.xpath(f'//*[@class="profile-row" and span = "Birthday"]/span/text()')[0].split()[-1])
                if today - birthday > 3:
                    await ctx.send("Checked all new players")
                    break
                await ctx.send(f"Checking {URL}profile.html?id={citizenId}")
                if tree.xpath('//*[@id="motivateCitizenButton"]'):
                    for num in storage:
                        payload = {'type': num, "submit": "Motivate", "id": citizenId}
                        send = await self.bot.get_content(f"{URL}motivateCitizen.html?id={citizenId}", data=payload)
                        if "&actionStatus=SUCCESFULLY_MOTIVATED" in send:
                            checking.append(send)
                            await ctx.send(send)
                            break
                citizenId -= 1
            except Exception as error:
                await ctx.send("error:", error)

    @command(aliases=["dow", "mpp"])
    async def attack(self, ctx, ID: int, delay_or_battle_link, *, nick):
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
            for _ in range(20):
                apiBattles = await self.bot.get_content(
                    delay_or_battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
                dScore = apiBattles['defenderScore']
                aScore = apiBattles['attackerScore']
                round_ends = apiBattles["hoursRemaining"] * 3600 + apiBattles["minutesRemaining"] * 60 + apiBattles[
                    "secondsRemaining"]
                if 8 in (dScore, aScore):
                    await ctx.send("This battle is over")
                    return
                elif 7 not in (dScore, aScore):
                    await sleep(round_ends + 20)
                    continue

                else:
                    if round_ends > 5:  # long round case, due to e-sim lags.
                        await sleep(round_ends)
                        continue
                    break

        elif delay_or_battle_link:
            await sleep(int(delay_or_battle_link))

        if action == "attack":
            payload = {'action': "ATTACK_REGION", 'regionId': ID, 'attackButton': "Attack"}
        elif action == "mpp":
            payload = {'action': "PROPOSE_ALLIANCE", 'countryId': ID, 'submit': "Propose alliance"}
        elif action == "dow":
            payload = {'action': "DECLARE_WAR", 'countryId': ID, 'submit': "Declare war"}
        else:
            await ctx.send(f"parameter 'action' MOST be one of those: mpp/dow/attack (not {action})")
            return
        for x in range(5):  # trying 5 times due to e-sim lags.
            url = await self.bot.get_content(URL + "countryLaws.html", data=payload, login_first=not x)
            await ctx.send(url)

    @command()
    async def muinv(self, ctx, *, nick: IsMyNick):
        """
        shows all of your in-game Military Unit inventory.
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(f"{URL}militaryUnitStorage.html", login_first=True)
        container_1 = tree.xpath("//div[@class='storage']")
        quantity = [item.xpath("div[1]/text()")[0].strip() for item in container_1]
        products = list()
        for item in container_1:
            name = item.xpath("div[2]/img/@src")[0].replace("//cdn.e-sim.org//img/productIcons/", "").replace(".png",
                                                                                                              "")
            if name.lower() in ["iron", "grain", "diamonds", "oil", "stone", "wood"]:
                quality = ""
            else:
                quality = item.xpath("div[2]/img/@src")[1].replace(
                    "//cdn.e-sim.org//img/productIcons/", "").replace(".png", "")
            products.append(f"{quality.title()} {name}" if quality else f"{name}")

        embed = Embed()
        for i in range(len(products) // 5 + 1):
            value = [f"**{a}**: {b}" for a, b in zip(products[i * 5:(i + 1) * 5], quantity[i * 5:(i + 1) * 5])]
            embed.add_field(name="**Products: **" if not i else u"\u200B",
                            value="\n".join(value) if value else u"\u200B")
        embed.set_footer(text="Military Unit inventory")
        await ctx.send(embed=embed)

    @command()
    async def limits(self, ctx, *, nick: IsMyNick):
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL, login_first=True)
        gold = tree.xpath('//*[@id="userMenu"]//div//div[4]//div[1]/b/text()')[0]
        food_limit = tree.xpath('//*[@id="foodQ5"]/text()')[0]
        gift_limit = tree.xpath('//*[@id="giftQ5"]/text()')[0]
        food = int(float(tree.xpath('//*[@id="foodLimit2"]')[0].text))
        gift = int(float(tree.xpath('//*[@id="giftLimit2"]')[0].text))
        await ctx.send(f"Limits: {food}/{gift}. Storage: {food_limit}/{gift_limit}\n{gold} Gold.")

    @command()
    async def medkit(self, ctx, *, nick: IsMyNick):
        post_use = await self.bot.get_content(
            f"https://{ctx.channel.name}.e-sim.org/medkit.html", data={}, login_first=True)
        await ctx.send(post_use)

    @command(aliases=["upgrade"])
    async def reshuffle(self, ctx, eq_id_or_link, parameter, *, nick: IsMyNick):
        """
        Reshuffle/upgrade specific parameter.
        Parameter example: Increase chance to avoid damage by 7.08%
        If it's not working, you can try writing "first" or "last" as parameter.

        it's recommended to copy and paste the parameter, but you can also write first/last
        """
        action = ctx.invoked_with
        if action.lower() not in ("reshuffle", "upgrade"):
            await ctx.send(f"'action' parameter can be reshuffle/upgrade only (not{action})")
            return
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        ID = str(eq_id_or_link).replace(f"{URL}showEquipment.html?id=", "")  # link case
        LINK = f"{URL}showEquipment.html?id={ID}"
        tree = await self.bot.get_content(LINK, login_first=True)
        eq = tree.xpath('//*[@id="esim-layout"]//div/div[4]/div/h4/text()')
        parameter_id = tree.xpath('//*[@id="esim-layout"]//div/div[4]/div/h3/text()')
        if parameter in eq[0].replace("by  ", "by ") or parameter == "first":
            parameter_id = parameter_id[0].split("#")[1]
        elif parameter in eq[1].replace("by  ", "by ") or parameter == "last":
            parameter_id = parameter_id[1].split("#")[1]
        else:
            return await ctx.send(f"Did not find parameter {parameter} at {LINK}. Try copy & paste.")
        payload = {'parameter_id': parameter_id, 'action': f"{action.upper()}_PARAMETER", "submit": action.capitalize()}
        url = await self.bot.get_content(URL + "equipmentAction.html", data=payload)
        await ctx.send(url)

    async def rw(self, ctx, region_id_or_link, ticket_quality: Optional[int] = 5, *, nick: IsMyNick):
        """
        Open RW.
        Note: region can be link or id.
        * It will auto fly to that region."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        region_link = region_id_or_link if "http" in region_id_or_link else f"{URL}region.html?id={region_id_or_link}"
        await ctx.invoke(self.bot.get_command("fly"), region_link, ticket_quality, nick=nick)
        url = await self.bot.get_content(region_link, data={"submit": "startRWbutton"})
        await ctx.send(url)

    async def supply(self, ctx, amount: int, quality: Optional[int] = 5, product="wep", *, nick: IsMyNick):
        """Taking specific product from MU storage."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL, login_first=True)
        my_id = str(tree.xpath('//*[@id="userName"]/@href')[0]).split("=")[1]
        payload = {'product': f"{quality}-{product}" if quality else product, 'quantity': amount,
                   "reason": " ", "citizen1": my_id, "submit": "Donate"}
        get_supply = await self.bot.get_content(URL + "militaryUnitStorage.html", data=payload)
        if "DONATE_PRODUCT_FROM_MU_OK" in str(get_supply):
            await ctx.send("DONATE_PRODUCT_FROM_MU_OK")
        await ctx.send(get_supply)

    @command(aliases=["gift"])
    async def food(self, ctx, quality: Optional[int] = 5, *, nick: IsMyNick):
        """Using food or gift"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        url = await self.bot.get_content(f"{URL}{ctx.invoked_with.lower().replace('food', 'eat')}.html",
                                         data={'quality': quality}, login_first=True)
        await ctx.send(url)

    async def watch(self, ctx, nick: IsMyNick, link, side, start_time: int = 60,
                    keep_wall="3kk", let_overkill="10kk", weapon_quality: int = 5):
        """
        [might be bugged at the moment]
        Fight at the last minutes of every round in a given battle.
    
        Examples:
        link="https://alpha.e-sim.org/battle.html?id=1", side="defender"
        In this example, it will start fighting at t1, it will keep 3kk wall (checking every 10 sec),
        and if enemies did more than 10kk it will pass this round.
        (rest args have default value)
    
        link="https://alpha.e-sim.org/battle.html?id=1", side="defender", start_time=120, keep_wall="5kk", let_overkill="15kk")
        In this example, it will start fighting at t2 (120 sec), it will keep 5kk wall (checking every 10 sec),
        and if enemies did more than 15kk it will pass this round.
        * It will auto fly to bonus region (with Q5 ticket)
        * If `nick` containing more than 1 word - it must be within quotes.
        """
        server = ctx.channel.name
        link = link if link.startswith("http") else f"https://{server}.e-sim.org/battle.html?id={link}"
        URL = f"https://{server}.e-sim.org/"
        if side.lower() not in ("defender", "attacker"):
            return await ctx.send(f'"side" must be "defender" or "attacker" (not {side})')

        let_overkill = let_overkill.replace("k", "000")
        keep_wall = keep_wall.replace("k", "000")
        r = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        if r['type'] == "ATTACK":
            if side.lower() == "attacker":
                try:
                    neighboursId = [z['neighbours'] for z in await self.bot.get_content(
                        f"{URL}apiRegions.html") if z["id"] == r['regionId']][0]
                    aBonus = [i for z in await self.bot.get_content(f'{URL}apiMap.html') for i in neighboursId if
                              i == z['regionId'] and z['occupantId'] == r['attackerId']]
                except:
                    aBonus = r['attackerId']
                try:
                    await ctx.invoke(self.bot.get_command("fly"), aBonus, 5, nick=nick)
                except:
                    return await ctx.send("I couldn't find the bonus region")
            elif side.lower() == "defender":
                await ctx.invoke(self.bot.get_command("fly"), r['regionId'], 5, nick=nick)
        elif r['type'] == "RESISTANCE":
            await ctx.invoke(self.bot.get_command("fly"), r['regionId'], 5, nick=nick)

        while 8 not in (r['defenderScore'], r['attackerScore']):
            r = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
            time_till_round_end = r["hoursRemaining"] * 3600 + r["minutesRemaining"] * 60 + r[
                "secondsRemaining"] - start_time
            await ctx.send(f"Sleeping for {time_till_round_end} seconds.")
            await sleep(time_till_round_end)
            start = time()
            tree = await self.bot.get_content(link, login_first=True)
            food = tree.xpath('//*[@id="foodLimit2"]')[0].text
            gift = tree.xpath('//*[@id="giftLimit2"]')[0].text
            food_limit = tree.xpath('//*[@id="sfoodQ5"]/text()')[0]
            gift_limit = tree.xpath('//*[@id="sgiftQ5"]/text()')[0]
            await ctx.send(f"{link}&round={r['currentRound']}\nStarting to hit {food} food ({food_limit}"
                           f"in storage) and {gift} gift ({gift_limit} in storage) limits.")

            if time() - start > start_time:
                break
            if side.lower() == "attacker":
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
            Health = int(float(tree.xpath('//*[@id="actualHealth"]')[0].text))
            if Health < 50:
                if int(food) and int(food_limit):
                    await self.bot.get_content(f"{URL}eat.html", data={'quality': 5})
                else:
                    await self.bot.get_content(f"{URL}gift.html", data={'quality': 5})
                if not int(food) and not int(gift):
                    await ctx.send("Done limits")
                    return
            else:
                await self.send_fight_request(URL, tree, weapon_quality, side)

            if not int(food) and not int(gift) and not Health:
                return await ctx.send("Done limits")
            await sleep(0.5)

    @command(aliases=["unwear"])
    async def wear(self, ctx, ids, *, nick: IsMyNick):
        """
        Wear/take off specific EQ IDs.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        ids = [x.strip() for x in ids.split(",") if x.strip()]
        for Index, ID in enumerate(ids):
            ID = ID.replace("#", "").strip()
            payload = {'action': "PUT_OFF" if ctx.invoked_with.lower() == "unwear" else "EQUIP",
                       'itemId': ID.replace("#", "").replace(f"{URL}showEquipment.html?id=", "")}
            url = await self.bot.get_content(f"{URL}equipmentAction.html", data=payload, login_first=not Index)
            await sleep(randint(1, 2))
            if url == "http://www.google.com/":
                # e-sim error
                await sleep(randint(2, 5))
            results.append(f"ID {ID} - {url}\n")
        await ctx.send("".join(results))


def setup(bot):
    bot.add_cog(War(bot))
