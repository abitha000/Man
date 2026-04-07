import bs4
from telegram.ext import ContextTypes
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
import requests
from tg_bot.modules.helper_funcs.decorators import kigcmd, kigcallback, rate_limit
from tg_bot.modules.language import gs

def shorten(description, info="anilist.co"):
    msg = ""
    if len(description) > 700:
        description = f'{description[:500]}....'
        msg += f"\n*Description*: _{description}_[Read More]({info})"
    else:
        msg += f"\n*Description*:_{description}_"
    return (
        msg.replace("<br>", "")
        .replace("</br>", "")
        .replace("<i>", "")
        .replace("</i>", "")
    )


def t(milliseconds: int) -> str:
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        (f'{str(days)} Days, ' if days else "")
        + (f'{str(hours)} Hours, ' if hours else "")
        + (f'{str(minutes)} Minutes, ' if minutes else "")
        + (f'{str(seconds)} Seconds, ' if seconds else "")
        + (f'{str(milliseconds)} ms, ' if milliseconds else "")
    )

    return tmp[:-2]


airing_query = """
    query ($id: Int,$search: String) {
      Media (id: $id, type: ANIME,search: $search) {
        id
        episodes
        title {
          romaji
          english
          native
        }
        nextAiringEpisode {
           airingAt
           timeUntilAiring
           episode
        }
      }
    }
    """

fav_query = """
query ($id: Int) {
      Media (id: $id, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
     }
}
"""

anime_query = """
   query ($id: Int,$search: String) {
      Media (id: $id, type: ANIME,search: $search) {
        id
        title {
          romaji
          english
          native
        }
        description (asHtml: false)
        startDate{
            year
          }
          episodes
          season
          type
          format
          status
          duration
          siteUrl
          studios{
              nodes{
                   name
              }
          }
          trailer{
               id
               site
               thumbnail
          }
          averageScore
          genres
          bannerImage
      }
    }
"""

anime_search_query = """
query ($search: String) {
  Page(perPage: 10) {
    media(search: $search, type: ANIME) {
      id
      title {
        romaji
        english
        native
      }
      startDate {
        year
      }
      status
      averageScore
      format
    }
  }
}
"""
character_query = """
    query ($id: Int, $query: String) {
        Character (id: $id, search: $query) {
               id
               name {
                     first
                     last
                     full
               }
               siteUrl
               image {
                        large
               }
               description
        }
    }
"""

character_search_query = """
query ($query: String) {
  Page(perPage: 10) {
    characters(search: $query) {
      id
      name {
        first
        last
        full
      }
    }
  }
}
"""

manga_query = """
query ($id: Int,$search: String) {
      Media (id: $id, type: MANGA,search: $search) {
        id
        title {
          romaji
          english
          native
        }
        description (asHtml: false)
        startDate{
            year
          }
          type
          format
          status
          siteUrl
          averageScore
          genres
          bannerImage
      }
    }
"""

manga_search_query = """
query ($search: String) {
  Page(perPage: 10) {
    media(search: $search, type: MANGA) {
      id
      title {
        romaji
        english
        native
      }
      startDate {
        year
      }
      status
      averageScore
      format
    }
  }
}
"""


url = "https://graphql.anilist.co"

@kigcmd(command="airing")
@rate_limit(messages_per_window=5, window_seconds=60)
async def airing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    search_str = message.text.split(" ", 1)
    if len(search_str) == 1:
        await update.effective_message.reply_text(
            "Tell Anime Name :) ( /airing <anime name>)"
        )
        return
    variables = {"search": search_str[1]}
    response = requests.post(
        url, json={"query": airing_query, "variables": variables}
    ).json()["data"]["Media"]
    msg = f"*Name*: *{response['title']['romaji']}*(`{response['title']['native']}`)\n*ID*: `{response['id']}`"
    if response["nextAiringEpisode"]:
        time = response["nextAiringEpisode"]["timeUntilAiring"] * 1000
        time = t(time)
        msg += f"\n*Episode*: `{response['nextAiringEpisode']['episode']}`\n*Airing In*: `{time}`"
    else:
        msg += f"\n*Episode*:{response['episodes']}\n*Status*: `N/A`"
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

@kigcmd(command="anime")
@rate_limit(40, 60)
async def anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    search = message.text.split(" ", 1)
    if len(search) == 1:
        await update.effective_message.reply_text("Format : /anime < anime name >")
        return
    else:
        search = search[1]
    variables = {"search": search}
    json = requests.post(
        url, json={"query": anime_search_query, "variables": variables}
    ).json()
    if "errors" in json.keys():
        await update.effective_message.reply_text("Anime not found")
        return
    media_list = json["data"]["Page"]["media"]
    if not media_list:
        await update.effective_message.reply_text("No anime found")
        return
    if len(media_list) == 1:
        anime_id = media_list[0]["id"]
        variables = {"id": anime_id}
        json = requests.post(
            url, json={"query": anime_query, "variables": variables}
        ).json()
        if "errors" in json.keys():
            await update.effective_message.reply_text("Anime not found")
            return
        json = json["data"]["Media"]
        msg = f"*{json['title']['romaji']}*(`{json['title']['native']}`)\n*Type*: {json['format']}\n*Status*: {json['status']}\n*Episodes*: {json.get('episodes', 'N/A')}\n*Duration*: {json.get('duration', 'N/A')} Per Ep.\n*Score*: {json['averageScore']}\n*Genres*: `"
        for x in json["genres"]:
            msg += f"{x}, "
        msg = msg[:-2] + "`\n"
        msg += "*Studios*: `"
        for x in json["studios"]["nodes"]:
            msg += f"{x['name']}, "
        msg = msg[:-2] + "`\n"
        info = json.get("siteUrl")
        trailer = json.get("trailer", None)
        anime_id = json["id"]
        if trailer:
            trailer_id = trailer.get("id", None)
            site = trailer.get("site", None)
            if site == "youtube":
                trailer = f"https://youtu.be/{trailer_id}"
        description = (
           bs4.BeautifulSoup(json.get("description", "N/A"), features='html.parser').text
        )
        msg += shorten(description, info)
        image = json.get("bannerImage", None)
        if trailer:
            buttons = [
                [
                    InlineKeyboardButton("More Info", url=info),
                    InlineKeyboardButton("Trailer \ud83c\udfac", url=trailer),
                ]
            ]
        else:
            buttons = [[InlineKeyboardButton("More Info", url=info)]]
        if image:
            try:
                await update.effective_message.reply_photo(
                    photo=image,
                    caption=msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            except Exception:
                msg += f" [\u303d\ufe0f]({image})"
                await update.effective_message.reply_text(
                    msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        else:
            await update.effective_message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    else:
        buttons = []
        for media in media_list:
            title = media["title"]["romaji"] or media["title"]["english"] or media["title"]["native"]
            year = media.get("startDate", {}).get("year", "N/A")
            status = media.get("status", "N/A")
            score = media.get("averageScore", "N/A")
            button_text = f"{title} ({year}) [{status}]"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"anilist_anime_{media['id']}_{update.effective_user.id}")])
        await update.effective_message.reply_text(
            "Select an anime:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

@kigcmd(command="character")
@rate_limit(40, 60)
async def character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    search = message.text.split(" ", 1)
    if len(search) == 1:
        await update.effective_message.reply_text("Format : /character < character name >")
        return
    search = search[1]
    variables = {"query": search}
    json = requests.post(
        url, json={"query": character_search_query, "variables": variables}
    ).json()
    if "errors" in json.keys():
        await update.effective_message.reply_text("Character not found")
        return
    char_list = json["data"]["Page"]["characters"]
    if not char_list:
        await update.effective_message.reply_text("No character found")
        return
    if len(char_list) == 1:
        char_id = char_list[0]["id"]
        variables = {"id": char_id}
        json = requests.post(
            url, json={"query": character_query, "variables": variables}
        ).json()
        if "errors" in json.keys():
            await update.effective_message.reply_text("Character not found")
            return
        json = json["data"]["Character"]
        msg = f"*{json.get('name').get('full')}*(`{json.get('name').get('native')}`)\n"
        description = bs4.BeautifulSoup(f"{json['description']}", features='html.parser').text
        site_url = json.get("siteUrl")
        msg += shorten(description, site_url)
        if image := json.get("image", None):
            image = image.get("large")
            await update.effective_message.reply_photo(
                photo=image,
                caption=msg.replace("<b>", "</b>"),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.effective_message.reply_text(
                msg.replace("<b>", "</b>"), parse_mode=ParseMode.MARKDOWN
            )
    else:
        buttons = []
        for char in char_list:
            name = char["name"]["full"] or f"{char['name']['first']} {char['name']['last']}"
            buttons.append([InlineKeyboardButton(name, callback_data=f"anilist_char_{char['id']}_{update.effective_user.id}")])
        await update.effective_message.reply_text(
            "Select a character:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

@kigcmd(command="manga")
@rate_limit(40, 60)
async def manga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    search = message.text.split(" ", 1)
    if len(search) == 1:
        await update.effective_message.reply_text("Format : /manga < manga name >")
        return
    search = search[1]
    variables = {"search": search}
    json = requests.post(
        url, json={"query": manga_search_query, "variables": variables}
    ).json()
    if "errors" in json.keys():
        await update.effective_message.reply_text("Manga not found")
        return
    media_list = json["data"]["Page"]["media"]
    if not media_list:
        await update.effective_message.reply_text("No manga found")
        return
    if len(media_list) == 1:
        manga_id = media_list[0]["id"]
        variables = {"id": manga_id}
        json = requests.post(
            url, json={"query": manga_query, "variables": variables}
        ).json()
        if "errors" in json.keys():
            await update.effective_message.reply_text("Manga not found")
            return
        json = json["data"]["Media"]
        msg = ""
        title, title_native = json["title"].get("romaji", False), json["title"].get(
            "native", False
        )
        start_date, status, score = (
            json["startDate"].get("year", False),
            json.get("status", False),
            json.get("averageScore", False),
        )
        if title:
            msg += f"*{title}*"
            if title_native:
                msg += f"(`{title_native}`)"
        if start_date:
            msg += f"\n*Start Date* - `{start_date}`"
        if status:
            msg += f"\n*Status* - `{status}`"
        if score:
            msg += f"\n*Score* - `{score}`"
        msg += "\n*Genres* - "
        for x in json.get("genres", []):
            msg += f"{x}, "
        msg = msg[:-2]
        info = json["siteUrl"]
        buttons = [[InlineKeyboardButton("More Info", url=info)]]
        image = json.get("bannerImage", False)
        msg += f"_{bs4.BeautifulSoup(json.get('description', None), features='html.parser').text}_"
        if image:
            try:
                await update.effective_message.reply_photo(
                    photo=image,
                    caption=msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            except Exception:
                msg += f" [\u303d\ufe0f]({image})"
                await update.effective_message.reply_text(
                    msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        else:
            await update.effective_message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    else:
        buttons = []
        for media in media_list:
            title = media["title"]["romaji"] or media["title"]["english"] or media["title"]["native"]
            year = media.get("startDate", {}).get("year", "N/A")
            status = media.get("status", "N/A")
            score = media.get("averageScore", "N/A")
            button_text = f"{title} ({year}) [{status}]"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"anilist_manga_{media['id']}_{update.effective_user.id}")])
        await update.effective_message.reply_text(
            "Select a manga:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )


@kigcallback(pattern=r"anilist_anime_(\d+)_(\d+)")
async def anime_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split('_')
    anime_id = int(parts[2])
    user_id = int(parts[3])
    if query.from_user.id != user_id:
        await query.edit_message_text("This selection is not for you!")
        return
    variables = {"id": anime_id}
    json = requests.post(
        url, json={"query": anime_query, "variables": variables}
    ).json()
    if "errors" in json.keys():
        await query.edit_message_text("Anime not found")
        return
    json = json["data"]["Media"]
    msg = f"*{json['title']['romaji']}*(`{json['title']['native']}`)\n*Type*: {json['format']}\n*Status*: {json['status']}\n*Episodes*: {json.get('episodes', 'N/A')}\n*Duration*: {json.get('duration', 'N/A')} Per Ep.\n*Score*: {json['averageScore']}\n*Genres*: `"
    for x in json["genres"]:
        msg += f"{x}, "
    msg = msg[:-2] + "`\n"
    msg += "*Studios*: `"
    for x in json["studios"]["nodes"]:
        msg += f"{x['name']}, "
    msg = msg[:-2] + "`\n"
    info = json.get("siteUrl")
    trailer = json.get("trailer", None)
    if trailer:
        trailer_id = trailer.get("id", None)
        site = trailer.get("site", None)
        if site == "youtube":
            trailer = f"https://youtu.be/{trailer_id}"
    description = (
       bs4.BeautifulSoup(json.get("description", "N/A"), features='html.parser').text
    )
    msg += shorten(description, info)
    image = json.get("bannerImage", None)
    if trailer:
        buttons = [
            [
                InlineKeyboardButton("More Info", url=info),
                InlineKeyboardButton("Trailer \ud83c\udfac", url=trailer),
            ]
        ]
    else:
        buttons = [[InlineKeyboardButton("More Info", url=info)]]
    if image:
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(image, caption=msg, parse_mode=ParseMode.MARKDOWN),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception:
            msg += f" [\u303d\ufe0f]({image})"
            await query.edit_message_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    else:
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons),
        )


@kigcallback(pattern=r"anilist_char_(\d+)_(\d+)")
async def character_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split('_')
    char_id = int(parts[2])
    user_id = int(parts[3])
    if query.from_user.id != user_id:
        await query.edit_message_text("This selection is not for you!")
        return
    variables = {"id": char_id}
    json = requests.post(
        url, json={"query": character_query, "variables": variables}
    ).json()
    if "errors" in json.keys():
        await query.edit_message_text("Character not found")
        return
    json = json["data"]["Character"]
    msg = f"*{json.get('name').get('full')}*(`{json.get('name').get('native')}`)\n"
    description = bs4.BeautifulSoup(f"{json['description']}", features='html.parser').text
    site_url = json.get("siteUrl")
    msg += shorten(description, site_url)
    image = json.get("image", None)
    if image:
        image = image.get("large")
        await query.edit_message_media(
            media=InputMediaPhoto(image, caption=msg.replace("<b>", "</b>"), parse_mode=ParseMode.MARKDOWN),
        )
    else:
        await query.edit_message_text(
            msg.replace("<b>", "</b>"), parse_mode=ParseMode.MARKDOWN
        )


@kigcallback(pattern=r"anilist_manga_(\d+)_(\d+)")
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    await query.answer()
    data = query.data
    parts = data.split('_')
    manga_id = int(parts[2])
    user_id = int(parts[3])
    if query.from_user.id != user_id:
        await query.edit_message_text("This selection is not for you!")
        return
    variables = {"id": manga_id}
    json = requests.post(
        url, json={"query": manga_query, "variables": variables}
    ).json()
    if "errors" in json.keys():
        await query.edit_message_text("Manga not found")
        return
    json = json["data"]["Media"]
    msg = ""
    title, title_native = json["title"].get("romaji", False), json["title"].get(
        "native", False
    )
    start_date, status, score = (
        json["startDate"].get("year", False),
        json.get("status", False),
        json.get("averageScore", False),
    )
    if title:
        msg += f"*{title}*"
        if title_native:
            msg += f"(`{title_native}`)"
    if start_date:
        msg += f"\n*Start Date* - `{start_date}`"
    if status:
        msg += f"\n*Status* - `{status}`"
    if score:
        msg += f"\n*Score* - `{score}`"
    msg += "\n*Genres* - "
    for x in json.get("genres", []):
        msg += f"{x}, "
    msg = msg[:-2]
    info = json["siteUrl"]
    buttons = [[InlineKeyboardButton("More Info", url=info)]]
    image = json.get("bannerImage", False)
    msg += f"_{bs4.BeautifulSoup(json.get('description', None), features='html.parser').text}_"
    if image:
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(image, caption=msg, parse_mode=ParseMode.MARKDOWN),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception:
            msg += f" [\u303d\ufe0f]({image})"
            await query.edit_message_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    else:
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons),
        )


    return gs(chat_id, "anilist_help")

__mod_name__ = "AniList"

def get_help(chat):
    return gs(chat, "anilist_help")
