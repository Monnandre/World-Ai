
import os

import asyncio, aiofiles
import random

import cv2
import Equirec2Perspec as E2P
import aiohttp
import requests

import discord
from discord.ext import commands
from discord import app_commands

api_key_bot = str(os.environ['api_key_bot'])

command_prefix = "!"
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=command_prefix, intents=intents)

# Set the video filename and parameters
fps = 30
frame_size = (540, 360)  # Width x Height in pixels
fourcc = cv2.VideoWriter_fourcc(*'mp4v')

def get_styles():
    request_url = "https://backend.blockadelabs.com/api/v1/skybox/styles"
    data = {"api_key": os.environ["api_key_ai"]}
    response = requests.get(request_url, json=data)
    result = response.json()

    choices = []
    for style in result:
        choices.append(app_commands.Choice(name=style["name"], value=style["id"]))
    return choices


@bot.event
async def on_ready():
    print('Logged in as :', bot.user.name)
    print('Bot ID :', bot.user.id)
    print('------')

    try:
        await bot.tree.sync()
    except Exception as e:
        print(e)


@bot.event
async def on_command_error(ctx, exc):
    if isinstance(exc, commands.CommandNotFound):
        await ctx.channel.send(f"{command_prefix}help est sans doute nécessaire...")
    if isinstance(exc, commands.MissingRequiredArgument):
        await ctx.channel.send("Il manque un argument...")

@bot.tree.command(name="new_world", description="Create an AI generated world")
@app_commands.describe(prompt="Describe your own world", style="The style of your world")
@app_commands.choices(style=get_styles())
async def world(interaction: discord.Interaction, prompt:str, style: app_commands.Choice[int]):
    if interaction.channel.id == 1082710248160231486:
        await interaction.response.send_message("Proccessing request...", ephemeral=True)
    else:
        await interaction.response.send_message("Wrong channel...", ephemeral=True)
        return
    equ = await get_image(prompt, style.value)

    if equ is None:
        await interaction.channel.send(content="Error getting image")
        return

    video_filename = f'output_video_{prompt}_{random.randint(1, 10_000)}.mp4'
    out = cv2.VideoWriter(video_filename, fourcc, fps, frame_size)

    for angle in range(0, 360):
        frame = equ.GetPerspective(70, angle, 0, frame_size[1], frame_size[0])
        out.write(frame)
    out.release()

    await interaction.channel.send(file=discord.File(video_filename), content=f"{interaction.user.mention}, here is your world! Generated in {style.name} style with prompt: {prompt}")

    os.remove(video_filename)

async def get_image(query, style):
    #send request
    request_url = "https://backend.blockadelabs.com/api/v1/skybox"
    async with aiohttp.ClientSession() as session:
        data = {"api_key": os.environ["api_key_ai"],
                "prompt": query,
                "skybox_style_id": style}
        async with session.post(request_url, json=data) as response:
            result = await response.json()
            status = result["status"]
            id = result["id"]

        while status not in ["complete", "abort", "error"]:
            print(status)
            await asyncio.sleep(10)
            get_url = f"https://backend.blockadelabs.com/api/v1/imagine/requests/{id}"
            data = {"api_key": os.environ["api_key_ai"]}
            async with session.get(get_url, params=data) as response:
                result = await response.json()
                status = result['request']['status']

        if status == "complete":
            filename = f"image_{id}.png"
            async with session.get(result['request']['file_url']) as response:
                async with aiofiles.open(filename, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        await f.write(chunk)

            image = E2P.Equirectangular(filename)
            os.remove(filename)
        else:
            image = None

    return image


bot.run(api_key_bot)
