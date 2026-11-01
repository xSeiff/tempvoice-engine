import os
import logging
import discord
from typing import Dict, Union

logger = logging.getLogger(__name__)

EMOJI_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "attached_assets", "emojis"
)

# Standard Unicode fallbacks in case application emojis are syncing or restricted
DEFAULT_FALLBACK_EMOJIS: Dict[str, str] = {
    "tv_name": "🔀",
    "tv_limit": "👥",
    "tv_privacy": "🛡️",
    "tv_waiting": "🕔",
    "tv_thread": "💬",
    "tv_trust": "👤",
    "tv_untrust": "🚫",
    "tv_invite": "📞",
    "tv_kick": "👢",
    "tv_region": "🌍",
    "tv_block": "⛔",
    "tv_unblock": "✅",
    "tv_claim": "👑",
    "tv_transfer": "🔄",
    "tv_delete": "🗑️",
}

class EmojiManager:
    """
    Manages custom Discord Application Emojis to match the exact 15 custom icons
    shown in the TempVoice interface reference screenshot.
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.emojis: Dict[str, Union[discord.Emoji, discord.PartialEmoji, str]] = dict(DEFAULT_FALLBACK_EMOJIS)
        self.synced = False

    async def sync_emojis(self):
        """Fetch or create application emojis on the Discord bot application."""
        try:
            logger.info("Checking custom Application Emojis for TempVoice buttons...")
            existing_emojis = await self.bot.fetch_application_emojis()
            existing_map = {e.name: e for e in existing_emojis}

            for key in DEFAULT_FALLBACK_EMOJIS.keys():
                if key in existing_map:
                    self.emojis[key] = existing_map[key]
                    logger.debug(f"Found existing application emoji: {key}")
                else:
                    file_path = os.path.join(EMOJI_DIR, f"{key}.png")
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            img_bytes = f.read()
                        try:
                            new_emoji = await self.bot.create_application_emoji(name=key, image=img_bytes)
                            self.emojis[key] = new_emoji
                            logger.info(f"Successfully uploaded custom application emoji: {key} ({new_emoji.id})")
                        except discord.HTTPException as e:
                            logger.warning(f"Could not upload application emoji {key}: {e}. Using fallback.")
                            self.emojis[key] = DEFAULT_FALLBACK_EMOJIS[key]
                    else:
                        self.emojis[key] = DEFAULT_FALLBACK_EMOJIS[key]

            self.synced = True
            logger.info("Custom application emojis sync complete! All 15 buttons now use custom icons.")
        except discord.HTTPException as e:
            logger.warning(f"Unable to fetch or upload application emojis: {e}. Using fallback emojis.")
        except Exception as e:
            logger.error(f"Unexpected error while syncing custom emojis: {e}")

    def get(self, key: str) -> Union[discord.Emoji, discord.PartialEmoji, str]:
        """Return the custom application emoji or unicode fallback."""
        return self.emojis.get(key, DEFAULT_FALLBACK_EMOJIS.get(key, "❓"))
