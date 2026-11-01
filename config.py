import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Database configuration
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tempvoice.db")

# Color constants
DISCORD_PRIMARY = 0x5865F2    # Blurple
DISCORD_SECONDARY = 0x2B2D31  # Dark theme surface
DISCORD_SUCCESS = 0x57F287    # Green
DISCORD_DANGER = 0xED4245     # Red
DISCORD_WHITE = 0xFFFFFF      # White
DISCORD_PINK = 0xEB459E       # Signature TempVoice Hot Pink

# Interface configuration
SHOW_BANNER_IMAGE = True      # Set to False if you prefer text-only without banner image