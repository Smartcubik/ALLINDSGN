#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Запускается по расписанию (за ~1 час до времени публикации каждого поста).
Если на сегодня есть пост со статусом "pending", чьё время публикации
приходится в ближайшие 90 минут — отправляет превью владельцу в Telegram
и помечает пост как "notified". ID найденного поста пишется в GITHUB_OUTPUT,
чтобы job "publish" (с обязательным ревью) знал, что публиковать.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

from tz_utils import now_tashkent, TASHKENT_TZ

POSTS_PATH = "data/posts.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OWNER_CHAT_ID = os.environ["TELEGRAM_OWNER_CHAT_ID"]

RUN_URL = "{}/{}/actions/runs/{}".format(
    os.environ.get("GITHUB_SERVER_URL", ""),
    os.environ.get("GITHUB_REPOSITORY", ""),
    os.environ.get("GITHUB_RUN_ID", ""),
)


def tg_send_message(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def main():
    with open(POSTS_PATH, encoding="utf-8") as f:
        posts = json.load(f)

    now = now_tashkent()
    today = now.date().isoformat()

    match = None
    for post in posts:
        if post["date"] != today:
            continue
        if post["status"] != "pending":
            continue
        hh, mm = map(int, post["time_tashkent"].split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        diff_minutes = (target - now).total_seconds() / 60
        if 0 <= diff_minutes <= 90:
            match = post
            break

    if not match:
        print("Нет постов, требующих уведомления в этом запуске.")
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a") as f:
                f.write("post_id=\n")
        return

    preview = (
        f"🔔 Пост №{match['id']} готов к публикации\n"
        f"Дата: {match['date']} ({match['day_ru']}) в {match['time_tashkent']} (Ташкент)\n"
        f"Тема: {match['title']}\n\n"
        f"— — — TELEGRAM текст — — —\n{match['telegram_text'][:900]}\n\n"
        f"Чтобы опубликовать — открой ссылку и нажми Approve:\n{RUN_URL}\n\n"
        f"Если этот пост не нужно публикать сегодня — просто ничего не делай, "
        f"он останется в очереди до твоего решения."
    )
    tg_send_message(OWNER_CHAT_ID, preview)

    match["status"] = "notified"
    with open(POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"post_id={match['id']}\n")

    print(f"Уведомление отправлено по посту {match['id']}")


if __name__ == "__main__":
    main()
