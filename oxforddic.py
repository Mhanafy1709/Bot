import requests
import json


def getDefinitions(word_id):
    word_id_lower = word_id.lower().strip()
    if not word_id_lower or ' ' in word_id_lower:  # Этот API лучше работает с одиночными словами
        print(f"API dictionaryapi.dev ожидает одно слово. Получено: '{word_id_lower}'")
        return False

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word_id_lower}"

    try:
        r = requests.get(url)
        r.raise_for_status()
        res = r.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP ошибка для '{word_id}': {e}")
        try:
            error_data = r.json()
            if isinstance(error_data, dict) and "title" in error_data:
                print(f"Сообщение от API: {error_data['title']}")
        except json.JSONDecodeError:
            pass  # Не удалось прочитать тело ошибки как JSON
        return False
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса для '{word_id}': {e}")
        return False
    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON для '{word_id}'. Ответ: {r.text[:200]}")
        return False

    if isinstance(res, dict) and "title" in res:  # Например, "No Definitions Found"
        print(f"API сообщение для '{word_id}': {res['title']}")
        return False

    if not isinstance(res, list) or not res:
        print(f"Неожиданный формат ответа для '{word_id}'. Ответ: {str(res)[:200]}")
        return False

    output = {}
    all_definitions = []
    all_synonyms = []
    audio_url = None

    entry = res[0]

    if entry.get("meanings"):
        for meaning in entry["meanings"]:
            part_of_speech = f"({meaning.get('partOfSpeech', '')}) " if meaning.get('partOfSpeech') else ""
            if meaning.get("definitions"):
                for i, definition_item in enumerate(meaning.get("definitions", [])):
                    if definition_item.get("definition"):
                        all_definitions.append(f"👉🏻 {part_of_speech}{definition_item['definition']}")
                    # Собираем синонимы, привязанные к конкретному определению
                    if definition_item.get("synonyms"):
                        for syn in definition_item["synonyms"]:
                            if syn not in all_synonyms:  # Избегаем дубликатов
                                all_synonyms.append(syn)
            # Собираем синонимы, привязанные к части речи (более общие)
            if meaning.get("synonyms"):
                for syn in meaning["synonyms"]:
                    if syn not in all_synonyms:  # Избегаем дубликатов
                        all_synonyms.append(syn)

    if all_definitions:
        output['definitions'] = '\n'.join(all_definitions)

    if all_synonyms:
        # Ограничим количество синонимов для вывода
        output['synonyms'] = ", ".join(list(dict.fromkeys(all_synonyms))[:10])  # Уникальные, до 10 штук

    if entry.get("phonetics"):
        for phonetic_info in entry["phonetics"]:
            if phonetic_info.get("audio") and phonetic_info["audio"].strip():
                audio_url = phonetic_info["audio"]
                # Некоторые API могут предоставлять аудио в разных форматах или для разных регионов,
                # здесь мы берем первое непустое аудио.
                if "opus" not in audio_url:  # Предпочитаем mp3 если есть выбор, opus не всегда хорошо поддерживается
                    output['audio'] = audio_url
                    break
                elif not output.get('audio'):  # Если еще не присвоили, берем opus
                    output['audio'] = audio_url
            if output.get('audio') and "opus" not in output.get('audio', ''):  # Если уже нашли не-opus, выходим
                break

    # Если ничего не нашли, но слово существует (например, только фонетика без аудио)
    if not output:
        # Проверяем, было ли слово в принципе найдено (res[0] существует)
        if entry.get("word"):
            # Можно вернуть что-то минимальное или все же False
            # print(f"Для слова '{entry.get('word')}' не найдено достаточно информации (определений, синонимов, аудио).")
            return False  # Если считаем, что без определений результат неполный
        return False

    return output if output else False


if __name__ == "__main__":
    from pprint import pprint

    print("--- Тест для 'hello' ---")
    pprint(getDefinitions('hello'))
    print("\n--- Тест для 'happy' (должны быть синонимы) ---")
    pprint(getDefinitions('happy'))
    print("\n--- Тест для 'great britain' (скорее всего не найдется) ---")
    pprint(getDefinitions('great britain'))
    print("\n--- Тест для 'nonexistentwordxyz' ---")
    pprint(getDefinitions('nonexistentwordxyz'))
    print("\n--- Тест для слова 'apple' ---")
    pprint(getDefinitions('apple'))

