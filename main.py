from interactions import Client, Intents, listen, slash_command, slash_option, OptionType, SlashContext, AutocompleteContext
from interactions.api.events import MessageCreate
from interactions.api.voice.audio import Audio
import os, glob, supabase, storage3.exceptions
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

bot = Client(
    intents=Intents.DEFAULT | Intents.GUILD_MESSAGES | Intents.GUILD_VOICE_STATES,
)

supabase_client: supabase.Client = supabase.create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

music_image = None
music_error_image = None

def setup_bucket():
    try:
        supabase_client.storage.create_bucket(
            "icons",
            options={
                "public": True,
                "allowed_mime_types": ["image/png"],
            }
        )

    except storage3.exceptions.StorageApiError as e:
        if e.code != "Duplicate":
            raise e
        
    # Upload icons to the bucket
    for filename in glob.glob("icons/*.png"):
        name = os.path.basename(filename)
        print(f"Uploading {name} to Supabase")
        with open(filename, "rb") as f:
            supabase_client.storage.from_("icons").upload(name, f, file_options={"content-type": "image/png", "upsert": "true"})

    # Get the public URL for the icons
    global music_image, music_error_image
    music_image = {
        "url": supabase_client.storage.from_("icons").get_public_url("music.png")
    }
    music_error_image = {
        "url": supabase_client.storage.from_("icons").get_public_url("music_error.png")
    }

setup_bucket()


music = {}

for filename in glob.glob("music/*.mp3"):
    name = os.path.splitext(os.path.basename(filename))[0]
    music[name] = filename

@slash_command(
    name="song",
    sub_cmd_name="list",
    sub_cmd_description="List all songs",
)
async def song_list(ctx: SlashContext):
    if not music:
        await ctx.send(embed={
            "thumbnail": music_error_image,
            "title": "Error",
            "description": "No songs found.",
            "color": 0xFF0000
        })
        return
    songs = "\n".join([f"`{s}`" for s in music.keys()])
    await ctx.send(embed={
        "thumbnail": music_image,
        "title": "Songs",
        "description": songs,
        "color": 0x22AAFF
    })


@song_list.subcommand(
    sub_cmd_name="play",
    sub_cmd_description="Play a song",
)
@slash_option(
    name="song",
    description="The name of the song to play",
    required=True,
    opt_type=OptionType.STRING,
    autocomplete=True
)
async def song_play(ctx: SlashContext, song: str):
    if song not in music:
        await ctx.send(embed={
            "thumbnail": music_error_image,
            "title": "Error",
            "description": f"Song `{song}` not found.",
            "color": 0xFF0000
        })
        return
    print(f"Song: {song}")
    if not ctx.voice_state:
        if not ctx.author.voice:
            await ctx.send(embed={
                "thumbnail": music_error_image,
                "title": "Error",
                "description": "You must be in a voice channel to play a song.",
                "color": 0xFF0000
            })
            return
        await ctx.author.voice.channel.connect()
    
    audio = Audio(music[song])
    print(f"Playing {song} in {ctx.voice_state.channel.name}")
    await ctx.send(embed={
        "thumbnail": music_image,
        "title": "Playing",
        "description": f"Playing `{song}` in {ctx.voice_state.channel.name}",
        "color": 0x00FF00
    })
    await ctx.voice_state.play(audio)
    await ctx.voice_state.stop()
    if ctx.voice_state.channel:
        await ctx.voice_state.channel.disconnect()
    

@song_play.autocomplete("song")
async def song_play_autocomplete(ctx: AutocompleteContext):
    song = ctx.input_text
    songs = list([s for s in music.keys() if song.lower() in s.lower()] if song else music.keys())

    print(songs)
    if len(songs) > 24:
        songs = songs[:24]

    await ctx.send(
        choices=[
            {
                "name": s,
                "value": s
            }
            for s in songs
        ]
    )

@song_list.subcommand(
    sub_cmd_name="stop",
    sub_cmd_description="Stop the current song",
)
async def stop(ctx: SlashContext):
    if not ctx.voice_state:
        await ctx.send(embed={
            "thumbnail": music_error_image,
            "title": "Error",
            "description": "Not connected to a voice channel.",
            "color": 0xFF0000
        })
        return
    await ctx.voice_state.stop()
    await ctx.send(embed={
        "thumbnail": music_image,
        "title": "Stopped",
        "description": f"Stopped playing in {ctx.voice_state.channel.name}",
        "color": 0x00FF00
    })
    await ctx.voice_state.channel.disconnect()


opinions = {
    975500843581321227: 1,
    1144727072992940082: -2,
}
emotes = {
    2: "✅",
    1: "👍",
    -1: "👎",
    -2: "❌",
}

@listen('on_ready')
async def on_ready():
    print(f"Logged in as {bot.user.username}")
    print("------")
    

@listen('on_message_create')
async def on_message_create(message_event: MessageCreate):
    message = message_event.message
    if message.author.bot:
        return
    
    if message.author.id in opinions:
        opinion = opinions[message.author.id]
        if opinion != 0:
            await message.add_reaction(emotes[opinion])


bot.load_extension("interactions.ext.sentry", dsn=os.getenv("SENTRY_DSN"))
bot.start(os.getenv("BOT_TOKEN"))