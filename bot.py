import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from aima_client import extract_tracking_id, fetch_case_status, TrackingNotFound, TrackingApiError
from checker import format_message, check_one, run_daily_check
from config import load_settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

settings = load_settings()
bot = Bot(token=settings.bot_token)
dp = Dispatcher()


WELCOME = (
    "Olá! Envie-me o seu link de acompanhamento AIMA "
    "(https://contactenos.aima.gov.pt/tracking/...) ou apenas o código, "
    "e eu vou verificar o estado do processo todos os dias e avisá-lo "
    "quando houver alteração.\n\n"
    "Comandos:\n"
    "/status - ver o estado atual agora\n"
    "/stop - pausar as verificações diárias e os avisos\n"
    "/resume - retomar as verificações (sem precisar reenviar o link)\n"
    "/lang en - mudar mensagens para inglês (/lang pt para português)"
)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(WELCOME)


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    sub = await db.get_subscription(settings.db_path, message.chat.id)
    if not sub:
        await message.answer("Ainda não tem nenhum processo registado.")
        return
    await db.set_active(settings.db_path, message.chat.id, active=False)
    await message.answer(
        "Ok, pausei as verificações e os avisos diários para este processo. "
        "Envie /resume a qualquer momento para retomar, sem precisar reenviar o link."
    )


@dp.message(Command("resume"))
async def cmd_resume(message: Message):
    sub = await db.get_subscription(settings.db_path, message.chat.id)
    if not sub:
        await message.answer("Ainda não tem nenhum processo registado. Envie o link de acompanhamento primeiro.")
        return
    await db.set_active(settings.db_path, message.chat.id, active=True)
    await message.answer("Retomei as verificações diárias para este processo.")


@dp.message(Command("lang"))
async def cmd_lang(message: Message):
    parts = message.text.split(maxsplit=1)
    lang = (parts[1].strip().lower() if len(parts) > 1 else "")
    if lang not in ("pt", "en"):
        await message.answer("Uso: /lang pt  ou  /lang en")
        return
    sub = await db.get_subscription(settings.db_path, message.chat.id)
    if not sub:
        await message.answer("Ainda não tem nenhum processo registado. Envie o link primeiro.")
        return
    await db.upsert_subscription(settings.db_path, message.chat.id, sub["tracking_id"], lang=lang)
    await message.answer(f"Idioma definido para: {lang}")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    sub = await db.get_subscription(settings.db_path, message.chat.id)
    if not sub:
        await message.answer("Ainda não tem nenhum processo registado. Envie o link de acompanhamento primeiro.")
        return
    await message.answer("A verificar...")
    await check_one(bot, settings.db_path, sub, force_notify=True)


@dp.message(F.text)
async def handle_text(message: Message):
    tracking_id = extract_tracking_id(message.text)
    if not tracking_id:
        await message.answer(
            "Não encontrei nenhum código de acompanhamento válido nessa mensagem. "
            "Envie o link completo ou o código UUID."
        )
        return

    await message.answer("A verificar o processo, aguarde um momento...")

    try:
        status = await fetch_case_status(tracking_id)
    except TrackingNotFound:
        await message.answer("Não encontrei nenhum processo com esse código. Verifique o link e tente novamente.")
        return
    except TrackingApiError as e:
        log.warning("API error: %s", e)
        await message.answer("Não consegui contactar o serviço da AIMA agora. Tente novamente mais tarde.")
        return

    await db.upsert_subscription(settings.db_path, message.chat.id, tracking_id, lang="pt")
    await db.update_status(settings.db_path, message.chat.id, status["tipo"], status["label_pt"])

    await message.answer(
        "Vou acompanhar este processo diariamente. Estado atual:\n\n"
        + format_message(status, lang="pt", changed=False)
    )


async def main():
    await db.init_db(settings.db_path)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_daily_check,
        "cron",
        hour=settings.check_hour_utc,
        minute=settings.check_minute_utc,
        args=[bot, settings.db_path],
    )
    scheduler.start()

    log.info("Bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
