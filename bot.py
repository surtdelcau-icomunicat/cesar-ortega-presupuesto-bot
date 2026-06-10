import os
import logging
import tempfile
from datetime import datetime

import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          filters, ContextTypes, CallbackQueryHandler)

from table_parser import parse_excel, parse_image
from pdf_presupuesto import PDFPresupuestoGenerator

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PORT = int(os.getenv('PORT', 8000))
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', '')
LOGO_URL = "https://raw.githubusercontent.com/surtdelcau-icomunicat/cesar-ortega-presupuesto-bot/main/cesar-logo-h.png"

user_data = {}

# Estados: 'waiting_table', 'confirming', 'client'


def init_user(user_id):
    user_data[user_id] = {
        'items': [],
        'cliente': None,
        'orientation': 'portrait',
        'state': 'waiting_table'
    }


def build_resumen(items):
    lines = ["📋 He leído esta tabla:\n"]
    subtotal = 0
    for it in items:
        total = it['cantidad'] * it['precio_unitario']
        subtotal += total
        qty = f"{it['cantidad']:g}"
        lines.append(f"• {it['concepto']} — {qty} × {it['precio_unitario']:.2f} € = {total:.2f} €")
    lines.append(f"\nSubtotal: {subtotal:.2f} €")
    return "\n".join(lines)


# ===== HANDLERS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    await update.message.reply_text(
        "👋 ¡Bienvenido a CESAR ORTEGA Presupuestos!\n\n"
        "📊 Envíame la tabla de productos:\n"
        "  • 📸 Una foto de la tabla, o\n"
        "  • 📎 Un archivo Excel (.xlsx)"
    )


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saltar nombre de cliente"""
    user_id = update.effective_user.id
    if user_data.get(user_id, {}).get('state') == 'client':
        user_data[user_id]['cliente'] = None
        await ask_format_msg(context, user_id)


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        init_user(user_id)

    msg = await update.message.reply_text("⏳ Analizando la tabla de la foto...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        temp_dir = tempfile.mkdtemp()
        photo_path = os.path.join(temp_dir, "tabla.jpg")
        await photo_file.download_to_drive(photo_path)

        items = parse_image(photo_path)
        user_data[user_id]['items'] = items
        user_data[user_id]['state'] = 'confirming'

        await msg.edit_text(build_resumen(items))
        await send_confirm_buttons(context, user_id)
    except Exception as e:
        logger.error(f"Error analizando foto: {e}")
        await msg.edit_text(
            "❌ No he podido leer la tabla de la foto.\n"
            "Prueba con una foto más nítida o envía el Excel."
        )


async def receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        init_user(user_id)

    doc = update.message.document
    filename = (doc.file_name or '').lower()

    if not filename.endswith('.xlsx'):
        await update.message.reply_text("❌ Solo acepto archivos .xlsx (o una foto de la tabla)")
        return

    msg = await update.message.reply_text("⏳ Leyendo el Excel...")
    try:
        file = await doc.get_file()
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, "tabla.xlsx")
        await file.download_to_drive(file_path)

        items = parse_excel(file_path)
        user_data[user_id]['items'] = items
        user_data[user_id]['state'] = 'confirming'

        await msg.edit_text(build_resumen(items))
        await send_confirm_buttons(context, user_id)
    except Exception as e:
        logger.error(f"Error leyendo Excel: {e}")
        await msg.edit_text(f"❌ No he podido leer el Excel: {e}")


async def send_confirm_buttons(context, user_id):
    keyboard = [
        [InlineKeyboardButton("✅ Correcto, continuar", callback_data='table_ok')],
        [InlineKeyboardButton("🔄 Volver a enviar la tabla", callback_data='table_retry')]
    ]
    await context.bot.send_message(
        chat_id=user_id,
        text="¿Los datos son correctos?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        await update.message.reply_text("Usa /start para comenzar")
        return

    state = user_data[user_id]['state']
    text = update.message.text.strip()

    if state == 'client':
        user_data[user_id]['cliente'] = text[:50]
        await update.message.reply_text(f"✅ Cliente: {text[:50]}")
        await ask_format_msg(context, user_id)
    else:
        await update.message.reply_text("📊 Envíame una foto de la tabla o un Excel (.xlsx)")


async def ask_format_msg(context, user_id):
    keyboard = [
        [InlineKeyboardButton("📃 Vertical", callback_data='format_portrait')],
        [InlineKeyboardButton("📄 Horizontal", callback_data='format_landscape')]
    ]
    await context.bot.send_message(
        chat_id=user_id,
        text="📐 ¿Qué formato quieres para el presupuesto?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id not in user_data:
        await query.edit_message_text("Usa /start para comenzar")
        return

    if query.data == 'table_ok':
        # Preguntar si los precios son con o sin IVA
        keyboard = [
            [InlineKeyboardButton("Sin IVA", callback_data='iva_sin')],
            [InlineKeyboardButton("Con IVA (21%)", callback_data='iva_con')]
        ]
        await query.edit_message_text(
            "💰 ¿Los precios de la tabla son sin IVA o con IVA?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == 'table_retry':
        user_data[user_id]['items'] = []
        user_data[user_id]['state'] = 'waiting_table'
        await query.edit_message_text("📊 Vale, envíame la tabla de nuevo (foto o .xlsx)")

    elif query.data == 'iva_con':
        # Convertir a base sin IVA (el PDF añade el 21% al final)
        for it in user_data[user_id]['items']:
            it['precio_unitario'] = round(it['precio_unitario'] / 1.21, 2)
        await ask_client(query, context, user_id)

    elif query.data == 'iva_sin':
        await ask_client(query, context, user_id)

    elif query.data.startswith('format_'):
        user_data[user_id]['orientation'] = query.data.replace('format_', '')
        await generate_pdf(query, context, user_id)


async def ask_client(query, context, user_id):
    user_data[user_id]['state'] = 'client'
    await query.edit_message_text(
        "👤 ¿Nombre del cliente para el presupuesto?\n(o /skip para no incluirlo)"
    )


async def generate_pdf(query, context, user_id):
    try:
        await query.edit_message_text("⏳ Generando presupuesto...")

        # Logo
        logo_path = None
        try:
            r = requests.get(LOGO_URL, timeout=5)
            if r.status_code == 200:
                tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                tmp.write(r.content)
                tmp.close()
                logo_path = tmp.name
        except Exception:
            pass

        fecha = datetime.now().strftime("%d-%m-%y")
        orientation = user_data[user_id].get('orientation', 'portrait')
        output_path = f"/tmp/presupuesto_{fecha}_{user_id}.pdf"

        generator = PDFPresupuestoGenerator(logo_path, orientation=orientation)
        generator.generate_pdf(
            user_data[user_id]['items'],
            output_path,
            cliente=user_data[user_id].get('cliente')
        )

        with open(output_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=user_id, document=f,
                filename=f"presupuesto_{fecha}.pdf"
            )
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ ¡Presupuesto listo!\n\nUsa /start para otro presupuesto"
        )
        if os.path.exists(output_path):
            os.remove(output_path)
    except Exception as e:
        logger.error(f"Error PDF: {e}")
        await context.bot.send_message(chat_id=user_id, text=f"❌ Error: {str(e)}")


# ===== MAIN =====

def main():
    logger.info("🚀 Iniciando bot de presupuestos...")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('skip', skip_command))
    application.add_handler(MessageHandler(filters.PHOTO, receive_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, receive_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))
    application.add_handler(CallbackQueryHandler(button_callback))

    webhook_url = f"{RENDER_URL}/webhook"
    logger.info(f"📡 Webhook: {webhook_url}")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=webhook_url
    )


if __name__ == '__main__':
    main()
