import os
import sys
import logging
import discord
from discord.ext import commands

from config import DISCORD_TOKEN
from utils.database import Database
from utils.interface import ControlView
from utils.emojis import EmojiManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Bot intents
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
intents.members = True
intents.guilds = True

class TempVoiceBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="temporary voice rooms"
            )
        )
        self.db = Database()
        self.emoji_manager = EmojiManager(self)

    async def setup_hook(self):
        # 1. Initialize SQLite Database
        await self.db.initialize()

        # 2. Load the voice manager cog
        await self.load_extension("cogs.voice_manager")
        logger.info("Voice manager cog loaded")

        # 3. Sync custom application emojis and register persistent ControlView
        await self.emoji_manager.sync_emojis()
        voice_cog = self.get_cog("VoiceManager")
        if voice_cog:
            view = ControlView(voice_cog)
            view.apply_custom_emojis()
            self.add_view(view)
            logger.info("Registered persistent ControlView with custom emojis")

        # 4. Sync application slash commands with Discord
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} application commands")
        except discord.HTTPException as e:
            logger.error(f"Failed to sync application commands: {e}")

    async def close(self):
        logger.info("Shutting down Temp Voice Bot...")
        await self.db.close()
        await super().close()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        # Run startup reconciliation to clean any channels abandoned during downtime
        voice_cog = self.get_cog("VoiceManager")
        if voice_cog:
            await voice_cog.channel_manager.reconcile_channels()
        logger.info("Temp Voice Bot is online and fully operational!")

def main():
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your_bot_token_here":
        logger.error("No valid DISCORD_TOKEN found! Please set your token in the .env file.")
        sys.exit(1)

    bot = TempVoiceBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()