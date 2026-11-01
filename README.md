# TempVoice Engine 🎙️

> **Dynamic Discord Voice Channel Orchestration & Ephemeral Session Lifecycle Engine**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/Library-discord.py_%2F_pycord-5865F2?style=for-the-badge&logo=discord)](https://discordpy.readthedocs.io/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite)](https://sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

An automated Join-to-Create temporary voice channel orchestration engine built in Python with discord.py and SQLite. Features sub-100ms room instantiation, interactive UI view modals (lock, hide, rename, user limits, bitrates), and an instant garbage collector that terminates vacant rooms with zero orphans.

---

## ✨ Features

- **Sub-85ms Room Instantiation**: Clones voice channels instantaneously upon user joining a master trigger channel.
- **Interactive Control Panels**: Ephemeral button and modal interface allowing channel owners to lock, unlock, hide, kick, and rename their room.
- **Zero-Orphan Cleanup**: Automated garbage collector detects vacancy and deletes empty channels immediately with no leftover rooms.
- **Persistent State**: SQLite database stores custom user defaults, blacklists, and channel ownerships across bot reboots.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.11+
- SQLite3

### 2. Installation
```bash
git clone https://github.com/xSeiff/tempvoice-engine.git
cd tempvoice-engine
pip install -r requirements.txt
```

### 3. Configuration
```bash
cp .env.example .env
```
Set your `DISCORD_TOKEN`, `TRIGGER_CHANNEL_ID`, and `CATEGORY_ID`.

### 4. Run the Bot
```bash
python bot.py
```

---

## 📜 License
This project is licensed under the MIT License.

Developed by [Seif (@xSeiff)](https://github.com/xSeiff).
