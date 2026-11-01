import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from typing import Optional

from utils.channel_manager import ChannelManager
from utils.interface import create_control_interface, ControlView

logger = logging.getLogger(__name__)

class VoiceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.channel_manager = ChannelManager(bot, self.db)
        self.cleanup_loop.start()

    def cog_unload(self):
        self.cleanup_loop.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Handle dynamic temporary channel creation and instant cleanup / handover."""
        # 1. User joins a "Join-to-Create" generator channel
        if after.channel and await self.db.is_generator(after.channel.id):
            new_channel = await self.channel_manager.create_temp_channel(member, after.channel)
            if new_channel:
                try:
                    await member.move_to(new_channel)
                    logger.info(f"Moved {member.name} to new temp voice channel {new_channel.name}")
                except discord.HTTPException as e:
                    logger.error(f"Failed to move {member.name} to {new_channel.name}: {e}")
            return

        # 2. User leaves a temporary voice channel
        if before.channel and before.channel != after.channel:
            if await self.channel_manager.is_temp_channel(before.channel.id):
                active_members = [m for m in before.channel.members if not m.bot]

                if len(active_members) == 0:
                    # Instant deletion when last member leaves
                    logger.info(f"Temp channel {before.channel.id} is empty. Deleting immediately.")
                    await self.channel_manager.delete_temp_channel(before.channel)
                else:
                    # Channel still has members; check if departed member was owner
                    if await self.channel_manager.is_channel_owner(before.channel, member):
                        logger.info(f"Owner {member.name} left channel {before.channel.id}. Initiating auto-handover.")
                        await self.channel_manager.handle_owner_leave(before.channel, member)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Clean up database records if a channel is deleted manually in Discord."""
        if isinstance(channel, discord.VoiceChannel):
            if await self.channel_manager.is_temp_channel(channel.id):
                logger.info(f"Tracked temp channel {channel.id} was deleted externally. Removing DB record.")
                await self.db.remove_temp_channel(channel.id)
            elif await self.db.is_generator(channel.id):
                logger.info(f"Generator channel {channel.id} was deleted externally. Removing DB record.")
                await self.db.remove_generator(channel.id)

    @app_commands.command(name="setup", description="Set up a temporary voice channel system in a category.")
    @app_commands.describe(
        category="Category to place the generator and voice channels in",
        channel_name="Name for the Join-to-Create voice channel (default: ➕ Create Channel)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        channel_name: Optional[str] = "➕ Create Channel"
    ):
        """Setup a Join-to-Create channel and persistent control dashboard."""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        try:
            # 1. Create the generator voice channel
            generator_channel = await category.create_voice_channel(
                name=channel_name,
                reason="Temp Voice generator channel"
            )
            await self.db.add_generator(generator_channel.id, guild.id, category.id)
            logger.info(f"Created generator channel '{generator_channel.name}' ({generator_channel.id}) in guild {guild.id}")

            # 2. Locate or create the voice-control text channel
            control_channel = discord.utils.get(category.text_channels, name="voice-control")
            if not control_channel:
                control_channel = await guild.create_text_channel(
                    name="voice-control",
                    category=category,
                    topic="Central controls for temporary voice channels",
                    reason="Temp Voice control panel channel"
                )
                logger.info(f"Created control channel '{control_channel.name}' ({control_channel.id})")

            # 3. Post or refresh persistent control interface
            await create_control_interface(control_channel, self)

            await interaction.followup.send(
                f"✅ **Temp Voice setup complete!**\n"
                f"• Generator: {generator_channel.mention}\n"
                f"• Dashboard: {control_channel.mention}\n"
                f"Users can now join {generator_channel.mention} to spawn private voice rooms.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during /setup in guild {guild.id}: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An error occurred during setup: {e}",
                ephemeral=True
            )

    @app_commands.command(name="cleanup", description="Purge any orphaned or empty temporary voice channels.")
    @app_commands.default_permissions(manage_channels=True)
    async def cleanup(self, interaction: discord.Interaction):
        """Admin command to clean up any orphaned empty voice channels."""
        await interaction.response.defer(ephemeral=True)
        try:
            before_count = len(await self.db.get_all_temp_channels())
            await self.channel_manager.cleanup_empty_channels()
            after_count = len(await self.db.get_all_temp_channels())
            removed = before_count - after_count

            await interaction.followup.send(
                f"🧹 Cleanup complete! Removed **{removed}** orphaned or empty channel(s).",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during /cleanup: {e}")
            await interaction.followup.send(f"❌ Failed to run cleanup: {e}", ephemeral=True)

    @tasks.loop(minutes=3)
    async def cleanup_loop(self):
        """Periodic safety net to clean up any empty channels that slipped through."""
        try:
            await self.channel_manager.cleanup_empty_channels()
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}")

    @cleanup_loop.before_loop
    async def before_cleanup_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(VoiceManager(bot))