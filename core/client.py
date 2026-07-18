# -*- coding: utf-8 -*-
"""
core/client.py
---------------
تمام تماس‌های خام با کتابخانه rubpy فقط از همین فایل انجام می‌شود.

================================================================
تغییر مهم نسبت به نسخه‌ی قبلی پروژه
================================================================
LeoBot دیگر با Session حساب کاربری (لاگین با شماره تلفن) اجرا نمی‌شود.
اتصال اکنون از طریق **Bot Token رسمی روبیکا** و کلاس ``rubpy.bot.BotClient``
انجام می‌شود؛ یعنی هیچ کاربری نباید با شماره تلفن یا کد تایید وارد شود.

بررسی فنی (طبق درخواست):
    - rubpy از نسخه‌های اخیر (>=7.x) به‌صورت رسمی از Bot Token با کلاس
      ``rubpy.bot.BotClient(token)`` پشتیبانی می‌کند؛ این کلاس با متدهای
      async مانند ``send_message``، ``delete_message``، ``edit_message_text``
      و دکوریتور ``@app.on_update(...)`` کار می‌کند. پس سوییچ به توکن رسمی
      از نظر rubpy امکان‌پذیر است.
    - اما API رسمی بات روبیکا (که BotClient از آن استفاده می‌کند) هیچ
      متدی برای «حذف عضو از گروه»، «سکوت/محدودسازی یک عضو خاص» یا
      «تنظیم ادمین» ندارد (فهرست کامل متدهای رسمی: getMe، sendMessage،
      sendPoll، sendLocation، sendContact، getChat، getUpdates،
      forwardMessage، editMessageText، editMessageKeypad، deleteMessage،
      setCommands، editChatKeypad، getFile، sendFile). این محدودیت از
      طرف پلتفرم روبیکاست، نه rubpy، و با هیچ کتابخانه‌ای قابل دور زدن
      نیست تا زمانی که خود روبیکا چنین متدی را در Bot API اضافه کند.
    - راه‌حل سازگار پیاده‌سازی‌شده: «بن»/«آنبن»/«سکوت» به‌صورت نرم‌افزاری
      (Soft-Moderation) توسط خود LeoBot در دیتابیس مدیریت می‌شوند
      (ر.ک. modules/admin.py و modules/anti_spam.py): پیام‌های کاربر
      بن‌شده/سکوت‌شده به‌طور خودکار با متد رسمی ``deleteMessage`` حذف
      می‌شوند. «حذف پیام» چون در Bot API رسمی موجود است، کاملاً واقعی
      و بدون محدودیت کار می‌کند.

================================================================
معماری Bridge سینک/اسینک
================================================================
BotClient کتابخانه‌ی rubpy کاملاً async است (باید با await فراخوانی شود)
اما بقیه‌ی ماژول‌های LeoBot (admin.py، locks.py و ...) به‌عمد Sync
نوشته شده‌اند تا ساختار قبلی پروژه حفظ شود. برای همین:
    1) هندلر ``on_update`` (که توسط rubpy async فراخوانی می‌شود) فقط
       حلقه‌ی درحال‌اجرا (event loop) را ذخیره می‌کند و پردازش پیام را
       به یک ترد جدا (ThreadPoolExecutor) می‌سپارد؛ در نتیجه حلقه‌ی
       اصلی هرگز مسدود (Block) نمی‌شود.
    2) کد Sync هر ماژول وقتی می‌خواهد پیام بفرستد/حذف کند، از طریق
       ``asyncio.run_coroutine_threadsafe`` روی همان حلقه‌ی ذخیره‌شده،
       متد async واقعی rubpy را صدا می‌زند و منتظر جواب می‌ماند.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import config
from core.logger import get_logger

log = get_logger("client")

try:
    from rubpy.bot import BotClient as _BotClient
    from rubpy.bot import filters as rubpy_filters
except ImportError as exc:
    raise ImportError(
        "کتابخانه rubpy نصب نیست یا نسخه‌ی نصب‌شده از BotClient پشتیبانی نمی‌کند. "
        "با دستور «pip install -U rubpy» آخرین نسخه را نصب کنید."
    ) from exc


def _safe_repr(obj, max_len=800):
    """
    نمایش امن یک آبجکت ناشناخته (پیام/آپدیت rubpy) برای لاگ DEBUG، بدون
    اینکه در صورت خطای __repr__ کل برنامه کرش کند.
    """
    try:
        if hasattr(obj, "__dict__"):
            data = repr(vars(obj))
        else:
            data = repr(obj)
    except Exception:
        data = f"<repr failed for {type(obj)}>"
    return data[:max_len]


class RubikaClient:
    """
    Wrapper سبک روی rubpy.bot.BotClient برای اتصال با Bot Token رسمی.
    اگر متدی در نسخه‌ی نصب‌شده‌ی rubpy نام متفاوتی داشت، فقط کافیست
    در همین کلاس تابع مربوطه (متد ``_call_async``) اصلاح شود.
    """

    def __init__(self, token: str):
        self._client = _BotClient(token)
        self.filters = rubpy_filters

        self._loop = None
        self._loop_ready = threading.Event()
        self._executor = ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="leobot-worker"
        )

    # -- Bridge بین ترد اصلی asyncio و تردهای کاری Sync ------------------------
    def _capture_loop(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
            self._loop_ready.set()
            self._loop.set_exception_handler(self._on_loop_exception)
            log.info("حلقه‌ی asyncio ربات شناسایی و ذخیره شد.")

    @staticmethod
    def _on_loop_exception(loop, context):
        """
        بدون این Handler، خطاهای داخل Task های async (مثلاً امضای اشتباه
        هندلر) به‌صورت کاملاً بی‌صدا بلعیده می‌شوند و بات «روشن ولی خاموش»
        به‌نظر می‌رسد. با ثبت این Handler، هر خطای async حتماً در لاگ ظاهر می‌شود.
        """
        message = context.get("exception", context.get("message"))
        log.error(f"خطای بی‌صدای asyncio شناسایی شد: {message}")

    def submit_sync_task(self, fn, *args, **kwargs):
        """
        اجرای منطق Sync (پردازش دستورات/پیام‌ها) در یک ترد جدا تا
        حلقه‌ی اصلی asyncio هرگز بلاک نشود.
        """
        def _safe_run():
            try:
                fn(*args, **kwargs)
            except Exception:
                log.exception("خطای مدیریت‌نشده در پردازش پیام (ترد کاری).")

        return self._executor.submit(_safe_run)

    def _call_async(self, coro_factory, default=None, timeout=15):
        if not self._loop_ready.wait(timeout=10):
            log.error("حلقه‌ی asyncio ربات هنوز آماده نیست؛ درخواست نادیده گرفته شد.")
            return default
        try:
            future = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
            return future.result(timeout=timeout)
        except Exception as exc:
            log.error(f"خطا در فراخوانی متد async rubpy: {exc}")
            return default

    # -- ثبت هندلر اصلی دریافت پیام‌ها -----------------------------------------
    def register_update_handler(self, dispatch_callback):
        """
        dispatch_callback(client_wrapper, message) یک تابع Sync است که در
        core/events.py تعریف شده و باید در یک ترد کاری اجرا شود.

        نکته‌ی مهم (رفع باگ «بات پاسخ نمی‌دهد»): نسخه‌های مختلف rubpy ممکن
        است هندلر ``on_update`` را با امضای متفاوتی صدا بزنند — بعضی فقط
        ``message`` می‌فرستند، بعضی ``(client, message)``. اگر امضای هندلر
        دقیق نباشد، پایتون یک TypeError داخل Task می‌اندازد که asyncio آن
        را می‌بلعد و هیچ خطایی در لاگ دیده نمی‌شود (دقیقاً همان رفتار
        «بات روشن است ولی هیچ پاسخی نمی‌دهد»). برای همین:
            1) هندلر با ``*args`` نوشته شده تا با هر دو امضا کار کند.
            2) یک Exception Handler سراسری روی حلقه‌ی asyncio ثبت می‌شود
               تا این‌جور خطاهای بی‌صدا هم در لاگ ظاهر شوند.
            3) به‌جای «فقط اولین روش موفق»، روی هر فیلتری که در این نسخه
               از rubpy پیدا شود جداگانه ثبت می‌شود (هم PV هم گروه)، تا
               اگر یکی از حالت‌ها ناموفق بود بقیه از کار نیفتند.
        """

        def _extract_message(args, kwargs):
            if "message" in kwargs:
                return kwargs["message"]
            if "update" in kwargs:
                return kwargs["update"]
            # قرارداد رایج: آخرین آرگومان موقعیتی، آبجکت واقعی پیام/آپدیت است
            return args[-1] if args else None

        async def _on_update(*args, **kwargs):
            try:
                self._capture_loop()
                message = _extract_message(args, kwargs)
                if message is None:
                    log.warning("آپدیتی دریافت شد اما نتوانستم آبجکت پیام را از آن استخراج کنم.")
                    return
                if log.isEnabledFor(10):  # DEBUG
                    log.debug(f"آپدیت خام دریافت شد: {_safe_repr(message)}")
                self.submit_sync_task(dispatch_callback, self, message)
            except Exception:
                log.exception("خطای مدیریت‌نشده داخل هندلر on_update (قبل از رسیدن به دیسپچر).")

        # کشف فیلترهای موجود در این نسخه از rubpy (بدون فرض قطعی روی نام‌ها)
        candidate_filters = []
        for attr_name in ("private", "group", "channel", "text", "chat", "started"):
            f = getattr(self.filters, attr_name, None)
            if f is not None:
                candidate_filters.append((attr_name, f))

        registered_on = []

        # روش ۱: ثبت بدون فیلتر (بهترین حالت — همه‌ی آپدیت‌ها را می‌گیرد)
        try:
            self._client.on_update()(_on_update)
            registered_on.append("no-filter")
        except TypeError:
            pass
        except Exception as exc:
            log.warning(f"ثبت بدون فیلتر ناموفق بود: {exc}")

        # روش ۲: اگر بدون فیلتر کار نکرد، روی تک‌تک فیلترهای شناخته‌شده ثبت کن
        if not registered_on:
            for name, f in candidate_filters:
                try:
                    self._client.on_update(f)(_on_update)
                    registered_on.append(name)
                except Exception as exc:
                    log.warning(f"ثبت هندلر با فیلتر '{name}' ناموفق بود: {exc}")

        if not registered_on:
            raise RuntimeError(
                "امکان ثبت هیچ هندلری روی BotClient وجود ندارد؛ نسخه‌ی rubpy را بررسی/به‌روزرسانی کنید."
            )

        log.info(f"هندلر دریافت پیام ثبت شد (حالت: {', '.join(registered_on)}).")

        log.info("هندلر دریافت پیام با موفقیت روی BotClient ثبت شد.")

    def run_forever(self):
        """
        اجرای مسدودکننده‌ی ربات (Polling). این تابع تا زمانی که ارتباط قطع
        یا خطایی رخ دهد، اجرا را ادامه می‌دهد؛ مدیریت تلاش مجدد در
        main.py انجام می‌شود.
        """
        self._client.run()

    # -- متدهای رسمی پشتیبانی‌شده توسط Bot API روبیکا ---------------------------
    def get_me(self):
        return self._call_async(lambda: self._client.get_me())

    def send_text(self, chat_guid: str, text: str, reply_to_message_id: str = None):
        return self._call_async(
            lambda: self._client.send_message(
                chat_guid, text, reply_to_message_id=reply_to_message_id
            )
        )

    def send_keypad(
        self,
        chat_guid: str,
        text: str,
        inline_keypad=None,
        chat_keypad=None,
        chat_keypad_type=None,
        reply_to_message_id: str = None,
    ):
        return self._call_async(
            lambda: self._client.send_message(
                chat_guid,
                text,
                inline_keypad=inline_keypad,
                chat_keypad=chat_keypad,
                chat_keypad_type=chat_keypad_type,
                reply_to_message_id=reply_to_message_id,
            )
        )

    def edit_message_text(self, chat_guid: str, message_id: str, text: str):
        return self._call_async(
            lambda: self._client.edit_message_text(chat_guid, message_id, text)
        )

    def edit_inline_keypad(self, chat_guid: str, message_id: str, inline_keypad):
        return self._call_async(
            lambda: self._client.edit_message_keypad(
                chat_guid, message_id, inline_keypad
            )
        )

    def remove_chat_keypad(self, chat_guid: str):
        return self._call_async(
            lambda: self._client.edit_chat_keypad(
                chat_guid, chat_keypad_type="Remove"
            )
        )

    def delete_message(self, chat_guid: str, message_id):
        """
        متد رسمی deleteMessage — این تنها عملیات مدیریتیِ واقعاً
        پشتیبانی‌شده توسط Bot API روبیکاست و کاملاً کار می‌کند
        (به شرطی که بات در گروه دسترسی حذف پیام داشته باشد).
        """
        return self._call_async(
            lambda: self._client.delete_message(chat_guid, message_id)
        )

    def get_chat(self, chat_guid: str):
        return self._call_async(lambda: self._client.get_chat(chat_guid))

    def forward_message(self, from_chat_id: str, message_id: str, to_chat_id: str):
        return self._call_async(
            lambda: self._client.forward_message(from_chat_id, message_id, to_chat_id)
        )


_client_singleton = None


def get_client(token: str) -> RubikaClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = RubikaClient(token)
    return _client_singleton
