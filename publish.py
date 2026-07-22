#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Публикует утверждённый пост в Telegram-канал @allindsgn и в Threads.
Вызывается job'ом "publish" ПОСЛЕ ручного approve в GitHub Environments.

Переменные окружения:
  POST_ID
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHANNEL_ID         — например "@allindsgn"
  THREADS_ACCESS_TOKEN        — опционально
  THREADS_USER_ID             — опционально
  PUBLIC_ASSETS_BASE_URL      — опционально, для фото в Threads
"""
import html
import json
import os
import time
import urllib.request
import urllib.parse

POSTS_PATH = "posts.json"
CATALOG_PATH = "photo_catalog.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
POST_ID = int(os.environ["POST_ID"])

THREADS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "")
PUBLIC_ASSETS_BASE_URL = os.environ.get("PUBLIC_ASSETS_BASE_URL", "")


def format_telegram_html(text: str) -> str:
    """Первый непустой абзац делает жирным, маркеры списков заменяет на ■."""
    lines = text.split("\n")
    out = []
    title_done = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("• ") or stripped.startswith("* "):
            escaped = "■ " + html.escape(stripped[2:].strip())
        else:
            escaped = html.escape(line)
        if not title_done and stripped:
            escaped = f"<b>{escaped}</b>"
            title_done = True
        out.append(escaped)
    return "\n".join(out)


def http_post(url, data=None, files=None):
    if files:
        import mimetypes
        boundary = "----ClaudeBoundary"
        body = b""
        for key, val in (data or {}).items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{val}\r\n".encode()
        for key, (filename, content) in files.items():
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; "
                      f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
            body += content + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data or {}).encode())
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def http_get(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def publish_telegram(post, photo_filename):
    formatted = format_telegram_html(post["telegram_text"])
    if photo_filename and os.path.exists(f"assets/photos/{photo_filename}"):
        with open(f"assets/photos/{photo_filename}", "rb") as f:
            content = f.read()
        result = http_post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL_ID, "caption": formatted[:1024], "parse_mode": "HTML"},
            files={"photo": (photo_filename, content)},
        )
    else:
        result = http_post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHANNEL_ID, "text": formatted, "parse_mode": "HTML"},
        )
    if not result.get("ok"):
        raise RuntimeError(f"Telegram publish failed: {result}")
    print("Telegram: опубликовано:", result["result"]["message_id"])


def publish_threads(post, photo_filename):
    if not (THREADS_TOKEN and THREADS_USER_ID):
        print("Threads: токен/ID не настроены — пропускаю публикацию в Threads.")
        return
    text = post["threads_text"]
    create_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    params = {"access_token": THREADS_TOKEN, "text": text[:500]}
    if photo_filename and PUBLIC_ASSETS_BASE_URL:
        params["media_type"] = "IMAGE"
        params["image_url"] = f"{PUBLIC_ASSETS_BASE_URL}/{urllib.parse.quote(photo_filename)}"
    else:
        params["media_type"] = "TEXT"
    created = http_post(create_url, data=params)
    if "id" not in created:
        raise RuntimeError(f"Threads container creation failed: {created}")
    creation_id = created["id"]
    time.sleep(5)
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    published = http_post(publish_url, data={
        "access_token": THREADS_TOKEN,
        "creation_id": creation_id,
    })
    if "id" not in published:
        raise RuntimeError(f"Threads publish failed: {published}")
    print("Threads: опубликовано:", published["id"])


def main():
    with open(POSTS_PATH, encoding="utf-8") as f:
        posts = json.load(f)
    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)

    post = next((p for p in posts if p["id"] == POST_ID), None)
    if not post:
        raise SystemExit(f"Пост {POST_ID} не найден в {POSTS_PATH}")

    photo_code = (post.get("photo_code") or "").split(" + ")[0].strip()
    photo_filename = catalog.get(photo_code)

    publish_telegram(post, photo_filename)
    publish_threads(post, photo_filename)

    post["status"] = "published"
    with open(POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print(f"Пост {POST_ID} помечен как опубликованный.")


if __name__ == "__main__":
    main()
