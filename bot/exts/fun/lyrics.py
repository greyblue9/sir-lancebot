from os import getenv
from re import compile, DOTALL
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from discord import Color, Embed
from discord.ext import commands
from httpx import AsyncClient

from bot.bot import Bot


class Lyrics(commands.Cog):
    """Cog for the Lyrics command."""
    
    "Used to trim excess newlines in lyrics content."
    NEWLINE_NORMALIZE_REGEX = compile(
        "\n\s*\n",
        DOTALL
    )
    
    "Used to search the Genius API"
    access_token = getenv("GENIUS_ACCESS_TOKEN")
 
    @commands.command(
        name="lyrics",
        aliases=("ly", "lyr")
    )
    async def lyrics_command(
        self,
        ctx: commands.Context,
        *,
        query: str=""
    ) -> None:
        """
        Send lyrics for the top song matching the given
        query.

        The results are fetched using the `genius.com` 
        API; the actual lyrics text is obtained by
        extracting the lyric textual content from the
        Genius webpage as indicated by the top matching
        API result.
        
        Yes, the API actually works this way. There is no
        API endpoint to retrieve the lyrics themselves :D
        """
        stripped_query = " ".join("".join(
          c 
          if c.isalnum() else " "
          for c in query
        ).split())
        
        if not query.strip():
            await ctx.reply(
              "**Error in `lyrics` command**: \n "
              "You must enter one or more search terms."
            )
            return
        
        # Reply with a status message so the user will
        # know their command worked.
        msg = await ctx.reply(
          f"{ctx.author.mention} Searching for "
          f"song lyrics matching `{stripped_query}` ...",
          delete_after=10,
        )
        
        headers = {
          "Authorization": f"bearer {access_token}" 
        }
        async with AsyncClient() as client:
            resp = await client.get(
              "https://api.genius.com/search",
              params={"q": query},
              headers=headers,
            )
            resp.raise_for_status()
        
        # Find the first song result.
        results_raw = [
          h for h in resp.json()["response"]["hits"]
          if h["type"] == "song"
        ]
        if not results_raw:
          msg = await msg.edit(
            content="Sorry, no lyric results found "
            f"for `{stripped_query}`."
          )
          return
        
        # Unpack a couple of extra layers here
        result_raw = results_raw[0]
        # Get the one value in this dict (`"result"`).
        result = result_raw["result"]
        
        # Extract the song information we care about
        title, artist, image_url, lyrics_path = (
          result["title"],
          result["primary_artist"]["name"],
          result["song_art_image_url"],
          result["path"]
        )
        # Derive the absolute URI of the page we will 
        # extract lyrics text from.
        lyrics_page_url = urljoin(
          "https://genius.com", lyrics_path
        )
       
        # Update the status message to let the user know
        # we are fetching lyrics for this 
        # particular song.
        msg = await msg.edit(
          content=f"Fetching lyrics for **\"{title}\"** "
          f"by *{artist}* ..."
        )
        
        async with AsyncClient() as client:
            lresp = await client.get(
                lyrics_page_url,
                headers={
                    "User-Agent": 
                        "Mozilla/5.0 (Windows NT 6.1; "
                        "WOW64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/"
                        "33.0.1750.154 Safari/537.36",
                    "Referer": "https://genius.com/"
                }
            )
            lresp.raise_for_status()

        doc = BeautifulSoup(
          lresp.content,
          features="html.parser"
        )
        
        # Hairy HTML element selector with 
        # preprocessing to preserve linebreaks while
        # discarding srbitrary element divisions here
        lyrics_text = NEWLINE_NORMALIZE_REGEX.subn(
          "\n",
          BeautifulSoup(
            "\n".join(
              [
                str(t).replace('<br/>', '\n')
                for t in doc.select(
                  "#lyrics-root-pin-spacer "
                  "[data-lyrics-container=true] " 
                  ":not(:empty) *"
                )
              ]
            )
          ).text
        )[0]
        
        # Prepare the lyrics embed
        embed = Embed(
          title=title,
          url=lyrics_page_url,
          description=lyrics_text,
          color=Color.blue(),
        )
        embed.set_thumbnail(
          image_url=song_art_image_url
        )
        await ctx.reply(
          content=f"**{title}** by *{artist}* lyrics",
          embed=embed
        )


def setup(bot: Bot) -> None:
    """Loads the lyrics cog."""
    bot.add_cog(Lyrics())