# -*- coding: utf-8 -*-
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List

import requests
from environs import Env
from telegram.error import (
    TelegramError,
    Unauthorized,
    BadRequest,
    TimedOut,
    ChatMigrated,
    NetworkError,
)
from telegram.ext import (
    CallbackContext,
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class News:
    """新闻信息的数据封装类"""

    id: int
    title: str
    content: str
    publish_time: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, News):
            return NotImplemented
        return self.id == other.id

    def to_markdown(self) -> str:
        return f"""
        *{escape_text(self.title)}*

{escape_text(self.content)}

{escape_text(datetime.fromtimestamp(self.publish_time / 1000, tz=timezone(timedelta(hours=8))).strftime('(%Y-%m-%d %H:%M)'))}
        """


def get_news() -> List[News]:
    url = "https://api.beekuaibao.com/homepage/pcApi/news/list"
    logger.info("Query news from BeeKuaiBao")
    response = requests.get(
        url,
        params={"pageSize": 20,},
        headers={
            "User-Agent": "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:70.0) Gecko/20100101 Firefox/70.0",
            "origin": "https://www.beekuaibao.com",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
    )
    news_list = []
    if response.status_code == 200:
        for item in response.json().get("data", []):
            news_list.append(
                News(
                    id=item["id"],
                    title=item["title"],
                    content=item["content"],
                    publish_time=item["publishTime"],
                )
            )
    else:
        logger.warning("Get news failed")
        logger.error(response.text)
    return news_list


def start(updater: Updater, context: CallbackContext) -> None:
    updater.message.reply_text("I'm a bot, please talk to me!")


def unknown(update: Updater, context: CallbackContext) -> None:
    update.message.reply_text("Sorry, I didn't understand that command.")


def escape_text(text: str) -> str:
    if text:
        for keyword in [
            "_",
            "*",
            "[",
            "]",
            "(",
            ")",
            "~",
            "`",
            ">",
            "#",
            "+",
            "-",
            "=",
            "|",
            "{",
            "}",
            ".",
            "!",
        ]:
            text = text.replace(keyword, f"\\{keyword}")
        return text
    return ""


def send_news_message(context: CallbackContext) -> None:
    news_list = get_news()
    # 按照时间先后排序
    news_list.reverse()
    chat_id = context.job.context.get("channel_id")
    interval = context.job.context.get("interval")
    for news in news_list:
        if news.publish_time + interval * 1000 >= int(time.time() * 1000):
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="MarkdownV2",
                text=news.to_markdown(),
                disable_web_page_preview=True,
            )
    else:
        logger.info(f"No news in latest {interval} seconds")


def error_callback(update: Updater, context: CallbackContext) -> None:
    try:
        raise context.error
    except Unauthorized as e:
        # remove update.message.chat_id from conversation list
        logger.error(e)
    except BadRequest as e:
        # handle malformed requests - read more below!
        logger.error(e)
    except TimedOut as e:
        # handle slow connection problems
        logger.error(e)
    except NetworkError as e:
        # handle other connection problems
        logger.error(e)
    except ChatMigrated as e:
        # the chat_id of a group has changed, use e.new_chat_id instead
        logger.error(e)
    except TelegramError as e:
        # handle all other telegram related errors
        logger.error(e)


def main() -> None:
    env = Env()
    # Read .env into os.environ
    env.read_env()
    # 每隔5分钟检查一次是否有新消息
    interval = 60 * 5  # seconds

    token = env.str("BOT_TOKEN", None)
    channel_id = env.str("CHANNEL_ID", None)
    assert token is not None, "Please Set Bot Token"
    assert channel_id is not None, "Please Set Channel id"
    # channel_id必须以@符号开头
    if not channel_id.startswith("@"):
        channel_id = f"@{channel_id}"

    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    updater.job_queue.run_repeating(
        send_news_message,
        interval,
        first=0,
        context={"channel_id": channel_id, "interval": interval},
    )
    start_handler = CommandHandler("start", start)
    dispatcher.add_handler(start_handler)

    # This handler must be added last. If you added it sooner, it would be triggered before the CommandHandlers had a chance to look at the update. Once an update is handled, all further handlers are ignored.
    unknown_handler = MessageHandler(Filters.command, unknown)
    dispatcher.add_handler(unknown_handler)
    dispatcher.add_error_handler(error_callback)

    updater.start_polling()
    logger.info("Started Bot...")
    updater.idle()


if __name__ == "__main__":
    main()
