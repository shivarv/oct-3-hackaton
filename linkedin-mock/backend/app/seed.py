"""Demo data.

Every demo member logs in with their lowercase first name as username and the password "test".

    python -m app.seed            # update existing demo members in place (skips SKIP_PROFILE_FOR)
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from .auth import hash_password

DEMO_PASSWORD = "test"

# Members whose profile details are never overwritten by the update command (login is still set).
SKIP_PROFILE_FOR = {"Shiva"}

DEMO_MEMBERS: list[dict[str, Any]] = [
    {
        "name": "Ada Lovelace",
        "headline": "Lead Algorithm Engineer · Analytical Engines Ltd",
        "location": "London, UK",
        "about": (
            "I write programs for machines that don't quite exist yet. Published the first "
            "algorithm intended for a computing machine (Note G, Bernoulli numbers).\n\n"
            "Interests: poetical science, mathematics, music generation, horses."
        ),
        "phone": "+44 20 7946 0101",
        "gender": "female",
        "date_of_birth": "1990-12-10",
    },
    {
        "name": "Alan Turing",
        "headline": "Mathematician & Codebreaker",
        "location": "Manchester, UK",
        "about": "Computability, morphogenesis and long-distance running.",
        "phone": "+44 161 496 0102",
        "gender": "male",
        "date_of_birth": "1988-06-23",
    },
    {
        "name": "Grace Hopper",
        "headline": "Rear Admiral · Compiler Pioneer · COBOL co-designer",
        "location": "Arlington, VA",
        "about": (
            "Built the first compiler and helped design COBOL. I keep a clock on my wall that "
            "runs counter-clockwise, because the most dangerous phrase is \"we've always done "
            "it this way.\"\n\nHappy to talk about nanoseconds, debugging and mentoring."
        ),
        "phone": "+1 703 555 0103",
        "gender": "female",
        "date_of_birth": "1986-12-09",
    },
    {
        "name": "Linus Torvalds",
        "headline": "Creator of Linux and Git · Kernel Maintainer",
        "location": "Portland, OR",
        "about": (
            "Started Linux as a hobby project in 1991 and wrote Git when we needed a better "
            "version control system.\n\nTalk is cheap. Show me the code."
        ),
        "phone": "+1 503 555 0104",
        "gender": "male",
        "date_of_birth": "1989-12-28",
    },
    {
        "name": "Margaret Hamilton",
        "headline": "Director of Software Engineering · Apollo Flight Software",
        "location": "Cambridge, MA",
        "about": (
            "Led the team that wrote the on-board flight software for Apollo. Coined the term "
            "\"software engineering\" so the discipline would get the respect it deserves.\n\n"
            "Focus areas: ultra-reliable systems, error detection and recovery, priority scheduling."
        ),
        "phone": "+1 617 555 0105",
        "gender": "female",
        "date_of_birth": "1986-08-17",
    },
]

POSTS = [
    ("Ada Lovelace", "Excited to share that my notes on the Analytical Engine are finally published! "
                     "Note G includes an algorithm for Bernoulli numbers. Feedback welcome."),
    ("Alan Turing", "Can machines think? I've proposed an imitation game to find out. "
                    "Would love to hear how others would design the test."),
    ("Grace Hopper", "Found an actual bug in the Mark II today. Taped it into the logbook. #debugging"),
    ("Linus Torvalds", "Just a hobby project, won't be big and professional. Anyway, here's the first release."),
    ("Margaret Hamilton", "Proud of the team: the software handled the 1202 alarms gracefully during "
                          "landing. Priority scheduling for the win."),
]


def age_on(dob: str, today: date) -> int:
    born = date.fromisoformat(dob)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def base_username(name: str) -> str:
    """Lowercase first name, reduced to the characters usernames allow."""
    first = name.split()[0] if name.split() else "member"
    cleaned = re.sub(r"[^a-z0-9_.]", "", first.lower())
    return cleaned if len(cleaned) >= 3 else f"{cleaned}user"


def profile_fields(member: dict[str, Any]) -> dict[str, Any]:
    fields = {k: v for k, v in member.items() if k != "name"}
    fields["age"] = age_on(member["date_of_birth"], datetime.now(UTC).date())
    return fields


async def seed_if_empty(db: AsyncDatabase[dict[str, Any]]) -> None:
    """Insert demo members, connections and posts if the users collection is empty."""
    if await db.users.count_documents({}, limit=1):
        return

    now = datetime.now(UTC)
    password_hash = await hash_password(DEMO_PASSWORD)
    ids = [ObjectId() for _ in DEMO_MEMBERS]
    by_name = {m["name"]: ids[i] for i, m in enumerate(DEMO_MEMBERS)}
    await db.users.insert_many(
        [
            {
                "_id": ids[i],
                "name": m["name"],
                "username": base_username(m["name"]),
                "password_hash": password_hash,
                **profile_fields(m),
                # Everyone starts connected to their neighbours in the list.
                "connections": [ids[(i - 1) % len(ids)], ids[(i + 1) % len(ids)]],
                "created_at": now,
            }
            for i, m in enumerate(DEMO_MEMBERS)
        ]
    )

    posts = []
    for n, (author, content) in enumerate(POSTS):
        author_id = by_name[author]
        others = [i for i in ids if i != author_id]
        posts.append(
            {
                "author_id": author_id,
                "content": content,
                "created_at": now - timedelta(hours=3 * (len(POSTS) - n)),
                "likes": others[:2],
                "comments": [
                    {
                        "_id": ObjectId(),
                        "author_id": others[0],
                        "text": "Congrats, this is great!",
                        "created_at": now - timedelta(hours=3 * (len(POSTS) - n) - 1),
                    }
                ],
            }
        )
    await db.posts.insert_many(posts)


async def update_existing(db: AsyncDatabase[dict[str, Any]]) -> None:
    """Give every member a login (first name / "test") and fill in demo profiles.

    Profiles of members in SKIP_PROFILE_FOR are left untouched apart from their login.
    """
    password_hash = await hash_password(DEMO_PASSWORD)
    demo_by_name = {m["name"]: m for m in DEMO_MEMBERS}
    members = await db.users.find({}, {"name": 1}).sort("created_at", 1).to_list(None)

    # Clear old usernames first so renaming can't collide with a value about to be replaced.
    await db.users.update_many({}, {"$unset": {"username": ""}})
    taken: set[str] = set()
    for member in members:
        base = base_username(member["name"])
        username, n = base, 2
        while username in taken:
            username, n = f"{base}{n}", n + 1
        taken.add(username)

        update: dict[str, Any] = {"username": username, "password_hash": password_hash}
        demo = demo_by_name.get(member["name"])
        if demo and member["name"] not in SKIP_PROFILE_FOR:
            update |= profile_fields(demo)
        await db.users.update_one({"_id": member["_id"]}, {"$set": update})

        note = "login only" if member["name"] in SKIP_PROFILE_FOR or not demo else "login + profile"
        print(f"{member['name']:<20} username={username:<12} ({note})")

    # Old sessions belonged to the previous login scheme; force everyone to log in again.
    await db.sessions.delete_many({})


async def _main() -> None:
    from .db import mongo

    await mongo.connect()
    await mongo.ensure_indexes()
    try:
        await update_existing(mongo.db)
    finally:
        await mongo.close()


if __name__ == "__main__":
    asyncio.run(_main())
