import re
from asyncio import sleep
from datetime import datetime, time as dt_time, timedelta
from random import randint, uniform
import time
from typing import Optional
import os

from discord.ext.commands import Cog, command
from pytz import timezone

import utils
from Converters import Dmg, Id, IsMyNick, Product, Quality, Side


class War(Cog):
    """War Commands"""

    def __init__(self, bot):
        self.bot = bot

    async def dump_health(self, server, battle_id, side, wep):
        URL = f"https://{server}.e-sim.org/"
        tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}', return_tree=True)
        fight_url, data = await self.get_fight_data(URL, tree, wep, side)
        for _ in range(1, 20):
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
            await sleep(uniform(0, 2))

    @command()
    async def auto_fight(self, ctx, nick: IsMyNick, restores: int = 100, battle_id: Id = 0,
                         side: Side = "attacker", wep: int = 0, food: int = 5, gift: int = 0, ticket_quality: int = 5,
                         chance_to_skip_restore: int = 15):
        """Dumping health at a random time every restore

        If `nick` contains more than 1 word - it must be within quotes.
        If you want to skip a parameter, you should write the default value.
        Example: `.add "My Nick" 100 0 attacker 0 5` - write 0 to `battle_id` in order to change `food`"""

        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        specific_battle = (battle_id != 0)
        await ctx.send(f"**{nick}** Ok sir! If you want to stop it, type `.hold auto_fight {nick}`")

        if specific_battle and 1 <= ticket_quality <= 5:
            api_battles = await self.bot.get_content(f"{URL}apiBattles.html?battleId={battle_id}")
            bonus_region = await utils.get_bonus_region(self.bot, URL, side, api_battles)
            if bonus_region:
                await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick)

        while restores > 0 and not self.bot.should_break(ctx):
            restores -= 1
            if randint(1, 100) <= chance_to_skip_restore:
                await sleep(600)
            if not battle_id:
                battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)
            await ctx.send(f'**{nick}** <{URL}battle.html?id={battle_id}> side: {side}')
            if not battle_id:
                await ctx.send(
                    f"**{nick}** WARNING: I can't fight in any battle right now, but I will check again after the next restore")
                await utils.random_sleep(restores)
                continue
            tree = await self.bot.get_content(URL + "home.html", return_tree=True)
            check = tree.xpath('//*[@id="taskButtonWork"]//@href')  # checking if you can work
            if check and randint(1, 4) == 2:  # Don't work as soon as you can (suspicious)
                current_loc = await utils.location(self.bot, nick, server)
                await ctx.invoke(self.bot.get_command("work"), nick=nick)
                await ctx.invoke(self.bot.get_command("fly"), current_loc, ticket_quality, nick=nick)
            apiBattles = await self.bot.get_content(f"{URL}apiBattles.html?battleId={battle_id}")
            if 8 in (apiBattles['attackerScore'], apiBattles['defenderScore']):
                if specific_battle:
                    return await ctx.send(f"**{nick}** Battle has finished.")
                else:
                    await ctx.send(f"**{nick}** Searching for the next battle...")
                    battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)

            tree = await self.bot.get_content(f'{URL}battle.html?id={battle_id}', return_tree=True)
            fight_ability = tree.xpath("//*[@id='newFightView']//div[3]//div[3]//div//text()[1]")
            if any("You can't fight in this battle from your current location." in s for s in fight_ability):
                return await ctx.send(f"**{nick}** ERROR: You can't fight in this battle from your current location.")
            await self.dump_health(server, battle_id, side, wep)
            if food:
                await self.bot.get_content(f"{URL}eat.html", data={'quality': food})
            if gift:
                await self.bot.get_content(f"{URL}gift.html", data={'quality': gift})
            if food or gift:
                await self.dump_health(server, battle_id, side, wep)
            await utils.random_sleep(restores)

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

    @command(aliases=["buff-"])
    async def buff(self, ctx, buffs_names, *, nick: IsMyNick):
        """Buy and use buffs.
        type `.buff-` if you don't want to buy the buff.
        The buff names should be formal (can be found via F12), but here are some shortcuts:
        VAC = EXTRA_VACATIONS, SPA = EXTRA_SPA, SEWER = SEWER_GUIDE, STR = STEROIDS, PD_10 = PAIN_DEALER_10_H
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
            elif "PD" in buff_name:
                buff_name = buff_name.replace("PD", "PAIN_DEALER") + "_H"

            actions = ("BUY", "USE") if ctx.invoked_with.lower() == "buff" else ("USE", )
            for Index, action in enumerate(actions):
                if self.bot.should_break(ctx):
                    return
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
                    dmg_or_hits: Dmg = 200, ticket_quality: int = 5, consume_first="food"):
        """
        Dumping limits at a specific battle.

        * It will auto fly to bonus region.
        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        * set `consume_first` to `none` if you want to consume `1/1` (fast servers)
        * If `nick` contains more than 1 word - it must be within quotes.
        """

        if consume_first.lower() not in ("food", "gift", "none"):
            return await ctx.send(f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        link = f"{URL}battle.html?id={link}"
        dmg = dmg_or_hits
        api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        tree = await self.bot.get_content(link, return_tree=True)
        Health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)
        food_storage = int((tree.xpath('//*[@id="sfoodQ5"]/text()') or [0])[0])
        gift_storage = int((tree.xpath('//*[@id="sgiftQ5"]/text()') or [0])[0])
        food_limit = int(float(tree.xpath('//*[@id="foodLimit2"]')[0].text))
        gift_limit = int(float(tree.xpath('//*[@id="giftLimit2"]')[0].text))
        try:
            wep = weapon_quality if not weapon_quality else int(
                tree.xpath(f'//*[@id="Q{weapon_quality}WeaponStock"]/text()')[0])
        except:
            return await ctx.send(f"ERROR: There are 0 Q{weapon_quality} in storage")

        if 1 <= ticket_quality <= 5:
            bonus_region = await utils.get_bonus_region(self.bot, URL, side, api)
            if bonus_region:
                await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick)
        output = f"**{nick}** Limits: {food_limit}/{gift_limit}. Storage: {food_storage}/{gift_storage}/{wep} Q{weapon_quality} weps.\n" \
                 f"If you want me to stop, type `.hold fight {nick}`"
        msg = await ctx.send(output)
        damage_done = 0
        update = 0
        fight_url, data = await self.get_fight_data(URL, tree, weapon_quality, side, value=("Berserk" if dmg >= 5 else ""))
        hits_or_dmg = "hits" if dmg < 1000 else "dmg"
        round_ends = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
        start = time.time()
        while not self.bot.should_break(ctx) and damage_done < dmg and (time.time() - start < round_ends):
            if weapon_quality > 0 and ((dmg >= 5 and wep < 5) or (dmg < 5 and wep == 0)):
                await ctx.send(f"**{nick}** Done {damage_done:,} {hits_or_dmg}\nERROR: no Q{weapon_quality} weps in storage")
                break
            if (Health < 50 and dmg >= 5) or (Health == 0 and dmg < 5):
                if food_storage == 0 and gift_storage == 0:
                    output += f"\nERROR: 0 food and gift in storage"
                    break
                elif food_limit == 0 and gift_limit == 0:
                    break
                elif food_storage == 0 or gift_storage == 0:
                    output += f"\nWARNING: 0 {'food' if food_storage == 0 else 'gift'} in storage"

                use = None
                if consume_first.lower() == "gift" or (consume_first.lower() == "none" and gift_limit > food_limit):
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
                        output += f"\nRound is over."
                        break
                    else:
                        res = tree.xpath('//div//div/text()')
                        await ctx.send(f"**{nick}** ERROR: {' '.join(res).strip()}")
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
        await msg.edit(content=output)
        await ctx.send(f"**{nick}** Done {damage_done:,} {hits_or_dmg}, reminding limits: {food_limit}/{gift_limit}")

    @command(hidden=True)
    async def hold(self, ctx, Command, *, nicks):
        server = ctx.channel.name
        Command = Command.lower()
        for nick in [x.strip() for x in nicks.split(",") if x.strip()]:
            if nick.lower() == "all":
                nick = utils.my_nick(server)
            if nick.lower() == utils.my_nick(server).lower():
                if server not in self.bot.should_break_dict:
                    self.bot.should_break_dict[server] = {}
                self.bot.should_break_dict[server][Command] = True
                if "auto_" in Command and "fight" not in Command:  # auto_motivate and auto_work
                    data = await utils.find_one("auto", Command.split("_")[1], os.environ['nick'])
                    if server in data:
                        del data[server]
                        await utils.replace_one("auto", Command.split("_")[1], os.environ['nick'], data)
                await sleep(uniform(1, 10))
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
                    if self.bot.should_break(ctx):
                        return
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
    async def hunt_battle(self, ctx, nick: IsMyNick, link, side: Side, dmg_or_hits_per_bh: Dmg = 1,
                          weapon_quality: int = 0, food: int = 5, gift: int = 5, start_time: int = 0):
        """Hunting BH at a specific battle.
        (Good for practice battle / leagues / civil war)

        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        If `nick` contains more than 1 word - it must be within quotes."""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        dmg = dmg_or_hits_per_bh
        hits_or_dmg = "hits" if dmg < 1000 else "dmg"
        while not self.bot.should_break(ctx):  # For each round
            api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
            if 8 in (api['defenderScore'], api['attackerScore']):
                await ctx.send(f"**{nick}** <{link}> is over")
                break
            seconds_till_round_end = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
            if seconds_till_round_end < 20:
                await sleep(30)
                continue
            seconds_till_hit = uniform(10, seconds_till_round_end - 10) if start_time < 10 else (seconds_till_round_end - uniform(start_time-5, start_time+5))
            await ctx.send(f"**{nick}** {seconds_till_hit} seconds from now (at T {timedelta(seconds=seconds_till_round_end-seconds_till_hit)}),"
                           f" I will hit {dmg} {hits_or_dmg} at <{link}> for the {side} side.\n"
                           f"If you want to cancel it, type `.hold hunt_battle {nick}`")
            await sleep(seconds_till_hit)
            tree = await self.bot.get_content(link, return_tree=True)
            if int(str(tree.xpath(f'//*[@id="{side}Score"]/text()')[0]).replace(",", "").strip()) != 0 and dmg_or_hits_per_bh == 1:
                await ctx.send(f"**{nick}** someone else already fought in this round <{link}>")
                await sleep(seconds_till_round_end - seconds_till_hit + 15)
                continue
            food_limit = int(tree.xpath('//*[@id="foodLimit2"]')[0].text)
            food_storage = int((tree.xpath('//*[@id="sfoodQ5"]/text()') or [0])[0])
            gift_limit = int(tree.xpath('//*[@id="giftLimit2"]')[0].text)
            gift_storage = int((tree.xpath('//*[@id="sgiftQ5"]/text()') or [0])[0])
            damage_done = 0
            fight_url, data = await self.get_fight_data(URL, tree, weapon_quality, side, value=("Berserk" if dmg >= 5 else ""))

            while damage_done < dmg and not self.bot.should_break(ctx):
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

                tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
                if not tree.xpath('//*[@id="DamageDone"]'):
                    if "Slow down a bit!" in tree.text_content():
                        await sleep(1)
                        continue
                    elif "No health left" in tree.text_content():
                        continue
                    elif "Round is closed" in tree.text_content():
                        break
                    else:
                        res = tree.xpath('//div//div/text()')
                        await ctx.send(f"**{nick}** ERROR: {' '.join(res).strip()}")
                        break
                if dmg < 5:
                    damage_done += 1
                elif dmg < 1000:
                    damage_done += 5
                else:
                    damage_done += int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
                await sleep(uniform(0, 2))

            await ctx.send(f"**{nick}** done {damage_done:,} {hits_or_dmg} at <{link}>")
            await sleep(seconds_till_round_end - seconds_till_hit + 15)

    @command()
    async def auto_motivate(self, ctx, *, nick: IsMyNick):
        """Motivates at random times throughout every day"""
        data = await utils.find_one("auto", "motivate", os.environ['nick'])
        data_copy = data.copy()
        data[ctx.channel.name] = {"channel_id": str(ctx.channel.id), "message_id": str(ctx.message.id), "nick": nick}
        if data != data_copy:
            await utils.replace_one("auto", "motivate", os.environ['nick'], data)
            await ctx.send(f"**{nick}** Alright.")

        while not self.bot.should_break(ctx):  # for every day:
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
            sec_til_midnight = (midnight - now).seconds
            await sleep(uniform(0, sec_til_midnight - 600))
            await ctx.invoke(self.bot.get_command("motivate"), nick=nick)

            # sleep till midnight
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
            await sleep((midnight - now).seconds + 20)

    @command()
    async def motivate(self, ctx, *, nick: IsMyNick):
        """
        Send motivates.
        * checking first 200 new citizens only.
        * If you do not have Q3 food / Q3 gift / Q1 weps when it starts - it will try to take some from your MU storage.
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        tree = await self.bot.get_content(URL + 'storage.html?storageType=PRODUCT', return_tree=True)

        def get_storage(tree):
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
                        break
                except:
                    break

            storage = {}
            if weps >= 15:
                storage["Q1 wep"] = 1

            if food >= 10:
                storage["Q3 food"] = 2

            if gift >= 5:
                storage["Q3 gift"] = 3
            return storage

        storage = get_storage(tree)
        if not storage:
            await ctx.invoke(self.bot.get_command("supply"), 15, "1", "WEAPON", nick=nick)
            await ctx.invoke(self.bot.get_command("supply"), 10, "3", "FOOD", nick=nick)
            await ctx.invoke(self.bot.get_command("supply"), 5, "3", "GIFT", nick=nick)
            tree = await self.bot.get_content(URL + 'storage.html?storageType=PRODUCT', return_tree=True)
            storage = get_storage(tree)
        if not storage:
            return await ctx.send(f"**{nick}** ERROR: Cannot motivate")
        for k in storage.keys():
            await ctx.send(f"**{nick}** WARNING: There are not enough {k}s in storage")
        new_citizens_tree = await self.bot.get_content(URL + 'newCitizens.html?countryId=0', return_tree=True)
        citizenId = int(new_citizens_tree.xpath("//tr[2]//td[1]/a/@href")[0].split("=")[1])
        checking = list()
        sent_count = 0
        while not self.bot.should_break(ctx):
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
                    for num in storage.values():
                        payload = {'type': num, "submit": "Motivate", "id": citizenId}
                        tree, url = await self.bot.get_content(f"{URL}motivateCitizen.html?id={citizenId}", data=payload, return_tree="both")
                        if "&actionStatus=SUCCESFULLY_MOTIVATED" in url:
                            checking.append(f"<{url}>")
                            sent_count += 1
                            break
                        else:
                            msg = ' '.join(tree.xpath("//div[2]/text()")).strip()
                            if "too many" in msg:
                                return await ctx.send(f"**{nick}** You have sent too many motivations today!")
                citizenId -= 1
            except Exception as error:
                await ctx.send(f"**{nick}** ERROR: {error}")
            if citizenId % 10 == 0 and checking:
                await ctx.send(f"**{nick}**\n" + "\n".join(checking))
                checking.clear()

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

        if not self.bot.should_break(ctx):
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
        tree = await self.bot.get_content(URL + "militaryUnitStorage.html", return_tree=True)
        my_id = str(tree.xpath('//*[@id="userName"]/@href')[0]).split("=")[1]
        payload = {'product': f"{quality or 5}-{product}", 'quantity': amount,
                   "reason": " ", "citizen1": my_id, "submit": "Donate"}
        url = await self.bot.get_content(URL + "militaryUnitStorage.html", data=payload)
        if "index" in url:
            await ctx.send(f"**{nick}** You are not in any military unit.")
        else:
            await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["gift"])
    async def food(self, ctx, quality: Optional[int] = 5, *, nick: IsMyNick):
        """Using food or gift"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        url = await self.bot.get_content(f"{URL}{ctx.invoked_with.lower().replace('food', 'eat')}.html", data={'quality': quality})
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def watch(self, ctx, nick: IsMyNick, link: Id, side: Side, start_time: int = 60,
                    keep_wall: Dmg = 3000000, let_overkill: Dmg = 10000000, weapon_quality: int = 5,
                    ticket_quality: int = 5, consume_first="food"):
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
        battle_link = f"https://{server}.e-sim.org/battle.html?id={link}"
        URL = f"https://{server}.e-sim.org/"

        r = await self.bot.get_content(battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
        if 1 <= ticket_quality <= 5:
            bonus_region = await utils.get_bonus_region(self.bot, URL, side, r)
            if bonus_region:
                await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick)

        while 8 not in (r['defenderScore'], r['attackerScore']):
            r = await self.bot.get_content(battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
            time_till_round_end = r["hoursRemaining"] * 3600 + r["minutesRemaining"] * 60 + r["secondsRemaining"]
            await ctx.send(f"**{nick}** Sleeping for {time_till_round_end} seconds :zzz:")
            await sleep(time_till_round_end - start_time)
            await ctx.send(f"**{nick}** <{battle_link}&round={r['currentRound']}>")
            start = time.time()
            while not self.bot.should_break(ctx) and time.time() - start < start_time:
                tree = await self.bot.get_content(battle_link, return_tree=True)
                if side == "attacker":
                    my_side = int(str(tree.xpath('//*[@id="attackerScore"]/text()')[0]).replace(",", "").strip())
                    enemy_side = int(str(tree.xpath('//*[@id="defenderScore"]/text()')[0]).replace(",", "").strip())
                else:
                    my_side = int(str(tree.xpath('//*[@id="defenderScore"]/text()')[0]).replace(",", "").strip())
                    enemy_side = int(str(tree.xpath('//*[@id="attackerScore"]/text()')[0]).replace(",", "").strip())
                if enemy_side - my_side > let_overkill:
                    await sleep(5)
                    continue
                if my_side - enemy_side > keep_wall:
                    await sleep(5)
                    continue
                await ctx.invoke(self.bot.get_command("fight"), nick, link, side, weapon_quality,
                                 abs(my_side - enemy_side) + keep_wall, ticket_quality, consume_first)

    @command(aliases=["unwear"])
    async def wear(self, ctx, ids, *, nick: IsMyNick):
        """
        Wear/take off a specific EQ IDs.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        ids = [int(x.replace("#", "").replace(f"{URL}showEquipment.html?id=", "").strip()) for x in ids.split(",") if x.strip()]
        for Index, ID in enumerate(ids):
            if self.bot.should_break(ctx):
                break
            payload = {'action': "PUT_OFF" if ctx.invoked_with.lower() == "unwear" else "EQUIP", 'itemId': ID}
            url = await self.bot.get_content(f"{URL}equipmentAction.html", data=payload)
            await sleep(uniform(1, 2))
            if url == "http://www.google.com/":
                # e-sim error
                await sleep(uniform(2, 5))
            results.append(f"ID {ID} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))


def setup(bot):
    bot.add_cog(War(bot))
