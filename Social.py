from asyncio import sleep
from json import loads
from random import choice

from discord import Embed
from discord.ext.commands import Cog, command

from Converters import IsMyNick


class Social(Cog):
    """Social Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command()
    async def comment(self, ctx, shout_or_article_link, body, *, nick: IsMyNick):
        """ Commenting an article or a shout.
        
        - `body` parameter MUST be within quotes.
        - You can find the shout link by clicking F12 on the page where you see the shout."""

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        id = shout_or_article_link.split("?id=")[1].split("&")[0]
        if "article" in shout_or_article_link:
            payload = {"action": "NEW", "key": f"Article {id}", "submit": "Publish", "body": body}
            url = await self.bot.get_content(URL + "comment.html", data=payload)
        elif "Shout" in shout_or_article_link:
            url = await self.bot.get_content(f"{URL}replyToShout.html?id={id}",
                                             data={"body": body, "submit": "Shout!"})
        else:
            return await ctx.send(f"**{nick}** ERROR: invalid article/shout link.")
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def read(self, ctx, *, nick: IsMyNick):
        """Reading all new msgs and notifications + accept friend requests"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        tree = await self.bot.get_content(URL, return_tree=True)
        msgs = int(str(tree.xpath("//*[@id='inboxMessagesMission']/b")[0].text))
        alerts = int(str(tree.xpath('//*[@id="numero1"]/a/b')[0].text))
        if alerts:
            for page in range(1, alerts // 20 + 2):
                tree = await self.bot.get_content(f"{URL}notifications.html?page={page}", return_tree=True)
                embed = Embed(title=f"**{nick}** {URL}notifications.html?page={page}\n")
                for tr in range(2, min(20, alerts) + 2):
                    try:
                        alert = tree.xpath(f'//tr[{tr}]//td[2]')[0].text_content().strip()
                        alertDate = tree.xpath(f'//tr[{tr}]//td[3]')[0].text_content().strip()
                        if "has requested to add you as a friend" in alert:
                            await self.bot.get_content(URL + str(tree.xpath(f"//tr[{tr}]//td[2]/a[2]/@href")[0]))
                        elif "has offered you to sign" in alert:
                            alert = alert.replace("contract", f'[contract]({URL}{tree.xpath(f"//tr[{tr}]//td[2]/a[2]/@href")[0]})').replace(
                                "Please read it carefully before accepting it, make sure that citizen doesn't want to cheat you!", "\nSee `.help contract`")
                        alerts -= 1
                        embed.add_field(name=alertDate, value=alert, inline=False)
                    except:
                        break
                await ctx.send(embed=embed)

        if msgs:
            tree = await self.bot.get_content(URL + "inboxMessages.html", return_tree=True)
            embed = Embed(title=f"**{nick}** {URL}inboxMessages.html")
            for tr in range(2, msgs + 2):
                AUTHOR = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[1]//div/a[2]/text()')[0].strip()
                CONTENT = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[2]/div[1]')[0].text_content().strip()
                Title = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[2]/b[1]//div')[0].text_content().strip()
                date = str(tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[3]')[0].text).strip()
                embed.add_field(name=AUTHOR, value=f"**{Title}**\n{CONTENT}\n{date}", inline=False)
            await ctx.send(embed=embed)
        if not alerts and not msgs:
            await ctx.send(f"**{nick}:** There are no new alerts or messages!")

    @command(aliases=["MU"])
    async def citizenship(self, ctx, country_or_mu_id: int, *, nick: IsMyNick):
        """Send application to a MU / country."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        messages = ["The application will be reviewed by congress members", "Hi ............... Accept me ..",
                    "Coming to help you guys pls accept me",
                    "[currency]GOLD[/currency][currency]GOLD[/currency]",
                    "[citizen][citizen] [citizen][citizen] [/citizen][/citizen]",
                    # feel free to add more in the same format: "item1", "item2"
                    ]

        if ctx.invoked_with.lower() == "citizenship":
            payload = {'action': "APPLY", 'countryId': country_or_mu_id, "message": choice(messages),
                       "submit": "Apply for citizenship"}
            link = "citizenshipApplicationAction.html"
            await self.bot.get_content(URL + "countryLaws.html", data={"action": "LEAVE_CONGRESS", "submit": "Leave congress"})
            await self.bot.get_content(URL + "partyStatistics.html", data={"action": "LEAVE", "submit": "Leave party"})
        else:
            payload = {'action': "SEND_APPLICATION", 'id': country_or_mu_id, "message": choice(messages),
                       "submit": "Send application"}
            link = "militaryUnitsActions.html"
            await self.bot.get_content(URL + link, data={"action": "CANCEL_APPLICATION", "submit": "Cancel application"})

        url = await self.bot.get_content(URL + link, data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def msg(self, ctx, receiver_name, title, body, *, nick: IsMyNick):
        """Sending a msg.
        If receiver_name, title or body contains more than 1 word - it must be within quotes"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'receiverName': receiver_name, "title": title, "body": body, "action": "REPLY", "submit": "Send"}
        url = await self.bot.get_content(URL + "composeMessage.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def shout(self, ctx, shout_body, *, nick: IsMyNick):
        """Publishing a shout.
        `shout_body` MUST be within quotes"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        payload = {'action': "POST_SHOUT", 'body': shout_body, 'sendToCountry': "on",
                   "sendToMilitaryUnit": "on", "sendToParty": "on", "sendToFriends": "on"}
        url = await self.bot.get_content(f"{URL}shoutActions.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["vote", "vote_shout"])
    async def sub(self, ctx, id: int, *, nick: IsMyNick):
        """Subscribe to specific newspaper / vote an article or a shout.
        (for voting a shout you will have to click F12 on the shouts page to find the id)"""

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if ctx.invoked_with.lower() == "sub":
            url = await self.bot.get_content(f"{URL}sub.html", data={"id": id})
        elif ctx.invoked_with.lower() == "vote":
            url = await self.bot.get_content(f"{URL}vote.html", data={"id": id})
        else:
            url = await self.bot.get_content(f"{URL}shoutVote.html", data={"id": id, "vote": 1})
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["friends+"])
    async def friends(self, ctx, *, nick: IsMyNick):
        """Sending friend request to the entire server / all online citizens"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        await ctx.send(f"**{nick}** on it")
        results = list()
        if ctx.invoked_with.lower() == "friends":
            for Index, row in enumerate(await self.bot.get_content(f"{URL}apiOnlinePlayers.html")):
                if (Index+1) % 10 == 0 and results:
                    await ctx.send(f"**{nick}**\n" + "\n".join(results))
                    results.clear()
                row = loads(row)
                try:
                    url = await self.bot.get_content(f"{URL}friends.html?action=PROPOSE&id={row['id']}")
                    if "PROPOSED_FRIEND_OK" in str(url):
                        results.append("Sent to: " + row['login'])
                except Exception as error:
                    await ctx.send(f"**{nick}** ERROR: {error}")
                await sleep(1)
        else:
            tree = await self.bot.get_content(URL + 'citizenStatistics.html?statisticType=DAMAGE&countryId=0', return_tree=True)
            last = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href")
            last = last[0].split("page=")[1]
            for page in range(1, int(last) + 1):
                if page != 1:
                    tree = await self.bot.get_content(
                        URL + 'citizenStatistics.html?statisticType=DAMAGE&countryId=0&page=' + str(page), return_tree=True)
                for link in tree.xpath("//td/a/@href"):
                    try:
                        url = f"{URL}friends.html?action=PROPOSE&id={link.split('=')[1]}"
                        send = await self.bot.get_content(url)
                        if send == url:
                            await ctx.send(f"**{nick}** ERROR: you are not logged in, see `.help login`")
                        results.append(f"<{send}>")
                    except Exception as error:
                        await ctx.send(f"**{nick}** ERROR: {error}")
                    await sleep(1)
                if results:
                    await ctx.send(f"**{nick}**\n" + "\n".join(results))
                    results.clear()
        if results:
            await ctx.send(f"**{nick}**\n" + "\n".join(results))
        await ctx.send(f"**{nick}** done.")


def setup(bot):
    bot.add_cog(Social(bot))
