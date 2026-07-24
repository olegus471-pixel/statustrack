import asyncio
import logging

from aiogram import Bot

import db
from aima_client import fetch_case_status, TrackingNotFound, TrackingApiError

log = logging.getLogger("checker")


def format_message(status: dict, lang: str, changed: bool) -> str:
    label = status["label_pt"] if lang == "pt" else status["label_en"]
    descricao = status["descricao_pt"] if lang == "pt" else status["descricao_en"]
    acao = status["acao_pt"] if lang == "pt" else status["acao_en"]

    header = "🔔 Novo estado do processo!" if changed else "ℹ️ Estado atual do processo"
    if lang == "en":
        header = "🔔 New case status!" if changed else "ℹ️ Current case status"

    lines = [
        header,
        "",
        f"📌 {label}",
        descricao,
    ]
    if acao:
        lines += ["", acao]
    if status.get("numero_processo"):
        lines += ["", f"Processo: {status['numero_processo']}"]
    return "\n".join(lines)


async def check_one(bot: Bot, db_path: str, sub: dict, force_notify: bool = False) -> None:
    chat_id = sub["chat_id"]
    tracking_id = sub["tracking_id"]
    lang = sub.get("lang") or "pt"

    try:
        status = await fetch_case_status(tracking_id)
    except TrackingNotFound:
        log.warning("Tracking id not found for chat %s", chat_id)
        return
    except TrackingApiError as e:
        log.warning("API error for chat %s: %s", chat_id, e)
        return

    changed = sub.get("last_tipo") != status["tipo"]

    if changed or force_notify:
        text = format_message(status, lang, changed=changed)
        try:
            await bot.send_message(chat_id, text)
        except Exception as e:
            log.warning("Failed to send message to chat %s: %s", chat_id, e)

    if changed:
        await db.update_status(db_path, chat_id, status["tipo"], status["label_pt"])


async def run_daily_check(bot: Bot, db_path: str) -> None:
    subs = await db.get_all_subscriptions(db_path)
    log.info("Running daily check for %d subscriptions", len(subs))
    for sub in subs:
        await check_one(bot, db_path, sub)
        await asyncio.sleep(1)  # be gentle with the remote server
