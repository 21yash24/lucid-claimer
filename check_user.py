import asyncio
import discord
import config

TARGET = "leothetiger"
GUILD_NAME = "LUCID"  # case-insensitive match on the server name


async def main():
    client = discord.Client()
    found = []
    scanned = 0

    @client.event
    async def on_ready():
        nonlocal found, scanned
        print(f"Logged in as {client.user}")
        for guild in client.guilds:
            if GUILD_NAME.lower() not in guild.name.lower():
                continue
            for member in guild.members:
                scanned += 1
                names = {member.name.lower(), member.display_name.lower()}
                global_names = {g.lower() for g in (getattr(member, "global_name", None) or [])}
                if TARGET in names or TARGET in global_names:
                    found.append((guild.name, member.name, member.display_name))
        print(f"Scanned {scanned} members in '{GUILD_NAME}' server.")
        if found:
            print(f"MATCH(es) for '{TARGET}':")
            for g, n, d in found:
                print(f"  - server: {g} | username: {n} | display: {d}")
        else:
            print(f"No member named '{TARGET}' found in the {GUILD_NAME} server.")
        await client.close()

    await client.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
