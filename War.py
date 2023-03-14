"""War.py"""
import os
import re
import time
from asyncio import sleep
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from random import randint, uniform
from typing import Optional

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
    async def auto_fight(self, ctx, nicks, restores: int = 100, battle_id: Id = 0,
                         side: Side = "attacker", wep: Quality = 0, food: Quality = 5, gift: Quality = 0, ticket_quality: Quality = 5,
                         chance_to_skip_restore: int = 15):
        """Dumping health at a random time every restore

        If `nick` contains more than 1 word - it must be within quotes.
        If you want to skip a parameter, you should write the default value.
        Example: `.add "My Nick" 100 0 attacker 0 5` - write 0 to `battle_id` in order to change `food`"""

        async for nick in utils.get_nicks(ctx.channel.name, nicks):
            data = {"restores": restores, "battle_id": battle_id, "side": side, "wep": wep, "food": food,
                    "gift": gift, "ticket_quality": ticket_quality, "chance_to_skip_restore": chance_to_skip_restore}
            random_id = randint(1, 9999)
            ctx.command = f"{ctx.command}-{random_id}"
            if await utils.save_command(ctx, "auto", "fight", data):
                return  # Command already running

            server = ctx.channel.name
            base_url = f"https://{server}.e-sim.org/"
            specific_battle = (battle_id != 0)
            await ctx.send(f"**{nick}** Ok sir! If you want to stop it, type `.cancel auto_fight-{random_id} {nick}`")

            if specific_battle and 1 <= ticket_quality <= 5:
                api_battles = await self.bot.get_content(f"{base_url}apiBattles.html?battleId={battle_id}")
                bonus_region = await utils.get_bonus_region(self.bot, base_url, side, api_battles)
                if bonus_region:
                    if not await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick):
                        restores = 0

            while restores > 0 and not self.bot.should_break(ctx):
                restores -= 1
                if randint(1, 100) <= chance_to_skip_restore:
                    await sleep(600)

                # update data from db
                d = (await utils.find_one("auto", "fight", os.environ['nick']))[server]
                restores, battle_id, side, wep, food = d["restores"], d["battle_id"], d["side"], d["wep"], d["food"]
                gift, ticket_quality, chance_to_skip_restore = d["gift"], d["ticket_quality"], d["chance_to_skip_restore"]

                if not battle_id:
                    battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)
                await ctx.send(f'**{nick}** <{base_url}battle.html?id={battle_id}> side: {side}\n'
                               f'If you want to stop it, type `.cancel auto_fight-{random_id} {nick}`')
                if not battle_id:
                    await ctx.send(
                        f"**{nick}** WARNING: I can't fight in any battle right now, but I will check again after the next restore")
                    await utils.random_sleep(restores)
                    continue
                tree = await self.bot.get_content(base_url + "home.html", return_tree=True)
                if tree.xpath('//*[@id="taskButtonWork"]//@href') and randint(1, 4) == 2:  # Don't work as soon as you can (suspicious)
                    current_loc = await utils.location(self.bot, nick, server)
                    await ctx.invoke(self.bot.get_command("work"), nicks=nick)
                    if not await ctx.invoke(self.bot.get_command("fly"), current_loc, ticket_quality, nick=nick):
                        break
                api_battles = await self.bot.get_content(f"{base_url}apiBattles.html?battleId={battle_id}")
                if 8 in (api_battles['attackerScore'], api_battles['defenderScore']):
                    if specific_battle:
                        await ctx.send(f"**{nick}** Battle has finished.")
                        break
                    await ctx.send(f"**{nick}** Searching for the next battle...")
                    battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)

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
    async def battle_order(self, ctx, battle: Id, side: Side, *, nick: IsMyNick):
        """
        Set battle order.
        You can use battle link/id.
        """
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'action': "SET_ORDERS",
                   'battleId': f"{battle}_{'true' if side == 'attacker' else 'false'}",
                   'submit': "Set orders"}
        url = await self.bot.get_content(base_url + "militaryUnitsActions.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["buff-"])
    async def buff(self, ctx, buffs_names, *, nick: IsMyNick):
        """Buy and use buffs.

        The buff names should be formal (can be found via F12), but here are some shortcuts:
        VAC = EXTRA_VACATIONS, SPA = EXTRA_SPA, SEWER = SEWER_GUIDE, STR = STEROIDS, PD 10 = PAIN_DEALER_10_H
        More examples: BANDAGE_SIZE_C and CAMOUFLAGE_II, MILI_JINXED_ELIXIR, MINI_BLOODY_MESS_ELIXIR

        * type `.buff-` if you don't want to buy the buff.

        Example: .buff  str,tank  my nick"""
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"

        results = []
        for buff_name in buffs_names.split(","):
            buff_name = buff_name.strip().upper().replace(" ", "_")
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
            elif any(x in buff_name for x in ("BLOODY_MESS", "FINESE", "JINXED", "LUCKY")):
                if not buff_name.endswith("_ELIXIR"):
                    buff_name += "_ELIXIR"

            actions = ("BUY", "USE") if ctx.invoked_with.lower() == "buff" else ("USE", )
            for action in actions:
                if self.bot.should_break(ctx):
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
                    data = await utils.find_one(server, "info", nick)
                    now = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%Y-%m-%d %H:%M:%S")
                    data["Buffed at"] = now
                    await utils.replace_one(server, "info", nick, data)
        await ctx.send(f"**{nick}**\n" + "\n".join(results))

    @command(aliases=["travel"])
    async def fly(self, ctx, region_id: Id, ticket_quality: Optional[int] = 5, *, nick: IsMyNick) -> bool:
        """traveling to a region"""
        if 1 <= ticket_quality <= 5:
            base_url = f"https://{ctx.channel.name}.e-sim.org/"
            tree = await self.bot.get_content(f"{base_url}region.html?id={region_id}", return_tree=True)
            country_id = tree.xpath('//*[@id="countryId"]/@value')
            tickets = tree.xpath('//*[@id="ticketQuality"]//@value')
            if not country_id:  # already in the location
                return True
            if str(ticket_quality) not in tickets:
                await ctx.send(f"**{nick}** there are 0 Q{ticket_quality} tickets in storage.")
                return False
            else:
                payload = {'countryId': country_id[0], 'regionId': region_id, 'ticketQuality': ticket_quality}
                url = await self.bot.get_content(f"{base_url}travel.html", data=payload)
                await sleep(uniform(0, 1))
                await ctx.send(f"**{nick}** <{url}>")
                return True
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

    @command()
    async def fight(self, ctx, nick: IsMyNick, battle: Id, side: Side, weapon_quality: Quality = 5,
                    dmg_or_hits: Dmg = 200, ticket_quality: Quality = 5, consume_first="gift", medkits: int = 0) -> (bool, int):
        """
        Dumping limits at a specific battle.

        Examples: (everything inside [] is optional with default values)
            .fight "my nick" https://primera.e-sim.org/battle.html?id=1 attacker
            .fight nick 1 a 5 1kk 5 none 1

        * It will auto fly to bonus region.
        * if dmg_or_hits < 10000 - it's hits, otherwise - dmg.
        * set `consume_first` to `none` if you want to consume `1/1` (fast servers)
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
            await ctx.send(f"**{nick}** ERROR: You are not logged in. Type `.limits {nick}` and try again.")
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
                 f"If you want me to stop, type `.hold {ctx.command} {nick}`"
        msg = await ctx.send(output)
        damage_done = 0
        update = 0
        fight_url, data = await self.get_fight_data(base_url, tree, weapon_quality, side, value=("Berserk" if dmg >= 5 else ""))
        hits_or_dmg = "hits" if dmg <= 10000 else "dmg"
        round_ends = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"]
        start = time.time()
        while not self.bot.should_break(ctx) and damage_done < dmg and (time.time() - start < round_ends):
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
                if food_storage == 0 or gift_storage == 0:
                    output += f"\nWARNING: 0 {'food' if food_storage == 0 else 'gift'} in storage"

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
            elif dmg <= 10000:
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
        return "ERROR" in output or damage_done == 0, medkits

    @command(aliases=["cancel"], hidden=True)
    async def hold(self, ctx, cmd, *, nicks):
        """Cancel command (it might take a while before it actually cancel)"""
        server = ctx.channel.name
        cmd = cmd.lower()
        async for nick in utils.get_nicks(server, nicks):
            if server not in self.bot.should_break_dict:
                self.bot.should_break_dict[server] = {}
            self.bot.should_break_dict[server][cmd] = True
            original = cmd
            if cmd in ("hunt", "hunt_battle", "watch"):
                cmd = "auto_" + cmd
            if "auto_" in cmd:
                data = await utils.find_one("auto", "_".join(cmd.split("_")[1:]), os.environ['nick'])
                if server in data and original in data[server]:
                    del data[server][original]
                    await utils.replace_one("auto", "_".join(cmd.split("_")[1:]), os.environ['nick'], data)

            await ctx.send(f"**{nick}** I have forwarded your instruction. (it might take a while until it actually cancel {cmd})")

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

        if country not in d:
            d[server].append(country)
            await ctx.send(f"**{nick}** added country id {country} to your {ctx.invoked_with} list.\n"
                           f"Current list: {', '.join(d[server])}")
        else:
            d[server].remove(country)
            await ctx.send(f"**{nick}** removed country id {country} from your {ctx.invoked_with} list.\n"
                           f"Current list: {', '.join(d[server])}")
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
        if await utils.save_command(ctx, "auto", "hunt", data):
            return  # Command already running
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        await ctx.send(f"**{nick}** Starting to hunt at {server}.\n"
                       f"If you want me to stop, type `.hold hunt {nick}`")
        should_break = False
        all_countries = [x["name"] for x in await self.bot.get_content(base_url + "apiCountries.html")]
        while not should_break:
            battles_time = {}
            for battle_filter in ("NORMAL", "RESISTANCE"):
                link = f'{base_url}battles.html?filter={battle_filter}'
                tree = await self.bot.get_content(link, return_tree=True)
                last_page = int((utils.get_ids_from_path(tree, "//ul[@id='pagination-digg']//li[last()-1]/") or ['1'])[0])
                for page in range(1, last_page+1):
                    if page > 1:
                        tree = await self.bot.get_content(link + f'&page={page}', return_tree=True)
                    battle_links = tree.xpath('//*[@class="battleHeader"]//a/@href')
                    sides = tree.xpath('//*[@class="battleHeader"]//em/text()')
                    counters = [i.split(");\n")[0] for i in
                                tree.xpath('//*[@id="battlesTable"]//div//div//script/text()') for i in
                                i.split("() + ")[1:]]
                    for round_ends, battle_link, sides in zip(await utils.chunker(counters, 3), battle_links, sides):
                        defender, attacker = sides.split(" vs ")
                        if attacker in all_countries and defender in all_countries:
                            battles_time[battle_link.split("=")[-1]] = int(
                                round_ends[0])*3600 + int(round_ends[1])*60 + int(round_ends[2])

            for battle_id, round_ends in sorted(battles_time.items(), key=lambda x: x[1]):
                api_battles = await self.bot.get_content(f'{base_url}apiBattles.html?battleId={battle_id}')
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
                if self.bot.should_break(ctx):
                    should_break = True
                    break
                # update data if needed
                d = (await utils.find_one("auto", "hunt", os.environ['nick']))[ctx.channel.name]
                max_dmg_for_bh, weapon_quality = d["max_dmg_for_bh"], d["weapon_quality"]
                start_time, ticket_quality, consume_first = d["start_time"], d["ticket_quality"], d["consume_first"]

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

                if a_dmg < max_a_dmg:
                    should_break, _ = await ctx.invoke(self.bot.get_command("fight"), nick, battle_id, "attacker",
                                                       weapon_quality, a_dmg+1, ticket_quality, consume_first, 0)
                if d_dmg < max_d_dmg:
                    should_break, _ = await ctx.invoke(self.bot.get_command("fight"), nick, battle_id, "defender",
                                                       weapon_quality, d_dmg+1, ticket_quality, consume_first, 0)
            await sleep(30)

        await utils.remove_command(ctx, "auto", "hunt")

    @command()
    async def hunt_battle(self, ctx, nick: IsMyNick, link, side: Side, dmg_or_hits_per_bh: Dmg = 1,
                          weapon_quality: Quality = 0, food: Quality = 5, gift: Quality = 5, start_time: int = 0):
        """Hunting BH at a specific battle.
        (Good for practice battle / leagues / civil war)

        * if dmg_or_hits < 10000 - it's hits, otherwise - dmg.
        If `nick` contains more than 1 word - it must be within quotes."""

        data = {"link": link, "side": side, "dmg_or_hits_per_bh": dmg_or_hits_per_bh,
                "weapon_quality": weapon_quality, "food": food, "gift": gift, "start_time": start_time}

        random_id = randint(1, 9999)
        ctx.command = f"{ctx.command}-{random_id}"
        await utils.save_command(ctx, "auto", "hunt_battle", data)

        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        dmg = dmg_or_hits_per_bh
        hits_or_dmg = "hits" if dmg <= 10000 else "dmg"
        while not self.bot.should_break(ctx):  # For each round
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
                           f"If you want to cancel it, type `.hold hunt_battle-{random_id} {nick}`")
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

            while damage_done < dmg and not self.bot.should_break(ctx):
                health = tree.xpath('//*[@id="actualHealth"]/text()') or tree.xpath("//*[@id='healthUpdate']/text()")
                if health:
                    health = float(health[0].split()[0])
                else:
                    tree = await self.bot.get_content(link, return_tree=True)
                    health = float(tree.xpath('//*[@id="actualHealth"]')[0].text)
                    if not any([health, food, gift]):
                        break

                if (dmg < 5 and health == 0) or (dmg >= 5 and health < 50):
                    if (not food or food_storage == 0) and (not gift or gift_storage == 0):
                        return await ctx.send(f"**{nick}** ERROR: food/gift storage error")
                    if (not food or food_limit == 0) and (not gift or gift_limit == 0):
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
                elif dmg <= 10000:
                    damage_done += 5
                else:
                    damage_done += int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
                await sleep(uniform(0, 2))

            await ctx.send(f"**{nick}** done {damage_done:,} {hits_or_dmg} at <{link}>")
            if not self.bot.should_break(ctx):
                await sleep(seconds_till_round_end - seconds_till_hit + 15)

        await utils.remove_command(ctx, "auto", "hunt_battle")

    @command()
    async def auto_motivate(self, ctx, chance_to_skip_a_day: Optional[int] = 7, *, nicks):
        """Motivates at random times throughout every day"""
        async for nick in utils.get_nicks(ctx.channel.name, nicks):
            if await utils.save_command(ctx, "auto", "motivate", {"chance_to_skip_a_day": chance_to_skip_a_day}):
                return  # Command already running

            while not self.bot.should_break(ctx):  # for every day:
                tz = timezone('Europe/Berlin')
                now = datetime.now(tz)
                midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
                sec_til_midnight = (midnight - now).seconds
                await sleep(uniform(0, sec_til_midnight - 600))
                if not self.bot.should_break(ctx) and randint(1, 100) > chance_to_skip_a_day:
                    await ctx.invoke(self.bot.get_command("motivate"), nick=nick)

                # sleep till midnight
                tz = timezone('Europe/Berlin')
                now = datetime.now(tz)
                midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
                await sleep((midnight - now).seconds + 20)

                data = (await utils.find_one("auto", "motivate", os.environ['nick']))[ctx.channel.name]
                chance_to_skip_a_day = data["chance_to_skip_a_day"]
            await utils.remove_command(ctx, "auto", "motivate")

    @command()
    async def motivate(self, ctx, *, nick: IsMyNick):
        """
        Send motivates.
        * checking first 200 new citizens only.
        * If you do not have Q3 food / Q3 gift / Q1 weps when it starts - it will try to take some from your MU storage.
        """
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        tree = await self.bot.get_content(base_url + 'storage.html?storageType=PRODUCT', return_tree=True)

        def get_storage(tree):
            food, gift = utils.get_storage(tree, 3)
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
                except Exception:
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
        while not self.bot.should_break(ctx):
            try:
                if sent_count == 5:
                    return await ctx.send(
                        f"**{nick}**\n" + "\n".join(checking) + "\n- Successfully motivated 5 players.")
                tree = await self.bot.get_content(f'{base_url}profile.html?id={citizen_id}', return_tree=True)
                today = int(tree.xpath('//*[@class="sidebar-clock"]//b/text()')[-1].split()[-1])
                birthday = int(
                    tree.xpath('//*[@class="profile-row" and span = "Birthday"]/span/text()')[0].split()[-1])
                if today - birthday > 3:
                    return await ctx.send(f"**{nick}** Checked all new players")
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
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
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
            url = await self.bot.get_content(base_url + "countryLaws.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def medkit(self, ctx, *, nick: IsMyNick):
        """Using a medkit"""
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
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        link = f"{base_url}showEquipment.html?id={eq_id_or_link}"
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
        url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def rw(self, ctx, region_id_or_link: Id, ticket_quality: Optional[int] = 5, *, nick: IsMyNick):
        """
        Open RW.
        Note: region can be link or id.
        * It will auto fly to that region."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        region_link = f"{base_url}region.html?id={region_id_or_link}"
        if not await ctx.invoke(self.bot.get_command("fly"), region_id_or_link, ticket_quality, nick=nick):
            return
        tree = await self.bot.get_content(region_link, data={"submit": "Start resistance"}, return_tree=True)
        result = tree.xpath("//*[@id='esim-layout']//div[2]/text()")[0]
        await ctx.send(f"**{nick}** {result}")

    @command()
    async def supply(self, ctx, amount: int, quality: Optional[Quality], product: Product, *, nick: IsMyNick):
        """Taking a specific product from MU storage."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(base_url + "militaryUnitStorage.html", return_tree=True)
        my_id = utils.get_ids_from_path(tree, '//*[@id="userName"]')[0]
        payload = {'product': f"{quality or 5}-{product}", 'quantity': amount,
                   "reason": " ", "citizen1": my_id, "submit": "Donate"}
        url = await self.bot.get_content(base_url + "militaryUnitStorage.html", data=payload)
        if "index" in url:
            await ctx.send(f"**{nick}** You are not in any military unit.")
        else:
            await ctx.send(f"**{nick}** <{url}>")

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
        """
        Fight at the last minutes of every round in a given battle.

        Examples:
        when link="https://alpha.e-sim.org/battle.html?id=1" and side="defender"
        In this example, it will start fighting at t1, it will keep a 3kk wall (checking every 10 sec),
        and if enemies did more than 10kk it will pass this round.
        (rest args have a default value)

        link="https://alpha.e-sim.org/battle.html?id=1", side="defender", start_time=120, keep_wall="5kk", let_overkill="15kk")
        In this example, it will start fighting at t2 (120+-5 secs), it will keep 5kk wall (checking every ~10 sec),
        and if enemies did more than 15kk it will skip this round.
        * It will auto fly to bonus region (with Q5 ticket)
        * If `nick` contains more than 1 word - it must be within quotes.
        """
        consume_first = consume_first.lower()
        if consume_first not in ("food", "gift", "none"):
            return await ctx.send(f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
        data = {"battle": battle, "side": side, "start_time": start_time, "keep_wall": keep_wall,
                "let_overkill": let_overkill, "weapon_quality": weapon_quality, "ticket_quality": ticket_quality,
                "consume_first": consume_first, "medkits": medkits}
        random_id = randint(1, 9999)
        ctx.command = f"{ctx.command}-{random_id}"
        await utils.save_command(ctx, "auto", "watch", data)

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api_citizen = await self.bot.get_content(f'{base_url}apiCitizenByName.html?name={nick.lower()}')
        battle_link = f"{base_url}battle.html?id={battle}"
        while not self.bot.should_break(ctx):
            r = await self.bot.get_content(battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
            if 8 in (r['defenderScore'], r['attackerScore']):
                break
            sleep_time = r["hoursRemaining"] * 3600 + r["minutesRemaining"] * 60 + r["secondsRemaining"] - start_time + uniform(-5, 5)
            if sleep_time > 0:
                await ctx.send(f"**{nick}** Sleeping for {round(sleep_time)} seconds :zzz:"
                               f"\nIf you want me to stop, type `.hold watch-{random_id} {nick}`")
                await sleep(sleep_time)
            if self.bot.should_break(ctx):
                break
            await ctx.send(f"**{nick}** T{round(start_time / 60, 1)} at <{battle_link}&round={r['currentRound']}>")
            tree = await self.bot.get_content(battle_link, return_tree=True)
            hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value
            error = False
            while not error and not self.bot.should_break(ctx):
                battle_score = await self.bot.get_content(
                    f'{base_url}battleScore.html?id={hidden_id}&at={api_citizen["id"]}&ci={api_citizen["citizenshipId"]}&premium=1',
                    return_type="json")
                if battle_score["remainingTimeInSeconds"] <= 0:
                    break
                wall = keep_wall if battle_score["spectatorsOnline"] != 1 else 1

                my_side = int(battle_score[f"{side}Score"].replace(",", ""))
                enemy_side = int(battle_score[("defender" if side == "attacker" else "attacker") + "Score"].replace(",", ""))
                if enemy_side - my_side < let_overkill and my_side - enemy_side < wall:
                    error, medkits = await ctx.invoke(self.bot.get_command("fight"), nick, battle, side, weapon_quality,
                                                    enemy_side - my_side + wall, ticket_quality, consume_first, medkits)
                await sleep(uniform(6, 13))

            await sleep(30)

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
            if self.bot.should_break(ctx):
                break
            payload = {'action': "PUT_OFF" if ctx.invoked_with.lower() == "unwear" else "EQUIP", 'itemId': eq_id}
            url = await self.bot.get_content(f"{base_url}equipmentAction.html", data=payload)
            await sleep(uniform(1, 2))
            if url == "http://www.google.com/":
                # e-sim error
                await sleep(uniform(2, 5))
            results.append(f"ID {eq_id} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))


def setup(bot):
    """setup"""
    bot.add_cog(War(bot))
