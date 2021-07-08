from asyncio import sleep
from json import loads
from random import choice

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
        - You can find shout link by clicking F12 in the page where you see the shout."""

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        id = shout_or_article_link.split("?id=")[1].split("&")[0]
        if "article" in shout_or_article_link:
            payload = {"action": "NEW", "key": f"Article {id}", "submit": "Publish", "body": body}
            url = await self.bot.get_content(URL + "comment.html", data=payload, login_first=True)
        elif "shout" in shout_or_article_link:
            url = await self.bot.get_content(f"{URL}replyToShout.html?id={id}",
                                             data={"body": body, "submit": "Shout!"}, login_first=True)
        else:
            return await ctx.send("Please provide a valid article/shout link.")
        await ctx.send(url)

    @command()
    async def read(self, ctx, *, nick: IsMyNick):
        """Reading all new msgs and notifications + accept friend requests"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        tree = await self.bot.get_content(URL, login_first=True)
        msgs = int(str(tree.xpath("//*[@id='inboxMessagesMission']/b")[0].text))
        alerts = int(str(tree.xpath('//*[@id="numero1"]/a/b')[0].text))
        results = []
        if alerts:
            for page in range(1, int(alerts / 20) + 2):
                tree = await self.bot.get_content(f"{URL}notifications.html?page={page}")
                await ctx.send(f"{URL}notifications.html?page={page}\n")
                for tr in range(2, alerts + 2):
                    try:
                        alert = tree.xpath(f'//tr[{tr}]//td[2]')[0].text_content().strip()
                        alertDate = tree.xpath(f'//tr[{tr}]//td[3]')[0].text_content().strip()
                        if "has requested to add you as a friend" in alert:
                            await self.bot.get_content(URL + str(tree.xpath(f"//tr[{tr}]//td[2]/a[2]/@href")[0]))
                        alerts -= 1
                        results.append(f"{alertDate} - {alert}\n")
                    except:
                        break

        if msgs:
            tree = await self.bot.get_content(URL + "inboxMessages.html")
            results.append(f"{URL}inboxMessages.html\n")
            for tr in range(2, msgs + 2):
                AUTHOR = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[1]//div/a[2]/text()')[0].strip()
                CONTENT = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[2]/div[1]')[0].text_content().strip()
                Title = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[2]/b[1]//div')[0].text_content().strip()
                date = str(tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[3]')[0].text).strip()
                results.append(f"From: {AUTHOR}: {Title}\n{CONTENT}\n{date}")
        if not results:
            results.append("No news")
        await ctx.send("".join(results))

    @command(aliases=["MU"])
    async def citizenship(self, ctx, country_or_mu_id, *, nick: IsMyNick):
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
        else:
            payload = {'action': "SEND_APPLICATION", 'id': country_or_mu_id, "message": choice(messages),
                       "submit": "Send application"}
            link = "militaryUnitsActions.html"
            link2 = "myMilitaryUnit"
            # If there's already pending application
            await self.bot.get_content(URL + link2,
                                       data={"action": "CANCEL_APPLICATION", "submit": "Cancel application"},
                                       login_first=True)

        url = await self.bot.get_content(URL + link, data=payload, login_first="citizenship" in link)
        await ctx.send(url)

    @command()
    async def msg(self, ctx, receiver_name, title, body, *, nick: IsMyNick):
        """Sending a msg.
        If any arg (receiverName, title or body) containing more than 1 word - it must be within quotes"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'receiverName': receiver_name, "title": title, "body": body, "action": "REPLY", "submit": "Send"}
        url = await self.bot.get_content(URL + "composeMessage.html", data=payload, login_first=True)
        await ctx.send(url)

    async def shout(self, ctx, shout_body, *, nick: IsMyNick):
        """Publishing a shout.
        `shout_body` MUST be within quotes"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        payload = {'action': "POST_SHOUT", 'body': shout_body, 'sendToCountry': "on",
                   "sendToMilitaryUnit": "on", "sendToParty": "on", "sendToFriends": "on"}
        url = await self.bot.get_content(f"{URL}shoutActions.html", data=payload, login_first=True)
        await ctx.send(url)

    @command(aliases=["vote", "vote_shout"])
    async def sub(self, ctx, id: int, *, nick: IsMyNick):
        """Subscribe to specific newspaper / vote an article or a shout.
        (for voting a shout you will have to click F12 at the shouts page in order to find the id)"""

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if ctx.invoked_with.lower() == "sub":
            url = await self.bot.get_content(f"{URL}sub.html", data={"id": id}, login_first=True)
        elif ctx.invoked_with.lower() == "vote":
            url = await self.bot.get_content(f"{URL}vote.html", data={"id": id}, login_first=True)
        else:
            url = await self.bot.get_content(f"{URL}shoutVote.html", data={"id": id, "vote": 1}, login_first=True)
        await ctx.send(url)

    @command(aliases=["friends+"])
    async def friends(self, ctx, *, nick: IsMyNick):
        """Sending friend request to the entire server / all online citizens"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if ctx.invoked_with.lower() == "friends":
            for Index, row in enumerate(await self.bot.get_content(f"{URL}apiOnlinePlayers.html")):
                row = loads(row)
                try:
                    url = await self.bot.get_content(f"{URL}friends.html?action=PROPOSE&id={row['id']}",
                                                     login_first=not Index, return_url=True)
                    if "PROPOSED_FRIEND_OK" in str(url):
                        await ctx.send("Sent to:", row['login'])
                except Exception as error:
                    await ctx.send("error:", error)
                await sleep(1)
        else:
            tree = await self.bot.get_content(URL + 'citizenStatistics.html?statisticType=DAMAGE&countryId=0')
            last = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href")
            last = last[0].split("page=")[1]
            for page in range(1, int(last) + 1):
                if page != 1:
                    tree = await self.bot.get_content(
                        URL + 'citizenStatistics.html?statisticType=DAMAGE&countryId=0&page=' + str(page))
                for link in tree.xpath("//td/a/@href"):
                    try:
                        send = await self.bot.get_content(f"{URL}friends.html?action=PROPOSE&id={link.split('=')[1]}",
                                                          return_url=True)
                        if "PROPOSED_FRIEND_OK" in str(send):
                            await ctx.send(send)
                    except Exception as error:
                        await ctx.send("error:", error)
                    await sleep(1)


def setup(bot):
    bot.add_cog(Social(bot))
