#!/usr/bin/env python3
"""
Telegram HTML/JavaScript decoder bot.
- Send an .html/.htm/.js/.txt file or paste a short code snippet.
- Decodes HTML entities, common Base64 data blocks, and beautifies HTML/JS.
- Does NOT execute uploaded code.
Set BOT_TOKEN as an environment variable before running.
"""
import os
import re
import html
import base64
import binascii
import logging
from pathlib import Path

import telebot
from telebot.types import Message

try:
    import jsbeautifier
except ImportError:
    jsbeautifier = None

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_INPUT_BYTES = 15 * 1024 * 1024
MAX_OUTPUT_BYTES = 45 * 1024 * 1024
ALLOWED_EXTS = {".html", ".htm", ".xhtml", ".js", ".txt"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("html-decoder")

if not BOT_TOKEN:
    raise SystemExit(
        "BOT_TOKEN is missing. Set it in your environment, e.g. "
        "export BOT_TOKEN='123456:ABC...'"
    )

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


def decode_base64_candidates(text: str) -> tuple[str, int]:
    """Decode obvious Base64 data URIs and standalone long Base64 strings."""
    count = 0

    def replace_data_uri(match):
        nonlocal count
        raw = match.group(2)
        try:
            decoded = base64.b64decode(raw + "=" * (-len(raw) % 4), validate=False)
            # Only replace if it looks like readable text.
            candidate = decoded.decode("utf-8")
            if sum(ch.isprintable() or ch in "\r\n\t" for ch in candidate) / max(1, len(candidate)) < 0.85:
                return match.group(0)
            count += 1
            return "data:" + match.group(1) + "," + candidate
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return match.group(0)

    text = re.sub(
        r"data:([^;,]+);base64,([A-Za-z0-9+/=\r\n]+)",
        replace_data_uri,
        text,
        flags=re.I
    )

    # Decode long standalone Base64 only when it is clearly a text payload.
    pattern = re.compile(r"(?<![A-Za-z0-9+/=])([A-Za-z0-9+/]{160,}={0,2})(?![A-Za-z0-9+/=])")

    def replace_standalone(match):
        nonlocal count
        raw = match.group(1)
        try:
            decoded = base64.b64decode(raw + "=" * (-len(raw) % 4), validate=False)
            candidate = decoded.decode("utf-8")
            if len(candidate) < 80:
                return raw
            printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in candidate) / max(1, len(candidate))
            if printable < 0.92:
                return raw
            count += 1
            return "\n/* BASE64 DECODED BLOCK */\n" + candidate + "\n/* END BASE64 BLOCK */\n"
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return raw

    text = pattern.sub(replace_standalone, text)
    return text, count


def beautify_js(js: str) -> str:
    if jsbeautifier:
        opts = jsbeautifier.default_options()
        opts.indent_size = 2
        opts.preserve_newlines = True
        opts.max_preserve_newlines = 2
        try:
            return jsbeautifier.beautify(js, opts)
        except Exception:
            pass
    # A lightweight fallback: add line breaks at common statement boundaries.
    return re.sub(r";\s*(?=(?:const|let|var|function|if|for|while|return)\b)", ";\n", js)


def decode_document(raw: bytes, filename: str) -> tuple[bytes, str]:
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("File is too large. Maximum input size is 15 MB.")
    text = raw.decode("utf-8-sig", errors="replace")
    text = html.unescape(text)
    text, b64_count = decode_base64_candidates(text)

    ext = Path(filename).suffix.lower()
    if ext == ".js":
        text = beautify_js(text)
    elif ext in {".html", ".htm", ".xhtml"}:
        # Beautify JavaScript inside script blocks while preserving surrounding HTML.
        script_count = 0
        def format_script(match):
            nonlocal script_count
            script_count += 1
            attrs, body = match.group(1), match.group(2)
            typ = re.search(r'type\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
            # Don't format JSON or inert/plain-text payloads as executable JS.
            if typ and ("json" in typ.group(1).lower() or "text/plain" in typ.group(1).lower()):
                return match.group(0)
            return "<script" + attrs + ">" + beautify_js(body) + "</script>"
        text = re.sub(r"<script\b([^>]*)>([\s\S]*?)</script\s*>", format_script, text, flags=re.I)
    notes = [
        "Processed without executing the uploaded file.",
        f"Readable Base64 text blocks decoded: {b64_count}.",
    ]
    if re.search(r"_0x[0-9a-f]{2,}", text, re.I) or "eng-protected-core" in text:
        notes.append(
            "This file appears to use custom JavaScript obfuscation/protection. "
            "Formatting and simple decoding cannot guarantee recovery of the original source."
        )
    if not jsbeautifier:
        notes.append("Optional package jsbeautifier is not installed; used basic formatting fallback.")
    return text.encode("utf-8"), "\n".join(notes)


@bot.message_handler(commands=["start", "help"])
def start(message: Message):
    bot.reply_to(
        message,
        "🧩 HTML / JS Decoder Bot\n\n"
        "একটি .html, .htm, .js বা .txt ফাইল পাঠান। আমি HTML entities, "
        "সহজ Base64 text block decode এবং JavaScript formatting করব।\n\n"
        "⚠️ ফাইলের কোড execute করা হয় না। Custom encryption/obfuscation "
        "থাকলে সব source উদ্ধার করা সম্ভব নাও হতে পারে।\n\n"
        "Supported: .html .htm .xhtml .js .txt\n"
        "Commands: /start, /help"
    )


@bot.message_handler(content_types=["document"])
def handle_document(message: Message):
    doc = message.document
    filename = doc.file_name or "upload.html"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        bot.reply_to(message, "এই ফাইল টাইপটি সাপোর্ট করি না। .html, .htm, .xhtml, .js বা .txt পাঠান।")
        return
    if doc.file_size and doc.file_size > MAX_INPUT_BYTES:
        bot.reply_to(message, "ফাইলটি 15 MB-এর বেশি। ছোট ফাইল পাঠান।")
        return

    status = bot.reply_to(message, "⏳ ফাইল প্রসেস হচ্ছে…")
    try:
        info = bot.get_file(doc.file_id)
        raw = bot.download_file(info.file_path)
        decoded, notes = decode_document(raw, filename)
        if len(decoded) > MAX_OUTPUT_BYTES:
            raise ValueError("Decoded output is too large to send.")
        out_name = Path(filename).stem + "_decoded" + (ext if ext else ".txt")
        with open(out_name, "wb") as f:
            f.write(decoded)
        with open(out_name, "rb") as f:
            bot.send_document(
                message.chat.id, f,
                visible_file_name=out_name,
                caption="✅ Processing complete\n" + notes,
                reply_to_message_id=message.message_id
            )
        try:
            bot.delete_message(message.chat.id, status.message_id)
        except Exception:
            pass
    except Exception as exc:
        log.exception("Failed to process uploaded file")
        bot.reply_to(message, "❌ ফাইল প্রসেস করা যায়নি: " + str(exc)[:700])
    finally:
        try:
            Path(Path(filename).stem + "_decoded" + ext).unlink(missing_ok=True)
        except Exception:
            pass


@bot.message_handler(content_types=["text"])
def handle_text(message: Message):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    if len(text.encode("utf-8")) > 30000:
        bot.reply_to(message, "টেক্সট অনেক বড়। ফাইল হিসেবে পাঠান।")
        return
    try:
        decoded, count = decode_base64_candidates(html.unescape(text))
        decoded = beautify_js(decoded)
        bot.reply_to(
            message,
            f"✅ Decode/format complete. Base64 text blocks decoded: {count}\n\n"
            + (decoded[:3500] if decoded else "(empty)")
        )
        if len(decoded) > 3500:
            import io
            buf = io.BytesIO(decoded.encode("utf-8"))
            buf.name = "decoded.txt"
            bot.send_document(message.chat.id, buf, caption="Full decoded text")
    except Exception:
        log.exception("Text decode failed")
        bot.reply_to(message, "❌ এই টেক্সটটি প্রসেস করা যায়নি। ফাইল হিসেবে পাঠানোর চেষ্টা করুন।")


if __name__ == "__main__":
    log.info("HTML decoder bot started")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
