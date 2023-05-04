"""Info.py"""
from datetime import date, datetime, timedelta

from discord import Embed
from discord.ext.commands import Cog, check, command
from lxml.html import fromstring
from pytz import timezone

import utils
from Converters import Country, IsMyNick


class Info(Cog):
    """Info Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command(aliases=["version"], hidden=True)
    async def ping(self, ctx, *, nicks):
        """Shows the code version of the given nick(s).
        Can also use: .ping all"""
        server = ctx.channel.name
        async for nick in utils.get_nicks(server, nicks):
            if nick != utils.my_nick(server):
                nick = f"{nick} ({utils.my_nick(server)})"
            await ctx.send(f'**{nick}** Code Version: {self.bot.VERSION}')

    @command()
    async def eqs(self, ctx, *, nick: IsMyNick):
        """Shows the list of EQs in storage."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(base_url + 'storage.html?storageType=EQUIPMENT', return_tree=True)
        items = tree.xpath('//*[starts-with(@id, "cell")]/b/text()')
        original_ids = [ID.replace('#', '') for ID in tree.xpath('//*[starts-with(@id, "cell")]/a/text()')]
        parameters = [[utils.get_parameter(p) for p in tree.xpath(f'//*[@id="cell{ID}"]/text()')[3:]] for ID in original_ids]
        ids = [f"[{ID}]({base_url}showEquipment.html?id={ID})" for ID in original_ids]
        if sum(len(x) for x in ids) > 1000:
            # Eq id instead of link
            ids = original_ids
        length = 20
        if not ids:
            return await ctx.send(f"**{nick}** no eqs in storage.")
        embed = Embed(title=nick)
        embed.add_field(name="ID", value="\n".join(ids[:length]))
        embed.add_field(name="Item", value="\n".join(items[:length]))
        embed.add_field(name="Parameters", value="\n".join(", ".join(par_val[1] for par_val in eq) for eq in parameters[:length]))
        if len(ids) > length:
            embed.set_footer(text=f"({length} out of {len(ids)} items)")
        await ctx.send(embed=embed)

    @command(aliases=["inventory"])
    async def inv(self, ctx, *, nick: IsMyNick):
        """Shows your inventory."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        special = {}
        products = {}

        storage_tree = await self.bot.get_content(f"{base_url}storage.html?storageType=PRODUCT", return_tree=True)
        for item in storage_tree.xpath("//div[@class='storage']"):
            name = item.xpath("div[2]/img/@src")[0].replace("//cdn.e-sim.org//img/productIcons/", "").replace(
                "Rewards/", "").replace(".png", "")
            if name.lower() in ["iron", "grain", "diamonds", "oil", "stone", "wood"]:
                quality = ""
            else:
                quality = item.xpath("div[2]/img/@src")[1].replace(
                    "//cdn.e-sim.org//img/productIcons/", "").replace(".png", "")
            products[f"{quality.title()} {name}"] = item.xpath("div[1]/text()")[0].strip()

        money_tree = await self.bot.get_content(base_url + "storage.html?storageType=MONEY", return_tree=True)
        money = [x.strip() for x in money_tree.xpath("//*[@class='currencyDiv']//text()") if x.strip()]
        coins = dict(zip(money[1::2], money[0::2]))

        elixirs = {"jinxed": [""]*6, "finesse": [""]*6, "bloody": [""]*6, "lucky": [""]*6}
        tiers = ["Mili", "Mini", "Standard", "Major", "Huge", "Exceptional"]
        special_tree = await self.bot.get_content(f"{base_url}storage.html?storageType=SPECIAL_ITEM", return_tree=True)
        for item in special_tree.xpath('//div[@class="specialItemInventory"]'):
            if item.xpath('span/text()'):
                s_item = item.xpath('b/text()')[0]
                if "elixir" not in s_item:
                    special[s_item] = item.xpath('span/text()')[0]
                else:
                    s_item = s_item.replace(" elixir", "").split()
                    tier, elixir = s_item[0], s_item[1]
                    elixirs[elixir][tiers.index(tier)] = item.xpath('span/text()')[0].replace("x", "")

        embed = Embed(title=nick, description=money_tree.xpath('//div[@class="sidebar-money"][1]/b/text()')[0] + " Gold")
        for name, data in zip(("Products", "Coins", "Special Items"), (products, coins, special)):
            embed.add_field(name=f"**{name}:**", value="\n".join(f"**{k}**: {v}" for k, v in sorted(data.items())[-20:]) or "-")
        embed.add_field(name="**Elixir**", value="\n".join(tiers))
        embed.add_field(name="**:blue_circle: Jinxed	:green_circle: Finesse**", value="\n".join(
            x.center(8, "\u2800") + y.center(8, "\u2800") for x, y in zip(elixirs['finesse'], elixirs['jinxed'])))
        embed.add_field(name="**:red_circle: Bloody	:yellow_circle: Lucky**", value="\n".join(
            x.center(7, "\u2800") + y.center(9, "\u2800") for x, y in zip(elixirs['bloody'], elixirs['lucky'])))

        await ctx.send(embed=embed)

    @command()
    async def muinv(self, ctx, *, nick: IsMyNick):
        """Shows your military unit inventory."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(f"{base_url}militaryUnitStorage.html", return_tree=True)
        products = {}
        for item in tree.xpath("//div[@class='storage']"):
            name = item.xpath("div[2]/img/@src")[0].replace("//cdn.e-sim.org//img/productIcons/", "").replace(
                "Rewards/", "").replace(".png", "")
            if name.lower() in ("iron", "grain", "diamonds", "oil", "stone", "wood"):
                quality = ""
            else:
                quality = item.xpath("div[2]/img/@src")[1].replace("//cdn.e-sim.org//img/productIcons/",
                                                                   "").replace(".png", "")
            products[f"{quality.title()} {name}"] = int(item.xpath("div[1]/text()")[0].strip())

        coins_len = max(5, len(products))
        tree = await self.bot.get_content(f"{base_url}militaryUnitMoneyAccount.html", return_tree=True)
        amounts = tree.xpath('//*[@id="esim-layout"]//div[4]//div//b/text()')[:coins_len]
        coins = tree.xpath('//*[@id="esim-layout"]//div[4]/div/text()')[2::3][:coins_len]

        embed = Embed(title=nick)
        embed.add_field(name="**Products:**",
                        value="\n".join(f"**{product}**: {amount:,}" for product, amount in products.items()) if products else "-")
        embed.add_field(name=f"**Coins (first {coins_len}):**",
                        value="\n".join(f"**{coin.strip()}**: {round(float(amount), 2):,}" for coin, amount in zip(coins, amounts)) if coins else "-")
        embed.set_footer(text="Military Unit Inventory")
        await ctx.send(embed=embed)

    @command()
    async def limits(self, ctx, *, nicks):
        """Display limits"""
        async for nick in utils.get_nicks(ctx.channel.name, nicks):
            base_url = f"https://{ctx.channel.name}.e-sim.org/"
            tree = await self.bot.get_content(base_url + "home.html", return_tree=True)
            gold = tree.xpath('//*[@id="userMenu"]//div//div[4]//div[1]/b/text()')[0]
            food_storage, gift_storage = utils.get_storage(tree)
            food_limit, gift_limit = utils.get_limits(tree)
            await ctx.send(f"**{nick}** Limits: {food_limit}/{gift_limit}, "
                           f"storage: {food_storage}/{gift_storage}, {gold} Gold.")

    @command()
    @check(utils.is_helper)
    async def regions(self, ctx, country: Country):
        """Lists the core regions of the given country"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api_regions = await self.bot.get_content(base_url + "apiRegions.html")
        regions = [region for region in api_regions if region["homeCountry"] == country]
        embed = Embed(title="Core Regions")
        embed.add_field(name="Region", value="\n".join(f"[{region['name']}]({base_url}region.html?id={region['id']})" +
                                                       (" (capital)" if region["capital"] else "") for region in regions))
        embed.add_field(name="Resource", value="\n".join(f"{region['rawRichness'].title()} {region.get('resource', '').title()}" for region in regions))
        embed.add_field(name="Neighbours Ids", value="\n".join(", ".join(str(x) for x in region['neighbours']) for region in regions))
        await ctx.send(embed=embed)

    @command()
    @check(utils.is_helper)
    async def country(self, ctx, country):
        """Provides some info about the given country."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api_countries = await self.bot.get_content(base_url + "apiCountries.html")
        country = next(x for x in api_countries if x["name"].lower() == country.lower())
        embed = Embed(title=country["name"])
        embed.add_field(name="Id", value=country["id"])
        embed.add_field(name="Capital", value=f'[{country["capitalName"]}]({base_url}region.html?id={country["capitalRegionId"]})')
        embed.add_field(name="Currency", value=country["currencyName"])
        embed.add_field(name="Short Name", value=country["shortName"])
        if "president" in country:
            president = await self.bot.get_content(f'{base_url}apiCitizenById.html?id={country["president"]}')
            embed.add_field(name="President", value=f"[{president['login']}]({base_url}profile.html?id={country['president']})")
        else:
            embed.add_field(name="President", value="-")
        await ctx.send(embed=embed)

    @command()
    @check(utils.is_helper)
    async def auctions(self, ctx):
        """Lists some details about the first upcoming 10 auctions"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(base_url + "auctions.html", return_tree=True)
        col1 = []
        col2 = []
        col3 = []
        for tr in range(2, 13):
            try:
                seller = tree.xpath(f'//tr[{tr}]//td[1]/a/text()')[0].strip()
            except IndexError:  # No more auctions
                break
            buyer = (tree.xpath(f'//tr[{tr}]//td[2]/a/text()') or ["None"])[0].strip()
            item = tree.xpath(f'//tr[{tr}]//td[3]/b/text()')
            parameters = tree.xpath(f'//tr[{tr}]//td[3]/text()')
            if not item:
                parameters = parameters[1]
            else:
                item = item[0].lower().replace("personal", "").replace("charm", "").replace("weapon upgrade", "WU").title()
                parameters = f"{item} " + ", ".join(par_val[1] for par_val in (utils.get_parameter(p) for p in parameters[5:]))

            price = tree.xpath(f'//tr[{tr}]//td[4]/b/text()')[0]
            link = utils.get_ids_from_path(tree, f'//tr[{tr}]//td[5]/a')[0]
            time = tree.xpath(f'//tr[{tr}]//td[6]/span/text()')[0]
            col1.append(f"{seller} : {buyer}"[:30])
            col2.append(parameters[:30])
            col3.append(f"{float(price):,}g : [{time}]({base_url}auction.html?id={link})")
        embed = Embed(title="First 10 auctions")
        embed.add_field(name="Seller : Buyer", value="\n".join(col1))
        embed.add_field(name="Item", value="\n".join(col2))
        embed.add_field(name="Gold : Time Reminding", value="\n".join(col3))
        await ctx.send(embed=embed)

    @command()
    async def info(self, ctx, *, nick):
        """Shows some info about a given user.
        `.info all` will give you a brief info about all users connected to MongoDB
        (if you did not set it via config.json or config command, the info is only about the specific nick)"""
        if nick.lower() == "all" and await utils.is_helper():
            values = await utils.find(ctx.channel.name, "info")
            if values:
                values.sort(key=lambda x: x.get('Buffed at', "-"))
                embed = Embed()
                for row in values:  # temp fix for old version
                    if "-" in row.get("Buffed at", ""):
                        row["Buffed at"] = row["Buffed at"][5:-3].replace("-", "/")
                    if "-" in row.get("Worked at", ""):
                        row["Worked at"] = row["Worked at"][5:-3].replace("-", "/")
                embed.add_field(name="Nick", value="\n".join([row["_id"] for row in values]))
                embed.add_field(name="Limits", value="\n".join([row.get("limits", "Unknown") for row in values]))
                embed.add_field(name="Worked At		 Buffed at", value="\n".join([row.get("Worked at", "-").ljust(13, "\u2800") + row.get("Buffed at", "-").ljust(13, "\u2800") for row in values]))
                embed.set_footer(text="Type .info <nick> for more info on a nick")
                await ctx.send(embed=embed)
            else:
                await ctx.send("No data available")
            return
        server = ctx.channel.name
        if nick.lower() != utils.my_nick(server).lower():
            return

        base_url = f"https://{server}.e-sim.org/"
        tree = await self.bot.get_content(base_url + "storage.html?storageType=PRODUCT", return_tree=True)

        gold = tree.xpath('//*[@id="userMenu"]//div//div[4]//div[1]/b/text()')[0]
        storage = {}
        for num in range(1, 22):
            try:
                item = str(tree.xpath(f'//*[@id="resourceInput"]/option[{num}]')[0].text).strip().replace(
                    "(available", "").replace(")", "").split(":")
                while "  " in item[0]:
                    item[0] = item[0].replace("  ", "")
                storage[item[0]] = int(item[1])
            except Exception:
                break

        special = {}
        elixirs = {"jinxed": [""]*6, "finesse": [""]*6, "bloody": [""]*6, "lucky": [""]*6}
        tiers = ["Mili", "Mini", "Standard", "Major", "Huge", "Exceptional"]
        special_tree = await self.bot.get_content(f"{base_url}storage.html?storageType=SPECIAL_ITEM", return_tree=True)
        for item in special_tree.xpath('//div[@class="specialItemInventory"]'):
            if item.xpath('span/text()'):
                s_item = item.xpath('b/text()')[0]
                if "elixir" not in s_item:
                    special[s_item] = item.xpath('span/text()')[0]
                else:
                    s_item = s_item.replace(" elixir", "").split()
                    tier, elixir = s_item[0], s_item[1]
                    elixirs[elixir][tiers.index(tier)] = item.xpath('span/text()')[0].replace("x", "")

        api = await self.bot.get_content(base_url + 'apiCitizenByName.html?name=' + nick.lower())
        data = await utils.find_one(server, "info", nick)
        date_format = "%m/%d %H:%M"

        now = datetime.now().astimezone(timezone('Europe/Berlin')).strftime(date_format)

        if "Buffed at" not in data:
            data["Buffed at"] = "-"
        else:
            if "-" in data["Buffed at"]:  # temp fix for old version
                data["Buffed at"] = data["Buffed at"][5:-3].replace("-", "/")
            days = 2 if api["premiumDays"] else 3
            buffed_seconds = (datetime.strptime(now, date_format) - datetime.strptime(data["Buffed at"], date_format)).total_seconds()
            day_seconds = 24 * 60 * 60
            debuff_ends = (timedelta(days=days) + datetime.strptime(data["Buffed at"], date_format)).strftime(date_format)
            if buffed_seconds < day_seconds:  # buff lasts 24h
                seconds = day_seconds - buffed_seconds
            elif buffed_seconds < day_seconds * days:  # debuff ends
                seconds = (datetime.strptime(debuff_ends, date_format) - datetime.strptime(
                    now, date_format)).total_seconds()
            else:
                seconds = 0
            data["Buffed at"] += f" ({timedelta(seconds=seconds)}h left)"

        link = f"{base_url}profile.html?id={api['id']}"
        tree = await self.bot.get_content(link, return_tree=True)

        embed = Embed(colour=0x3D85C6, url=link)
        embed.title = ("\U0001f7e2" if tree.xpath('//*[@id="loginBar"]/span[2]/@class')[0] == "online" else
                       "\U0001f534") + f" {api['login']}, {api['citizenship']} (id {api['citizenshipId']})"

        buffs_debuffs = [x.split("/specialItems/")[-1].split(".png")[0] for x in
                         tree.xpath('//*[@class="profile-row" and (strong="Debuffs" or strong="Buffs")]//img/@src') if
                         "//cdn.e-sim.org//img/specialItems/" in x]
        buffs = ', '.join([x.split("_")[0].lower().replace("vacations", "vac").replace("resistance", "sewer").replace(
            "paindealer", "PD ").replace("bonusdamage", "") + ("% Bonus" if "bonusdamage" in x.lower() else "") for x in
                           buffs_debuffs if "positive" in x.split("_")[1:]]).title()
        debuffs = ', '.join([x.split("_")[0].lower().replace("vacations", "vac").replace(
            "resistance", "sewer") for x in buffs_debuffs if "negative" in x.split("_")[1:]]).title()

        stats = {"Buffs": buffs or "-", "Debuffs": debuffs or "-",
                 "Total DMG": f"{api['totalDamage'] - api['damageToday']:,}",
                 "Today's DMG": f"{api['damageToday']:,}", "XP": f"{api['xp']:,}",
                 "Premium": f"till {date.today() + timedelta(days=int(api['premiumDays']))} ({api['premiumDays']} days)" if
                            api['premiumDays'] else "", "Economy skill": round(api['economySkill'], 1),
                 "Birthday": (tree.xpath('//*[@class="profile-row" and span = "Birthday"]/span/text()') or [1])[0],
                 "Medals": f"{api['medalsCount']:,}", "Friends": f"{api['friendsCount']:,}", "Gold": gold}
        data.update(stats)

        eqs = []
        for slot_path in tree.xpath('//*[@id="profileEquipmentNew"]//div//div//div//@title'):
            tree = fromstring(slot_path)
            try:
                eq_type = tree.xpath('//b/text()')[0].lower().replace("personal", "").replace("charm", "").replace(
                    "weapon upgrade", "WU").replace("  ", " ").title().strip()
            except IndexError:
                continue
            eq_id = utils.get_ids_from_path(tree, "//a")[0]
            parameters = [utils.get_parameter(p) for p in tree.xpath('//p/text()') if p.replace("Merged by", "").strip()]
            eqs.append(f"**[{eq_type}]({base_url}showEquipment.html?id={eq_id}):** " + ", ".join(f"{p[0]} {p[1]}" for p in parameters))

        if api['militaryUnitId']:
            mu = await self.bot.get_content(f"{base_url}apiMilitaryUnitById.html?id={api['militaryUnitId']}")
            data["MU"] = f"[{mu['name']}]({base_url}militaryUnit.html?id={api['militaryUnitId']})"
        else:
            data["MU"] = "No MU"

        api_regions = await self.bot.get_content(base_url + "apiRegions.html")
        api_countries = await self.bot.get_content(base_url + "apiCountries.html")

        region, country = utils.get_region_and_country_names(api_regions, api_countries, api['currentLocationRegionId'])
        data["Location"] = f"[{region}, {country}]({base_url}region.html?id={api['currentLocationRegionId']})"
        parameters = {"Crit": api['eqCriticalHit'],
                      "Avoid": api['eqAvoidDamage'],
                      "Miss": api['eqReduceMiss'],
                      "Dmg": api['eqIncreaseDamage'],
                      "Max": api['eqIncreaseMaxDamage'],
                      "Inc. Eco Skill": api['eqIncreaseEcoSkill'],
                      "Less Weapons": api['eqLessWeapons'],
                      "Find Weapon": api['eqFindAWeapon'],
                      "Inc. Strength": api['eqIncreaseStrength'],
                      "Increase Hit": api['eqIncreaseHit'],
                      "Free Flight": api['eqFreeFlight']}

        embed.add_field(name="__Stats__", value="\n".join([f"**{k}**: {v}" for k, v in data.items()]))
        embed.add_field(name="__Parameters__", value="\n".join([f"**{k}**: {v}" for k, v in parameters.items() if v]))
        embed.add_field(name="__Slots__", value="\n".join(eqs) or "- no eqs found -")

        if 'companyId' in api:
            comp_link = f"{base_url}company.html?id={api['companyId']}"
            tree = await self.bot.get_content(comp_link, return_tree=True)
            company_type = tree.xpath("//div[1]/div/div[1]/div/div[3]/b/span/@title")[0]
            company_quality = tree.xpath("//div[1]/div/div[1]/div/div[3]/b/text()[2]")[0].strip()
            company_name = tree.xpath('//a[@style="font-weight: bold;clear:both;"]/text()')[0]
            region_id = utils.get_ids_from_path(tree, "//div[1]/div/div[1]/div/div[4]/b/a")[0]
            region, country = utils.get_region_and_country_names(api_regions, api_countries, int(region_id))
            embed.add_field(name=f"Works in a {company_quality} {company_type} company",
                            value=f"[{company_name}]({comp_link}) ([{region}]({base_url}region.html?id={region_id}), {country})")
        embed.add_field(name="__Storage__", value="\n".join([f'**{k}**: x{v:,}' for k, v in sorted(storage.items())]) or "-")
        embed.add_field(name="__Special Items__", value="\n".join([f'**{k}**: {v}' for k, v in sorted(special.items())]) or "-")

        embed.add_field(name="**Elixir**", value="\n".join(tiers))
        embed.add_field(name="**:blue_circle: Jinxed	:green_circle: Finesse**", value="\n".join(
            x.center(8, "\u2800") + y.center(8, "\u2800") for x, y in zip(elixirs['finesse'], elixirs['jinxed'])))
        embed.add_field(name="**:red_circle: Bloody	:yellow_circle: Lucky**", value="\n".join(
            x.center(7, "\u2800") + y.center(9, "\u2800") for x, y in zip(elixirs['bloody'], elixirs['lucky'])))

        embed.set_footer(text="Code Version: " + self.bot.VERSION)
        await ctx.send(embed=embed)


def setup(bot):
    """setup"""
    bot.add_cog(Info(bot))
