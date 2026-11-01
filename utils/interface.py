import os
import discord
from discord import ui
import logging
from typing import Optional

from config import SHOW_BANNER_IMAGE, DISCORD_PINK

logger = logging.getLogger(__name__)

async def validate_owner_interaction(
    interaction: discord.Interaction, cog, require_owner: bool = True
) -> Optional[discord.VoiceChannel]:
    """
    Validate that interaction.user is connected to a temporary voice channel
    and is the channel owner (if require_owner=True).
    Sends ephemeral error response if validation fails.
    """
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "❌ يجب أن تكون متصلاً بالروم الصوتي المؤقت الخاص بك لاستخدام هذه الأزرار!\n*(You must be connected to your temporary voice channel)*",
            ephemeral=True
        )
        return None

    channel = interaction.user.voice.channel
    is_temp = await cog.channel_manager.is_temp_channel(channel.id)
    if not is_temp:
        await interaction.response.send_message(
            "❌ أنت لست في روم صوتي مؤقت مسجل!\n*(You are not in a registered temporary voice channel)*",
            ephemeral=True
        )
        return None

    if require_owner:
        is_owner = await cog.channel_manager.is_channel_owner(channel, interaction.user)
        if not is_owner:
            await interaction.response.send_message(
                "❌ مالك الروم فقط يمكنه استخدام هذا الخيار!\n*(Only the channel owner can use this control)*",
                ephemeral=True
            )
            return None

    return channel


class ControlView(discord.ui.View):
    """
    Persistent dashboard view for managing temporary voice channels.
    Matches the exact 3x5 emoji button layout from the TempVoice interface.
    """

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.apply_custom_emojis()

    def apply_custom_emojis(self):
        """Apply custom Application Emojis if available."""
        emoji_mgr = getattr(self.cog, "emoji_manager", None) or getattr(getattr(self.cog, "bot", None), "emoji_manager", None)
        if emoji_mgr:
            self.name_button.emoji = emoji_mgr.get("tv_name")
            self.limit_button.emoji = emoji_mgr.get("tv_limit")
            self.privacy_button.emoji = emoji_mgr.get("tv_privacy")
            self.waiting_button.emoji = emoji_mgr.get("tv_waiting")
            self.thread_button.emoji = emoji_mgr.get("tv_thread")
            self.trust_button.emoji = emoji_mgr.get("tv_trust")
            self.untrust_button.emoji = emoji_mgr.get("tv_untrust")
            self.invite_button.emoji = emoji_mgr.get("tv_invite")
            self.kick_button.emoji = emoji_mgr.get("tv_kick")
            self.region_button.emoji = emoji_mgr.get("tv_region")
            self.block_button.emoji = emoji_mgr.get("tv_block")
            self.unblock_button.emoji = emoji_mgr.get("tv_unblock")
            self.claim_button.emoji = emoji_mgr.get("tv_claim")
            self.transfer_button.emoji = emoji_mgr.get("tv_transfer")
            self.delete_button.emoji = emoji_mgr.get("tv_delete")

    # ==================== Row 0 ====================

    @discord.ui.button(
        emoji="🔀",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_name",
        row=0
    )
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Change channel name."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        modal = NameModal(self.cog, channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        emoji="👥",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_limit",
        row=0
    )
    async def limit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set user limit."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        modal = LimitModal(self.cog, channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        emoji="🛡️",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_privacy",
        row=0
    )
    async def privacy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle Privacy / Lock."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return

        is_currently_locked = channel.overwrites_for(channel.guild.default_role).connect is False
        new_locked_state = not is_currently_locked
        success = await self.cog.channel_manager.set_privacy(channel, new_locked_state)

        if success:
            state_ar = "مقفل 🔒" if new_locked_state else "مفتوح 🔓"
            desc_ar = "يمكن للأعضاء الموثوقين فقط الدخول الآن." if new_locked_state else "يمكن للجميع الدخول الآن."
            await interaction.response.send_message(
                f"**تم تغيير حالة الروم إلى: {state_ar}**\n{desc_ar}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ حدث خطأ أثناء تغيير خصوصية الروم.", ephemeral=True)

    @discord.ui.button(
        emoji="🕔",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_waiting",
        row=0
    )
    async def waiting_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle Waiting Room / Knock mode."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return

        is_currently_locked = channel.overwrites_for(channel.guild.default_role).connect is False
        new_state = not is_currently_locked
        await self.cog.channel_manager.set_privacy(channel, new_state)

        status_msg = (
            "🕔 **تم تفعيل غرفة الانتظار / القفل!**\nالأعضاء غير الموثوقين لا يمكنهم الدخول مباشرة."
            if new_state
            else "🕔 **تم إلغاء غرفة الانتظار!**\nيمكن للجميع الانضمام الآن."
        )
        await interaction.response.send_message(status_msg, ephemeral=True)

    @discord.ui.button(
        emoji="💬",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_thread",
        row=0
    )
    async def thread_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set topic/status and create discussion thread INSIDE the temporary voice room."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return

        modal = TopicModal(self.cog, channel)
        await interaction.response.send_modal(modal)

    # ==================== Row 1 ====================

    @discord.ui.button(
        emoji="👤",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_trust",
        row=1
    )
    async def trust_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trust a user (grant connect permission even if locked)."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = UserActionSelectView(self.cog, channel, action="trust")
        await interaction.response.send_message("اختر العضو الذي تريد إعطاءه **الثقة**:", view=view, ephemeral=True)

    @discord.ui.button(
        emoji="🚫",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_untrust",
        row=1
    )
    async def untrust_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Untrust a user."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = UserActionSelectView(self.cog, channel, action="untrust")
        await interaction.response.send_message("اختر العضو الذي تريد **إلغاء الثقة** عنه:", view=view, ephemeral=True)

    @discord.ui.button(
        emoji="📞",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_invite",
        row=1
    )
    async def invite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Invite a user to voice channel."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = UserActionSelectView(self.cog, channel, action="invite")
        await interaction.response.send_message("اختر العضو الذي تريد **دعوته** للروم:", view=view, ephemeral=True)

    @discord.ui.button(
        emoji="👢",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_kick",
        row=1
    )
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Kick a user from voice channel."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = UserActionSelectView(self.cog, channel, action="kick")
        await interaction.response.send_message("اختر العضو الذي تريد **طرده** من الروم:", view=view, ephemeral=True)

    @discord.ui.button(
        emoji="🌍",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_region",
        row=1
    )
    async def region_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Change voice RTC region."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = RegionSelectView(self.cog, channel)
        await interaction.response.send_message("اختر منطقة الصوت (Voice Region):", view=view, ephemeral=True)

    # ==================== Row 2 ====================

    @discord.ui.button(
        emoji="⛔",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_block",
        row=2
    )
    async def block_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Block a user from voice room."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = UserActionSelectView(self.cog, channel, action="block")
        await interaction.response.send_message("اختر العضو الذي تريد **حظره** من الروم:", view=view, ephemeral=True)

    @discord.ui.button(
        emoji="✅",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_unblock",
        row=2
    )
    async def unblock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Unblock a user."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = UserActionSelectView(self.cog, channel, action="unblock")
        await interaction.response.send_message("اختر العضو الذي تريد **إلغاء حظره**:", view=view, ephemeral=True)

    @discord.ui.button(
        emoji="👑",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_claim",
        row=2
    )
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Claim ownership if original owner left."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=False)
        if not channel:
            return

        is_owner = await self.cog.channel_manager.is_channel_owner(channel, interaction.user)
        if is_owner:
            await interaction.response.send_message("👑 أنت بالفعل مالك هذا الروم!", ephemeral=True)
            return

        can_claim = await self.cog.channel_manager.can_claim_channel(channel, interaction.user)
        if not can_claim:
            await interaction.response.send_message(
                "❌ لا يمكنك أخذ الملكية بينما المالك الحالي لا يزال موجوداً في الروم!",
                ephemeral=True
            )
            return

        success = await self.cog.channel_manager.transfer_ownership(channel, interaction.user)
        if success:
            await interaction.response.send_message(
                f"🎉 تمت المطالبة بالملكية بنجاح بواسطة {interaction.user.mention}!",
                ephemeral=True
            )
            try:
                await channel.send(f"👑 أصبح {interaction.user.mention} المالك الجديد للروم الصوتي!")
            except (discord.HTTPException, discord.Forbidden):
                pass
        else:
            await interaction.response.send_message("❌ فشل نقل الملكية.", ephemeral=True)

    @discord.ui.button(
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_transfer",
        row=2
    )
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Transfer ownership to another user."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return
        view = UserActionSelectView(self.cog, channel, action="transfer")
        await interaction.response.send_message("اختر العضو الذي تريد **نقل الملكية** إليه:", view=view, ephemeral=True)

    @discord.ui.button(
        emoji="🗑️",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_control_delete",
        row=2
    )
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete temporary channel immediately."""
        channel = await validate_owner_interaction(interaction, self.cog, require_owner=True)
        if not channel:
            return

        await interaction.response.send_message("🗑️ جاري حذف الروم الصوتي الخاص بك...", ephemeral=True)
        await self.cog.channel_manager.delete_temp_channel(channel)


class NameModal(discord.ui.Modal, title="تغيير اسم الروم"):
    name_input = discord.ui.TextInput(
        label="الاسم الجديد",
        placeholder="أدخل اسم الروم الجديد...",
        min_length=1,
        max_length=100,
        required=True
    )

    def __init__(self, cog, channel: discord.VoiceChannel):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.name_input.default = channel.name

    async def on_submit(self, interaction: discord.Interaction):
        new_name = str(self.name_input.value).strip()
        if not new_name:
            await interaction.response.send_message("❌ اسم الروم لا يمكن أن يكون فارغاً!", ephemeral=True)
            return

        success, message = await self.cog.channel_manager.rename_channel(self.channel, new_name)
        if success:
            await interaction.response.send_message(f"✅ تم تغيير اسم الروم إلى: **{new_name}**", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {message}", ephemeral=True)


class LimitModal(discord.ui.Modal, title="تحديد عدد الأعضاء"):
    limit_input = discord.ui.TextInput(
        label="الحد الأقصى (0 لغير محدود، 1-99)",
        placeholder="أدخل رقماً بين 0 و 99...",
        min_length=1,
        max_length=2,
        required=True
    )

    def __init__(self, cog, channel: discord.VoiceChannel):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.limit_input.default = str(channel.user_limit)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(str(self.limit_input.value).strip())
            if not (0 <= limit <= 99):
                await interaction.response.send_message("❌ يجب أن يكون الحد رقماً بين 0 و 99.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ يرجى إدخال رقم صحيح (0-99).", ephemeral=True)
            return

        success = await self.cog.channel_manager.set_user_limit(self.channel, limit)
        if success:
            limit_desc = "غير محدود (Unlimited)" if limit == 0 else f"{limit} أعضاء"
            await interaction.response.send_message(f"✅ تم تعديل حد الأعضاء إلى: **{limit_desc}**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ فشل تعديل حد الأعضاء.", ephemeral=True)


class TopicModal(discord.ui.Modal, title="موضوع الروم الصوتي"):
    topic_input = discord.ui.TextInput(
        label="موضوع أو حالة الروم (Room Topic / Status)",
        placeholder="أدخل موضوع النقاش أو حالة الروم...",
        min_length=1,
        max_length=100,
        required=True
    )

    def __init__(self, cog, channel: discord.VoiceChannel):
        super().__init__()
        self.cog = cog
        self.channel = channel
        if hasattr(channel, "status") and channel.status:
            self.topic_input.default = channel.status
        else:
            self.topic_input.default = channel.name

    async def on_submit(self, interaction: discord.Interaction):
        topic = str(self.topic_input.value).strip()
        if not topic:
            await interaction.response.send_message("❌ لا يمكن أن يكون الموضوع فارغاً!", ephemeral=True)
            return

        success, message = await self.cog.channel_manager.create_voice_discussion(self.channel, topic)
        if success:
            await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)


class UserActionSelectView(discord.ui.View):
    """Interactive UserSelect menu for Trust, Untrust, Invite, Kick, Block, Unblock, and Transfer."""

    def __init__(self, cog, channel: discord.VoiceChannel, action: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.channel = channel
        self.action = action

        self.user_select = discord.ui.UserSelect(
            placeholder="اختر عضواً من القائمة...",
            min_values=1,
            max_values=1
        )
        self.user_select.callback = self.select_callback
        self.add_item(self.user_select)

    async def select_callback(self, interaction: discord.Interaction):
        target = self.user_select.values[0]
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id)

        if not target:
            await interaction.response.send_message("❌ لم يتم العثور على العضو في السيرفر.", ephemeral=True)
            return

        if target.id == interaction.user.id:
            await interaction.response.send_message("❌ لا يمكنك تطبيق هذا الإجراء على نفسك!", ephemeral=True)
            return

        if target.bot:
            await interaction.response.send_message("❌ لا يمكن تحديد البوتات لهذا الإجراء.", ephemeral=True)
            return

        if self.action == "trust":
            success = await self.cog.channel_manager.trust_user(self.channel, target)
            msg = f"🔰 أصبح {target.mention} الآن **عضواً موثوقاً** في رومك."
        elif self.action == "untrust":
            success = await self.cog.channel_manager.untrust_user(self.channel, target)
            msg = f"🚫 تم **إلغاء الثقة** عن {target.mention}."
        elif self.action == "invite":
            await self.cog.channel_manager.trust_user(self.channel, target)
            invite = await self.channel.create_invite(max_age=3600, max_uses=1, reason="Temp Voice invite")
            dm_sent = False
            try:
                await target.send(
                    f"📬 دعاك **{interaction.user.display_name}** للانضمام إلى رومه الصوتي في سيرفر **{interaction.guild.name}**!\n"
                    f"رابط الانضمام: {invite.url}"
                )
                dm_sent = True
            except (discord.HTTPException, discord.Forbidden):
                pass
            msg = f"📬 تم إرسال دعوة إلى {target.mention}!" + (" (وصلته بالخاص)" if dm_sent else f"\nرابط الروم: {invite.url}")
            success = True
        elif self.action == "block":
            success = await self.cog.channel_manager.block_user(self.channel, target)
            msg = f"⛔ تم **حظر** {target.mention} من الروم."
        elif self.action == "unblock":
            success = await self.cog.channel_manager.unblock_user(self.channel, target)
            msg = f"✅ تم **إلغاء الحظر** عن {target.mention}."
        elif self.action == "kick":
            success = await self.cog.channel_manager.kick_user(self.channel, target)
            msg = f"👢 تم **طرد** {target.mention} من الروم."
            if not success:
                msg = f"❌ {target.mention} غير متواجد حالياً داخل الروم."
        elif self.action == "transfer":
            success = await self.cog.channel_manager.transfer_ownership(self.channel, target)
            msg = f"👑 تم نقل ملكية الروم إلى {target.mention}!"
            if success:
                try:
                    await self.channel.send(f"👑 قام {interaction.user.mention} بنقل ملكية الروم إلى {target.mention}!")
                except (discord.HTTPException, discord.Forbidden):
                    pass
        else:
            success = False
            msg = "❌ إجراء غير معروف."

        if success:
            await interaction.response.edit_message(content=msg, view=None)
        else:
            await interaction.response.edit_message(content=f"❌ تعذر تنفيذ الإجراء: {msg}", view=None)


class RegionSelectView(discord.ui.View):
    """Voice Region selection dropdown."""

    def __init__(self, cog, channel: discord.VoiceChannel):
        super().__init__(timeout=60)
        self.cog = cog
        self.channel = channel

        options = [
            discord.SelectOption(label="Automatic (تلقائي)", value="auto", description="أفضل منطقة صوت يحددها ديسكورد", emoji="🌐"),
            discord.SelectOption(label="Europe (أوروبا)", value="rotterdam", description="سيرفرات أوروبا", emoji="🇪🇺"),
            discord.SelectOption(label="US East (شرق أمريكا)", value="us-east", description="الولايات المتحدة الشرقية", emoji="🇺🇸"),
            discord.SelectOption(label="US West (غرب أمريكا)", value="us-west", description="الولايات المتحدة الغربية", emoji="🇺🇸"),
            discord.SelectOption(label="Singapore (سنغافورة)", value="singapore", description="سيرفرات آسيا / سنغافورة", emoji="🇸🇬"),
            discord.SelectOption(label="India (الهند)", value="india", description="سيرفرات الهند", emoji="🇮🇳"),
            discord.SelectOption(label="Brazil (البرازيل)", value="brazil", description="سيرفرات أمريكا الجنوبية", emoji="🇧🇷"),
        ]
        self.select = discord.ui.Select(placeholder="اختر منطقة الصوت المناسبة...", options=options)
        self.select.callback = self.region_callback
        self.add_item(self.select)

    async def region_callback(self, interaction: discord.Interaction):
        choice = self.select.values[0]
        region_val = None if choice == "auto" else choice
        success = await self.cog.channel_manager.set_voice_region(self.channel, region_val)
        if success:
            label = "Automatic (تلقائي)" if region_val is None else choice.title()
            await interaction.response.edit_message(content=f"🌍 تم تغيير منطقة الصوت إلى: **{label}**", view=None)
        else:
            await interaction.response.edit_message(content="❌ تعذر تغيير منطقة الصوت.", view=None)


async def create_control_interface(control_channel: discord.TextChannel, cog) -> discord.Message:
    """Create and post the persistent central control dashboard matching the exact reference image."""
    embed = discord.Embed(
        title="TempVoice Interface",
        description="يمكنك استخدام voice/ الأوامر للتحكم في الروم الخاص بك الصوتي المؤقت. المزيد من الخيارات متاحة من خلال هذه",
        color=DISCORD_PINK
    )
    embed.set_footer(text="يمكن استخدام هذه الواجهة بالنقر فوق الأزرار أدناه")

    banner_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "attached_assets", "banner.png")
    view = ControlView(cog)

    if SHOW_BANNER_IMAGE and os.path.exists(banner_path):
        banner_file = discord.File(banner_path, filename="banner.png")
        embed.set_image(url="attachment://banner.png")
        message = await control_channel.send(file=banner_file, embed=embed, view=view)
    else:
        # Clean text legend layout if banner image is disabled
        embed.add_field(
            name="⚙️ إعدادات الروم",
            value="🔀 **تغيير اسم** • 👥 **حد الأعضاء** • 🛡️ **خصوصية قناتك** • 🕔 **غرفة الانتظار** • 💬 **موضوع**",
            inline=False
        )
        embed.add_field(
            name="👥 إدارة الأعضاء والمنطقة",
            value="👤 **الثقة** • 🚫 **عدم الثقة** • 📞 **دعوة** • 👢 **طرد** • 🌍 **تغيير منطقة**",
            inline=False
        )
        embed.add_field(
            name="👑 الملكية والحظر",
            value="⛔ **حظر** • ✅ **رفع الحظر** • 👑 **اخذ الملكية** • 🔄 **نقل ملكية** • 🗑️ **إلغاء**",
            inline=False
        )
        message = await control_channel.send(embed=embed, view=view)

    await cog.db.set_control_panel(control_channel.guild.id, control_channel.id, message.id)
    return message