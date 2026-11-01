import discord
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Set, List
from utils.database import Database

logger = logging.getLogger(__name__)

class ChannelManager:
    def __init__(self, bot, db: Database):
        self.bot = bot
        self.db = db
        # channel_id: list of datetimes of recent renames for rate-limit protection
        self.rename_history: dict[int, list[datetime]] = {}
        self._creation_lock = asyncio.Lock()

    async def is_temp_channel(self, channel_id: int) -> bool:
        """Check if a channel ID is a registered temporary channel."""
        data = await self.db.get_temp_channel(channel_id)
        return data is not None

    async def get_channel_owner_id(self, channel_id: int) -> Optional[int]:
        """Get the user ID of the channel owner."""
        data = await self.db.get_temp_channel(channel_id)
        return data["owner_id"] if data else None

    async def is_channel_owner(self, channel: discord.VoiceChannel, member: discord.Member) -> bool:
        """Verify whether member is the owner of channel."""
        if not channel or not member:
            return False
        owner_id = await self.get_channel_owner_id(channel.id)
        return owner_id == member.id

    async def create_temp_channel(
        self, member: discord.Member, generator_channel: discord.VoiceChannel
    ) -> Optional[discord.VoiceChannel]:
        """Create a temporary voice channel for a member."""
        async with self._creation_lock:
            # Check if user already owns an active channel in this guild
            existing = await self.db.get_user_temp_channel(member.guild.id, member.id)
            if existing:
                existing_channel = member.guild.get_channel(existing["channel_id"])
                if existing_channel and len(existing_channel.members) > 0:
                    return existing_channel
                elif existing_channel:
                    # Stale empty channel, clean it up first
                    try:
                        await existing_channel.delete()
                    except discord.HTTPException:
                        pass
                    await self.db.remove_temp_channel(existing["channel_id"])

            category = generator_channel.category
            channel_name = f"🔊 {member.display_name}'s channel"

            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(
                    connect=True,
                    view_channel=True
                ),
                member: discord.PermissionOverwrite(
                    manage_channels=True,
                    manage_roles=True,
                    connect=True,
                    move_members=True
                ),
                member.guild.me: discord.PermissionOverwrite(
                    manage_channels=True,
                    manage_roles=True,
                    connect=True,
                    move_members=True,
                    view_channel=True
                )
            }

            try:
                channel = await member.guild.create_voice_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"Temp voice channel for {member.name}"
                )
                await self.db.add_temp_channel(channel.id, member.guild.id, member.id)
                logger.info(f"Created temp voice channel {channel.name} ({channel.id}) for {member.name}")
                return channel
            except discord.HTTPException as e:
                logger.error(f"Failed to create temporary voice channel: {e}")
                return None

    def _can_rename(self, channel_id: int) -> Tuple[bool, int]:
        """
        Discord rate limits channel name edits to 2 edits per 10 minutes.
        Returns (can_rename, seconds_to_wait).
        """
        now = datetime.now(timezone.utc)
        ten_minutes_ago = now - timedelta(minutes=10)

        history = self.rename_history.get(channel_id, [])
        # Keep only timestamps within last 10 minutes
        history = [ts for ts in history if ts > ten_minutes_ago]
        self.rename_history[channel_id] = history

        if len(history) >= 2:
            oldest = history[0]
            wait_seconds = int((oldest + timedelta(minutes=10) - now).total_seconds())
            return False, max(1, wait_seconds)
        return True, 0

    async def rename_channel(self, channel: discord.VoiceChannel, new_name: str) -> Tuple[bool, str]:
        """Rename temporary channel with rate-limit protection."""
        can_rename, wait_time = self._can_rename(channel.id)
        if not can_rename:
            minutes = wait_time // 60
            seconds = wait_time % 60
            time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
            return False, f"Discord rate limits channel renames to 2 times per 10 minutes. Please wait {time_str}."

        try:
            await channel.edit(name=new_name)
            now = datetime.now(timezone.utc)
            self.rename_history.setdefault(channel.id, []).append(now)
            return True, f"Channel renamed to **{new_name}**!"
        except discord.HTTPException as e:
            logger.error(f"Failed to rename channel {channel.id}: {e}")
            return False, f"Failed to rename channel: {e}"

    async def set_user_limit(self, channel: discord.VoiceChannel, limit: int) -> bool:
        """Set user limit (0 for unlimited, 1-99)."""
        try:
            await channel.edit(user_limit=limit)
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to set user limit on {channel.id}: {e}")
            return False

    async def set_privacy(self, channel: discord.VoiceChannel, locked: bool) -> bool:
        """Lock or unlock the channel for @everyone."""
        try:
            overwrites = channel.overwrites
            owner_id = await self.get_channel_owner_id(channel.id)
            owner = channel.guild.get_member(owner_id) if owner_id else None

            # Set @everyone connect permission
            default_role = channel.guild.default_role
            current_default = overwrites.get(default_role, discord.PermissionOverwrite())
            current_default.connect = not locked
            overwrites[default_role] = current_default

            # Ensure owner can always connect
            if owner:
                owner_ov = overwrites.get(owner, discord.PermissionOverwrite())
                owner_ov.connect = True
                overwrites[owner] = owner_ov

            # Ensure bot can always connect
            bot_ov = overwrites.get(channel.guild.me, discord.PermissionOverwrite())
            bot_ov.connect = True
            bot_ov.view_channel = True
            overwrites[channel.guild.me] = bot_ov

            # Apply trusted users connect permission
            trusted_ids = await self.db.get_trusted_users(channel.id)
            for uid in trusted_ids:
                m = channel.guild.get_member(uid)
                if m:
                    u_ov = overwrites.get(m, discord.PermissionOverwrite())
                    u_ov.connect = True
                    overwrites[m] = u_ov

            # Apply blocked users deny permission
            blocked_ids = await self.db.get_blocked_users(channel.id)
            for uid in blocked_ids:
                m = channel.guild.get_member(uid)
                if m:
                    b_ov = overwrites.get(m, discord.PermissionOverwrite())
                    b_ov.connect = False
                    overwrites[m] = b_ov

            await channel.edit(overwrites=overwrites)
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to set privacy on channel {channel.id}: {e}")
            return False

    async def trust_user(self, channel: discord.VoiceChannel, user: discord.Member) -> bool:
        """Trust a user, granting them connect permission even if locked."""
        try:
            await self.db.add_trusted_user(channel.id, user.id)
            await self.db.remove_blocked_user(channel.id, user.id)
            overwrites = channel.overwrites
            u_ov = overwrites.get(user, discord.PermissionOverwrite())
            u_ov.connect = True
            overwrites[user] = u_ov
            await channel.edit(overwrites=overwrites)
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to trust user {user.id} in {channel.id}: {e}")
            return False

    async def untrust_user(self, channel: discord.VoiceChannel, user: discord.Member) -> bool:
        """Untrust a user, resetting their connect overwrite to inherit channel defaults."""
        try:
            await self.db.remove_trusted_user(channel.id, user.id)
            overwrites = channel.overwrites
            if user in overwrites:
                del overwrites[user]
            await channel.edit(overwrites=overwrites)
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to untrust user {user.id} in {channel.id}: {e}")
            return False

    async def block_user(self, channel: discord.VoiceChannel, user: discord.Member) -> bool:
        """Block a user from connecting and disconnect them if currently in channel."""
        try:
            await self.db.add_blocked_user(channel.id, user.id)
            await self.db.remove_trusted_user(channel.id, user.id)
            overwrites = channel.overwrites
            b_ov = overwrites.get(user, discord.PermissionOverwrite())
            b_ov.connect = False
            overwrites[user] = b_ov
            await channel.edit(overwrites=overwrites)

            # If user is in channel, disconnect them
            if user in channel.members:
                await user.move_to(None, reason="Blocked from temporary voice channel")
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to block user {user.id} from {channel.id}: {e}")
            return False

    async def unblock_user(self, channel: discord.VoiceChannel, user: discord.Member) -> bool:
        """Unblock a user, clearing the connect=False overwrite."""
        try:
            await self.db.remove_blocked_user(channel.id, user.id)
            overwrites = channel.overwrites
            if user in overwrites:
                del overwrites[user]
            await channel.edit(overwrites=overwrites)
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to unblock user {user.id} in {channel.id}: {e}")
            return False

    async def kick_user(self, channel: discord.VoiceChannel, user: discord.Member) -> bool:
        """Disconnect a user from the channel."""
        try:
            if user in channel.members:
                await user.move_to(None, reason="Kicked by channel owner")
                return True
            return False
        except discord.HTTPException as e:
            logger.error(f"Failed to kick user {user.id} from {channel.id}: {e}")
            return False

    async def transfer_ownership(
        self, channel: discord.VoiceChannel, new_owner: discord.Member
    ) -> bool:
        """Transfer channel ownership to new_owner."""
        try:
            old_owner_id = await self.get_channel_owner_id(channel.id)
            overwrites = channel.overwrites

            # Remove privileges from old owner if still in guild
            if old_owner_id:
                old_owner = channel.guild.get_member(old_owner_id)
                if old_owner and old_owner in overwrites:
                    del overwrites[old_owner]

            # Grant privileges to new owner
            overwrites[new_owner] = discord.PermissionOverwrite(
                manage_channels=True,
                manage_roles=True,
                connect=True,
                move_members=True
            )

            await channel.edit(overwrites=overwrites)
            await self.db.update_temp_channel_owner(channel.id, new_owner.id)
            logger.info(f"Transferred channel {channel.id} ownership to {new_owner.name}")
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to transfer ownership on {channel.id}: {e}")
            return False

    async def handle_owner_leave(
        self, channel: discord.VoiceChannel, departed_owner: discord.Member
    ) -> Optional[discord.Member]:
        """
        Automatically transfer ownership when owner leaves but members remain.
        Picks the oldest active member in the channel.
        """
        remaining_members = [m for m in channel.members if not m.bot and m.id != departed_owner.id]
        if not remaining_members:
            return None

        # Select the first member (oldest in channel)
        new_owner = remaining_members[0]
        success = await self.transfer_ownership(channel, new_owner)
        if success:
            try:
                await channel.send(
                    f"👑 {departed_owner.display_name} left the channel. "
                    f"Ownership has been transferred to {new_owner.mention}!"
                )
            except (discord.HTTPException, discord.Forbidden):
                pass
            return new_owner
        return None

    async def can_claim_channel(self, channel: discord.VoiceChannel, member: discord.Member) -> bool:
        """Check if a member can manually claim the channel."""
        owner_id = await self.get_channel_owner_id(channel.id)
        if not owner_id:
            return False
        if member.id == owner_id:
            return False
        current_owner = channel.guild.get_member(owner_id)
        # Member can claim if current owner is not connected to the channel
        return current_owner not in channel.members

    async def delete_temp_channel(self, channel: discord.VoiceChannel):
        """Delete temporary channel from Discord and remove from database."""
        channel_id = channel.id
        await self.db.remove_temp_channel(channel_id)
        self.rename_history.pop(channel_id, None)
        try:
            await channel.delete(reason="Temporary voice channel empty or closed by owner")
            logger.info(f"Deleted temp channel {channel_id}")
        except discord.HTTPException as e:
            logger.error(f"Failed to delete voice channel {channel_id}: {e}")

    async def cleanup_empty_channels(self):
        """Scan and delete all registered temp channels that have 0 members."""
        channels_data = await self.db.get_all_temp_channels()
        for data in channels_data:
            channel = self.bot.get_channel(data["channel_id"])
            if channel is None:
                # Channel was already deleted from Discord
                await self.db.remove_temp_channel(data["channel_id"])
            elif len(channel.members) == 0:
                await self.delete_temp_channel(channel)

    async def reconcile_channels(self):
        """Run on startup: reconcile DB temp channels against live guild channels."""
        channels_data = await self.db.get_all_temp_channels()
        logger.info(f"Reconciling {len(channels_data)} temporary channels from database...")
        for data in channels_data:
            channel = self.bot.get_channel(data["channel_id"])
            if channel is None:
                await self.db.remove_temp_channel(data["channel_id"])
                continue

            if len(channel.members) == 0:
                await self.delete_temp_channel(channel)
            else:
                # Channel is active; check if owner is still inside
                owner_id = data["owner_id"]
                owner = channel.guild.get_member(owner_id)
                if owner not in channel.members:
                    # Auto transfer to a connected member
                    remaining = [m for m in channel.members if not m.bot]
                    if remaining:
                        await self.transfer_ownership(channel, remaining[0])
                        logger.info(f"Reconciled channel {channel.id}: transferred to {remaining[0].name}")
        logger.info("Channel reconciliation completed.")

    async def create_voice_discussion(self, channel: discord.VoiceChannel, topic: Optional[str] = None) -> Tuple[bool, str]:
        """
        Set the room status and create a discussion thread INSIDE the temporary voice room,
        ensuring the public voice-control channel remains completely clean.
        """
        topic_text = (topic or channel.name).strip()

        # 1. Update official Discord Voice Channel Status (visible in server sidebar)
        try:
            await channel.edit(status=topic_text[:500])
        except Exception as e:
            logger.debug(f"Could not set voice channel status on {channel.id}: {e}")

        # 2. Send the topic message inside the temp voice room's native text chat
        try:
            msg = await channel.send(
                f"💬 **موضوع الروم (Room Topic):** {topic_text}\n"
                f"يمكنكم التفاعل والمحادثة هنا داخل الروم."
            )
            # Create a thread on the message inside the voice channel if permitted
            try:
                thread = await msg.create_thread(name=f"💬 {topic_text[:90]}", auto_archive_duration=1440)
                return True, f"تم تعيين موضوع الروم وإنشاء الثريد داخل غرفتك: {thread.mention}"
            except Exception:
                return True, f"تم تعيين موضوع الروم داخل شات غرفتك الصوتية: {channel.mention}"
        except discord.HTTPException as e:
            logger.error(f"Failed to post discussion inside voice channel {channel.id}: {e}")
            return False, f"تعذر إرسال الموضوع داخل الروم: {e}"

    async def set_voice_region(self, channel: discord.VoiceChannel, region: Optional[str]) -> bool:
        """Set voice RTC region."""
        try:
            await channel.edit(rtc_region=region)
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to set region for {channel.id}: {e}")
            return False