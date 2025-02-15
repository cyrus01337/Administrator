import asyncio
import contextlib
import re
from typing import Optional, Tuple, Union

import discord
from discord.ext import commands

from base import custom

Medium = Union[discord.Message, discord.Member]


class Emotes(custom.Cog, hidden=True):
    def __init__(self, bot):
        self.bot = bot

        self._cached = set()
        self._cached_event = asyncio.Event()
        self.emotes = {}
        self.pattern = re.compile(r"\$(?P<escaped>\\)?(?P<name>[a-zA-Z0-9_]+)")
        self.bonk_emotes: Tuple = None

        self.bot.loop.create_task(self.__ainit__())

    async def __ainit__(self):
        await self.bot.wait_until_ready()
        self._cache_emotes(self.bot.home)

        for guild in self.bot.guilds:
            self._cache_emotes(guild)

        self.bonk_emotes = (self.emotes["angery"], "🗞️")
        self._cached_event.set()

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    def _cache_emotes(self, guild):
        if guild.id not in self._cached:
            self._cached.add(guild.id)

            for emote in guild.emojis:
                self.emotes.setdefault(emote.name, str(emote))

    async def _get_recent_message(self,
                                  channel: discord.TextChannel,
                                  before: discord.Message,
                                  *, author: Optional[discord.Member] = None):
        async for message in channel.history(before=before):
            if author and message.author != author:
                continue
            return message

    @commands.Cog.listener()
    async def on_message(self, message):
        uncached = not self._cached_event.is_set()
        ctx = await self.bot.get_context(message)

        if message.author.bot or uncached or ctx.valid:
            return
        generated = wrapping = ""
        matches = self.pattern.findall(message.content)

        if not matches:
            return

        for escaped, name in matches:
            emote_found = self.emotes.get(name)

            if not emote_found:
                continue
            append = emote_found

            if escaped:
                wrapping += f"{append} "
                continue
            elif not escaped and wrapping:
                append = f"`{wrapping}` {append} "
                wrapping = ""
            generated += append

        if wrapping:
            generated += f"`{wrapping}`"

        if not generated:
            return
        elif len(generated) > 2000:
            return await message.add_reaction("❌")
        await message.channel.send(generated)

    @commands.command()
    async def bonk(self,
                   ctx,
                   medium: Optional[Medium] = None):
        kwargs = {}
        joined = ("").join(self.bonk_emotes)

        if isinstance(medium, discord.Member):
            kwargs["author"] = medium

        if not isinstance(medium, discord.Message):
            medium = await self._get_recent_message(
                ctx.channel,
                ctx.message,
                author=medium
            )

        with contextlib.suppress(discord.Forbidden):
            for emote in self.bonk_emotes:
                await medium.add_reaction(emote)
        await ctx.send(f"{medium.author.mention} {joined}")

    @commands.command()
    async def react(self, ctx, message_id: Optional[int], name):
        added = 0

        def check(guild):
            return (guild.name.lower() == name.lower() and
                    guild.owner_id == ctx.author.id)

        guild = discord.utils.find(check, self.bot.guilds)
        emojis = filter(lambda e: e.name.lower() == name.lower(), guild.emojis)

        if message_id:
            message_found = await ctx.channel.fetch_message(message_id)
        else:
            async for message in ctx.channel.history():
                if message.author != ctx.author:
                    message_found = message

                    break

        if message_found:
            with contextlib.suppress(discord.Forbidden):
                for emoji in emojis:
                    await message_found.add_reaction(emoji)
                    added += 1

        if added > 0:
            await ctx.send(message_found.jump_url)


def setup(bot):
    bot.add_cog(Emotes(bot))
