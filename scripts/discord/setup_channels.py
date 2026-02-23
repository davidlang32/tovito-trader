"""
TOVITO TRADER - Discord Channel Setup

Posts pinnable welcome/about/FAQ content to Discord channels via webhooks.
Run once per channel to seed the initial content, then pin the messages manually.

Usage:
    python scripts/discord/setup_channels.py --channel about     # Post About content
    python scripts/discord/setup_channels.py --channel faq       # Post FAQ content
    python scripts/discord/setup_channels.py --channel rules     # Post Rules & Disclaimers
    python scripts/discord/setup_channels.py --channel all       # Post all content
    python scripts/discord/setup_channels.py --list              # Show available channels

Each channel requires its own webhook URL in .env:
    DISCORD_WELCOME_WEBHOOK_URL=...
    DISCORD_ABOUT_WEBHOOK_URL=...
    DISCORD_FAQ_WEBHOOK_URL=...
    DISCORD_RULES_WEBHOOK_URL=...

Or use a single webhook and post to the same channel:
    python scripts/discord/setup_channels.py --channel about --webhook <URL>
"""

import sys
import os
import argparse
import logging
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")

from src.utils.discord import post_embed, post_embeds, make_embed, COLORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("channel_setup")


# ---------------------------------------------------------------------------
# Channel content definitions
# ---------------------------------------------------------------------------

def get_welcome_embeds() -> list:
    """Content for #welcome channel — first thing new members see."""
    return [
        make_embed(
            title="\u26A1 Welcome to Tovito Trader",
            color=COLORS["gold"],
            description=(
                "**Your money should work harder than you do.**\n\n"
                "Tovito Trader is a pooled investment fund built on one idea: "
                "**momentum doesn't lie.** We ride the wave when the market shows "
                "its hand — and we get out before it pulls the rug.\n\n"
                "No guessing. No hoping. Just disciplined, data-driven trading."
            ),
        ),
        make_embed(
            title="\U0001F4A1 How It Works — 30 Seconds",  # 💡
            color=COLORS["blue"],
            description=(
                "**1.** You invest \u2192 you get shares in the fund\n"
                "**2.** We trade momentum strategies on your behalf\n"
                "**3.** Your share value updates daily at market close\n"
                "**4.** Withdraw anytime — your money stays liquid\n\n"
                "That's it. No lockups. No mystery. You see every trade we make, live."
            ),
        ),
        make_embed(
            title="\U0001F5FA\uFE0F Find Your Way Around",  # 🗺️
            color=COLORS["purple"],
            description=(
                "\U0001F4CC **You are here** — check the pinned message above for "
                "live fund performance and NAV chart\n\n"
                "\U0001F4D6 **#about-tovito** — deep dive into the fund, our strategy, "
                "and what's coming next\n\n"
                "\u2753 **#faq** — answers to the questions everyone asks\n\n"
                "\U0001F4DC **#rules-and-disclaimers** — the fine print (yes, read it)\n\n"
                "\U0001F4E2 **#announcements** — fund updates, new offerings, milestones\n\n"
                "\U0001F4B9 **#tovito-trader-trades** — every trade, in real time, as it happens\n\n"
                "\U0001F6A8 **#portfolio-alerts** — market alerts and position updates"
            ),
        ),
        make_embed(
            title="\U0001F680 Ready to Invest?",  # 🚀
            color=COLORS["green"],
            description=(
                "Interested in putting your money to work? Here's how to get started:\n\n"
                "**1.** Read through **#about-tovito** and **#faq**\n"
                "**2.** Review **#rules-and-disclaimers**\n"
                "**3.** Reach out to the fund manager directly\n\n"
                "We keep things transparent. Watch the trades. Watch the NAV. "
                "Then decide for yourself."
            ),
        ),
    ]


def get_about_embeds() -> list:
    """Content for #about-tovito channel."""
    return [
        make_embed(
            title="\U0001F4B0 Welcome to Tovito Trader",  # 💰
            color=COLORS["gold"],
            description=(
                "Tovito Trader is a **pooled investment fund** that uses "
                "**momentum trading** strategies on behalf of its investors. "
                "Think of it like a private mutual fund — your money is combined "
                "with other investors, and a professional fund manager actively "
                "trades the portfolio to capture price momentum in the market."
            ),
        ),
        make_embed(
            title="\U0001F680 Momentum Trading",  # 🚀
            color=COLORS["purple"],
            description=(
                "Our strategy focuses on identifying and riding **price momentum** — "
                "entering positions as trends develop and exiting as they fade. "
                "This means we hold positions from hours to days, capturing the "
                "meat of a move rather than chasing every tick.\n\n"
                "Momentum trading sits between day trading and swing trading, "
                "balancing active management with disciplined patience."
            ),
        ),
        make_embed(
            title="\U0001F4C8 How It Works",  # 📈
            color=COLORS["blue"],
            fields=[
                {
                    "name": "Share-Based System",
                    "value": (
                        "Each investor owns **shares** in the fund. "
                        "As the portfolio grows, your shares increase in value. "
                        "The price per share (NAV) is calculated daily after market close."
                    ),
                    "inline": False,
                },
                {
                    "name": "Daily NAV Update",
                    "value": (
                        "Every trading day at ~4:05 PM ET, the fund's Net Asset Value "
                        "is recalculated based on the total portfolio value divided by "
                        "total shares outstanding."
                    ),
                    "inline": False,
                },
                {
                    "name": "Contributions & Withdrawals",
                    "value": (
                        "Investors can contribute or withdraw funds at any time. "
                        "Shares are issued or redeemed at the current NAV per share."
                    ),
                    "inline": False,
                },
            ],
        ),
        make_embed(
            title="\U0001F916 Live Trade Notifications",  # 🤖
            color=COLORS["green"],
            description=(
                "The **#tovito-trader-trades** channel shows every trade in real time "
                "as it happens during market hours.\n\n"
                "\U0001F7E2 **Green** = Opening a new position\n"
                "\U0001F534 **Red** = Closing a position\n\n"
                "Each notification includes the symbol, action, quantity, price, "
                "and which brokerage executed the trade."
            ),
        ),
        make_embed(
            title="\U0001F52E What's Ahead",  # 🔮
            color=COLORS["gold"],
            description=(
                "Tovito Trader's momentum fund is just the beginning. "
                "Future fund offerings under consideration include:\n\n"
                "\U0001F4C8 **Long-Term Investing**\n"
                "\U0001F4B5 **Dividends**\n"
                "\u26A1 **Day Trading**\n"
                "\U0001F4CA **Option Selling**\n"
                "\U0001F4C9 **Futures**\n"
                "\U0001FA99 **Cryptocurrency**\n\n"
                "Stay tuned — announcements will be posted as new funds become available."
            ),
        ),
    ]


def get_faq_embeds() -> list:
    """Content for #faq channel."""
    return [
        make_embed(
            title="\u2753 Frequently Asked Questions",  # ❓
            color=COLORS["purple"],
            description="Common questions about investing with Tovito Trader.",
        ),
        make_embed(
            title="How is my investment valued?",
            color=COLORS["blue"],
            description=(
                "Your investment value = **your shares x current NAV per share**. "
                "The NAV (Net Asset Value) is updated daily after market close, "
                "reflecting the total portfolio value divided by all shares outstanding."
            ),
        ),
        make_embed(
            title="How do contributions work?",
            color=COLORS["blue"],
            description=(
                "When you contribute funds, you receive new shares at the current "
                "NAV per share. For example, if NAV is $10.50 and you contribute "
                "$1,050, you receive 100 new shares."
            ),
        ),
        make_embed(
            title="How do withdrawals work?",
            color=COLORS["blue"],
            description=(
                "Withdrawals redeem your shares at the current NAV. A 37% tax is "
                "withheld on any realized gains (the difference between your "
                "withdrawal value and your cost basis for those shares)."
            ),
        ),
        make_embed(
            title="How often can I contribute or withdraw?",
            color=COLORS["blue"],
            description=(
                "Contributions and withdrawals can be requested at any time. "
                "Processing typically occurs within 1-2 business days after "
                "funds are received or the request is approved."
            ),
        ),
        make_embed(
            title="What does the fund trade?",
            color=COLORS["blue"],
            description=(
                "The fund trades **equities and options** on US markets using a "
                "**momentum trading** strategy. We identify developing price trends "
                "and ride them — holding positions from hours to days based on "
                "market conditions. Active risk management is applied to every position."
            ),
        ),
        make_embed(
            title="Will there be other funds?",
            color=COLORS["blue"],
            description=(
                "Yes — additional fund offerings are under consideration, including "
                "long-term investing, dividends, day trading, option selling, futures, "
                "and cryptocurrency. No launch dates have been set. Announcements will "
                "be made in **#announcements** as new funds become available."
            ),
        ),
        make_embed(
            title="How are taxes handled?",
            color=COLORS["blue"],
            description=(
                "Tovito Trader is a **pass-through tax entity**. Gains flow to the "
                "fund manager's personal income and are taxed at the 37% federal rate. "
                "Tax withholding is applied at the time of withdrawal on any realized gains."
            ),
        ),
    ]


def get_rules_embeds() -> list:
    """Content for #rules-and-disclaimers channel."""
    return [
        make_embed(
            title="\U0001F4DC Server Rules & Disclaimers",  # 📜
            color=COLORS["orange"],
            description="Please read before participating in this server.",
        ),
        make_embed(
            title="\u2696\uFE0F Investment Disclaimers",  # ⚖️
            color=COLORS["red"],
            fields=[
                {
                    "name": "Not Financial Advice",
                    "value": (
                        "Nothing shared in this server constitutes financial advice. "
                        "Trade notifications are for **transparency purposes only** and "
                        "should not be interpreted as buy/sell recommendations."
                    ),
                    "inline": False,
                },
                {
                    "name": "Risk of Loss",
                    "value": (
                        "All investments carry risk, including the potential loss of "
                        "principal. Past performance does not guarantee future results. "
                        "Active trading involves substantial risk."
                    ),
                    "inline": False,
                },
                {
                    "name": "Confidentiality",
                    "value": (
                        "Individual investor account details, balances, and personal "
                        "information are never shared publicly. Only aggregate fund "
                        "performance is discussed in this server."
                    ),
                    "inline": False,
                },
            ],
        ),
        make_embed(
            title="\U0001F4CB Community Guidelines",  # 📋
            color=COLORS["blue"],
            fields=[
                {
                    "name": "1. Respect Privacy",
                    "value": "Never share other investors' personal or financial information.",
                    "inline": False,
                },
                {
                    "name": "2. No Solicitation",
                    "value": "Do not promote other investment services or solicit members.",
                    "inline": False,
                },
                {
                    "name": "3. Questions Welcome",
                    "value": "Ask questions about the fund, trades, or strategy at any time.",
                    "inline": False,
                },
                {
                    "name": "4. Be Professional",
                    "value": "This is a professional investment community. Keep discussions constructive.",
                    "inline": False,
                },
            ],
        ),
    ]


CHANNEL_MAP = {
    "welcome": {
        "name": "Welcome",
        "env_key": "DISCORD_WELCOME_WEBHOOK_URL",
        "builder": get_welcome_embeds,
    },
    "about": {
        "name": "About Tovito",
        "env_key": "DISCORD_ABOUT_WEBHOOK_URL",
        "builder": get_about_embeds,
    },
    "faq": {
        "name": "FAQ",
        "env_key": "DISCORD_FAQ_WEBHOOK_URL",
        "builder": get_faq_embeds,
    },
    "rules": {
        "name": "Rules & Disclaimers",
        "env_key": "DISCORD_RULES_WEBHOOK_URL",
        "builder": get_rules_embeds,
    },
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Post channel setup content to Discord")
    parser.add_argument(
        "--channel",
        choices=list(CHANNEL_MAP.keys()) + ["all"],
        help="Which channel content to post",
    )
    parser.add_argument("--webhook", type=str, help="Override webhook URL")
    parser.add_argument("--list", action="store_true", help="List available channels")
    args = parser.parse_args()

    if args.list:
        print("Available channels:")
        for key, info in CHANNEL_MAP.items():
            env = info["env_key"]
            url = os.getenv(env, "")
            status = "configured" if url else "not configured"
            print(f"  {key:8s}  {info['name']:25s}  env: {env} ({status})")
        return

    if not args.channel:
        parser.print_help()
        return

    channels = list(CHANNEL_MAP.keys()) if args.channel == "all" else [args.channel]

    for channel_key in channels:
        info = CHANNEL_MAP[channel_key]
        webhook = args.webhook or os.getenv(info["env_key"], "")

        if not webhook:
            logger.warning(
                "Skipping %s — no webhook. Set %s or use --webhook",
                info["name"],
                info["env_key"],
            )
            continue

        embeds = info["builder"]()
        logger.info("Posting %d embeds to %s...", len(embeds), info["name"])

        success = post_embeds(webhook, embeds)
        if success:
            logger.info("[OK] %s content posted", info["name"])
        else:
            logger.error("[FAIL] Could not post %s content", info["name"])


if __name__ == "__main__":
    main()
