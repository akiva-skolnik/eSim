"""War.py"""
import os
import re
import time
from asyncio import sleep
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from random import randint, uniform, shuffle
from typing import Optional

from discord import Embed
from discord.ext.commands import Cog, command
from pytz import timezone

import utils
from Converters import Country, Dmg, Id, IsMyNick, Product, Quality, Side

# You may want to replace all `consume_first="gift"` to `consume_first="food"`


class War(Cog):
    """War Commands"""

    def __init__(self, bot):
        self.bot = bot

    async def dump_health(self, server, battle_id, side, wep):
        """Hit all limits"""
        base_url = f"https://{server}.e-sim.org/"
        tree = await self.bot.get_content(f'{base_url}battle.html?id={battle_id}', return_tree=True)
        fight_url, data = await self.get_fight_data(base_url, tree, wep, side)
        for _ in range(1, 20):
            health = tree.xpath("//*[@id='healthUpdate']/text()") or tree.xpath('//*[@id="actualHealth"]/text()')
            if health:
                health = float(health[0].split()[0])
            else:
                tree = await self.bot.get_content(f'{base_url}battle.html?id={battle_id}', return_tree=True)
                health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)

            if health == 0:
                break
            data["value"] = "Berserk" if health >= 50 else ""
            tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
            await sleep(uniform(0, 2))

    @command()
    async def auto_fight(self, ctx, nick: IsMyNick, battle_id: Id = 0, side: Side = "attacker", wep: Quality = 0,
                         food: Quality = 5, gift: Quality = 0, ticket_quality: Quality = 5,
                         chance_to_skip_restore: int = 7, restores: int = 120):
        """Dumping health at a random time every restore
        (everything inside [] is optional with default values)
        `battle_id=0` means random battle.

        If `nick` contains more than 1 word - it must be within quotes.
        You can write multiple nicks: "nick 1, nick 2, ..."

        Example: `.auto_fight "My Nick" 0 attacker 1 5 5 1 0 100`
        [In this example: battle=0 (random), fight for the attacker side, wep quality=1, food and gift quality=5, ticket quality=1, no skip restores (0%), 120 restores (20 hours)]"""

        data = {"restores": restores, "battle_id": battle_id, "side": side, "wep": wep, "food": food,
                "gift": gift, "ticket_quality": ticket_quality, "chance_to_skip_restore": chance_to_skip_restore}
        ctx.command = f"auto_fight-{ctx.message.id}"
        await utils.save_command(ctx, "auto", "fight", data)

        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        specific_battle = (battle_id != 0)
        while restores > 0 and not utils.should_break(ctx):
            restores -= 1
            if randint(0, 100) <= chance_to_skip_restore:
                await sleep(600)
            if not battle_id:
                battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)
            await ctx.send(f'**{nick}** <{base_url}battle.html?id={battle_id}> side: {side}\n'
                           f'If you want to stop it, type `.cancel auto_fight-{ctx.message.id} {nick}`')
            if not battle_id:
                await ctx.send(
                    f"**{nick}** WARNING: I can't fight in any battle right now, but I will check again after the next restore")
                await utils.random_sleep(restores)
                continue
            tree = await self.bot.get_content(base_url + "home.html", return_tree=True)
            if tree.xpath('//*[@id="taskButtonWork"]//@href') and randint(1, 4) == 2:  # Don't work as soon as you can (suspicious)
                await ctx.invoke(self.bot.get_command("work"), nick=nick)
            api_battles = await self.bot.get_content(f"{base_url}apiBattles.html?battleId={battle_id}")
            if 8 in (api_battles['attackerScore'], api_battles['defenderScore']):
                if specific_battle:
                    await ctx.send(f"**{nick}** Battle has finished.")
                    break
                await ctx.send(f"**{nick}** Searching for the next battle...")
                battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)
            if specific_battle and 1 <= ticket_quality <= 5:
                bonus_region = await utils.get_bonus_region(self.bot, base_url, side, api_battles)
                if bonus_region:
                    if not await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick):
                        restores = 0
            tree = await self.bot.get_content(f'{base_url}battle.html?id={battle_id}', return_tree=True)
            fight_ability = tree.xpath("//*[@id='newFightView']//div[3]//div[3]//div//text()[1]")
            if any("You can't fight in this battle from your current location." in s for s in fight_ability):
                if specific_battle and 1 <= ticket_quality <= 5:
                    bonus_region = await utils.get_bonus_region(self.bot, base_url, side, api_battles)
                    if bonus_region:
                        if not await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick):
                            break
                await ctx.send(f"**{nick}** ERROR: You can't fight in this battle from your current location.")
                break
            await self.dump_health(server, battle_id, side, wep)
            if food:
                await self.bot.get_content(f"{base_url}eat.html", data={'quality': food})
            if gift:
                await self.bot.get_content(f"{base_url}gift.html", data={'quality': gift})
            if food or gift:
                await self.dump_health(server, battle_id, side, wep)
            await utils.random_sleep(restores)

        await utils.remove_command(ctx, "auto", "fight")

    @command(name="BO")
    async def battle_order(self, ctx, battle: Id, side: Side, key: Optional[int] = 0, *, nick: IsMyNick):
        """
        Set battle order.
        You can use battle link/id.
        key=0 means MU order, key=1 means country order, and key=2 means coalition order
        """
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'action': 'SET_ORDERS' if key != 1 else 'CHANGE_ORDER',
                   'battleId' if key != 1 else 'battleOrderId': f"{battle}_{'true' if side == 'attacker' else 'false'}",
                   'submit': "Set orders"}
        links = {0: "militaryUnitsActions.html", 1: "countryLaws.html", 2: "coalitionManagement.html"}
        await self.bot.get_content(base_url + "myMilitaryUnit.html")
        url = await self.bot.get_content(base_url + links[key], data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def buff(self, ctx, buffs_names: str, *, nick: IsMyNick):
        """Buy and use buffs.

        The buff names should be formal (can be found via F12), but here are some shortcuts:
        VAC = EXTRA_VACATIONS, SPA = EXTRA_SPA, SEWER = SEWER_GUIDE, STR = STEROIDS, PD_10 = PAIN_DEALER_10_H
        More examples: BANDAGE_SIZE_C and CAMOUFLAGE_II, MILI_JINXED_ELIXIR, MINI_BLOODY_MESS_ELIXIR

        * You can also use blue/green/red/yellow instead of Jinxed/Finesse/bloody_mess/lucky
        * You can also use Q1-Q6 instead of mili/mini/standard/major/huge/exceptional
        * type `.buff-` if you don't want to buy the buff.

        Examples:
            .buff  str,tank    my nick
            .buff  Q1_elixirs  my nick"""
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        elixirs = ["BLOODY_MESS", "FINESE", "JINXED", "LUCKY"]
        shuffle(elixirs)

        buffs_names = buffs_names.upper().split(",")
        for buff in buffs_names[:]:
            if buff.endswith("_ELIXIRS"):
                buffs_names.remove(buff)
                buffs_names.extend([f'{buff.split("_")[0]}_{elixir}_ELIXIR' for elixir in elixirs])

        special_tree = await self.bot.get_content(f"{base_url}storage.html?storageType=SPECIAL_ITEM", return_tree=True)
        special = [item.xpath('b/text()')[0].replace(" ", "_").upper() for item in
                   special_tree.xpath('//div[@class="specialItemInventory"]') if item.xpath('span/text()')]
        results = []
        buffed = False
        for i, buff_name in enumerate(buffs_names):
            buff_name = buff_name.strip().replace(" ", "_")
            if buff_name == "VAC":
                buff_name = "EXTRA_VACATIONS"
            elif buff_name == "SPA":
                buff_name = "EXTRA_SPA"
            elif buff_name == "SEWER":
                buff_name = "SEWER_GUIDE"
            elif "STR" in buff_name:
                buff_name = "STEROIDS"
            elif "PD" in buff_name:
                buff_name = buff_name.replace("PD", "PAIN_DEALER") + ("_H" if not buff_name.endswith("_H") else "")
            elif buff_name.endswith("_ELIXIR"):
                buff_name = utils.fix_elixir(buff_name)
            buffs_names[i] = buff_name
            buff_for_sell = buff_name in ("STEROIDS", "EXTRA_VACATIONS", "EXTRA_SPA", "TANK", "BUNKER", "SEWER_GUIDE")
            actions = ("BUY", "USE") if buff_for_sell and buff_name not in special else ("USE", )
            for action in actions:
                if utils.should_break(ctx):
                    return
                if action == "USE":
                    payload = {'item': buff_name, 'storageType': "SPECIAL_ITEM", 'action': action, 'submit': 'Use'}
                else:
                    payload = {'itemType': buff_name, 'storageType': "SPECIAL_ITEM", 'action': action, "quantity": 1}
                url = await self.bot.get_content(base_url + "storage.html", data=payload)
                results.append(f"{buff_name}: <{url}>")
                if "error" in url.lower():
                    results.append(f"ERROR: No such buff ({buff_name})")
                if "MESSAGE_OK" in url and buff_name in ("STEROIDS", "TANK", "SEWER", "BUNKER"):
                    buffed = True
        if buffed:
            data = await utils.find_one(server, "info", nick)
            data["Buffed at"] = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%d/%m  %H:%M")
            await utils.replace_one(server, "info", nick, data)

        await ctx.send(f"**{nick}**\n" + "\n".join(results))
        if "EXTRA_SPA" in buffs_names or "EXTRA_VACATIONS" in buffs_names:
            tree = await self.bot.get_content(base_url, return_tree=True)
            food_limit, gift_limit = utils.get_limits(tree)
            await utils.update_info(server, nick, {"limits": f"{food_limit}/{gift_limit}"})

    @command(aliases=["travel"])
    async def fly(self, ctx, region_id: Id, ticket_quality: Optional[int] = 5, *, nick: IsMyNick) -> bool:
        """traveling to a region.
        If you do not have tickets of that quality, the bot will use lower quality"""
        if 1 <= ticket_quality <= 5:
            base_url = f"https://{ctx.channel.name}.e-sim.org/"
            tree = await self.bot.get_content(f"{base_url}region.html?id={region_id}", return_tree=True)
            country_id = tree.xpath('//*[@id="countryId"]/@value')
            tickets_qualities = [int(x) for x in tree.xpath('//*[@id="ticketQuality"]//@value')] or [6]
            if not country_id:  # already in the location
                return True
            if ticket_quality not in tickets_qualities:
                if min(tickets_qualities) < ticket_quality:
                    ticket_quality = min(tickets_qualities)
                else:
                    await ctx.reply(f"**{nick}** ERROR: there are 0 Q{ticket_quality} tickets in storage.")
                    return False
            health = float(tree.xpath('//*[@id="actualHealth"]/text()')[0].split()[0])
            required_hp = 50 - ticket_quality * 10
            if health < required_hp:
                food_storage, gift_storage = utils.get_storage(tree)
                food_limit, gift_limit = utils.get_limits(tree)
                if food_limit and food_storage:
                    await self.bot.get_content(f"{base_url}eat.html", data={'quality': 5})
                elif gift_limit and gift_storage:
                    await self.bot.get_content(f"{base_url}gift.html", data={'quality': 5})
                else:
                    await ctx.reply(f"**{nick}** ERROR: no health / limits.")
                    return False

            payload = {'countryId': country_id[0], 'regionId': region_id, 'ticketQuality': ticket_quality}
            url = await self.bot.get_content(f"{base_url}travel.html", data=payload)
            await sleep(uniform(0, 1))
            await ctx.send(f"**{nick}** <{url}>")
            return True
        else:
            return ticket_quality == 0  # ticket_quality=0 indicates that there's no need to fly.

    @classmethod
    def convert_to_dict(cls, s):
        """convert to dict"""
        return dict([a.split("=") for a in s.split("&")])

    @classmethod
    async def get_fight_data(cls, base_url, tree, wep, side, value="Berserk"):
        """get fight data"""
        fight_page_id = re.sub("[\"\']*", "", re.findall('url: (\".*fight.*.html\")', tree.text_content())[0])
        hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value
        data = {"weaponQuality": wep, "battleRoundId": hidden_id, "side": side if side == "attacker" else "default", "value": value or "Regular"}
        for script in tree.xpath("//script/text()"):
            if "&ip=" in script:
                break
        data.update(cls.convert_to_dict("ip=" + "".join(script).split("&ip=")[1].split("'")[0]))
        return f"{base_url}{fight_page_id}", data

    @command(aliases=["fight_fast"])
    async def fight(self, ctx, nick: IsMyNick, battle: Id, side: Side, weapon_quality: Quality = 5,
                    dmg_or_hits: Dmg = 200, ticket_quality: Quality = 5, consume_first="gift", medkits: int = 0) -> (bool, int):
        """
        Dumping limits at a specific battle.
        (everything inside [] is optional with default values)
        Examples:
            .fight "my nick" https://primera.e-sim.org/battle.html?id=1 attacker
            .fight nick 1 a 5 1kk 5 none 1

        * It will auto fly to bonus region.
        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        * set `consume_first` to `none` if you want to consume `1/1` (fast servers)
        * Use `fight_fast` instead of `fight` if you don't want it to spec the battle for a few seconds.
        * If `nick` contains more than 1 word - it must be within quotes.
        """

        consume_first = consume_first.lower()
        if consume_first not in ("food", "gift", "none"):
            await ctx.send(f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
            return True, 0
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        link = f"{base_url}battle.html?id={battle}"
        dmg = dmg_or_hits
        api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        if 1 <= ticket_quality <= 5:
            bonus_region = await utils.get_bonus_region(self.bot, base_url, side, api)
            if bonus_region:
                if not await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick):
                    return

        tree = await self.bot.get_content(link, return_tree=True)
        health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)
        try:
            food_storage, gift_storage = utils.get_storage(tree)
        except IndexError:
            await ctx.send(f"**{nick}** ERROR")
            return True, 0
        food_limit, gift_limit = utils.get_limits(tree)
        try:
            wep = weapon_quality if not weapon_quality else int(
                tree.xpath(f'//*[@id="weaponQ{weapon_quality}"]')[0].text)
        except IndexError:
            await ctx.send(f"**{nick}** ERROR: There are 0 Q{weapon_quality} weapons in storage")
            return True, 0

        output = f"**{nick}** Fighting at: <{link}&round={api['currentRound']}> for the {side}\n" \
                 f"Limits: {food_limit}/{gift_limit}. Storage: {food_storage}/{gift_storage}/{wep} Q{weapon_quality} weps.\n" \
                 f"If you want me to stop, type `.cancel {ctx.command} {nick}`"
        if food_storage < food_limit or gift_storage < gift_limit or (weapon_quality and wep < (food_limit+gift_limit)*5/0.6):
            output += f"\nWARNING: you need to refill your storage. See `.help supply`, `.help pack`, `.help buy`"
        msg = await ctx.send(output)
        damage_done = 0
        update = 0
        fight_url, data = await self.get_fight_data(base_url, tree, weapon_quality, side, value=("Berserk" if dmg >= 5 else ""))
        if ctx.invoked_with.lower() != "fight_fast":
            await sleep(uniform(3, 7))
        hits_or_dmg = "hits" if dmg <= 1000 else "dmg"
        round_ends = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
        start = time.time()
        while damage_done < dmg and (time.time() - start < round_ends) and not utils.should_break(ctx):
            if len(output) > 1900:
                output = "(Message is too long)"
            if weapon_quality > 0 and ((dmg >= 5 > wep) or (dmg < 5 and wep == 0)):
                await ctx.send(f"**{nick}** Done {damage_done:,} {hits_or_dmg}\nERROR: no Q{weapon_quality} weps in storage")
                break
            if (health < 50 and dmg >= 5) or (health == 0 and dmg < 5):
                if food_storage == 0 and gift_storage == 0:
                    output += "\nERROR: 0 food and gift in storage"
                    break
                if food_limit == 0 and gift_limit == 0:
                    if medkits > 0:
                        await ctx.invoke(self.bot.get_command("medkit"), nick=nick)
                        output = f"**{nick}** Continuing..."
                        msg = await ctx.send(output)
                        medkits -= 1
                        food_limit += 10
                        gift_limit += 10
                    else:
                        break

                use = None
                if consume_first == "gift" or (consume_first == "none" and gift_limit > food_limit):
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
                    await self.bot.get_content(f"{base_url}{use}.html", data={'quality': 5})
                    health += 50

            tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
            if not tree.xpath("//*[@id='healthUpdate']/text()"):
                if "Slow down a bit!" in tree.text_content():
                    await sleep(1)
                    continue
                if "No health left" in tree.text_content():
                    health = 0
                    continue
                if "Round is closed" in tree.text_content():
                    output += "\nRound is over."
                    break
                res = tree.xpath('//div//div/text()')
                await ctx.send(f"**{nick}** ERROR: {' '.join(res).strip()}")
                break
            if weapon_quality:
                wep -= 5 if dmg >= 5 else 1
            health = float(tree.xpath("//*[@id='healthUpdate']")[0].text.split()[0])
            if dmg < 5:
                damage_done += 1
            elif dmg <= 1000:
                damage_done += 5
            else:
                damage_done += int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
            update += 1
            await sleep(uniform(0.3, 0.55))

            if update % 4 == 0:
                # dmg update every 4 berserks.
                output += f"\n{hits_or_dmg.title()} done so far: {damage_done:,}"
                await msg.edit(content=output)
        await msg.edit(content=output)
        await ctx.send(f"**{nick}** Done {damage_done:,} {hits_or_dmg}, reminding limits: {food_limit}/{gift_limit}")
        await utils.update_info(server, nick, {"limits": f"{food_limit}/{gift_limit}"})
        self.bot.loop.create_task(utils.idle(self.bot, [link, base_url, base_url + "battles.html"]))
        return utils.should_break(ctx) or "ERROR" in output or damage_done == 0 or not any((food_limit, gift_limit)), medkits

    @command()
    async def friend(self, ctx, your_friend: str, *, nick: IsMyNick):
        """Adding a friend to your list.
        - You won't overbid your friends when using `.bid_all_auctions`
        - TODO: You should not steal BHs from your friends
        - TODO: You should not fight hard on `watch` when your friend is fighting.
        If the friend is already in the list, it will be removed."""
        server = ctx.channel.name
        your_friend = your_friend.lower()
        d = self.bot.friends
        if server not in d:
            d[server] = []

        if your_friend not in d[server]:
            d[server].append(your_friend)
            await ctx.send(f"**{nick}** added the nick {your_friend} to your friends list.\n"
                           f"Current list: {', '.join(d[server])}")
        else:
            d[server].remove(your_friend)
            await ctx.send(f"**{nick}** removed the nick {your_friend} from your friends list.\n"
                           f"Current list: {', '.join(d[server])}")
        await utils.replace_one("friends", "list", utils.my_nick(), d)

    @command(aliases=["ally"])
    async def enemy(self, ctx, country: Country, *, nick: IsMyNick):
        """Adding an ally/enemy to your list.
        The bot will spend more dmg while hunting for an ally, and less when hunting for enemies side.
        It will also give a little push to your allies and against your enemies.
        If the country is already in the list, it will be removed."""
        server = ctx.channel.name

        d = self.bot.allies if ctx.invoked_with.lower() == "ally" else self.bot.enemies
        if server not in d:
            d[server] = []

        if country not in d[server]:
            d[server].append(country)
            await ctx.send(f"**{nick}** added country id {country} to your {ctx.invoked_with} list.\n"
                           f"Current list: {', '.join(str(x) for x in d[server])}")
        else:
            d[server].remove(country)
            await ctx.send(f"**{nick}** removed country id {country} from your {ctx.invoked_with} list.\n"
                           f"Current list: {', '.join(str(x) for x in d[server])}")
        await utils.replace_one(ctx.invoked_with.lower().replace("y", "ies"), "list", utils.my_nick(), d)

    @command()
    async def hunt(self, ctx, nick: IsMyNick, max_dmg_for_bh: Dmg = 1, weapon_quality: Quality = 5, start_time: int = 60,
                   ticket_quality: Quality = 5, consume_first="none"):
        """Auto hunt BHs (attack and RWs).
        - You can set a list of enemies / allies and the bot will hit half / double for them, see `.help enemy`
        If `nick` contains more than 1 word - it must be within quotes.
        * `consume_first=none` means 1/1 (for fast servers)"""
        consume_first = consume_first.lower()
        if consume_first not in ("food", "gift", "none"):
            return await ctx.send(f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
        data = {"max_dmg_for_bh": max_dmg_for_bh, "weapon_quality": weapon_quality, "start_time": start_time,
                "ticket_quality": ticket_quality, "consume_first": consume_first}
        ctx.command = f"hunt-{ctx.message.id}"
        await utils.save_command(ctx, "auto", "hunt", data)
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        await ctx.send(f"**{nick}** Starting to hunt at {server}.\n"
                       f"If you want me to stop, type `.cancel hunt-{ctx.message.id} {nick}`")
        avg_hit = 0
        if max_dmg_for_bh == 1:
            try:
                api = await self.bot.get_content(base_url + 'apiCitizenByName.html?name=' + nick.lower())
                tree = await self.bot.get_content(f"{base_url}profile.html?id={api['id']}", return_tree=True)
                avg_hit = float(tree.xpath("//*[@id='hitHelp']/text()")[0].strip().split("-")[-1].replace(",", ""))
            except:
                pass
        should_break = False
        while not should_break:
            battles_time = {}
            for battle in await utils.get_battles(self.bot, base_url):
                round_ends = battle["time_reminding"].split(":")
                battles_time[battle["battle_id"]] = int(round_ends[0]) * 3600 + int(round_ends[1]) * 60 + int(round_ends[2])

            for battle_id, round_ends in sorted(battles_time.items(), key=lambda x: x[1]):
                api_battles = await self.bot.get_content(f'{base_url}apiBattles.html?battleId={battle_id}')
                if api_battles['currentRound'] == 1 and server not in ("secura", "suna", "primera"):
                    break  # first round is longer in some servers
                t = api_battles["hoursRemaining"] * 3600 + api_battles["minutesRemaining"] * 60 + api_battles[
                    "secondsRemaining"]
                if t > round_ends:  # some error
                    break
                if api_battles['frozen'] or t < 10:
                    continue
                if t > start_time:
                    till_next = t - start_time + uniform(-5, 5)
                    await ctx.send(f"**{nick}** Time until <{base_url}battle.html?id={battle_id}&round="
                                   f"{api_battles['currentRound']}>: {timedelta(seconds=round(till_next))}")
                    await sleep(till_next)
                if utils.should_break(ctx):
                    should_break = True
                    break

                defender, attacker = {}, {}
                for hit_record in await self.bot.get_content(
                        f'{base_url}apiFights.html?battleId={battle_id}&roundId={api_battles["currentRound"]}'):
                    side = defender if hit_record['defenderSide'] else attacker
                    if hit_record['citizenId'] in side:
                        side[hit_record['citizenId']] += hit_record['damage']
                    else:
                        side[hit_record['citizenId']] = hit_record['damage']

                a_dmg = sorted(attacker.items(), key=lambda x: x[1], reverse=True)[0][1] if attacker else 0
                d_dmg = sorted(defender.items(), key=lambda x: x[1], reverse=True)[0][1] if defender else 0

                enemies, allies = self.bot.enemies.get(server, []), self.bot.allies.get(server, [])
                max_a_dmg = max_d_dmg = max_dmg_for_bh
                # give a little push to your ally or against your enemy
                if api_battles["defenderId"] in enemies or api_battles["attackerId"] in allies:
                    if api_battles["defenderId"] in enemies:
                        max_d_dmg //= 2
                    if api_battles["attackerId"] in allies:
                        max_a_dmg *= 2
                        a_dmg += 1
                    enemy_dmg, ally_dmg = sum(defender.values()), sum(attacker.values())
                    if 0 <= enemy_dmg - ally_dmg <= max_dmg_for_bh and a_dmg > max_a_dmg:
                        a_dmg = enemy_dmg - ally_dmg

                elif api_battles["attackerId"] in enemies or api_battles["defenderId"] in allies:
                    if api_battles["attackerId"] in enemies:
                        max_a_dmg //= 2
                    if api_battles["defenderId"] in allies:
                        max_d_dmg *= 2
                        d_dmg += 1
                    enemy_dmg, ally_dmg = sum(attacker.values()), sum(defender.values())
                    if 0 <= enemy_dmg - ally_dmg <= max_dmg_for_bh and d_dmg > max_d_dmg:
                        d_dmg = enemy_dmg - ally_dmg

                if a_dmg < max(max_a_dmg, avg_hit):
                    if 10 < a_dmg < 1000:
                        a_dmg = 1000
                    should_break, _ = await ctx.invoke(self.bot.get_command("fight"), nick, battle_id, "attacker",
                                                       weapon_quality, 1 if a_dmg < avg_hit else (a_dmg+1), ticket_quality, consume_first, 0)
                if d_dmg < max(max_d_dmg, avg_hit):
                    if 10 < d_dmg < 1000:
                        d_dmg = 1000
                    should_break, _ = await ctx.invoke(self.bot.get_command("fight"), nick, battle_id, "defender",
                                                       weapon_quality, 1 if d_dmg < avg_hit else (d_dmg+1), ticket_quality, consume_first, 0)
                if should_break:
                    break
            await sleep(30)

        await utils.remove_command(ctx, "auto", "hunt")

    @command()
    async def duel(self, ctx, nick: IsMyNick, link, max_hits_per_round: Dmg = 100, weapon_quality: Quality = 0,
                   food: Quality = 0, gift: Quality = 0, start_time: int = 0,
                   chance_for_sleep: int = 3, sleep_duration: int = 7, chance_for_nap: int = 27):
        """Auto register and fights in duel tournament.
        By default, every ~33 duels (100/3), it will skip 5-9 hours (7+-2).
        It will also skip ~27% from the rest of the duels.

        * start_time=0 means random.
        """
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        if "duelTournament" not in link:
            return await ctx.send("Not a duel link")
        await ctx.send(f"**{nick}** If you want to cancel it, type `.cancel duel {nick}`")
        while not utils.should_break(ctx):
            ctx.command = f"duel-{ctx.message.id}"
            if uniform(0, 100) < chance_for_sleep:
                rand = uniform(sleep_duration-2, sleep_duration+2)*2
                await ctx.send(f"**{nick}** Sleeping for {timedelta(seconds=round(rand*30*60))}h")
                await sleep(rand*30*60)
            elif uniform(0, 100) < chance_for_nap:
                rand = uniform(1, 2)
                await ctx.send(f"**{nick}** Sleeping for {timedelta(seconds=round(rand*30*60))}h")
                await sleep(rand*30*60)
            else:
                if utils.should_break(ctx):
                    break
                url = await self.bot.get_content(link, data={"action": "ENLIST"})
                if not url.endswith("BATTLE_IN_PROGRESS"):
                    await ctx.send(f'**{nick}** <{url}>\nYou can cancel with: `.cancel duel-{ctx.message.id} {nick}` or ' +
                                   f'`.click "{nick}" {link} ' + '{"action": "CANCEL_ENLIST"}`')

                    tree = await self.bot.get_content(link.replace("duelTournament.html", "duelTournamentSchedules.html"), return_tree=True)
                    starts_in = tree.xpath("//tr[2]//td[2]//span[1]/text()")[0].replace("Starts: ", "")
                    now = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%H:%M:%S %d-%m-%Y")
                    seconds = (datetime.strptime(starts_in, "%H:%M %d-%m-%Y") - datetime.strptime(now, "%H:%M:%S %d-%m-%Y")).total_seconds()
                    if seconds < 0:
                        await ctx.send(f"**{nick}** {link} is over")
                        break
                    await ctx.send(f"**{nick}** Round starts in {timedelta(seconds=seconds)}")
                    await sleep(seconds+uniform(60, 80))
                if utils.should_break(ctx):
                    break
                tree = await self.bot.get_content(link, return_tree=True)
                my_id = utils.get_ids_from_path(tree, '//*[@id="userName"]')[0]
                attacker, battle, defender = tree.xpath("//*[@class='highlighted']//@href")[:3]
                side = "attacker" if attacker.endswith(f"={my_id}") else "defender"
                await ctx.invoke(self.bot.get_command("hunt_battle"), nick, base_url+battle, side, max_hits_per_round,
                                 weapon_quality, food, gift, start_time)

    @command()
    async def hunt_battle(self, ctx, nick: IsMyNick, battle: Id, side: Side, dmg_or_hits_per_bh: Dmg = 1,
                          weapon_quality: Quality = 0, food: Quality = 5, gift: Quality = 5, start_time: int = 0):
        """Hunting BH at a specific battle.
        (Good for practice battle / leagues / civil war)

        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        If `nick` contains more than 1 word - it must be within quotes."""

        data = {"link": battle, "side": side, "dmg_or_hits_per_bh": dmg_or_hits_per_bh,
                "weapon_quality": weapon_quality, "food": food, "gift": gift, "start_time": start_time}

        ctx.command = f"hunt_battle-{ctx.message.id}"
        await utils.save_command(ctx, "auto", "hunt_battle", data)

        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        link = f"{base_url}battle.html?id={battle}" if not str(battle).startswith("http") else battle
        dmg = dmg_or_hits_per_bh
        hits_or_dmg = "hits" if dmg <= 1000 else "dmg"
        while not utils.should_break(ctx):  # For each round
            api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
            if 8 in (api['defenderScore'], api['attackerScore']):
                await ctx.send(f"**{nick}** <{link}> is over")
                break
            seconds_till_round_end = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
            if seconds_till_round_end < 20:
                await sleep(30)
                continue
            seconds_till_hit = uniform(10, seconds_till_round_end - 10) if start_time < 10 else (
                    seconds_till_round_end - start_time + uniform(-5, 5))
            await ctx.send(f"**{nick}** {round(seconds_till_hit)} seconds from now (at T {timedelta(seconds=round(seconds_till_round_end-seconds_till_hit))}),"
                           f" I will hit {dmg} {hits_or_dmg} at <{link}> for the {side} side.\n"
                           f"If you want to cancel it, type `.cancel hunt_battle-{ctx.message.id} {nick}`")
            await sleep(seconds_till_hit)
            tree = await self.bot.get_content(link, return_tree=True)
            top = tree.xpath(f'//*[@id="top{side}1"]//div[3]/text()')
            if dmg_or_hits_per_bh == 1 and top and int(str(top[0]).replace(",", "").strip()) != 0:
                await ctx.send(f"**{nick}** someone else already fought in this round <{link}>")
                await sleep(seconds_till_round_end - seconds_till_hit + 15)
                continue
            food_limit, gift_limit = utils.get_limits(tree)
            food_storage, gift_storage = utils.get_storage(tree)
            damage_done = 0
            fight_url, data = await self.get_fight_data(base_url, tree, weapon_quality, side, value=("Berserk" if dmg >= 5 else ""))
            while damage_done < dmg and not utils.should_break(ctx):
                health = tree.xpath('//*[@id="actualHealth"]/text()') or tree.xpath("//*[@id='healthUpdate']/text()")
                if health:
                    health = float(health[0].split()[0])
                else:
                    tree = await self.bot.get_content(link, return_tree=True)
                    health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)
                    if not any([health, food, gift]):
                        break
                restore_needed = (dmg < 5 and health == 0) or (dmg >= 5 and health < 50)
                if not (food or gift) and restore_needed:
                    break
                if (food or gift) and restore_needed:
                    if (food and food_storage == 0) and (gift and gift_storage == 0):
                        return await ctx.send(f"**{nick}** ERROR: food/gift storage error")
                    if (food and food_limit == 0) and (gift and gift_limit == 0):
                        return await ctx.send(f"**{nick}** ERROR: food/gift limits error")
                    if food and food_storage > 0 and food_limit > 0:
                        food_storage -= 1
                        food_limit -= 1
                        await self.bot.get_content(f"{base_url}eat.html", data={'quality': 5})
                    elif gift and gift_storage > 0 and gift_limit > 0:
                        gift_storage -= 1
                        gift_limit -= 1
                        await self.bot.get_content(f"{base_url}gift.html", data={'quality': 5})
                    else:
                        return await ctx.send(f"**{nick}** ERROR: I couldn't restore health.")
                    health += 50

                tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
                if not tree.xpath('//*[@id="DamageDone"]'):
                    if "Slow down a bit!" in tree.text_content():
                        await sleep(1)
                        continue
                    if "No health left" in tree.text_content():
                        continue
                    if "Round is closed" in tree.text_content():
                        break
                    res = tree.xpath('//div//div/text()')
                    await ctx.send(f"**{nick}** ERROR: {' '.join(res).strip()}")
                    break
                if dmg < 5:
                    damage_done += 1
                elif dmg <= 1000:
                    damage_done += 5
                else:
                    damage_done += int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
                await sleep(uniform(0, 2))

            await ctx.send(f"**{nick}** done {damage_done:,} {hits_or_dmg} at <{link}>")
            if not utils.should_break(ctx):
                await sleep(seconds_till_round_end - seconds_till_hit + 15)

        await utils.remove_command(ctx, "auto", "hunt_battle")

    @command()
    async def auto_motivate(self, ctx, chance_to_skip_a_day: Optional[int] = 5, *, nick: IsMyNick):
        """Motivates at random times throughout every day"""
        await utils.save_command(ctx, "auto", "motivate", {"chance_to_skip_a_day": chance_to_skip_a_day})

        await ctx.send(f"**{nick}** Starting to motivate every day with {chance_to_skip_a_day}% chance to skip a day.\n"
                       f"Cancel with `.cancel auto_motivate {nick}`")

        while not utils.should_break(ctx):  # for every day:
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
            sec_til_midnight = (midnight - now).seconds
            await sleep(uniform(0, sec_til_midnight - 600))
            if not utils.should_break(ctx) and randint(1, 100) > chance_to_skip_a_day:
                await ctx.invoke(self.bot.get_command("motivate"), nick=nick)

            # sleep till midnight
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
            await sleep((midnight - now).seconds + 20)

            data = (await utils.find_one("auto", "motivate", os.environ['nick']))[ctx.channel.name]
            if isinstance(data, list):
                data = data[0]
            chance_to_skip_a_day = data["chance_to_skip_a_day"]
        await utils.remove_command(ctx, "auto", "motivate")

    @command()
    async def motivate(self, ctx, *, nick: IsMyNick):
        """
        Send motivates.
        * checking first 200 new citizens only.
        * If you do not have Q3 food / Q3 gift / Q1 weps when it starts - it will try to take some from your MU storage.
        """
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"

        def get_storage(tree):
            products = utils.get_products(tree)

            storage = {}
            if products.get("Q1 Weapon", 0) >= 15:
                storage["Q1 wep"] = 1

            if products.get("Q3 Food", 0) >= 10:
                storage["Q3 food"] = 2

            if products.get("Q3 Gift", 0) >= 5:
                storage["Q3 gift"] = 3
            return storage

        tree = await self.bot.get_content(base_url + 'storage.html?storageType=PRODUCT', return_tree=True)
        storage = get_storage(tree)
        if not storage:
            data = [(randint(3, 15)*5, "1", "WEAPON"), (randint(1, 7)*5, "3", "FOOD"), (randint(1, 5)*5, "3", "GIFT")]
            shuffle(data)
            for entry in data:
                await ctx.invoke(self.bot.get_command("supply"), entry[0], entry[1], entry[2], nick=nick)
                await sleep(1, 4)
            tree = await self.bot.get_content(base_url + 'storage.html?storageType=PRODUCT', return_tree=True)
            storage = get_storage(tree)
        if not storage:
            return await ctx.send(f"**{nick}** ERROR: There is not enough Q1 wep / Q3 food / Q3 gift")
        for k in ("Q1 wep", "Q3 food", "Q3 gift"):
            if k not in storage:
                await ctx.send(f"**{nick}** WARNING: There are not enough {k}s in storage")
        new_citizens_tree = await self.bot.get_content(base_url + 'newCitizens.html?countryId=0', return_tree=True)
        citizen_id = int(utils.get_ids_from_path(new_citizens_tree, "//tr[2]//td[1]/a")[0])
        checking = []
        sent_count = 0
        errors = 0
        while not utils.should_break(ctx):
            try:
                if sent_count == 5:
                    await ctx.send(f"**{nick}**\n" + "\n".join(checking) + "\n- Successfully motivated 5 players.")
                    break
                tree = await self.bot.get_content(f'{base_url}profile.html?id={citizen_id}', return_tree=True)
                today = int(tree.xpath('//*[@class="sidebar-clock"]//b/text()')[-1].split()[-1])
                birthday = int(
                    tree.xpath('//*[@class="profile-row" and span = "Birthday"]/span/text()')[0].split()[-1])
                if today - birthday > 3:
                    await ctx.send(f"**{nick}** Checked all new players")
                    break
                checking.append(f"Checking <{base_url}profile.html?id={citizen_id}>")
                if tree.xpath('//*[@id="motivateCitizenButton"]'):
                    for num in storage.values():
                        payload = {'type': num, "submit": "Motivate", "id": citizen_id}
                        tree, url = await self.bot.get_content(f"{base_url}motivateCitizen.html?id={citizen_id}", data=payload, return_tree="both")
                        if "&actionStatus=SUCCESFULLY_MOTIVATED" in url:
                            checking.append(f"<{url}>")
                            sent_count += 1
                            break
                        msg = ' '.join(tree.xpath("//div[2]/text()")).strip()
                        if "too many" in msg:
                            return await ctx.send(f"**{nick}** You have sent too many motivations today!")
                citizen_id -= 1
            except Exception as exc:
                await ctx.send(f"**{nick}** ERROR: {exc}")
                errors += 1
                if errors == 5:
                    break
            if citizen_id % 10 == 0 and checking:
                await ctx.send(f"**{nick}**\n" + "\n".join(checking))
                checking.clear()

        food_limit, gift_limit = utils.get_limits(tree)
        await utils.update_info(server, nick, {"limits": f"{food_limit}/{gift_limit}"})

    @command(aliases=["dow", "mpp"])
    async def attack(self, ctx, country_or_region_id: Id, delay: Optional[int] = 0, *, nick: IsMyNick):
        """
        Attack region / Declare war / Propose MPP
        Possible after a given delay.
        """
        action = ctx.invoked_with.lower()
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if delay:
            await ctx.send(f"**{nick}** Ok. Sleeping for {delay} seconds. You can cancel with `.cancel {ctx.command} {nick}`")
            await sleep(delay)
            if utils.should_break(ctx):
                return

        if action == "attack":
            payload = {'action': "ATTACK_REGION", 'regionId': country_or_region_id, 'submit': "Attack"}
        elif action == "mpp":
            payload = {'action': "PROPOSE_ALLIANCE", 'countryId': country_or_region_id, 'submit': "Propose alliance"}
        elif action == "dow":
            payload = {'action': "DECLARE_WAR", 'dowCountryId': country_or_region_id, 'submit': "Declare war"}
        else:
            return

        url = await self.bot.get_content(base_url + "countryLaws.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def medkit(self, ctx, *, nick: IsMyNick):
        """Using a medkit"""
        server = ctx.channel.name
        url = await self.bot.get_content(f"https://{server}.e-sim.org/medkit.html", data={})
        await ctx.send(f"**{nick}** <{url}>")
        if url.endswith("MESSAGE_OK"):  # update db
            data = await utils.find_one(server, "info", nick)
            medkits = int(data.get("medkits", 0))
            data["medkits"] = str(medkits - 1)
            await utils.replace_one(server, "info", nick, data)

    @command(aliases=["upgrade"])
    async def reshuffle(self, ctx, eq_id_or_link: Id, parameter, *, nick: IsMyNick):
        """
        Reshuffle/upgrade a specific parameter.
        Parameter example: Increase chance to avoid damage by 7.08%
        If it's not working, you can try writing "first", "second" or "last" as a parameter.
        (you can also try "avoid", but sometimes there may be unexpected behavior)

        it's recommended to copy and paste the parameter, but you can also write first/last
        """
        action = ctx.invoked_with
        if action.lower() not in ("reshuffle", "upgrade"):
            return await ctx.send(f"**{nick}** ERROR: 'action' parameter can be reshuffle/upgrade only (not {action})")
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"

        link = f"{base_url}showEquipment.html?id={eq_id_or_link}"
        tree = await self.bot.get_content(link, return_tree=True)
        eq = tree.xpath('//*[@id="esim-layout"]//div/div[3]/div/h4/text()')
        parameter_id = tree.xpath('//*[@id="esim-layout"]//div/div[3]/div/h3/text()')
        parameter = parameter.lower()
        if parameter in eq[0].replace("by  ", "by ").lower() or parameter == "first":
            parameter_id = parameter_id[0].split("#")[1]
        elif parameter in eq[1].replace("by  ", "by ").lower() or parameter == "second":
            parameter_id = parameter_id[1].split("#")[1]
        elif parameter in eq[-1].replace("by  ", "by ").lower() or parameter in ("last", "third"):
            parameter_id = parameter_id[-1].split("#")[1]
        else:
            return await ctx.send(
                f"**{nick}** ERROR: I did not find the parameter {parameter} at <{link}>. Try copy & paste.")
        payload = {'parameterId': parameter_id, 'action': f"{action.upper()}_PARAMETER", "submit": action.capitalize()}
        url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
        if not url.endswith("SPLIT_ITEM_OK"):
            return await ctx.send(f"**{nick}** <{url}>")
        api_link = f"{base_url}apiEquipmentById.html?id={eq_id_or_link}"
        api = await self.bot.get_content(api_link)
        embed = Embed(url=link, title=f"{nick} Q{api['EqInfo'][0]['quality']} {api['EqInfo'][0]['slot'].title()}")
        embed.add_field(name="Parameters:", value="\n".join(
            f"**{x['Name']}:** {round(x['Value'], 3)}" for x in api['Parameters']))
        await ctx.send(embed=embed)

    @command()
    async def rw(self, ctx, region_id_or_link: Id, ticket_quality: Optional[int] = 5, delay: Optional[int] = 0, *, nick: IsMyNick):
        """Opens RW (Resistance War).
        `delay` means how many seconds the bot should wait before opening the RW.
        Note: region can be link or id."""
        if delay > 0:
            await ctx.send(f"**{nick}** Ok. If you changed your mind, type `.cancel rw {nick}`")
            await sleep(delay)
        if not utils.should_break(ctx):
            base_url = f"https://{ctx.channel.name}.e-sim.org/"
            region_link = f"{base_url}region.html?id={region_id_or_link}"
            if not await ctx.invoke(self.bot.get_command("fly"), region_id_or_link, ticket_quality, nick=nick):
                return
            tree = await self.bot.get_content(region_link, data={"submit": "Start resistance"}, return_tree=True)
            result = tree.xpath("//*[@id='esim-layout']//div[2]/text()")[0]
            await ctx.send(f"**{nick}** {result}")

    @command()
    async def pack(self, ctx, nick: IsMyNick, wep_quality: Quality, weps: int = 200, food: int = 15, gift: int = 15,
                   tickets_quality: Quality = 0, tickets: int = 0):
        """Sends a pack of supply from your MU.
        Examples:
            .pack "my nick" Q1                    (it will send the default amounts: 15/15 and 200 Q1 weps)
            .pack "my nick" Q5 150 20 15 Q1 20    (it will send: 20/15 food/gift, 150 Q5 weps, 20 Q1 tickets)
        """
        data = [(food, 5, "FOOD"), (gift, 5, "GIFT"), (weps, wep_quality, "WEAPON"), (tickets, tickets_quality, "TICKET")]
        shuffle(data)
        for entry in data:
            if entry[0] and entry[1]:
                await ctx.invoke(self.bot.get_command("supply"), entry[0], entry[1], entry[2], nick=nick)
                await sleep(uniform(1, 5))

    @command()
    async def supply(self, ctx, amount: int, quality: Optional[Quality], product: Product, *, nick: IsMyNick):
        """Taking a specific product from MU storage."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(base_url + "militaryUnitStorage.html", return_tree=True)
        my_id = utils.get_ids_from_path(tree, '//*[@id="userName"]')[0]
        payload = {'product': f"{quality or 5}-{product}", 'quantity': amount,
                   "reason": "", "citizen1": my_id, "submit": "Donate"}
        url = await self.bot.get_content(base_url + "militaryUnitStorage.html", data=payload)
        if "index" in url:
            await ctx.send(f"**{nick}** You are not in any military unit.")
        else:
            await ctx.send(f"**{nick}** {amount} Q{payload['product']} <{url}>")

    @command(aliases=["gift"])
    async def food(self, ctx, quality: Optional[int] = 5, *, nick: IsMyNick):
        """Using food or gift"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        url = await self.bot.get_content(f"{base_url}{ctx.invoked_with.lower().replace('food', 'eat')}.html", data={'quality': quality})
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def watch(self, ctx, nick: IsMyNick, battle: Id, side: Side, start_time: int = 60,
                    keep_wall: Dmg = 3000000, let_overkill: Dmg = 10000000, weapon_quality: Quality = 5,
                    ticket_quality: Quality = 5, consume_first="gift", medkits: int = 0):
        """Fight at the last minutes of every round in a given battle.

        Examples:
        .watch https://alpha.e-sim.org/battle.html?id=1 defender
        In this example, it will start fighting at t1, and will try to keep a default 3kk wall (checking every ~10 sec),
        and if enemies did more than 10kk it will skip the round.

        If link="https://alpha.e-sim.org/battle.html?id=1", side="defender", start_time=120, keep_wall="5kk", let_overkill="15kk"
        it will start fighting at ~t2 (120+-5 secs), it will keep a 5kk wall (checking every ~10 sec),
        and if enemies did more than 15kk it will skip the round.

        * It will increase the wall for every fighting enemy, to compensate for the delay.
        * If `nick` contains more than 1 word - it must be within quotes.
        """
        consume_first = consume_first.lower()
        if consume_first not in ("food", "gift", "none"):
            return await ctx.send(f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
        data = {"battle": battle, "side": side, "start_time": start_time, "keep_wall": keep_wall,
                "let_overkill": let_overkill, "weapon_quality": weapon_quality, "ticket_quality": ticket_quality,
                "consume_first": consume_first, "medkits": medkits}
        ctx.command = f"watch-{ctx.message.id}"
        await utils.save_command(ctx, "auto", "watch", data)

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api_citizen = await self.bot.get_content(f'{base_url}apiCitizenByName.html?name={nick.lower()}')
        battle_link = f"{base_url}battle.html?id={battle}"
        error = False
        while not error:
            ctx.invoked_with = "watch"
            r = await self.bot.get_content(battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
            if 8 in (r['defenderScore'], r['attackerScore']):
                break
            sleep_time = r["hoursRemaining"] * 3600 + r["minutesRemaining"] * 60 + r["secondsRemaining"] - start_time + uniform(-5, 5)
            if sleep_time > 0:
                await ctx.send(f"**{nick}** Sleeping for {round(sleep_time)} seconds :zzz:"
                               f"\nIf you want me to stop, type `.cancel watch-{ctx.message.id} {nick}`")
                await sleep(sleep_time)
            if utils.should_break(ctx):
                break
            await ctx.send(f"**{nick}** T{round(start_time / 60, 1)} at <{battle_link}&round={r['currentRound']}>")
            tree = await self.bot.get_content(battle_link, return_tree=True)
            hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value

            while not error:
                battle_score = await self.bot.get_content(
                    f'{base_url}battleScore.html?id={hidden_id}&at={api_citizen["id"]}&ci={api_citizen["citizenshipId"]}&premium=1')
                if battle_score["remainingTimeInSeconds"] <= 0:
                    break
                my_side = int(battle_score[f"{side}Score"].replace(",", ""))
                enemy = "defender" if side == "attacker" else "attacker"
                enemy_side = int(battle_score[enemy + "Score"].replace(",", ""))
                wall = keep_wall * (battle_score[f"{enemy}sOnline"] + 1) if battle_score["spectatorsOnline"] != 1 else 1
                if enemy_side - my_side < let_overkill and my_side - enemy_side < wall:
                    error, medkits = await ctx.invoke(self.bot.get_command("fight"), nick, battle, side, weapon_quality,
                                                      max(enemy_side - my_side + wall, 10001), ticket_quality, consume_first, medkits)
                    ctx.invoked_with = "fight_fast"
                await sleep(uniform(6, 13))

            await utils.idle(self.bot, [battle_link, base_url, base_url+"battles.html"])

        await utils.remove_command(ctx, "auto", "watch")

    @command(aliases=["unwear"])
    async def wear(self, ctx, ids, *, nick: IsMyNick):
        """
        Wear/take off a specific EQ IDs.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        ids = [int(x.replace("#", "").replace(f"{base_url}showEquipment.html?id=", "").strip()) for x in ids.split(",") if x.strip()]
        for eq_id in ids:
            if utils.should_break(ctx):
                break
            payload = {'action': "PUT_OFF" if ctx.invoked_with.lower() == "unwear" else "EQUIP", 'itemId': eq_id}
            url = await self.bot.get_content(f"{base_url}equipmentAction.html", data=payload)
            await sleep(uniform(1, 2))
            if url == "http://www.google.com/":
                # e-sim error
                await sleep(uniform(2, 5))
            results.append(f"ID {eq_id} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))

    @command()
    async def hunt_events(self, ctx, nick: IsMyNick, dmg_or_hits_per_bh: Dmg = 1,
                          weapon_quality: Quality = 0, food: Quality = 5, gift: Quality = 5, start_time: int = 0):
        """Checks every ~10 minutes if there's a new event battle, and start hunt_battle on it."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api_citizen = await self.bot.get_content(f'{base_url}apiCitizenByName.html?name={nick.lower()}')
        my_citizenship_id = api_citizen["citizenshipId"]
        my_citizenship = api_citizen["citizenship"]
        await ctx.send(f"**{nick}** Ok. You can cancel with `.cancel hunt_events {nick}`")
        added_battles = []
        while not utils.should_break(ctx):
            try:
                battles = await utils.get_battles(self.bot, base_url, country_id=my_citizenship_id, normal_battles=False)
            except:
                battles = []
            for battle in battles:
                if my_citizenship.lower() == battle["defender"]["name"].lower():
                    side = "defender"
                elif my_citizenship.lower() == battle["attacker"]["name"].lower():
                    side = "attacker"
                else:
                    continue
                battle_id = battle["battle_id"]
                if battle_id not in added_battles:
                    added_battles.append(battle_id)
                    self.bot.loop.create_task(ctx.invoke(
                        self.bot.get_command("hunt_battle"), nick, battle_id, side, dmg_or_hits_per_bh,
                        weapon_quality, food, gift, start_time))
            await sleep(uniform(500, 700))


def setup(bot):
    """setup"""
    bot.add_cog(War(bot))
