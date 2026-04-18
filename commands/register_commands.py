import os
import requests
import yaml


TOKEN = os.environ.get("DISCORD_TOKEN")
APPLICATION_ID = os.environ.get("DISCORD_APPLICATION_ID")
GUILD_ID = os.environ.get("DISCORD_GUILD_ID")

if GUILD_ID:
    URL = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/guilds/{GUILD_ID}/commands"
    print(f"Registering guild-scoped commands for guild {GUILD_ID}")
else:
    URL = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"
    print("Registering global commands")


with open("discord_commands.yaml", "r") as file:
    yaml_content = file.read()

commands = yaml.safe_load(yaml_content)
headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}

for command in commands:
    response = requests.post(URL, json=command, headers=headers)
    command_name = command["name"]
    if response.status_code in (200, 201):
        print(f"  {command_name}: OK ({response.status_code})")
    else:
        print(f"  {command_name}: FAILED ({response.status_code}) {response.text}")
