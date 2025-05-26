import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage  # Для хранения состояний
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Убедитесь, что файл oxforddic.py находится в той же папке
# и содержит обновленную функцию getDefinitions
from oxforddic import getDefinitions
from googletrans import Translator

translator = Translator()

# ВАЖНО: Храните токен в переменной окружения или конфигурационном файле
API_TOKEN = '7834569712:AAHykrUVVzGbW_kPmQ61dhs3c8ZPVB3TeXE'

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize FSM storage
storage = MemoryStorage()

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

# Словарь для языков (код: название для кнопки)
AVAILABLE_LANGUAGES = {
    "en": "🇬🇧 English",
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский"
}
DEFAULT_PRIMARY_LANG = "en"
DEFAULT_TARGET_LANG = "uz"


# States for language selection
class LanguageSetup(StatesGroup):
    choosing_primary_lang = State()
    choosing_target_lang = State()


# Helper function to get user languages
async def get_user_languages(user_id: int, state: FSMContext):
    user_data = await state.get_data()
    primary_lang = user_data.get(f"user_{user_id}_primary_lang", DEFAULT_PRIMARY_LANG)
    target_lang = user_data.get(f"user_{user_id}_target_lang", DEFAULT_TARGET_LANG)
    return primary_lang, target_lang


# Helper function to create language keyboard
def create_language_keyboard(exclude_lang_code: str = None):
    keyboard = InlineKeyboardMarkup(row_width=2)
    for code, name in AVAILABLE_LANGUAGES.items():
        if code != exclude_lang_code:
            keyboard.add(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
    return keyboard


@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()  # Сбрасываем предыдущее состояние, если есть
    user_name = message.from_user.first_name
    await message.reply(
        f"Salom, {user_name}! Men English Word Bot!\n"
        "Sizga so'zlarni o'rganishda va iboralarni tarjima qilishda yordam beraman!\n\n"
        "Iltimos, asosiy tilingizni tanlang (siz yozadigan til):",
        reply_markup=create_language_keyboard()
    )
    await LanguageSetup.choosing_primary_lang.set()
    # Сохраняем user_id для дальнейшего использования в state
    await state.update_data(current_user_id_for_setup=message.from_user.id)


@dp.callback_query_handler(lambda c: c.data.startswith('lang_'), state=LanguageSetup.choosing_primary_lang)
async def process_primary_language(callback_query: types.CallbackQuery, state: FSMContext):
    primary_lang_code = callback_query.data.split('_')[1]
    user_data = await state.get_data()
    user_id = user_data.get('current_user_id_for_setup', callback_query.from_user.id)

    await state.update_data({f"user_{user_id}_primary_lang": primary_lang_code})

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        f"Asosiy til '{AVAILABLE_LANGUAGES[primary_lang_code]}' qilib tanlandi.\n"
        "Endi tarjima tilini tanlang (asosiy tilga tarjima qilinadi):",
        reply_markup=create_language_keyboard(exclude_lang_code=primary_lang_code)
    )
    await LanguageSetup.choosing_target_lang.set()


@dp.callback_query_handler(lambda c: c.data.startswith('lang_'), state=LanguageSetup.choosing_target_lang)
async def process_target_language(callback_query: types.CallbackQuery, state: FSMContext):
    target_lang_code = callback_query.data.split('_')[1]
    user_data = await state.get_data()
    user_id = user_data.get('current_user_id_for_setup', callback_query.from_user.id)
    primary_lang_code = user_data.get(f"user_{user_id}_primary_lang", DEFAULT_PRIMARY_LANG)

    await state.update_data({f"user_{user_id}_target_lang": target_lang_code})

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        f"Til sozlamalari o'rnatildi:\n"
        f"Sizning tilingiz: {AVAILABLE_LANGUAGES[primary_lang_code]}\n"
        f"Tarjima tili: {AVAILABLE_LANGUAGES[target_lang_code]}\n\n"
        "Endi so'z yoki matn yuborishingiz mumkin."
    )
    await state.finish()  # Завершаем настройку


@dp.message_handler(commands=['help'], state="*")
async def cmd_help(message: types.Message):
    await message.reply(
        "Men bilan siz Ingliz tilidagi so'zlarning ma'nolarini, sinonimlarini va ularning talaffuzini o'rganasiz.\n"
        "Biror so'zni yuborsangiz, uning tarjimasi, ma'nosi va (agar mavjud bo'lsa) talaffuzini olasiz.\n"
        "Agar matn yuborsangiz, uni tarjima qilaman.\n"
        "Til sozlamalarini o'zgartirish uchun /start buyrug'ini qayta yuboring."
    )


@dp.message_handler(content_types=types.ContentTypes.TEXT, state="*")  # Обработка любого текстового сообщения
async def handle_text(message: types.Message, state: FSMContext):
    user_text = message.text.strip()
    if not user_text:
        await message.reply("Iltimos, biror narsa yozing.")
        return

    primary_lang, target_lang = await get_user_languages(message.from_user.id, state)

    # Определяем, одно слово или фраза
    is_single_word = ' ' not in user_text

    if not is_single_word:  # Если это фраза
        try:
            translated_obj = translator.translate(user_text, src=primary_lang, dest=target_lang)
            await message.reply(f"Tarjima ({primary_lang} -> {target_lang}):\n{translated_obj.text}")
        except Exception as e:
            logging.error(f"Ошибка перевода фразы '{user_text}': {e}")
            await message.reply("Matnni tarjima qilishda xatolik yuz berdi.")
    else:  # Если это одно слово
        reply_parts = []
        word_for_lookup_en = None  # Слово на английском для словаря

        # 1. Переводим слово
        try:
            translated_obj = translator.translate(user_text, src=primary_lang, dest=target_lang)
            reply_parts.append(f"📖 So'z: {user_text.capitalize()} ({primary_lang})")
            reply_parts.append(f"🔄 Tarjimasi ({target_lang}): {translated_obj.text.capitalize()}")
        except Exception as e:
            logging.error(f"Ошибка перевода слова '{user_text}': {e}")
            await message.reply(f"'{user_text}' so'zini tarjima qilishda xatolik.")
            return

        # 2. Готовим слово для поиска в словаре (должно быть на английском)
        if primary_lang == 'en':
            word_for_lookup_en = user_text
        else:
            try:
                # Переводим исходное слово на английский для поиска в словаре
                en_translation_obj = translator.translate(user_text, src=primary_lang, dest='en')
                # Убедимся, что результат перевода на английский - одно слово
                if ' ' not in en_translation_obj.text.strip():
                    word_for_lookup_en = en_translation_obj.text
                else:
                    logging.info(
                        f"Слово '{user_text}' ({primary_lang}) перевелось на английский как фраза: '{en_translation_obj.text}'. Пропуск поиска в словаре.")
            except Exception as e:
                logging.error(f"Ошибка перевода '{user_text}' на английский для словаря: {e}")

        lookup_result = None
        if word_for_lookup_en:
            # Добавляем информацию о том, для какого слова ищем определения, если оно отличается
            if word_for_lookup_en.lower() != user_text.lower():
                reply_parts.append(f"\nℹ️ Quyidagi ma'lumotlar '{word_for_lookup_en.capitalize()}' (en) so'zi uchun:")

            lookup_result = getDefinitions(word_for_lookup_en)  # Функция из oxforddic.py

        if lookup_result:
            if lookup_result.get('definitions'):
                reply_parts.append(f"\n📚 Ma'nolari:\n{lookup_result['definitions']}")
            if lookup_result.get('synonyms'):
                reply_parts.append(f"\n🤝 Sinonimlari:\n{lookup_result['synonyms']}")
        elif word_for_lookup_en:  # Если искали, но не нашли
            reply_parts.append("\n😔 Afsuski, bu so'z uchun qo'shimcha ma'lumot (ma'no, sinonim) topilmadi.")

        # Отправляем текстовый ответ
        if reply_parts:
            await message.reply("\n".join(reply_parts))
        else:  # Если даже перевод не удался (хотя выше должна быть обработка)
            await message.reply("So'rovni qayta ishlashda xatolik yuz berdi.")

        # Отправляем аудио, если есть
        if lookup_result and lookup_result.get('audio'):
            try:
                # Проверяем URL аудио на распространенные проблемы
                audio_url = lookup_result['audio']
                if not audio_url.startswith(('http://', 'https://')):
                    # Иногда API может вернуть относительный путь, попробуем сделать его абсолютным
                    # Это предположение, dictionaryapi.dev обычно дает полные URL
                    if audio_url.startswith("//"):
                        audio_url = "https:" + audio_url
                        # else: # Если это просто имя файла, мы не сможем его загрузить без базового URL
                    #     logging.warning(f"Получен некорректный URL аудио: {audio_url}")
                    #     audio_url = None # Сбрасываем, чтобы не пытаться отправить

                if audio_url:
                    await bot.send_chat_action(message.chat.id, types.ChatActions.UPLOAD_VOICE)
                    await message.reply_voice(audio_url, caption=f"🎤 Talaffuzi ({word_for_lookup_en.capitalize()})")
            except Exception as e:
                logging.error(
                    f"Ошибка отправки аудио для '{word_for_lookup_en}': {e}. URL: {lookup_result.get('audio')}")
                # Можно уведомить пользователя, если аудио не отправилось
                # await message.reply("Audio talaffuzni yuborishda xatolik yuz berdi.")
        elif lookup_result and not lookup_result.get('audio') and word_for_lookup_en:
            pass  # Уже сообщили, что нет доп. информации или есть, но без аудио


if __name__ == '__main__':
    logging.info("Bot ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True)

