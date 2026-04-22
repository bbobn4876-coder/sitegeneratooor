import requests
import json
import os
import sys
import re
import zipfile
import shutil
import base64
import random
import time
from pathlib import Path
from byteplussdkarkruntime import Ark
from byteplussdkarkruntime.types.images.images import SequentialImageGenerationOptions
from dotenv import load_dotenv

# Опциональный импорт для Windows (Ctrl+V в password input)
try:
    import win32clipboard  # type: ignore
except ImportError:
    win32clipboard = None  # type: ignore

# Опциональный импорт для воспроизведения звука
try:
    import winsound  # type: ignore
except ImportError:
    winsound = None  # type: ignore

# Загрузка переменных окружения из .env файла (если есть)
load_dotenv()

# ============================================================================
# SOUND NOTIFICATION FUNCTION
# ============================================================================
def play_notification_sound():
    """Воспроизведение звукового уведомления после завершения генерации"""
    # Получаем путь к директории, где находится .exe файл
    if getattr(sys, 'frozen', False):  # type: ignore
        # Если программа запущена как .exe (PyInstaller)
        exe_dir = os.path.dirname(sys.executable)  # type: ignore
    else:
        # Если программа запущена как скрипт
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    notification_file = os.path.join(exe_dir, "notification.mp3")

    try:
        # Проверяем наличие файла notification.mp3 в папке с .exe
        if os.path.exists(notification_file):
            # Для Windows используем winsound
            if winsound and os.name == 'nt':
                try:
                    # Конвертируем mp3 в wav временно или используем системный звук
                    winsound.PlaySound(notification_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                except:
                    # Если не получилось, используем системный beep
                    winsound.MessageBeep()
            else:
                # Для Linux/Mac пытаемся использовать системные команды
                try:
                    if os.name == 'posix':
                        os.system(f'mpg123 -q "{notification_file}" 2>/dev/null &')
                except:
                    pass
        else:
            # Если файла нет, используем системный beep для Windows
            if winsound and os.name == 'nt':
                # Играем мелодичный beep
                winsound.Beep(800, 200)  # частота 800Hz, длительность 200ms
                time.sleep(0.1)
                winsound.Beep(1000, 300)  # частота 1000Hz, длительность 300ms
            else:
                # Для Linux/Mac используем системный beep
                try:
                    os.system('printf "\\a"')
                except:
                    pass
    except Exception as e:
        # Тихо игнорируем ошибки воспроизведения звука
        pass

# ============================================================================
# SECURITY SYSTEM - PASSWORD AUTHENTICATION WITH DEVICE MEMORY
# ============================================================================
def get_device_id():
    """Генерация уникального идентификатора устройства"""
    import hashlib
    import platform
    import uuid

    # Собираем уникальные характеристики устройства
    device_info = []

    # MAC-адрес (наиболее стабильный идентификатор)
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                       for elements in range(0,2*6,2)][::-1])
        device_info.append(mac)
    except:
        pass

    # Hostname
    try:
        device_info.append(platform.node())
    except:
        pass

    # Платформа
    try:
        device_info.append(platform.system())
        device_info.append(platform.machine())
    except:
        pass

    # Создаем хэш из всех характеристик
    device_string = '|'.join(device_info)
    device_hash = hashlib.sha256(device_string.encode()).hexdigest()

    return device_hash

def is_device_trusted(device_id, auth_file):
    """Проверка, является ли устройство доверенным"""
    if not os.path.exists(auth_file):
        return False

    try:
        with open(auth_file, 'r') as f:
            trusted_devices = f.read().strip().split('\n')
            return device_id in trusted_devices
    except:
        return False

def add_trusted_device(device_id, auth_file):
    """Добавление устройства в список доверенных"""
    try:
        # Читаем существующие устройства
        trusted_devices = []
        if os.path.exists(auth_file):
            with open(auth_file, 'r') as f:
                trusted_devices = [line.strip() for line in f.readlines() if line.strip()]

        # Добавляем новое устройство, если его еще нет
        if device_id not in trusted_devices:
            trusted_devices.append(device_id)

        # Сохраняем обратно
        with open(auth_file, 'w') as f:
            f.write('\n'.join(trusted_devices))

        return True
    except:
        return False

def secure_password_input(prompt="Введите пароль: "):
    """Безопасный ввод пароля с поддержкой Ctrl+V (вставка из буфера обмена)"""
    import sys
    import platform

    # Определяем операционную систему
    is_windows = platform.system() == 'Windows'

    if is_windows:
        # Windows: используем msvcrt
        import msvcrt
        print(prompt, end='', flush=True)
        password = []
        while True:
            char = msvcrt.getwch()

            if char == '\r' or char == '\n':  # Enter
                print()
                break
            elif char == '\x03':  # Ctrl+C
                print()
                raise KeyboardInterrupt
            elif char == '\b':  # Backspace
                if len(password) > 0:
                    password.pop()
                    # Стираем последнюю звездочку
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif char == '\x16':  # Ctrl+V
                # Вставка из буфера обмена (Windows)
                if win32clipboard is not None:
                    try:
                        win32clipboard.OpenClipboard()
                        clipboard_data = win32clipboard.GetClipboardData()
                        win32clipboard.CloseClipboard()

                        for c in clipboard_data:
                            password.append(c)
                            sys.stdout.write('*')
                            sys.stdout.flush()
                    except Exception:
                        # Ошибка доступа к буферу обмена - продолжаем без вставки
                        pass
                # Если win32clipboard не доступен - игнорируем Ctrl+V
            else:
                password.append(char)
                sys.stdout.write('*')
                sys.stdout.flush()

        return ''.join(password)

    else:
        # Unix/Linux/macOS: используем termios
        import termios
        import tty

        print(prompt, end='', flush=True)
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)
            password = []

            while True:
                char = sys.stdin.read(1)

                if char == '\r' or char == '\n':  # Enter
                    print()
                    break
                elif char == '\x03':  # Ctrl+C
                    print()
                    raise KeyboardInterrupt
                elif char == '\x7f' or char == '\x08':  # Backspace/Delete
                    if len(password) > 0:
                        password.pop()
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                elif char == '\x16':  # Ctrl+V
                    # На Unix пытаемся прочитать из clipboard через различные методы
                    try:
                        # Пытаемся использовать xclip (Linux)
                        import subprocess
                        try:
                            clipboard_data = subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'],
                                                                    stderr=subprocess.DEVNULL).decode('utf-8')
                        except:
                            # Пытаемся использовать pbpaste (macOS)
                            try:
                                clipboard_data = subprocess.check_output(['pbpaste'],
                                                                        stderr=subprocess.DEVNULL).decode('utf-8')
                            except:
                                clipboard_data = None

                        if clipboard_data:
                            for c in clipboard_data:
                                if c != '\n' and c != '\r':  # Игнорируем переносы строк
                                    password.append(c)
                                    sys.stdout.write('*')
                                    sys.stdout.flush()
                    except:
                        pass
                elif ord(char) >= 32:  # Печатаемые символы
                    password.append(char)
                    sys.stdout.write('*')
                    sys.stdout.flush()

            return ''.join(password)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def verify_access():
    """Проверка доступа через пароль с запоминанием устройства"""
    import hashlib
    import time
    import sys

    # Определяем путь к директории скрипта (работает и для .py и для .exe)
    if getattr(sys, 'frozen', False):
        # Если запущен как .exe (скомпилирован PyInstaller)
        script_dir = os.path.dirname(sys.executable)
    else:
        # Если запущен как обычный .py файл
        script_dir = os.path.dirname(os.path.abspath(__file__))
    password_file = os.path.join(script_dir, 'password.txt')
    auth_file = os.path.join(script_dir, '.auth_devices')

    # Проверка наличия файла с хэшем пароля
    if not os.path.exists(password_file):
        print("\n❌ ОШИБКА: Файл безопасности не найден")
        print("Система заблокирована")
        sys.exit(1)

    # Получаем ID устройства
    device_id = get_device_id()

    # Проверяем, доверенное ли это устройство
    if is_device_trusted(device_id, auth_file):
        print("\n✅ УСТРОЙСТВО РАСПОЗНАНО - Доступ разрешён")
        return True

    # Устройство не доверенное - требуется пароль
    # Чтение хэша пароля из файла
    try:
        with open(password_file, 'r') as f:
            stored_hash = f.read().strip()
    except Exception as e:
        print(f"\n❌ ОШИБКА: Не удалось прочитать файл безопасности")
        sys.exit(1)

    max_attempts = 3
    attempt = 0

    print("\n" + "="*60)
    print("🔐 СИСТЕМА БЕЗОПАСНОСТИ - ТРЕБУЕТСЯ АУТЕНТИФИКАЦИЯ")
    print("🆕 НОВОЕ УСТРОЙСТВО ОБНАРУЖЕНО")
    print("💡 ПОДСКАЗКА: Можно вставить пароль через Ctrl+V")
    print("="*60)

    while attempt < max_attempts:
        try:
            # Безопасный ввод пароля (скрытый) с поддержкой Ctrl+V
            user_password = secure_password_input(f"\nПопытка {attempt + 1}/{max_attempts} - Введите пароль: ")

            # Хэширование введенного пароля
            user_hash = hashlib.sha256(user_password.encode()).hexdigest()

            # Очистка пароля из памяти
            user_password = None
            del user_password

            # Сравнение хэшей
            if user_hash == stored_hash:
                # Очистка хэша из памяти
                user_hash = None
                stored_hash = None
                del user_hash
                del stored_hash

                print("\n✅ ДОСТУП РАЗРЕШЁН")

                # Добавляем устройство в список доверенных
                if add_trusted_device(device_id, auth_file):
                    print("💾 УСТРОЙСТВО СОХРАНЕНО - В следующий раз пароль не потребуется")

                print("="*60 + "\n")
                time.sleep(0.5)
                return True
            else:
                attempt += 1
                remaining = max_attempts - attempt

                if remaining > 0:
                    print(f"\n❌ НЕВЕРНЫЙ ПАРОЛЬ")
                    print(f"⚠️  Осталось попыток: {remaining}")
                    # Задержка между попытками (защита от брутфорса)
                    time.sleep(2)

                # Очистка неверного хэша
                user_hash = None
                del user_hash

        except KeyboardInterrupt:
            print("\n\n❌ ДОСТУП ОТМЕНЁН")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ ОШИБКА: {str(e)}")
            sys.exit(1)

    # Превышено количество попыток
    print("\n" + "="*60)
    print("❌ ДОСТУП ЗАБЛОКИРОВАН")
    print("Превышено максимальное количество попыток")
    print("="*60)
    sys.exit(1)

# Запускаем проверку доступа при импорте модуля (только если запускается напрямую)
if __name__ == "__main__":
    verify_access()

# ============================================================================

class PHPWebsiteGenerator:
    def __init__(self):
        # API ключи (жестко заданные - всегда работают!)
        self.api_key = "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"
        self.bytedance_key = "ark-d010e341-cb4f-4a84-89e7-d26637845463-9bf03"
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.code_model = "google/gemini-2.5-flash"
        self.max_tokens = 65536
        self.use_symfony = False
        self.site_type = "landing"  # "landing" или "multipage"
        self.blueprint = {}
        self.header_code = ""
        self.footer_code = ""
        self.header_footer_css = ""
        self.database_content = ""
        self.template_sites = []
        self.generated_images = []
        self.primary_color = ""  # Основной цвет сайта
        self.num_blog_articles = 0  # Количество статей блога (DISABLED - blog1-blog6 pages removed)
        self.theme_content_cache = {}  # Кэш для контента на основе темы

        # Инициализация Ark клиента для ByteDance Seedream-4.0
        print(f"🔑 Инициализация ByteDance Ark SDK...")
        print(f"   API Key: {self.bytedance_key[:20]}...")
        
        self.ark_client = Ark(
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
            api_key=self.bytedance_key
        )
        print(f"✓ Ark SDK готов\n")

    def get_language_for_country(self, country):
        """Определяет язык для генерации контента на основе страны"""
        country_lower = country.lower()

        # Словарь: страна -> язык
        country_language_map = {
            # Албания
            'albania': 'Albanian', 'албания': 'Albanian',
            # Андорра
            'andorra': 'Catalan', 'андорра': 'Catalan',
            # Армения
            'armenia': 'Armenian', 'армения': 'Armenian',
            # Австрия
            'austria': 'German', 'австрия': 'German',
            # Азербайджан
            'azerbaijan': 'Azerbaijani', 'азербайджан': 'Azerbaijani',
            # Беларусь
            'belarus': 'Belarusian', 'беларусь': 'Belarusian',
            # Бельгия
            'belgium': 'Dutch', 'бельгия': 'Dutch',
            # Босния и Герцеговина
            'bosnia': 'Bosnian', 'herzegovina': 'Bosnian', 'босния': 'Bosnian', 'герцеговина': 'Bosnian',
            # Болгария
            'bulgaria': 'Bulgarian', 'болгария': 'Bulgarian',
            # Великобритания
            'uk': 'English', 'britain': 'English', 'united kingdom': 'English', 'великобритания': 'English',
            # Венгрия
            'hungary': 'Hungarian', 'венгрия': 'Hungarian',
            # Венесуэла
            'venezuela': 'Spanish', 'венесуэла': 'Spanish',
            # Германия
            'germany': 'German', 'германия': 'German',
            # Греция
            'greece': 'Greek', 'греция': 'Greek',
            # Грузия
            'georgia': 'Georgian', 'грузия': 'Georgian',
            # Дания
            'denmark': 'Danish', 'дания': 'Danish',
            # Эстония
            'estonia': 'Estonian', 'эстония': 'Estonian',
            # Испания
            'spain': 'Spanish', 'испания': 'Spanish',
            # Италия
            'italy': 'Italian', 'италия': 'Italian',
            # Кипр
            'cyprus': 'Greek', 'кипр': 'Greek',
            # Латвия
            'latvia': 'Latvian', 'латвия': 'Latvian',
            # Лихтенштейн
            'liechtenstein': 'German', 'лихтенштейн': 'German',
            # Литва
            'lithuania': 'Lithuanian', 'литва': 'Lithuanian',
            # Люксембург
            'luxembourg': 'French', 'люксембург': 'French',
            # Мальта
            'malta': 'Maltese', 'мальта': 'Maltese',
            # Молдавия
            'moldova': 'Romanian', 'молдавия': 'Romanian', 'молдова': 'Romanian',
            # Монако
            'monaco': 'French', 'монако': 'French',
            # Черногория
            'montenegro': 'Montenegrin', 'черногория': 'Montenegrin',
            # Нидерланды
            'netherlands': 'Dutch', 'dutch': 'Dutch', 'holland': 'Dutch', 'нидерланды': 'Dutch', 'голландия': 'Dutch',
            # Норвегия
            'norway': 'Norwegian', 'норвегия': 'Norwegian',
            # Польша
            'poland': 'Polish', 'польша': 'Polish',
            # Португалия
            'portugal': 'Portuguese', 'португалия': 'Portuguese',
            # Македония
            'macedonia': 'Macedonian', 'македония': 'Macedonian',
            # Румыния
            'romania': 'Romanian', 'румыния': 'Romanian',
            # Россия
            'russia': 'Russian', 'россия': 'Russian',
            # Сан-Марино
            'san marino': 'Italian', 'сан-марино': 'Italian',
            # Сербия
            'serbia': 'Serbian', 'сербия': 'Serbian',
            # Словакия
            'slovakia': 'Slovak', 'словакия': 'Slovak',
            # Словения
            'slovenia': 'Slovenian', 'словения': 'Slovenian',
            # Турция
            'turkey': 'Turkish', 'турция': 'Turkish',
            # Украина
            'ukraine': 'Ukrainian', 'украина': 'Ukrainian',
            # Финляндия
            'finland': 'Finnish', 'финляндия': 'Finnish',
            # Франция
            'france': 'French', 'франция': 'French',
            # Хорватия
            'croatia': 'Croatian', 'хорватия': 'Croatian',
            # Чехия
            'czech': 'Czech', 'чехия': 'Czech',
            # Швейцария
            'switzerland': 'German', 'швейцария': 'German',
            # Швеция
            'sweden': 'Swedish', 'швеция': 'Swedish',
        }

        # Ищем язык для страны
        for key, lang in country_language_map.items():
            if key in country_lower:
                return lang

        # По умолчанию English
        return 'English'

    def call_api(self, prompt, max_tokens=65536, model=None):
        """Вызов API OpenRouter с retry логикой и обработкой всех типов ошибок"""
        if model is None:
            model = self.code_model

        if max_tokens > 65536:
            max_tokens = 65536  # Максимальное ограничение
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://php-generator.local",
            "X-Title": "PHP Website Generator"
        }
        
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        # Retry до 5 раз при ошибках
        for attempt in range(5):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=json.dumps(data),
                    timeout=360,  # Увеличен таймаут до 6 минут
                    verify=True   # SSL проверка
                )
                response.raise_for_status()
                result = response.json()
                content = result['choices'][0]['message']['content']
                if not content or not content.strip():
                    print(f"    ⚠️  API вернул пустой контент")
                    if attempt < 4:
                        import time
                        # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                        delay = 5 * (attempt + 1)
                        print(f"    ⏳ Ожидание {delay} секунд перед повторной попыткой...")
                        time.sleep(delay)
                        continue
                    return None
                return content
                
            except requests.exceptions.ChunkedEncodingError as e:
                # Ошибка "Response ended prematurely"
                if attempt < 4:
                    import time
                    # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                    delay = 5 * (attempt + 1)
                    print(f"    ⚠️  Соединение прервано, попытка {attempt + 2}/5... (ожидание {delay}с)")
                    time.sleep(delay)
                    continue
                else:
                    print(f"    ✗ Соединение прервано после 5 попыток")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                # Ошибки соединения
                if attempt < 4:
                    import time
                    # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                    delay = 5 * (attempt + 1)
                    print(f"    ⚠️  Ошибка соединения, попытка {attempt + 2}/5... (ожидание {delay}с)")
                    time.sleep(delay)
                    continue
                else:
                    print(f"    ✗ Ошибка соединения после 5 попыток")
                    return None
                    
            except requests.exceptions.SSLError as e:
                # SSL ошибка - пробуем еще раз
                if attempt < 4:
                    import time
                    # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                    delay = 5 * (attempt + 1)
                    print(f"    ⚠️  SSL ошибка, попытка {attempt + 2}/5... (ожидание {delay}с)")
                    time.sleep(delay)
                    continue
                else:
                    print(f"    ✗ SSL ошибка после 5 попыток")
                    return None
                    
            except requests.exceptions.Timeout as e:
                # Таймаут
                if attempt < 4:
                    import time
                    # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                    delay = 5 * (attempt + 1)
                    print(f"    ⚠️  Таймаут запроса, попытка {attempt + 2}/5... (ожидание {delay}с)")
                    time.sleep(delay)
                    continue
                else:
                    print(f"    ✗ Таймаут после 5 попыток")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code >= 500:
                    if attempt < 4:
                        import time
                        # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                        delay = 5 * (attempt + 1)
                        print(f"    ⚠️  Ошибка сервера {e.response.status_code}, попытка {attempt + 2}/5... (ожидание {delay}с)")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"    ✗ Ошибка API после 5 попыток: {e.response.status_code}")
                        return None
                else:
                    print(f"    ✗ Ошибка API: {e.response.status_code}")
                    return None
                    
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                # Ошибки парсинга JSON ответа
                if attempt < 4:
                    import time
                    # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                    delay = 5 * (attempt + 1)
                    print(f"    ⚠️  Некорректный ответ API, попытка {attempt + 2}/5... (ожидание {delay}с)")
                    time.sleep(delay)
                    continue
                else:
                    print(f"    ✗ Некорректный ответ после 5 попыток")
                    return None
                    
            except Exception as e:
                # Любые другие ошибки
                error_msg = str(e)
                if attempt < 4:
                    import time
                    # Экспоненциальная задержка: 5, 10, 15, 20 секунд
                    delay = 5 * (attempt + 1)
                    print(f"    ⚠️  Ошибка: {error_msg[:50]}, попытка {attempt + 2}/5... (ожидание {delay}с)")
                    time.sleep(delay)
                    continue
                print(f"    ✗ Ошибка после 5 попыток: {error_msg[:100]}")
                return None
        
        return None
    
    def generate_unique_site_name(self, country, theme):
        """Генерация уникального названия сайта через API с учетом тематики"""
        
        # Специализированные промпты для разных тематик
        theme_specific_examples = {
            "Bookstore": "PageTurn, StoryNest, BookHaven, ReadCraft, NovelVault, ChapterHouse",
            "Restaurant": "TasteHub, FlavorCraft, DishDash, CulinaryNest, PlateFlow, BiteSpot",
            "Hotel": "StayNest, RoomHaven, RestPoint, LodgeHub, SleepCraft, InnFlow",
            "Shop": "ShopFlow, CartCraft, MarketNest, StoreHub, BuyPoint, TradeSpot",
            "Fitness": "FitFlow, PowerNest, GymCraft, StrengthHub, ActivePoint, MuscleSpot",
            "Healthcare": "CareNest, MediFlow, HealthHub, WellCraft, CurePoint, VitalSpot",
            "Education": "LearnHub, KnowNest, StudyCraft, EduFlow, BrainPoint, SkillSpot",
            "IT": "CodeNest, TechFlow, ByteCraft, DataHub, CloudPoint, DevSpot",
            "Real Estate": "PropertyNest, HomeHub, EstateFlow, DwellCraft, SpacePoint, HouseSpot",
            "Travel": "WanderHub, TripNest, JourneyCraft, TravelFlow, RoutePoint, TourSpot",
            "IT Training": "SkillForge, CodeAcademy, LearnTech, DevMentor, TechSkills, ByteLearn",
            "Legal Consulting": "LawCounsel, JusticePoint, LegalWise, RightAdvice, LawGuide, CounselHub",
            "Furniture Store": "HomeCraft, FurnishNest, ComfortSpace, StyleHaven, WoodWorks, DecorHub",
            "Online Stores": "StyleCart, FashionFlow, TrendHub, ChicShop, ModaVault, DressPoint",
            "Online Courses": "LearnOnline, CourseHub, SkillStream, EduPath, KnowledgeFlow, StudyWave",
            "Travel Service Ratings": "TripRate, TravelScore, JourneyReview, RateVoyage, TourInsight, TripVerdict",
            "Technology": "TechWave, InnovateLab, FutureCore, DigitalEdge, NextGen, TechVision",
            "Car Sales": "AutoHub, DrivePoint, CarSelect, MotorNest, WheelCraft, VehicleFlow",
            "Psychology": "MindCare, TherapyHub, MentalWell, PsychoSupport, MindFlow, ThoughtSpace",
            "AI Consulting": "AIVision, IntelliConsult, SmartAdvisory, CognitoPartners, AIStrategy, ThinkAI"
        }
        
        # Получаем примеры для конкретной тематики
        examples = theme_specific_examples.get(theme, "TechWave, CloudNest, DataSphere, CodeCraft, ByteForge")
        
        prompt = f"""Generate a unique, creative website name for a {theme} company based in {country}.

CRITICAL REQUIREMENTS:
- The name MUST be directly related to {theme} industry in {country}
- The name should reflect the nature of {theme} business
- Consider the cultural and geographical context of {country}
- 1-3 words maximum
- DO NOT use generic tech words like "Digital", "Tech", "Cyber", "Web", "Net" unless the theme is IT/Technology
- DO NOT use the exact words "{theme}" or "{country}" in the name
- Use creative combinations, metaphors, or related terms specific to {theme}
- The name should sound appropriate for a company operating in {country}

Examples of good names for {theme}: {examples}

Industry-specific guidance for {theme}:
{self._get_industry_guidance(theme)}

Geographic and cultural context for {country}:
- Consider local business naming conventions in {country}
- The name should resonate with customers in {country}
- Avoid names that might be culturally inappropriate or confusing in {country}

Return ONLY the site name, nothing else. No quotes, no punctuation, no explanations."""
        
        response = self.call_api(prompt, max_tokens=50)
        if response:
            # Очистка от лишних символов
            site_name = response.strip().replace('"', '').replace("'", "").replace(".", "").replace(",", "")
            # Берем только первую строку если вернулось несколько
            site_name = site_name.split('\n')[0].strip()
            # Ограничиваем длину
            if len(site_name) > 30:
                site_name = site_name[:30].strip()
            
            # Проверяем, что название не содержит запрещенные слова для неIT тематик
            forbidden_for_non_it = ['digital', 'tech', 'cyber', 'web', 'net', 'byte', 'data', 'cloud', 'code']
            tech_allowed_themes = ['IT', 'Technology', 'Software', 'Digital', 'IT Training', 'Online Courses']
            if theme not in tech_allowed_themes and any(word in site_name.lower() for word in forbidden_for_non_it):
                # Если название неподходящее, используем fallback для тематики
                return self._get_fallback_name(theme)
            
            return site_name if site_name else self._get_fallback_name(theme)
        
        # Fallback если API не ответил
        return self._get_fallback_name(theme)
    
    def _get_industry_guidance(self, theme):
        """Возвращает специфические рекомендации по названию для каждой индустрии"""
        guidance = {
            "Bookstore": "Focus on reading, stories, pages, chapters, authors. Avoid tech terms.",
            "Restaurant": "Focus on food, taste, flavor, cuisine, dishes. Avoid tech terms.",
            "Hotel": "Focus on accommodation, rest, stay, rooms, comfort. Avoid tech terms.",
            "Shop": "Focus on products, shopping, stores, marketplace. Can use tech for e-commerce.",
            "Fitness": "Focus on health, strength, workout, training, body. Avoid tech terms.",
            "Healthcare": "Focus on health, care, wellness, medical, healing. Avoid tech terms.",
            "Education": "Focus on learning, knowledge, teaching, skills. Can use tech for e-learning.",
            "IT": "Focus on technology, software, code, data, digital solutions.",
            "Real Estate": "Focus on property, homes, spaces, dwellings. Avoid tech terms.",
            "Travel": "Focus on journey, destinations, adventure, exploration. Avoid tech terms.",
            "IT Training": "Focus on learning, skills, coding, development, education. Can use tech terms.",
            "Legal Consulting": "Focus on law, justice, counsel, legal advice, rights. Avoid tech terms.",
            "Furniture Store": "Focus on furniture, home, comfort, style, wood, decor. Avoid tech terms.",
            "Online Stores": "Focus on fashion, style, clothing, shopping, trends. Can use e-commerce tech terms.",
            "Online Courses": "Focus on learning, education, knowledge, training, skills. Can use tech terms.",
            "Travel Service Ratings": "Focus on reviews, ratings, travel, trips, feedback. Avoid tech terms.",
            "Technology": "Focus on innovation, tech, digital, future, solutions, cutting-edge.",
            "Car Sales": "Focus on cars, vehicles, automotive, driving, wheels. Avoid tech terms unless for electric/smart cars.",
            "Psychology": "Focus on mind, mental health, therapy, wellness, counseling. Avoid tech terms.",
            "AI Consulting": "Focus on artificial intelligence, consulting, strategy, business improvement, innovation, smart solutions. Can use AI and tech terms."
        }
        return guidance.get(theme, "Create a name that reflects the core business values and services.")
    
    def _get_fallback_name(self, theme):
        """Возвращает fallback название специфичное для тематики"""
        fallback_names = {
            "Bookstore": ["PageTurn", "StoryNest", "BookHaven", "ReadCraft", "NovelVault", "ChapterHouse"],
            "Restaurant": ["TasteHub", "FlavorCraft", "DishDash", "CulinaryNest", "PlateFlow"],
            "Hotel": ["StayNest", "RoomHaven", "RestPoint", "LodgeHub", "SleepCraft"],
            "Shop": ["ShopFlow", "CartCraft", "MarketNest", "StoreHub", "BuyPoint"],
            "Fitness": ["FitFlow", "PowerNest", "GymCraft", "StrengthHub", "ActivePoint"],
            "Healthcare": ["CareNest", "MediFlow", "HealthHub", "WellCraft", "CurePoint"],
            "Education": ["LearnHub", "KnowNest", "StudyCraft", "EduFlow", "BrainPoint"],
            "IT": ["TechWave", "CloudNest", "DataSphere", "CodeCraft", "ByteForge"],
            "Real Estate": ["PropertyNest", "HomeHub", "EstateFlow", "DwellCraft", "SpacePoint"],
            "Travel": ["WanderHub", "TripNest", "JourneyCraft", "TravelFlow", "RoutePoint"],
            "IT Training": ["SkillForge", "CodeAcademy", "LearnTech", "DevMentor", "TechSkills"],
            "Legal Consulting": ["LawCounsel", "JusticePoint", "LegalWise", "RightAdvice", "LawGuide"],
            "Furniture Store": ["HomeCraft", "FurnishNest", "ComfortSpace", "StyleHaven", "WoodWorks"],
            "Online Stores": ["StyleCart", "FashionFlow", "TrendHub", "ChicShop", "ModaVault"],
            "Online Courses": ["LearnOnline", "CourseHub", "SkillStream", "EduPath", "KnowledgeFlow"],
            "Travel Service Ratings": ["TripRate", "TravelScore", "JourneyReview", "RateVoyage", "TourInsight"],
            "Technology": ["TechWave", "InnovateLab", "FutureCore", "DigitalEdge", "NextGen"],
            "Car Sales": ["AutoHub", "DrivePoint", "CarSelect", "MotorNest", "WheelCraft"],
            "Psychology": ["MindCare", "TherapyHub", "MentalWell", "PsychoSupport", "MindFlow"],
            "AI Consulting": ["AIVision", "IntelliConsult", "SmartAdvisory", "CognitoPartners", "AIStrategy"]
        }
        names = fallback_names.get(theme, ["TechWave", "CloudNest", "DataSphere", "CodeCraft", "ByteForge"])
        return random.choice(names)

    def generate_site_name_from_blueprint(self, blueprint):
        """
        API-style метод: принимает blueprint как запрос и генерирует название сайта.
        Это позволяет использовать полный контекст из blueprint для генерации названия.

        Args:
            blueprint (dict): Blueprint с данными о сайте (theme, country, color_scheme и т.д.)

        Returns:
            str: Сгенерированное название сайта
        """
        # Извлекаем необходимые данные из blueprint
        theme = blueprint.get('theme', 'Business')
        country = blueprint.get('country', 'USA')
        color_scheme = blueprint.get('color_scheme', {})

        # Можно использовать дополнительный контекст из blueprint
        # Например, цветовую схему для более персонализированной генерации
        print(f"  📡 Отправка blueprint в API для генерации названия...")
        print(f"     Theme: {theme}, Country: {country}")

        # В будущем сюда можно добавить больше параметров из blueprint
        # например: sections, header_layout, footer_layout и т.д.
        # для более точной генерации названия

        # Вызываем существующую логику генерации
        site_name = self.generate_unique_site_name(country, theme)

        print(f"  ✓ API вернул название: {site_name}")
        return site_name

    def get_country_contact_data(self, country):
        """Возвращает разные номера телефонов и адреса в зависимости от страны"""
        country_lower = country.lower()

        # Данные по странам
        country_data = {
            'netherlands': {
                'phones': ['+31 20 684 2937', '+31 10 472 8156', '+31 30 591 3842'],
                'cities': ['Amsterdam', 'Rotterdam', 'Utrecht', 'The Hague', 'Eindhoven', 'Groningen'],
                'streets': ['Damrak', 'Kalverstraat', 'Leidsestraat', 'Nieuwendijk', 'Rokin'],
                'postal_codes': ['1012 AB', '3011 AD', '3512 AB', '2511 CM', '5611 AA']
            },
            'usa': {
                'phones': ['+1 (555) 827-4163', '+1 (555) 392-6847', '+1 (555) 718-2945'],
                'cities': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia'],
                'streets': ['Main Street', 'Broadway', 'Park Avenue', 'Wall Street', 'Market Street'],
                'postal_codes': ['10001', '90001', '60601', '77001', '85001']
            },
            'uk': {
                'phones': ['+44 20 7946 3825', '+44 161 824 7593', '+44 131 596 2847'],
                'cities': ['London', 'Manchester', 'Birmingham', 'Edinburgh', 'Liverpool', 'Bristol'],
                'streets': ['High Street', 'King Street', 'Oxford Street', 'Queen Street', 'Victoria Road'],
                'postal_codes': ['SW1A 1AA', 'M1 1AD', 'B1 1AA', 'EH1 1YZ', 'L1 8JQ']
            },
            'germany': {
                'phones': ['+49 30 8294 6375', '+49 89 5738 2946', '+49 40 6182 7394'],
                'cities': ['Berlin', 'Munich', 'Hamburg', 'Frankfurt', 'Cologne', 'Stuttgart'],
                'streets': ['Hauptstraße', 'Bahnhofstraße', 'Marktplatz', 'Kirchstraße', 'Schulstraße'],
                'postal_codes': ['10115', '80331', '20095', '60311', '50667']
            },
            'france': {
                'phones': ['+33 1 42 68 97 35', '+33 4 72 84 61 93', '+33 5 61 38 94 27'],
                'cities': ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Nice', 'Bordeaux'],
                'streets': ['Rue de la Paix', 'Avenue des Champs-Élysées', 'Rue Royale', 'Boulevard Haussmann'],
                'postal_codes': ['75001', '69001', '13001', '31000', '06000']
            },
            'poland': {
                'phones': ['+48 22 594 8372', '+48 12 374 9185', '+48 61 829 4736'],
                'cities': ['Warsaw', 'Krakow', 'Poznan', 'Wroclaw', 'Gdansk', 'Lodz'],
                'streets': ['ul. Nowy Świat', 'ul. Floriańska', 'ul. Piotrkowska', 'ul. Marszałkowska', 'ul. Długa'],
                'postal_codes': ['00-001', '30-001', '61-001', '50-001', '80-001']
            },
            'spain': {
                'phones': ['+34 91 528 4736', '+34 93 274 9185', '+34 95 482 7364'],
                'cities': ['Madrid', 'Barcelona', 'Seville', 'Valencia', 'Bilbao', 'Malaga'],
                'streets': ['Calle Mayor', 'Gran Via', 'Paseo de Gracia', 'Calle Alcalá', 'Rambla'],
                'postal_codes': ['28001', '08001', '41001', '46001', '48001']
            },
            'italy': {
                'phones': ['+39 06 4829 5173', '+39 02 5738 2946', '+39 055 394 8271'],
                'cities': ['Rome', 'Milan', 'Florence', 'Venice', 'Naples', 'Turin'],
                'streets': ['Via del Corso', 'Via Montenapoleone', 'Via Roma', 'Via Garibaldi', 'Piazza Navona'],
                'postal_codes': ['00186', '20121', '50122', '30121', '80133']
            },
            'russia': {
                'phones': ['+7 495 628 4937', '+7 812 574 8293', '+7 383 925 7384'],
                'cities': ['Moscow', 'St Petersburg', 'Novosibirsk', 'Yekaterinburg', 'Kazan', 'Nizhny Novgorod'],
                'streets': ['Tverskaya Street', 'Nevsky Prospekt', 'Lenina Street', 'Krasnaya Street', 'Arbat Street'],
                'postal_codes': ['101000', '190000', '630000', '620000', '420000']
            },
            'ukraine': {
                'phones': ['+380 44 528 7394', '+380 56 374 8295', '+380 32 685 2947'],
                'cities': ['Kyiv', 'Kharkiv', 'Odesa', 'Dnipro', 'Lviv', 'Zaporizhzhia'],
                'streets': ['Khreshchatyk Street', 'Sumska Street', 'Deribasivska Street', 'Shevchenka Avenue', 'Prospekt Svobody'],
                'postal_codes': ['01001', '61001', '65001', '49000', '79000']
            },
            'turkey': {
                'phones': ['+90 212 528 4937', '+90 312 684 2957', '+90 232 795 3841'],
                'cities': ['Istanbul', 'Ankara', 'Izmir', 'Bursa', 'Antalya', 'Adana'],
                'streets': ['Istiklal Caddesi', 'Atatürk Bulvarı', 'Kordon', 'Cumhuriyet Caddesi', 'Bağdat Caddesi'],
                'postal_codes': ['34000', '06000', '35000', '16000', '07000']
            },
            'sweden': {
                'phones': ['+46 8 528 4937', '+46 31 694 8275', '+46 40 582 7394'],
                'cities': ['Stockholm', 'Gothenburg', 'Malmö', 'Uppsala', 'Västerås', 'Örebro'],
                'streets': ['Drottninggatan', 'Kungsgatan', 'Storgatan', 'Vasagatan', 'Norrlandsgatan'],
                'postal_codes': ['111 20', '411 05', '211 20', '753 10', '722 11']
            },
            'norway': {
                'phones': ['+47 22 58 49 37', '+47 55 28 64 93', '+47 73 94 82 75'],
                'cities': ['Oslo', 'Bergen', 'Trondheim', 'Stavanger', 'Drammen', 'Fredrikstad'],
                'streets': ['Karl Johans gate', 'Storgaten', 'Torggaten', 'Jernbanetorget', 'Olav Kyrres gate'],
                'postal_codes': ['0150', '5003', '7011', '4001', '3044']
            },
            'denmark': {
                'phones': ['+45 33 52 84 93', '+45 86 29 47 58', '+45 98 74 52 83'],
                'cities': ['Copenhagen', 'Aarhus', 'Odense', 'Aalborg', 'Esbjerg', 'Randers'],
                'streets': ['Strøget', 'Vestergade', 'Nørregade', 'Østergade', 'Kongens Nytorv'],
                'postal_codes': ['1000', '8000', '5000', '9000', '6700']
            },
            'finland': {
                'phones': ['+358 9 528 4937', '+358 3 694 8275', '+358 8 472 9385'],
                'cities': ['Helsinki', 'Espoo', 'Tampere', 'Vantaa', 'Oulu', 'Turku'],
                'streets': ['Aleksanterinkatu', 'Mannerheimintie', 'Hämeenkatu', 'Yliopistonkatu', 'Kauppakatu'],
                'postal_codes': ['00100', '02100', '33100', '01300', '90100']
            },
            'czech': {
                'phones': ['+420 2 5284 9375', '+420 5 3749 2856', '+420 3 8425 7394'],
                'cities': ['Prague', 'Brno', 'Ostrava', 'Plzeň', 'Liberec', 'Olomouc'],
                'streets': ['Václavské náměstí', 'Národní třída', 'Na Příkopě', 'Masarykova', 'Česká'],
                'postal_codes': ['110 00', '602 00', '702 00', '301 00', '460 00']
            },
            'austria': {
                'phones': ['+43 1 528 4937', '+43 316 749 285', '+43 732 684 295'],
                'cities': ['Vienna', 'Graz', 'Linz', 'Salzburg', 'Innsbruck', 'Klagenfurt'],
                'streets': ['Kärntner Straße', 'Herrengasse', 'Landstraße', 'Graben', 'Mariahilfer Straße'],
                'postal_codes': ['1010', '8010', '4020', '5020', '6020']
            },
            'switzerland': {
                'phones': ['+41 44 528 49 37', '+41 22 694 82 75', '+41 31 582 73 94'],
                'cities': ['Zurich', 'Geneva', 'Basel', 'Bern', 'Lausanne', 'Winterthur'],
                'streets': ['Bahnhofstrasse', 'Rue du Rhône', 'Freie Strasse', 'Kramgasse', 'Rue de Lausanne'],
                'postal_codes': ['8001', '1201', '4001', '3011', '1003']
            },
            'portugal': {
                'phones': ['+351 21 528 4937', '+351 22 694 8275', '+351 239 582 749'],
                'cities': ['Lisbon', 'Porto', 'Coimbra', 'Braga', 'Faro', 'Funchal'],
                'streets': ['Avenida da Liberdade', 'Rua de Santa Catarina', 'Rua Ferreira Borges', 'Rua Augusta', 'Rua do Carmo'],
                'postal_codes': ['1250-001', '4000-001', '3000-001', '4700-001', '8000-001']
            },
            'romania': {
                'phones': ['+40 21 528 4937', '+40 264 749 285', '+40 256 682 749'],
                'cities': ['Bucharest', 'Cluj-Napoca', 'Timișoara', 'Iași', 'Constanța', 'Craiova'],
                'streets': ['Calea Victoriei', 'Strada Eroilor', 'Bulevardul Unirii', 'Strada Republicii', 'Bulevardul Ferdinand'],
                'postal_codes': ['010001', '400001', '300001', '700001', '900001']
            },
            'greece': {
                'phones': ['+30 21 0528 4937', '+30 231 0749 285', '+30 261 0682 749'],
                'cities': ['Athens', 'Thessaloniki', 'Patras', 'Heraklion', 'Larissa', 'Volos'],
                'streets': ['Ermou', 'Tsimiski', 'Agiou Nikolaou', 'Syntagma Square', 'Aristotelous'],
                'postal_codes': ['105 63', '546 24', '262 21', '712 01', '412 22']
            },
            'hungary': {
                'phones': ['+36 1 528 4937', '+36 62 749 285', '+36 52 682 749'],
                'cities': ['Budapest', 'Debrecen', 'Szeged', 'Miskolc', 'Pécs', 'Győr'],
                'streets': ['Váci utca', 'Andrássy út', 'Kossuth utca', 'Petőfi utca', 'Rákóczi út'],
                'postal_codes': ['1051', '4024', '6720', '3525', '7621']
            },
            'belgium': {
                'phones': ['+32 2 528 49 37', '+32 3 694 82 75', '+32 9 582 73 94'],
                'cities': ['Brussels', 'Antwerp', 'Ghent', 'Charleroi', 'Liège', 'Bruges'],
                'streets': ['Avenue Louise', 'Meir', 'Veldstraat', 'Rue Neuve', 'Korenmarkt'],
                'postal_codes': ['1000', '2000', '9000', '6000', '4000']
            },
            'bulgaria': {
                'phones': ['+359 2 528 4937', '+359 32 694 827', '+359 52 582 739'],
                'cities': ['Sofia', 'Plovdiv', 'Varna', 'Burgas', 'Ruse', 'Stara Zagora'],
                'streets': ['Vitosha Boulevard', 'Glavnata Street', 'Knyaz Boris I Boulevard', 'Aleksandrovska Street', 'Tsar Simeon Street'],
                'postal_codes': ['1000', '4000', '9000', '8000', '7000']
            },
            'croatia': {
                'phones': ['+385 1 528 4937', '+385 21 694 827', '+385 52 582 739'],
                'cities': ['Zagreb', 'Split', 'Rijeka', 'Osijek', 'Zadar', 'Pula'],
                'streets': ['Ilica', 'Riva', 'Korzo', 'Kapucinska', 'Kalelarga'],
                'postal_codes': ['10000', '21000', '51000', '31000', '23000']
            },
            'serbia': {
                'phones': ['+381 11 528 4937', '+381 21 694 827', '+381 18 582 739'],
                'cities': ['Belgrade', 'Novi Sad', 'Niš', 'Kragujevac', 'Subotica', 'Zemun'],
                'streets': ['Knez Mihailova', 'Zmaj Jovina', 'Obrenovićeva', 'Kralja Milana', 'Bulevar Oslobođenja'],
                'postal_codes': ['11000', '21000', '18000', '34000', '24000']
            },
            'slovakia': {
                'phones': ['+421 2 5284 9375', '+421 55 694 8275', '+421 37 582 7394'],
                'cities': ['Bratislava', 'Košice', 'Prešov', 'Nitra', 'Žilina', 'Banská Bystrica'],
                'streets': ['Obchodná', 'Hlavná', 'Masarykova', 'Štefánikova', 'Námestie SNP'],
                'postal_codes': ['811 01', '040 01', '080 01', '949 01', '010 01']
            }
        }

        # Определяем страну
        for key in country_data.keys():
            if key in country_lower:
                data = country_data[key]
                # Генерируем случайный номер и адрес
                phone = random.choice(data['phones'])
                city = random.choice(data['cities'])
                street_num = random.randint(1, 999)
                street = random.choice(data['streets'])
                postal = random.choice(data['postal_codes'])

                return {
                    'phone': phone,
                    'address': f"{street_num} {street}, {city} {postal}"
                }

        # Fallback если страна не найдена
        return {
            'phone': '+1 (555) 739-2814',
            'address': '456 Business Street, Suite 200, New York, NY 10001'
        }

    def generate_theme_content_via_api(self, theme, content_type, num_items=4, page_context=None):
        """
        Генерирует контент на основе темы через API

        Args:
            theme: Тема сайта (например, "Travel", "Restaurant", "Cryptocurrency")
            content_type: Тип контента ("process_steps", "featured_solutions", "approach_content", "services")
            num_items: Количество элементов для генерации
            page_context: Контекст страницы (например, "home", "company") для уникальной генерации

        Returns:
            Структурированный контент в виде списка словарей или словаря
        """
        # Получаем язык и страну из blueprint
        language = self.blueprint.get('language', 'English')
        country = self.blueprint.get('country', '')

        # Проверяем кэш (теперь с учетом языка, страны и контекста страницы)
        cache_key = f"{theme}_{content_type}_{num_items}_{language}_{country}"
        if page_context:
            cache_key = f"{cache_key}_{page_context}"
        if cache_key in self.theme_content_cache:
            return self.theme_content_cache[cache_key]

        # Максимальное количество попыток генерации перед fallback
        max_retries = 5

        # Пытаемся сгенерировать контент с несколькими попытками
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                print(f"    ⚠️  Попытка {attempt}/{max_retries} генерации контента...")

            result = self._generate_content_attempt(theme, content_type, num_items, language, country, cache_key)

            if result is not None:
                return result

            # Если это была не последняя попытка, пробуем снова
            if attempt < max_retries:
                import time
                time.sleep(0.5)  # Небольшая пауза между попытками

        # Если все попытки не удались
        print(f"    ✗ Все {max_retries} попыток генерации не удались для {content_type}, будет использован fallback")
        return None

    def _generate_content_attempt(self, theme, content_type, num_items, language, country, cache_key):
        """
        Одна попытка генерации контента через API

        Returns:
            Контент или None если попытка не удалась
        """

        # ГЛОБАЛЬНАЯ инструкция - ЗАПРЕТ ЦЕН для ВСЕХ тематик
        global_price_ban = "\n\nCRITICAL REQUIREMENT: Do NOT mention ANY prices, costs, pricing information, dollar amounts, savings, or monetary values. Focus ONLY on features, benefits, quality, and outcomes."

        # Специальные инструкции для определенных тем
        theme_specific_instructions = ""
        if theme == "Furniture Store":
            theme_specific_instructions = "\nIMPORTANT: Focus on quality, style, craftsmanship, and design features."
        elif theme == "Online Stores":
            theme_specific_instructions = "\nIMPORTANT: This is a women's clothing store. Focus on women's fashion, apparel, and accessories."

        # Инструкция о языке - КРИТИЧЕСКИ ВАЖНАЯ
        language_instruction = f"\n\nCRITICAL LANGUAGE REQUIREMENT: You MUST generate ALL content EXCLUSIVELY in {language} language. Every single word, title, description, and text MUST be in {language}. Do NOT use English or any other language. This is MANDATORY and NON-NEGOTIABLE. Language: {language}."

        # Создаем промпт в зависимости от типа контента
        if content_type == "process_steps":
            prompt = f"""Generate {num_items} process steps for a {theme} business/website.
Return the result as a JSON array of objects, where each object has:
- "title": short step title (2-4 words)
- "description": detailed step description (1-2 sentences)

Make the content highly specific to the {theme} industry. Use industry-specific terminology and realistic workflow.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example format:
[
  {{"title": "Step Title", "description": "Detailed description of this step."}},
  ...
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "featured_solutions":
            prompt = f"""Generate {num_items} featured solutions/services for a {theme} business.
Return the result as a JSON array of objects, where each object has:
- "title": solution/service name (2-4 words)
- "description": compelling description (1-2 sentences)
- "image": placeholder image filename like "service1.jpg", "service2.jpg", etc.

Make the content highly specific to the {theme} industry. Focus on real solutions that such a business would offer.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example format:
[
  {{"title": "Solution Name", "description": "Description of the solution.", "image": "service1.jpg"}},
  ...
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "approach_content":
            prompt = f"""Generate approach/philosophy content for a {theme} business.
Return the result as a JSON object with these exact keys:
- "approach_badge": Badge label for approach section (2-3 words, e.g., "Our Philosophy", "Our Approach")
- "approach_title": Section title (e.g., "Our Approach")
- "approach_text1": First paragraph about approach (2-3 sentences)
- "approach_text2": Second paragraph about approach (2-3 sentences)
- "why_badge": Badge label for advantages section (2-3 words, e.g., "Our Advantages", "Why Us")
- "why_title": Why choose us section title (e.g., "Why Choose Us")
- "why_text1": First paragraph about why choose (2-3 sentences, include "{theme}" in the text)
- "why_text2": Second paragraph about why choose (2-3 sentences)

Make the content highly specific to the {theme} industry and business model.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example format:
{{
  "approach_badge": "Our Philosophy",
  "approach_title": "Our Approach",
  "approach_text1": "...",
  "approach_text2": "...",
  "why_badge": "Our Advantages",
  "why_title": "Why Choose Us",
  "why_text1": "...",
  "why_text2": "..."
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "services":
            prompt = f"""Generate {num_items} services/offerings for a {theme} business.
Return the result as a JSON array of objects, where each object has:
- "title": service name (2-4 words)
- "description": service description (1-2 sentences)

Make the content highly specific to the {theme} industry. These should be core services that such a business would realistically offer.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example format:
[
  {{"title": "Service Name", "description": "Description of the service."}},
  ...
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "work_showcase":
            prompt = f"""Generate work showcase section for a {theme} business with {num_items} case studies.

Return as JSON object with these EXACT fields:
- "section_heading": Section heading (3-5 words, e.g., "Our Work & Expertise", "Portfolio & Projects")
- "section_description": Section description (2 sentences, 25-35 words)
- "cases": Array of {num_items} case studies, each with:
  * "title": case title (3-5 words)
  * "description": project description (2 sentences max, 40 words max)
  * "metrics": array of exactly 3 short metrics (5-8 words each)
- "cta_heading": CTA heading at bottom (4-7 words, action-oriented)
- "cta_description": CTA description (2 sentences, 20-30 words)
- "cta_button": CTA button text (2-4 words)

Be specific to {theme} industry. Keep descriptions concise.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "section_heading": "Our Work & Expertise",
  "section_description": "We bring proven experience and innovative solutions to every project. Here are some highlights from our journey in delivering exceptional results.",
  "cases": [
    {{"title": "Digital Platform Launch", "description": "Created comprehensive solution for enterprise client. Delivered measurable improvements in efficiency and user satisfaction.", "metrics": ["Enhanced operational efficiency", "Improved user experience", "Successful deployment"]}},
    {{"title": "System Optimization", "description": "Modernized infrastructure for growing organization. Achieved better performance through strategic improvements.", "metrics": ["Better system performance", "Increased capacity", "Enhanced security"]}}
  ],
  "cta_heading": "Ready to Create Your Success Story?",
  "cta_description": "These are just a few examples of how we've helped organizations achieve their goals. Let's discuss how we can bring similar results to your business.",
  "cta_button": "Start Your Project"
}}

Return ONLY complete valid JSON object. No markdown, no extra text."""

        elif content_type == "about_content":
            from datetime import datetime
            current_year = datetime.now().year

            prompt = f"""Generate About Us section content for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Section heading (e.g., "About Us", "Who We Are", etc.) - translate to the target language
- "founded_year": Realistic founding year (choose a year between 2000 and {current_year-2}, make it believable for this industry)
- "paragraph1": First paragraph about the company (2-3 sentences describing mission/services)
- "paragraph2": UNIQUE company history and story (2-3 sentences about how the company started, key milestones, growth journey - make it specific and interesting, avoid generic statements)
- "button_text": Button text (e.g., "Learn More", "Discover More", etc.) - translate to the target language

IMPORTANT: Make the history paragraph UNIQUE and specific. Include details like:
- How the company started (founder's vision, initial challenge they solved)
- Key growth milestone or turning point
- Evolution of services or specialization
- What makes their journey distinctive

Be specific to {theme} industry.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "About Us",
  "founded_year": "2015",
  "paragraph1": "We are dedicated to providing exceptional {theme} services that transform businesses through innovative solutions and strategic expertise.",
  "paragraph2": "Founded by a team of industry veterans who recognized the growing need for specialized {theme} solutions, we've grown from a boutique consultancy to a trusted partner for organizations worldwide. Our breakthrough came in 2018 when we pioneered a unique methodology that reduced implementation time by 40%, establishing us as innovators in the field.",
  "button_text": "Learn More"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "gallery_content":
            prompt = f"""Generate Gallery section content for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Section heading (e.g., "Our Gallery", "Portfolio", "Our Work", etc.) - translate to the target language
- "subheading": Brief subtitle (1 sentence describing the gallery)
- "captions": Array of exactly 3 short captions for gallery items (3-5 words each) - these represent different aspects of the work

Be specific to {theme} industry.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Our Gallery",
  "subheading": "Explore our latest projects and achievements",
  "captions": ["Professional Excellence", "Quality Service", "Innovation"]
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "blog_posts":
            from datetime import datetime
            current_year = datetime.now().year
            prompt = f"""Generate {num_items} blog post previews for a {theme} business.

Return as JSON array with these EXACT fields for each post:
- "title": Blog post title (5-8 words)
- "excerpt": Brief excerpt/summary (15-20 words)
- "date": Recent date in format "Month DD, YYYY" (use realistic recent dates from {current_year})

Be specific to {theme} industry. Topics should be relevant, educational, or industry news.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
[
  {{"title": "The Future of {theme}", "excerpt": "Explore the latest innovations and what they mean for your business", "date": "November 15, {current_year}"}},
  {{"title": "Top 5 Trends in {theme}", "excerpt": "Stay competitive with these emerging trends in the industry", "date": "November 10, {current_year}"}}
]

Return ONLY valid JSON array with {num_items} items, no additional text or markdown formatting."""

        elif content_type == "hero_content":
            prompt = f"""Generate hero section content for a {theme} business.

Return as JSON object with these EXACT fields:
- "title": Main hero title (3-6 words, should be impactful)
- "subtitle": Hero subtitle/tagline (10-15 words, describing value proposition)
- "button_primary": Primary button text (2-3 words, call to action)
- "button_secondary": Secondary button text (2-3 words, alternative action)

Be specific to {theme} industry. Make it compelling and professional.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "title": "Transform Your Business",
  "subtitle": "Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.",
  "button_primary": "Get Started",
  "button_secondary": "Learn More"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "achievements_content":
            prompt = f"""Generate achievements/statistics section for a {theme} business.{language_instruction}

CRITICAL TRANSLATION REQUIREMENTS:
- ALL fields including "heading" and ALL "stat_label" fields MUST be in {language}
- Do NOT use English for ANY field, especially not for stat labels
- Translate ALL text: "heading", "stat1_label", "stat2_label", "stat3_label", "stat4_label"
- Numbers can stay as-is (like "500+", "98%"), but labels MUST be in {language}

Return as JSON object with these EXACT fields:
- "heading": Section heading in {language} (e.g., achievements, statistics, results)
- "stat1_number": First statistic number (e.g., "500+", "15+")
- "stat1_label": First statistic label in {language} (2-3 words, specific to {theme})
- "stat2_number": Second statistic number
- "stat2_label": Second statistic label in {language} (2-3 words, specific to {theme})
- "stat3_number": Third statistic number
- "stat3_label": Third statistic label in {language} (2-3 words, specific to {theme})
- "stat4_number": Fourth statistic number
- "stat4_label": Fourth statistic label in {language} (2-3 words, specific to {theme})

Be specific to {theme} industry. Use realistic, impressive but believable numbers.{global_price_ban}{theme_specific_instructions}

REMEMBER: Every single word in heading and labels MUST be in {language} language. NO English words allowed!

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "testimonials_content":
            # Специальная инструкция для имен в зависимости от страны
            names_instruction = ""
            if country == "USA":
                names_instruction = "\n\nCRITICAL NAMES REQUIREMENT: Generate ENGLISH names ONLY for client names (e.g., Sarah Johnson, Michael Chen, Emily Rodriguez, David Williams, Jennifer Martinez, James Anderson). Use diverse English first and last names typical for USA. Do NOT use non-English names. All client names must be in English regardless of the content language."

            prompt = f"""Generate {num_items} client testimonials for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Section heading (2-4 words, e.g., "What Our Clients Say", "Client Reviews", "Testimonials")
- "testimonials": Array of {num_items} testimonials, each with:
  * "quote": The testimonial text (15-25 words, authentic and specific)
  * "name": Client full name
  * "position": Job title (2-4 words)
  * "company": Company name or description (2-4 words)
  * "rating": Always "5" (5 stars)

IMPORTANT: Generate UNIQUE names each time - do not repeat the same names. Each testimonial should have a different person's name.

Be specific to {theme} industry. Make testimonials sound genuine and professional.{global_price_ban}{theme_specific_instructions}{language_instruction}{names_instruction}

Example:
{{
  "heading": "What Our Clients Say",
  "testimonials": [
    {{"quote": "Outstanding service and exceptional results. The team went above and beyond to ensure our project's success.", "name": "John Anderson", "position": "CEO", "company": "Tech Solutions", "rating": "5"}},
    {{"quote": "Professional, reliable, and highly skilled. They delivered exactly what we needed, on time and within budget.", "name": "Sarah Mitchell", "position": "Director", "company": "Marketing Agency", "rating": "5"}}
  ]
}}

Return ONLY valid JSON object, no additional text or markdown formatting."""

        elif content_type == "benefits_content":
            prompt = f"""Generate {num_items} key benefits for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Section heading (2-3 words, e.g., "Key Benefits", "Our Advantages", "Why Choose Us")
- "subheading": Supporting subheading text (10-20 words, e.g., "We deliver exceptional results through our commitment to quality, innovation, and customer satisfaction")
- "benefits": Array of {num_items} benefits, each with:
  * "title": Benefit name (2-4 words)
  * "description": Benefit description (10-15 words)

Be specific to {theme} industry. Focus on real business benefits.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Key Benefits",
  "subheading": "We deliver exceptional results through our commitment to quality, innovation, and customer satisfaction",
  "benefits": [
    {{"title": "Cost Efficiency", "description": "Maximize your ROI with our optimized processes and competitive pricing structure"}},
    {{"title": "Scalability", "description": "Solutions designed to grow with your business needs and adapt to market changes"}},
    {{"title": "24/7 Support", "description": "Round-the-clock assistance to ensure your operations run smoothly"}}
  ]
}}

Return ONLY valid JSON object, no additional text or markdown formatting."""

        elif content_type == "cta_content":
            prompt = f"""Generate call-to-action section content for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": CTA heading (3-6 words, should be action-oriented)
- "subheading": Supporting text (10-15 words, explain the value)
- "button_primary": Primary button text (2-4 words)
- "button_secondary": Secondary button text (2-4 words)

Be specific to {theme} industry. Make it compelling and clear.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Ready to Get Started?",
  "subheading": "Let's discuss how we can help you achieve your goals and transform your business",
  "button_primary": "Contact Us Today",
  "button_secondary": "View Services"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "contact_page_content":
            prompt = f"""Generate contact page content for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Page heading (2-4 words, e.g., "Contact Us", "Get In Touch")
- "subheading": Page description (15-20 words)
- "name_label": Form field label for name (1-2 words)
- "email_label": Form field label for email (1-2 words)
- "phone_label": Form field label for phone (1-2 words)
- "message_label": Form field label for message (1-2 words)
- "submit_button": Submit button text (2-3 words)
- "info_heading": Contact info section heading (2-3 words)
- "address_label": Address label (1 word)
- "phone_label_display": Phone display label (1 word)
- "email_label_display": Email display label (1 word)

{language_instruction}

Example:
{{
  "heading": "Contact Us",
  "subheading": "Have a question or want to discuss your project? We'd love to hear from you. Fill out the form below.",
  "name_label": "Your Name",
  "email_label": "Email",
  "phone_label": "Phone",
  "message_label": "Message",
  "submit_button": "Send Message",
  "info_heading": "Contact Information",
  "address_label": "Address",
  "phone_label_display": "Phone",
  "email_label_display": "Email"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "blog_page_content":
            prompt = f"""Generate blog page content for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Page heading (2-4 words, e.g., "Our Blog", "Latest News", "Insights")
- "subheading": Page description (10-15 words)
- "read_more": Read more button text (2-3 words)
- "no_posts": Message when no posts available (5-8 words)

Be specific to {theme} industry.{language_instruction}

Example:
{{
  "heading": "Our Blog",
  "subheading": "Stay updated with the latest insights, trends, and news from the {theme} industry",
  "read_more": "Read More",
  "no_posts": "No blog posts available yet"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "policy_content":
            prompt = f"""Generate privacy policy, terms of service, and cookie policy headings for a {theme} business.

Return as JSON object with these EXACT fields:
- "privacy_policy": Privacy Policy page title (2-3 words)
- "terms_of_service": Terms of Service page title (3-4 words)
- "cookie_policy": Cookie Policy page title (2-3 words)
- "last_updated": "Last Updated" label (2-3 words)

{language_instruction}

Example:
{{
  "privacy_policy": "Privacy Policy",
  "terms_of_service": "Terms of Service",
  "cookie_policy": "Cookie Policy",
  "last_updated": "Last Updated"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "footer_content":
            prompt = f"""Generate footer content for a {theme} business.

Return as JSON object with these EXACT fields:
- "tagline": Short tagline for footer (6-10 words, describing company mission)
- "quick_links": "Quick Links" section title (1-2 words)
- "legal": "Legal" section title (1 word)
- "legal_info": "Legal Information" title (2 words)
- "all_rights": "All rights reserved" text (3-4 words)
- "privacy_policy": "Privacy Policy" translation (2-3 words)
- "terms_of_service": "Terms of Service" translation (3-4 words)
- "cookie_policy": "Cookie Policy" translation (2-3 words)

Be specific to {theme} industry.{language_instruction}

Example:
{{
  "tagline": "Your trusted partner in {theme}",
  "quick_links": "Quick Links",
  "legal": "Legal",
  "legal_info": "Legal Information",
  "all_rights": "All rights reserved",
  "privacy_policy": "Privacy Policy",
  "terms_of_service": "Terms of Service",
  "cookie_policy": "Cookie Policy"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "blog_article_full":
            # num_items используется как article_number (1-6)
            article_number = num_items

            from datetime import datetime
            current_year = datetime.now().year

            # Получаем title из blog_posts_previews если они есть
            required_title = None
            excerpt_text = None
            date_text = None
            if hasattr(self, 'blueprint') and 'blog_posts_previews' in self.blueprint:
                previews = self.blueprint['blog_posts_previews']
                if article_number <= len(previews):
                    preview = previews[article_number - 1]
                    required_title = preview.get('title')
                    excerpt_text = preview.get('excerpt')
                    date_text = preview.get('date')

            # Создаем промпт с обязательным title если он известен
            title_instruction = ""
            if required_title:
                title_instruction = f'\n\nCRITICAL REQUIREMENT: You MUST use EXACTLY this title: "{required_title}". Do NOT change or modify the title in any way.'
                if date_text:
                    title_instruction += f'\nCRITICAL REQUIREMENT: You MUST use EXACTLY this date: "{date_text}".'
                if excerpt_text:
                    title_instruction += f'\nThe article should expand on this excerpt: "{excerpt_text}"'

            prompt = f"""Generate a complete blog article for a {theme} business.

Article should be article #{article_number} of 6 total articles about {theme}.{title_instruction}

Return as JSON object with these EXACT fields:
- "title": Article title (5-10 words, specific to {theme}){' - MUST BE: "' + required_title + '"' if required_title else ''}
- "date": Publication date in format "Month DD, YYYY" (recent date from {current_year}){' - MUST BE: "' + date_text + '"' if date_text else ''}
- "author": Author name (e.g., "{theme} Team", "Expert Team")
- "intro_paragraph": Opening paragraph (2-3 sentences introducing the topic)
- "sections": Array of 3-4 content sections, each with:
  * "heading": Section heading (3-6 words)
  * "content": Section content (2-3 paragraphs, 4-6 sentences total)

Make each article unique and specific to {theme} industry. Topics should be educational, informative, or provide industry insights.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "title": "{required_title if required_title else 'The Future of ' + theme}",
  "date": "{date_text if date_text else f'November 15, {current_year}'}",
  "author": "{theme} Expert Team",
  "intro_paragraph": "The {theme} industry is evolving rapidly...",
  "sections": [
    {{
      "heading": "Key Innovations",
      "content": "Recent advances have transformed..."
    }},
    {{
      "heading": "What This Means",
      "content": "These changes impact..."
    }}
  ]
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "menu_content":
            prompt = f"""Generate navigation menu translations for a {theme} business website.

Return as JSON object with these EXACT fields:
- "home": Translation for "Home" page
- "company": Translation for "Company" or "About" page
- "services": Translation for "Services" page
- "blog": Translation for "Blog" page
- "contact": Translation for "Contact" page

{language_instruction}

Example:
{{
  "home": "Home",
  "company": "Company",
  "services": "Services",
  "blog": "Blog",
  "contact": "Contact"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "features_comparison":
            prompt = f"""Generate features comparison section for a {theme} business.

Return as JSON object with these EXACT fields:
- "section_heading": Main section heading (3-5 words, e.g., "What Sets Us Apart", "Why Choose Us")
- "section_description": Brief description (15-20 words explaining value proposition)
- "features": Array of exactly 4 key features, each with:
  * "heading": Feature heading (3-5 words)
  * "description": Feature description (10-15 words)
- "cta_heading": CTA box heading (4-8 words, action-oriented and engaging)
- "cta_description": CTA box description (15-20 words, explain benefits of contacting)
- "cta_button": CTA button text (2-4 words)

Be specific to {theme} industry. Focus on competitive advantages.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "section_heading": "What Sets Us Apart",
  "section_description": "We combine expertise, innovation, and dedication to deliver exceptional results that exceed expectations.",
  "features": [
    {{"heading": "Industry-Leading Expertise", "description": "Our team brings years of specialized experience to every project"}},
    {{"heading": "Customized Solutions", "description": "Tailored approaches designed specifically for your unique needs"}},
    {{"heading": "Results-Driven Approach", "description": "Focused on delivering measurable outcomes and ROI"}},
    {{"heading": "Ongoing Partnership", "description": "Long-term support and collaboration beyond project completion"}}
  ],
  "cta_heading": "Let's Build Something Great Together",
  "cta_description": "Contact us today to discuss your project and discover how we can help you achieve your goals.",
  "cta_button": "Start Your Project"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "blog_section_headers":
            prompt = f"""Generate blog section headers for a {theme} business website.

IMPORTANT: Create professional, engaging section headers that encourage readers to explore blog content. The headers should be appropriate for the {theme} industry.

Return as JSON object with these EXACT fields (all fields are REQUIRED and MUST be present):
- "section_heading": Blog section heading (3-5 words, e.g., "Latest from Our Blog", "Recent Articles", "Industry Insights")
  * Should be engaging and relevant to {theme}
  * Should invite users to explore the blog content
  * Examples: "Latest from Our Blog", "Industry Insights", "Recent Updates"
- "view_all_text": "View all" button text (2-3 words)
  * Should be a clear call-to-action
  * Should be concise and action-oriented
  * Examples: "View All", "Read More", "See All Posts"
- "read_more": "Read more" link text for individual blog posts (2-3 words)
  * Should encourage clicking to read the full article
  * Should be action-oriented
  * Examples: "Read More", "Learn More", "Continue Reading"

{language_instruction}

CRITICAL: You MUST provide ALL THREE fields. Do NOT skip any fields. Return a complete JSON object.

Example for {theme} business:
{{
  "section_heading": "Latest from Our Blog",
  "view_all_text": "View All",
  "read_more": "Read More"
}}

IMPORTANT: Return ONLY valid JSON object with ALL THREE fields. No additional text, no markdown formatting, no explanations. The response must be a valid JSON object, not an array or string."""

        elif content_type == "cookie_notice_content":
            prompt = f"""Generate cookie notice translations for a {theme} business website.

Return as JSON object with these EXACT fields:
- "message": Cookie notice message (15-25 words explaining cookie usage)
- "learn_more": "Learn more" or "Cookie Policy" link text (2-3 words)
- "accept": "Accept" button text (1-2 words)
- "decline": "Decline" button text (1-2 words)
- "accept_all": "Accept All" button text (2-3 words)
- "ok": "OK" button text (1 word)
- "consent_title": "Cookie Consent" heading (2-3 words)
- "best_experience": "Best experience" message (10-15 words)

{language_instruction}

Example:
{{
  "message": "We use cookies to enhance your browsing experience. By continuing, you agree to our Cookie Policy.",
  "learn_more": "Learn more",
  "accept": "Accept",
  "decline": "Decline",
  "accept_all": "Accept All",
  "ok": "OK",
  "consent_title": "Cookie Consent",
  "best_experience": "This website uses cookies to ensure you get the best experience."
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "section_headings":
            prompt = f"""Generate common section headings for a {theme} business website.

Return as JSON object with these EXACT fields:
- "services": "Our Services" section heading (2-4 words)
- "featured_solutions": "Featured Solutions" section heading (2-4 words)
- "our_process": "Our Process" section heading (2-4 words)
- "faq": "Frequently Asked Questions" section heading (3-6 words)
- "our_approach": "Our Approach" section heading (2-4 words)
- "our_values": "Our Values" or "Our Fundamental Values" section heading (2-5 words)

{language_instruction}

Example:
{{
  "services": "Our Services",
  "featured_solutions": "Featured Solutions",
  "our_process": "Our Process",
  "faq": "Frequently Asked Questions",
  "our_approach": "Our Approach",
  "our_values": "Our Fundamental Values"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "our_process_content":
            prompt = f"""Generate "Our Process" section content for a {theme} business website.

Return as JSON object with this EXACT field:
- "subheading": Subheading for Our Process section (8-15 words, e.g., "A proven methodology to transform your ideas into reality")

{language_instruction}

Example:
{{
  "subheading": "A proven methodology to transform your ideas into reality"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "thankyou_content":
            prompt = f"""Generate thank you page translations for a {theme} business website.

Return as JSON object with these EXACT fields:
- "thank_you": "Thank You!" heading (2-3 words)
- "success": "Success!" heading (1-2 words)
- "message_sent": "Message Sent Successfully!" heading (3-5 words)
- "received_message": Success message (10-15 words about message being received)
- "get_back_soon": Message about response time (8-12 words)
- "response_time": "We'll respond within 24 hours" message (5-8 words)
- "explore_more_heading": "While You Wait, Explore More" section heading (4-6 words)
- "return_home": "Return to Homepage" button text (2-4 words)
- "back_home": "Back to Home" button text (2-4 words)
- "view_services": "View Services" button text (2-3 words)
- "about_us": "About Us" link text (2-3 words)
- "blog": "Blog" link text (1-2 words)
- "what_next": "What Happens Next?" heading (2-4 words)
- "review_message": "We Review Your Message" step heading (3-5 words)
- "review_description": Description for review step (10-15 words)
- "personalized_response": "Personalized Response" step heading (2-3 words)
- "response_description": Description for response step (10-15 words)
- "get_back": "Get Back to You" step heading (3-5 words)
- "get_back_description": Description for getting back (8-12 words)
- "thank_contacting": "Thank you for contacting" text (4-6 words)
- "email_heading": "Email" section heading (1-2 words)
- "email_subheading": "Check your inbox" email description (2-4 words)
- "team_heading": "Our Team" section heading (2-3 words)
- "team_subheading": "Ready to help" team description (2-4 words)

{language_instruction}

Example:
{{
  "thank_you": "Thank You!",
  "success": "Success!",
  "message_sent": "Message Sent Successfully!",
  "received_message": "Your message has been sent successfully. We'll get back to you soon.",
  "get_back_soon": "We'll get back to you soon.",
  "response_time": "Expect a response within 24 hours via email.",
  "explore_more_heading": "While You Wait, Explore More",
  "return_home": "Return to Homepage",
  "back_home": "Back to Home",
  "view_services": "View Services",
  "about_us": "About Us",
  "blog": "Blog",
  "what_next": "What Happens Next?",
  "review_message": "We Review Your Message",
  "review_description": "Our team will carefully review your inquiry within the next few hours.",
  "personalized_response": "Personalized Response",
  "response_description": "We'll prepare a detailed response tailored to your specific needs.",
  "get_back": "Get Back to You",
  "get_back_description": "Expect a response from us within 24 hours via email.",
  "thank_contacting": "Thank you for contacting",
  "email_heading": "Email",
  "email_subheading": "Check your inbox",
  "team_heading": "Our Team",
  "team_subheading": "Ready to help"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "what_we_offer_content":
            prompt = f"""Generate "What We Offer" section translations for a {theme} business website.

Return as JSON object with these EXACT fields:
- "heading": "What We Offer" section heading (2-4 words)
- "subheading_1": First variation subheading (6-10 words, e.g., "Comprehensive solutions tailored to your needs")
- "subheading_2": Second variation subheading (10-15 words, e.g., "Discover our range of professional services...")
- "subheading_3": Third variation subheading (6-10 words, e.g., "Six core services that drive exceptional results")
- "variant_heading": Variant section heading (5-8 words, e.g., "We serve our clients around the globe")
- "learn_more": "Learn More" button text (2-3 words)
- "explore": "Explore" button text (1-2 words)
- "read_more": "Read More" button text (2-3 words)

{language_instruction}

Example:
{{
  "heading": "What We Offer",
  "subheading_1": "Comprehensive solutions tailored to your needs",
  "subheading_2": "Discover our range of professional services designed to elevate your business",
  "subheading_3": "Six core services that drive exceptional results",
  "variant_heading": "We serve our clients around the globe",
  "learn_more": "Learn More",
  "explore": "Explore",
  "read_more": "Read More"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "blog_navigation_content":
            prompt = f"""Generate blog navigation and CTA translations for a {theme} business website.

Return as JSON object with these EXACT fields:
- "want_learn_more": "Want to Learn More?" heading (3-5 words)
- "contact_specific_needs": Contact message (8-15 words, e.g., "Contact us to discuss your specific needs...")
- "get_in_touch": "Get in Touch" button text (2-4 words)
- "interested_services": "Interested in Our Services?" heading (3-5 words)
- "get_in_touch_today": Message about contacting today (10-15 words)
- "contact_us": "Contact Us" button text (2-3 words)
- "previous_article": "Previous Article" text (1-3 words)
- "next_article": "Next Article" text (1-3 words)
- "published_on": "Published on" text (1-3 words)

{language_instruction}

Example:
{{
  "want_learn_more": "Want to Learn More?",
  "contact_specific_needs": "Contact us to discuss your specific needs and how we can help.",
  "get_in_touch": "Get in Touch",
  "interested_services": "Interested in Our Services?",
  "get_in_touch_today": "Get in touch with us today to learn how we can help your business grow.",
  "contact_us": "Contact Us",
  "previous_article": "Previous Article",
  "next_article": "Next Article",
  "published_on": "Published on"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "button_texts":
            prompt = f"""Generate common button text translations for a {theme} business website.

IMPORTANT: Create professional, action-oriented button texts that are appropriate for the {theme} industry. Each button text should be clear, concise, and encourage user engagement.

Return as JSON object with these EXACT fields (all fields are REQUIRED and MUST be present):
- "contact_us": "Contact Us" button text (2-3 words, professional call-to-action)
- "contact_us_today": "Contact Us Today" button text (3-4 words, urgent call-to-action)
- "start_your_project": "Start Your Project" button text (3-4 words, action-oriented)
- "get_started": "Get Started" button text (2-3 words, beginner-friendly)
- "discuss_your_project": "Discuss Your Project" button text (3-4 words, consultative approach)
- "learn_more": "Learn More" button text (2-3 words, informational)
- "view_services": "View Services" button text (2-3 words, navigational)
- "view_all": "View All" button text (2-3 words, browsing action)
- "read_more": "Read More" button text (2-3 words, content action)
- "send_message": "Send Message" button text (2-3 words, form submission)
- "submit": "Submit" button text (1-2 words, generic submission)

{language_instruction}

CRITICAL: You MUST provide ALL 11 button texts. Do NOT skip any fields. Return a complete JSON object.

Example for {theme} business:
{{
  "contact_us": "Contact Us",
  "contact_us_today": "Contact Us Today",
  "start_your_project": "Start Your Project",
  "get_started": "Get Started",
  "discuss_your_project": "Discuss Your Project",
  "learn_more": "Learn More",
  "view_services": "View Services",
  "view_all": "View All",
  "read_more": "Read More",
  "send_message": "Send Message",
  "submit": "Submit"
}}

IMPORTANT: Return ONLY valid JSON object with ALL 11 fields. No additional text, no markdown formatting, no explanations."""

        elif content_type == "services_page_content":
            prompt = f"""Generate translation content for a Services page for a {theme} business website.

IMPORTANT: Create professional, engaging content that effectively presents the services offered by a {theme} business. The content should be clear, compelling, and encourage visitors to take action.

Return as JSON object with these EXACT fields (all fields are REQUIRED and MUST be present):
- "section_heading": Services section heading (2-3 words, e.g., "Our Services")
  * Should be clear and professional
  * Should be appropriate for the {theme} industry
  * Examples: "Our Services", "What We Offer", "Services"

- "section_description": Brief description of services (15-25 words)
  * Should introduce the services in a compelling way
  * Should highlight value proposition
  * Should be specific to {theme} industry
  * Example: "We offer comprehensive solutions tailored to meet your unique needs"

- "get_started_button": Button text for service cards (2-3 words, e.g., "Get Started")
  * Should be action-oriented
  * Should encourage engagement
  * Examples: "Get Started", "Learn More", "Explore"

- "contact_cta": Call-to-action heading at bottom (4-8 words)
  * Should be engaging and action-oriented
  * Should create urgency or interest
  * Examples: "Ready to Get Started?", "Let's Work Together"

- "contact_cta_description": CTA description (15-25 words)
  * Should explain benefits of contacting
  * Should be persuasive and professional
  * Should relate to {theme} industry

{language_instruction}

CRITICAL: You MUST provide ALL 5 fields. Do NOT skip any fields. Return a complete JSON object.

Example for {theme} business:
{{
  "section_heading": "Our Services",
  "section_description": "We offer comprehensive solutions tailored to meet your unique needs. Discover how our expertise can help your business grow.",
  "get_started_button": "Get Started",
  "contact_cta": "Ready to Get Started?",
  "contact_cta_description": "Contact us today to discuss how our services can help you achieve your goals and drive success."
}}

IMPORTANT: Return ONLY valid JSON object with ALL 5 fields. No additional text, no markdown formatting, no explanations."""

        elif content_type == "company_page_content":
            prompt = f"""Generate translation content for a Company/About page for a {theme} business website.

IMPORTANT: Create professional, engaging content that effectively presents the company story and values. The content should be clear, compelling, and build trust with visitors.

Return as JSON object with these EXACT fields (all fields are REQUIRED and MUST be present):
- "section_heading": Company section heading (2-4 words, e.g., "About Us", "Our Company", "Our Story")
  * Should be clear and welcoming
  * Should be appropriate for the {theme} industry
  * Examples: "About Us", "Our Company", "Our Story", "Who We Are"

- "section_description": Brief description introducing the company (15-25 words)
  * Should introduce the company's mission in a compelling way
  * Should highlight unique value proposition
  * Should be specific to {theme} industry
  * Example: "Your trusted partner in digital transformation, helping businesses thrive through innovative AI-powered solutions."

- "values_heading": Section heading for company values (2-4 words, e.g., "Our Values", "Core Values")
  * Should be clear and professional
  * Examples: "Our Values", "Core Values", "What We Stand For", "Our Principles"

- "team_heading": Section heading for team members (2-4 words, e.g., "Our Team", "Meet the Team")
  * Should be welcoming and professional
  * Examples: "Our Team", "Meet the Team", "The Team", "Our People"

- "contact_cta": Call-to-action heading at bottom (4-8 words)
  * Should be engaging and action-oriented
  * Examples: "Ready to Work Together?", "Let's Start Your Journey"

- "contact_cta_description": CTA description (15-25 words)
  * Should explain benefits of contacting
  * Should be persuasive and professional
  * Should relate to {theme} industry

{language_instruction}

CRITICAL: You MUST provide ALL 6 fields. Do NOT skip any fields. Return a complete JSON object.

Example for {theme} business:
{{
  "section_heading": "About Us",
  "section_description": "Your trusted partner in business transformation, delivering innovative solutions that help organizations achieve their goals.",
  "values_heading": "Our Core Values",
  "team_heading": "Meet Our Team",
  "contact_cta": "Ready to Work Together?",
  "contact_cta_description": "Get in touch today to discover how our expertise can help transform your business and achieve lasting success."
}}

IMPORTANT: Return ONLY valid JSON object with ALL 6 fields. No additional text, no markdown formatting, no explanations."""

        elif content_type == "our_approach_blocks":
            prompt = f"""Generate "Our Approach" section blocks for a {theme} business website.

Return as JSON array with these 3 exact blocks in this order:
1. Client-Centered approach block
2. Innovation & Excellence block
3. Transparent Communication block

Each block must have:
- "title": Block title (2-4 words)
- "description": Block description (10-20 words about the approach/value)

{language_instruction}

Example:
[
  {{
    "title": "Client-Centered Solutions",
    "description": "We prioritize understanding your unique challenges and goals to deliver customized solutions that drive real results."
  }},
  {{
    "title": "Innovation & Excellence",
    "description": "We combine cutting-edge techniques with industry best practices to ensure superior outcomes."
  }},
  {{
    "title": "Transparent Communication",
    "description": "Regular updates and open dialogue ensure you're always informed about your project's progress."
  }}
]

Return ONLY valid JSON array with exactly 3 blocks, no additional text or markdown formatting."""

        elif content_type == "faq_blocks":
            prompt = f"""Generate FAQ (Frequently Asked Questions) section for a {theme} business website.

Return as JSON object with:
- "section_description": Brief description under heading (8-15 words, e.g., "Find answers to common questions about our services")
- "questions": Array of exactly 4 FAQ items, each with:
  * "question": Question text (5-10 words)
  * "answer": Answer text (15-30 words)

Questions should cover: services offered, project timeline, post-project support, and what makes the company different.

{language_instruction}

Example:
{{
  "section_description": "Find answers to common questions about our services",
  "questions": [
    {{
      "question": "What services do you offer?",
      "answer": "We provide comprehensive {theme} services tailored to your specific needs, including consultation, implementation, and ongoing support."
    }},
    {{
      "question": "How long does a typical project take?",
      "answer": "Project timelines vary based on scope and complexity. We provide detailed timelines during the initial consultation phase."
    }},
    {{
      "question": "Do you offer support after project completion?",
      "answer": "Yes, we provide comprehensive post-project support and maintenance to ensure long-term success."
    }},
    {{
      "question": "What makes your company different?",
      "answer": "Our commitment to quality, personalized approach, and proven track record set us apart in the industry."
    }}
  ]
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "team_section_content":
            prompt = f"""Generate team section heading for a {theme} business website.

Return as JSON object with:
- "heading": Team section main heading (2-4 words, e.g., "Our Amazing Team", "Meet Our Team", "Our Experts")

{language_instruction}

Example:
{{
  "heading": "Our Amazing Team"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "team_members":
            # Специальная инструкция для имен в зависимости от страны
            names_instruction = ""
            if country == "USA":
                names_instruction = "\n\nCRITICAL NAMES REQUIREMENT: Generate ENGLISH names ONLY (e.g., Sarah Johnson, Michael Chen, Emily Rodriguez, David Williams, Jennifer Martinez, James Anderson). Use diverse English first and last names typical for USA. Do NOT use non-English names. All names must be in English regardless of the content language."

            prompt = f"""Generate team member profiles for a {theme} business website.

Return as JSON array of exactly {num_items} team members. Each member should have:
- "name": Full name (first and last name ONLY)
  * CRITICAL: Do NOT include titles, honorifics, or professional designations in the name
  * FORBIDDEN: "Доктор", "Профессор", "Инженер", "Doctor", "Professor", "Engineer", "Dr.", "Prof.", etc.
  * CORRECT: "Anna Petrova", "Michael Smith", "Elena Morozova"
  * WRONG: "Доктор Анна Петрова", "Dr. Michael Smith", "Профессор Елена Морозова"
- "position": Job title or role (2-4 words, e.g., "Worldwide Partner", "Senior Consultant", "Managing Director")
  * Titles and professional designations go HERE in the position field, NOT in the name
- "gender": Either "male" or "female" (for image generation purposes)

Create realistic, professional names and positions appropriate for a {theme} business.
Ensure diversity in positions and genders.
IMPORTANT: Generate UNIQUE names each time - do not repeat the same names.

IMPORTANT: The "name" field must contain ONLY first name and last name, with NO titles or honorifics.
Professional titles belong in the "position" field.{names_instruction}

{language_instruction}

Example for 3 members:
[
  {{"name": "Nat Reynolds", "position": "Worldwide Partner", "gender": "male"}},
  {{"name": "Jennie Roberts", "position": "Partner", "gender": "female"}},
  {{"name": "Mila Parker", "position": "Partner", "gender": "female"}}
]

Return ONLY valid JSON array, no additional text or markdown formatting."""

        elif content_type == "hero_mission_variant":
            prompt = f"""Generate hero section content for a {theme} business website.

Return as JSON object with:
- "heading": Main heading (4-7 words, friendly and welcoming message)
- "description": Descriptive paragraph (20-35 words)
- "button_text": Call-to-action button text (1-3 words, e.g., "Read More", "Learn More", "Get Started")

{language_instruction}

Example:
{{
  "heading": "We are always beginner friendly",
  "description": "Professional services tailored to your needs with personalized approach and commitment to excellence.",
  "button_text": "Read More"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "mission_content":
            prompt = f"""Generate mission block content for a {theme} business website.

Return as JSON object with:
- "label": Small label text (2-3 words, e.g., "Our Mission", "Our Vision", "Our Goal")
- "heading": Main heading word (1-2 words, action verb like "Explore", "Excel", "Achieve", "Deliver")
- "heading_second": Optional second line (0-2 words, can be empty string "")
- "subheading": Subheading text (2-3 words, e.g., "Every Journey", "Every Day", "Every Time")

Create an inspiring mission statement appropriate for a {theme} business.

{language_instruction}

Example for travel business:
{{
  "label": "Our Mission",
  "heading": "Explore",
  "heading_second": "",
  "subheading": "Every Journey"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "cta_bottom_block":
            prompt = f"""Generate call-to-action block content for a {theme} business website.

Return as JSON object with:
- "heading": CTA heading (2-5 words, engaging and action-oriented)
- "description": Description text (20-35 words, explain the offer or invitation)
- "button_text": Button text (1-3 words, e.g., "Join Now", "Sign Up", "Get Started", "Contact Us")

Create compelling CTA content appropriate for a {theme} business.

{language_instruction}

Example:
{{
  "heading": "Join Our Community",
  "description": "Connect with like-minded professionals and take advantage of exclusive benefits, resources, and networking opportunities.",
  "button_text": "Join Now"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "company_values":
            prompt = f"""Generate {num_items} company core values for a {theme} business website.

Return as JSON array of exactly {num_items} values. Each value should have:
- "title": Value name (1-3 words, e.g., "Passion", "Integrity", "Excellence", "Innovation", "Collaboration", "Quality", "Client Success", "Teamwork", "Customer Focus", "Continuous Improvement", "Results Driven")
- "description": Value description (8-15 words explaining what this value means for the company)

Create inspiring, professional values appropriate for a {theme} business.
Make each value unique and meaningful. Focus on qualities that build trust and demonstrate commitment.

{language_instruction}

Example:
[
  {{"title": "Innovation", "description": "Pushing boundaries with creative solutions and cutting-edge approaches."}},
  {{"title": "Integrity", "description": "Trust and transparency in everything we do."}},
  {{"title": "Excellence", "description": "Committed to delivering the highest quality in every project."}}
]

Return ONLY valid JSON array, no additional text or markdown formatting."""

        elif content_type == "button_labels":
            prompt = f"""Generate button text labels for a {theme} business Company/About page.

Return as JSON object with:
- "contact_us": Contact button text (1-3 words, e.g., "Contact Us", "Get in Touch", "Reach Out")
- "get_started": Get started button text (1-3 words, e.g., "Get Started", "Start Now", "Begin")
- "learn_more": Learn more button text (1-3 words, e.g., "Learn More", "Discover More", "Find Out")

Create natural, action-oriented button texts appropriate for a {theme} business.

{language_instruction}

Example:
{{
  "contact_us": "Contact Us",
  "get_started": "Get Started",
  "learn_more": "Learn More"
}}

Return ONLY valid JSON object, no additional text or markdown formatting."""

        elif content_type == "privacy_policy_full":
            prompt = f"""Generate complete Privacy Policy page content for a {theme} business website.

Return as JSON object with section headings and content. All text must be in the target language.

IMPORTANT: When referring to the company/business name, use the appropriate placeholder based on the target language:
- French: [Nom de l'Entreprise de Voyages]
- English: [Company Name]
- Italian: [Nome dell'azienda]
- Spanish: [Nombre de la empresa]
- German: [Firmenname]
- Polish: [Nazwa firmy]
- Czech: [Název společnosti]
- Dutch: [Bedrijfsnaam]
- Other languages: [Site Name]

Do NOT invent or use any specific company names. Always use the placeholder.

Required fields:
- "introduction_heading": Section 1 heading (e.g., "Introduction")
- "introduction_text": Introduction paragraph (20-30 words) - MUST use the appropriate company name placeholder
- "info_we_collect_heading": Section 2 heading (e.g., "Information We Collect")
- "info_we_collect_intro": Introduction text before subsections (e.g., "We may collect information about you in a variety of ways. The information we may collect includes:")
- "personal_data_heading": Subsection heading (e.g., "Personal Data")
- "personal_data_items": Array of 4 data items collected
- "usage_data_heading": Subsection heading (e.g., "Usage Data")
- "usage_data_items": Array of 4 usage data items
- "how_we_use_heading": Section 3 heading (e.g., "How We Use Your Information")
- "how_we_use_intro": Introduction text before list (e.g., "We use the information we collect to:")
- "how_we_use_items": Array of 6 usage purposes
- "data_security_heading": Section 4 heading
- "data_security_text": Paragraph (20-30 words)
- "your_rights_heading": Section 5 heading
- "your_rights_text": Paragraph (15-25 words)
- "contact_heading": Section 6 heading (e.g., "Contact Us")
- "contact_text": Paragraph (10-15 words)
- "contact_email_label": Label before email (e.g., "Email:")

{language_instruction}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "terms_of_service_full":
            prompt = f"""Generate complete Terms of Service page content for a {theme} business website.

Return as JSON object with section headings and content. All text must be in the target language.

IMPORTANT: When referring to the company/business name, use the appropriate placeholder based on the target language:
- French: [Nom de l'Entreprise de Voyages]
- English: [Company Name]
- Italian: [Nome dell'azienda]
- Spanish: [Nombre de la empresa]
- German: [Firmenname]
- Polish: [Nazwa firmy]
- Czech: [Název společnosti]
- Dutch: [Bedrijfsnaam]
- Other languages: [Site Name]

Do NOT invent or use any specific company names. Always use the placeholder.

Required fields:
- "agreement_heading": Section 1 heading (e.g., "Agreement to Terms")
- "agreement_text": Paragraph (20-30 words) - MUST use the appropriate company name placeholder
- "use_license_heading": Section 2 heading (e.g., "Use License")
- "use_license_intro": Intro paragraph (20-30 words) - MUST use the appropriate company name placeholder
- "use_license_items": Array of 5 prohibited actions
- "user_responsibilities_heading": Section 3 heading
- "user_responsibilities_intro": Intro text (e.g., "As a user of our website, you agree to:")
- "user_responsibilities_items": Array of 5 user responsibilities
- "disclaimer_heading": Section 4 heading (e.g., "Disclaimer")
- "disclaimer_text": Paragraph (30-40 words)
- "limitations_heading": Section 5 heading (e.g., "Limitations of Liability")
- "limitations_text": Paragraph (15-25 words)
- "modifications_heading": Section 6 heading (e.g., "Modifications")
- "modifications_text": Paragraph (15-25 words)
- "contact_heading": Section 7 heading (e.g., "Contact Information")
- "contact_intro": Intro text (10-15 words)
- "contact_email_label": Label before email (e.g., "Email:")

{language_instruction}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "cookie_policy_full":
            prompt = f"""Generate complete Cookie Policy page content for a {theme} business website.

Return as JSON object with section headings and content. All text must be in the target language.

IMPORTANT: When referring to the company/business name, use the appropriate placeholder based on the target language:
- French: [Nom de l'Entreprise de Voyages]
- English: [Company Name]
- Italian: [Nome dell'azienda]
- Spanish: [Nombre de la empresa]
- German: [Firmenname]
- Polish: [Nazwa firmy]
- Czech: [Název społnosti]
- Dutch: [Bedrijfsnaam]
- Other languages: [Site Name]

Do NOT invent or use any specific company names. Always use the placeholder.

Required fields:
- "what_are_cookies_heading": Section 1 heading (e.g., "What Are Cookies")
- "what_are_cookies_text": Paragraph (20-30 words)
- "types_heading": Section 2 heading (e.g., "Types of Cookies We Use")
- "essential_heading": Subsection heading (e.g., "Essential Cookies")
- "essential_text": Paragraph (15-25 words)
- "analytics_heading": Subsection heading (e.g., "Analytics Cookies")
- "analytics_text": Paragraph (15-25 words)
- "functionality_heading": Subsection heading (e.g., "Functionality Cookies")
- "functionality_text": Paragraph (15-25 words)
- "advertising_heading": Subsection heading (e.g., "Advertising Cookies")
- "advertising_text": Paragraph (15-25 words)
- "third_party_heading": Section 3 heading (e.g., "Third-Party Cookies")
- "third_party_text": Paragraph (15-25 words)
- "managing_heading": Section 4 heading (e.g., "Managing Cookies")
- "managing_intro": Intro paragraph (25-35 words)
- "how_to_control_heading": Subsection heading (e.g., "How to Control Cookies")
- "control_items": Array of 3 control methods
- "updates_heading": Section 5 heading (e.g., "Updates to This Policy")
- "updates_text": Paragraph (15-20 words)
- "contact_heading": Section 6 heading (e.g., "Contact Us")
- "contact_intro": Intro text (10-15 words)
- "contact_email_label": Label before email (e.g., "Email:")

{language_instruction}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "two_images_no_button":
            prompt = f"""Generate content for a two-image section without button for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Compelling section heading (4-8 words, specific to {theme} industry)
- "description": Detailed description (20-35 words explaining the value proposition)

Make the content highly specific to the {theme} industry. Focus on real benefits and professional solutions.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Real-world Solutions Designed Just for You",
  "description": "Professional solutions tailored to meet your specific needs and exceed expectations in the {theme} industry."
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "two_images_section":
            prompt = f"""Generate content for a two-image section with button for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Compelling section heading (4-8 words, specific to {theme} industry)
- "description": Detailed description (20-35 words explaining the value proposition)
- "button_text": Call-to-action button text (2-3 words)

Make the content highly specific to the {theme} industry. Focus on real benefits and professional solutions.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Transform Your Business Operations",
  "description": "Comprehensive solutions designed to streamline workflows and maximize efficiency in the {theme} sector.",
  "button_text": "Learn More"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "four_images_section":
            prompt = f"""Generate content for a four-image grid section for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Compelling section heading (4-8 words, specific to {theme} industry)
- "description": Detailed description (20-35 words explaining comprehensive services)
- "button_text": Call-to-action button text (2-3 words)

Make the content highly specific to the {theme} industry. Emphasize comprehensive support and professional services.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Complete Professional Support Services",
  "description": "End-to-end solutions covering every aspect of your business needs in the {theme} industry with expert guidance.",
  "button_text": "Read More"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "contact_form_benefits":
            prompt = f"""Generate content for a contact form section with benefits for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Main section heading (4-8 words, action-oriented for {theme})
- "description": Compelling description about services (30-50 words, specific to {theme} industry)
- "name_label": Placeholder for name field (2-4 words)
- "email_label": Placeholder for email field (3-5 words)
- "message_label": Placeholder for message field (1-2 words)
- "submit_button": Submit button text (2-4 words)
- "form_heading": Form heading (3-5 words)

Make the content highly specific to the {theme} industry. Avoid generic Lorem Ipsum text.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Transform Business Growth with Expert Services",
  "description": "We specialize in delivering innovative solutions tailored to your industry needs. Our expert team provides comprehensive support to help you achieve measurable results and sustainable growth.",
  "name_label": "Enter your Name",
  "email_label": "Enter a valid email address",
  "message_label": "Message",
  "submit_button": "Connect With Us",
  "form_heading": "Request a Free Consultation"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "benefits_list":
            prompt = f"""Generate {num_items} key benefits for a {theme} business.

Return as JSON array of objects, where each object has:
- "title": Benefit title (3-5 words, specific to {theme} industry)

Make the benefits highly specific to the {theme} industry. Focus on strategic advantages and professional capabilities.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
[
  {{"title": "Strategic Planning Excellence"}},
  {{"title": "Advanced Technology Integration"}},
  {{"title": "Data-Driven Insights"}}
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "contact_form_quick":
            prompt = f"""Generate content for a quick contact form for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Form section heading (3-5 words)
- "description": Brief description (10-15 words, can be empty string if not needed)
- "first_name_label": Placeholder for first name field (2-3 words)
- "last_name_label": Placeholder for last name field (2-3 words)
- "email_label": Placeholder for email field (3-5 words)
- "message_label": Placeholder for message field (1-2 words)
- "submit_button": Submit button text (2-3 words)

Make the content professional and specific to {theme} industry.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Get in Touch",
  "description": "Contact us today to discuss your project needs",
  "first_name_label": "First Name",
  "last_name_label": "Last Name",
  "email_label": "Email Address",
  "message_label": "Message",
  "submit_button": "Send Message"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "image_benefits_section":
            prompt = f"""Generate content for an image with benefits section for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": Main section heading (4-7 words, specific to {theme})
- "description": Description paragraph (20-35 words)
- "button_text": Call-to-action button text (2-3 words)

Make the content highly specific to the {theme} industry.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Innovative Solutions for Modern Challenges",
  "description": "Our comprehensive approach combines cutting-edge technology with industry expertise to deliver exceptional results tailored to your business needs.",
  "button_text": "Discover More"
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "benefits_icons":
            prompt = f"""Generate {num_items} benefits with icons for a {theme} business.

Return as JSON array of objects, where each object has:
- "title": Benefit title (3-6 words, specific to {theme} industry)
- "description": Brief benefit description (10-15 words)
- "icon": Icon name (e.g., "check-circle", "star", "shield", "rocket", "award")

Make the benefits highly specific to the {theme} industry.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
[
  {{"title": "Expert Team", "description": "Skilled professionals with extensive industry experience and proven results", "icon": "award"}},
  {{"title": "Quality Assurance", "description": "Rigorous testing and quality control for exceptional outcomes", "icon": "shield"}},
  {{"title": "Innovation Focus", "description": "Cutting-edge solutions leveraging latest industry advancements", "icon": "rocket"}}
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "what_we_offer_variant":
            prompt = f"""Generate {num_items} service offerings for a {theme} business.

Return as JSON array of objects, where each object has:
- "title": Service title (2-5 words)
- "description": Service description (12-18 words)
- "icon": Icon identifier (e.g., "service1", "service2", etc.)

Make the services highly specific to the {theme} industry.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
[
  {{"title": "Strategic Consulting", "description": "Expert guidance to optimize your business strategy and achieve sustainable growth", "icon": "service1"}},
  {{"title": "Technology Solutions", "description": "Advanced technical implementations tailored to your specific operational requirements", "icon": "service2"}}
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "faq_content":
            prompt = f"""Generate FAQ content for a {theme} business.

Return as JSON object with these EXACT fields:
- "heading": FAQ section heading (2-4 words, e.g., "Frequently Asked Questions", "Common Questions")
- "description": Brief description (10-20 words about the FAQ section)
- "items": Array of exactly {num_items} FAQ items, each with:
  * "question": Question text (5-10 words, specific to {theme} industry)
  * "answer": Answer text (15-30 words, informative and specific)

Make the content highly specific to the {theme} industry. Questions should address real concerns customers have.{global_price_ban}{theme_specific_instructions}{language_instruction}

Example:
{{
  "heading": "Frequently Asked Questions",
  "description": "Find answers to common questions about our services and approach",
  "items": [
    {{"question": "What services do you offer?", "answer": "We provide comprehensive solutions tailored to your specific needs in the {theme} industry, including consulting, implementation, and ongoing support."}},
    {{"question": "How long does a typical project take?", "answer": "Project timelines vary based on scope and complexity, but we work efficiently to deliver results within agreed timeframes."}}
  ]
}}

Return ONLY valid JSON, no additional text or markdown formatting."""

        else:
            return None

        # Вызываем API с разными max_tokens в зависимости от типа контента
        # Некоторые типы контента требуют больше токенов
        if content_type in ["privacy_policy_full", "terms_of_service_full", "cookie_policy_full"]:
            max_tokens = 10000  # Очень большой лимит для полных policy страниц
        elif content_type == "blog_article_full":
            max_tokens = 8000  # Большой лимит для полной статьи с несколькими секциями
        elif content_type == "work_showcase":
            max_tokens = 6000  # Больше токенов для 4 детальных кейсов
        elif content_type in ["services", "featured_solutions", "process_steps", "blog_posts", "benefits_content", "benefits_list", "benefits_icons", "what_we_offer_variant"]:
            max_tokens = 5000  # Увеличенный лимит для списков
        elif content_type == "about_content":
            max_tokens = 6000  # Увеличенный лимит для about_content чтобы избежать обрезания
        elif content_type == "company_page_content":
            max_tokens = 8000  # Большой лимит для company page с множеством полей
        elif content_type in ["approach_content", "gallery_content", "faq_blocks", "services_page_content", "thankyou_content", "what_we_offer_content", "contact_form_benefits", "contact_form_quick", "faq_content"]:
            max_tokens = 4000  # Увеличенный лимит для контента с несколькими параграфами и полями
        elif content_type == "testimonials_content":
            max_tokens = 4000  # Достаточно для 3 отзывов
        else:
            max_tokens = 3000  # Для простых объектов (hero, achievements, cta, contact, blog, policy, footer)

        print(f"    🤖 Генерация контента для темы '{theme}' ({content_type})...")
        response = self.call_api(prompt, max_tokens=max_tokens)

        if not response or not response.strip():
            # Специальная обработка для button_texts - используем упрощенный промпт
            if content_type == "button_texts":
                print(f"    ⚠️  Первая попытка не удалась, пробуем упрощенный промпт для button_texts...")
                simplified_prompt = f"""You are a professional translator. Translate these button texts to {language} language for a {theme} website.

CRITICAL: Return ONLY a valid JSON object. ALL text must be in {language} language.

{{
  "contact_us": "Contact Us",
  "contact_us_today": "Contact Us Today",
  "start_your_project": "Start Your Project",
  "get_started": "Get Started",
  "discuss_your_project": "Discuss Your Project",
  "learn_more": "Learn More",
  "view_services": "View Services",
  "view_all": "View All",
  "read_more": "Read More",
  "send_message": "Send Message",
  "submit": "Submit"
}}

Translate ALL values to {language}. Return ONLY the JSON object, nothing else."""

                response = self.call_api(simplified_prompt, max_tokens=2000)

                if not response or not response.strip():
                    print(f"    ✗ Упрощенный промпт также не сработал для button_texts")
                    return None
                else:
                    print(f"    ✓ Упрощенный промпт сработал для button_texts")

            # Специальная обработка для blog_section_headers - используем упрощенный промпт
            elif content_type == "blog_section_headers":
                print(f"    ⚠️  Первая попытка не удалась, пробуем упрощенный промпт для blog_section_headers...")
                simplified_prompt = f"""You are a professional translator. Translate these blog section headers to {language} language for a {theme} website.

CRITICAL: Return ONLY a valid JSON object (not an array, not a string). ALL text must be in {language} language.

{{
  "section_heading": "Latest from Our Blog",
  "view_all_text": "View All"
}}

Translate ALL values to {language}. Return ONLY the JSON object, nothing else. Make sure it's an object with curly braces {{}}, not an array with square brackets []."""

                response = self.call_api(simplified_prompt, max_tokens=1000)

                if not response or not response.strip():
                    print(f"    ✗ Упрощенный промпт также не сработал для blog_section_headers")
                    return None
                else:
                    print(f"    ✓ Упрощенный промпт сработал для blog_section_headers")

            # Специальная обработка для services_page_content - используем упрощенный промпт
            elif content_type == "services_page_content":
                print(f"    ⚠️  Первая попытка не удалась, пробуем упрощенный промпт для services_page_content...")
                simplified_prompt = f"""You are a professional translator. Translate this services page content to {language} language for a {theme} website.

CRITICAL: Return ONLY a valid JSON object. ALL text must be in {language} language.

{{
  "section_heading": "Our Services",
  "section_description": "We offer comprehensive solutions tailored to meet your unique needs. Discover how our expertise can help your business grow.",
  "get_started_button": "Get Started",
  "contact_cta": "Ready to Get Started?",
  "contact_cta_description": "Contact us today to discuss how our services can help you achieve your goals and drive success."
}}

Translate ALL values to {language}. Return ONLY the JSON object, nothing else. Make sure to provide all 5 fields."""

                response = self.call_api(simplified_prompt, max_tokens=1500)

                if not response or not response.strip():
                    print(f"    ✗ Упрощенный промпт также не сработал для services_page_content")
                    return None
                else:
                    print(f"    ✓ Упрощенный промпт сработал для services_page_content")

            # Специальная обработка для about_content - используем упрощенный промпт
            elif content_type == "about_content":
                print(f"    ⚠️  Первая попытка не удалась, пробуем упрощенный промпт для about_content...")
                from datetime import datetime
                current_year = datetime.now().year

                simplified_prompt = f"""Generate About Us section content for a {theme} business in {language} language.

Return ONLY valid JSON with EXACTLY these 5 fields:

{{
  "heading": "About Us",
  "founded_year": "{current_year-5}",
  "paragraph1": "We are dedicated to providing exceptional {theme} services that help our clients achieve their goals.",
  "paragraph2": "Our team of professionals brings years of experience and expertise to every project we undertake.",
  "button_text": "Learn More"
}}

Translate ALL values to {language}. Be specific to {theme} industry. Return ONLY the JSON object, nothing else."""

                response = self.call_api(simplified_prompt, max_tokens=2000)

                if not response or not response.strip():
                    print(f"    ✗ Упрощенный промпт также не сработал для about_content")
                    return None
                else:
                    print(f"    ✓ Упрощенный промпт сработал для about_content")

            else:
                print(f"    ✗ API не вернул ответ для {content_type} (response is {'None' if response is None else 'empty'})")
                return None

        try:
            # Очищаем ответ от markdown форматирования если есть
            response = response.strip()
            if response.startswith('```'):
                # Удаляем markdown code blocks
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response
                response = response.replace('```json', '').replace('```', '').strip()

            # Проверяем, что JSON не обрезан (заканчивается на ] или })
            if not (response.endswith(']') or response.endswith('}')):
                print(f"    ⚠️  JSON выглядит обрезанным для {content_type} (не заканчивается на ] или }})")
                print(f"    Последние 100 символов: ...{response[-100:]}")

                # Улучшенная логика восстановления JSON
                if response.count('[') > response.count(']'):
                    # Это массив - находим последний полный объект
                    # Ищем последнее вхождение "},\n  {" или последнее полное закрытие }
                    last_complete = response.rfind('},')
                    if last_complete > 0:
                        # Обрезаем до последнего полного объекта и закрываем массив
                        response = response[:last_complete + 1] + '\n]'
                        print(f"    🔧 Восстановление: обрезан до последнего полного объекта и добавлена ]")
                    else:
                        # Если нет даже одного полного объекта, просто закрываем
                        response += ']'
                        print(f"    🔧 Попытка восстановления: добавлена закрывающая ]")
                elif response.count('{') > response.count('}'):
                    # Это объект - находим последнее полное поле
                    last_complete = response.rfind(',')
                    if last_complete > 0:
                        # Обрезаем до последнего полного поля и закрываем объект
                        response = response[:last_complete] + '\n}'
                        print(f"    🔧 Восстановление: обрезан до последнего полного поля и добавлена }}")
                    else:
                        response += '}'
                        print(f"    🔧 Попытка восстановления: добавлена закрывающая }}")

            # Парсим JSON с обработкой extra data
            try:
                content = json.loads(response)
            except json.JSONDecodeError as e:
                # Если ошибка "Extra data" - пытаемся найти первый валидный JSON
                if "Extra data" in str(e):
                    print(f"    🔧 Обнаружены лишние данные после JSON, попытка извлечения...")
                    # Находим позицию где заканчивается валидный JSON
                    # Для объекта: ищем первую закрывающую }
                    # Для массива: ищем первую закрывающую ]
                    if response.strip().startswith('{'):
                        # Это объект - ищем парную закрывающую скобку
                        bracket_count = 0
                        for i, char in enumerate(response):
                            if char == '{':
                                bracket_count += 1
                            elif char == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    # Нашли конец JSON объекта
                                    response = response[:i+1]
                                    print(f"    🔧 Обрезан лишний текст, осталось {len(response)} символов")
                                    break
                    elif response.strip().startswith('['):
                        # Это массив - ищем парную закрывающую скобку
                        bracket_count = 0
                        for i, char in enumerate(response):
                            if char == '[':
                                bracket_count += 1
                            elif char == ']':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    # Нашли конец JSON массива
                                    response = response[:i+1]
                                    print(f"    🔧 Обрезан лишний текст, осталось {len(response)} символов")
                                    break
                    # Повторная попытка парсинга
                    content = json.loads(response)
                else:
                    # Другая ошибка парсинга - пробрасываем дальше
                    raise

            # Проверяем что получили ожидаемую структуру
            if content_type == "work_showcase":
                if not isinstance(content, dict):
                    print(f"    ⚠️  Получен неверный тип данных для {content_type} (ожидается объект), используем fallback")
                    return None
                if "cases" not in content or not isinstance(content["cases"], list) or len(content["cases"]) < 4:
                    cases_len = len(content.get("cases", [])) if isinstance(content.get("cases"), list) else 0
                    print(f"    ⚠️  Получено меньше 4 кейсов ({cases_len}), используем fallback")
                    return None

            # Для других типов списков - проверяем что получили хотя бы что-то
            elif content_type in ["services", "featured_solutions", "process_steps", "blog_posts", "benefits_list", "benefits_icons", "what_we_offer_variant"]:
                if not isinstance(content, list) or len(content) == 0:
                    print(f"    ⚠️  Не получено элементов для {content_type}, используем fallback")
                    return None
                elif len(content) < num_items:
                    print(f"    ⚠️  Получено {len(content)} элементов вместо {num_items} для {content_type}, используем их")

            # Проверка для benefits_content - объект с массивом benefits
            elif content_type == "benefits_content":
                if not isinstance(content, dict):
                    print(f"    ⚠️  Получен неверный тип данных для {content_type} (ожидается объект), используем fallback")
                    return None
                if "benefits" not in content or not isinstance(content["benefits"], list) or len(content["benefits"]) == 0:
                    benefits_len = len(content.get("benefits", [])) if isinstance(content.get("benefits"), list) else 0
                    print(f"    ⚠️  Не получено элементов для benefits ({benefits_len}), используем fallback")
                    return None
                elif len(content["benefits"]) < num_items:
                    print(f"    ⚠️  Получено {len(content['benefits'])} элементов вместо {num_items} для benefits, используем их")

            # Проверка для testimonials_content - объект с массивом testimonials
            elif content_type == "testimonials_content":
                if not isinstance(content, dict):
                    print(f"    ⚠️  Получен неверный тип данных для {content_type} (ожидается объект), используем fallback")
                    return None
                if "testimonials" not in content or not isinstance(content["testimonials"], list) or len(content["testimonials"]) == 0:
                    testimonials_len = len(content.get("testimonials", [])) if isinstance(content.get("testimonials"), list) else 0
                    print(f"    ⚠️  Не получено элементов для testimonials ({testimonials_len}), используем fallback")
                    return None
                elif len(content["testimonials"]) < num_items:
                    print(f"    ⚠️  Получено {len(content['testimonials'])} элементов вместо {num_items} для testimonials, используем их")

            # Проверка для faq_content - объект с массивом items
            elif content_type == "faq_content":
                if not isinstance(content, dict):
                    print(f"    ⚠️  Получен неверный тип данных для {content_type} (ожидается объект), используем fallback")
                    return None
                if "items" not in content or not isinstance(content["items"], list) or len(content["items"]) == 0:
                    items_len = len(content.get("items", [])) if isinstance(content.get("items"), list) else 0
                    print(f"    ⚠️  Не получено элементов для faq items ({items_len}), используем fallback")
                    return None
                elif len(content["items"]) < num_items:
                    print(f"    ⚠️  Получено {len(content['items'])} элементов вместо {num_items} для faq items, используем их")

            # Для объектных типов контента - проверяем что это словарь
            elif content_type in ["hero_content", "achievements_content", "cta_content", "contact_page_content", "blog_page_content", "policy_content", "footer_content", "menu_content", "about_content", "gallery_content", "approach_content", "blog_article_full", "section_headings", "blog_section_headers", "button_texts", "blog_navigation_content", "cookie_notice_content", "thankyou_content", "what_we_offer_content", "features_comparison", "two_images_no_button", "two_images_section", "four_images_section", "contact_form_benefits", "contact_form_quick", "image_benefits_section"]:
                if not isinstance(content, dict):
                    print(f"    ⚠️  Получен неверный тип данных для {content_type} (получен {type(content).__name__} вместо dict)")

                    # Специальная обработка для blog_section_headers - пробуем упрощенный промпт
                    if content_type == "blog_section_headers":
                        print(f"    ⚠️  Пробуем упрощенный промпт для blog_section_headers...")
                        simplified_prompt = f"""You are a professional translator. Translate these blog section headers to {language} language for a {theme} website.

CRITICAL: Return ONLY a valid JSON object (not an array, not a string). ALL text must be in {language} language.

{{
  "section_heading": "Latest from Our Blog",
  "view_all_text": "View All"
}}

Translate ALL values to {language}. Return ONLY the JSON object, nothing else. Make sure it's an object with curly braces {{}}, not an array with square brackets []."""

                        retry_response = self.call_api(simplified_prompt, max_tokens=1000)

                        if retry_response and retry_response.strip():
                            try:
                                # Очищаем от markdown
                                retry_response = retry_response.strip()
                                if retry_response.startswith('```'):
                                    lines = retry_response.split('\n')
                                    retry_response = '\n'.join(lines[1:-1]) if len(lines) > 2 else retry_response
                                    retry_response = retry_response.replace('```json', '').replace('```', '').strip()

                                retry_content = json.loads(retry_response)
                                if isinstance(retry_content, dict):
                                    print(f"    ✓ Упрощенный промпт сработал для blog_section_headers")
                                    self.theme_content_cache[cache_key] = retry_content
                                    print(f"    ✓ Контент успешно сгенерирован для '{theme}' (OK)")
                                    return retry_content
                            except:
                                pass

                        print(f"    ✗ Упрощенный промпт также не сработал для blog_section_headers")

                    return None

            # Сохраняем в кэш
            self.theme_content_cache[cache_key] = content

            print(f"    ✓ Контент успешно сгенерирован для '{theme}' ({len(content) if isinstance(content, list) else 'OK'})")
            return content

        except json.JSONDecodeError as e:
            print(f"    ✗ Ошибка парсинга JSON для {content_type}: {e}")
            print(f"    Длина ответа: {len(response)} символов")
            print(f"    Начало ответа: {response[:150]}...")
            print(f"    Конец ответа: ...{response[-150:]}")
            return None
        except Exception as e:
            print(f"    ✗ Неожиданная ошибка для {content_type}: {e}")
            return None

    def get_localized_fallback(self, content_type, fallback_data, theme=None, num_items=None):
        """
        Пытается сгенерировать уникальный контент через API (5 попыток),
        и только потом переводит fallback контент на нужный язык

        Args:
            content_type: Тип контента
            fallback_data: Данные fallback на английском
            theme: Тема сайта (опционально, для генерации через API)
            num_items: Количество элементов (опционально, для генерации через API)

        Returns:
            Сгенерированные или переведенные данные
        """
        language = self.blueprint.get('language', 'English')

        # Если язык английский - возвращаем как есть
        if language.lower() == 'english':
            return fallback_data

        # Если предоставлены theme и num_items, пытаемся сгенерировать через API
        if theme is not None:
            # Определяем num_items на основе типа контента или используем предоставленное значение
            if num_items is None:
                # Дефолтные значения для разных типов контента
                num_items_map = {
                    'process_steps': 4,
                    'featured_solutions': 6,
                    'services': 6,
                    'team_members': 3,
                    'testimonials_content': 3,
                    'benefits_list': 4,
                    'faq_blocks': 4,
                }
                num_items = num_items_map.get(content_type, 3)

            print(f"    ⚠️  Вместо fallback пытаемся сгенерировать уникальный контент через API...")

            # Пытаемся сгенерировать контент через API (уже с 5 попытками внутри)
            generated_content = self.generate_theme_content_via_api(theme, content_type, num_items)

            if generated_content is not None:
                print(f"    ✓ Уникальный контент успешно сгенерирован вместо fallback!")
                return generated_content

            print(f"    ⚠️  Не удалось сгенерировать уникальный контент, используем перевод fallback...")

        # Если генерация не удалась или параметры не предоставлены, переводим fallback
        # Создаем промпт для перевода
        import json
        fallback_json = json.dumps(fallback_data, ensure_ascii=False, indent=2)

        prompt = f"""Translate the following JSON content to {language} language.
Keep the JSON structure EXACTLY the same, only translate the text values.
Preserve all keys in English.

CRITICAL REQUIREMENT: You MUST translate ALL text values to {language}. Do NOT leave any text in English.

IMPORTANT EXCEPTION: Do NOT translate these fields as they are country-specific, not language-specific:
- "phone" (phone numbers)
- "email" (email addresses)
- "address" (physical addresses including street names, cities, postal codes)
- "city" (city names)
- "street" (street names)
- "postal_code" or "zip" (postal/zip codes)
Keep these fields EXACTLY as they are in the original.

Original JSON:
{fallback_json}

Return ONLY the translated JSON, no additional text or markdown formatting."""

        try:
            # Используем тот же API для перевода
            translated_content = self.call_api(prompt, max_tokens=4096)
            if not translated_content:
                print(f"    ⚠️  Не удалось перевести fallback для {content_type}, используем английский")
                return fallback_data

            # Очищаем от markdown форматирования
            if translated_content.startswith('```'):
                lines = translated_content.split('\n')
                translated_content = '\n'.join([line for line in lines if not line.strip().startswith('```')])

            # Парсим переведенный JSON
            translated_data = json.loads(translated_content)
            print(f"    ✓ Fallback успешно переведен на {language}")
            return translated_data

        except Exception as e:
            print(f"    ⚠️  Ошибка перевода fallback для {content_type}: {e}, используем английский")
            return fallback_data

    def get_theme_based_process_steps(self, theme):
        """Возвращает 4 шага процесса на основе темы"""
        theme_lower = theme.lower()

        # Travel / Tourism
        if any(word in theme_lower for word in ['travel', 'tourism', 'tour', 'vacation', 'holiday', 'trip']):
            return [
                {
                    'title': 'Choose Destination',
                    'description': 'Explore our curated destinations and find the perfect location that matches your travel dreams and preferences.'
                },
                {
                    'title': 'Plan Your Trip',
                    'description': 'Work with our travel experts to create a customized itinerary with activities, accommodations, and experiences.'
                },
                {
                    'title': 'Book & Prepare',
                    'description': 'Secure your bookings, handle documentation, and get ready for your adventure with our comprehensive travel guides.'
                },
                {
                    'title': 'Enjoy Journey',
                    'description': 'Embark on your adventure with 24/7 support, ensuring a memorable and hassle-free travel experience.'
                }
            ]

        # Restaurant / Food
        elif any(word in theme_lower for word in ['restaurant', 'cafe', 'food', 'dining', 'cuisine']):
            return [
                {
                    'title': 'Browse Menu',
                    'description': 'Discover our carefully crafted dishes made with fresh, locally-sourced ingredients and authentic recipes.'
                },
                {
                    'title': 'Make Reservation',
                    'description': 'Reserve your table easily online or by phone, selecting your preferred date, time, and seating area.'
                },
                {
                    'title': 'Prepare Your Meal',
                    'description': 'Our expert chefs prepare each dish with precision and passion, ensuring quality and authentic flavors.'
                },
                {
                    'title': 'Savor Experience',
                    'description': 'Enjoy exceptional dining in a welcoming atmosphere with attentive service and unforgettable culinary moments.'
                }
            ]

        # Fitness / Gym / Sports
        elif any(word in theme_lower for word in ['fitness', 'gym', 'sport', 'workout', 'training']):
            return [
                {
                    'title': 'Set Your Goals',
                    'description': 'Discuss your fitness objectives with our trainers to create a personalized path to success.'
                },
                {
                    'title': 'Get Custom Plan',
                    'description': 'Receive a tailored workout program designed specifically for your goals, fitness level, and schedule.'
                },
                {
                    'title': 'Train & Track',
                    'description': 'Follow your program with guidance from certified trainers while monitoring your progress and achievements.'
                },
                {
                    'title': 'Achieve Results',
                    'description': 'Reach your fitness goals and maintain your success with ongoing support and program adjustments.'
                }
            ]

        # Real Estate / Property
        elif any(word in theme_lower for word in ['real estate', 'property', 'realty', 'housing']):
            return [
                {
                    'title': 'Find Properties',
                    'description': 'Browse our extensive portfolio of properties that match your criteria, budget, and location preferences.'
                },
                {
                    'title': 'Schedule Viewing',
                    'description': 'Book private tours of your favorite properties with our experienced real estate professionals.'
                },
                {
                    'title': 'Make Offer',
                    'description': 'Submit your offer with expert guidance on pricing, negotiations, and contract terms.'
                },
                {
                    'title': 'Close Deal',
                    'description': 'Complete the transaction smoothly with our comprehensive support through every step of the process.'
                }
            ]

        # Education / School / Courses
        elif any(word in theme_lower for word in ['education', 'school', 'course', 'learning', 'training', 'academy']):
            return [
                {
                    'title': 'Explore Programs',
                    'description': 'Discover our range of courses and programs designed to help you achieve your educational goals.'
                },
                {
                    'title': 'Enroll & Start',
                    'description': 'Complete simple enrollment process and get access to learning materials and resources.'
                },
                {
                    'title': 'Learn & Practice',
                    'description': 'Engage with interactive lessons, assignments, and hands-on projects guided by expert instructors.'
                },
                {
                    'title': 'Graduate & Succeed',
                    'description': 'Complete your program, earn certification, and apply your new skills in real-world situations.'
                }
            ]

        # Healthcare / Medical / Clinic
        elif any(word in theme_lower for word in ['health', 'medical', 'clinic', 'doctor', 'care', 'hospital']):
            return [
                {
                    'title': 'Book Appointment',
                    'description': 'Schedule a consultation with our qualified healthcare professionals at your convenient time.'
                },
                {
                    'title': 'Consultation',
                    'description': 'Receive thorough examination and professional medical assessment of your health concerns.'
                },
                {
                    'title': 'Treatment Plan',
                    'description': 'Get personalized treatment recommendations and care plan tailored to your specific needs.'
                },
                {
                    'title': 'Follow-up Care',
                    'description': 'Continue your health journey with regular check-ups and ongoing support from our medical team.'
                }
            ]

        # Cryptocurrency / Blockchain / Crypto
        elif any(word in theme_lower for word in ['crypto', 'cryptocurrency', 'blockchain', 'bitcoin', 'ethereum', 'defi', 'nft', 'web3']):
            return [
                {
                    'title': 'Create Account',
                    'description': 'Sign up securely with advanced encryption and two-factor authentication to protect your digital assets.'
                },
                {
                    'title': 'Verify Identity',
                    'description': 'Complete quick KYC verification to ensure compliance and unlock full platform features and higher limits.'
                },
                {
                    'title': 'Fund & Trade',
                    'description': 'Deposit funds and start trading cryptocurrencies with our intuitive interface and advanced trading tools.'
                },
                {
                    'title': 'Secure & Grow',
                    'description': 'Store your assets in secure wallets and grow your portfolio with staking, lending, and yield farming.'
                }
            ]

        # Default / Business / Technology
        else:
            return [
                {
                    'title': 'Consultation',
                    'description': 'We listen to your needs, understand your goals, and identify the best approach for your project.'
                },
                {
                    'title': 'Planning',
                    'description': 'We create a detailed roadmap with clear milestones, timelines, and deliverables for your project.'
                },
                {
                    'title': 'Development',
                    'description': 'Our expert team brings your vision to life with cutting-edge technology and best practices.'
                },
                {
                    'title': 'Delivery',
                    'description': 'We launch your project and provide ongoing support to ensure everything runs smoothly.'
                }
            ]

    def get_theme_based_featured_solutions(self, theme):
        """Возвращает 3 решения/предложения на основе темы"""
        theme_lower = theme.lower()

        # Travel / Tourism
        if any(word in theme_lower for word in ['travel', 'tourism', 'tour', 'vacation', 'holiday', 'trip']):
            return [
                {
                    'title': 'Beach Resorts',
                    'description': 'Discover pristine beaches and luxury resorts with world-class amenities and breathtaking ocean views.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Adventure Tours',
                    'description': 'Experience thrilling adventures from mountain trekking to wildlife safaris in exotic locations.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Cultural Experiences',
                    'description': 'Immerse yourself in local cultures, traditions, and authentic experiences around the world.',
                    'image': 'service3.jpg'
                }
            ]

        # Restaurant / Food
        elif any(word in theme_lower for word in ['restaurant', 'cafe', 'food', 'dining', 'cuisine']):
            return [
                {
                    'title': 'Signature Dishes',
                    'description': 'Experience our chef\'s masterpieces crafted with the finest ingredients and traditional techniques.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Private Dining',
                    'description': 'Exclusive private dining experiences perfect for special occasions and intimate gatherings.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Catering Services',
                    'description': 'Professional catering for events of any size with customized menus and exceptional service.',
                    'image': 'service3.jpg'
                }
            ]

        # Fitness / Gym / Sports
        elif any(word in theme_lower for word in ['fitness', 'gym', 'sport', 'workout', 'training']):
            return [
                {
                    'title': 'Personal Training',
                    'description': 'One-on-one coaching with certified trainers to help you achieve your fitness goals faster.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Group Classes',
                    'description': 'Dynamic group fitness classes including yoga, HIIT, spinning, and more in motivating atmosphere.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Nutrition Plans',
                    'description': 'Customized meal plans and nutritional guidance to complement your fitness journey.',
                    'image': 'service3.jpg'
                }
            ]

        # Real Estate / Property
        elif any(word in theme_lower for word in ['real estate', 'property', 'realty', 'housing']):
            return [
                {
                    'title': 'Luxury Properties',
                    'description': 'Exclusive portfolio of premium homes and estates in the most desirable locations.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Investment Opportunities',
                    'description': 'High-return investment properties with strong appreciation potential and rental income.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Commercial Spaces',
                    'description': 'Prime commercial real estate for businesses looking to expand or relocate.',
                    'image': 'service3.jpg'
                }
            ]

        # Education / School / Courses
        elif any(word in theme_lower for word in ['education', 'school', 'course', 'learning', 'training', 'academy']):
            return [
                {
                    'title': 'Online Programs',
                    'description': 'Flexible online courses and certifications you can complete at your own pace from anywhere.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Expert Instructors',
                    'description': 'Learn from industry professionals with years of practical experience in their fields.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Career Support',
                    'description': 'Job placement assistance and career coaching to help you succeed after graduation.',
                    'image': 'service3.jpg'
                }
            ]

        # Healthcare / Medical / Clinic
        elif any(word in theme_lower for word in ['health', 'medical', 'clinic', 'doctor', 'care', 'hospital']):
            return [
                {
                    'title': 'Primary Care',
                    'description': 'Comprehensive preventive care and treatment for all your health and wellness needs.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Specialist Services',
                    'description': 'Access to experienced specialists across all medical disciplines and treatments.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Telehealth',
                    'description': 'Convenient virtual consultations with healthcare professionals from the comfort of home.',
                    'image': 'service3.jpg'
                }
            ]

        # Cryptocurrency / Blockchain / Crypto
        elif any(word in theme_lower for word in ['crypto', 'cryptocurrency', 'blockchain', 'bitcoin', 'ethereum', 'defi', 'nft', 'web3']):
            return [
                {
                    'title': 'Spot Trading',
                    'description': 'Trade 500+ cryptocurrencies with low fees, deep liquidity, and advanced charting tools.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Staking & Yield',
                    'description': 'Earn passive income by staking your crypto assets and participating in DeFi protocols.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Secure Wallet',
                    'description': 'Bank-grade security with cold storage, multi-signature protection, and insurance coverage.',
                    'image': 'service3.jpg'
                }
            ]

        # Default / Business / Technology
        else:
            return [
                {
                    'title': 'Enterprise Solutions',
                    'description': 'Scalable solutions designed for large-scale operations and complex requirements.',
                    'image': 'service1.jpg'
                },
                {
                    'title': 'Custom Development',
                    'description': 'Tailored solutions built specifically for your unique business needs and goals.',
                    'image': 'service2.jpg'
                },
                {
                    'title': 'Consulting Services',
                    'description': 'Expert guidance to help you navigate challenges and achieve your objectives.',
                    'image': 'service3.jpg'
                }
            ]

    def get_theme_based_approach_content(self, theme):
        """Возвращает контент для секции Our Approach на основе темы"""
        theme_lower = theme.lower()

        # Travel / Tourism
        if any(word in theme_lower for word in ['travel', 'tourism', 'tour', 'vacation', 'holiday', 'trip']):
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Approach',
                'approach_text1': 'We create personalized travel experiences that go beyond typical tourist destinations. Understanding your travel style and preferences allows us to craft unforgettable journeys.',
                'approach_text2': 'Our expert travel planners combine local knowledge with global expertise to design itineraries that match your dreams and exceed your expectations.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Choose Us',
                'why_text1': f'With years of experience in the {theme} industry, we\'ve helped thousands of travelers discover amazing destinations and create lasting memories.',
                'why_text2': 'Our dedication to exceptional service means you can travel with confidence, knowing every detail has been carefully planned and arranged for your comfort.'
            }

        # Restaurant / Food
        elif any(word in theme_lower for word in ['restaurant', 'cafe', 'food', 'dining', 'cuisine']):
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Philosophy',
                'approach_text1': 'We believe exceptional dining starts with the finest ingredients and passionate chefs who bring authentic flavors to every dish.',
                'approach_text2': 'Our culinary approach honors traditional recipes while embracing innovation, creating memorable dining experiences that delight all senses.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Dine With Us',
                'why_text1': f'With years of culinary excellence in the {theme} industry, we\'ve earned a reputation for outstanding food, warm hospitality, and unforgettable moments.',
                'why_text2': 'From sourcing fresh ingredients to crafting each dish with care, our commitment to quality shines through in every meal we serve.'
            }

        # Fitness / Gym / Sports
        elif any(word in theme_lower for word in ['fitness', 'gym', 'sport', 'workout', 'training']):
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Training Philosophy',
                'approach_text1': 'We understand that every fitness journey is unique. Our personalized approach focuses on your individual goals, abilities, and lifestyle.',
                'approach_text2': 'Combining proven training methods with cutting-edge fitness science, we create programs that deliver real, sustainable results.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Train With Us',
                'why_text1': f'With extensive experience in the {theme} industry, our certified trainers have helped countless members achieve and exceed their fitness goals.',
                'why_text2': 'Your success is our motivation. We provide ongoing support, expert guidance, and a welcoming community to keep you inspired every step of the way.'
            }

        # Real Estate / Property
        elif any(word in theme_lower for word in ['real estate', 'property', 'realty', 'housing']):
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Approach',
                'approach_text1': 'We take a personalized approach to real estate, taking time to understand your unique needs, preferences, and long-term investment goals.',
                'approach_text2': 'Our market expertise and dedication to client service ensure you make informed decisions whether buying, selling, or investing in property.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Choose Us',
                'why_text1': f'With deep knowledge of the {theme} market, we\'ve built a strong reputation for integrity, professionalism, and exceptional results.',
                'why_text2': 'From first consultation to closing and beyond, we\'re committed to making your real estate journey smooth, successful, and stress-free.'
            }

        # Education / School / Courses
        elif any(word in theme_lower for word in ['education', 'school', 'course', 'learning', 'training', 'academy']):
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Teaching Approach',
                'approach_text1': 'We believe effective learning combines engaging instruction, hands-on practice, and personalized support tailored to each student\'s needs.',
                'approach_text2': 'Our curriculum blends theoretical knowledge with practical skills, preparing students for real-world success in their chosen fields.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Learn With Us',
                'why_text1': f'With proven expertise in the {theme} field, our instructors bring both academic knowledge and industry experience to every class.',
                'why_text2': 'Your educational success matters to us. We provide comprehensive support, flexible learning options, and a pathway to achieving your career goals.'
            }

        # Healthcare / Medical / Clinic
        elif any(word in theme_lower for word in ['health', 'medical', 'clinic', 'doctor', 'care', 'hospital']):
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Care Philosophy',
                'approach_text1': 'We provide compassionate, patient-centered healthcare that treats you as a whole person, not just a set of symptoms.',
                'approach_text2': 'Our medical team combines clinical expertise with genuine care, ensuring you receive personalized treatment in a comfortable, supportive environment.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Choose Us',
                'why_text1': f'With years of experience in {theme}, we\'ve earned the trust of our community through quality care, professional excellence, and genuine compassion.',
                'why_text2': 'Your health and wellbeing are our priority. We\'re committed to providing accessible, comprehensive care that helps you live your healthiest life.'
            }

        # Cryptocurrency / Blockchain / Crypto
        elif any(word in theme_lower for word in ['crypto', 'cryptocurrency', 'blockchain', 'bitcoin', 'ethereum', 'defi', 'nft', 'web3']):
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Platform',
                'approach_text1': 'We\'ve built a cutting-edge cryptocurrency platform that combines institutional-grade security with an intuitive user experience for traders of all levels.',
                'approach_text2': 'Our technology infrastructure ensures lightning-fast execution, deep liquidity, and 24/7 uptime so you never miss market opportunities.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Trade With Us',
                'why_text1': f'As leaders in the {theme} space, we provide the most secure and reliable platform with advanced features trusted by millions of users worldwide.',
                'why_text2': 'Your assets are protected by multi-layered security, cold storage, and insurance. Our dedicated support team is available around the clock to assist you.'
            }

        # Default / Business / Technology
        else:
            return {
                'approach_badge': 'Our Philosophy',
                'approach_title': 'Our Approach',
                'approach_text1': 'We believe in a personalized approach to every project. Understanding your unique needs allows us to deliver tailored solutions that exceed expectations.',
                'approach_text2': 'Our methodology combines industry best practices with innovative thinking to ensure optimal results for your business.',
                'why_badge': 'Our Advantages',
                'why_title': 'Why Choose Us',
                'why_text1': f'With years of experience in the {theme} industry, we\'ve built a reputation for reliability, quality, and exceptional customer service.',
                'why_text2': 'Our commitment to your success drives everything we do, from initial consultation to project completion and beyond.'
            }

    def generate_image_text_alternating_section(self, site_name, theme, primary, hover):
        """Генерирует секцию Image Text Alternating с тематическим контентом"""
        content = self.generate_theme_content_via_api(theme, "approach_content", 1)

        # Fallback если API не вернул результат или вернул неполный результат
        if not content or not all(key in content for key in ['approach_badge', 'approach_title', 'approach_text1', 'approach_text2', 'why_badge', 'why_title', 'why_text1', 'why_text2']):
            content = self.get_theme_based_approach_content(theme)

        # service1.jpg и service2.jpg всегда генерируются как 'required'
        # поэтому можем смело использовать их без проверки наличия
        # (изображения генерируются ПОСЛЕ страниц, поэтому self.generated_images пуст на этом этапе)
        has_service1 = True
        has_service2 = True

        # Первая секция (approach)
        if has_service1:
            section1 = f"""
            <div class="grid md:grid-cols-2 gap-16 items-center mb-24">
                <div class="relative group">
                    <div class="absolute -inset-1 bg-gradient-to-r from-{primary} to-{hover} rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-300"></div>
                    <img src="images/service1.jpg" alt="{content.get('approach_title', 'Our Approach')}" class="relative rounded-2xl shadow-2xl w-full h-96 object-cover transition-transform duration-300 group-hover:scale-[1.02]">
                </div>
                <div class="space-y-6">
                    <div class="inline-block">
                        <span class="bg-{primary} text-white px-4 py-2 rounded-full text-sm font-semibold tracking-wide uppercase">{content.get('approach_badge', 'Our Philosophy')}</span>
                    </div>
                    <h3 class="text-4xl md:text-5xl font-bold text-gray-900 leading-tight">{content.get('approach_title', 'Our Approach')}</h3>
                    <div class="space-y-4">
                        <p class="text-lg text-gray-600 leading-relaxed">
                            {content.get('approach_text1', 'We believe in a personalized approach to every project.')}
                        </p>
                        <p class="text-lg text-gray-600 leading-relaxed">
                            {content.get('approach_text2', 'Our methodology combines industry best practices with innovative thinking.')}
                        </p>
                    </div>
                </div>
            </div>"""
        else:
            section1 = f"""
            <div class="mb-24 text-center max-w-4xl mx-auto">
                <div class="inline-block mb-6">
                    <span class="bg-{primary} text-white px-4 py-2 rounded-full text-sm font-semibold tracking-wide uppercase">{content.get('approach_badge', 'Our Philosophy')}</span>
                </div>
                <h3 class="text-4xl md:text-5xl font-bold text-gray-900 mb-8 leading-tight">{content.get('approach_title', 'Our Approach')}</h3>
                <div class="space-y-4">
                    <p class="text-lg text-gray-600 leading-relaxed">
                        {content.get('approach_text1', 'We believe in a personalized approach to every project.')}
                    </p>
                    <p class="text-lg text-gray-600 leading-relaxed">
                        {content.get('approach_text2', 'Our methodology combines industry best practices with innovative thinking.')}
                    </p>
                </div>
            </div>"""

        # Вторая секция (why)
        if has_service2:
            section2 = f"""
            <div class="grid md:grid-cols-2 gap-16 items-center">
                <div class="space-y-6 order-2 md:order-1">
                    <div class="inline-block">
                        <span class="bg-{primary} text-white px-4 py-2 rounded-full text-sm font-semibold tracking-wide uppercase">{content.get('why_badge', 'Our Advantages')}</span>
                    </div>
                    <h3 class="text-4xl md:text-5xl font-bold text-gray-900 leading-tight">{content.get('why_title', 'Why Choose Us')}</h3>
                    <div class="space-y-4">
                        <p class="text-lg text-gray-600 leading-relaxed">
                            {content.get('why_text1', 'We have built a reputation for reliability and quality.')}
                        </p>
                        <p class="text-lg text-gray-600 leading-relaxed">
                            {content.get('why_text2', 'Our commitment to your success drives everything we do.')}
                        </p>
                    </div>
                </div>
                <div class="relative group order-1 md:order-2">
                    <div class="absolute -inset-1 bg-gradient-to-r from-{hover} to-{primary} rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-300"></div>
                    <img src="images/service2.jpg" alt="{content.get('why_title', 'Why Choose Us')}" class="relative rounded-2xl shadow-2xl w-full h-96 object-cover transition-transform duration-300 group-hover:scale-[1.02]">
                </div>
            </div>"""
        else:
            section2 = f"""
            <div class="text-center max-w-4xl mx-auto">
                <div class="inline-block mb-6">
                    <span class="bg-{primary} text-white px-4 py-2 rounded-full text-sm font-semibold tracking-wide uppercase">{content.get('why_badge', 'Our Advantages')}</span>
                </div>
                <h3 class="text-4xl md:text-5xl font-bold text-gray-900 mb-8 leading-tight">{content.get('why_title', 'Why Choose Us')}</h3>
                <div class="space-y-4">
                    <p class="text-lg text-gray-600 leading-relaxed">
                        {content.get('why_text1', 'We have built a reputation for reliability and quality.')}
                    </p>
                    <p class="text-lg text-gray-600 leading-relaxed">
                        {content.get('why_text2', 'Our commitment to your success drives everything we do.')}
                    </p>
                </div>
            </div>"""

        return f"""
    <section class="py-24 bg-gradient-to-br from-gray-50 via-white to-gray-50">
        <div class="container mx-auto px-6">{section1}
{section2}
        </div>
    </section>"""

    def get_theme_based_what_we_offer(self, theme):
        """Возвращает 6 услуг/предложений на основе темы для секции What We Offer"""
        theme_lower = theme.lower()

        # Travel / Tourism
        if any(word in theme_lower for word in ['travel', 'tourism', 'tour', 'vacation', 'holiday', 'trip']):
            return [
                {'title': 'Flight Booking', 'description': 'Book flights to destinations worldwide with convenient scheduling and flexible options.'},
                {'title': 'Hotel Reservations', 'description': 'Access to thousands of hotels, resorts, and accommodations for every budget and style.'},
                {'title': 'Tour Packages', 'description': 'Curated tour packages combining activities, transport, and accommodations for seamless travel.'},
                {'title': 'Travel Insurance', 'description': 'Comprehensive travel insurance coverage for peace of mind during your journey.'},
                {'title': 'Visa Assistance', 'description': 'Expert help with visa applications and travel documentation requirements.'},
                {'title': '24/7 Support', 'description': 'Round-the-clock customer support to assist you anywhere in the world.'}
            ]

        # Restaurant / Food
        elif any(word in theme_lower for word in ['restaurant', 'cafe', 'food', 'dining', 'cuisine']):
            return [
                {'title': 'Dine-In Service', 'description': 'Enjoy exceptional meals in our welcoming atmosphere with attentive table service.'},
                {'title': 'Takeout Orders', 'description': 'Convenient takeout options with quick preparation and quality packaging.'},
                {'title': 'Delivery Service', 'description': 'Fast delivery bringing fresh, hot meals directly to your door.'},
                {'title': 'Catering Events', 'description': 'Professional catering for corporate events, parties, and special occasions.'},
                {'title': 'Private Dining', 'description': 'Exclusive private dining rooms perfect for intimate gatherings and celebrations.'},
                {'title': 'Chef Specials', 'description': 'Daily chef specials featuring seasonal ingredients and creative culinary innovations.'}
            ]

        # Fitness / Gym / Sports
        elif any(word in theme_lower for word in ['fitness', 'gym', 'sport', 'workout', 'training']):
            return [
                {'title': 'Personal Training', 'description': 'One-on-one coaching sessions customized to your goals and fitness level.'},
                {'title': 'Group Classes', 'description': 'Energizing group fitness classes including yoga, HIIT, cycling, and more.'},
                {'title': 'Nutrition Coaching', 'description': 'Personalized meal plans and nutritional guidance to support your fitness journey.'},
                {'title': 'Strength Training', 'description': 'State-of-the-art equipment and expert guidance for building strength and muscle.'},
                {'title': 'Cardio Programs', 'description': 'Comprehensive cardio training programs to improve endurance and heart health.'},
                {'title': 'Recovery Services', 'description': 'Massage therapy, stretching sessions, and recovery tools to prevent injury.'}
            ]

        # Real Estate / Property
        elif any(word in theme_lower for word in ['real estate', 'property', 'realty', 'housing']):
            return [
                {'title': 'Property Search', 'description': 'Access to extensive property listings with advanced search and filtering tools.'},
                {'title': 'Market Analysis', 'description': 'Expert market analysis and property valuations to inform your decisions.'},
                {'title': 'Buyer Representation', 'description': 'Professional representation throughout the entire home buying process.'},
                {'title': 'Seller Services', 'description': 'Comprehensive services to market and sell your property for top value.'},
                {'title': 'Investment Consulting', 'description': 'Strategic advice for real estate investments and portfolio growth.'},
                {'title': 'Property Management', 'description': 'Full-service property management for landlords and property owners.'}
            ]

        # Education / School / Courses
        elif any(word in theme_lower for word in ['education', 'school', 'course', 'learning', 'training', 'academy']):
            return [
                {'title': 'Online Courses', 'description': 'Self-paced online courses accessible anywhere with lifetime access to materials.'},
                {'title': 'Live Classes', 'description': 'Interactive live sessions with instructors for real-time learning and questions.'},
                {'title': 'Certifications', 'description': 'Industry-recognized certifications to validate your skills and knowledge.'},
                {'title': 'Career Services', 'description': 'Job placement assistance, resume reviews, and interview preparation.'},
                {'title': 'Mentorship Program', 'description': 'One-on-one mentorship with industry experts to guide your learning path.'},
                {'title': 'Learning Resources', 'description': 'Extensive library of tutorials, guides, and practice materials.'}
            ]

        # Healthcare / Medical / Clinic
        elif any(word in theme_lower for word in ['health', 'medical', 'clinic', 'doctor', 'care', 'hospital']):
            return [
                {'title': 'Primary Care', 'description': 'Comprehensive primary care services for routine check-ups and preventive health.'},
                {'title': 'Specialist Consultations', 'description': 'Access to experienced medical specialists across all healthcare disciplines.'},
                {'title': 'Diagnostic Testing', 'description': 'Advanced diagnostic services including lab work, imaging, and screening tests.'},
                {'title': 'Urgent Care', 'description': 'Walk-in urgent care for non-emergency medical conditions and injuries.'},
                {'title': 'Telehealth Services', 'description': 'Virtual consultations with healthcare providers from the comfort of home.'},
                {'title': 'Prescription Services', 'description': 'Convenient prescription management and refills with pharmacy coordination.'}
            ]

        # Cryptocurrency / Blockchain / Crypto
        elif any(word in theme_lower for word in ['crypto', 'cryptocurrency', 'blockchain', 'bitcoin', 'ethereum', 'defi', 'nft', 'web3']):
            return [
                {'title': 'Spot Trading', 'description': 'Trade 500+ cryptocurrencies with competitive fees and instant execution.'},
                {'title': 'Margin Trading', 'description': 'Leverage your positions with margin trading and advanced risk management tools.'},
                {'title': 'Staking Rewards', 'description': 'Earn passive income by staking supported cryptocurrencies with competitive APY.'},
                {'title': 'NFT Marketplace', 'description': 'Buy, sell, and trade NFTs on our secure and user-friendly marketplace.'},
                {'title': 'Crypto Wallet', 'description': 'Multi-currency wallet with cold storage and advanced security features.'},
                {'title': 'DeFi Integration', 'description': 'Access to decentralized finance protocols for lending, borrowing, and yield farming.'}
            ]

        # Default / Business / Technology
        else:
            default_solutions = [
                {'title': 'Consultation', 'description': 'Expert advice to help you make informed decisions about your project.'},
                {'title': 'Planning', 'description': 'Strategic planning to ensure your project\'s success from start to finish.'},
                {'title': 'Implementation', 'description': 'Professional execution with attention to every detail of your project.'},
                {'title': 'Testing', 'description': 'Thorough testing to ensure quality and reliability in all deliverables.'},
                {'title': 'Support', 'description': 'Ongoing support to help you get the most from your investment.'},
                {'title': 'Optimization', 'description': 'Continuous improvement to keep your solution performing at its best.'}
            ]
            # Локализуем каждую услугу (или пытаемся сгенерировать через API)
            return [self.get_localized_fallback('featured_solutions', sol, theme=theme) for sol in default_solutions]

    def generate_featured_solutions_section(self, site_name, theme, primary, hover):
        """Генерирует секцию Featured Solutions с тематическим контентом"""
        solutions = self.generate_theme_content_via_api(theme, "featured_solutions", 3)

        # Fallback если API не вернул результат
        if not solutions:
            solutions = self.get_theme_based_featured_solutions(theme)

        # Фильтруем решения - показываем только те, для которых есть изображения
        available_solutions = []
        for sol in solutions:
            if self._has_image(sol['image']):
                available_solutions.append(sol)

        # Если нет доступных изображений, не показываем секцию вообще
        if not available_solutions:
            return ""

        # Получаем переведенные заголовки секций
        section_headings = self.generate_theme_content_via_api(theme, "section_headings", 1)
        featured_solutions_heading = section_headings.get('featured_solutions', 'Featured Solutions') if section_headings else 'Featured Solutions'

        # Получаем переводы кнопок
        button_texts = self.generate_theme_content_via_api(theme, "button_texts", 1)
        contact_us_text = button_texts.get('contact_us', 'Contact Us') if button_texts else 'Contact Us'

        # Генерируем карточки только для доступных решений
        cards_html = ""
        _sol_contact_btn = ('' if self.site_type == 'landing' else
                            f'<a href="contact.php" class="inline-block bg-white text-{primary} px-6 py-3 rounded-lg font-semibold hover:bg-gray-100 transition w-fit">{contact_us_text}</a>')
        for sol in available_solutions:
            cards_html += f"""
                <div class="relative overflow-hidden rounded-xl shadow-lg h-96 group">
                    <img src="images/{sol['image']}" alt="{sol['title']}" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent"></div>
                    <div class="relative h-full flex flex-col justify-end p-8">
                        <h3 class="text-white text-2xl font-bold mb-3">{sol['title']}</h3>
                        <p class="text-white/90 mb-4">{sol['description']}</p>
                        {_sol_contact_btn}
                    </div>
                </div>"""

        # Адаптируем grid в зависимости от количества карточек
        grid_class = f"md:grid-cols-{len(available_solutions)}" if len(available_solutions) <= 3 else "md:grid-cols-3"

        return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">{featured_solutions_heading}</h2>
            <div class="grid {grid_class} gap-8">{cards_html}
            </div>
        </div>
    </section>"""

    def generate_our_process_section(self, site_name, theme, primary, hover):
        """Генерирует одну из 3 вариаций секции Our Process"""
        variation = random.randint(1, 3)
        steps = self.generate_theme_content_via_api(theme, "process_steps", 4)

        # Fallback если API не вернул результат
        if not steps:
            steps = self.get_theme_based_process_steps(theme)

        # Получаем переведенные заголовки секций
        section_headings = self.generate_theme_content_via_api(theme, "section_headings", 1)
        our_process_heading = section_headings.get('our_process', 'Our Process') if section_headings else 'Our Process'

        # Получаем переведенный подзаголовок для Our Process
        process_content = self.generate_theme_content_via_api(theme, "our_process_content", 1)
        if process_content and isinstance(process_content, dict):
            process_subheading = process_content.get('subheading', 'A proven methodology to transform your ideas into reality')
        else:
            process_subheading = 'A proven methodology to transform your ideas into reality'

        # Получаем переводы кнопок
        button_texts = self.generate_theme_content_via_api(theme, "button_texts", 1)
        start_project_text = button_texts.get('start_your_project', 'Start Your Project') if button_texts else 'Start Your Project'
        get_started_text = button_texts.get('get_started', 'Get Started') if button_texts else 'Get Started'

        # Получаем переводы меток шагов через локализацию (не через API, так как это простые метки)
        step_labels_fallback = {
            'step_1': 'STEP 01',
            'step_2': 'STEP 02',
            'step_3': 'STEP 03',
            'step_4': 'STEP 04'
        }
        step_labels_localized = self.get_localized_fallback('step_labels', step_labels_fallback)
        step_labels = [
            step_labels_localized.get('step_1', 'STEP 01'),
            step_labels_localized.get('step_2', 'STEP 02'),
            step_labels_localized.get('step_3', 'STEP 03'),
            step_labels_localized.get('step_4', 'STEP 04')
        ]

        _cta_start = ('' if self.site_type == 'landing' else
                      f'<div class="text-center mt-16"><a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">{start_project_text}</a></div>')
        _cta_get_started = ('' if self.site_type == 'landing' else
                            f'<div class="text-center mt-16"><a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">{get_started_text}</a></div>')

        if variation == 1:
            return f"""
    <section class="py-20 bg-gradient-to-br from-gray-50 to-white relative overflow-hidden">
        <div class="absolute top-0 right-0 w-96 h-96 bg-{primary}/5 rounded-full blur-3xl"></div>
        <div class="absolute bottom-0 left-0 w-96 h-96 bg-{hover}/5 rounded-full blur-3xl"></div>

        <div class="container mx-auto px-6 relative z-10">
            <div class="text-center mb-16">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">{our_process_heading}</h2>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">{process_subheading}</p>
            </div>

            <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-7xl mx-auto">
                <div class="group relative">
                    <div class="bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 h-full border-2 border-transparent hover:border-{primary}/20">
                        <div class="absolute -top-4 -right-4 w-12 h-12 bg-{primary} rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg transform group-hover:scale-110 transition-transform">
                            01
                        </div>
                        <div class="w-16 h-16 bg-gradient-to-br from-{primary} to-{hover} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                            <svg class="w-8 h-8 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
                            </svg>
                        </div>
                        <h3 class="text-2xl font-bold mb-3 text-gray-900">{steps[0]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{steps[0]['description']}</p>
                    </div>
                </div>

                <div class="group relative">
                    <div class="bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 h-full border-2 border-transparent hover:border-{primary}/20">
                        <div class="absolute -top-4 -right-4 w-12 h-12 bg-{primary} rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg transform group-hover:scale-110 transition-transform">
                            02
                        </div>
                        <div class="w-16 h-16 bg-gradient-to-br from-{primary} to-{hover} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                            <svg class="w-8 h-8 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                            </svg>
                        </div>
                        <h3 class="text-2xl font-bold mb-3 text-gray-900">{steps[1]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{steps[1]['description']}</p>
                    </div>
                </div>

                <div class="group relative">
                    <div class="bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 h-full border-2 border-transparent hover:border-{primary}/20">
                        <div class="absolute -top-4 -right-4 w-12 h-12 bg-{primary} rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg transform group-hover:scale-110 transition-transform">
                            03
                        </div>
                        <div class="w-16 h-16 bg-gradient-to-br from-{primary} to-{hover} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                            <svg class="w-8 h-8 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                            </svg>
                        </div>
                        <h3 class="text-2xl font-bold mb-3 text-gray-900">{steps[2]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{steps[2]['description']}</p>
                    </div>
                </div>

                <div class="group relative">
                    <div class="bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 h-full border-2 border-transparent hover:border-{primary}/20">
                        <div class="absolute -top-4 -right-4 w-12 h-12 bg-{primary} rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg transform group-hover:scale-110 transition-transform">
                            04
                        </div>
                        <div class="w-16 h-16 bg-gradient-to-br from-{primary} to-{hover} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                            <svg class="w-8 h-8 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                            </svg>
                        </div>
                        <h3 class="text-2xl font-bold mb-3 text-gray-900">{steps[3]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{steps[3]['description']}</p>
                    </div>
                </div>
            </div>

            {_cta_start}
        </div>
    </section>"""

        elif variation == 2:
            return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-20">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">{our_process_heading}</h2>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">{process_subheading}</p>
            </div>

            <div class="max-w-6xl mx-auto">
                <div class="relative">
                    <div class="hidden md:block absolute top-24 left-0 right-0 h-1 bg-gradient-to-r from-{primary} via-{hover} to-{primary}"></div>

                    <div class="grid md:grid-cols-4 gap-8 relative">
                        <div class="text-center group">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-{primary} rounded-full mb-6 shadow-xl relative z-10 group-hover:scale-110 transition-transform">
                                <svg class="w-10 h-10 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                                </svg>
                            </div>
                            <div class="bg-gray-50 rounded-xl p-6 hover:shadow-lg transition-shadow">
                                <div class="text-{primary} font-bold text-lg mb-2">{step_labels[0]}</div>
                                <h3 class="text-xl font-bold mb-3">{steps[0]['title']}</h3>
                                <p class="text-gray-600">{steps[0]['description']}</p>
                            </div>
                        </div>

                        <div class="text-center group">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-{primary} rounded-full mb-6 shadow-xl relative z-10 group-hover:scale-110 transition-transform">
                                <svg class="w-10 h-10 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"></path>
                                </svg>
                            </div>
                            <div class="bg-gray-50 rounded-xl p-6 hover:shadow-lg transition-shadow">
                                <div class="text-{primary} font-bold text-lg mb-2">{step_labels[1]}</div>
                                <h3 class="text-xl font-bold mb-3">{steps[1]['title']}</h3>
                                <p class="text-gray-600">{steps[1]['description']}</p>
                            </div>
                        </div>

                        <div class="text-center group">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-{primary} rounded-full mb-6 shadow-xl relative z-10 group-hover:scale-110 transition-transform">
                                <svg class="w-10 h-10 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                                </svg>
                            </div>
                            <div class="bg-gray-50 rounded-xl p-6 hover:shadow-lg transition-shadow">
                                <div class="text-{primary} font-bold text-lg mb-2">{step_labels[2]}</div>
                                <h3 class="text-xl font-bold mb-3">{steps[2]['title']}</h3>
                                <p class="text-gray-600">{steps[2]['description']}</p>
                            </div>
                        </div>

                        <div class="text-center group">
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-{primary} rounded-full mb-6 shadow-xl relative z-10 group-hover:scale-110 transition-transform">
                                <svg class="w-10 h-10 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>
                                </svg>
                            </div>
                            <div class="bg-gray-50 rounded-xl p-6 hover:shadow-lg transition-shadow">
                                <div class="text-{primary} font-bold text-lg mb-2">{step_labels[3]}</div>
                                <h3 class="text-xl font-bold mb-3">{steps[3]['title']}</h3>
                                <p class="text-gray-600">{steps[3]['description']}</p>
                            </div>
                        </div>
                    </div>
                </div>

                {_cta_get_started}
            </div>
        </div>
    </section>"""

        else:
            return f"""
    <section class="py-20 bg-gradient-to-b from-white to-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-20">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">{our_process_heading}</h2>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">{process_subheading}</p>
            </div>

            <div class="max-w-4xl mx-auto space-y-12">
                <div class="flex flex-col md:flex-row items-center gap-8 group">
                    <div class="md:w-1/2 md:text-right">
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">{step_labels[0]}</div>
                        <h3 class="text-3xl font-bold mb-4">{steps[0]['title']}</h3>
                        <p class="text-gray-600 text-lg leading-relaxed">{steps[0]['description']}</p>
                    </div>
                    <div class="md:w-1/2 flex justify-center">
                        <div class="w-32 h-32 bg-gradient-to-br from-{primary} to-{hover} rounded-2xl flex items-center justify-center shadow-2xl group-hover:scale-110 transition-transform">
                            <svg class="w-16 h-16 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                            </svg>
                        </div>
                    </div>
                </div>

                <div class="flex flex-col md:flex-row-reverse items-center gap-8 group">
                    <div class="md:w-1/2 md:text-left">
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">{step_labels[1]}</div>
                        <h3 class="text-3xl font-bold mb-4">{steps[1]['title']}</h3>
                        <p class="text-gray-600 text-lg leading-relaxed">{steps[1]['description']}</p>
                    </div>
                    <div class="md:w-1/2 flex justify-center">
                        <div class="w-32 h-32 bg-gradient-to-br from-{primary} to-{hover} rounded-2xl flex items-center justify-center shadow-2xl group-hover:scale-110 transition-transform">
                            <svg class="w-16 h-16 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                            </svg>
                        </div>
                    </div>
                </div>

                <div class="flex flex-col md:flex-row items-center gap-8 group">
                    <div class="md:w-1/2 md:text-right">
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">{step_labels[2]}</div>
                        <h3 class="text-3xl font-bold mb-4">{steps[2]['title']}</h3>
                        <p class="text-gray-600 text-lg leading-relaxed">{steps[2]['description']}</p>
                    </div>
                    <div class="md:w-1/2 flex justify-center">
                        <div class="w-32 h-32 bg-gradient-to-br from-{primary} to-{hover} rounded-2xl flex items-center justify-center shadow-2xl group-hover:scale-110 transition-transform">
                            <svg class="w-16 h-16 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                            </svg>
                        </div>
                    </div>
                </div>

                <div class="flex flex-col md:flex-row-reverse items-center gap-8 group">
                    <div class="md:w-1/2 md:text-left">
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">{step_labels[3]}</div>
                        <h3 class="text-3xl font-bold mb-4">{steps[3]['title']}</h3>
                        <p class="text-gray-600 text-lg leading-relaxed">{steps[3]['description']}</p>
                    </div>
                    <div class="md:w-1/2 flex justify-center">
                        <div class="w-32 h-32 bg-gradient-to-br from-{primary} to-{hover} rounded-2xl flex items-center justify-center shadow-2xl group-hover:scale-110 transition-transform">
                            <svg class="w-16 h-16 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                        </div>
                    </div>
                </div>
            </div>

            {_cta_start}
        </div>
    </section>"""

    def generate_what_we_offer_section(self, site_name, theme, primary, hover):
        """Генерирует одну из 3 вариаций секции What We Offer (6 карточек)"""
        variation = random.randint(1, 3)
        services = self.generate_theme_content_via_api(theme, "services", 6)

        # Fallback если API не вернул результат
        if not services:
            services = self.get_theme_based_what_we_offer(theme)

        # Получаем переводы для What We Offer
        what_we_offer_data = self.generate_theme_content_via_api(theme, "what_we_offer_content", 1)
        if not what_we_offer_data:
            what_we_offer_data_fallback = {
                'heading': 'What We Offer',
                'subheading_1': 'Comprehensive solutions tailored to your needs',
                'subheading_2': 'Discover our range of professional services designed to elevate your business',
                'subheading_3': 'Six core services that drive exceptional results',
                'variant_heading': 'We serve our clients around the globe',
                'learn_more': 'Learn More',
                'explore': 'Explore',
                'read_more': 'Read More'
            }
            what_we_offer_data = self.get_localized_fallback('what_we_offer_content', what_we_offer_data_fallback)
        heading = what_we_offer_data.get('heading', 'What We Offer')
        subheading_1 = what_we_offer_data.get('subheading_1', 'Comprehensive solutions tailored to your needs')
        subheading_2 = what_we_offer_data.get('subheading_2', 'Discover our range of professional services designed to elevate your business')
        subheading_3 = what_we_offer_data.get('subheading_3', 'Six core services that drive exceptional results')
        learn_more = what_we_offer_data.get('learn_more', 'Learn More')
        explore = what_we_offer_data.get('explore', 'Explore')

        # Получаем переводы кнопок
        button_texts = self.generate_theme_content_via_api(theme, "button_texts", 1)
        discuss_project_text = button_texts.get('discuss_your_project', 'Discuss Your Project') if button_texts else 'Discuss Your Project'

        _card_link_v1 = ('' if self.site_type == 'landing' else
                         f'<a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">\n                        {learn_more} →\n                    </a>')
        _card_link_v2 = ('' if self.site_type == 'landing' else
                         f'<a href="contact.php" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition group-hover:translate-x-2 transform duration-300">\n                        {explore} <span class="ml-2">→</span>\n                    </a>')
        _cta_discuss = ('' if self.site_type == 'landing' else
                        f'<div class="text-center mt-16"><a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">{discuss_project_text}</a></div>')

        if variation == 1:
            return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-4">{heading}</h2>
            <p class="text-gray-600 text-center mb-12 text-lg">{subheading_1}</p>
            <div class="grid md:grid-cols-3 gap-6">
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[0]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[0]['description']}</p>
                    {_card_link_v1}
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[1]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[1]['description']}</p>
                    {_card_link_v1}
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[2]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[2]['description']}</p>
                    {_card_link_v1}
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[3]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[3]['description']}</p>
                    {_card_link_v1}
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[4]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[4]['description']}</p>
                    {_card_link_v1}
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[5]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[5]['description']}</p>
                    {_card_link_v1}
                </div>
            </div>
        </div>
    </section>"""

        elif variation == 2:
            return f"""
    <section class="py-20 bg-gradient-to-br from-gray-50 to-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">{heading}</h2>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">{subheading_2}</p>
            </div>

            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[0]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[0]['description']}</p>
                    {_card_link_v2}
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[1]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[1]['description']}</p>
                    {_card_link_v2}
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[2]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[2]['description']}</p>
                    {_card_link_v2}
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[3]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[3]['description']}</p>
                    {_card_link_v2}
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[4]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[4]['description']}</p>
                    {_card_link_v2}
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[5]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[5]['description']}</p>
                    {_card_link_v2}
                </div>
            </div>
        </div>
    </section>"""

        else:
            return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">{heading}</h2>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">{subheading_3}</p>
            </div>

            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        01
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[0]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{services[0]['description']}</p>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        02
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[1]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{services[1]['description']}</p>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        03
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[2]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{services[2]['description']}</p>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        04
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[3]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{services[3]['description']}</p>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        05
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[4]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{services[4]['description']}</p>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        06
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[5]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{services[5]['description']}</p>
                    </div>
                </div>
            </div>

            {_cta_discuss}
        </div>
    </section>"""

    def generate_work_showcase_section(self, site_name, theme, primary, hover):
        """Генерирует секцию Work Showcase с уникальными кейсами через API"""
        # Получаем кейсы через API
        work_data = self.generate_theme_content_via_api(theme, "work_showcase", 4)

        # Fallback если API не вернул результат
        if not work_data or not work_data.get('cases') or len(work_data.get('cases', [])) < 4:
            section_heading = 'Our Work & Expertise'
            section_description = 'We bring proven experience and innovative solutions to every project. Here are some highlights from our journey in delivering exceptional results.'
            cta_heading = 'Ready to Create Your Success Story?'
            cta_description = "These are just a few examples of how we've helped organizations achieve their goals. Let's discuss how we can bring similar results to your business."
            cta_button = 'Start Your Project'
            case_studies = [
                {
                    'title': 'Strategic Implementation Project',
                    'description': f'Successfully delivered a comprehensive solution that transformed operations and enhanced efficiency. Our team worked closely with stakeholders to ensure seamless integration and measurable results.',
                    'metrics': ['Significant efficiency gains', 'Enhanced user experience', 'Successful deployment']
                },
                {
                    'title': 'Innovation Initiative',
                    'description': f'Developed and launched an innovative platform that addressed critical challenges in the {theme} sector. The solution gained widespread adoption and positive feedback from users.',
                    'metrics': ['Strong user adoption', 'Positive industry feedback', 'Sustained growth']
                },
                {
                    'title': 'Optimization & Enhancement',
                    'description': f'Partnered with an organization to optimize their operations while improving overall performance. Through strategic planning and modern approaches, we achieved substantial improvements.',
                    'metrics': ['Improved performance', 'Streamlined operations', 'Enhanced capabilities']
                },
                {
                    'title': 'Community Success Story',
                    'description': f'Created a solution for an organization that made a real difference in their operations. Our platform improved coordination, streamlined processes, and enhanced overall effectiveness.',
                    'metrics': ['Improved coordination', 'Better efficiency', 'Recognized achievement']
                }
            ]
        else:
            section_heading = work_data.get('section_heading', 'Our Work & Expertise')
            section_description = work_data.get('section_description', 'We bring proven experience and innovative solutions to every project.')
            cta_heading = work_data.get('cta_heading', 'Ready to Create Your Success Story?')
            cta_description = work_data.get('cta_description', "Let's discuss how we can help you achieve your goals.")
            cta_button = work_data.get('cta_button', 'Start Your Project')
            case_studies = work_data.get('cases', [])

        _work_cta_btn = ('' if self.site_type == 'landing' else
                         f'<a href="contact.php" class="inline-block bg-white text-{primary} hover:bg-gray-100 px-8 py-4 rounded-lg font-semibold transition shadow-lg hover:shadow-xl">{cta_button}</a>')

        # SVG иконки для карточек
        icons = [
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1"></path>',
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>'
        ]

        # Генерируем карточки кейсов
        cards_html = ""
        for i, case in enumerate(case_studies[:4]):
            icon = icons[i]
            metrics_html = "\n".join([f'                                <li>• {metric}</li>' for metric in case['metrics']])

            cards_html += f"""
                <div class="bg-white rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow">
                    <div class="flex items-start mb-4">
                        <div class="bg-{primary} text-white rounded-lg p-4 mr-4 flex-shrink-0">
                            <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                {icon}
                            </svg>
                        </div>
                        <div>
                            <h3 class="text-2xl font-bold mb-3">{case['title']}</h3>
                            <p class="text-gray-700 mb-3">
                                {case['description']}
                            </p>
                            <ul class="text-gray-600 space-y-1">
{metrics_html}
                            </ul>
                        </div>
                    </div>
                </div>
"""

        return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl font-bold mb-4">{section_heading}</h2>
                <p class="text-gray-600 text-lg max-w-3xl mx-auto">
                    {section_description}
                </p>
            </div>

            <div class="grid md:grid-cols-2 gap-8 mb-12">{cards_html}
            </div>

            <div class="bg-{primary} rounded-xl p-8 text-white text-center">
                <h3 class="text-2xl font-bold mb-4">{cta_heading}</h3>
                <p class="text-white/90 mb-6 max-w-2xl mx-auto">
                    {cta_description}
                </p>
                {_work_cta_btn}
            </div>
        </div>
    </section>"""

    def generate_about_us_section(self, site_name, theme, primary, hover):
        """Генерирует секцию About Us через API с языковой поддержкой"""
        # Получаем 1 элемент с типом "about_content" для About секции
        about_data = self.generate_theme_content_via_api(theme, "about_content", 1)

        # Fallback если API не вернул результат
        if not about_data:
            from datetime import datetime
            current_year = datetime.now().year

            about_data_fallback = {
                'heading': 'About Us',
                'founded_year': str(current_year - 5),
                'paragraph1': f'We are dedicated to providing exceptional {theme} services that help our clients achieve their goals. With years of experience and a commitment to excellence, we deliver results that matter.',
                'paragraph2': 'Our team of professionals brings expertise, innovation, and a customer-first approach to every project. We understand that every client is unique, and we tailor our solutions to meet your specific needs.',
                'button_text': 'Learn More'
            }
            about_data = self.get_localized_fallback('about_content', about_data_fallback, theme=theme, num_items=1)

        # API возвращает словарь для about_content, не список
        content = about_data if isinstance(about_data, dict) else about_data[0]

        # Формируем отображение года основания
        founded_year_badge = ""
        if content.get('founded_year'):
            founded_year_badge = f'<span class="inline-block bg-{primary}/10 text-{primary} px-4 py-2 rounded-lg font-semibold mb-4">Est. {content.get("founded_year")}</span>'
        _company_link = ('' if self.site_type == 'landing' else
                         f'<a href="company.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg font-semibold transition">{content.get("button_text", "Learn More")}</a>')

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    {founded_year_badge}
                    <h2 class="text-4xl font-bold mb-6">{content.get('heading', 'About Us')}</h2>
                    <p class="text-gray-700 mb-4 text-lg">
                        {content.get('paragraph1', f'We are dedicated to providing exceptional {theme} services.')}
                    </p>
                    <p class="text-gray-700 mb-6">
                        {content.get('paragraph2', 'Our team brings expertise and innovation to every project.')}
                    </p>
                    {_company_link}
                </div>
                <div>
                    <img src="images/about.jpg" alt="{content.get('heading', 'About Us')}" class="rounded-xl shadow-lg w-full h-96 object-cover">
                </div>
            </div>
        </div>
    </section>"""

    def generate_gallery_section(self, site_name, theme, primary, hover):
        """Генерирует секцию Gallery через API с языковой поддержкой"""
        # Получаем 1 элемент с типом "gallery_content" для заголовков
        gallery_data = self.generate_theme_content_via_api(theme, "gallery_content", 1)

        # Fallback если API не вернул результат
        if not gallery_data:
            gallery_data_fallback = {
                'heading': 'Our Gallery',
                'subheading': 'Explore our latest projects and achievements',
                'captions': ['Professional Excellence', 'Quality Service', 'Innovation']
            }
            gallery_data = self.get_localized_fallback('gallery_content', gallery_data_fallback)

        # API возвращает словарь для gallery_content, не список
        content = gallery_data if isinstance(gallery_data, dict) else gallery_data[0]
        captions = content.get('captions', ['Professional Excellence', 'Quality Service', 'Innovation'])

        return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-12">
                <h2 class="text-4xl font-bold mb-4">{content.get('heading', 'Our Gallery')}</h2>
                <p class="text-gray-600 text-lg">{content.get('subheading', 'Explore our latest projects')}</p>
            </div>
            <div class="grid md:grid-cols-3 gap-6">
                <div class="group relative overflow-hidden rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300">
                    <img src="images/gallery1.jpg" alt="Gallery 1" class="w-full h-64 object-cover">
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-70 transition-all duration-300 flex items-center justify-center">
                        <p class="text-white text-center px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            {captions[0] if len(captions) > 0 else 'Excellence'}
                        </p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300">
                    <img src="images/gallery2.jpg" alt="Gallery 2" class="w-full h-64 object-cover">
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-70 transition-all duration-300 flex items-center justify-center">
                        <p class="text-white text-center px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            {captions[1] if len(captions) > 1 else 'Quality'}
                        </p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300">
                    <img src="images/gallery3.jpg" alt="Gallery 3" class="w-full h-64 object-cover">
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-70 transition-all duration-300 flex items-center justify-center">
                        <p class="text-white text-center px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            {captions[2] if len(captions) > 2 else 'Innovation'}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </section>"""

    def generate_services_cards_section(self, site_name, theme, primary, hover):
        """Генерирует секцию Services Cards (3 карточки) через API с языковой поддержкой"""
        # Получаем заголовки секций через API для перевода
        section_headings = self.generate_theme_content_via_api(theme, "section_headings", 1)
        services_heading = section_headings.get('services', 'Our Services') if section_headings else 'Our Services'

        # Получаем 3 сервиса через API
        services = self.generate_theme_content_via_api(theme, "services", 3)

        # Fallback если API не вернул результат
        if not services or len(services) < 3:
            services = [
                {'title': 'Fast Service', 'description': 'Quick turnaround times without compromising on quality. We deliver results when you need them.'},
                {'title': 'Quality Assured', 'description': 'Every project undergoes rigorous quality checks to ensure excellence in every detail.'},
                {'title': 'Expert Team', 'description': 'Our experienced professionals bring knowledge and dedication to every project we undertake.'}
            ]

        # SVG иконки для карточек
        icons = [
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>'
        ]

        # Генерируем карточки
        cards_html = ''
        for i, service in enumerate(services[:3]):
            icon_svg = icons[i] if i < len(icons) else icons[0]
            cards_html += f"""
                <div class="group bg-white border border-gray-200 rounded-xl p-8 hover:shadow-2xl hover:scale-105 transition-all duration-300 cursor-pointer">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-{primary} transition-colors">
                        <svg class="w-8 h-8 text-{primary} group-hover:text-white transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            {icon_svg}
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4 group-hover:text-{primary} transition-colors">{service['title']}</h3>
                    <p class="text-gray-600">{service['description']}</p>
                </div>"""

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">{services_heading}</h2>
            <div class="grid md:grid-cols-3 gap-8">{cards_html}
            </div>
        </div>
    </section>"""

    def generate_blog_preview_section(self, site_name, theme, primary, hover):
        """Генерирует секцию Blog Preview через API с языковой поддержкой

        Синхронизируется с blog_posts_previews в blueprint для согласованности
        между главной страницей, blog.php и отдельными статьями blog1-blog6.php
        """
        # Получаем заголовки секции через API
        blog_headers = self.generate_theme_content_via_api(theme, "blog_section_headers", 1)

        # Fallback для заголовков
        if not blog_headers:
            headers_fallback = {
                'section_heading': 'Latest from Our Blog',
                'view_all_text': 'View All',
                'read_more': 'Read More'
            }
            blog_headers = self.get_localized_fallback('blog_section_headers', headers_fallback)

        section_heading = blog_headers.get('section_heading', 'Latest from Our Blog')
        read_more_text = blog_headers.get('read_more', 'Read More')

        num_preview_posts = random.randint(3, 6)

        # КРИТИЧЕСКИ ВАЖНО: Проверяем, есть ли уже blog_posts_previews в blueprint
        # Если есть - используем их для синхронизации с blog.php и blog1-blog6.php
        if hasattr(self, 'blueprint') and 'blog_posts_previews' in self.blueprint:
            # Используем существующие данные из blueprint
            all_blog_articles = self.blueprint['blog_posts_previews']
            blog_posts = all_blog_articles[:num_preview_posts]
        else:
            # Генерируем 6 статей через API (будут использоваться позже в blog.php)
            api_blog_posts = self.generate_theme_content_via_api(theme, "blog_posts", 6)

            # Fallback если API не вернул результат
            if not api_blog_posts or len(api_blog_posts) < 6:
                # Генерируем даты с интервалом ~6 месяцев от текущей даты
                from datetime import datetime, timedelta

                now = datetime.now()
                blog_dates = []
                current_date = now
                for i in range(6):
                    blog_dates.append(current_date.strftime('%B %d, %Y'))
                    # Вычитаем примерно 6 месяцев (150-210 дней)
                    current_date = current_date - timedelta(days=random.randint(150, 210))

                all_blog_articles = [
                    {
                        'title': f'The Future of {theme}',
                        'url': 'blog1.php',
                        'excerpt': f'Explore the latest innovations in {theme} and what they mean for your business.',
                        'date': blog_dates[0],
                        'image': 'images/blog1.jpg'
                    },
                    {
                        'title': f'Top 5 Trends in {theme}',
                        'url': 'blog2.php',
                        'excerpt': f'Stay competitive with these emerging trends in the {theme} industry.',
                        'date': blog_dates[1],
                        'image': 'images/blog2.jpg'
                    },
                    {
                        'title': f'How to Choose the Right {theme} Service',
                        'url': 'blog3.php',
                        'excerpt': f'A comprehensive guide to selecting the best {theme} solution for your needs.',
                        'date': blog_dates[2],
                        'image': 'images/blog3.jpg'
                    },
                    {
                        'title': f'Best Practices for {theme} Success',
                        'url': 'blog4.php',
                        'excerpt': f'Learn proven strategies and techniques to maximize your {theme} results.',
                        'date': blog_dates[3],
                        'image': 'images/blog4.jpg'
                    },
                    {
                        'title': f'Common {theme} Mistakes to Avoid',
                        'url': 'blog5.php',
                        'excerpt': f'Discover the pitfalls that could derail your {theme} projects and how to avoid them.',
                        'date': blog_dates[4],
                        'image': 'images/blog5.jpg'
                    },
                    {
                        'title': f'The Complete {theme} Guide',
                        'url': 'blog6.php',
                        'excerpt': f'Everything you need to know about {theme} in one comprehensive resource.',
                        'date': blog_dates[5],
                        'image': 'images/blog6.jpg'
                    }
                ]
            else:
                # Используем данные из API и добавляем URL и изображения
                all_blog_articles = []
                for i, post in enumerate(api_blog_posts[:6]):
                    all_blog_articles.append({
                        'title': post.get('title', f'{theme} Article {i+1}'),
                        'url': f'blog{i+1}.php',
                        'excerpt': post.get('excerpt', f'Read about {theme}...'),
                        'date': post.get('date', 'November 2025'),
                        'image': f'images/blog{i+1}.jpg'
                    })

            # Сохраняем в blueprint для использования в blog.php и blog1-blog6.php
            self.blueprint['blog_posts_previews'] = all_blog_articles
            blog_posts = all_blog_articles[:num_preview_posts]

        # Генерируем статьи
        articles_html = ''
        for i, post in enumerate(blog_posts):
            article_num = i + 1
            articles_html += f"""
                <article class="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow">
                    <img src="images/blog{article_num}.jpg" alt="Blog Post {article_num}" class="w-full h-48 object-cover">
                    <div class="p-6">
                        <p class="text-gray-500 text-sm mb-2">{post.get('date', 'November 2025')}</p>
                        <h3 class="text-xl font-bold mb-3">{post['title']}</h3>
                        <p class="text-gray-600 mb-4">{post.get('excerpt', post.get('description', ''))}</p>
                        <a href="blog{article_num}.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                            {read_more_text} →
                        </a>
                    </div>
                </article>"""

        return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold mb-12">{section_heading}</h2>
            <div class="grid md:grid-cols-3 gap-8">{articles_html}
            </div>
        </div>
    </section>"""

    def generate_faq_section(self, theme, primary):
        """Генерирует секцию FAQ с переведенными заголовками и вопросами"""
        # Получаем переведенные заголовки секций
        section_headings = self.generate_theme_content_via_api(theme, "section_headings", 1)
        faq_heading = section_headings.get('faq', 'Frequently Asked Questions') if section_headings else 'Frequently Asked Questions'

        # Получаем переведенные FAQ блоки
        faq_data = self.generate_theme_content_via_api(theme, "faq_blocks", 4)

        # Fallback если API не вернул результат
        if not faq_data or not isinstance(faq_data, dict) or 'questions' not in faq_data:
            faq_data_fallback = {
                "section_description": "Find answers to common questions about our services",
                "questions": [
                    {
                        "question": "What services do you offer?",
                        "answer": f"We provide comprehensive {theme} services tailored to your specific needs, including consultation, implementation, and ongoing support."
                    },
                    {
                        "question": "How long does a typical project take?",
                        "answer": "Project timelines vary based on scope and complexity. We provide detailed timelines during the initial consultation phase."
                    },
                    {
                        "question": "Do you offer support after project completion?",
                        "answer": "Yes, we provide comprehensive post-project support and maintenance to ensure long-term success."
                    },
                    {
                        "question": "What makes your company different?",
                        "answer": "Our commitment to quality, personalized approach, and proven track record set us apart in the industry."
                    }
                ]
            }
            faq_data = self.get_localized_fallback('faq_content', faq_data_fallback)

        section_description = faq_data.get('section_description', 'Find answers to common questions about our services')
        questions = faq_data.get('questions', [])

        # Генерируем HTML для вопросов
        faq_items = ''
        for q in questions[:4]:  # Берем только первые 4 вопроса
            faq_items += f'''
                <div class="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition">
                    <h3 class="text-xl font-bold mb-2 text-{primary}">{q['question']}</h3>
                    <p class="text-gray-600">{q['answer']}</p>
                </div>'''

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl font-bold mb-4">{faq_heading}</h2>
                <p class="text-gray-600 text-lg">{section_description}</p>
            </div>
            <div class="max-w-3xl mx-auto space-y-4">{faq_items}
            </div>
        </div>
    </section>"""

    def generate_our_approach_section(self, theme, primary):
        """Генерирует секцию Our Approach с переведенными заголовками и блоками"""
        # Получаем переведенные заголовки секций
        section_headings = self.generate_theme_content_via_api(theme, "section_headings", 1)
        our_approach_heading = section_headings.get('our_approach', 'Our Approach') if section_headings else 'Our Approach'

        # Получаем переведенные блоки контента
        approach_blocks = self.generate_theme_content_via_api(theme, "our_approach_blocks", 3)

        # Fallback если API не вернул результат
        if not approach_blocks or not isinstance(approach_blocks, list) or len(approach_blocks) < 3:
            approach_blocks_fallback = [
                {
                    "title": "Client-Centered Solutions",
                    "description": "We prioritize understanding your unique challenges and goals to deliver customized solutions that drive real results."
                },
                {
                    "title": "Innovation & Excellence",
                    "description": "We combine cutting-edge techniques with industry best practices to ensure superior outcomes."
                },
                {
                    "title": "Transparent Communication",
                    "description": "Regular updates and open dialogue ensure you're always informed about your project's progress."
                }
            ]
            approach_blocks = self.get_localized_fallback('our_approach_blocks', approach_blocks_fallback)

        return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto">
                <h2 class="text-4xl font-bold text-center mb-16">{our_approach_heading}</h2>
                <div class="space-y-8">
                    <div class="flex gap-6">
                        <div class="flex-shrink-0 w-16 h-16 bg-{primary} rounded-lg flex items-center justify-center text-white text-2xl font-bold">1</div>
                        <div>
                            <h3 class="text-2xl font-bold mb-3">{approach_blocks[0]['title']}</h3>
                            <p class="text-gray-600 text-lg">{approach_blocks[0]['description']}</p>
                        </div>
                    </div>
                    <div class="flex gap-6">
                        <div class="flex-shrink-0 w-16 h-16 bg-{primary} rounded-lg flex items-center justify-center text-white text-2xl font-bold">2</div>
                        <div>
                            <h3 class="text-2xl font-bold mb-3">{approach_blocks[1]['title']}</h3>
                            <p class="text-gray-600 text-lg">{approach_blocks[1]['description']}</p>
                        </div>
                    </div>
                    <div class="flex gap-6">
                        <div class="flex-shrink-0 w-16 h-16 bg-{primary} rounded-lg flex items-center justify-center text-white text-2xl font-bold">3</div>
                        <div>
                            <h3 class="text-2xl font-bold mb-3">{approach_blocks[2]['title']}</h3>
                            <p class="text-gray-600 text-lg">{approach_blocks[2]['description']}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>"""

    def generate_our_locations_section(self, country, primary, hover):
        """Генерирует секцию Our Locations с городами из указанной страны"""
        country_lower = country.lower()

        # Данные по странам для локаций
        country_locations = {
            'netherlands': [
                {'city': 'Amsterdam', 'description': 'Our headquarters in the heart of Netherlands, serving clients with expertise and innovation.'},
                {'city': 'Rotterdam', 'description': 'Major port city office providing comprehensive solutions for business growth.'},
                {'city': 'Utrecht', 'description': 'Central Netherlands hub delivering excellence in service and support.'},
                {'city': 'The Hague', 'description': 'Government city office specializing in corporate and institutional services.'},
                {'city': 'Eindhoven', 'description': 'Technology hub bringing cutting-edge innovation to our clients.'},
                {'city': 'Groningen', 'description': 'Northern office serving the region with dedication and professionalism.'}
            ],
            'usa': [
                {'city': 'New York', 'description': 'Our headquarters serving the East Coast market with dedicated professionals.'},
                {'city': 'San Francisco', 'description': 'West Coast hub bringing innovation and technology expertise to your doorstep.'},
                {'city': 'Chicago', 'description': 'Central location serving clients across the Midwest with excellence.'},
                {'city': 'Miami', 'description': 'Southern operations center providing exceptional service to our clients.'},
                {'city': 'Seattle', 'description': 'Pacific Northwest headquarters for innovation and growth initiatives.'},
                {'city': 'Boston', 'description': 'Northeast regional office delivering quality service and expertise.'}
            ],
            'uk': [
                {'city': 'London', 'description': 'Our main UK headquarters in the financial heart of the country.'},
                {'city': 'Manchester', 'description': 'Northern powerhouse office driving business growth and innovation.'},
                {'city': 'Birmingham', 'description': 'Midlands hub serving clients with comprehensive business solutions.'},
                {'city': 'Edinburgh', 'description': 'Scottish office providing exceptional service across the region.'},
                {'city': 'Bristol', 'description': 'Southwest operations center for technology and creative industries.'},
                {'city': 'Leeds', 'description': 'Yorkshire office delivering professional services and expertise.'}
            ],
            'germany': [
                {'city': 'Berlin', 'description': 'Capital city headquarters driving innovation and digital transformation.'},
                {'city': 'Munich', 'description': 'Bavarian office serving clients with precision and excellence.'},
                {'city': 'Frankfurt', 'description': 'Financial hub providing corporate and enterprise solutions.'},
                {'city': 'Hamburg', 'description': 'Northern office specializing in international business services.'},
                {'city': 'Cologne', 'description': 'West German operations center for creative and media industries.'},
                {'city': 'Stuttgart', 'description': 'Southwest office delivering engineering and technology expertise.'}
            ],
            'france': [
                {'city': 'Paris', 'description': 'Capital headquarters serving French and European markets with elegance.'},
                {'city': 'Lyon', 'description': 'Second city office providing comprehensive business solutions.'},
                {'city': 'Marseille', 'description': 'Mediterranean hub for international trade and commerce.'},
                {'city': 'Toulouse', 'description': 'Aerospace city office specializing in technology and innovation.'},
                {'city': 'Nice', 'description': 'Côte d\'Azur office serving the French Riviera market.'},
                {'city': 'Bordeaux', 'description': 'Southwest regional office delivering professional excellence.'}
            ]
        }

        # Выбираем города для страны или используем USA по умолчанию
        locations = None
        for key in country_locations.keys():
            if key in country_lower:
                locations = country_locations[key]
                break

        if not locations:
            locations = country_locations['usa']

        # Генерируем HTML с 6 локациями
        _location_contact_btn = ('' if self.site_type == 'landing' else
                                 f'<a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-2 rounded-lg font-semibold transition">Contact</a>')
        location_cards = ""
        for i, location in enumerate(locations, 1):
            location_cards += f"""
                    <div class="w-full md:w-1/3 flex-shrink-0 px-3">
                        <div class="bg-white rounded-xl p-6 shadow-md hover:shadow-xl transition-shadow">
                            <img src="images/location{i}.jpg" alt="{location['city']}" class="w-full h-40 object-cover rounded-lg mb-4">
                            <h4 class="text-xl font-bold mb-2">{location['city']} Office</h4>
                            <p class="text-gray-600 mb-4">{location['description']}</p>
                            {_location_contact_btn}
                        </div>
                    </div>
"""

        return f"""
    <section class="py-20 pb-28 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="flex justify-between items-center mb-12">
                <h2 class="text-4xl font-bold">Our Locations</h2>
                <div class="flex gap-4">
                    <button id="locations-prev" class="w-10 h-10 bg-{primary} text-white rounded-full flex items-center justify-center hover:bg-{hover} transition">
                        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                        </svg>
                    </button>
                    <button id="locations-next" class="w-10 h-10 bg-{primary} text-white rounded-full flex items-center justify-center hover:bg-{hover} transition">
                        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </button>
                </div>
            </div>

            <div class="relative overflow-hidden pb-4">
                <div id="locations-slider" class="flex transition-transform duration-500 ease-in-out">{location_cards}
                </div>
            </div>

            <div class="flex justify-center mt-8 gap-2">
                <button class="location-indicator w-3 h-3 rounded-full bg-{primary} transition" data-index="0"></button>
                <button class="location-indicator w-3 h-3 rounded-full bg-gray-300 transition" data-index="1"></button>
                <button class="location-indicator w-3 h-3 rounded-full bg-gray-300 transition" data-index="2"></button>
                <button class="location-indicator w-3 h-3 rounded-full bg-gray-300 transition" data-index="3"></button>
            </div>
        </div>

        <script>
        (function() {{
            const slider = document.getElementById('locations-slider');
            const prevBtn = document.getElementById('locations-prev');
            const nextBtn = document.getElementById('locations-next');
            const indicators = document.querySelectorAll('.location-indicator');
            let currentIndex = 0;
            const totalCards = 6;
            const cardsPerView = window.innerWidth >= 768 ? 3 : 1;
            const maxIndex = totalCards - cardsPerView;

            function updateSlider() {{
                const offset = -(currentIndex * (100 / cardsPerView));
                slider.style.transform = `translateX(${{offset}}%)`;

                indicators.forEach((indicator, idx) => {{
                    if (idx === currentIndex) {{
                        indicator.classList.remove('bg-gray-300');
                        indicator.classList.add('bg-{primary}');
                    }} else {{
                        indicator.classList.remove('bg-{primary}');
                        indicator.classList.add('bg-gray-300');
                    }}
                }});
            }}

            prevBtn.addEventListener('click', () => {{
                currentIndex = Math.max(0, currentIndex - 1);
                updateSlider();
            }});

            nextBtn.addEventListener('click', () => {{
                currentIndex = Math.min(maxIndex, currentIndex + 1);
                updateSlider();
            }});

            indicators.forEach((indicator, idx) => {{
                indicator.addEventListener('click', () => {{
                    currentIndex = idx;
                    updateSlider();
                }});
            }});
        }})();
        </script>
    </section>"""

    def generate_color_scheme(self):
        """Генерация уникальной цветовой схемы для сайта"""
        color_schemes = [
            {
                'primary': 'blue-600',
                'secondary': 'indigo-600',
                'accent': 'cyan-500',
                'hover': 'blue-700',
                'bg_light': 'blue-50',
                'bg_dark': 'blue-100'
            },
            {
                'primary': 'purple-600',
                'secondary': 'pink-600',
                'accent': 'purple-400',
                'hover': 'purple-700',
                'bg_light': 'purple-50',
                'bg_dark': 'purple-100'
            },
            {
                'primary': 'emerald-600',
                'secondary': 'teal-600',
                'accent': 'green-500',
                'hover': 'emerald-700',
                'bg_light': 'emerald-50',
                'bg_dark': 'emerald-100'
            },
            {
                'primary': 'orange-600',
                'secondary': 'amber-600',
                'accent': 'yellow-500',
                'hover': 'orange-700',
                'bg_light': 'orange-50',
                'bg_dark': 'orange-100'
            },
            {
                'primary': 'rose-600',
                'secondary': 'red-600',
                'accent': 'pink-500',
                'hover': 'rose-700',
                'bg_light': 'rose-50',
                'bg_dark': 'rose-100'
            },
            {
                'primary': 'sky-600',
                'secondary': 'blue-600',
                'accent': 'cyan-400',
                'hover': 'sky-700',
                'bg_light': 'sky-50',
                'bg_dark': 'sky-100'
            },
            {
                'primary': 'violet-600',
                'secondary': 'purple-600',
                'accent': 'indigo-500',
                'hover': 'violet-700',
                'bg_light': 'violet-50',
                'bg_dark': 'violet-100'
            },
            {
                'primary': 'fuchsia-600',
                'secondary': 'pink-600',
                'accent': 'purple-500',
                'hover': 'fuchsia-700',
                'bg_light': 'fuchsia-50',
                'bg_dark': 'fuchsia-100'
            }
        ]
        
        return random.choice(color_schemes)
    
    def generate_header_layout(self):
        """Генерация случайного варианта расположения header"""
        layouts = [
            'centered',  # Логотип по центру, меню по бокам
            'left-aligned',  # Логотип слева, меню справа
            'split',  # Логотип слева, меню по центру, CTA справа
            'minimal',  # Минималистичный header
            'bold'  # Жирный header с большим логотипом
        ]
        return random.choice(layouts)
    
    def generate_footer_layout(self):
        """Генерация случайного варианта расположения footer"""
        layouts = [
            'columns-3',  # 3 колонки
            'columns-4',  # 4 колонки
            'centered',  # Центрированный
            'minimal',  # Минимальный
            'split'  # Разделенный (info слева, links справа)
        ]
        return random.choice(layouts)
    
    def generate_section_variations(self):
        """Генерация случайных вариантов секций для сайта"""
        all_sections = [
            'hero_full_screen',
            'hero_split',
            'hero_minimal',
            'features_grid_3',
            'features_grid_4',
            'features_cards',
            'services_carousel',
            'services_tabs',
            'services_accordion',
            'testimonials_slider',
            'testimonials_grid',
            'testimonials_masonry',
            'cta_banner',
            'cta_modal',
            'cta_sidebar',
            'stats_counter',
            'stats_charts',
            'team_grid',
            'team_list',
            'portfolio_masonry',
            'portfolio_grid',
            'blog_cards',
            'blog_list',
            'pricing_tables',
            'pricing_cards',
            'faq_accordion',
            'faq_tabs',
            'contact_form_inline',
            'contact_form_modal',
            'newsletter_popup',
            'newsletter_footer'
        ]
        
        # Выбираем 5-8 случайных секций
        num_sections = random.randint(5, 8)
        return random.sample(all_sections, num_sections)
    
    def generate_image_via_bytedance(self, prompt, filename, output_dir, allow_text=False):
        """Генерация изображения через ByteDance Ark SDK"""
        # Убрали вывод отсюда - он делается в generate_images_for_site

        try:
            # Формируем промпт с условным добавлением ограничения на текст
            text_restriction = "" if allow_text else ", no text, no words, no letters"
            full_prompt = f"{prompt}, professional photography, high quality, photorealistic, 4K{text_restriction}"

            # Генерация изображения через Ark API
            imagesResponse = self.ark_client.images.generate(
                model="seedream-4-0-250828",
                prompt=full_prompt,
                response_format="url",
                size="2K",
                stream=True,
                watermark=False
            )
            
            image_url = None
            for event in imagesResponse:
                if event is None:
                    continue
                    
                if event.type == "image_generation.partial_failed":
                    if event.error is not None and hasattr(event.error, 'code') and event.error.code == "InternalServiceError":
                        return None

                elif event.type == "image_generation.partial_succeeded":
                    if event.error is None and event.url:
                        image_url = event.url

                elif event.type == "image_generation.completed":
                    if event.error is None:
                        break

            # Скачивание изображения
            if image_url:
                img_response = requests.get(image_url, timeout=60)
                img_response.raise_for_status()

                image_path = os.path.join(output_dir, filename)
                with open(image_path, 'wb') as f:
                    f.write(img_response.content)

                return filename
            else:
                return None

        except Exception as e:
            return None
    
    def generate_placeholder_image(self, filename, output_dir, description=""):
        """Создание placeholder изображения"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            if 'hero' in filename:
                width, height = 1920, 1080
            elif 'service' in filename or 'gallery' in filename:
                width, height = 600, 600
            else:
                width, height = 1024, 768
            
            img = Image.new('RGB', (width, height))
            draw = ImageDraw.Draw(img)
            
            theme = self.blueprint.get('theme', '').lower()
            
            if any(word in theme for word in ['it', 'tech', 'software', 'digital', 'education']):
                colors = [(59, 130, 246), (139, 92, 246), (16, 185, 129), (34, 211, 238), (249, 115, 22)]
            else:
                colors = [(74, 144, 226), (80, 227, 194), (245, 158, 11), (239, 68, 68), (168, 85, 247)]
            
            color1, color2 = random.sample(colors, 2)
            
            for y in range(height):
                ratio = y / height
                r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            try:
                font_size = 60 if width > 1000 else 40
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
            text = filename.replace('.jpg', '').replace('_', ' ').upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) / 2
            y = (height - text_height) / 2
            draw.text((x+2, y+2), text, fill=(0, 0, 0, 128), font=font)
            draw.text((x, y), text, fill=(255, 255, 255), font=font)
            
            image_path = os.path.join(output_dir, filename)
            img.save(image_path, 'JPEG', quality=85)
            
            return filename
            
        except Exception as e:
            print(f"⚠️  Ошибка placeholder {filename}: {e}")
            # Minimal 1x1 JPEG
            minimal_jpeg = base64.b64decode(
                '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBwcG'
                'BwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwMDAwM'
                'DAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCAABAAEDASIA'
                'AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEB'
                'AQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8='
            )
            image_path = os.path.join(output_dir, filename)
            with open(image_path, 'wb') as f:
                f.write(minimal_jpeg)
            return filename
    
    def generate_images_for_site(self, output_dir, num_images=24):
        """Генерация изображений для сайта в папке images/ с приоритетной генерацией"""
        # Создаем папку images (очищаем если существует)
        images_dir = os.path.join(output_dir, 'images')
        if os.path.exists(images_dir):
            import shutil
            shutil.rmtree(images_dir)
        os.makedirs(images_dir, exist_ok=True)

        theme = self.blueprint.get('theme', 'business')
        site_name = self.blueprint.get('site_name', 'Company')
        country = self.blueprint.get('country', 'USA')

        # Создаем детальные контекстные промпты в зависимости от ТЕМЫ и СТРАНЫ
        theme_lower = theme.lower()
        country_lower = country.lower()

        # Определяем, разрешены ли outdoor сцены с вывесками для данного типа бизнеса
        # Для магазинов, ресторанов, кафе, салонов и других физических локаций разрешаем показывать здание снаружи
        allow_outdoor_storefront = any(word in theme_lower for word in [
            'furniture', 'restaurant', 'cafe', 'coffee', 'food', 'shop', 'store', 'retail',
            'beauty', 'salon', 'spa', 'boutique', 'bakery', 'bar', 'pub', 'hotel',
            'gym', 'fitness', 'studio', 'gallery', 'showroom'
        ])

        # Определяем контекст работы в зависимости от темы
        work_context = ""
        work_setting = ""

        if 'travel' in theme_lower or 'tour' in theme_lower or 'voyage' in theme_lower or 'tourism' in theme_lower:
            # Travel/Tourism - красивые виды, достопримечательности, путешествия
            work_context = "scenic destinations, beautiful landscapes, famous landmarks, tourist attractions, cultural sites, natural wonders, beaches, mountains, historical monuments"
            work_setting = "breathtaking travel destinations, stunning natural scenery, iconic landmarks, picturesque locations, outdoor landscapes, beautiful vistas, tourist attractions, world-famous sites, exotic locations"
        elif 'consulting' in theme_lower or 'it' in theme_lower or 'tech' in theme_lower or 'software' in theme_lower:
            # IT/Tech Consulting - офисная среда
            work_context = "professional office environment, business casual attire (shirts and trousers), people working at computers and laptops"
            work_setting = "modern office interior, desk with computer monitors, meeting rooms, presentation screens with charts and graphs (NO text on charts)"
        elif 'legal' in theme_lower or 'law' in theme_lower or 'attorney' in theme_lower:
            # Legal - офисная среда, более формально
            work_context = "professional law office environment, business formal attire, working with documents and laptops"
            work_setting = "elegant office interior, bookshelves with legal books, meeting rooms, professional workspace"
        elif 'furniture' in theme_lower or 'interior' in theme_lower or 'design' in theme_lower:
            # Furniture Store - магазин мебели (ONLY behind glass or inside, NO outdoor furniture)
            work_context = "inside furniture showroom, customers sitting on sofas and chairs, testing furniture, STRICTLY NO outdoor furniture"
            work_setting = "furniture store interior, display of sofas, chairs, tables, modern furniture arrangements, showroom atmosphere. Furniture ONLY behind glass windows or inside the store, NO furniture on streets or outdoors"
        elif 'restaurant' in theme_lower or 'food' in theme_lower or 'cafe' in theme_lower:
            # Restaurant/Cafe - интерьер заведения
            work_context = "restaurant or cafe interior, staff and customers, dining atmosphere"
            work_setting = "restaurant interior, tables with food, kitchen, welcoming atmosphere"
        elif 'medical' in theme_lower or 'health' in theme_lower or 'clinic' in theme_lower:
            # Medical - медицинские помещения
            work_context = "medical office or clinic interior, healthcare professionals in medical attire"
            work_setting = "clean medical facility interior, examination rooms, modern medical equipment"
        else:
            # General business - офисная среда
            work_context = "professional office environment, business attire, workplace interaction"
            work_setting = "modern office interior, professional workspace, meeting areas"

        # Определяем географический и этнический контекст на основе СТРАНЫ
        location_context = ""
        ethnicity_context = ""

        # Список европейских стран (только европеоиды, NO ASIAN appearance)
        european_countries = [
            # English names
            'netherlands', 'dutch', 'holland', 'europe', 'european', 'uk', 'britain', 'united kingdom',
            'germany', 'france', 'italy', 'spain', 'albania', 'andorra', 'armenia', 'austria',
            'azerbaijan', 'belarus', 'belgium', 'bosnia', 'herzegovina', 'bulgaria', 'hungary',
            'venezuela', 'greece', 'georgia', 'denmark', 'estonia', 'cyprus', 'latvia',
            'liechtenstein', 'lithuania', 'luxembourg', 'malta', 'moldova', 'monaco', 'montenegro',
            'norway', 'poland', 'portugal', 'macedonia', 'romania', 'russia', 'san marino',
            'serbia', 'slovakia', 'slovenia', 'turkey', 'ukraine', 'finland', 'croatia',
            'czech', 'switzerland', 'sweden',
            # Russian names (Cyrillic)
            'албания', 'андорра', 'армения', 'австрия', 'азербайджан', 'беларусь', 'бельгия',
            'босния', 'герцеговина', 'болгария', 'великобритания', 'венгрия', 'венесуэла',
            'германия', 'греция', 'грузия', 'дания', 'эстония', 'испания', 'италия', 'кипр',
            'латвия', 'лихтенштейн', 'литва', 'люксембург', 'мальта', 'молдавия', 'молдова',
            'монако', 'черногория', 'нидерланды', 'норвегия', 'польша', 'португалия',
            'македония', 'румыния', 'россия', 'сан-марино', 'сербия', 'словакия', 'словения',
            'турция', 'украина', 'финляндия', 'франция', 'хорватия', 'чехия', 'швейцария', 'швеция'
        ]

        if any(word in country_lower for word in ['netherlands', 'dutch', 'holland', 'нидерланды']):
            location_context = "in the Netherlands, Dutch architecture, windmills, canals, tulip fields, traditional Dutch buildings, European countryside"
            ethnicity_context = "ONLY European Caucasian people, Dutch ethnicity, white skin, Northern European features. STRICTLY NO Asian, NO East Asian, NO Oriental people whatsoever"
        elif any(word in country_lower for word in european_countries):
            location_context = "in Europe, European cities, historic architecture, European landmarks"
            ethnicity_context = "ONLY European Caucasian people, white skin, diverse European ethnicities. STRICTLY NO Asian, NO East Asian, NO Oriental people whatsoever"
        elif any(word in country_lower for word in ['asia', 'asian', 'japan', 'china', 'singapore', 'korea', 'thailand', 'азия']):
            location_context = "in Asia, Asian cities, Asian architecture"
            ethnicity_context = "Asian people, East Asian ethnicity"
        elif any(word in country_lower for word in ['america', 'usa', 'united states', 'америка', 'сша']):
            location_context = "in America, American cities, modern American architecture"
            ethnicity_context = "diverse American people, multicultural"
        else:
            # Нейтральный контекст
            location_context = "in a modern professional setting"
            ethnicity_context = "diverse people"

        # ПРИОРИТЕТНЫЙ СПИСОК ИЗОБРАЖЕНИЙ
        # Минимум 10 ОБЯЗАТЕЛЬНЫХ: hero(1) + services(3) + blog(3) + gallery(3)
        # Blog: 3 или 6 в зависимости от self.num_blog_articles
        # Company: 4 опциональных для Home страницы (генерируются если num_images > 10)

        # Начинаем со статичных обязательных изображений
        images_to_generate = []

        # PRIORITY 1: Hero (обязательно - 1 шт)
        if allow_outdoor_storefront:
            # Для магазинов/ресторанов - показываем здание снаружи с вывеской
            # Для мебельных магазинов - мебель ТОЛЬКО за стеклом или внутри
            if 'furniture' in theme_lower:
                hero_prompt = f"Professional wide banner photograph of {theme} building exterior. Beautiful storefront facade with large glass windows displaying furniture inside, attractive entrance, business sign with text '{site_name}' clearly visible on the sign. Furniture visible ONLY behind glass windows or inside the store, STRICTLY NO furniture on streets or outdoors. Clean modern architecture, inviting atmosphere, natural daylight, high quality, photorealistic, 8k resolution. CRITICAL: Pure photograph only, NO website headers, NO navigation bars, NO UI elements, NO overlaid text."
            else:
                hero_prompt = f"Professional wide banner photograph of {theme} building exterior. Beautiful storefront facade, attractive entrance, business sign with text '{site_name}' clearly visible on the sign. Clean modern architecture, inviting atmosphere, natural daylight, high quality, photorealistic, 8k resolution. Street view, welcoming commercial exterior. CRITICAL: Pure photograph only, NO website headers, NO navigation bars, NO UI elements, NO overlaid text."
            hero_allow_text = True
        else:
            # Для остальных - интерьер без текста, для Travel - красивые виды
            if 'travel' in theme_lower or 'tour' in theme_lower or 'voyage' in theme_lower or 'tourism' in theme_lower:
                # Для Travel: красивое изображение места назначения с человеком
                hero_prompt = f"Professional wide banner photograph for {theme} website. Beautiful travel destination scene: stunning beach with turquoise water, mountains in background, modern resort buildings along the coast, sunny day with clear blue sky. {ethnicity_context} person relaxing in foreground (sitting at a cafe table or terrace), enjoying the view, natural lifestyle photography. Clean composition, natural lighting, high quality, photorealistic, 8k resolution. CRITICAL: Pure photograph only, NO website headers, NO navigation bars, NO UI elements, NO text overlays, just a beautiful travel scene."
            else:
                hero_prompt = f"Professional wide banner photograph for {theme} website. {work_setting}. {work_context}. Clean composition, natural lighting, high quality, photorealistic, 8k resolution. {ethnicity_context} if people are visible. STRICTLY NO outdoor scenes, NO streets, NO city exteriors. Interior setting only. CRITICAL: Pure photograph only, NO website headers, NO navigation bars, NO UI elements, NO text overlays."
            hero_allow_text = False

        images_to_generate.append({
            'filename': 'hero.jpg',
            'priority': 'required',
            'prompt': hero_prompt,
            'allow_text': hero_allow_text
        })
        # PRIORITY 2: Services (обязательно - 3 шт)
        # Service images always show professionals in business suits in office environment
        service1_prompt = f"Professional office photograph showing business professionals in formal business suits and dress shirts working together in modern office environment. {ethnicity_context}. Conference room or office meeting space, laptops and documents on table, collaborative discussion, natural office lighting, photorealistic, high quality. STRICTLY interior office setting only."

        images_to_generate.extend([
            {
                'filename': 'service1.jpg',
                'priority': 'required',
                'prompt': service1_prompt,
                'allow_text': False
            },
            {
                'filename': 'service2.jpg',
                'priority': 'required',
                'prompt': f"Professional business photograph showing diverse team of professionals in formal business suits and dress shirts in modern office. {ethnicity_context} collaborating around desk with laptops, professional office interior, natural interaction, bright office lighting, photorealistic. STRICTLY NO outdoor scenes, interior office only.",
                'allow_text': False
            },
            {
                'filename': 'service3.jpg',
                'priority': 'required',
                'prompt': f"High-quality office photograph with business professionals in formal business attire (suits, dress shirts, blazers) working in professional office environment. {ethnicity_context}. Modern office workspace, professional presentation or meeting, confident business people, natural office lighting, photorealistic. STRICTLY interior office setting only.",
                'allow_text': False
            },
        ])

        # PRIORITY 3: Blog (динамически - 3 или 6 шт в зависимости от self.num_blog_articles)
        blog_prompts = [
            f"Engaging blog header photograph related to {theme} topic. {work_setting}. {work_context}. Creative composition, storytelling visual, authentic scene, natural colors, high quality, photorealistic. {ethnicity_context} if people present.",
            f"Inspiring blog featured photograph for {theme} article. {work_setting}. {work_context}. Professional quality, engaging composition, relevant to topic, authentic setting, natural lighting, photorealistic. {ethnicity_context} if people present.",
            f"Informative blog post photograph about {theme}. {work_setting}. {work_context}. Clear visual storytelling, educational value, authentic scene, natural environment, high-quality photography, photorealistic. {ethnicity_context} if people present.",
            f"Unique perspective blog photograph for {theme} content. {work_setting}. {work_context}. Creative angle, interesting composition, authentic moment, natural lighting, professional photography, photorealistic. {ethnicity_context} if people present.",
            f"Compelling blog content photograph representing {theme}. {work_setting}. {work_context}. Strong visual narrative, authentic scene, engaging composition, natural colors, high quality, photorealistic. {ethnicity_context} if people present.",
            f"Professional blog header photograph for {theme} article. {work_setting}. {work_context}. Attractive composition, relevant content, authentic setting, clear subject, natural lighting, photorealistic. {ethnicity_context} if people present."
        ]

        # Добавляем blog изображения в зависимости от количества статей
        for i in range(self.num_blog_articles):
            images_to_generate.append({
                'filename': f'blog{i+1}.jpg',
                'priority': 'required',
                'prompt': blog_prompts[i],
                'allow_text': False
            })

        # PRIORITY 4: Services (service4 обязательный, 5-6 опциональные - для Services страницы)
        images_to_generate.extend([
            {
                'filename': 'service4.jpg',
                'priority': 'required',
                'prompt': f"Professional office photograph with business professionals in formal business suits working in modern office setting. {ethnicity_context}. Executive meeting or presentation, professional business environment, confident professionals, office interior, natural lighting, photorealistic. STRICTLY interior office only.",
                'allow_text': False
            },
            {
                'filename': 'service5.jpg',
                'priority': 'optional',
                'prompt': f"High-quality business photograph showing professionals in business suits and dress shirts in office environment. {ethnicity_context}. Modern office workspace, business people at work, professional atmosphere, office interior with computers and workspace, photorealistic. STRICTLY interior office setting only.",
                'allow_text': False
            },
            {
                'filename': 'service6.jpg',
                'priority': 'optional',
                'prompt': f"Professional business photograph with team in formal business attire (suits, blazers, dress shirts) in office setting. {ethnicity_context}. Professional office environment, collaborative work, modern business interior, confident professionals, photorealistic. STRICTLY interior office only.",
                'allow_text': False
            },
        ])

        # PRIORITY 5: Company (опционально - 7 шт для Home и Company страниц)
        images_to_generate.extend([
            {
                'filename': 'about.jpg',
                'priority': 'required',
                'prompt': f"Professional business photograph showing {theme} company culture. {work_setting}. {ethnicity_context} in natural professional setting, {work_context}, candid moments, warm atmosphere, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            {
                'filename': 'mission.jpg',
                'priority': 'optional',
                'prompt': f"Inspiring photograph representing company mission and vision for {theme} business. {work_setting}. Forward-thinking perspective, aspirational imagery, professional setting, authentic motivation, natural lighting, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            {
                'filename': 'values.jpg',
                'priority': 'optional',
                'prompt': f"Professional photograph showcasing company values and culture for {theme}. {work_setting}. {ethnicity_context} demonstrating teamwork and collaboration, {work_context}, authentic workplace values, positive atmosphere, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            {
                'filename': 'team.jpg',
                'priority': 'optional',
                'prompt': f"Professional team photograph for {theme} company. {work_setting}. {ethnicity_context} in business setting, {work_context}, diverse professional team, confident and approachable, natural group composition, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
        ])

        # Генерируем team изображения на основе gender из API с контекстом "home_images" для уникальных имен
        team_members = self.generate_theme_content_via_api(theme, "team_members", 3, page_context="home_images")
        if not team_members or not isinstance(team_members, list) or len(team_members) < 3:
            # Fallback к дефолтным значениям если API не вернул результат
            team_members = [
                {'gender': 'male'},
                {'gender': 'female'},
                {'gender': 'female'}
            ]

        # Генерируем изображения для каждого члена команды на основе их gender
        # Добавляем уникальные характеристики для каждого члена, чтобы они визуально различались
        unique_characteristics = [
            {
                'age': 'young professional in late 20s',
                'style': 'modern slim-fit business suit with crisp white shirt',
                'hair': 'short neat professional hairstyle',
                'pose': 'centered composition, facing camera directly, serious professional expression',
                'extras': 'clean-shaven or minimal facial hair, professional demeanor'
            },
            {
                'age': 'experienced professional in mid 30s',
                'style': 'classic business blazer with professional blouse',
                'hair': 'medium length professional hairstyle',
                'pose': 'perfectly centered in frame, facing camera directly, slight professional smile',
                'extras': 'confident professional appearance'
            },
            {
                'age': 'seasoned professional in early 40s',
                'style': 'executive business attire with sophisticated styling',
                'hair': 'elegant professional hairstyle',
                'pose': 'centered straight-on composition, facing camera, serious expression',
                'extras': 'authoritative and experienced demeanor'
            }
        ]

        for i, member in enumerate(team_members[:3], 1):
            gender = member.get('gender', 'male' if i == 1 else 'female').lower()
            chars = unique_characteristics[i-1]

            if gender == 'male' or gender == 'м' or gender == 'мужской':
                gender_desc = f"{ethnicity_context} male"
                gender_critical = "Male person only"
                clothing_detail = chars['style']
                hair_detail = f"{chars['hair']}, {chars['extras']}"
            else:
                gender_desc = f"{ethnicity_context} female"
                gender_critical = "Female person only"
                clothing_detail = chars['style']
                hair_detail = chars['hair']

            images_to_generate.append({
                'filename': f'team{i}.jpg',
                'priority': 'required',
                'prompt': f"Professional corporate headshot portrait of a {gender_desc} business professional, {chars['age']}, wearing {clothing_detail}. {hair_detail}. Pure white background, neutral white studio lighting, {chars['pose']}, {chars['extras']}, photorealistic, high quality corporate photography. CRITICAL: {gender_critical}, perfectly centered in frame, clean white background, neutral/cool lighting ONLY, NO warm lighting, NO orange tones, NO yellow tones, person must be centered and facing camera directly, no other elements, business attire, UNIQUE person #{i} - must look distinctly different from other team members.",
                'allow_text': False
            })

        images_to_generate.extend([
        ])

        # Benefits image для секции image_with_benefits (обязательно для travel тематики)
        if 'travel' in theme_lower or 'tour' in theme_lower or 'voyage' in theme_lower or 'tourism' in theme_lower:
            images_to_generate.append({
                'filename': 'benefits.jpg',
                'priority': 'required',
                'prompt': f"Professional travel photograph showing beautiful destination scene. Stunning natural landscape: pristine beach with turquoise ocean water, tropical paradise, palm trees, white sand beach, crystal clear water, scenic coastal view. {ethnicity_context} travelers enjoying the destination in background, relaxing beach atmosphere, natural daylight, professional travel photography, photorealistic, 8k quality. CRITICAL: Pure travel destination photograph, beautiful scenery, paradise location.",
                'allow_text': False
            })

            # Testimonials image для секции testimonials_with_image (опционально, для travel тематики)
            images_to_generate.append({
                'filename': 'testimonials.jpg',
                'priority': 'optional',
                'prompt': f"Professional travel photograph showing happy tourists at a famous landmark. {ethnicity_context} travelers posing in front of iconic tourist attraction (historic monument, famous building, scenic viewpoint). Tourists wearing casual vacation clothes, smiling and enjoying their trip, landmark clearly visible in background, sunny day, vibrant atmosphere, authentic travel moment, natural lighting, professional photography, photorealistic, 8k quality. CRITICAL: Focus on tourists with landmark backdrop, genuine vacation atmosphere.",
                'allow_text': False
            })

        # PRIORITY 6: Gallery (обязательно - 3 шт)
        images_to_generate.extend([
            {
                'filename': 'gallery1.jpg',
                'priority': 'required',
                'prompt': f"Showcase photograph highlighting {theme} work. {work_setting}. {work_context}. Portfolio quality, interesting composition, professional execution, authentic project, natural lighting, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            {
                'filename': 'gallery2.jpg',
                'priority': 'required',
                'prompt': f"Professional portfolio photograph of {theme} project. {work_setting}. {work_context}. Different perspective, quality craftsmanship, authentic work, detailed shot, natural light, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            {
                'filename': 'gallery3.jpg',
                'priority': 'required',
                'prompt': f"Quality showcase photograph for {theme} services. {work_setting}. {work_context}. Professional presentation, real project example, clean composition, authentic work, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            # PRIORITY 6.5: Workspace images for Two Images Right section (обязательно - 2 шт)
            {
                'filename': 'workspace1.jpg',
                'priority': 'required',
                'prompt': f"Modern professional workspace for {theme} business. {work_setting}. Clean organized office environment, contemporary design, professional atmosphere, bright natural lighting, minimal clutter, focus on workspace details, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            {
                'filename': 'workspace2.jpg',
                'priority': 'required',
                'prompt': f"Collaborative work environment for {theme} company. {work_setting}. Team collaboration space, modern office interior, professional setting, dynamic composition, natural light, authentic business environment, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            # PRIORITY 7: Gallery 4 (1 шт)
            {
                'filename': 'gallery4.jpg',
                'priority': 'optional',
                'prompt': f"Professional portfolio piece for {theme} company. {work_setting}. {work_context}. High-quality craftsmanship, finished project, authentic work, professional photography, photorealistic. {'Interior or exterior setting.' if allow_outdoor_storefront else 'STRICTLY NO outdoor scenes. Interior only.'}",
                'allow_text': False
            },
            # PRIORITY 8: Locations (6 шт)
            {
                'filename': 'location1.jpg',
                'priority': 'optional',
                'prompt': f"Beautiful cityscape photograph of a major city {location_context}. Iconic architecture, vibrant urban landscape, famous landmarks, clear blue sky, natural daylight, professional travel photography, photorealistic, 8k quality.",
                'allow_text': False
            },
            {
                'filename': 'location2.jpg',
                'priority': 'optional',
                'prompt': f"Stunning city view photograph {location_context}. Historic district, charming streets, cultural landmarks, authentic urban environment, golden hour lighting, professional cityscape photography, photorealistic.",
                'allow_text': False
            },
            {
                'filename': 'location3.jpg',
                'priority': 'optional',
                'prompt': f"Professional city photograph {location_context}. Modern business district, contemporary architecture, dynamic city life, clean composition, bright daylight, high-quality urban photography, photorealistic.",
                'allow_text': False
            },
            {
                'filename': 'location4.jpg',
                'priority': 'optional',
                'prompt': f"Attractive cityscape showing urban beauty {location_context}. Waterfront view, riverside or canal scene, scenic city landscape, natural lighting, professional travel photography, photorealistic, detailed.",
                'allow_text': False
            },
            {
                'filename': 'location5.jpg',
                'priority': 'optional',
                'prompt': f"Impressive city photograph {location_context}. Cultural center, historic buildings, city square or plaza, authentic urban setting, clear weather, professional cityscape photography, photorealistic.",
                'allow_text': False
            },
            {
                'filename': 'location6.jpg',
                'priority': 'optional',
                'prompt': f"High-quality urban photograph {location_context}. Residential and business areas, typical city architecture, local character, natural daylight, professional photography, photorealistic, vibrant colors.",
                'allow_text': False
            }
        ])

        self.generated_images = []

        # Разделяем изображения по приоритетам
        required_images = [img for img in images_to_generate if img.get('priority') == 'required']
        optional_images = [img for img in images_to_generate if img.get('priority') == 'optional']

        print(f"\n🖼️  Генерация изображений: {num_images} шт.")
        print(f"   📌 Обязательные: {len(required_images)} (hero + 4 services + {self.num_blog_articles} blog + about + 3 gallery + 3 team + benefits для travel)")
        print(f"   ⭐ Дополнительные: {len(optional_images)} (3 company, gallery4, 6 locations, 2 services, testimonials для travel)")

        generated_count = 0

        # ЭТАП 1: Генерируем ВСЕ обязательные изображения (без ограничения num_images)
        print(f"\n   🔥 Этап 1/2: Генерация обязательных изображений ({len(required_images)} шт)...")
        for img_data in required_images:
            print(f"      → {img_data['filename']}...", end=' ')

            # Сначала пробуем ByteDance
            result = self.generate_image_via_bytedance(
                img_data['prompt'],
                img_data['filename'],
                images_dir,
                allow_text=img_data.get('allow_text', False)
            )

            # Если не получилось, создаем placeholder
            if not result:
                result = self.generate_placeholder_image(
                    img_data['filename'],
                    images_dir,
                    img_data['prompt']
                )

            if result:
                self.generated_images.append(img_data['filename'])
                generated_count += 1
                print(f"✓ ({generated_count})")
            else:
                print("✗ ошибка")

        # ЭТАП 2: Генерируем дополнительные изображения если есть место
        # (num_images может быть больше чем required, тогда добавляем optional)
        remaining = max(0, num_images - generated_count)
        if remaining > 0:
            print(f"\n   ⭐ Этап 2/2: Генерация дополнительных изображений (осталось {remaining})...")
            for img_data in optional_images[:remaining]:
                print(f"      → {img_data['filename']}...", end=' ')

                # Сначала пробуем ByteDance
                result = self.generate_image_via_bytedance(
                    img_data['prompt'],
                    img_data['filename'],
                    images_dir,
                    allow_text=img_data.get('allow_text', False)
                )

                # Если не получилось, создаем placeholder
                if not result:
                    result = self.generate_placeholder_image(
                        img_data['filename'],
                        images_dir,
                        img_data['prompt']
                    )

                if result:
                    self.generated_images.append(img_data['filename'])
                    generated_count += 1
                    print(f"✓ ({generated_count}/{num_images})")
                else:
                    print("✗ ошибка")

        print(f"\n   ✅ Сгенерировано: {generated_count} изображений")
        print(f"      Успешные: {', '.join(self.generated_images)}")

    def _has_image(self, filename):
        """Проверяет наличие сгенерированного изображения"""
        # Убираем префикс images/ если есть
        clean_name = filename.replace('images/', '')
        return clean_name in self.generated_images

    def _img_tag(self, filename, alt_text, css_class):
        """Генерирует тег <img> если изображение существует, иначе возвращает пустую строку"""
        if self._has_image(filename):
            return f'<img src="images/{filename.replace("images/", "")}" alt="{alt_text}" class="{css_class}">'
        return ''

    def _section_with_img(self, filename, html_with_img, html_without_img=''):
        """Возвращает HTML с изображением если оно есть, иначе альтернативный HTML"""
        if self._has_image(filename):
            return html_with_img
        return html_without_img

    def load_database(self, data_dir="data"):
        """Загрузка данных из папки data (работа с любым путем)"""
        import sys

        # Нормализуем путь для Windows/Linux
        data_dir = os.path.normpath(data_dir)
        
        if not os.path.exists(data_dir):
            # Пробуем найти в разных местах
            # Определяем базовую директорию (работает и для .py и для .exe)
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()

            possible_paths = [
                data_dir,
                os.path.join(".", data_dir),
                os.path.join(os.getcwd(), data_dir),
                os.path.join(base_dir, data_dir)
            ]
            
            found = False
            for path in possible_paths:
                if os.path.exists(path):
                    data_dir = path
                    found = True
                    break
            
            if not found:
                print(f"⚠️  Папка {data_dir} не найдена. Создание...")
                os.makedirs(data_dir, exist_ok=True)
                print(f"   Поместите туда ZIP/папки с PHP сайтами или текстовые файлы.")
                return False
        
        all_data = []
        files = os.listdir(data_dir)
        
        if not files:
            print(f"⚠️  Папка {data_dir} пуста")
            return False
        
        print(f"\n📂 Загрузка данных из {data_dir}:")
        
        # Распаковываем ZIP файлы
        for filename in files:
            filepath = os.path.join(data_dir, filename)
            if filename.endswith('.zip') and os.path.isfile(filepath):
                print(f"  📦 Распаковка {filename}...")
                try:
                    extract_dir = os.path.join(data_dir, filename[:-4])
                    if os.path.exists(extract_dir):
                        shutil.rmtree(extract_dir)
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    print(f"    ✓ Распаковано")
                except Exception as e:
                    print(f"    ✗ Ошибка: {e}")
        
        # Обновляем список файлов после распаковки
        files = os.listdir(data_dir)
        
        # Загружаем PHP сайты как шаблоны
        for item in files:
            itempath = os.path.join(data_dir, item)
            if os.path.isdir(itempath):
                print(f"  📁 Анализ {item}/...")
                site_data = self.analyze_php_site(itempath, item)
                if site_data:
                    self.template_sites.append(site_data)
                    print(f"    ✓ Загружен как шаблон")
        
        # Загружаем текстовые файлы
        for filename in files:
            filepath = os.path.join(data_dir, filename)
            if os.path.isfile(filepath) and not filename.endswith('.zip'):
                try:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.txt', '.json', '.csv', '.md', '.html', '.php']:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            all_data.append(f"\n--- {filename} ---\n{content}\n")
                            print(f"  ✓ {filename} ({len(content)} символов)")
                except Exception as e:
                    print(f"  ✗ Ошибка {filename}: {e}")
        
        if all_data:
            self.database_content = "\n".join(all_data)
        
        print(f"\n✓ Загружено: Шаблонов: {len(self.template_sites)}, Данных: {len(self.database_content)} символов")
        return len(self.template_sites) > 0 or len(self.database_content) > 0
    
    def analyze_php_site(self, site_dir, site_name):
        """Анализ PHP сайта и извлечение структуры"""
        site_data = {
            'name': site_name,
            'pages': [],
            'structure': {},
            'has_header': False,
            'has_footer': False
        }
        
        try:
            for root, dirs, files in os.walk(site_dir):
                for file in files:
                    if file.endswith('.php') or file.endswith('.html'):
                        filepath = os.path.join(root, file)
                        rel_path = os.path.relpath(filepath, site_dir)
                        site_data['pages'].append(rel_path)
                        
                        # Проверяем наличие header/footer
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                                if 'header' in content or '<nav' in content:
                                    site_data['has_header'] = True
                                if 'footer' in content:
                                    site_data['has_footer'] = True
                        except:
                            pass
            
            if site_data['pages']:
                return site_data
        except Exception as e:
            print(f"    ⚠️  Ошибка анализа: {e}")
        
        return None
    
    def create_blueprint(self, user_prompt, site_name):
        """Создание Blueprint сайта с улучшенной обработкой"""
        # Улучшенное извлечение темы и страны из промпта
        country = "USA"
        theme = "Business"

        # Ищем явное указание country, theme и language
        country_match = re.search(r'country[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)
        theme_match = re.search(r'theme[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)
        language_match = re.search(r'language[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)

        # Флаг для отслеживания явного указания страны
        country_explicitly_set = False

        if country_match:
            country = country_match.group(1).strip()
            country_explicitly_set = True  # Страна указана явно

        if theme_match:
            theme = theme_match.group(1).strip()
        else:
            # Если theme не указана явно, пробуем определить из контекста промпта
            prompt_lower = user_prompt.lower()

            # Определяем тему по ключевым словам
            if any(word in prompt_lower for word in ['book', 'bookstore', 'library', 'книг', 'книжн']):
                theme = "Bookstore"
            elif any(word in prompt_lower for word in ['restaurant', 'cafe', 'food', 'ресторан', 'кафе']):
                theme = "Restaurant"
            elif any(word in prompt_lower for word in ['hotel', 'accommodation', 'отель', 'гостиниц']):
                theme = "Hotel"
            elif any(word in prompt_lower for word in ['shop', 'store', 'магазин', 'товар']):
                theme = "Shop"
            elif any(word in prompt_lower for word in ['fitness', 'gym', 'sport', 'фитнес', 'спорт']):
                theme = "Fitness"
            elif any(word in prompt_lower for word in ['clinic', 'medical', 'health', 'клиника', 'медицин']):
                theme = "Healthcare"
            elif any(word in prompt_lower for word in ['education', 'school', 'course', 'обучени', 'школ']):
                theme = "Education"
            elif any(word in prompt_lower for word in ['tech', 'it', 'software', 'digital', 'технолог']):
                theme = "IT"
            elif any(word in prompt_lower for word in ['real estate', 'property', 'недвижим']):
                theme = "Real Estate"
            elif any(word in prompt_lower for word in ['travel', 'tour', 'туризм', 'путешеств']):
                theme = "Travel"

        # Ищем страну в тексте ТОЛЬКО если она НЕ была явно указана через "Country:"
        if not country_explicitly_set:
            prompt_lower = user_prompt.lower()
            # Европейские страны
            if any(word in prompt_lower for word in ['albania', 'албания']):
                country = "Albania"
            elif any(word in prompt_lower for word in ['andorra', 'андорра']):
                country = "Andorra"
            elif any(word in prompt_lower for word in ['armenia', 'армения']):
                country = "Armenia"
            elif any(word in prompt_lower for word in ['austria', 'австрия']):
                country = "Austria"
            elif any(word in prompt_lower for word in ['azerbaijan', 'азербайджан']):
                country = "Azerbaijan"
            elif any(word in prompt_lower for word in ['belarus', 'беларусь']):
                country = "Belarus"
            elif any(word in prompt_lower for word in ['belgium', 'бельгия']):
                country = "Belgium"
            elif any(word in prompt_lower for word in ['bosnia', 'herzegovina', 'босния', 'герцеговина']):
                country = "Bosnia and Herzegovina"
            elif any(word in prompt_lower for word in ['bulgaria', 'болгария']):
                country = "Bulgaria"
            elif any(word in prompt_lower for word in ['uk', 'britain', 'united kingdom', 'великобритания']):
                country = "United Kingdom"
            elif any(word in prompt_lower for word in ['hungary', 'венгрия']):
                country = "Hungary"
            elif any(word in prompt_lower for word in ['venezuela', 'венесуэла']):
                country = "Venezuela"
            elif any(word in prompt_lower for word in ['germany', 'german', 'германия']):
                country = "Germany"
            elif any(word in prompt_lower for word in ['greece', 'греция']):
                country = "Greece"
            elif any(word in prompt_lower for word in ['georgia', 'грузия']):
                country = "Georgia"
            elif any(word in prompt_lower for word in ['denmark', 'дания']):
                country = "Denmark"
            elif any(word in prompt_lower for word in ['estonia', 'эстония']):
                country = "Estonia"
            elif any(word in prompt_lower for word in ['spain', 'spanish', 'испания']):
                country = "Spain"
            elif any(word in prompt_lower for word in ['italy', 'italian', 'италия']):
                country = "Italy"
            elif any(word in prompt_lower for word in ['cyprus', 'кипр']):
                country = "Cyprus"
            elif any(word in prompt_lower for word in ['latvia', 'латвия']):
                country = "Latvia"
            elif any(word in prompt_lower for word in ['liechtenstein', 'лихтенштейн']):
                country = "Liechtenstein"
            elif any(word in prompt_lower for word in ['lithuania', 'литва']):
                country = "Lithuania"
            elif any(word in prompt_lower for word in ['luxembourg', 'люксембург']):
                country = "Luxembourg"
            elif any(word in prompt_lower for word in ['malta', 'мальта']):
                country = "Malta"
            elif any(word in prompt_lower for word in ['moldova', 'молдавия', 'молдова']):
                country = "Moldova"
            elif any(word in prompt_lower for word in ['monaco', 'монако']):
                country = "Monaco"
            elif any(word in prompt_lower for word in ['montenegro', 'черногория']):
                country = "Montenegro"
            elif any(word in prompt_lower for word in ['netherlands', 'dutch', 'holland', 'amsterdam', 'нидерланды', 'голландия']):
                country = "Netherlands"
            elif any(word in prompt_lower for word in ['norway', 'норвегия']):
                country = "Norway"
            elif any(word in prompt_lower for word in ['poland', 'польша']):
                country = "Poland"
            elif any(word in prompt_lower for word in ['portugal', 'португалия']):
                country = "Portugal"
            elif any(word in prompt_lower for word in ['macedonia', 'македония']):
                country = "North Macedonia"
            elif any(word in prompt_lower for word in ['romania', 'румыния']):
                country = "Romania"
            elif any(word in prompt_lower for word in ['russia', 'россия']):
                country = "Russia"
            elif any(word in prompt_lower for word in ['san marino', 'сан-марино']):
                country = "San Marino"
            elif any(word in prompt_lower for word in ['serbia', 'сербия']):
                country = "Serbia"
            elif any(word in prompt_lower for word in ['slovakia', 'словакия']):
                country = "Slovakia"
            elif any(word in prompt_lower for word in ['slovenia', 'словения']):
                country = "Slovenia"
            elif any(word in prompt_lower for word in ['turkey', 'турция']):
                country = "Turkey"
            elif any(word in prompt_lower for word in ['ukraine', 'украина']):
                country = "Ukraine"
            elif any(word in prompt_lower for word in ['finland', 'финляндия']):
                country = "Finland"
            elif any(word in prompt_lower for word in ['france', 'french', 'франция']):
                country = "France"
            elif any(word in prompt_lower for word in ['croatia', 'хорватия']):
                country = "Croatia"
            elif any(word in prompt_lower for word in ['czech', 'чехия']):
                country = "Czech Republic"
            elif any(word in prompt_lower for word in ['switzerland', 'швейцария']):
                country = "Switzerland"
            elif any(word in prompt_lower for word in ['sweden', 'швеция']):
                country = "Sweden"
            # Другие страны
            elif 'singapore' in prompt_lower:
                country = "Singapore"
            elif 'usa' in prompt_lower or 'america' in prompt_lower:
                country = "USA"
            elif 'japan' in prompt_lower or 'japanese' in prompt_lower:
                country = "Japan"
            elif 'china' in prompt_lower or 'chinese' in prompt_lower:
                country = "China"

        # Определяем язык: сначала проверяем явное указание, потом определяем по стране
        if language_match:
            language = language_match.group(1).strip()
            print(f"  Явно указан язык: {language}")
        else:
            language = self.get_language_for_country(country)
            print(f"  Язык определен по стране: {language}")

        print(f"  Определена тема: {theme}")
        print(f"  Определена страна: {country}")
        print(f"  Используется название: {site_name}")

        # Генерируем цветовую схему
        color_scheme = self.generate_color_scheme()
        self.primary_color = color_scheme['primary']

        # Генерируем layouts
        header_layout = self.generate_header_layout()
        footer_layout = self.generate_footer_layout()

        # Генерируем секции
        sections = self.generate_section_variations()

        # Создаем простой tagline локально (не через API для надежности)
        taglines = [
            f"Your Trusted {theme} Partner",
            f"Leading {theme} Solutions",
            f"Innovation in {theme}",
            f"Excellence in {theme}",
            f"Professional {theme} Services"
        ]
        tagline = random.choice(taglines)

        # Генерируем контактные данные для страны ОДИН РАЗ и сохраняем в blueprint
        contact_data = self.get_country_contact_data(country)
        print(f"  Контактные данные: {contact_data['phone']}")

        # Создаем финальный blueprint с введенным названием
        self.blueprint = {
            "site_name": site_name,
            "tagline": tagline,
            "theme": theme,
            "country": country,
            "language": language,  # Добавляем язык в blueprint
            "color_scheme": color_scheme,
            "header_layout": header_layout,
            "footer_layout": footer_layout,
            "sections": sections,
            "menu": ["Home", "Services", "Company", "Blog", "Contact"],
            "pages": ["index", "company", "services", "contact", "blog1", "blog2", "blog3", "privacy", "terms", "cookie", "thanks"],
            "contact_data": contact_data  # Сохраняем контактные данные в blueprint
        }

        print(f"✓ Blueprint создан: {site_name}")
        print(f"  Цвета: {color_scheme['primary']} (hover: {color_scheme['hover']})")
        print(f"  Header: {header_layout}, Footer: {footer_layout}")
        print(f"  Секции: {len(sections)}")

        return True
    
    def generate_header_footer(self):
        """Генерация Header и Footer с гарантированным меню и футером"""
        try:
            site_name = self.blueprint.get('site_name', 'Company')
            menu = self.blueprint.get('menu', ['Home', 'Services', 'Company', 'Blog', 'Contact'])
            colors = self.blueprint.get('color_scheme', {})
            header_layout = self.blueprint.get('header_layout', 'left-aligned')
            footer_layout = self.blueprint.get('footer_layout', 'columns-3')
            
            hover_color = colors.get('hover', 'blue-700')
            primary_color = colors.get('primary', 'blue-600')
            theme = self.blueprint.get('theme', 'business')

            # Случайный выбор шрифта (4 варианта)
            font_options = [
                {'name': 'Inter', 'import': '@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap");', 'family': "'Inter', sans-serif"},
                {'name': 'Poppins', 'import': '@import url("https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap");', 'family': "'Poppins', sans-serif"},
                {'name': 'Montserrat', 'import': '@import url("https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap");', 'family': "'Montserrat', sans-serif"},
                {'name': 'Roboto', 'import': '@import url("https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap");', 'family': "'Roboto', sans-serif"}
            ]
            selected_font = random.choice(font_options)
            self.selected_font = selected_font  # Сохраняем для использования в других местах

            # Получаем переводы меню через API
            menu_content = self.generate_theme_content_via_api(theme, "menu_content", 1)

            # Fallback если API не вернул результат
            if not menu_content:
                menu_content_fallback = {
                    'home': 'Home',
                    'company': 'Company',
                    'services': 'Services',
                    'blog': 'Blog',
                    'contact': 'Contact'
                }
                menu_content = self.get_localized_fallback('menu_content', menu_content_fallback)

            # Определяем страницы в зависимости от типа сайта
            if self.site_type == "landing":
                nav_pages = [
                    (menu_content.get('home', 'Home'), 'index.php'),
                    (menu_content.get('contact', 'Contact'), 'contact.php')
                ]
            else:
                nav_pages = [
                    (menu_content.get('home', 'Home'), 'index.php'),
                    (menu_content.get('company', 'Company'), 'company.php'),
                    (menu_content.get('services', 'Services'), 'services.php'),
                    (menu_content.get('blog', 'Blog'), 'blog.php'),
                    (menu_content.get('contact', 'Contact'), 'contact.php')
                ]
            
            # Случайный выбор варианта header (2 варианта)
            header_variant = random.randint(1, 2)
            
            if header_variant == 1:
                # Вариант 1: Меню справа (классический)
                self.header_code = f"""<header class="bg-white shadow-md sticky top-0 z-50">
    <div class="container mx-auto px-6 py-4">
        <div class="flex justify-between items-center">
            <div class="text-2xl font-bold text-{primary_color}">
                {site_name}
            </div>
            
            <nav class="hidden md:flex space-x-8">
                {' '.join([f'<a href="{page[1]}" class="text-gray-700 hover:text-{hover_color} transition-colors">{page[0]}</a>' for page in nav_pages])}
            </nav>
            
            <button id="mobile-menu-btn" class="md:hidden text-gray-700 hover:text-{hover_color}">
                <svg class="w-6 h-6 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
        </div>
        
        <nav id="mobile-menu" class="hidden md:hidden mt-4 pb-4">
            {' '.join([f'<a href="{page[1]}" class="block py-2 text-gray-700 hover:text-{hover_color} transition-colors">{page[0]}</a>' for page in nav_pages])}
        </nav>
    </div>
    
    <script>
        document.getElementById('mobile-menu-btn').addEventListener('click', function() {{
            var menu = document.getElementById('mobile-menu');
            menu.classList.toggle('hidden');
        }});
    </script>
</header>"""
            else:
                # Вариант 2: Меню по центру
                self.header_code = f"""<header class="bg-white shadow-md sticky top-0 z-50">
    <div class="container mx-auto px-6 py-4">
        <div class="flex flex-col items-center">
            <div class="text-2xl font-bold text-{primary_color} mb-4">
                {site_name}
            </div>
            
            <nav class="hidden md:flex space-x-8">
                {' '.join([f'<a href="{page[1]}" class="text-gray-700 hover:text-{hover_color} transition-colors">{page[0]}</a>' for page in nav_pages])}
            </nav>
            
            <button id="mobile-menu-btn" class="md:hidden text-gray-700 hover:text-{hover_color} absolute right-6 top-4">
                <svg class="w-6 h-6 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
        </div>
        
        <nav id="mobile-menu" class="hidden md:hidden mt-4 pb-4 text-center">
            {' '.join([f'<a href="{page[1]}" class="block py-2 text-gray-700 hover:text-{hover_color} transition-colors">{page[0]}</a>' for page in nav_pages])}
        </nav>
    </div>
    
    <script>
        document.getElementById('mobile-menu-btn').addEventListener('click', function() {{
            var menu = document.getElementById('mobile-menu');
            menu.classList.toggle('hidden');
        }});
    </script>
</header>"""
            
            print(f"  ✓ Header создан (вариант {header_variant}/2) с навигацией")

            # Получаем контент footer через API
            footer_content = self.generate_theme_content_via_api(theme, "footer_content", 1)

            # Fallback если API не вернул результат
            if not footer_content:
                footer_content_fallback = {
                    'tagline': f'Your trusted partner in {theme}',
                    'quick_links': 'Quick Links',
                    'legal': 'Legal',
                    'legal_info': 'Legal Information',
                    'all_rights': 'All rights reserved',
                    'privacy_policy': 'Privacy Policy',
                    'terms_of_service': 'Terms of Service',
                    'cookie_policy': 'Cookie Policy'
                }
                footer_content = self.get_localized_fallback('footer_content', footer_content_fallback)

            # ГАРАНТИРОВАННЫЙ FOOTER (всегда создается, даже если API не отвечает)
            # Используем переводы из menu_content и footer_content
            footer_links = [
                (menu_content.get('home', 'Home'), 'index.php'),
                (footer_content.get('privacy_policy', 'Privacy Policy'), 'privacy.php'),
                (footer_content.get('terms_of_service', 'Terms of Service'), 'terms.php'),
                (footer_content.get('cookie_policy', 'Cookie Policy'), 'cookie.php')
            ]

            if self.site_type == "multipage":
                footer_links.insert(1, (menu_content.get('company', 'Company'), 'company.php'))
                footer_links.insert(2, (menu_content.get('services', 'Services'), 'services.php'))
                footer_links.insert(3, (menu_content.get('blog', 'Blog'), 'blog.php'))
                footer_links.insert(4, (menu_content.get('contact', 'Contact'), 'contact.php'))

            tagline = footer_content.get('tagline', f'Your trusted partner in {theme}')
            quick_links_title = footer_content.get('quick_links', 'Quick Links')
            legal_title = footer_content.get('legal', 'Legal')
            legal_info_title = footer_content.get('legal_info', 'Legal Information')
            all_rights_text = footer_content.get('all_rights', 'All rights reserved')

            # Разделяем ссылки на основные страницы и policy страницы (по URL вместо названий)
            policy_urls = ['privacy.php', 'terms.php', 'cookie.php']
            main_links = [link for link in footer_links if link[1] not in policy_urls]
            policy_links = [link for link in footer_links if link[1] in policy_urls]
            
            # Случайный выбор варианта footer (4 варианта - убран вариант 3)
            footer_variant = random.choice([1, 2, 4, 5])  # Пропускаем вариант 3
            
            if footer_variant == 1:
                # Вариант 1: Классический 3-колоночный (название + основные ссылки + policy)
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-12 mt-auto">
    <div class="container mx-auto px-6">
        <div class="grid md:grid-cols-3 gap-8">
            <div>
                <h3 class="text-xl font-bold mb-4">{site_name}</h3>
                <p class="text-gray-400">{tagline}</p>
            </div>

            <div>
                <h4 class="text-lg font-semibold mb-4">{quick_links_title}</h4>
                <ul class="space-y-2">
                    {' '.join([f'<li><a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a></li>' for link in main_links])}
                </ul>
            </div>

            <div>
                <h4 class="text-lg font-semibold mb-4">{legal_title}</h4>
                <ul class="space-y-2">
                    {' '.join([f'<li><a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a></li>' for link in policy_links])}
                </ul>
            </div>
        </div>

        <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 {site_name}. {all_rights_text}.</p>
        </div>
    </div>
</footer>"""
            
            elif footer_variant == 2:
                # Вариант 2: Горизонтальный (ссылки слева, policy справа, название сверху)
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-12 mt-auto">
    <div class="container mx-auto px-6">
        <div class="text-center mb-8">
            <h3 class="text-2xl font-bold">{site_name}</h3>
            <p class="text-gray-400 mt-2">{tagline}</p>
        </div>

        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <nav class="flex flex-wrap gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in main_links])}
            </nav>

            <nav class="flex flex-wrap gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in policy_links])}
            </nav>
        </div>

        <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 {site_name}. {all_rights_text}.</p>
        </div>
    </div>
</footer>"""
            
            elif footer_variant == 4:
                # Вариант 4: 2 колонки (основные ссылки слева вертикально, policy + контакт справа)
                # Получаем контактные данные из blueprint
                contact_data = self.blueprint.get('contact_data', {'phone': '+1 (555) 739-2814', 'address': '456 Business Street'})
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-12 mt-auto">
    <div class="container mx-auto px-6">
        <div class="grid md:grid-cols-2 gap-8">
            <div>
                <h3 class="text-xl font-bold mb-4">{site_name}</h3>
                <p class="text-gray-400 mb-6">{tagline}</p>
                <nav class="flex flex-col space-y-2">
                    {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in main_links])}
                </nav>
            </div>

            <div>
                <h4 class="text-lg font-semibold mb-4">{legal_info_title}</h4>
                <nav class="flex flex-col space-y-2">
                    {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in policy_links])}
                </nav>
                <div class="mt-6">
                    <p class="text-gray-400">Email: {site_name.lower().replace(' ', '')}@gmail.com</p>
                    <p class="text-gray-400">Phone: {contact_data['phone']}</p>
                </div>
            </div>
        </div>

        <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 {site_name}. {all_rights_text}.</p>
        </div>
    </div>
</footer>"""

            else:  # footer_variant == 5
                # Вариант 5: Минималистичный (все в одну строку горизонтально, без названия компании вверху)
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-8 mt-auto">
    <div class="container mx-auto px-6">
        <div class="flex flex-col md:flex-row justify-between items-center gap-6">
            <div class="text-center md:text-left">
                <p class="font-bold text-lg">{site_name}</p>
                <p class="text-gray-400 text-sm">&copy; 2025 {all_rights_text}.</p>
            </div>

            <nav class="flex flex-wrap justify-center gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors text-sm">{link[0]}</a>' for link in main_links])}
            </nav>

            <nav class="flex flex-wrap justify-center gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors text-sm">{link[0]}</a>' for link in policy_links])}
            </nav>
        </div>
    </div>
</footer>"""
            
            footer_variants_map = {1: 1, 2: 2, 4: 3, 5: 4}
            print(f"  ✓ Footer создан (вариант {footer_variants_map.get(footer_variant, footer_variant)}/4) с навигацией (без соц. сетей)")

            # Генерируем Cookie Notice и добавляем к footer
            cookie_notice = self.generate_cookie_notice()
            self.footer_code += cookie_notice
            print(f"  ✓ Cookie Notice добавлен к footer")

            # CSS для header и footer (обязательный footer на всех страницах)
            self.header_footer_css = f"""<script src="https://cdn.tailwindcss.com"></script>
<style>
    {selected_font['import']}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html {{ height: 100%; scroll-behavior: smooth; }}
    body {{
        font-family: {selected_font['family']};
        min-height: 100vh;
        display: flex;
        flex-direction: column;
    }}
    main {{ flex: 1 0 auto; }}
    footer {{ flex-shrink: 0; margin-top: auto; }}
    /* Обеспечиваем footer всегда внизу */
    #root, .page-wrapper {{ min-height: 100vh; display: flex; flex-direction: column; }}

    /* Защита SVG иконок от деформации */
    svg {{
        flex-shrink: 0;
        width: auto;
        height: auto;
        display: inline-block;
        vertical-align: middle;
    }}

    /* Сохранение соотношения сторон для всех SVG */
    svg:not([width]):not([height]) {{
        max-width: 100%;
        max-height: 100%;
    }}
</style>"""

            return True
            
        except Exception as e:
            # Если произошла ЛЮБАЯ ошибка - создаем минимальный, но рабочий header/footer
            print(f"  ⚠️  Ошибка генерации header/footer: {str(e)[:50]}")
            print(f"  🔧 Создание базового header/footer...")
            
            site_name = self.blueprint.get('site_name', 'Company')
            theme = self.blueprint.get('theme', 'business')
            
            # Минимальный header
            self.header_code = f"""<header class="bg-white shadow-md sticky top-0 z-50">
    <div class="container mx-auto px-6 py-4">
        <div class="text-2xl font-bold text-blue-600">{site_name}</div>
    </div>
</header>"""
            
            # Минимальный footer
            self.footer_code = f"""<footer class="bg-gray-900 text-white py-8 mt-auto">
    <div class="container mx-auto px-6 text-center">
        <p class="font-bold text-lg mb-2">{site_name}</p>
        <p class="text-gray-400 text-sm mb-4">Your trusted partner in {theme}.</p>
        <div class="flex flex-wrap justify-center gap-4 text-sm">
            <a href="index.php" class="text-gray-400 hover:text-blue-400">Home</a>
            <a href="company.php" class="text-gray-400 hover:text-blue-400">Company</a>
            <a href="services.php" class="text-gray-400 hover:text-blue-400">Services</a>
            <a href="contact.php" class="text-gray-400 hover:text-blue-400">Contact</a>
            <a href="privacy.php" class="text-gray-400 hover:text-blue-400">Privacy</a>
            <a href="terms.php" class="text-gray-400 hover:text-blue-400">Terms</a>
        </div>
        <p class="text-gray-400 text-sm mt-4">&copy; 2025 {site_name}. All rights reserved.</p>
    </div>
</footer>"""

            # Добавляем Cookie Notice даже в fallback режиме
            cookie_notice = self.generate_cookie_notice()
            self.footer_code += cookie_notice

            # Минимальный CSS (используем Inter по умолчанию при ошибке)
            self.header_footer_css = """<script src="https://cdn.tailwindcss.com"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { height: 100%; }
    body {
        font-family: 'Inter', sans-serif;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
    }
    main { flex: 1; }
    footer { margin-top: auto; }
</style>"""

            print(f"  ✓ Базовый header/footer создан (fallback режим)")
            return True
    
    def clean_code_response(self, response):
        """Очистка кода от markdown и лишних тегов"""
        code = response.strip()
        
        # Удаляем markdown code blocks
        if code.startswith('```'):
            lines = code.split('\n')
            code = '\n'.join(lines[1:])
        if code.endswith('```'):
            code = code[:-3]
        
        # Удаляем ```html если есть
        code = code.replace('```html', '').replace('```php', '').replace('```', '')
        
        return code.strip()
    
    def get_favicon_url(self):
        """Возвращает URL favicon с cache busting timestamp"""
        timestamp = getattr(self, 'favicon_timestamp', '')
        if timestamp:
            return f"favicon.svg?v={timestamp}"
        return "favicon.svg"

    def generate_favicon(self, output_dir):
        """Генерация простого SVG favicon"""
        site_name = self.blueprint.get('site_name', 'Site')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')

        # Конвертируем Tailwind цвет в hex
        color_map = {
            'blue-600': '#2563eb',
            'purple-600': '#9333ea',
            'emerald-600': '#059669',
            'orange-600': '#ea580c',
            'rose-600': '#e11d48',
            'sky-600': '#0284c7',
            'violet-600': '#7c3aed',
            'fuchsia-600': '#c026d3'
        }

        hex_color = color_map.get(primary, '#2563eb')

        # Берем первую букву названия
        letter = site_name[0].upper()

        favicon_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" fill="{hex_color}" rx="20"/>
    <text x="50" y="70" font-family="Arial, sans-serif" font-size="60" font-weight="bold"
          fill="white" text-anchor="middle">{letter}</text>
</svg>"""

        # Удаляем старый favicon если существует
        favicon_path = os.path.join(output_dir, 'favicon.svg')
        if os.path.exists(favicon_path):
            os.remove(favicon_path)

        with open(favicon_path, 'w', encoding='utf-8') as f:
            f.write(favicon_svg)

        # Сохраняем timestamp для cache busting
        import time
        self.favicon_timestamp = str(int(time.time()))

        print(f"✓ Favicon создан: {letter} ({hex_color})")

    def generate_cookie_notice(self):
        """Генерация Cookie Notice с 9 вариациями (3 баннера снизу + 3 поп-ап справа + 3 маленьких)"""
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')

        # Получаем переводы cookie notice через API
        cookie_content = self.generate_theme_content_via_api(theme, "cookie_notice_content", 1)

        # Fallback если API не вернул результат
        if not cookie_content:
            cookie_content_fallback = {
                'message': 'We use cookies to enhance your browsing experience. By continuing, you agree to our Cookie Policy.',
                'learn_more': 'Learn more',
                'accept': 'Accept',
                'decline': 'Decline',
                'accept_all': 'Accept All',
                'ok': 'OK',
                'consent_title': 'Cookie Consent',
                'best_experience': 'This website uses cookies to ensure you get the best experience.'
            }
            cookie_content = self.get_localized_fallback('cookie_notice_content', cookie_content_fallback)

        # Выбираем случайный вариант из 9
        variation = random.randint(1, 9)

        if variation <= 3:
            # Баннер снизу (3 вариации)
            if variation == 1:
                # Баннер 1: Классический по центру
                return f"""
<div id="cookie-notice" class="fixed bottom-0 left-0 right-0 bg-gray-900 text-white py-4 px-6 shadow-lg z-50 hidden">
    <div class="container mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-3">
            <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <p class="text-sm">{cookie_content.get('message', 'We use cookies to enhance your browsing experience.')}</p>
        </div>
        <div class="flex gap-3">
            <button onclick="acceptCookies()" class="bg-{primary} hover:bg-{hover} text-white px-6 py-2 rounded-lg text-sm font-semibold transition">
                {cookie_content.get('accept', 'Accept')}
            </button>
            <button onclick="dismissCookieNotice()" class="bg-gray-700 hover:bg-gray-600 text-white px-6 py-2 rounded-lg text-sm font-semibold transition">
                {cookie_content.get('decline', 'Decline')}
            </button>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
function dismissCookieNotice() {{
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""
            elif variation == 2:
                # Баннер 2: Широкий с иконкой cookie
                return f"""
<div id="cookie-notice" class="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-{primary} shadow-2xl py-6 px-6 z-50 hidden">
    <div class="container mx-auto">
        <div class="flex flex-col md:flex-row items-center justify-between gap-4">
            <div class="flex items-start gap-4">
                <div class="text-4xl">🍪</div>
                <div>
                    <h3 class="font-bold text-lg mb-1">{cookie_content.get('consent_title', 'Cookie Consent')}</h3>
                    <p class="text-gray-600 text-sm">{cookie_content.get('best_experience', 'This website uses cookies to ensure you get the best experience.')} <a href="cookie.php" class="text-{primary} underline hover:text-{hover} transition">{cookie_content.get('learn_more', 'Learn more')}</a></p>
                </div>
            </div>
            <div class="flex gap-3 flex-shrink-0">
                <button onclick="acceptCookies()" class="bg-{primary} hover:bg-{hover} text-white px-8 py-3 rounded-lg font-semibold transition shadow-lg">
                    {cookie_content.get('accept_all', 'Accept All')}
                </button>
                <button onclick="dismissCookieNotice()" class="border-2 border-gray-300 hover:border-gray-400 text-gray-700 px-8 py-3 rounded-lg font-semibold transition">
                    {cookie_content.get('decline', 'Decline')}
                </button>
            </div>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
function dismissCookieNotice() {{
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""
            else:  # variation == 3
                # Баннер 3: Минималистичный
                return f"""
<div id="cookie-notice" class="fixed bottom-0 left-0 right-0 bg-{primary} text-white py-3 px-6 z-50 hidden">
    <div class="container mx-auto flex items-center justify-between">
        <p class="text-sm">🍪 {cookie_content.get('message', 'We use cookies.')}</p>
        <div class="flex gap-2">
            <button onclick="acceptCookies()" class="bg-white text-{primary} px-4 py-1 rounded font-semibold text-sm hover:opacity-90 transition">
                {cookie_content.get('ok', 'OK')}
            </button>
            <button onclick="dismissCookieNotice()" class="border border-white text-white px-4 py-1 rounded font-semibold text-sm hover:bg-white hover:text-{primary} transition">
                ✕
            </button>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
function dismissCookieNotice() {{
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""

        elif variation <= 6:
            # Поп-ап справа снизу (3 вариации)
            if variation == 4:
                # Поп-ап 1: Карточка с тенью
                return f"""
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-white rounded-xl shadow-2xl p-6 max-w-md z-50 hidden border border-gray-200">
    <div class="flex items-start gap-3 mb-4">
        <div class="w-10 h-10 bg-{primary}/10 rounded-full flex items-center justify-center flex-shrink-0">
            <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
            </svg>
        </div>
        <div>
            <h3 class="font-bold text-lg mb-2">{cookie_content.get('consent_title', 'Cookie Settings')}</h3>
            <p class="text-gray-600 text-sm">{cookie_content.get('best_experience', 'We use cookies to improve your experience.')} <a href="cookie.php" class="text-{primary} underline hover:text-{hover}">{cookie_content.get('learn_more', 'cookie policy')}</a>.</p>
        </div>
        <button onclick="dismissCookieNotice()" class="text-gray-400 hover:text-gray-600 flex-shrink-0">
            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
        </button>
    </div>
    <div class="flex gap-3">
        <button onclick="acceptCookies()" class="flex-1 bg-{primary} hover:bg-{hover} text-white py-2 rounded-lg font-semibold transition">
            {cookie_content.get('accept', 'Accept')}
        </button>
        <button onclick="dismissCookieNotice()" class="flex-1 border-2 border-gray-300 hover:border-gray-400 text-gray-700 py-2 rounded-lg font-semibold transition">
            {cookie_content.get('decline', 'Decline')}
        </button>
    </div>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
function dismissCookieNotice() {{
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""
            elif variation == 5:
                # Поп-ап 2: Темный с градиентом
                return f"""
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-gradient-to-br from-gray-900 to-gray-800 text-white rounded-2xl shadow-2xl p-6 max-w-sm z-50 hidden">
    <div class="mb-4">
        <div class="flex items-center justify-between mb-3">
            <span class="text-3xl">🍪</span>
            <button onclick="dismissCookieNotice()" class="text-gray-400 hover:text-white">
                <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
        <h3 class="font-bold text-xl mb-2">{cookie_content.get('consent_title', 'Cookies Notice')}</h3>
        <p class="text-gray-300 text-sm">{cookie_content.get('best_experience', 'We value your privacy.')} <a href="cookie.php" class="text-{primary} underline hover:opacity-80">{cookie_content.get('learn_more', 'cookie policy')}</a></p>
    </div>
    <button onclick="acceptCookies()" class="w-full bg-{primary} hover:bg-{hover} text-white py-3 rounded-xl font-bold transition shadow-lg">
        {cookie_content.get('accept', 'Accept Cookies')}
    </button>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
function dismissCookieNotice() {{
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""
            else:  # variation == 6
                # Поп-ап 3: Компактный с border
                return f"""
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-white rounded-lg shadow-xl p-5 max-w-xs z-50 hidden border-l-4 border-{primary}">
    <div class="flex items-center justify-between mb-3">
        <h4 class="font-bold text-gray-900">{cookie_content.get('consent_title', 'Cookie Notice')}</h4>
        <button onclick="dismissCookieNotice()" class="text-gray-400 hover:text-gray-600">✕</button>
    </div>
    <p class="text-gray-600 text-sm mb-4">{cookie_content.get('message', 'We use cookies to personalize content.')} <a href="cookie.php" class="text-{primary} font-semibold hover:underline">{cookie_content.get('learn_more', 'Details')}</a></p>
    <button onclick="acceptCookies()" class="w-full bg-{primary} hover:bg-{hover} text-white py-2 rounded-lg font-semibold text-sm transition">
        {cookie_content.get('ok', 'Got it!')}
    </button>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
function dismissCookieNotice() {{
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""

        else:
            # Маленькие уведомления (3 вариации)
            if variation == 7:
                # Маленькое 1: Таблетка снизу справа
                return f"""
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-gray-900 text-white rounded-full px-5 py-3 shadow-lg z-50 hidden flex items-center gap-3">
    <span class="text-sm">🍪 {cookie_content.get('consent_title', 'Cookies')}</span>
    <button onclick="acceptCookies()" class="bg-{primary} hover:bg-{hover} text-white px-4 py-1 rounded-full text-xs font-semibold transition">
        {cookie_content.get('ok', 'OK')}
    </button>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""
            elif variation == 8:
                # Маленькое 2: Badge с иконкой
                return f"""
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-white border-2 border-{primary} rounded-xl px-4 py-3 shadow-lg z-50 hidden">
    <div class="flex items-center gap-2">
        <div class="w-8 h-8 bg-{primary} rounded-full flex items-center justify-center text-white font-bold text-sm">C</div>
        <div>
            <p class="text-xs text-gray-700 font-semibold">{cookie_content.get('message', 'Cookies active')}</p>
            <button onclick="acceptCookies()" class="text-{primary} text-xs underline hover:no-underline">{cookie_content.get('accept', 'Agree')}</button>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""
            else:  # variation == 9
                # Маленькое 3: Minimal toast
                return f"""
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-{primary} text-white rounded-lg px-6 py-3 shadow-lg z-50 hidden flex items-center gap-3">
    <span class="text-sm font-medium">{cookie_content.get('message', 'Cookies in use')}</span>
    <button onclick="acceptCookies()" class="text-white hover:opacity-80 font-bold text-lg">×</button>
</div>
<script>
function showCookieNotice() {{
    document.getElementById('cookie-notice').classList.remove('hidden');
}}
function acceptCookies() {{
    localStorage.setItem('cookiesAccepted', 'true');
    document.getElementById('cookie-notice').classList.add('hidden');
}}
setTimeout(showCookieNotice, 1000);
</script>
"""

    def generate_contact_page(self, output_dir):
        """Генерация Contact страницы с 5 вариациями"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        country = self.blueprint.get('country', 'USA')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        # Получаем контент contact page через API
        contact_page_data = self.generate_theme_content_via_api(theme, "contact_page_content", 1)

        # Fallback если API не вернул результат
        if not contact_page_data:
            contact_page_data_fallback = {
                'heading': 'Get In Touch',
                'subheading': 'Have a question or want to work together? We would love to hear from you.',
                'name_label': 'Your Name',
                'email_label': 'Your Email',
                'phone_label': 'Phone Number',
                'message_label': 'Your Message',
                'submit_button': 'Send Message',
                'info_heading': 'Contact Information',
                'address_label': 'Address',
                'phone_label_display': 'Phone',
                'email_label_display': 'Email'
            }
            contact_page_data = self.get_localized_fallback('contact_page_content', contact_page_data_fallback)

        heading = contact_page_data.get('heading', 'Get In Touch')
        subheading = contact_page_data.get('subheading', 'Have a question or want to work together?')
        name_label = contact_page_data.get('name_label', 'Your Name')
        email_label = contact_page_data.get('email_label', 'Your Email')
        phone_label = contact_page_data.get('phone_label', 'Phone Number')
        message_label = contact_page_data.get('message_label', 'Your Message')
        submit_button = contact_page_data.get('submit_button', 'Send Message')
        info_heading = contact_page_data.get('info_heading', 'Contact Information')
        address_label = contact_page_data.get('address_label', 'Address')
        phone_label_display = contact_page_data.get('phone_label_display', 'Phone')
        email_label_display = contact_page_data.get('email_label_display', 'Email')

        # Используем сохраненные контактные данные из blueprint (те же что и в footer)
        contact_data_1 = self.blueprint.get('contact_data', self.get_country_contact_data(country))
        # Для разнообразия можем генерировать дополнительные контакты, но основной остается из blueprint
        contact_data_2 = self.get_country_contact_data(country)
        contact_data_3 = self.get_country_contact_data(country)

        # Улучшенная рандомизация: используем weighted random choice
        # Каждый вариант получает равный вес для равномерного распределения
        variations = [1, 2, 3, 4, 5]

        # Используем детерминированный выбор на основе site_name для консистентности
        # но добавляем случайность через shuffle с сохранением seed
        random.shuffle(variations)
        variation = variations[0]

        # Сохраняем выбор в blueprint для консистентности
        self.blueprint['contact_page_variant'] = variation

        # Вариация 1: Классический двухколоночный (форма слева, инфо справа)
        if variation == 1:
            main_content = f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">{heading}</h1>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">
                    {subheading}
                </p>
            </div>

            <div class="grid md:grid-cols-2 gap-12 max-w-6xl mx-auto">
                <div class="bg-white rounded-2xl shadow-xl p-8 md:p-10">
                    <h2 class="text-3xl font-bold mb-6">{submit_button}</h2>
                    <form action="thanks_you.php" method="POST" class="space-y-6">
                        <div>
                            <label for="name" class="block text-gray-700 font-semibold mb-2">{name_label} <span class="text-red-500">*</span></label>
                            <input type="text" id="name" name="name" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none">
                        </div>
                        <div>
                            <label for="email" class="block text-gray-700 font-semibold mb-2">{email_label} <span class="text-red-500">*</span></label>
                            <input type="email" id="email" name="email" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none">
                        </div>
                        <div>
                            <label for="phone" class="block text-gray-700 font-semibold mb-2">{phone_label}</label>
                            <input type="tel" id="phone" name="phone" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none">
                        </div>
                        <div>
                            <label for="message" class="block text-gray-700 font-semibold mb-2">{message_label} <span class="text-red-500">*</span></label>
                            <textarea id="message" name="message" rows="5" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none resize-none"></textarea>
                        </div>
                        <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-0.5">{submit_button}</button>
                    </form>
                </div>

                <div class="space-y-8">
                    <div class="bg-white rounded-2xl shadow-xl p-8">
                        <h2 class="text-3xl font-bold mb-6">{info_heading}</h2>
                        <div class="space-y-6">
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">{email_label_display}</h3>
                                    <a href="mailto:{site_name.lower().replace(' ', '')}@gmail.com" class="text-gray-600 hover:text-{primary} transition">{site_name.lower().replace(' ', '')}@gmail.com</a>
                                </div>
                            </div>
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">{phone_label_display}</h3>
                                    <a href="tel:{contact_data_1["phone"].replace(" ", "")}" class="text-gray-600 hover:text-{primary} transition">{contact_data_1["phone"]}</a>
                                </div>
                            </div>
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">{address_label}</h3>
                                    <p class="text-gray-600">{contact_data_1["address"]}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 2: Центрированная форма с карточками контактов внизу
        elif variation == 2:
            main_content = f"""<main>
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-12">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">{heading}</h1>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">{subheading}</p>
            </div>

            <div class="max-w-3xl mx-auto bg-white rounded-2xl shadow-2xl p-10 mb-16">
                <form action="thanks_you.php" method="POST" class="space-y-6">
                    <div class="grid md:grid-cols-2 gap-6">
                        <div>
                            <label for="name" class="block text-gray-700 font-semibold mb-2">{name_label} <span class="text-red-500">*</span></label>
                            <input type="text" id="name" name="name" required class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none">
                        </div>
                        <div>
                            <label for="email" class="block text-gray-700 font-semibold mb-2">{email_label} <span class="text-red-500">*</span></label>
                            <input type="email" id="email" name="email" required class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none">
                        </div>
                    </div>
                    <div class="grid md:grid-cols-2 gap-6">
                        <div>
                            <label for="phone" class="block text-gray-700 font-semibold mb-2">{phone_label}</label>
                            <input type="tel" id="phone" name="phone" class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none">
                        </div>
                        <div>
                            <label for="company" class="block text-gray-700 font-semibold mb-2">{info_heading}</label>
                            <input type="text" id="company" name="company" class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none">
                        </div>
                    </div>
                    <div>
                        <label for="message" class="block text-gray-700 font-semibold mb-2">{message_label} <span class="text-red-500">*</span></label>
                        <textarea id="message" name="message" rows="6" required class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none resize-none"></textarea>
                    </div>
                    <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-bold transition-all shadow-lg hover:shadow-xl transform hover:scale-105">{submit_button}</button>
                </form>
            </div>

            <div class="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
                <div class="text-center p-8 bg-gradient-to-br from-{primary}/5 to-white rounded-xl hover:shadow-lg transition-shadow">
                    <div class="w-16 h-16 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">{email_label_display}</h3>
                    <p class="text-gray-600">{site_name.lower().replace(' ', '')}@gmail.com</p>
                </div>
                <div class="text-center p-8 bg-gradient-to-br from-{primary}/5 to-white rounded-xl hover:shadow-lg transition-shadow">
                    <div class="w-16 h-16 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">{phone_label_display}</h3>
                    <p class="text-gray-600">{contact_data_2["phone"]}</p>
                </div>
                <div class="text-center p-8 bg-gradient-to-br from-{primary}/5 to-white rounded-xl hover:shadow-lg transition-shadow">
                    <div class="w-16 h-16 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">{address_label}</h3>
                    <p class="text-gray-600">{contact_data_2["address"]}</p>
                </div>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 3: Split-screen с градиентом слева
        elif variation == 3:
            main_content = f"""<main>
    <section class="min-h-screen flex items-center">
        <div class="grid md:grid-cols-2 w-full">
            <div class="bg-gradient-to-br from-{primary} to-{hover} p-12 md:p-20 flex flex-col justify-center text-white">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">{heading}</h1>
                <p class="text-xl mb-12 opacity-90">{subheading}</p>

                <div class="space-y-8">
                    <div class="flex items-center">
                        <div class="w-14 h-14 bg-white/20 rounded-lg flex items-center justify-center mr-6 flex-shrink-0">
                            <svg class="w-7 h-7 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z"></path></svg>
                        </div>
                        <div>
                            <p class="text-sm opacity-75">{phone_label_display}</p>
                            <p class="text-lg font-semibold">{contact_data_3["phone"]}</p>
                        </div>
                    </div>
                    <div class="flex items-center">
                        <div class="w-14 h-14 bg-white/20 rounded-lg flex items-center justify-center mr-6 flex-shrink-0">
                            <svg class="w-7 h-7 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"></path><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"></path></svg>
                        </div>
                        <div>
                            <p class="text-sm opacity-75">{email_label_display}</p>
                            <p class="text-lg font-semibold">{site_name.lower().replace(' ', '')}@gmail.com</p>
                        </div>
                    </div>
                    <div class="flex items-center">
                        <div class="w-14 h-14 bg-white/20 rounded-lg flex items-center justify-center mr-6 flex-shrink-0">
                            <svg class="w-7 h-7 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path></svg>
                        </div>
                        <div>
                            <p class="text-sm opacity-75">{address_label}</p>
                            <p class="text-lg font-semibold">{contact_data_3["address"]}</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-white p-12 md:p-20 flex flex-col justify-center">
                <h2 class="text-3xl font-bold mb-8">{info_heading}</h2>
                <form action="thanks_you.php" method="POST" class="space-y-6">
                    <div>
                        <input type="text" name="name" required class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none text-lg" placeholder="{name_label} *">
                    </div>
                    <div>
                        <input type="email" name="email" required class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none text-lg" placeholder="{email_label} *">
                    </div>
                    <div>
                        <input type="tel" name="phone" class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none text-lg" placeholder="{phone_label}">
                    </div>
                    <div>
                        <textarea name="message" rows="5" required class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none resize-none text-lg" placeholder="{message_label} *"></textarea>
                    </div>
                    <button type="submit" class="bg-{primary} hover:bg-{hover} text-white px-12 py-4 rounded-full text-lg font-bold transition-all shadow-lg hover:shadow-xl transform hover:scale-105">{submit_button}</button>
                </form>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 4: Полноширинная форма с плавающими карточками
        elif variation == 4:
            main_content = f"""<main>
    <section class="py-20 bg-gray-50 relative">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">{heading}</h1>
                <p class="text-xl text-gray-600">{subheading}</p>
            </div>

            <div class="max-w-5xl mx-auto relative">
                <div class="bg-white rounded-3xl shadow-2xl p-10 md:p-16">
                    <form action="thanks_you.php" method="POST" class="space-y-8">
                        <div class="grid md:grid-cols-3 gap-6">
                            <div>
                                <label class="block text-sm font-bold text-gray-700 mb-3">{name_label.upper()} *</label>
                                <input type="text" name="name" required class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none">
                            </div>
                            <div>
                                <label class="block text-sm font-bold text-gray-700 mb-3">{email_label.upper()} *</label>
                                <input type="email" name="email" required class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none">
                            </div>
                            <div>
                                <label class="block text-sm font-bold text-gray-700 mb-3">{phone_label.upper()}</label>
                                <input type="tel" name="phone" class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none">
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-bold text-gray-700 mb-3">{message_label.upper()} *</label>
                            <textarea name="message" rows="6" required class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none resize-none"></textarea>
                        </div>
                        <div class="flex justify-center pt-4">
                            <button type="submit" class="bg-{primary} hover:bg-{hover} text-white px-16 py-5 rounded-xl text-lg font-bold transition-all shadow-xl hover:shadow-2xl transform hover:-translate-y-1">{submit_button}</button>
                        </div>
                    </form>
                </div>

                <div class="grid md:grid-cols-3 gap-6 mt-12">
                    <div class="bg-white rounded-2xl shadow-xl p-6 text-center border-t-4 border-{primary}">
                        <div class="w-12 h-12 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-3">
                            <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                        </div>
                        <h3 class="font-bold text-gray-900 mb-1">{email_label_display}</h3>
                        <p class="text-sm text-gray-600">{site_name.lower().replace(' ', '')}@gmail.com</p>
                    </div>
                    <div class="bg-white rounded-2xl shadow-xl p-6 text-center border-t-4 border-{primary}">
                        <div class="w-12 h-12 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-3">
                            <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                        </div>
                        <h3 class="font-bold text-gray-900 mb-1">{phone_label_display}</h3>
                        <p class="text-sm text-gray-600">{contact_data_1["phone"]}</p>
                    </div>
                    <div class="bg-white rounded-2xl shadow-xl p-6 text-center border-t-4 border-{primary}">
                        <div class="w-12 h-12 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-3">
                            <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                        </div>
                        <h3 class="font-bold text-gray-900 mb-1">{address_label}</h3>
                        <p class="text-sm text-gray-600">{contact_data_1["address"]}</p>
                    </div>
                </div>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 5: Форма с расширенными полями
        else:  # variation == 5
            main_content = f"""<main>
    <section class="py-20 bg-gradient-to-br from-gray-50 to-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-12">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">{heading}</h1>
                <p class="text-xl text-gray-600">{subheading}</p>
            </div>

            <div class="max-w-4xl mx-auto">
                <div class="bg-white rounded-3xl shadow-2xl p-10 md:p-16">
                    <form action="thanks_you.php" method="POST" class="space-y-8">
                        <div class="grid md:grid-cols-2 gap-8">
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                                    {name_label} <span class="text-red-500 ml-1">*</span>
                                </label>
                                <input type="text" name="name" required class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none">
                            </div>
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                                    {email_label} <span class="text-red-500 ml-1">*</span>
                                </label>
                                <input type="email" name="email" required class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none">
                            </div>
                        </div>

                        <div class="grid md:grid-cols-2 gap-8">
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                                    {phone_label}
                                </label>
                                <input type="tel" name="phone" class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none">
                            </div>
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
                                    {info_heading}
                                </label>
                                <input type="text" name="company" class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none">
                            </div>
                        </div>

                        <div>
                            <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"></path></svg>
                                {message_label} <span class="text-red-500 ml-1">*</span>
                            </label>
                            <textarea name="message" rows="6" required class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none resize-none"></textarea>
                        </div>

                        <div class="flex justify-center pt-4">
                            <button type="submit" class="bg-{primary} hover:bg-{hover} text-white px-16 py-5 rounded-xl text-lg font-bold transition-all shadow-xl hover:shadow-2xl transform hover:-translate-y-1 flex items-center">
                                {submit_button}
                                <svg class="w-6 h-6 ml-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                            </button>
                        </div>
                    </form>

                    <div class="mt-12 pt-8 border-t border-gray-200 grid md:grid-cols-3 gap-6 text-center">
                        <div>
                            <p class="text-sm text-gray-500 mb-1">{email_label_display}</p>
                            <p class="font-semibold text-gray-900">{site_name.lower().replace(' ', '')}@gmail.com</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-500 mb-1">{phone_label_display}</p>
                            <p class="font-semibold text-gray-900">{contact_data_2["phone"]}</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-500 mb-1">{address_label}</p>
                            <p class="font-semibold text-gray-900">{contact_data_2["address"]}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
</main>"""

        # КРИТИЧЕСКИ ВАЖНО: Проверяем, что header и footer созданы
        if not self.header_code or not self.footer_code:
            print(f"    ⚠️  Header/Footer не найдены, регенерация...")
            self.generate_header_footer()

        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact Us - {site_name}</title>
    <link rel="icon" type="image/svg+xml" href="{self.get_favicon_url()}">
    {self.header_footer_css}
</head>
<body>
    {self.header_code}

    {main_content}

    {self.footer_code}
</body>
</html>"""

        page_path = os.path.join(output_dir, "contact.php")
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(full_html)

        print(f"    ✓ contact.php создана (готовый шаблон)")
        return True

    def generate_hero_section(self, site_name, theme, primary, hover):
        """Генерация Hero секции с 5 вариациями"""
        # Получаем контент через API
        hero_data = self.generate_theme_content_via_api(theme, "hero_content", 1)

        # Fallback если API не вернул результат
        if not hero_data:
            hero_data_fallback = {
                'title': f'Welcome to {site_name}',
                'subtitle': f'Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.',
                'button_primary': 'About Us',
                'button_secondary': 'Contact'
            }
            hero_data = self.get_localized_fallback('hero_content', hero_data_fallback)

        # Извлекаем данные
        title = hero_data.get('title', f'Welcome to {site_name}')
        subtitle = hero_data.get('subtitle', f'Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.')
        button_primary = hero_data.get('button_primary', 'About Us')
        button_secondary = hero_data.get('button_secondary', 'Contact')

        # hero.jpg, about.jpg и service1.jpg всегда генерируются как 'required'
        # поэтому можем смело использовать все варианты без проверки наличия изображений
        # (изображения генерируются ПОСЛЕ страниц, поэтому self.generated_images пуст на этом этапе)

        # Все 5 вариантов доступны, так как необходимые изображения будут сгенерированы
        available_variants = [1, 2, 3, 4, 5]

        # Используем weighted choice для равномерного распределения
        # Вариант 3 (без изображения) получает меньший вес для большего разнообразия
        weights = [1.5, 1.5, 0.8, 1.5, 1.5]  # Вариант 3 с весом 0.8 вместо 1.5
        hero_variant = random.choices(available_variants, weights=weights, k=1)[0]

        # Сохраняем выбор в blueprint для консистентности
        if not hasattr(self, 'blueprint'):
            self.blueprint = {}
        self.blueprint['hero_variant'] = hero_variant

        # hero.jpg всегда будет сгенерирован
        hero_image = 'hero.jpg'

        # Вариация 1: Фотография справа
        if hero_variant == 1:
            return f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h1 class="text-5xl md:text-6xl font-bold mb-6">{title}</h1>
                    <p class="text-xl text-gray-600 mb-8">{subtitle}</p>
                    <div>
                        <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl text-center">
                            {button_primary}
                        </a>
                    </div>
                </div>
                <div>
                    <img src="images/{hero_image}" alt="{site_name}" class="rounded-2xl shadow-2xl w-full h-full object-cover min-h-[400px]">
                </div>
            </div>
        </div>
    </section>
"""

        # Вариация 2: Карусель с фотографиями на фоне
        elif hero_variant == 2:
            # hero.jpg, about.jpg и service1.jpg всегда генерируются как 'required'
            # поэтому можем смело использовать их без проверки наличия
            # (изображения генерируются ПОСЛЕ страниц, поэтому self.generated_images пуст на этом этапе)
            carousel_images = [
                ('hero.jpg', 'Slide 1'),
                ('about.jpg', 'Slide 2'),
                ('service1.jpg', 'Slide 3')
            ]

            # Генерируем слайды только для существующих изображений
            carousel_slides = ''
            for idx, (img, alt) in enumerate(carousel_images):
                active_class = 'active' if idx == 0 else 'opacity-0'
                carousel_slides += f"""
                <div class="carousel-item {active_class} absolute inset-0 transition-opacity duration-1000">
                    <img src="images/{img}" alt="{alt}" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-black/50"></div>
                </div>"""

            return f"""<main>
    <section class="relative py-32 overflow-hidden">
        <div class="absolute inset-0 z-0">
            <div id="hero-carousel" class="w-full h-full">{carousel_slides}
            </div>
        </div>

        <div class="container mx-auto px-6 relative z-10">
            <div class="max-w-4xl mx-auto text-center text-white">
                <h1 class="text-5xl md:text-7xl font-bold mb-6 drop-shadow-lg">{title}</h1>
                <p class="text-xl md:text-2xl mb-8 drop-shadow-lg">{subtitle}</p>
                <div class="flex justify-center">
                    <a href="contact.php" class="inline-block bg-white hover:bg-gray-100 text-{primary} px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        {button_primary}
                    </a>
                </div>
            </div>
        </div>

        <script>
        (function() {{
            let currentSlide = 0;
            const slides = document.querySelectorAll('.carousel-item');
            const totalSlides = slides.length;

            function nextSlide() {{
                slides[currentSlide].classList.remove('opacity-100');
                slides[currentSlide].classList.add('opacity-0');
                currentSlide = (currentSlide + 1) % totalSlides;
                slides[currentSlide].classList.remove('opacity-0');
                slides[currentSlide].classList.add('opacity-100');
            }}

            setInterval(nextSlide, 4000);
        }})();
        </script>
    </section>
"""

        # Вариация 3: Без фотографии (центрированная)
        elif hero_variant == 3:
            return f"""<main>
    <section class="relative py-32 bg-gradient-to-br from-{primary}/10 via-white to-{primary}/5">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto text-center">
                <h1 class="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-{primary} to-{hover} bg-clip-text text-transparent">
                    {title}
                </h1>
                <p class="text-xl md:text-2xl text-gray-600 mb-8">
                    {subtitle}
                </p>
                <div class="flex justify-center">
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        {button_primary}
                    </a>
                </div>
            </div>
        </div>
        <div class="absolute top-0 right-0 w-64 h-64 bg-{primary}/10 rounded-full blur-3xl"></div>
        <div class="absolute bottom-0 left-0 w-96 h-96 bg-{hover}/10 rounded-full blur-3xl"></div>
    </section>
"""

        # Вариация 4: Картинка на фоне
        elif hero_variant == 4:
            return f"""<main>
    <section class="relative py-40 overflow-hidden">
        <div class="absolute inset-0 z-0">
            <img src="images/hero.jpg" alt="{site_name}" class="w-full h-full object-cover">
            <div class="absolute inset-0 bg-gradient-to-b from-black/60 via-black/50 to-black/70"></div>
        </div>

        <div class="container mx-auto px-6 relative z-10">
            <div class="max-w-4xl mx-auto text-center text-white">
                <h1 class="text-6xl md:text-8xl font-bold mb-6 drop-shadow-2xl">{title}</h1>
                <p class="text-2xl md:text-3xl mb-12 drop-shadow-lg">{subtitle}</p>
                <div class="flex justify-center">
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-12 py-5 rounded-lg text-xl font-bold transition shadow-2xl hover:shadow-3xl transform hover:-translate-y-1">
                        {button_secondary}
                    </a>
                </div>
            </div>
        </div>
    </section>
"""

        # Вариация 5: Фотография слева
        else:
            return f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div class="order-2 md:order-1">
                    <img src="images/{hero_image}" alt="{site_name}" class="rounded-2xl shadow-2xl w-full h-96 object-cover">
                </div>
                <div class="order-1 md:order-2">
                    <h1 class="text-5xl md:text-6xl font-bold mb-6">{title}</h1>
                    <p class="text-xl text-gray-600 mb-8">{subtitle}</p>
                    <div>
                        <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl text-center">
                            {button_primary}
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </section>
"""

    def generate_company_page(self, site_name, primary, hover):
        """Генерация Company страницы с 4 вариациями"""
        theme = self.blueprint.get('theme', 'business')

        # Получаем переводы company page через API
        company_content = self.generate_theme_content_via_api(theme, "company_page_content", 1)

        # Получаем контент about_content через API для истории компании
        about_data = self.generate_theme_content_via_api(theme, "about_content", 1)

        # Получаем ценности компании через API (3 ценности)
        company_values = self.generate_theme_content_via_api(theme, "company_values", 3)

        # Получаем членов команды через API (3 члена) с контекстом "company" для уникальных имен
        team_members = self.generate_theme_content_via_api(theme, "team_members", 3, page_context="company")

        # Получаем тексты кнопок через API
        button_labels = self.generate_theme_content_via_api(theme, "button_labels", 1)

        # Fallback если API не вернул результат
        if not company_content:
            company_content = {
                'section_heading': 'About Us',
                'section_description': 'Your trusted partner in business transformation, delivering innovative solutions that help organizations achieve their goals.',
                'values_heading': 'Our Core Values',
                'team_heading': 'Meet Our Team',
                'contact_cta': 'Ready to Work Together?',
                'contact_cta_description': 'Get in touch today to discover how our expertise can help transform your business and achieve lasting success.'
            }
            company_content = self.get_localized_fallback('company_page_content', company_content)

        if not about_data:
            about_data = {
                'heading': 'Our Story',
                'paragraph1': 'Founded in 2012, we have been dedicated to providing exceptional services and solutions to our clients.',
                'paragraph2': 'Our team brings years of experience and expertise to every project, ensuring the best possible outcomes.',
                'button_text': 'Learn More'
            }
            about_data = self.get_localized_fallback('about_content', about_data)

        if not company_values or not isinstance(company_values, list) or len(company_values) < 3:
            company_values = [
                {'title': 'Excellence', 'description': 'Committed to delivering the highest quality.'},
                {'title': 'Innovation', 'description': 'Pushing boundaries with creative solutions.'},
                {'title': 'Integrity', 'description': 'Trust and transparency in everything we do.'}
            ]
            company_values = [self.get_localized_fallback('company_values', val) for val in company_values]

        if not team_members or not isinstance(team_members, list) or len(team_members) < 3:
            team_members = [
                {'name': 'Sarah Johnson', 'position': 'Chief Executive Officer', 'description': 'Leading our vision with passion and expertise.'},
                {'name': 'Michael Chen', 'position': 'Chief Technology Officer', 'description': 'Driving innovation and technical excellence.'},
                {'name': 'Emily Rodriguez', 'position': 'Head of Operations', 'description': 'Ensuring seamless execution and delivery.'}
            ]
            team_members = [self.get_localized_fallback('team_members', member) for member in team_members]

        # Добавляем описания к членам команды, если их нет
        team_descriptions_fallback = [
            {'description': 'Leading our vision with passion and expertise.'},
            {'description': 'Driving innovation and technical excellence.'},
            {'description': 'Ensuring seamless execution and delivery.'}
        ]
        # Переводим описания на нужный язык
        team_descriptions_localized = [self.get_localized_fallback('team_member_description', desc) for desc in team_descriptions_fallback]

        for i, member in enumerate(team_members):
            if 'description' not in member or not member.get('description'):
                member['description'] = team_descriptions_localized[i % len(team_descriptions_localized)].get('description', '')

        if not button_labels or not isinstance(button_labels, dict):
            button_labels = {
                'contact_us': 'Contact Us',
                'get_started': 'Get Started',
                'learn_more': 'Learn More'
            }
            button_labels = self.get_localized_fallback('button_labels', button_labels)

        # Team изображения генерируются с приоритетом 'required', поэтому всегда доступны
        has_team_images = True

        # Используем предвыбранный вариант или выбираем случайно
        company_variant = getattr(self, 'selected_company_variant', random.randint(1, 4))

        # Вариация 1: Классический дизайн с историей, ценностями и командой
        if company_variant == 1:
            # SVG icons для ценностей
            value_icons = [
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>',
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>',
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>'
            ]

            # Values section - динамические ценности
            values_items_html = []
            for i, value in enumerate(company_values[:3]):
                icon = value_icons[i % len(value_icons)]
                values_items_html.append(f"""
                    <div class="text-center">
                        <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg class="w-8 h-8 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                {icon}
                            </svg>
                        </div>
                        <h3 class="text-xl font-bold mb-2">{value.get('title', '')}</h3>
                        <p class="text-gray-600">{value.get('description', '')}</p>
                    </div>""")

            values_html = f"""
                <div class="grid md:grid-cols-3 gap-8">
                    {''.join(values_items_html)}
                </div>"""

            # Team section - динамические члены команды
            if has_team_images:
                team_items_html = []
                for i, member in enumerate(team_members[:3]):
                    team_items_html.append(f"""
                    <div class="bg-white rounded-xl shadow-lg overflow-hidden">
                        <img src="images/team{i+1}.jpg" alt="Team Member" class="w-full h-64 object-cover">
                        <div class="p-6">
                            <h3 class="text-xl font-bold mb-1">{member.get('name', '')}</h3>
                            <p class="text-{primary} font-semibold mb-3">{member.get('position', '')}</p>
                            <p class="text-gray-600">{member.get('description', '')}</p>
                        </div>
                    </div>""")
                team_html = f"""
                <div class="grid md:grid-cols-3 gap-8">
                    {''.join(team_items_html)}
                </div>"""
            else:
                team_items_html = []
                for i, member in enumerate(team_members[:3]):
                    team_items_html.append(f"""
                    <div class="bg-white rounded-xl shadow-lg p-8">
                        <h3 class="text-xl font-bold mb-1">{member.get('name', '')}</h3>
                        <p class="text-{primary} font-semibold mb-3">{member.get('position', '')}</p>
                        <p class="text-gray-600">{member.get('description', '')}</p>
                    </div>""")
                team_html = f"""
                <div class="grid md:grid-cols-3 gap-8">
                    {''.join(team_items_html)}
                </div>"""

            return f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/10 to-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-12">
                <h1 class="text-5xl font-bold mb-6">{company_content['section_heading']}</h1>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">{company_content['section_description']}</p>
            </div>
        </div>
    </section>

    <section class="py-16 bg-white">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto">
                <h2 class="text-3xl font-bold mb-6">{about_data.get('heading', 'Our Story')}</h2>
                <p class="text-lg text-gray-700 mb-4 leading-relaxed">{about_data.get('paragraph1', '')}</p>
                <p class="text-lg text-gray-700 leading-relaxed">{about_data.get('paragraph2', '')}</p>
            </div>
        </div>
    </section>

    <section class="py-16 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">{company_content['values_heading']}</h2>
            {values_html}
        </div>
    </section>

    <section class="py-16 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">{company_content['team_heading']}</h2>
            {team_html}
        </div>
    </section>

    <section class="py-16 bg-gradient-to-r from-{primary} to-{hover} text-white">
        <div class="container mx-auto px-6 text-center">
            <h2 class="text-4xl font-bold mb-4">{company_content['contact_cta']}</h2>
            <p class="text-xl opacity-90 mb-8">{company_content['contact_cta_description']}</p>
            <a href="contact.php" class="inline-block bg-white text-{primary} px-10 py-4 rounded-lg text-lg font-semibold hover:bg-gray-100 transition shadow-lg">{button_labels.get('contact_us', 'Contact Us')}</a>
        </div>
    </section>
</main>"""

        # Вариация 2: Современный дизайн с большими карточками
        elif company_variant == 2:
            # SVG icons для ценностей
            value_icons_v2 = [
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path>',
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>',
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>'
            ]

            # Values section - динамические ценности
            values_items_html_v2 = []
            for i, value in enumerate(company_values[:3]):
                icon = value_icons_v2[i % len(value_icons_v2)]
                values_items_html_v2.append(f"""
                    <div class="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition">
                        <div class="w-14 h-14 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center mb-4">
                            <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                {icon}
                            </svg>
                        </div>
                        <h3 class="text-2xl font-bold mb-3">{value.get('title', '')}</h3>
                        <p class="text-gray-600 leading-relaxed">{value.get('description', '')}</p>
                    </div>""")

            values_html = f"""
                <div class="grid md:grid-cols-3 gap-6">
                    {''.join(values_items_html_v2)}
                </div>"""

            # Team section - динамические члены команды
            if has_team_images:
                team_items_html_v2 = []
                for i, member in enumerate(team_members[:3]):
                    team_items_html_v2.append(f"""
                    <div class="group">
                        <div class="relative overflow-hidden rounded-2xl mb-4">
                            <img src="images/team{i+1}.jpg" alt="Team Member" class="w-full h-80 object-cover group-hover:scale-110 transition-transform duration-300">
                        </div>
                        <h3 class="text-2xl font-bold mb-1">{member.get('name', '')}</h3>
                        <p class="text-{primary} font-semibold mb-2">{member.get('position', '')}</p>
                        <p class="text-gray-600">{member.get('description', '')}</p>
                    </div>""")
                team_html = f"""
                <div class="grid md:grid-cols-3 gap-8">
                    {''.join(team_items_html_v2)}
                </div>"""
            else:
                team_items_html_v2 = []
                for member in team_members[:3]:
                    team_items_html_v2.append(f"""
                    <div class="bg-gradient-to-br from-gray-50 to-white p-8 rounded-2xl border border-gray-100">
                        <h3 class="text-2xl font-bold mb-1">{member.get('name', '')}</h3>
                        <p class="text-{primary} font-semibold mb-3">{member.get('position', '')}</p>
                        <p class="text-gray-600">{member.get('description', '')}</p>
                    </div>""")
                team_html = f"""
                <div class="grid md:grid-cols-3 gap-8">
                    {''.join(team_items_html_v2)}
                </div>"""

            return f"""<main>
    <section class="py-24 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center max-w-4xl mx-auto">
                <h1 class="text-6xl font-bold mb-6 bg-gradient-to-r from-{primary} to-{hover} bg-clip-text text-transparent">{company_content['section_heading']}</h1>
                <p class="text-2xl text-gray-600">{company_content['section_description']}</p>
            </div>
        </div>
    </section>

    <section class="py-20 bg-gradient-to-br from-gray-50 to-white">
        <div class="container mx-auto px-6">
            <div class="max-w-5xl mx-auto">
                <div class="bg-white rounded-3xl shadow-2xl p-12">
                    <h2 class="text-4xl font-bold mb-8 text-center">{about_data.get('heading', 'Our Story')}</h2>
                    <p class="text-xl text-gray-700 mb-6 leading-relaxed">{about_data.get('paragraph1', '')}</p>
                    <p class="text-xl text-gray-700 leading-relaxed">{about_data.get('paragraph2', '')}</p>
                </div>
            </div>
        </div>
    </section>

    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-5xl font-bold text-center mb-16">{company_content['values_heading']}</h2>
            {values_html}
        </div>
    </section>

    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-5xl font-bold text-center mb-16">{company_content['team_heading']}</h2>
            {team_html}
        </div>
    </section>

    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="bg-gradient-to-r from-{primary} to-{hover} rounded-3xl p-16 text-center text-white shadow-2xl">
                <h2 class="text-5xl font-bold mb-6">{company_content['contact_cta']}</h2>
                <p class="text-2xl opacity-95 mb-10 max-w-3xl mx-auto">{company_content['contact_cta_description']}</p>
                <a href="contact.php" class="inline-block bg-white text-{primary} px-12 py-5 rounded-lg text-xl font-bold hover:bg-gray-100 transition shadow-lg">{button_labels.get('contact_us', 'Contact Us')}</a>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 3: Минималистичный дизайн
        elif company_variant == 3:
            # Values section - динамические ценности
            values_items_html_v3 = []
            for value in company_values[:3]:
                values_items_html_v3.append(f"""
                    <div class="border-l-4 border-{primary} pl-6">
                        <h3 class="text-2xl font-bold mb-2">{value.get('title', '')}</h3>
                        <p class="text-gray-600 text-lg">{value.get('description', '')}</p>
                    </div>""")

            values_html = f"""
                <div class="space-y-8">
                    {''.join(values_items_html_v3)}
                </div>"""

            # Team section - динамические члены команды с круглыми аватарами слева
            if has_team_images:
                team_items_html_v3 = []
                for i, member in enumerate(team_members[:3]):
                    team_items_html_v3.append(f"""
                    <div class="flex items-start gap-6">
                        <div class="flex-shrink-0">
                            <img src="images/team{i+1}.jpg" alt="Team Member" class="w-32 h-32 rounded-full object-cover shadow-lg">
                        </div>
                        <div class="flex-1">
                            <h3 class="text-3xl font-bold mb-2">{member.get('name', '')}</h3>
                            <p class="text-{primary} text-xl font-semibold mb-4">{member.get('position', '')}</p>
                            <p class="text-gray-600 text-lg">{member.get('description', '')}</p>
                        </div>
                    </div>""")
                team_html = f"""
                <div class="space-y-8">
                    {''.join(team_items_html_v3)}
                </div>"""
            else:
                team_items_html_v3_no_img = []
                for i, member in enumerate(team_members[:3]):
                    border_class = 'border-b border-gray-200 pb-8' if i < 2 else ''
                    team_items_html_v3_no_img.append(f"""
                    <div class="{border_class}">
                        <h3 class="text-3xl font-bold mb-2">{member.get('name', '')}</h3>
                        <p class="text-{primary} text-xl font-semibold mb-3">{member.get('position', '')}</p>
                        <p class="text-gray-600 text-lg">{member.get('description', '')}</p>
                    </div>""")
                team_html = f"""
                <div class="max-w-4xl mx-auto space-y-8">
                    {''.join(team_items_html_v3_no_img)}
                </div>"""

            return f"""<main>
    <section class="py-32 bg-white">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto">
                <h1 class="text-7xl font-bold mb-8">{company_content['section_heading']}</h1>
                <p class="text-2xl text-gray-600 leading-relaxed">{company_content['section_description']}</p>
            </div>
        </div>
    </section>

    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto">
                <h2 class="text-4xl font-bold mb-8">{about_data.get('heading', 'Our Story')}</h2>
                <div class="space-y-6 text-lg text-gray-700 leading-relaxed">
                    <p>{about_data.get('paragraph1', '')}</p>
                    <p>{about_data.get('paragraph2', '')}</p>
                </div>
            </div>
        </div>
    </section>

    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="max-w-3xl mx-auto">
                <h2 class="text-4xl font-bold mb-12">{company_content['values_heading']}</h2>
                {values_html}
            </div>
        </div>
    </section>

    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold mb-16">{company_content['team_heading']}</h2>
            {team_html}
        </div>
    </section>

    <section class="py-24 bg-{primary} text-white">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto text-center">
                <h2 class="text-5xl font-bold mb-6">{company_content['contact_cta']}</h2>
                <p class="text-2xl opacity-90 mb-10">{company_content['contact_cta_description']}</p>
                <a href="contact.php" class="inline-block bg-white text-{primary} px-12 py-5 rounded-lg text-xl font-bold hover:bg-gray-100 transition">{button_labels.get('contact_us', 'Contact Us')}</a>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 4: Компактный дизайн с акцентом на ценности
        else:
            # SVG icons для ценностей (4 иконки для 4 ценностей)
            value_icons_v4 = [
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>',
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>'
            ]

            # Values section - динамические ценности (показываем до 4 ценностей)
            values_items_html_v4 = []
            num_values = min(len(company_values), 4) if isinstance(company_values, list) else 3
            for i in range(num_values):
                value = company_values[i] if i < len(company_values) else {'title': 'Value', 'description': 'Description'}
                icon = value_icons_v4[i % len(value_icons_v4)]
                values_items_html_v4.append(f"""
                    <div class="flex items-start space-x-4">
                        <div class="w-12 h-12 bg-{primary} rounded-lg flex items-center justify-center flex-shrink-0">
                            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                {icon}
                            </svg>
                        </div>
                        <div>
                            <h3 class="text-xl font-bold mb-2">{value.get('title', '')}</h3>
                            <p class="text-gray-600">{value.get('description', '')}</p>
                        </div>
                    </div>""")

            values_html = f"""
                <div class="grid md:grid-cols-2 gap-8">
                    {''.join(values_items_html_v4)}
                </div>"""

            # Team section - динамические члены команды
            if has_team_images:
                team_items_html_v4 = []
                for i, member in enumerate(team_members[:3]):
                    team_items_html_v4.append(f"""
                    <div>
                        <img src="images/team{i+1}.jpg" alt="Team Member" class="w-full h-64 object-cover rounded-xl mb-4">
                        <h3 class="text-xl font-bold">{member.get('name', '')}</h3>
                        <p class="text-{primary} font-semibold">{member.get('position', '')}</p>
                    </div>""")
                team_html = f"""
                <div class="grid md:grid-cols-3 gap-6">
                    {''.join(team_items_html_v4)}
                </div>"""
            else:
                team_items_html_v4_no_img = []
                for member in team_members[:3]:
                    # Генерируем инициалы из имени
                    name_parts = member.get('name', 'XX').split()
                    initials = ''.join([part[0] for part in name_parts[:2]]).upper() if name_parts else 'XX'
                    team_items_html_v4_no_img.append(f"""
                    <div class="p-6">
                        <div class="w-20 h-20 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                            <span class="text-2xl font-bold text-{primary}">{initials}</span>
                        </div>
                        <h3 class="text-xl font-bold mb-1">{member.get('name', '')}</h3>
                        <p class="text-{primary} font-semibold">{member.get('position', '')}</p>
                    </div>""")
                team_html = f"""
                <div class="grid md:grid-cols-3 gap-6 text-center">
                    {''.join(team_items_html_v4_no_img)}
                </div>"""

            return f"""<main>
    <section class="py-16 bg-white">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto text-center">
                <h1 class="text-5xl font-bold mb-6">{company_content['section_heading']}</h1>
                <p class="text-xl text-gray-600">{company_content['section_description']}</p>
            </div>
        </div>
    </section>

    <section class="py-16 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="max-w-5xl mx-auto">
                <div class="mb-16">
                    <h2 class="text-3xl font-bold mb-6">{about_data.get('heading', 'Our Story')}</h2>
                    <p class="text-lg text-gray-700 mb-4">{about_data.get('paragraph1', '')}</p>
                    <p class="text-lg text-gray-700">{about_data.get('paragraph2', '')}</p>
                </div>

                <div>
                    <h2 class="text-3xl font-bold mb-8">{company_content['values_heading']}</h2>
                    {values_html}
                </div>
            </div>
        </div>
    </section>

    <section class="py-16 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-3xl font-bold text-center mb-12">{company_content['team_heading']}</h2>
            <div class="max-w-5xl mx-auto">
                {team_html}
            </div>
        </div>
    </section>

    <section class="py-16 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto bg-gradient-to-r from-{primary} to-{hover} rounded-2xl p-12 text-center text-white shadow-xl">
                <h2 class="text-4xl font-bold mb-4">{company_content['contact_cta']}</h2>
                <p class="text-xl opacity-90 mb-8">{company_content['contact_cta_description']}</p>
                <a href="contact.php" class="inline-block bg-white text-{primary} px-10 py-4 rounded-lg text-lg font-bold hover:bg-gray-100 transition">{button_labels.get('get_started', 'Get Started')}</a>
            </div>
        </div>
    </section>
</main>"""

    def generate_thankyou_page(self, site_name, primary, hover):
        """Генерация Thanks You страницы с 6 вариациями"""
        theme = self.blueprint.get('theme', 'business')

        # Получаем переводы thank you page через API
        thanks_content = self.generate_theme_content_via_api(theme, "thankyou_content", 1)

        # Fallback если API не вернул результат
        if not thanks_content:
            thanks_content_fallback = {
                'thank_you': 'Thank You!',
                'success': 'Success!',
                'message_sent': 'Message Sent Successfully!',
                'received_message': 'Your message has been sent successfully. We\'ll get back to you soon.',
                'get_back_soon': 'We\'ll get back to you soon.',
                'response_time': 'Expect a response within 24 hours via email.',
                'explore_more_heading': 'While You Wait, Explore More',
                'return_home': 'Return to Homepage',
                'back_home': 'Back to Home',
                'view_services': 'View Services',
                'about_us': 'About Us',
                'blog': 'Blog',
                'what_next': 'What Happens Next?',
                'review_message': 'We Review Your Message',
                'review_description': 'Our team will carefully review your inquiry within the next few hours.',
                'personalized_response': 'Personalized Response',
                'response_description': 'We\'ll prepare a detailed response tailored to your specific needs.',
                'get_back': 'Get Back to You',
                'get_back_description': 'Expect a response from us within 24 hours via email.',
                'thank_contacting': 'Thank you for contacting',
                'email_heading': 'Email',
                'email_subheading': 'Check your inbox',
                'team_heading': 'Our Team',
                'team_subheading': 'Ready to help'
            }
            thanks_content = self.get_localized_fallback('thankyou_content', thanks_content_fallback)

        thanks_variant = random.randint(1, 6)

        # Для лендингов убираем кнопку services.php и блок "While you wait"
        _thanks_services_btn = ('' if self.site_type == 'landing' else
                                f'<a href="services.php" class="inline-block bg-white hover:bg-gray-50 text-{primary} border-2 border-{primary} px-10 py-4 rounded-lg text-lg font-semibold transition transform hover:scale-105">{thanks_content.get("view_services", "View Services")}</a>')

        if self.site_type == 'landing':
            _explore_block = ''
        else:
            _explore_block = (
                '<div class="bg-gray-50 rounded-2xl p-8 mb-10">'
                f'<h2 class="text-xl font-bold mb-6 text-center">{thanks_content.get("explore_more_heading", "While You Wait, Explore More")}</h2>'
                '<div class="grid md:grid-cols-3 gap-4">'
                f'<a href="services.php" class="block p-6 bg-white rounded-xl hover:shadow-lg transition text-center">'
                f'<svg class="w-8 h-8 text-{primary} mx-auto mb-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>'
                f'<p class="font-semibold text-gray-900">{thanks_content.get("view_services", "Our Services")}</p></a>'
                f'<a href="company.php" class="block p-6 bg-white rounded-xl hover:shadow-lg transition text-center">'
                f'<svg class="w-8 h-8 text-{primary} mx-auto mb-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>'
                f'<p class="font-semibold text-gray-900">{thanks_content.get("about_us", "About Us")}</p></a>'
                f'<a href="blog.php" class="block p-6 bg-white rounded-xl hover:shadow-lg transition text-center">'
                f'<svg class="w-8 h-8 text-{primary} mx-auto mb-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>'
                f'<p class="font-semibold text-gray-900">{thanks_content.get("blog", "Blog")}</p></a>'
                '</div></div>'
            )

        # Вариация 1: Простая с иконкой галочки
        if thanks_variant == 1:
            return f"""<main>
    <section class="min-h-screen flex items-center justify-center bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <div class="max-w-2xl mx-auto text-center">
                <div class="w-24 h-24 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-8 shadow-lg">
                    <svg class="w-12 h-12 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                    </svg>
                </div>
                <h1 class="text-5xl md:text-6xl font-bold mb-6">{thanks_content.get('thank_you', 'Thank You!')}</h1>
                <p class="text-xl text-gray-600 mb-8">{thanks_content.get('received_message', "Your message has been sent successfully. We'll get back to you soon.")}</p>
                <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                    {thanks_content.get('return_home', 'Return to Homepage')}
                </a>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 2: Анимированная с конфетти эффектом
        elif thanks_variant == 2:
            return f"""<main>
    <section class="min-h-screen flex items-center justify-center bg-white relative overflow-hidden">
        <div class="absolute inset-0 bg-gradient-to-br from-{primary}/10 via-transparent to-{hover}/10"></div>
        <div class="container mx-auto px-6 relative z-10">
            <div class="max-w-3xl mx-auto text-center">
                <div class="mb-8 animate-bounce">
                    <div class="w-32 h-32 bg-gradient-to-br from-{primary} to-{hover} rounded-full flex items-center justify-center mx-auto shadow-2xl">
                        <svg class="w-16 h-16 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                </div>
                <h1 class="text-6xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-{primary} to-{hover} bg-clip-text text-transparent">
                    {thanks_content.get('success', 'Success!')}
                </h1>
                <p class="text-2xl text-gray-700 mb-4 font-semibold">{thanks_content.get('thank_you', 'Thank you for reaching out!')}</p>
                <p class="text-lg text-gray-600 mb-10">{thanks_content.get('response_time', "We've received your message and will respond within 24 hours.")}</p>
                <div class="flex flex-col sm:flex-row gap-4 justify-center">
                    <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-lg text-lg font-semibold transition transform hover:scale-105 shadow-xl">
                        {thanks_content.get('back_home', 'Back to Home')}
                    </a>
                    {_thanks_services_btn}
                </div>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 3: С таймлайном процесса
        elif thanks_variant == 3:
            return f"""<main>
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto">
                <div class="text-center mb-16">
                    <div class="w-20 h-20 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-10 h-10 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                    </div>
                    <h1 class="text-5xl font-bold mb-4">{thanks_content.get('message_sent', 'Message Sent Successfully!')}</h1>
                    <p class="text-xl text-gray-600">{thanks_content.get('thank_contacting', 'Thank you for contacting')} {site_name}</p>
                </div>

                <div class="bg-white rounded-2xl shadow-xl p-10 mb-12">
                    <h2 class="text-2xl font-bold mb-8 text-center">{thanks_content.get('what_next', 'What Happens Next?')}</h2>
                    <div class="space-y-6">
                        <div class="flex items-start">
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">1</div>
                            <div class="ml-6">
                                <h3 class="text-xl font-bold mb-2">{thanks_content.get('review_message', 'We Review Your Message')}</h3>
                                <p class="text-gray-600">{thanks_content.get('review_description', 'Our team will carefully review your inquiry within the next few hours.')}</p>
                            </div>
                        </div>
                        <div class="flex items-start">
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">2</div>
                            <div class="ml-6">
                                <h3 class="text-xl font-bold mb-2">{thanks_content.get('personalized_response', 'Personalized Response')}</h3>
                                <p class="text-gray-600">{thanks_content.get('response_description', "We'll prepare a detailed response tailored to your specific needs.")}</p>
                            </div>
                        </div>
                        <div class="flex items-start">
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">3</div>
                            <div class="ml-6">
                                <h3 class="text-xl font-bold mb-2">{thanks_content.get('get_back', 'Get Back to You')}</h3>
                                <p class="text-gray-600">{thanks_content.get('get_back_description', 'Expect a response from us within 24 hours via email.')}</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="text-center">
                    <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        {thanks_content.get('return_home', 'Return to Homepage')}
                    </a>
                </div>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 4: Минималистичная
        elif thanks_variant == 4:
            return f"""<main>
    <section class="min-h-screen flex items-center justify-center bg-white">
        <div class="container mx-auto px-6">
            <div class="max-w-xl mx-auto text-center">
                <h1 class="text-7xl md:text-8xl font-bold mb-8 text-{primary}">{thanks_content.get('thank_you', 'Thanks!')}</h1>
                <div class="w-24 h-1 bg-{primary} mx-auto mb-8"></div>
                <p class="text-2xl text-gray-700 mb-4">{thanks_content.get('received_message', "We've received your message.")}</p>
                <p class="text-lg text-gray-600 mb-12">{thanks_content.get('get_back_soon', 'Our team will respond shortly.')}</p>
                <a href="index.php" class="text-{primary} hover:text-{hover} text-lg font-semibold transition border-b-2 border-{primary}">
                    ← {thanks_content.get('back_home', 'Back to Home')}
                </a>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 5: С карточкой контактной информации
        elif thanks_variant == 5:
            return f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/10 to-white">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto">
                <div class="bg-white rounded-3xl shadow-2xl p-12">
                    <div class="text-center mb-12">
                        <div class="inline-block p-4 bg-{primary}/10 rounded-full mb-6">
                            <svg class="w-16 h-16 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                        </div>
                        <h1 class="text-5xl font-bold mb-4">{thanks_content.get('thank_you', 'Thank You!')}</h1>
                        <p class="text-xl text-gray-600">{thanks_content.get('received_message', 'Your message has been successfully sent to our team.')}</p>
                    </div>

                    <div class="border-t border-gray-200 pt-8 mb-8">
                        <div class="grid md:grid-cols-3 gap-6 text-center">
                            <div>
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                                    <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                </div>
                                <p class="font-semibold text-gray-900">{thanks_content.get('response_time', 'Response Time')}</p>
                                <p class="text-sm text-gray-600">{thanks_content.get('get_back_description', 'Within 24 hours')}</p>
                            </div>
                            <div>
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                                    <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                    </svg>
                                </div>
                                <p class="font-semibold text-gray-900">{thanks_content.get('email_heading', 'Email')}</p>
                                <p class="text-sm text-gray-600">{thanks_content.get('email_subheading', 'Check your inbox')}</p>
                            </div>
                            <div>
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                                    <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                                    </svg>
                                </div>
                                <p class="font-semibold text-gray-900">{thanks_content.get('team_heading', 'Our Team')}</p>
                                <p class="text-sm text-gray-600">{thanks_content.get('team_subheading', 'Ready to help')}</p>
                            </div>
                        </div>
                    </div>

                    <div class="text-center pt-4">
                        <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                            {thanks_content.get('back_home', 'Back to Homepage')}
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 6: С социальными сетями и дополнительными ссылками
        else:
            return f"""<main>
    <section class="min-h-screen flex items-center justify-center bg-white">
        <div class="container mx-auto px-6">
            <div class="max-w-3xl mx-auto">
                <div class="text-center mb-12">
                    <div class="relative inline-block mb-8">
                        <div class="w-28 h-28 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center shadow-2xl">
                            <svg class="w-14 h-14 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                            </svg>
                        </div>
                        <div class="absolute -top-2 -right-2 w-8 h-8 bg-{primary} rounded-full animate-ping"></div>
                    </div>
                    <h1 class="text-6xl font-bold mb-6">{thanks_content.get('message_sent', 'Message Received!')}</h1>
                    <p class="text-2xl text-gray-700 mb-3">{thanks_content.get('thank_you', 'Thank you for contacting us.')}</p>
                    <p class="text-lg text-gray-600 mb-10">{thanks_content.get('get_back_soon', "We'll be in touch very soon!")}</p>
                </div>

                {_explore_block}


                <div class="text-center">
                    <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-12 py-4 rounded-full text-lg font-bold transition shadow-xl hover:shadow-2xl transform hover:scale-105">
                        {thanks_content.get('return_home', 'Return to Homepage')}
                    </a>
                </div>
            </div>
        </div>
    </section>
</main>"""

    def generate_services_page(self, site_name, primary, hover):
        """Генерация Services страницы с 4 вариациями"""
        theme = self.blueprint.get('theme', 'business')

        # Получаем переводы services page через API
        services_content = self.generate_theme_content_via_api(theme, "services_page_content", 1)

        # Получаем данные о сервисах (3 для вариаций 1-2, 1 для вариаций 3-4)
        services_data_3 = self.generate_theme_content_via_api(theme, "services", 3)
        services_data_1 = self.generate_theme_content_via_api(theme, "services", 1)

        # Получаем benefits для вариации 3 и 4
        benefits_content = self.generate_theme_content_via_api(theme, "benefits_content", 3)

        # Fallback если API не вернул результат
        if not services_content:
            services_content = {
                'section_heading': 'Our Services',
                'section_description': 'We offer comprehensive solutions tailored to meet your unique needs. Discover how our expertise can help your business grow.',
                'get_started_button': 'Get Started',
                'contact_cta': 'Ready to Get Started?',
                'contact_cta_description': 'Contact us today to discuss how our services can help you achieve your goals and drive success.'
            }

        if not services_data_3:
            services_data_3 = [
                {'title': 'Professional Services', 'description': 'Expert solutions tailored to your needs.'},
                {'title': 'Consultation', 'description': 'Strategic guidance for your business.'},
                {'title': 'Support', 'description': 'Ongoing assistance and maintenance.'}
            ]

        if not services_data_1:
            services_data_1 = [
                {'title': 'Professional Services', 'description': 'Expert solutions tailored to your needs with comprehensive support and guidance.'}
            ]

        if not benefits_content:
            benefits_content = {
                'heading': 'Key Benefits',
                'benefits': [
                    {'title': 'Expert team with years of experience', 'description': ''},
                    {'title': 'Customized approach for every client', 'description': ''},
                    {'title': 'Proven track record of success', 'description': ''}
                ]
            }

        # Используем предвыбранный вариант или выбираем случайно
        services_variant = getattr(self, 'selected_services_variant', random.randint(1, 4))

        # Вариация 1: 3 блока в сетке
        if services_variant == 1:
            service_cards = ""
            for i, service in enumerate(services_data_3, 1):
                service_cards += f"""
                <div class="bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden group">
                    <div class="h-64 overflow-hidden">
                        <img src="images/service{i}.jpg" alt="{service['title']}" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300">
                    </div>
                    <div class="p-8">
                        <h3 class="text-2xl font-bold mb-4">{service['title']}</h3>
                        <p class="text-gray-600 leading-relaxed">{service['description']}</p>
                    </div>
                </div>"""

            return f"""<main>
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h1 class="text-5xl font-bold mb-6">{services_content['section_heading']}</h1>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">{services_content['section_description']}</p>
            </div>

            <div class="grid md:grid-cols-3 gap-8 mb-16">
                {service_cards}
            </div>

            <div class="bg-{primary} text-white rounded-3xl p-12 text-center">
                <h2 class="text-4xl font-bold mb-4">{services_content['contact_cta']}</h2>
                <p class="text-xl opacity-90">{services_content['contact_cta_description']}</p>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 2: 2 блока в сетке
        elif services_variant == 2:
            # Используем только первые 2 сервиса
            services_data_2 = services_data_3[:2]
            service_cards = ""
            for i, service in enumerate(services_data_2, 1):
                service_cards += f"""
                <div class="bg-white rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 overflow-hidden">
                    <div class="h-80 overflow-hidden">
                        <img src="images/service{i}.jpg" alt="{service['title']}" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">
                    </div>
                    <div class="p-10">
                        <h3 class="text-3xl font-bold mb-4 text-gray-900">{service['title']}</h3>
                        <p class="text-gray-600 text-lg leading-relaxed">{service['description']}</p>
                    </div>
                </div>"""

            return f"""<main>
    <section class="py-20 bg-gradient-to-br from-gray-50 to-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-20">
                <h1 class="text-6xl font-bold mb-6 bg-gradient-to-r from-{primary} to-{hover} bg-clip-text text-transparent">{services_content['section_heading']}</h1>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">{services_content['section_description']}</p>
            </div>

            <div class="grid md:grid-cols-2 gap-10 mb-20">
                {service_cards}
            </div>

            <div class="bg-gradient-to-r from-{primary} to-{hover} text-white rounded-3xl p-16 text-center shadow-2xl">
                <h2 class="text-5xl font-bold mb-6">{services_content['contact_cta']}</h2>
                <p class="text-xl opacity-95 max-w-2xl mx-auto">{services_content['contact_cta_description']}</p>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 3: 1 блок с текстом справа
        elif services_variant == 3:
            service = services_data_1[0]
            # Генерируем список benefits из API
            benefits_html = ""
            for benefit in benefits_content.get('benefits', [])[:3]:
                benefits_html += f"""
                            <div class="flex items-start">
                                <svg class="w-6 h-6 text-{primary} mr-3 mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                                </svg>
                                <p class="text-gray-700">{benefit['title']}</p>
                            </div>"""

            return f"""<main>
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h1 class="text-5xl font-bold mb-6">{services_content['section_heading']}</h1>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">{services_content['section_description']}</p>
            </div>

            <div class="max-w-7xl mx-auto mb-20">
                <div class="grid md:grid-cols-2 gap-12 items-center">
                    <div class="order-2 md:order-1">
                        <div class="h-96 rounded-2xl overflow-hidden shadow-2xl">
                            <img src="images/service1.jpg" alt="{service['title']}" class="w-full h-full object-cover">
                        </div>
                    </div>
                    <div class="order-1 md:order-2">
                        <h2 class="text-4xl font-bold mb-6 text-{primary}">{service['title']}</h2>
                        <p class="text-lg text-gray-600 mb-8 leading-relaxed">{service['description']}</p>
                        <div class="space-y-4">{benefits_html}
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-gray-50 rounded-3xl p-12 text-center">
                <h2 class="text-4xl font-bold mb-4">{services_content['contact_cta']}</h2>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">{services_content['contact_cta_description']}</p>
            </div>
        </div>
    </section>
</main>"""

        # Вариация 4: 1 блок с текстом слева
        else:
            service = services_data_1[0]
            # Генерируем список benefits из API
            benefits_list_html = ""
            for benefit in benefits_content.get('benefits', [])[:3]:
                benefits_list_html += f"""
                                <li class="flex items-center">
                                    <div class="w-2 h-2 bg-{primary} rounded-full mr-3"></div>
                                    <span class="text-gray-700">{benefit['title']}</span>
                                </li>"""

            return f"""<main>
    <section class="py-20 bg-gradient-to-br from-white to-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h1 class="text-5xl font-bold mb-6 text-{primary}">{services_content['section_heading']}</h1>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">{services_content['section_description']}</p>
            </div>

            <div class="max-w-7xl mx-auto mb-20">
                <div class="grid md:grid-cols-2 gap-12 items-center">
                    <div>
                        <h2 class="text-4xl font-bold mb-6">{service['title']}</h2>
                        <p class="text-lg text-gray-600 mb-8 leading-relaxed">{service['description']}</p>
                        <div class="bg-white rounded-xl p-8 shadow-lg">
                            <h3 class="text-xl font-bold mb-4">{benefits_content['heading']}</h3>
                            <ul class="space-y-3">{benefits_list_html}
                            </ul>
                        </div>
                    </div>
                    <div>
                        <div class="h-96 rounded-2xl overflow-hidden shadow-2xl transform hover:scale-105 transition-transform duration-300">
                            <img src="images/service1.jpg" alt="{service['title']}" class="w-full h-full object-cover">
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-{primary} text-white rounded-3xl p-12 text-center shadow-2xl">
                <h2 class="text-4xl font-bold mb-4">{services_content['contact_cta']}</h2>
                <p class="text-xl opacity-90 max-w-2xl mx-auto">{services_content['contact_cta_description']}</p>
            </div>
        </div>
    </section>
</main>"""

    def generate_stats_section(self, theme, primary):
        """Генерирует секцию статистики через API с языковой поддержкой"""
        language = self.blueprint.get('language', 'English')

        # Пробуем до 3 раз получить контент от API
        achievements_data = None
        for attempt in range(3):
            if attempt > 0:
                print(f"    ⚠️  Попытка #{attempt + 1} для achievements_content...")
                # Очищаем кэш для этого запроса, чтобы гарантировать новый API вызов
                cache_key = f"{theme}_achievements_content_1_{language}"
                if cache_key in self.theme_content_cache:
                    del self.theme_content_cache[cache_key]

            achievements_data = self.generate_theme_content_via_api(theme, "achievements_content", 1)

            # Проверяем, что мы получили все необходимые поля
            if achievements_data and all(key in achievements_data for key in ['heading', 'stat1_label', 'stat2_label', 'stat3_label', 'stat4_label']):
                print(f"    ✓ achievements_content успешно получен с попытки #{attempt + 1}")
                break

        if not achievements_data:
            # Если все попытки не удались, используем минимальный fallback
            print(f"    ⚠️  Все 3 попытки achievements_content не удались, используем базовый fallback")
            achievements_data_fallback = {
                'heading': 'Stats',
                'stat1_number': '500+',
                'stat1_label': 'Projects',
                'stat2_number': '15+',
                'stat2_label': 'Years',
                'stat3_number': '98%',
                'stat3_label': 'Satisfaction',
                'stat4_number': '50+',
                'stat4_label': 'Team'
            }
            achievements_data = self.get_localized_fallback('achievements_content', achievements_data_fallback)

        return f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center text-white mb-16">{achievements_data.get('heading', 'Stats')}</h2>
            <div class="grid md:grid-cols-4 gap-8">
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">{achievements_data.get('stat1_number', '500+')}</div>
                    <p class="text-white/80 text-lg">{achievements_data.get('stat1_label', 'Projects')}</p>
                </div>
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">{achievements_data.get('stat2_number', '15+')}</div>
                    <p class="text-white/80 text-lg">{achievements_data.get('stat2_label', 'Years')}</p>
                </div>
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">{achievements_data.get('stat3_number', '98%')}</div>
                    <p class="text-white/80 text-lg">{achievements_data.get('stat3_label', 'Satisfaction')}</p>
                </div>
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">{achievements_data.get('stat4_number', '50+')}</div>
                    <p class="text-white/80 text-lg">{achievements_data.get('stat4_label', 'Team')}</p>
                </div>
            </div>
        </div>
    </section>"""

    def generate_benefits_section(self, theme, primary):
        """Генерирует секцию Key Benefits через API с языковой поддержкой"""
        benefits_data = self.generate_theme_content_via_api(theme, "benefits_content", 6)

        # Fallback если API не вернул результат
        if not benefits_data or not benefits_data.get('benefits'):
            benefits_data_fallback = {
                'heading': 'Key Benefits',
                'benefits': [
                    {'title': 'Cost Efficiency', 'description': 'Maximize your ROI with our optimized processes and competitive pricing structure'},
                    {'title': 'Scalability', 'description': 'Solutions designed to grow with your business needs and adapt to market changes'},
                    {'title': '24/7 Support', 'description': 'Round-the-clock assistance to ensure your operations run smoothly'},
                    {'title': 'Expert Team', 'description': 'Skilled professionals with extensive industry experience and certifications'},
                    {'title': 'Quality Assurance', 'description': 'Rigorous testing and quality control at every stage of development'},
                    {'title': 'Innovation', 'description': 'Stay ahead with the latest technologies and industry best practices'}
                ]
            }
            benefits_data = self.get_localized_fallback('benefits_content', benefits_data_fallback)

        heading = benefits_data.get('heading', 'Key Benefits')
        benefits = benefits_data.get('benefits', [])

        # Генерируем карточки преимуществ
        cards_html = ''
        for benefit in benefits[:6]:
            cards_html += f"""
                <div class="p-6 border-l-4 border-{primary} bg-gray-50">
                    <h3 class="text-xl font-bold mb-3">{benefit.get('title', 'Benefit')}</h3>
                    <p class="text-gray-600">{benefit.get('description', 'Description')}</p>
                </div>"""

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-16">{heading}</h2>
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">{cards_html}
            </div>
        </div>
    </section>"""

    def generate_why_choose_us_section(self, theme, primary):
        """Генерирует секцию Why Choose Us через API с языковой поддержкой"""
        benefits_data = self.generate_theme_content_via_api(theme, "benefits_content", 3)

        # Fallback если API не вернул результат
        if not benefits_data or not benefits_data.get('benefits'):
            heading = 'Why Choose Us'
            subheading = 'We deliver exceptional results through our commitment to quality, innovation, and customer satisfaction'
            benefits = [
                {'title': 'Proven Track Record', 'description': 'Over 15 years of delivering successful projects across various industries'},
                {'title': 'Fast Delivery', 'description': 'We understand deadlines and consistently deliver projects on time'},
                {'title': 'Best Value', 'description': 'Competitive pricing without compromising on quality or service'}
            ]
        else:
            heading = benefits_data.get('heading', 'Why Choose Us')
            subheading = benefits_data.get('subheading', 'We deliver exceptional results through our commitment to quality, innovation, and customer satisfaction')
            benefits = benefits_data.get('benefits', [])

        # SVG icons для трех преимуществ
        icons = [
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
        ]

        # Генерируем карточки
        cards_html = ''
        for i, benefit in enumerate(benefits[:3]):
            icon = icons[i] if i < len(icons) else icons[0]
            cards_html += f"""
                <div class="text-center p-6">
                    <div class="w-20 h-20 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-10 h-10 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            {icon}
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-3">{benefit.get('title', 'Benefit')}</h3>
                    <p class="text-gray-600">{benefit.get('description', 'Description')}</p>
                </div>"""

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl font-bold mb-4">{heading}</h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">{subheading}</p>
            </div>
            <div class="grid md:grid-cols-3 gap-8">{cards_html}
            </div>
        </div>
    </section>"""

    def generate_testimonials_section(self, theme, primary):
        """Генерирует секцию отзывов через API с языковой поддержкой"""
        testimonials_data = self.generate_theme_content_via_api(theme, "testimonials_content", 3)

        # Fallback если API не вернул результат
        if not testimonials_data or not testimonials_data.get('testimonials'):
            heading = 'What Our Clients Say'
            testimonials = [
                {'quote': 'Outstanding service and exceptional results. The team went above and beyond to ensure our project success.', 'name': 'John Anderson', 'position': 'CEO', 'company': 'Tech Solutions', 'rating': '5'},
                {'quote': 'Professional, reliable, and highly skilled. They delivered exactly what we needed, on time and within budget.', 'name': 'Sarah Mitchell', 'position': 'Director', 'company': 'Marketing Agency', 'rating': '5'},
                {'quote': 'Excellent communication throughout the project. Their expertise and dedication made all the difference.', 'name': 'Michael Chen', 'position': 'Founder', 'company': 'StartupHub', 'rating': '5'}
            ]
        else:
            heading = testimonials_data.get('heading', 'What Our Clients Say')
            testimonials = testimonials_data.get('testimonials', [])

        # Генерируем карточки отзывов
        cards_html = ''
        for testimonial in testimonials[:3]:
            cards_html += f"""
                <div class="bg-white p-8 rounded-xl shadow-md">
                    <div class="text-{primary} text-4xl mb-4">"</div>
                    <p class="text-gray-600 mb-6">{testimonial.get('quote', 'Great service!')}</p>
                    <div class="flex items-center gap-2 mb-2">
                        <div class="text-yellow-400">★★★★★</div>
                    </div>
                    <p class="font-bold">{testimonial.get('name', 'Client')}</p>
                    <p class="text-gray-500 text-sm">{testimonial.get('position', 'Position')}, {testimonial.get('company', 'Company')}</p>
                </div>"""

        return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-16">{heading}</h2>
            <div class="grid md:grid-cols-3 gap-8">{cards_html}
            </div>
        </div>
    </section>"""

    def generate_cta_section(self, theme, primary):
        """Генерирует секцию Call-to-Action через API с языковой поддержкой"""
        cta_data = self.generate_theme_content_via_api(theme, "cta_content", 1)

        # Fallback если API не вернул результат
        if not cta_data:
            cta_data = {
                'heading': 'Ready to Get Started?',
                'subheading': 'Let us discuss how we can help you achieve your goals and transform your business',
                'button_primary': 'Contact Us Today',
                'button_secondary': 'View Services'
            }

        _cta_contact_btn = ('' if self.site_type == 'landing' else
                            f'<a href="contact.php" class="inline-block bg-white text-{primary} px-8 py-4 rounded-lg font-bold text-lg hover:bg-gray-100 transition shadow-lg">{cta_data.get("button_primary", "Contact Us Today")}</a>')

        return f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <div class="max-w-3xl mx-auto text-center">
                <h2 class="text-4xl font-bold text-white mb-6">{cta_data.get('heading', 'Ready to Get Started?')}</h2>
                <p class="text-white/90 text-xl mb-8">{cta_data.get('subheading', 'Let us discuss how we can help you achieve your goals')}</p>
                <div class="flex justify-center">
                    {_cta_contact_btn}
                </div>
            </div>
        </div>
    </section>"""

    def generate_features_comparison_section(self, theme, primary, hover):
        """Генерирует секцию Features Comparison (What Sets Us Apart) через API с языковой поддержкой"""
        features_data = self.generate_theme_content_via_api(theme, "features_comparison", 1)

        # Fallback если API не вернул результат
        if not features_data or not features_data.get('features'):
            section_heading = 'What Sets Us Apart'
            section_description = 'We combine expertise, innovation, and dedication to deliver exceptional results that exceed expectations.'
            cta_heading = "Let's Build Something Great Together"
            cta_description = 'Contact us today to discuss your project and discover how we can help you achieve your goals.'
            cta_button = 'Start Your Project'
            features = [
                {'heading': 'Industry-Leading Expertise', 'description': 'Our team brings years of specialized experience to every project'},
                {'heading': 'Customized Solutions', 'description': 'Tailored approaches designed specifically for your unique needs'},
                {'heading': 'Results-Driven Approach', 'description': 'Focused on delivering measurable outcomes and ROI'},
                {'heading': 'Ongoing Partnership', 'description': 'Long-term support and collaboration beyond project completion'}
            ]
        else:
            section_heading = features_data.get('section_heading', 'What Sets Us Apart')
            section_description = features_data.get('section_description', 'We combine expertise, innovation, and dedication to deliver exceptional results.')
            cta_heading = features_data.get('cta_heading', "Let's Build Something Great Together")
            cta_description = features_data.get('cta_description', 'Contact us today to discuss your project.')
            cta_button = features_data.get('cta_button', 'Start Your Project')
            features = features_data.get('features', [])

        _features_cta_btn = ('' if self.site_type == 'landing' else
                             f'<a href="contact.php" class="inline-block bg-white text-{primary} px-8 py-4 rounded-lg font-bold hover:bg-gray-100 transition">{cta_button}</a>')

        # Генерируем список фич
        features_html = ''
        for feature in features[:4]:
            features_html += f"""
                        <div class="flex gap-4">
                            <div class="flex-shrink-0 w-6 h-6 bg-{primary} rounded-full flex items-center justify-center">
                                <svg class="w-4 h-4 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-bold text-lg mb-1">{feature.get('heading', 'Feature')}</h3>
                                <p class="text-gray-600">{feature.get('description', 'Description')}</p>
                            </div>
                        </div>"""

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h2 class="text-4xl font-bold mb-6">{section_heading}</h2>
                    <p class="text-gray-600 text-lg mb-8">{section_description}</p>
                    <div class="space-y-4">{features_html}
                    </div>
                </div>
                <div>
                    <div class="bg-gradient-to-br from-{primary} to-{hover} rounded-xl p-12 text-white">
                        <h3 class="text-3xl font-bold mb-6">{cta_heading}</h3>
                        <p class="text-white/90 mb-8">{cta_description}</p>
                        {_features_cta_btn}
                    </div>
                </div>
            </div>
        </div>
    </section>"""

    def generate_contact_form_section(self, theme, primary, hover):
        """Генерирует секцию контактной формы через API с языковой поддержкой"""
        contact_data = self.generate_theme_content_via_api(theme, "contact_page_content", 1)

        # Fallback если API не вернул результат
        if not contact_data:
            contact_data = {
                'heading': 'Get Started Today',
                'subheading': 'Tell us about your project and we will get back to you soon',
                'name_label': 'Your Name',
                'email_label': 'Your Email',
                'phone_label': 'Phone Number',
                'message_label': 'Tell Us About Your Project',
                'submit_button': 'Send Message'
            }

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6 max-w-3xl">
            <div class="text-center mb-12">
                <h2 class="text-4xl font-bold mb-4">{contact_data.get('heading', 'Get Started Today')}</h2>
                <p class="text-gray-600 text-lg">{contact_data.get('subheading', 'Tell us about your project')}</p>
            </div>
            <div class="bg-gray-50 rounded-xl p-8 shadow-lg">
                <form action="thanks_you.php" method="POST" class="space-y-6">
                    <div>
                        <label for="name" class="block text-gray-700 font-semibold mb-2">{contact_data.get('name_label', 'Your Name')}</label>
                        <input type="text" id="name" name="name" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                    </div>
                    <div>
                        <label for="email" class="block text-gray-700 font-semibold mb-2">{contact_data.get('email_label', 'Your Email')}</label>
                        <input type="email" id="email" name="email" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                    </div>
                    <div>
                        <label for="phone" class="block text-gray-700 font-semibold mb-2">{contact_data.get('phone_label', 'Phone Number')}</label>
                        <input type="tel" id="phone" name="phone" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                    </div>
                    <div>
                        <label for="message" class="block text-gray-700 font-semibold mb-2">{contact_data.get('message_label', 'Tell Us About Your Project')}</label>
                        <textarea id="message" name="message" rows="4" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent"></textarea>
                    </div>
                    <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        {contact_data.get('submit_button', 'Send Message')}
                    </button>
                </form>
            </div>
        </div>
    </section>"""

    def generate_two_images_right_section(self, site_name, theme, primary, hover):
        """Генерирует секцию с двумя изображениями справа и контентом слева с кнопкой на Contact"""
        # Получаем контент через API
        content_data = self.generate_theme_content_via_api(theme, "two_images_section", 1)

        if not content_data:
            content_data = {
                'heading': 'Reduce Your Expenses by 50%',
                'description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.',
                'button_text': 'Learn More'
            }

        _two_images_btn = ('' if self.site_type == 'landing' else
                           f'<a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">{content_data.get("button_text", "Learn More")} →</a>')

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h2 class="text-5xl font-bold mb-6 text-gray-900">{content_data.get('heading', 'Reduce Your Expenses by 50%')}</h2>
                    <p class="text-gray-600 text-lg mb-8 leading-relaxed">{content_data.get('description', 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.')}</p>
                    {_two_images_btn}
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-4">
                        <img src="images/workspace1.jpg" alt="Professional work" class="rounded-2xl shadow-lg w-full h-64 object-cover">
                    </div>
                    <div class="space-y-4 mt-8">
                        <img src="images/workspace2.jpg" alt="Team collaboration" class="rounded-2xl shadow-lg w-full h-64 object-cover">
                    </div>
                </div>
            </div>
        </div>
    </section>"""

    def generate_contact_form_with_benefits_section(self, theme, primary, hover):
        """Генерирует секцию с контактной формой справа и преимуществами слева"""
        # Получаем контент через API
        form_data = self.generate_theme_content_via_api(theme, "contact_form_benefits", 1)
        benefits_data = self.generate_theme_content_via_api(theme, "benefits_list", 3)

        if not form_data:
            form_data_fallback = {
                'heading': 'Transform Business Growth with Revolutionary Services',
                'description': 'We specialize in investing in technological startups in the field of rear view. Duis aute irure dolor in osaedeut za sladoestrastie velit esse cilum dolore eu fugiat nulla pariatur. Excepteur sint osaedeut cupidatat not proident, sunt in culpa qui officia deserunt mollit anim id est Laborum.',
                'name_label': 'Enter your Name',
                'email_label': 'Enter a valid email address',
                'message_label': 'Message',
                'submit_button': 'Connect With Us',
                'form_heading': 'Order a Free Consultation'
            }
            form_data = self.get_localized_fallback('contact_form_benefits', form_data_fallback)

        if not benefits_data:
            benefits_data_fallback = [
                {'title': 'Strategic Roadmap Planning'},
                {'title': 'Cloud Solutions Implementation'},
                {'title': 'Data-Driven Understanding'}
            ]
            benefits_data = self.get_localized_fallback('benefits_list', benefits_data_fallback)

        benefits_html = ""
        for benefit in benefits_data:
            benefits_html += f"<li class=\"flex items-start\"><span class=\"text-{primary} mr-3 text-xl\">•</span><span class=\"text-lg\">{benefit.get('title', '')}</span></li>\n                    "

        return f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-start">
                <div class="text-white">
                    <h2 class="text-4xl font-bold mb-6">{form_data.get('heading', 'Transform Business Growth')}</h2>
                    <p class="text-white opacity-90 mb-8 leading-relaxed">{form_data.get('description', 'We offer comprehensive solutions.')}</p>
                    <ul class="space-y-4 text-white">
                        {benefits_html}
                    </ul>
                </div>
                <div class="bg-white rounded-2xl p-8 shadow-2xl">
                    <h3 class="text-2xl font-bold mb-6">{form_data.get('form_heading', 'Order a Free Consultation')}</h3>
                    <form action="thanks_you.php" method="POST" class="space-y-6">
                        <div>
                            <input type="text" id="name" name="name" placeholder="{form_data.get('name_label', 'Enter your Name')}" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                        </div>
                        <div>
                            <input type="email" id="email" name="email" placeholder="{form_data.get('email_label', 'Enter a valid email address')}" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                        </div>
                        <div>
                            <textarea id="message" name="message" rows="4" placeholder="{form_data.get('message_label', 'Message')}" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent"></textarea>
                        </div>
                        <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                            {form_data.get('submit_button', 'Connect With Us')}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </section>"""

    def generate_four_images_grid_section(self, site_name, theme, primary, hover):
        """Генерирует секцию с 4 изображениями в сетке с кнопкой на Services"""
        content_data = self.generate_theme_content_via_api(theme, "four_images_section", 1)

        if not content_data:
            content_data = {
                'heading': 'Complete HR Management Support Services',
                'description': 'Dignissim suspendisse in est ante in nibh mauris. Varius quam quisque id diam vel quam elementum pulvinar etiam. Nunc pulvinar sapien et ligula ullamcorper malesuada proin. Nunc mattis enim ut tellus elementum.',
                'button_text': 'Read More'
            }

        return f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div class="grid grid-cols-2 gap-6">
                    <div class="space-y-6">
                        <img src="images/service1.jpg" alt="Service 1" class="rounded-xl shadow-lg w-full h-48 object-cover">
                        <img src="images/service3.jpg" alt="Service 3" class="rounded-xl shadow-lg w-full h-48 object-cover">
                    </div>
                    <div class="space-y-6 mt-8">
                        <img src="images/service2.jpg" alt="Service 2" class="rounded-xl shadow-lg w-full h-48 object-cover">
                        <img src="images/service4.jpg" alt="Service 4" class="rounded-xl shadow-lg w-full h-48 object-cover" onerror="this.src='images/gallery1.jpg'">
                    </div>
                </div>
                <div class="text-white">
                    <h2 class="text-5xl font-bold mb-6">{content_data.get('heading', 'Complete HR Management Support Services')}</h2>
                    <p class="text-white opacity-90 mb-8 text-lg leading-relaxed">{content_data.get('description', 'Professional services tailored to your needs.')}</p>
                </div>
            </div>
        </div>
    </section>"""

    def generate_our_team_section(self, site_name, theme, primary):
        """Генерирует секцию Our Team с портретами членов команды"""
        # Получаем данные команды через API с контекстом "home_section" для уникальных имен
        team_section_data = self.generate_theme_content_via_api(theme, "team_section_content", 1)
        team_data = self.generate_theme_content_via_api(theme, "team_members", 3, page_context="home_section")

        if not team_section_data:
            team_section_fallback = {
                'heading': 'Our Amazing Team'
            }
            team_section_data = self.get_localized_fallback('team_section_content', team_section_fallback)

        if not team_data:
            team_data_fallback = [
                {'name': 'Nat Reynolds', 'position': 'Worldwide Partner', 'gender': 'male'},
                {'name': 'Jennie Roberts', 'position': 'Partner', 'gender': 'female'},
                {'name': 'Mila Parker', 'position': 'Partner', 'gender': 'female'}
            ]
            team_data = self.get_localized_fallback('team_members', team_data_fallback)

        # Генерируем карточки команды
        team_cards = ""
        for i, member in enumerate(team_data, 1):
            team_cards += f"""
                <div class="bg-white rounded-2xl shadow-lg overflow-hidden">
                    <div class="h-80 overflow-hidden bg-gray-100">
                        <img src="images/team{i}.jpg" alt="{member.get('name', 'Team Member')}" class="w-full h-full object-cover" onerror="this.src='images/about.jpg'">
                    </div>
                    <div class="p-8 text-center">
                        <h3 class="text-2xl font-bold mb-2">{member.get('name', 'Team Member')}</h3>
                        <p class="text-gray-600 font-semibold mb-4">{member.get('position', 'Team Member')}</p>
                    </div>
                </div>"""

        return f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-5xl font-bold text-white mb-4">{team_section_data.get('heading', 'Our Amazing Team')}</h2>
            </div>
            <div class="grid md:grid-cols-3 gap-8">
                {team_cards}
            </div>
        </div>
    </section>"""

    def generate_two_images_right_no_button_section(self, site_name, theme, primary):
        """Генерирует секцию с двумя изображениями справа и контентом слева без кнопки"""
        content_data = self.generate_theme_content_via_api(theme, "two_images_no_button", 1)

        if not content_data:
            content_data_fallback = {
                'heading': 'Real-world Solutions Designed Just for You',
                'description': 'Dignissim suspendisse in est ante in nibh mauris. Varius quam quisque id diam vel quam elementum pulvinar etiam. Nunc pulvinar sapien et ligula ullamcorper malesuada proin. Nunc mattis enim ut tellus elementum.'
            }
            content_data = self.get_localized_fallback('two_images_no_button', content_data_fallback)

        # Randomly choose between 3 background variations
        import random
        bg_variation = random.choice(['dark', 'light', 'primary'])

        if bg_variation == 'dark':
            # Dark background (original)
            bg_class = "bg-gray-900"
            text_class = "text-white"
            desc_class = "text-gray-300"
        elif bg_variation == 'light':
            # Light/white background
            bg_class = "bg-white"
            text_class = "text-gray-900"
            desc_class = "text-gray-600"
        else:
            # Primary color background
            bg_class = f"bg-{primary}"
            text_class = "text-white"
            desc_class = "text-white/90"

        return f"""
    <section class="py-20 {bg_class} {text_class}">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h2 class="text-5xl font-bold mb-6">{content_data.get('heading', 'Real-world Solutions Designed Just for You')}</h2>
                    <p class="{desc_class} text-lg leading-relaxed">{content_data.get('description', 'Professional solutions tailored to your needs.')}</p>
                </div>
                <div class="grid grid-cols-1 gap-6">
                    <img src="images/service1.jpg" alt="Professional work" class="rounded-2xl shadow-2xl w-full h-64 object-cover">
                    <img src="images/service2.jpg" alt="Team collaboration" class="rounded-2xl shadow-2xl w-full h-64 object-cover">
                </div>
            </div>
        </div>
    </section>"""

    def generate_qna_with_image_section(self, site_name, theme, primary):
        """Генерирует секцию Q&A с изображением справа и вопросами-ответами слева"""
        # Получаем FAQ данные через API
        faq_data = self.generate_theme_content_via_api(theme, "faq_content", 4)

        if not faq_data or not isinstance(faq_data, dict) or 'items' not in faq_data:
            faq_data_fallback = {
                'heading': 'What drives us',
                'description': 'Discover the key areas where we excel and deliver exceptional value to our clients.',
                'items': [
                    {'question': '01. Recruitment Staffing', 'answer': 'Answer. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur id suscipit ex. Suspendisse rhoncus laoreet purus quis elementum. Phasellus sed efficitur dolor, et ultricies sapien. Quisque fringilla sit amet dolor commodo efficitur. Aliquam et sem odio. In ullamcorper nisi nunc, et molestie ipsum iaculis sit amet.'},
                    {'question': '02. Compensation Management', 'answer': 'Expert compensation strategies tailored to your organization.'},
                    {'question': '03. Training Development', 'answer': 'Comprehensive training programs for employee growth.'},
                    {'question': '04. Performance Management', 'answer': 'Effective performance evaluation and improvement systems.'}
                ]
            }
            faq_data = self.get_localized_fallback('faq_content', faq_data_fallback)

        # Генерируем HTML для Q&A items
        qa_items = ""
        for i, item in enumerate(faq_data.get('items', [])[:4]):
            is_first = i == 0
            qa_items += f"""
                <div class="border-b border-gray-200">
                    <button class="w-full text-left py-6 flex justify-between items-center focus:outline-none group" onclick="toggleAccordion(this)">
                        <span class="text-xl font-bold text-gray-900">{item.get('question', f'Question {i+1}')}</span>
                        <svg class="w-6 h-6 transform transition-transform duration-200 group-hover:text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>
                    <div class="accordion-content overflow-hidden transition-all duration-300 {'max-h-96' if is_first else 'max-h-0'}">
                        <div class="pb-6 text-gray-600 leading-relaxed">
                            {item.get('answer', 'Answer content here.')}
                        </div>
                    </div>
                </div>"""

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-12">
                <h2 class="text-5xl font-bold mb-4">{faq_data.get('heading', 'What drives us')}</h2>
                <p class="text-gray-600 text-lg">{faq_data.get('description', 'Find answers to your questions.')}</p>
            </div>
            <div class="grid md:grid-cols-2 gap-12 items-start">
                <div class="space-y-2">
                    {qa_items}
                </div>
                <div class="sticky top-6">
                    <img src="images/service1.jpg" alt="Professional service" class="rounded-2xl shadow-2xl w-full h-full object-cover" style="max-height: 600px;">
                </div>
            </div>
        </div>
    </section>
    <script>
    function toggleAccordion(button) {{
        const content = button.nextElementSibling;
        const icon = button.querySelector('svg');
        const allContents = document.querySelectorAll('.accordion-content');
        const allIcons = document.querySelectorAll('.accordion-content').forEach(item => {{
            if (item !== content) {{
                item.style.maxHeight = '0';
                item.previousElementSibling.querySelector('svg').style.transform = 'rotate(0deg)';
            }}
        }});
        if (content.style.maxHeight === '0px' || !content.style.maxHeight) {{
            content.style.maxHeight = content.scrollHeight + 'px';
            icon.style.transform = 'rotate(180deg)';
        }} else {{
            content.style.maxHeight = '0';
            icon.style.transform = 'rotate(0deg)';
        }}
    }}
    </script>"""

    def generate_contact_form_with_office_image_section(self, theme, primary, hover):
        """Генерирует секцию контактной формы с изображением офиса справа"""
        # Получаем контент через API
        form_data = self.generate_theme_content_via_api(theme, "contact_form_quick", 1)

        if not form_data:
            form_data_fallback = {
                'heading': 'Quick Online Consultancy',
                'description': '',
                'first_name_label': 'First Name',
                'last_name_label': 'Last Name',
                'email_label': 'Email Address',
                'message_label': 'Message',
                'submit_button': 'Send Message'
            }
            form_data = self.get_localized_fallback('contact_form_quick', form_data_fallback)

        return f"""
    <section class="py-20 bg-gray-900">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div class="bg-white rounded-2xl p-10 shadow-2xl">
                    <h2 class="text-4xl font-bold mb-4">{form_data.get('heading', 'Quick Online Consultancy')}</h2>
                    {'<p class="text-gray-600 mb-8">' + form_data.get('description', '') + '</p>' if form_data.get('description', '') else ''}
                    <form action="thanks_you.php" method="POST" class="space-y-6">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <input type="text" id="first_name" name="first_name" placeholder="{form_data.get('first_name_label', 'First Name')}" required class="w-full px-4 py-3 border-b-2 border-gray-300 focus:border-{primary} focus:outline-none transition">
                            </div>
                            <div>
                                <input type="text" id="last_name" name="last_name" placeholder="{form_data.get('last_name_label', 'Last Name')}" required class="w-full px-4 py-3 border-b-2 border-gray-300 focus:border-{primary} focus:outline-none transition">
                            </div>
                        </div>
                        <div>
                            <input type="email" id="email" name="email" placeholder="{form_data.get('email_label', 'Email Address')}" required class="w-full px-4 py-3 border-b-2 border-gray-300 focus:border-{primary} focus:outline-none transition">
                        </div>
                        <div>
                            <textarea id="message" name="message" rows="4" placeholder="{form_data.get('message_label', 'Message')}" class="w-full px-4 py-3 border-b-2 border-gray-300 focus:border-{primary} focus:outline-none transition"></textarea>
                        </div>
                        <button type="submit" class="w-full bg-gray-900 hover:bg-gray-800 text-white py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                            {form_data.get('submit_button', 'Send Message')}
                        </button>
                    </form>
                </div>
                <div class="h-full">
                    <img src="images/service2.jpg" alt="Office environment" class="rounded-2xl shadow-2xl w-full h-full object-cover" style="min-height: 500px;">
                </div>
            </div>
        </div>
    </section>"""

    def generate_image_with_benefits_section(self, site_name, theme, primary, hover):
        """Генерирует секцию с фото и текстом слева, преимуществами справа"""
        # Получаем контент через API
        content_data = self.generate_theme_content_via_api(theme, "image_benefits_section", 1)
        benefits_data = self.generate_theme_content_via_api(theme, "benefits_icons", 3)

        if not content_data:
            content_data_fallback = {
                'heading': 'Our Commitment to Excellence',
                'description': 'We deliver exceptional results through innovative solutions, expert knowledge, and dedicated service. Our team combines years of industry experience with cutting-edge approaches to provide value that exceeds expectations.',
                'button_text': 'Learn More'
            }
            content_data = self.get_localized_fallback('image_benefits_content', content_data_fallback)

        if not benefits_data:
            benefits_data_fallback = [
                {
                    'icon': '⚖️',
                    'title': 'What We Do',
                    'description': 'We provide comprehensive solutions tailored to your unique needs. Our services combine industry expertise with innovative approaches to deliver measurable results and sustainable growth.'
                },
                {
                    'icon': '🏛️',
                    'title': 'Who We Are',
                    'description': 'A team of dedicated professionals committed to excellence. We bring together diverse expertise, proven experience, and a passion for helping our clients achieve their goals.'
                },
                {
                    'icon': '⚖️',
                    'title': 'How We Differ',
                    'description': 'Our client-focused approach sets us apart. We prioritize transparency, communication, and collaboration to ensure every project delivers exceptional value and lasting impact.'
                }
            ]
            benefits_data = self.get_localized_fallback('image_benefits_blocks', benefits_data_fallback)

        benefits_html = ""
        for benefit in benefits_data:
            benefits_html += f"""
                <div class="mb-8">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mb-4">
                        <svg class="w-8 h-8 text-{primary}" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"></path>
                            <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-2 text-gray-900">{benefit.get('title', 'Benefit')}</h3>
                    <p class="text-gray-600">{benefit.get('description', 'Sample text.')}</p>
                </div>"""

        # Для travel тематики используем benefits.jpg, для остальных - service3.jpg
        theme_lower = theme.lower()
        if 'travel' in theme_lower or 'tour' in theme_lower or 'voyage' in theme_lower or 'tourism' in theme_lower:
            image_file = 'benefits.jpg'
            image_alt = 'Travel destination'
        else:
            image_file = 'service3.jpg'
            image_alt = 'Professional service'

        _benefits_btn = ('' if self.site_type == 'landing' else
                         f'<a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">{content_data.get("button_text", "View More")}</a>')

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-start">
                <div>
                    <h2 class="text-5xl font-bold mb-6 text-gray-900">{content_data.get('heading', 'Make legal better')}</h2>
                    <div class="mb-8">
                        <img src="images/{image_file}" alt="{image_alt}" class="rounded-xl shadow-2xl w-full h-80 object-cover">
                    </div>
                    <p class="text-gray-600 text-lg mb-8 leading-relaxed">{content_data.get('description', 'Professional services description.')}</p>
                    {_benefits_btn}
                </div>
                <div class="text-gray-900">
                    {benefits_html}
                </div>
            </div>
        </div>
    </section>"""

    def generate_what_we_offer_variant_section(self, site_name, theme, primary):
        """Генерирует вариацию секции What We Offer с сеткой карточек"""
        # Получаем переводы для заголовка и кнопок
        what_we_offer_data = self.generate_theme_content_via_api(theme, "what_we_offer_content", 1)
        if not what_we_offer_data:
            what_we_offer_data_fallback = {
                'variant_heading': 'We serve our clients around the globe',
                'read_more': 'Read More'
            }
            what_we_offer_data = self.get_localized_fallback('what_we_offer_content', what_we_offer_data_fallback)

        variant_heading = what_we_offer_data.get('variant_heading', 'We serve our clients around the globe')
        read_more_text = what_we_offer_data.get('read_more', 'Read More')

        # Получаем контент через API
        offers_data = self.generate_theme_content_via_api(theme, "what_we_offer_variant", 6)

        if not offers_data or not isinstance(offers_data, list):
            offers_data_fallback = [
                {'title': 'Finance Awards', 'description': 'Professional financial advisory and recognition services.'},
                {'title': 'Life sciences and healthcare', 'description': 'Innovative solutions for healthcare industry.'},
                {'title': 'Responsible Business', 'description': 'Sustainable and ethical business practices.'},
                {'title': 'Join Us', 'description': 'Become part of our growing team.'},
            ]
            offers_data = self.get_localized_fallback('what_we_offer_variant', offers_data_fallback)

        # Генерируем карточки
        cards_html = ""
        card_configs = [
            {'bg': 'white', 'text': 'gray-900', 'has_button': False, 'has_image': False},
            {'bg': primary, 'text': 'white', 'has_button': True, 'has_image': False},
            {'bg': 'white', 'text': 'gray-900', 'has_button': False, 'has_image': False},
            {'bg': 'white', 'text': 'gray-900', 'has_button': False, 'has_image': True},
            {'bg': 'white', 'text': 'gray-900', 'has_button': False, 'has_image': False},
            {'bg': 'white', 'text': 'gray-900', 'has_button': False, 'has_image': True},
        ]

        for i, (offer, config) in enumerate(zip(offers_data[:6], card_configs)):
            card_class = f"bg-{config['bg']} text-{config['text']}" if config['bg'] != primary else f"bg-{primary} text-white"

            if config['has_image']:
                cards_html += f"""
                <div class="overflow-hidden rounded-xl shadow-lg">
                    <img src="images/gallery{(i % 3) + 1}.jpg" alt="{offer.get('title', 'Service')}" class="w-full h-full object-cover" style="min-height: 300px;">
                </div>"""
            else:
                button_html = ""

                cards_html += f"""
                <div class="{card_class} p-8 rounded-xl shadow-lg flex flex-col justify-center" style="min-height: 300px;">
                    <h3 class="text-3xl font-bold mb-4">{offer.get('title', 'Service Title')}</h3>
                    <p class="{'text-white' if config['bg'] == primary else 'text-gray-600'} leading-relaxed">{offer.get('description', 'Sample text.')}</p>
                    {button_html}
                </div>"""

        return f"""
    <section class="py-20 bg-gray-900">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-5xl font-bold text-white mb-4">{variant_heading}</h2>
            </div>
            <div class="grid md:grid-cols-3 gap-8">
                {cards_html}
            </div>
        </div>
    </section>"""

    def generate_testimonials_with_image_section(self, site_name, theme, primary):
        """Генерирует секцию отзывов с изображением слева"""
        # Получаем отзывы через API
        testimonials_api_data = self.generate_theme_content_via_api(theme, "testimonials_content", 4)

        # Обрабатываем данные из API
        if testimonials_api_data and isinstance(testimonials_api_data, dict):
            heading = testimonials_api_data.get('heading', 'What Our Clients Say')
            testimonials_list = testimonials_api_data.get('testimonials', [])
        else:
            heading = None
            testimonials_list = []

        # Если данных нет, используем fallback с переводом
        if not testimonials_list:
            heading_fallback = 'What Our Clients Say'
            heading = self.get_localized_fallback('testimonials_heading', heading_fallback)

            testimonials_fallback = [
                {
                    'quote': 'The consulting firm provided exceptional service and valuable insights that significantly contributed to the success of our project. Their team demonstrated deep expertise in the field, delivering innovative solutions tailored to our specific needs.',
                    'name': 'Nat Reynolds',
                    'position': 'Developer',
                    'company': 'co-founder'
                },
                {
                    'quote': 'Outstanding work and dedication. The team understood our requirements perfectly and delivered beyond our expectations with creative and efficient solutions.',
                    'name': 'Sarah Mitchell',
                    'position': 'Project Manager',
                    'company': 'Tech Solutions Inc'
                },
                {
                    'quote': 'Professional approach and excellent communication throughout the project. Their expertise helped us achieve our goals on time and within budget.',
                    'name': 'Michael Chen',
                    'position': 'CTO',
                    'company': 'Innovation Labs'
                },
                {
                    'quote': 'Highly recommend their services. The quality of work and attention to detail exceeded our expectations. A true partner in our success.',
                    'name': 'Emily Johnson',
                    'position': 'CEO',
                    'company': 'Growth Ventures'
                }
            ]
            testimonials_list = self.get_localized_fallback('testimonials_list', testimonials_fallback)

        # Определяем какое изображение использовать (для travel темы - testimonials.jpg)
        theme_lower = theme.lower()
        if ('travel' in theme_lower or 'tour' in theme_lower or 'voyage' in theme_lower or 'tourism' in theme_lower) and self._has_image('testimonials.jpg'):
            testimonial_image = 'testimonials.jpg'
        else:
            testimonial_image = 'service1.jpg'

        # Генерируем HTML для всех отзывов
        testimonials_html = ""
        for idx, testimonial in enumerate(testimonials_list):
            quote = testimonial.get('quote', 'Great service and professional team.')
            name = testimonial.get('name', 'Client Name')

            display_style = '' if idx == 0 else 'style="display: none;"'

            testimonials_html += f"""
                        <div class="testimonial-item" {display_style}>
                            <div class="text-8xl text-white opacity-30 absolute -top-8 -left-4">"</div>
                            <div class="relative z-10 pl-8">
                                <p class="text-xl italic mb-8 leading-relaxed">{quote}</p>
                                <div class="mb-6">
                                    <h4 class="text-2xl font-bold">{name}</h4>
                                </div>
                            </div>
                        </div>"""

        return f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <img src="images/{testimonial_image}" alt="Client testimonial" class="rounded-2xl shadow-2xl w-full h-full object-cover" style="min-height: 500px;">
                </div>
                <div class="text-white">
                    <h2 class="text-5xl font-bold mb-12">{heading}</h2>
                    <div class="relative testimonials-carousel">
{testimonials_html}
                        <div class="flex gap-4 mt-8 pl-8">
                            <button onclick="previousTestimonial()" class="w-12 h-12 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition">
                                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                                </svg>
                            </button>
                            <button onclick="nextTestimonial()" class="w-12 h-12 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full flex items-center justify-center transition">
                                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <script>
        let currentTestimonial = 0;
        const testimonials = document.querySelectorAll('.testimonial-item');

        function showTestimonial(index) {{
            testimonials.forEach((testimonial, i) => {{
                testimonial.style.display = i === index ? 'block' : 'none';
            }});
        }}

        function nextTestimonial() {{
            currentTestimonial = (currentTestimonial + 1) % testimonials.length;
            showTestimonial(currentTestimonial);
        }}

        function previousTestimonial() {{
            currentTestimonial = (currentTestimonial - 1 + testimonials.length) % testimonials.length;
            showTestimonial(currentTestimonial);
        }}
    </script>"""

    def generate_hero_mission_variant_section(self, site_name, theme, primary, hover):
        """Генерирует hero секцию с миссией и call-to-action блоками"""
        # Получаем контент через API
        hero_data = self.generate_theme_content_via_api(theme, "hero_mission_variant", 1)
        mission_data = self.generate_theme_content_via_api(theme, "mission_content", 1)
        cta_data = self.generate_theme_content_via_api(theme, "cta_bottom_block", 1)

        # Извлекаем первый элемент, если API вернул список
        if isinstance(hero_data, list) and len(hero_data) > 0:
            hero_data = hero_data[0]
        if isinstance(mission_data, list) and len(mission_data) > 0:
            mission_data = mission_data[0]
        if isinstance(cta_data, list) and len(cta_data) > 0:
            cta_data = cta_data[0]

        if not hero_data:
            hero_data_fallback = {
                'heading': 'We are always beginner friendly',
                'description': 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.',
                'button_text': 'Read More'
            }
            hero_data = self.get_localized_fallback('hero_mission_variant', hero_data_fallback)

        if not mission_data:
            # Темо-специфичные миссии
            theme_lower = theme.lower()
            if 'travel' in theme_lower or 'tour' in theme_lower:
                mission_data_fallback = {
                    'label': 'Our Mission',
                    'heading': 'Explore',
                    'heading_second': 'Every Corner',
                    'subheading': 'Every Journey'
                }
            elif 'fitness' in theme_lower or 'gym' in theme_lower or 'sport' in theme_lower:
                mission_data_fallback = {
                    'label': 'Our Mission',
                    'heading': 'Run',
                    'heading_second': '',
                    'subheading': 'Every Morning'
                }
            elif 'food' in theme_lower or 'restaurant' in theme_lower or 'cafe' in theme_lower:
                mission_data_fallback = {
                    'label': 'Our Mission',
                    'heading': 'Serve Fresh',
                    'heading_second': '',
                    'subheading': 'Every Day'
                }
            elif 'education' in theme_lower or 'learning' in theme_lower:
                mission_data_fallback = {
                    'label': 'Our Mission',
                    'heading': 'Learn New',
                    'heading_second': '',
                    'subheading': 'Every Day'
                }
            else:
                mission_data_fallback = {
                    'label': 'Our Mission',
                    'heading': 'Excel',
                    'heading_second': '',
                    'subheading': 'Every Day'
                }
            mission_data = self.get_localized_fallback('mission_content', mission_data_fallback)

        if not cta_data:
            cta_data_fallback = {
                'heading': 'Future Run Club',
                'description': 'A 2 to 4 mile Central Park run followed by brunch! As always, all levels are welcomed, and the goal is to meet some new running buddies and have fun.',
                'button_text': 'Join Now'
            }
            cta_data = self.get_localized_fallback('cta_bottom_block', cta_data_fallback)

        _mission_cta_btn = ('' if self.site_type == 'landing' else
                            f'<a href="contact.php" class="inline-block bg-white text-{primary} hover:bg-gray-100 px-6 py-3 rounded-lg font-semibold transition">{cta_data.get("button_text", "Join Now")}</a>')

        return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-3 gap-8 items-stretch">
                <div class="flex flex-col justify-center">
                    <h1 class="text-5xl font-bold mb-6 text-{primary}">{hero_data.get('heading', 'We are always beginner friendly')}</h1>
                    <p class="text-gray-600 mb-8 leading-relaxed">{hero_data.get('description', 'Professional services description.')}</p>
                </div>

                <div class="flex flex-col gap-8">
                    <div class="text-white p-8 rounded-2xl flex flex-col justify-center" style="background: linear-gradient(135deg, #C8985A 0%, #B8885A 100%);">
                        <p class="text-sm uppercase tracking-wider mb-4 opacity-90">{mission_data.get('label', 'Our Mission')}</p>
                        <h2 class="text-6xl font-bold mb-2">{mission_data.get('heading', 'Excel')}</h2>
                        <p class="text-xl uppercase tracking-wide">{mission_data.get('subheading', 'Every Day')}</p>
                    </div>

                    <div class="bg-{primary} text-white p-8 rounded-2xl flex flex-col justify-between">
                        <div>
                            <h3 class="text-2xl font-bold mb-4">{cta_data.get('heading', 'Join Us Today')}</h3>
                            <p class="text-white opacity-90 mb-6 leading-relaxed">{cta_data.get('description', 'Get in touch with us.')}</p>
                        </div>
                        <div>
                            {_mission_cta_btn}
                        </div>
                    </div>
                </div>

                <div class="flex items-stretch">
                    <img src="images/hero.jpg" alt="{site_name}" class="rounded-2xl shadow-2xl w-full h-full object-cover" style="min-height: 500px;">
                </div>
            </div>
        </div>
    </section>"""

    def select_home_sections(self):
        """Выбор секций для Home страницы без генерации контента"""
        # Все доступные секции
        all_section_keys = [
            'image_text_about', 'gallery_centered', 'cards_3_animated',
            'image_text_alternating', 'cards_6_grid', 'work_showcase',
            'cards_3_carousel_bg', 'carousel_workflow', 'carousel_blog',
            'contact_form_multistep', 'stats_section', 'why_choose_us',
            'faq_section', 'approach_section', 'benefits_grid',
            'testimonials_text', 'cta_centered', 'features_list',
            'two_images_right', 'contact_form_benefits', 'four_images_grid',
            'our_team', 'two_images_no_button', 'qna_with_image',
            'contact_form_office_image', 'image_with_benefits',
            'what_we_offer_variant', 'testimonials_with_image', 'hero_mission_variant'
        ]

        # Для лендинга убираем блог-секцию
        if self.site_type == 'landing':
            all_section_keys = [k for k in all_section_keys if k != 'carousel_blog']

        # Секции, требующие изображений
        sections_requiring_gallery = {'gallery_centered'}

        # Фильтруем доступные секции
        available_section_keys = list(all_section_keys)

        # Выбираем 5-6 случайных секций
        random.shuffle(available_section_keys)
        num_sections = random.randint(5, 6)
        num_sections = min(num_sections, len(available_section_keys))
        selected_sections = available_section_keys[:num_sections]

        # Все типы контактных форм
        contact_form_types = ['contact_form_multistep', 'contact_form_benefits', 'contact_form_office_image']

        # Находим все контактные формы в выбранных секциях
        selected_contact_forms = [cf for cf in contact_form_types if cf in selected_sections]

        # Если выбрано несколько контактных форм, оставляем только одну (первую)
        if len(selected_contact_forms) > 1:
            for cf in selected_contact_forms[1:]:
                selected_sections.remove(cf)

        # Все типы FAQ секций
        faq_types = ['faq_section', 'qna_with_image']

        # Находим все FAQ секции в выбранных секциях
        selected_faq_sections = [faq for faq in faq_types if faq in selected_sections]

        # Если выбрано несколько FAQ секций, оставляем только одну (первую)
        if len(selected_faq_sections) > 1:
            for faq in selected_faq_sections[1:]:
                selected_sections.remove(faq)

        # Определяем, какая контактная форма и FAQ секция остались
        contact_form = selected_contact_forms[0] if selected_contact_forms else None
        faq_section = selected_faq_sections[0] if selected_faq_sections else None
        has_work_showcase = 'work_showcase' in selected_sections

        # Перемещаем work_showcase, FAQ и Contact Form в конец в правильном порядке
        # Порядок: обычные секции -> work_showcase -> FAQ -> contact_form
        if contact_form:
            selected_sections.remove(contact_form)
        if faq_section:
            selected_sections.remove(faq_section)
        if has_work_showcase:
            selected_sections.remove('work_showcase')

        # Проверяем, что benefits_grid не является последней секцией
        # Последней секцией должна быть контактная форма, work_showcase, four_images_grid или image_with_benefits
        allowed_last_sections = ['contact_form_multistep', 'contact_form_benefits', 'contact_form_office_image',
                                 'work_showcase', 'four_images_grid', 'image_with_benefits']

        # Если benefits_grid последний в списке и нет contact_form, FAQ или work_showcase, переместим его
        if selected_sections and selected_sections[-1] == 'benefits_grid':
            # Пытаемся найти разрешенную секцию для перемещения в конец
            last_section_candidate = None
            for section in ['four_images_grid', 'image_with_benefits']:
                if section in selected_sections:
                    last_section_candidate = section
                    break

            # Если нашли подходящую секцию, меняем местами
            if last_section_candidate:
                selected_sections.remove(last_section_candidate)
                selected_sections.append(last_section_candidate)

        # Добавляем в конец в правильном порядке
        # Порядок: work_showcase -> faq_section -> contact_form
        if has_work_showcase:
            selected_sections.append('work_showcase')
        if faq_section:
            selected_sections.append(faq_section)
        if contact_form:
            selected_sections.append(contact_form)

        return selected_sections

    def calculate_required_images(self):
        """Подсчет необходимых изображений на основе выбранных секций и страниц"""
        required = set()

        # Hero всегда нужен
        required.add('hero.jpg')

        # Services страница - всегда минимум 3 изображения
        if self.site_type == "multipage":
            # Всегда генерируем минимум 3 изображения для Services, независимо от варианта
            required.update(['service1.jpg', 'service2.jpg', 'service3.jpg'])

        # Blog изображения
        if self.site_type == "multipage":
            for i in range(1, self.num_blog_articles + 1):
                required.add(f'blog{i}.jpg')

        # Gallery секция - только если выбрана
        if 'gallery_centered' in self.selected_home_sections:
            required.update(['gallery1.jpg', 'gallery2.jpg', 'gallery3.jpg'])

        # About секции
        if 'image_text_about' in self.selected_home_sections:
            required.add('about.jpg')

        # Company страница team изображения теперь опциональные (не включаем в required)
        # Они будут генерироваться только если есть место после обязательных изображений

        return len(required)

    def generate_home_sections(self):
        """Генерация выбранных секций для Home страницы"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        country = self.blueprint.get('country', 'USA')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        # Все доступные секции
        all_sections = {
            'image_text_about': self.generate_about_us_section(site_name, theme, primary, hover),
            'gallery_centered': self.generate_gallery_section(site_name, theme, primary, hover),
            'cards_3_animated': self.generate_services_cards_section(site_name, theme, primary, hover),
            'image_text_alternating': self.generate_image_text_alternating_section(site_name, theme, primary, hover),
            'cards_6_grid': self.generate_what_we_offer_section(site_name, theme, primary, hover),
            'work_showcase': self.generate_work_showcase_section(site_name, theme, primary, hover),
            'cards_3_carousel_bg': self.generate_featured_solutions_section(site_name, theme, primary, hover),
            'carousel_workflow': self.generate_our_process_section(site_name, theme, primary, hover),
            'carousel_blog': self.generate_blog_preview_section(site_name, theme, primary, hover),
            'contact_form_multistep': self.generate_contact_form_section(theme, primary, hover),
            'stats_section': self.generate_stats_section(theme, primary),
            'why_choose_us': self.generate_why_choose_us_section(theme, primary),
            'faq_section': self.generate_faq_section(theme, primary),
            'approach_section': self.generate_our_approach_section(theme, primary),
            'benefits_grid': self.generate_benefits_section(theme, primary),
            'testimonials_text': self.generate_testimonials_section(theme, primary),
            'cta_centered': self.generate_cta_section(theme, primary),
            'features_list': self.generate_features_comparison_section(theme, primary, hover),
            'two_images_right': self.generate_two_images_right_section(site_name, theme, primary, hover),
            'contact_form_benefits': self.generate_contact_form_with_benefits_section(theme, primary, hover),
            'four_images_grid': self.generate_four_images_grid_section(site_name, theme, primary, hover),
            'our_team': self.generate_our_team_section(site_name, theme, primary),
            'two_images_no_button': self.generate_two_images_right_no_button_section(site_name, theme, primary),
            'qna_with_image': self.generate_qna_with_image_section(site_name, theme, primary),
            'contact_form_office_image': self.generate_contact_form_with_office_image_section(theme, primary, hover),
            'image_with_benefits': self.generate_image_with_benefits_section(site_name, theme, primary, hover),
            'what_we_offer_variant': self.generate_what_we_offer_variant_section(site_name, theme, primary),
            'testimonials_with_image': self.generate_testimonials_with_image_section(site_name, theme, primary),
            'hero_mission_variant': self.generate_hero_mission_variant_section(site_name, theme, primary, hover),
        }

        # Используем предвыбранные секции
        selected_sections = getattr(self, 'selected_home_sections', [])
        if not selected_sections:
            # Fallback если секции не были выбраны
            selected_sections = self.select_home_sections()
            self.selected_home_sections = selected_sections

        # Возвращаем выбранные секции
        return '\n'.join([all_sections[key] for key in selected_sections if key in all_sections])

    def generate_page(self, page_name, output_dir):
        """Генерация страницы с максимальным качеством"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        language = self.blueprint.get('language', 'English')  # Получаем язык из blueprint

        # Для policy страниц используем готовый контент
        if page_name in ['privacy', 'terms', 'cookie']:
            return self.generate_policy_page(page_name, output_dir)

        # Для blog страниц используем готовый контент
        if page_name in ['blog1', 'blog2', 'blog3', 'blog4', 'blog5', 'blog6']:
            return self.generate_blog_page(page_name, output_dir)
        
        # Для главной страницы blog (список статей)
        if page_name == 'blog':
            return self.generate_blog_main_page(output_dir)

        # Для Contact страницы используем готовый профессиональный шаблон
        if page_name == 'contact':
            return self.generate_contact_page(output_dir)

        # Языковая инструкция для всех промптов
        language_requirement = f"\n\nCRITICAL LANGUAGE REQUIREMENT: Generate ALL content (headings, text, buttons, labels) EXCLUSIVELY in {language}. Every single word MUST be in {language}. This is MANDATORY."

        # Определяем промпт для Company в зависимости от наличия team изображений
        # Team изображения генерируются с приоритетом 'required', поэтому всегда доступны
        has_team_images = True

        if has_team_images:
            # Если есть team изображения - используем их
            company_prompt = f"""Create a professional COMPANY page for {site_name} - a {theme} business.

REQUIREMENTS:
- Heading section with page title
- Company story/mission section with rich, UNIQUE text content:
  * Create a COMPLETELY ORIGINAL company history - DO NOT use generic templates
  * Include specific founding year (between 2005-2015), specific founding location, founder motivation
  * Describe unique challenges the founders faced and how they overcame them
  * Explain company's growth journey with specific milestones
  * Mission statement should be industry-specific and unique to {theme}
  * Make it feel like a real, authentic company story with personality and character
- Our Fundamental Values section with 3 value cards (NO images, use icons):
  * Each card should have an icon, heading, and description
  * Values like: Passion, Authenticity, Excellence (or similar industry-appropriate values)
  * Icons using SVG (e.g., heart icon for Passion, location icon for Authenticity, mountain/trophy icon for Excellence)
  * Cards should be in a responsive grid (3 columns on desktop, 1 column on mobile)
- Team section with 3 team member cards, each with:
  * Image: images/team1.jpg, images/team2.jpg, images/team3.jpg
  * Name and role/title (ONLY - NO icons, NO additional decorations)
  * Brief description
  * Clean, minimal design with NO icons in team cards
- MUST include a call-to-action button at the bottom that redirects to contact.php: <a href="contact.php" class="...">Contact Us</a>
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Responsive design with grid layout for team cards
- NO emojis, NO prices

CRITICAL:
- Values section comes BEFORE team section
- Values section MUST have a translated heading like "Our Fundamental Values" or "Our Core Values"
- MUST use images/team1.jpg, images/team2.jpg, images/team3.jpg for team members
- Team cards should be in a responsive grid (3 columns on desktop, 1 column on mobile)
- Team cards MUST NOT include any icons - only image, name, role/title, and description
- Page MUST have a CTA button at the bottom that links to contact.php{language_requirement}

Return ONLY the content for <main> tag."""
        else:
            # Если нет team изображений - используем текстовые блоки без изображений
            company_prompt = f"""Create a professional COMPANY page for {site_name} - a {theme} business.

REQUIREMENTS:
- Heading section with page title
- Company story/mission section with rich, UNIQUE text content:
  * Create a COMPLETELY ORIGINAL company history - DO NOT use generic templates
  * Include specific founding year (between 2005-2015), specific founding location, founder motivation
  * Describe unique challenges the founders faced and how they overcame them
  * Explain company's growth journey with specific milestones
  * Mission statement should be industry-specific and unique to {theme}
  * Make it feel like a real, authentic company story with personality and character
- Our Fundamental Values section with 3 value cards (NO images, use icons):
  * Each card should have an icon, heading, and description
  * Values like: Passion, Authenticity, Excellence (or similar industry-appropriate values)
  * Icons using SVG (e.g., heart icon for Passion, location icon for Authenticity, mountain/trophy icon for Excellence)
  * Cards should be in a responsive grid (3 columns on desktop, 1 column on mobile)
- Team section with descriptive text-based cards (NO images, NO icons)
  * ONLY name, role/title, and brief description for each team member
  * Clean, text-only design with NO icons, NO decorative elements
  * Simple, professional typography-based cards
- MUST include a call-to-action button at the bottom that redirects to contact.php: <a href="contact.php" class="...">Contact Us</a>
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Responsive design
- NO emojis, NO prices

CRITICAL:
- Values section MUST have a translated heading like "Our Fundamental Values" or "Our Core Values"
- Team section MUST NOT include any icons - use ONLY text (name, role, description)
- Focus on storytelling through well-crafted text sections
- Page MUST have a CTA button at the bottom that links to contact.php{language_requirement}

Return ONLY the content for <main> tag."""

        # Для основных страниц генерируем через API с детальными промптами
        page_configs = {
            'index': {
                'title': 'Home',
                'prompt': f"""Create a professional HOME page for {site_name} - a {theme} website.

REQUIREMENTS:
- Hero section with eye-catching headline and CTA button that links to contact.php
- CTA button MUST use: href="contact.php" (NOT #services or any other link)
- Features/benefits section (3-4 features with icons)
- About Us preview section with:
  * MUST include an image on the right side: <img src="images/about.jpg" alt="About Us" class="...">
  * Text content on the left describing the company
  * "Learn More" button that links to company.php: <a href="company.php" class="...">Learn More</a>
  * Responsive grid layout (text left, image right on desktop; stacked on mobile)
- Services showcase section (3 services) with CTA buttons to contact.php
- Testimonials section (2-3 testimonials with circular avatar badges containing initials, NO images)
- For testimonials: use colored circles with white text initials (e.g. JD, MS) instead of photos
- Call-to-action section at the end with button to contact.php
- ALL other CTA buttons on the page MUST link to contact.php (except the About Us "Learn More" which goes to company.php)
- Use images for hero, about section, and services (images/hero.jpg, images/about.jpg, images/service1.jpg)
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Include proper spacing, padding, and responsive design
- NO emojis, NO prices, NO currency symbols

CRITICAL: About Us section MUST have images/about.jpg image and "Learn More" button linking to company.php
CRITICAL: Every OTHER button on this page MUST have href="contact.php"
CRITICAL: Testimonials MUST use avatar circles with initials, NOT images{language_requirement}

Return ONLY the content for <main> tag (not full HTML)."""
            },
            'company': {
                'title': 'Company',
                'prompt': company_prompt  # Используем динамический промпт
            },
            'services': {
                'title': 'Services',
                'prompt': f"""Create a professional SERVICES page for {site_name} - a {theme} business.

REQUIREMENTS:
- Heading section with page title and subtitle
- Grid of EXACTLY 3 service cards in a single row
- Each card: image, title, description, and "Get Started" button linking to contact.php
- Use images: images/service1.jpg, images/service2.jpg, images/service3.jpg
- ALL buttons MUST link to contact.php (NOT "Learn More", use "Get Started", "Contact Us", or "Request Info")
- Call-to-action section at the bottom with button linking to contact.php
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Responsive grid layout (3 columns on desktop, 1 on mobile)
- NO emojis, NO prices, NO currency

CRITICAL:
- MUST use ONLY 3 service cards (service1.jpg, service2.jpg, service3.jpg)
- Cards should have consistent height and professional design
- ALL buttons (on cards AND bottom CTA) MUST link to contact.php
- Do NOT use "Learn More" text, use alternatives like "Get Started", "Contact Us", "Request Quote"{language_requirement}

Return ONLY the content for <main> tag."""
            },
            'thanks_you': {
                'title': 'Thank You',
                'prompt': f"""Create a simple THANK YOU page for {site_name}.

REQUIREMENTS:
- Large "Thank You" heading
- Message: "Your message has been sent successfully. We'll get back to you soon."
- Button to return to homepage (href="index.php")
- Simple, clean design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Centered layout
- NO emojis{language_requirement}

Return ONLY the content for <main> tag."""
            }
        }

        config = page_configs.get(page_name)
        if not config:
            print(f"    ⚠️  Неизвестная страница: {page_name}")
            return False

        # Для index страницы используем готовые секции со случайным выбором
        if page_name == 'index':
            print(f"    📝 Генерация Home страницы со случайными секциями...")
            primary = colors.get('primary', 'blue-600')
            hover = colors.get('hover', 'blue-700')

            # Hero секция (5 вариаций со случайным выбором)
            hero_section = self.generate_hero_section(site_name, theme, primary, hover)

            # Добавляем случайные секции
            random_sections = self.generate_home_sections()

            # Собираем main_content
            main_content = hero_section + random_sections + "\n</main>"
        elif page_name == 'thanks_you':
            print(f"    📝 Генерация Thank You страницы (1 из 6 вариаций)...")
            primary = colors.get('primary', 'blue-600')
            hover = colors.get('hover', 'blue-700')

            # Генерируем одну из 6 вариаций
            main_content = self.generate_thankyou_page(site_name, primary, hover)
        elif page_name == 'services':
            print(f"    📝 Генерация Services страницы (1 из 4 вариаций)...")
            primary = colors.get('primary', 'blue-600')
            hover = colors.get('hover', 'blue-700')

            # Генерируем одну из 4 вариаций
            main_content = self.generate_services_page(site_name, primary, hover)
        elif page_name == 'company':
            print(f"    📝 Генерация Company страницы (1 из 4 вариаций)...")
            primary = colors.get('primary', 'blue-600')
            hover = colors.get('hover', 'blue-700')

            # Генерируем одну из 4 вариаций
            main_content = self.generate_company_page(site_name, primary, hover)
        else:
            # Генерируем контент через API для других страниц
            print(f"    📝 Генерация контента для {page_name}...")
            response = self.call_api(config['prompt'], max_tokens=8000)

            if response:
                main_content = self.clean_code_response(response)
                # Оборачиваем в main если нужно
                if not main_content.strip().startswith('<main'):
                    main_content = f"<main>\n{main_content}\n</main>"
            else:
                print(f"    ⚠️  API не ответил, используется fallback")
                main_content = self.generate_fallback_content(page_name, site_name, colors)
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем, что header и footer созданы
        if not hasattr(self, 'header_code') or not self.header_code or not hasattr(self, 'footer_code') or not self.footer_code:
            print(f"    ⚠️  Header/Footer не найдены для {page_name}, регенерация...")
            self.generate_header_footer()

        # Еще одна проверка - если footer всё ещё пустой, создаем минимальный
        if not self.footer_code:
            print(f"    ⚠️  Footer всё ещё пустой для {page_name}, создание минимального footer...")
            self.footer_code = f"""<footer class="bg-gray-900 text-white py-8 mt-auto">
    <div class="container mx-auto px-6 text-center">
        <p class="font-bold text-lg mb-2">{site_name}</p>
        <div class="flex flex-wrap justify-center gap-4 text-sm">
            <a href="index.php" class="text-gray-400 hover:text-blue-400">Home</a>
            <a href="company.php" class="text-gray-400 hover:text-blue-400">Company</a>
            <a href="services.php" class="text-gray-400 hover:text-blue-400">Services</a>
            <a href="contact.php" class="text-gray-400 hover:text-blue-400">Contact</a>
        </div>
        <p class="text-gray-400 text-sm mt-4">&copy; 2025 {site_name}. All rights reserved.</p>
    </div>
</footer>"""

        # Собираем полную страницу
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config['title']} - {site_name}</title>
    <link rel="icon" type="image/svg+xml" href="{self.get_favicon_url()}">
    {self.header_footer_css}
</head>
<body>
    {self.header_code}

    {main_content}

    {self.footer_code}
</body>
</html>"""
        
        # Сохраняем файл
        page_path = os.path.join(output_dir, f"{page_name}.php")
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        print(f"    ✓ {page_name}.php создана")
        return True
    
    def generate_fallback_content(self, page_name, site_name, colors):
        """Генерация fallback контента для страницы"""
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')
        
        fallbacks = {
            'index': f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/10 to-white">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto text-center">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Welcome to {site_name}</h1>
                <p class="text-xl md:text-2xl text-gray-600 mb-8">Your trusted partner in excellence</p>
                <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                    Get Started
                </a>
            </div>
        </div>
    </section>
    
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Why Choose Us</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="text-center p-6">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Quality Service</h3>
                    <p class="text-gray-600">We deliver exceptional quality in everything we do.</p>
                </div>
                <div class="text-center p-6">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Fast Delivery</h3>
                    <p class="text-gray-600">Quick turnaround times without compromising quality.</p>
                </div>
                <div class="text-center p-6">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Expert Team</h3>
                    <p class="text-gray-600">Experienced professionals dedicated to your success.</p>
                </div>
            </div>
        </div>
    </section>
    
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center max-w-6xl mx-auto">
                <div>
                    <h2 class="text-4xl font-bold mb-6">About {site_name}</h2>
                    <p class="text-xl text-gray-600 mb-8">
                        We are dedicated to providing excellent service and building lasting relationships with our clients. 
                        Our team brings years of experience and expertise to every project.
                    </p>
                    {'<a href="company.php" class="inline-block bg-' + primary + ' hover:bg-' + hover + ' text-white px-8 py-4 rounded-lg text-lg font-semibold transition">Learn More</a>' if self.site_type != 'landing' else ''}
                </div>
                <div class="rounded-xl overflow-hidden shadow-lg">
                    <img src="images/about.jpg" alt="About Us" class="w-full h-full object-cover">
                </div>
            </div>
        </div>
    </section>
    
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Our Services</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="bg-white p-8 rounded-xl shadow-lg hover:shadow-xl transition">
                    <h3 class="text-2xl font-bold mb-4">Service One</h3>
                    <p class="text-gray-600 mb-4">Comprehensive solutions tailored to your needs.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold">Get Started →</a>
                </div>
                <div class="bg-white p-8 rounded-xl shadow-lg hover:shadow-xl transition">
                    <h3 class="text-2xl font-bold mb-4">Service Two</h3>
                    <p class="text-gray-600 mb-4">Professional expertise you can trust.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold">Get Started →</a>
                </div>
                <div class="bg-white p-8 rounded-xl shadow-lg hover:shadow-xl transition">
                    <h3 class="text-2xl font-bold mb-4">Service Three</h3>
                    <p class="text-gray-600 mb-4">Innovative solutions for modern challenges.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold">Get Started →</a>
                </div>
            </div>
        </div>
    </section>
    
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">What Our Clients Say</h2>
            <div class="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
                <div class="bg-white p-8 rounded-xl shadow-lg">
                    <p class="text-gray-600 mb-6 italic">"Excellent service and professional team. Highly recommended!"</p>
                    <div class="flex items-center">
                        <div class="w-12 h-12 rounded-full bg-{primary} flex items-center justify-center text-white font-bold mr-4">
                            JS
                        </div>
                        <div>
                            <p class="font-bold">John Smith</p>
                            <p class="text-sm text-gray-500">CEO, Tech Corp</p>
                        </div>
                    </div>
                </div>
                <div class="bg-white p-8 rounded-xl shadow-lg">
                    <p class="text-gray-600 mb-6 italic">"They exceeded our expectations in every way. Amazing results!"</p>
                    <div class="flex items-center">
                        <div class="w-12 h-12 rounded-full bg-{primary} flex items-center justify-center text-white font-bold mr-4">
                            SJ
                        </div>
                        <div>
                            <p class="font-bold">Sarah Johnson</p>
                            <p class="text-sm text-gray-500">Founder, StartupXYZ</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <section class="py-20 bg-gradient-to-br from-{primary} to-{hover} text-white">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto text-center">
                <h2 class="text-4xl font-bold mb-6">Ready to Get Started?</h2>
                <p class="text-xl mb-8 opacity-90">Contact us today and let's discuss how we can help you achieve your goals.</p>
                <a href="contact.php" class="inline-block bg-white text-{primary} px-8 py-4 rounded-lg text-lg font-semibold hover:bg-gray-100 transition">
                    Contact Us Now
                </a>
            </div>
        </div>
    </section>
</main>""",
            'company': f"""<main>
    <section class="py-20">
        <div class="container mx-auto px-6">
            <h1 class="text-5xl font-bold text-center mb-12">Company - {site_name}</h1>
            <div class="max-w-4xl mx-auto">
                <p class="text-xl text-gray-600 mb-6">
                    We are dedicated to providing excellent service and building lasting relationships with our clients.
                </p>
                <p class="text-xl text-gray-600 mb-8">
                    Our team of professionals brings years of experience and expertise to every project.
                </p>
                <div class="text-center mt-12">
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                        Contact Us
                    </a>
                </div>
            </div>
        </div>
    </section>
</main>""",
            'services': f"""<main>
    <section class="py-20">
        <div class="container mx-auto px-6">
            <h1 class="text-5xl font-bold text-center mb-12">Our Services</h1>
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
                <div class="bg-white p-8 rounded-xl shadow-lg">
                    <h3 class="text-2xl font-bold mb-4">Service One</h3>
                    <p class="text-gray-600 mb-4">Comprehensive solution for your needs.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold">Learn More →</a>
                </div>
                <div class="bg-white p-8 rounded-xl shadow-lg">
                    <h3 class="text-2xl font-bold mb-4">Service Two</h3>
                    <p class="text-gray-600 mb-4">Professional expertise you can trust.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold">Learn More →</a>
                </div>
                <div class="bg-white p-8 rounded-xl shadow-lg">
                    <h3 class="text-2xl font-bold mb-4">Service Three</h3>
                    <p class="text-gray-600 mb-4">Innovative solutions for modern challenges.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold">Learn More →</a>
                </div>
            </div>
        </div>
    </section>
</main>""",
            'contact': f"""<main>
    <section class="py-20">
        <div class="container mx-auto px-6">
            <h1 class="text-5xl font-bold text-center mb-12">Contact Us</h1>
            <div class="max-w-2xl mx-auto">
                <form action="thanks_you.php" method="POST" class="space-y-6">
                    <div>
                        <label class="block text-gray-700 font-semibold mb-2">Name</label>
                        <input type="text" name="name" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-{primary}">
                    </div>
                    <div>
                        <label class="block text-gray-700 font-semibold mb-2">Email</label>
                        <input type="email" name="email" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-{primary}">
                    </div>
                    <div>
                        <label class="block text-gray-700 font-semibold mb-2">Message</label>
                        <textarea name="message" rows="5" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-{primary}"></textarea>
                    </div>
                    <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                        Send Message
                    </button>
                </form>
            </div>
        </div>
    </section>
</main>""",
            'thanks_you': f"""<main>
    <section class="py-20">
        <div class="container mx-auto px-6">
            <div class="max-w-2xl mx-auto text-center">
                <h1 class="text-5xl font-bold mb-6">Thank You!</h1>
                <p class="text-xl text-gray-600 mb-8">Your message has been sent successfully. We'll get back to you soon.</p>
                <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                    Return to Home
                </a>
            </div>
        </div>
    </section>
</main>"""
        }
        
        return fallbacks.get(page_name, f'<main><section class="py-20"><div class="container mx-auto px-6 text-center"><h1 class="text-4xl font-bold">{page_name.title()}</h1></div></section></main>')
    
    def generate_blog_page(self, page_name, output_dir):
        """Генерация blog страниц с вариациями (с/без картинки, с/без стрелок)

        КРИТИЧЕСКИ ВАЖНО: Заголовки, изображения и даты ВСЕГДА синхронизируются с blog_posts_previews
        для согласованности между главной страницей, blog.php и отдельными статьями.
        """
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        # Определяем номер статьи (1-6)
        article_number = int(page_name.replace('blog', ''))

        # Получаем переводы для blog navigation
        blog_nav_data = self.generate_theme_content_via_api(theme, "blog_navigation_content", 1)
        if not blog_nav_data:
            blog_nav_data = {
                'interested_services': 'Interested in Our Services?',
                'get_in_touch_today': 'Get in touch with us today to learn how we can help your business grow.',
                'contact_us': 'Contact Us',
                'previous_article': 'Previous Article',
                'next_article': 'Next Article',
                'published_on': 'Published on'
            }
        interested_services = blog_nav_data.get('interested_services', 'Interested in Our Services?')
        get_in_touch_today = blog_nav_data.get('get_in_touch_today', 'Get in touch with us today to learn how we can help your business grow.')
        contact_us = blog_nav_data.get('contact_us', 'Contact Us')
        previous_article = blog_nav_data.get('previous_article', 'Previous Article')
        next_article = blog_nav_data.get('next_article', 'Next Article')
        published_on = blog_nav_data.get('published_on', 'Published on')

        # КРИТИЧЕСКИ ВАЖНО: Используем заголовки и даты из blog_posts_previews для синхронизации
        # Это гарантирует, что заголовки на главной странице, blog.php и отдельных статьях совпадают
        if hasattr(self, 'blueprint') and 'blog_posts_previews' in self.blueprint:
            blog_posts_previews = self.blueprint['blog_posts_previews']
            # Находим данные для текущей статьи (индекс = article_number - 1)
            if article_number <= len(blog_posts_previews):
                article_preview = blog_posts_previews[article_number - 1]
                blog_title = article_preview['title']
                article_date = article_preview['date']
            else:
                # Fallback если статьи нет в списке
                blog_title = f'{theme} Article {article_number}'
                article_date = 'November 2025'
        else:
            # Fallback если blog_posts_previews не существует
            fallback_titles = {
                'blog1': f'The Future of {theme}',
                'blog2': f'Top 5 Trends in {theme}',
                'blog3': f'How to Choose the Right {theme} Service',
                'blog4': f'Best Practices for {theme} Success',
                'blog5': f'Common {theme} Mistakes to Avoid',
                'blog6': f'The Complete {theme} Guide'
            }
            blog_title = fallback_titles.get(page_name, f'{theme} Article')
            article_date = 'November 2025'

        # Генерируем ТОЛЬКО контент статьи через API (не заголовок и дату!)
        article_data = self.generate_theme_content_via_api(theme, "blog_article_full", article_number)

        blog_titles = {page_name: blog_title}

        # Генерируем контент из API или используем fallback
        if article_data and article_data.get('sections'):
            # Формируем HTML из API данных
            content_html = f'<p class="text-lg text-gray-700 mb-6">{article_data.get("intro_paragraph", "")}</p>\n'
            for section in article_data.get('sections', []):
                content_html += f'<h2 class="text-2xl font-bold mt-8 mb-4">{section.get("heading", "")}</h2>\n'
                content_html += f'<p class="text-gray-700 mb-6">{section.get("content", "")}</p>\n'
            blog_contents = {page_name: content_html}
        else:
            # Fallback контент
            blog_contents = {
                'blog1': f'<p class="text-lg text-gray-700 mb-6">The {theme} industry is evolving rapidly...</p><h2 class="text-2xl font-bold mt-8 mb-4">Key Innovations</h2><p class="text-gray-700 mb-6">Recent technological advances have transformed how we approach {theme}.</p>',
                'blog2': f'<p class="text-lg text-gray-700 mb-6">The {theme} sector is constantly evolving. Here are the top 5 trends...</p><h2 class="text-2xl font-bold mt-8 mb-4">1. Digital Transformation</h2><p class="text-gray-700 mb-6">More businesses are embracing digital solutions...</p>',
                'blog3': f'<p class="text-lg text-gray-700 mb-6">Choosing the right {theme} service can be challenging...</p><h2 class="text-2xl font-bold mt-8 mb-4">Assess Your Needs</h2><p class="text-gray-700 mb-6">Start by clearly defining what you need...</p>',
                'blog4': f'<p class="text-lg text-gray-700 mb-6">Achieving success in {theme} requires following proven strategies...</p><h2 class="text-2xl font-bold mt-8 mb-4">Set Clear Goals</h2><p class="text-gray-700 mb-6">Define specific, measurable objectives...</p>',
                'blog5': f'<p class="text-lg text-gray-700 mb-6">Avoiding common pitfalls can save you time, money, and frustration...</p><h2 class="text-2xl font-bold mt-8 mb-4">Mistake 1: Lack of Planning</h2><p class="text-gray-700 mb-6">Rushing into {theme} projects without proper planning...</p>',
                'blog6': f'<p class="text-lg text-gray-700 mb-6">This comprehensive guide covers everything you need to know about {theme}...</p><h2 class="text-2xl font-bold mt-8 mb-4">Understanding the Basics</h2><p class="text-gray-700 mb-6">Start with the fundamentals of {theme}...</p>'
            }

        blog_images = {
            'blog1': 'images/blog1.jpg',
            'blog2': 'images/blog2.jpg',
            'blog3': 'images/blog3.jpg',
            'blog4': 'images/blog4.jpg',
            'blog5': 'images/blog5.jpg',
            'blog6': 'images/blog6.jpg'
        }

        # Вариации: случайный выбор картинки для каждой статьи
        blog_variations = {
            'blog1': {'has_image': random.choice([True, False])},
            'blog2': {'has_image': random.choice([True, False])},
            'blog3': {'has_image': random.choice([True, False])},
            'blog4': {'has_image': random.choice([True, False])},
            'blog5': {'has_image': random.choice([True, False])},
            'blog6': {'has_image': random.choice([True, False])}
        }

        current_variation = blog_variations.get(page_name, {'has_image': True})

        # Navigation removed - no more Past Article/Next Article links
        nav_buttons = ''

        # Создаем секцию с картинкой (если has_image=True И изображение сгенерировано)
        image_section = ''
        blog_img_filename = page_name + '.jpg'  # Например 'blog1.jpg'
        if current_variation['has_image'] and self._has_image(blog_img_filename):
            image_section = f'''
        <div class="mb-8 rounded-xl overflow-hidden">
            <img src="{blog_images[page_name]}" alt="{blog_titles[page_name]}" class="w-full h-96 object-cover">
        </div>
        '''

        # Используем дату из синхронизированных данных (уже установлена выше)
        # Автора берем из API или используем fallback
        article_author = article_data.get('author', f'{site_name} Team') if article_data else f'{site_name} Team'

        main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">{blog_titles[page_name]}</h1>
        <p class="text-gray-500 mb-8">{published_on} {article_date} by {article_author}</p>

        {image_section}

        <div class="prose prose-lg max-w-none">
            {blog_contents[page_name]}
        </div>

        {nav_buttons}

        <div class="mt-12 p-8 bg-gradient-to-br from-{primary}/10 to-{primary}/5 rounded-xl text-center">
            <h3 class="text-2xl font-bold mb-4">{interested_services}</h3>
            <p class="text-gray-700 mb-6">{get_in_touch_today}</p>
            <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                {contact_us}
            </a>
        </div>
    </div>
</section>
</main>"""
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем, что header и footer созданы
        if not self.header_code or not self.footer_code:
            print(f"    ⚠️  Header/Footer не найдены, регенерация...")
            self.generate_header_footer()
        
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{blog_titles[page_name]} - {site_name}</title>
    <link rel="icon" type="image/svg+xml" href="{self.get_favicon_url()}">
    {self.header_footer_css}
</head>
<body>
    {self.header_code}
    
    {main_content}
    
    {self.footer_code}
</body>
</html>"""
        
        page_path = os.path.join(output_dir, f"{page_name}.php")
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        print(f"    ✓ {page_name}.php создана")
        return True
    
    def generate_blog_main_page(self, output_dir):
        """Генерация главной страницы blog со списком статей (3 или 6 случайно)"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        # Получаем контент blog page через API
        blog_page_data = self.generate_theme_content_via_api(theme, "blog_page_content", 1)

        # Fallback если API не вернул результат - используем язык из blueprint
        if not blog_page_data:
            language = self.blueprint.get('language', 'English')
            # Минимальный fallback - пробуем еще раз с упрощенным промптом
            print(f"    ⚠️  Первая попытка blog_page_content не удалась, пробуем снова...")
            blog_page_data = self.generate_theme_content_via_api(theme, "blog_page_content", 1)

            if not blog_page_data:
                # Если и вторая попытка не удалась, используем базовый fallback
                print(f"    ⚠️  Используем базовый fallback для blog_page_content")
                blog_page_fallback = {
                    'heading': 'Blog',
                    'subheading': f'{theme}',
                    'read_more': 'Read More',
                    'no_posts': 'No posts'
                }
                blog_page_data = self.get_localized_fallback('blog_page_content', blog_page_fallback)

        heading = blog_page_data.get('heading', 'Our Blog')
        subheading = blog_page_data.get('subheading', f'Insights, tips, and news about {theme}')
        read_more_text = blog_page_data.get('read_more', 'Read More')
        no_posts_text = blog_page_data.get('no_posts', 'No blog posts available yet')

        # Получаем переводы для blog navigation
        blog_nav_data = self.generate_theme_content_via_api(theme, "blog_navigation_content", 1)
        if not blog_nav_data:
            blog_nav_fallback = {
                'want_learn_more': 'Want to Learn More?',
                'contact_specific_needs': 'Contact us to discuss your specific needs and how we can help.',
                'get_in_touch': 'Get in Touch'
            }
            blog_nav_data = self.get_localized_fallback('blog_navigation_content', blog_nav_fallback)
        want_learn_more = blog_nav_data.get('want_learn_more', 'Want to Learn More?')
        contact_specific_needs = blog_nav_data.get('contact_specific_needs', 'Contact us to discuss your specific needs and how we can help.')
        get_in_touch = blog_nav_data.get('get_in_touch', 'Get in Touch')

        # КРИТИЧЕСКИ ВАЖНО: Проверяем, есть ли уже blog_posts_previews в blueprint
        # Если есть - используем их для согласованности с главной страницей
        if hasattr(self, 'blueprint') and 'blog_posts_previews' in self.blueprint:
            # Используем существующие данные из blueprint (созданные в generate_blog_preview_section)
            all_blog_articles = self.blueprint['blog_posts_previews']
        else:
            # Генерируем статьи через API
            api_blog_posts = self.generate_theme_content_via_api(theme, "blog_posts", 6)

            # Fallback если API не вернул результат
            if not api_blog_posts or len(api_blog_posts) < 6:
                # Генерируем даты с интервалом ~6 месяцев от текущей даты
                from datetime import datetime, timedelta
                import random

                now = datetime.now()
                blog_dates = []
                current_date = now
                for i in range(6):
                    blog_dates.append(current_date.strftime('%B %d, %Y'))
                    # Вычитаем примерно 6 месяцев (150-210 дней)
                    current_date = current_date - timedelta(days=random.randint(150, 210))

                all_blog_articles = [
                    {
                        'title': f'The Future of {theme}',
                        'url': 'blog1.php',
                        'excerpt': f'Explore the latest innovations in {theme} and what they mean for your business.',
                        'date': blog_dates[0],
                        'image': 'images/blog1.jpg'
                    },
                    {
                        'title': f'Top 5 Trends in {theme}',
                        'url': 'blog2.php',
                        'excerpt': f'Stay competitive with these emerging trends in the {theme} industry.',
                        'date': blog_dates[1],
                        'image': 'images/blog2.jpg'
                    },
                    {
                        'title': f'How to Choose the Right {theme} Service',
                        'url': 'blog3.php',
                        'excerpt': f'A comprehensive guide to selecting the best {theme} solution for your needs.',
                        'date': blog_dates[2],
                        'image': 'images/blog3.jpg'
                    },
                    {
                        'title': f'Best Practices for {theme} Success',
                        'url': 'blog4.php',
                        'excerpt': f'Learn proven strategies and techniques to maximize your {theme} results.',
                        'date': blog_dates[3],
                        'image': 'images/blog4.jpg'
                    },
                    {
                        'title': f'Common {theme} Mistakes to Avoid',
                        'url': 'blog5.php',
                        'excerpt': f'Discover the pitfalls that could derail your {theme} projects and how to avoid them.',
                        'date': blog_dates[4],
                        'image': 'images/blog5.jpg'
                    },
                    {
                        'title': f'The Complete {theme} Guide',
                        'url': 'blog6.php',
                        'excerpt': f'Everything you need to know about {theme} in one comprehensive resource.',
                        'date': blog_dates[5],
                        'image': 'images/blog6.jpg'
                    }
                ]
            else:
                # Используем данные из API и добавляем URL и изображения
                all_blog_articles = []
                for i, post in enumerate(api_blog_posts[:6]):
                    all_blog_articles.append({
                        'title': post.get('title', f'{theme} Article {i+1}'),
                        'url': f'blog{i+1}.php',
                        'excerpt': post.get('excerpt', f'Read about {theme}...'),
                        'date': post.get('date', 'November 2025'),
                        'image': f'images/blog{i+1}.jpg'
                    })

            # Сохраняем в blueprint для использования в generate_blog_page
            self.blueprint['blog_posts_previews'] = all_blog_articles


        # Используем заранее определенное количество статей (3 или 6)
        # self.num_blog_articles уже установлено в generate_website()
        # Изображения blog1-3 или blog1-6 уже сгенерированы в зависимости от этого значения
        blog_articles = all_blog_articles[:self.num_blog_articles]

        # Создаем карточки статей
        article_cards = ''
        for article in blog_articles:
            article_cards += f'''
            <article class="bg-white rounded-xl shadow-lg overflow-hidden hover:shadow-xl transition group">
                <div class="aspect-video overflow-hidden">
                    <img src="{article['image']}" alt="{article['title']}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">
                </div>
                <div class="p-6">
                    <p class="text-sm text-gray-500 mb-2">{article['date']}</p>
                    <h2 class="text-2xl font-bold mb-3 group-hover:text-{primary} transition">{article['title']}</h2>
                    <p class="text-gray-600 mb-4">{article['excerpt']}</p>
                    <a href="{article['url']}" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition">
                        {read_more_text}
                        <svg class="w-5 h-5 ml-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </a>
                </div>
            </article>
            '''

        main_content = f"""<main>
<section class="py-20 bg-gradient-to-br from-{primary}/10 to-white">
    <div class="container mx-auto px-6">
        <div class="max-w-4xl mx-auto text-center">
            <h1 class="text-5xl md:text-6xl font-bold mb-6">{heading}</h1>
            <p class="text-xl md:text-2xl text-gray-600">{subheading}</p>
        </div>
    </div>
</section>

<section class="py-20 bg-white">
    <div class="container mx-auto px-6">
        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {article_cards}
        </div>
    </div>
</section>

<section class="py-20 bg-gray-50">
    <div class="container mx-auto px-6">
        <div class="max-w-4xl mx-auto text-center">
            <h2 class="text-4xl font-bold mb-6">{want_learn_more}</h2>
            <p class="text-xl text-gray-600 mb-8">{contact_specific_needs}</p>
            <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                {get_in_touch}
            </a>
        </div>
    </div>
</section>
</main>"""
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем, что header и footer созданы
        if not self.header_code or not self.footer_code:
            print(f"    ⚠️  Header/Footer не найдены, регенерация...")
            self.generate_header_footer()
        
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog - {site_name}</title>
    <link rel="icon" type="image/svg+xml" href="{self.get_favicon_url()}">
    {self.header_footer_css}
</head>
<body>
    {self.header_code}
    
    {main_content}
    
    {self.footer_code}
</body>
</html>"""
        
        page_path = os.path.join(output_dir, "blog.php")
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        print(f"    ✓ blog.php создана (главная страница блога)")
        return True
    
    def generate_policy_page(self, page_name, output_dir):
        """Генерация policy страниц с УНИКАЛЬНЫМ контентом для каждой"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')

        # Получаем контент policy через API
        policy_data = self.generate_theme_content_via_api(theme, "policy_content", 1)

        # Fallback если API не вернул результат
        if not policy_data:
            policy_data = {
                'privacy_policy': 'Privacy Policy',
                'terms_of_service': 'Terms of Service',
                'cookie_policy': 'Cookie Policy',
                'last_updated': 'Last updated'
            }

        titles = {
            'privacy': policy_data.get('privacy_policy', 'Privacy Policy'),
            'terms': policy_data.get('terms_of_service', 'Terms of Service'),
            'cookie': policy_data.get('cookie_policy', 'Cookie Policy')
        }

        last_updated_label = policy_data.get('last_updated', 'Last updated')
        
        # УНИКАЛЬНЫЙ контент для каждой страницы
        # Функция для замены плейсхолдеров названия компании во всех строках
        def replace_placeholders(data, site_name):
            """Рекурсивно заменяет плейсхолдеры названия компании на реальное имя"""
            import re

            # Паттерны для различных плейсхолдеров в разных языках
            patterns = [
                r"\[Nom de l['']Entreprise[^\]]*\]",  # Французский
                r'\[Company Name[^\]]*\]',             # Английский
                r"\[Nome dell['']azienda[^\]]*\]",   # Итальянский
                r'\[Nombre de la empresa[^\]]*\]',     # Испанский
                r'\[Firmenname[^\]]*\]',               # Немецкий
                r'\[Nazwa firmy[^\]]*\]',              # Польский
                r'\[Název společnosti[^\]]*\]',        # Чешский
                r'\[Bedrijfsnaam[^\]]*\]',             # Нидерландский
                r'\[Site Name[^\]]*\]',                # Общий
                r'\[Business Name[^\]]*\]',            # Общий
            ]

            if isinstance(data, dict):
                return {key: replace_placeholders(value, site_name) for key, value in data.items()}
            elif isinstance(data, list):
                return [replace_placeholders(item, site_name) for item in data]
            elif isinstance(data, str):
                result = data
                for pattern in patterns:
                    result = re.sub(pattern, site_name, result, flags=re.IGNORECASE)
                return result
            else:
                return data

        if page_name == 'privacy':
            # Получаем полный переведенный контент privacy policy
            privacy_content = self.generate_theme_content_via_api(theme, "privacy_policy_full", 1)

            # Заменяем плейсхолдеры на реальное название сайта
            if privacy_content and isinstance(privacy_content, dict):
                privacy_content = replace_placeholders(privacy_content, site_name)

            # Fallback если API не вернул результат
            if not privacy_content or not isinstance(privacy_content, dict):
                privacy_content = {
                    "introduction_heading": "Introduction",
                    "introduction_text": f"{site_name} ('us', 'we', or 'our') is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you visit our website.",
                    "info_we_collect_heading": "Information We Collect",
                    "info_we_collect_intro": "We may collect information about you in a variety of ways. The information we may collect includes:",
                    "personal_data_heading": "Personal Data",
                    "personal_data_items": ["Name and contact information (email address, phone number)", "Demographic information (age, gender, interests)", "Payment information for transactions", "Any other information you voluntarily provide"],
                    "usage_data_heading": "Usage Data",
                    "usage_data_items": ["IP address and browser type", "Pages visited and time spent on pages", "Referring website addresses", "Device information"],
                    "how_we_use_heading": "How We Use Your Information",
                    "how_we_use_intro": "We use the information we collect to:",
                    "how_we_use_items": ["Provide, operate, and maintain our website and services", "Improve and personalize your experience", "Communicate with you about updates, offers, and news", "Process transactions and send transaction notifications", "Monitor and analyze usage patterns and trends", "Detect, prevent, and address technical issues and fraud"],
                    "data_security_heading": "Data Security",
                    "data_security_text": "We implement appropriate security measures to protect your personal information. However, no method of transmission over the Internet is 100% secure, and we cannot guarantee absolute security.",
                    "your_rights_heading": "Your Rights",
                    "your_rights_text": "You have the right to access, update, or delete your personal information at any time. You may also opt-out of marketing communications.",
                    "contact_heading": "Contact Us",
                    "contact_text": "If you have any questions about this Privacy Policy, please contact us at:",
                    "contact_email_label": "Email:"
                }

            # Генерируем списки HTML
            personal_data_list = '\n            '.join([f"<li>{item}</li>" for item in privacy_content.get('personal_data_items', [])])
            usage_data_list = '\n            '.join([f"<li>{item}</li>" for item in privacy_content.get('usage_data_items', [])])
            how_we_use_list = '\n            '.join([f"<li>{item}</li>" for item in privacy_content.get('how_we_use_items', [])])

            main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold text-center mb-4">{titles[page_name]}</h1>
        <p class="text-gray-500 text-center mb-12">{last_updated_label}: November 14, 2025</p>

        <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed">

        <h2 class="text-2xl font-bold mt-8 mb-4">1. {privacy_content.get('introduction_heading', 'Introduction')}</h2>
        <p>{privacy_content.get('introduction_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">2. {privacy_content.get('info_we_collect_heading', 'Information We Collect')}</h2>
        <p>{privacy_content.get('info_we_collect_intro', 'We may collect information about you in a variety of ways. The information we may collect includes:')}</p>

        <h3 class="text-xl font-semibold mt-6 mb-3">{privacy_content.get('personal_data_heading', 'Personal Data')}</h3>
        <ul class="list-disc pl-6 my-4">
            {personal_data_list}
        </ul>

        <h3 class="text-xl font-semibold mt-6 mb-3">{privacy_content.get('usage_data_heading', 'Usage Data')}</h3>
        <ul class="list-disc pl-6 my-4">
            {usage_data_list}
        </ul>

        <h2 class="text-2xl font-bold mt-8 mb-4">3. {privacy_content.get('how_we_use_heading', 'How We Use Your Information')}</h2>
        <p>{privacy_content.get('how_we_use_intro', 'We use the information we collect to:')}</p>
        <ul class="list-disc pl-6 my-4">
            {how_we_use_list}
        </ul>

        <h2 class="text-2xl font-bold mt-8 mb-4">4. {privacy_content.get('data_security_heading', 'Data Security')}</h2>
        <p>{privacy_content.get('data_security_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">5. {privacy_content.get('your_rights_heading', 'Your Rights')}</h2>
        <p>{privacy_content.get('your_rights_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">6. {privacy_content.get('contact_heading', 'Contact Us')}</h2>
        <p>{privacy_content.get('contact_text', '')}</p>
        <p class="mt-2">{privacy_content.get('contact_email_label', 'Email:')} {site_name.lower().replace(' ', '')}@gmail.com</p>
        </div>
    </div>
</section>
</main>"""
        
        elif page_name == 'terms':
            # Получаем полный переведенный контент terms of service
            terms_content = self.generate_theme_content_via_api(theme, "terms_of_service_full", 1)

            # Заменяем плейсхолдеры на реальное название сайта
            if terms_content and isinstance(terms_content, dict):
                terms_content = replace_placeholders(terms_content, site_name)

            # Fallback если API не вернул результат
            if not terms_content or not isinstance(terms_content, dict):
                terms_content = {
                    "agreement_heading": "Agreement to Terms",
                    "agreement_text": f"By accessing and using {site_name}'s website, you accept and agree to be bound by the terms and provisions of this agreement. If you do not agree to these Terms of Service, please do not use this website.",
                    "use_license_heading": "Use License",
                    "use_license_intro": f"Permission is granted to temporarily access the materials on {site_name}'s website for personal, non-commercial use only. This is the grant of a license, not a transfer of title, and under this license you may not:",
                    "use_license_items": ["Modify or copy the materials", "Use the materials for any commercial purpose", "Attempt to decompile or reverse engineer any software", "Remove any copyright or proprietary notations", "Transfer the materials to another person"],
                    "user_responsibilities_heading": "User Responsibilities",
                    "user_responsibilities_intro": "As a user of our website, you agree to:",
                    "user_responsibilities_items": ["Provide accurate and complete information", "Maintain the security of your account credentials", "Notify us immediately of any unauthorized use", "Not engage in any activity that disrupts or interferes with our services", "Comply with all applicable laws and regulations"],
                    "disclaimer_heading": "Disclaimer",
                    "disclaimer_text": f"The materials on {site_name}'s website are provided on an 'as is' basis. {site_name} makes no warranties, expressed or implied, and hereby disclaims all other warranties including, without limitation, implied warranties or conditions of merchantability, fitness for a particular purpose, or non-infringement of intellectual property.",
                    "limitations_heading": "Limitations of Liability",
                    "limitations_text": f"In no event shall {site_name} or its suppliers be liable for any damages arising out of the use or inability to use the materials on our website.",
                    "modifications_heading": "Modifications",
                    "modifications_text": f"{site_name} may revise these Terms of Service at any time without notice. By using this website, you agree to be bound by the current version of these terms.",
                    "contact_heading": "Contact Information",
                    "contact_intro": "For questions about these Terms of Service, please contact us at:",
                    "contact_email_label": "Email:"
                }

            # Генерируем списки HTML
            use_license_list = '\n            '.join([f"<li>{item}</li>" for item in terms_content.get('use_license_items', [])])
            responsibilities_list = '\n            '.join([f"<li>{item}</li>" for item in terms_content.get('user_responsibilities_items', [])])

            main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold text-center mb-4">{titles[page_name]}</h1>
        <p class="text-gray-500 text-center mb-12">{last_updated_label}: November 14, 2025</p>

        <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed">

        <h2 class="text-2xl font-bold mt-8 mb-4">1. {terms_content.get('agreement_heading', 'Agreement to Terms')}</h2>
        <p>{terms_content.get('agreement_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">2. {terms_content.get('use_license_heading', 'Use License')}</h2>
        <p>{terms_content.get('use_license_intro', '')}</p>
        <ul class="list-disc pl-6 my-4">
            {use_license_list}
        </ul>

        <h2 class="text-2xl font-bold mt-8 mb-4">3. {terms_content.get('user_responsibilities_heading', 'User Responsibilities')}</h2>
        <p>{terms_content.get('user_responsibilities_intro', '')}</p>
        <ul class="list-disc pl-6 my-4">
            {responsibilities_list}
        </ul>

        <h2 class="text-2xl font-bold mt-8 mb-4">4. {terms_content.get('disclaimer_heading', 'Disclaimer')}</h2>
        <p>{terms_content.get('disclaimer_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">5. {terms_content.get('limitations_heading', 'Limitations of Liability')}</h2>
        <p>{terms_content.get('limitations_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">6. {terms_content.get('modifications_heading', 'Modifications')}</h2>
        <p>{terms_content.get('modifications_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">7. {terms_content.get('contact_heading', 'Contact Information')}</h2>
        <p>{terms_content.get('contact_intro', '')}</p>
        <p class="mt-2">{terms_content.get('contact_email_label', 'Email:')} {site_name.lower().replace(' ', '')}@gmail.com</p>
        </div>
    </div>
</section>
</main>"""
        
        elif page_name == 'cookie':
            # Получаем полный переведенный контент cookie policy
            cookie_content = self.generate_theme_content_via_api(theme, "cookie_policy_full", 1)

            # Заменяем плейсхолдеры на реальное название сайта
            if cookie_content and isinstance(cookie_content, dict):
                cookie_content = replace_placeholders(cookie_content, site_name)

            # Fallback если API не вернул результат
            if not cookie_content or not isinstance(cookie_content, dict):
                cookie_content = {
                    "what_are_cookies_heading": "What Are Cookies",
                    "what_are_cookies_text": "Cookies are small text files that are placed on your device when you visit our website. They help us provide you with a better experience by remembering your preferences and understanding how you use our site.",
                    "types_heading": "Types of Cookies We Use",
                    "essential_heading": "Essential Cookies",
                    "essential_text": "These cookies are necessary for the website to function properly. They enable basic functions like page navigation and access to secure areas of the website.",
                    "analytics_heading": "Analytics Cookies",
                    "analytics_text": "We use analytics cookies to understand how visitors interact with our website. This helps us improve our content and user experience. These cookies collect information anonymously.",
                    "functionality_heading": "Functionality Cookies",
                    "functionality_text": "These cookies allow our website to remember choices you make (such as your language preference) and provide enhanced, personalized features.",
                    "advertising_heading": "Advertising Cookies",
                    "advertising_text": "We may use advertising cookies to deliver relevant advertisements to you and track the effectiveness of our marketing campaigns.",
                    "third_party_heading": "Third-Party Cookies",
                    "third_party_text": "In addition to our own cookies, we may use various third-party cookies to report usage statistics, deliver advertisements, and provide social media features.",
                    "managing_heading": "Managing Cookies",
                    "managing_intro": "You can control and/or delete cookies as you wish. You can delete all cookies that are already on your computer and you can set most browsers to prevent them from being placed. However, if you do this, you may have to manually adjust some preferences every time you visit our site.",
                    "how_to_control_heading": "How to Control Cookies",
                    "control_items": ["Browser settings: Most browsers allow you to refuse or accept cookies", "Third-party tools: Use browser extensions or privacy tools", "Opt-out links: Some third-party services provide opt-out mechanisms"],
                    "updates_heading": "Updates to This Policy",
                    "updates_text": "We may update this Cookie Policy from time to time. We encourage you to review this page periodically for any changes.",
                    "contact_heading": "Contact Us",
                    "contact_intro": "If you have questions about our use of cookies, please contact us at:",
                    "contact_email_label": "Email:"
                }

            # Генерируем списки HTML
            control_items_list = '\n            '.join([f"<li>{item}</li>" for item in cookie_content.get('control_items', [])])

            main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold text-center mb-4">{titles[page_name]}</h1>
        <p class="text-gray-500 text-center mb-12">{last_updated_label}: November 14, 2025</p>

        <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed">

        <h2 class="text-2xl font-bold mt-8 mb-4">1. {cookie_content.get('what_are_cookies_heading', 'What Are Cookies')}</h2>
        <p>{cookie_content.get('what_are_cookies_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">2. {cookie_content.get('types_heading', 'Types of Cookies We Use')}</h2>

        <h3 class="text-xl font-semibold mt-6 mb-3">{cookie_content.get('essential_heading', 'Essential Cookies')}</h3>
        <p>{cookie_content.get('essential_text', '')}</p>

        <h3 class="text-xl font-semibold mt-6 mb-3">{cookie_content.get('analytics_heading', 'Analytics Cookies')}</h3>
        <p>{cookie_content.get('analytics_text', '')}</p>

        <h3 class="text-xl font-semibold mt-6 mb-3">{cookie_content.get('functionality_heading', 'Functionality Cookies')}</h3>
        <p>{cookie_content.get('functionality_text', '')}</p>

        <h3 class="text-xl font-semibold mt-6 mb-3">{cookie_content.get('advertising_heading', 'Advertising Cookies')}</h3>
        <p>{cookie_content.get('advertising_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">3. {cookie_content.get('third_party_heading', 'Third-Party Cookies')}</h2>
        <p>{cookie_content.get('third_party_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">4. {cookie_content.get('managing_heading', 'Managing Cookies')}</h2>
        <p>{cookie_content.get('managing_intro', '')}</p>

        <h3 class="text-xl font-semibold mt-6 mb-3">{cookie_content.get('how_to_control_heading', 'How to Control Cookies')}</h3>
        <ul class="list-disc pl-6 my-4">
            {control_items_list}
        </ul>

        <h2 class="text-2xl font-bold mt-8 mb-4">5. {cookie_content.get('updates_heading', 'Updates to This Policy')}</h2>
        <p>{cookie_content.get('updates_text', '')}</p>

        <h2 class="text-2xl font-bold mt-8 mb-4">6. {cookie_content.get('contact_heading', 'Contact Us')}</h2>
        <p>{cookie_content.get('contact_intro', '')}</p>
        <p class="mt-2">{cookie_content.get('contact_email_label', 'Email:')} {site_name.lower().replace(' ', '')}@gmail.com</p>
        </div>
    </div>
</section>
</main>"""
        
        else:
            # Fallback на случай неизвестной страницы
            main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold text-center mb-4">Policy Page</h1>
        <p class="text-center text-gray-600">Content coming soon.</p>
    </div>
</section>
</main>"""
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем, что header и footer созданы
        if not self.header_code or not self.footer_code:
            print(f"    ⚠️  Header/Footer не найдены, регенерация...")
            self.generate_header_footer()
        
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{titles[page_name]} - {site_name}</title>
    <link rel="icon" type="image/svg+xml" href="{self.get_favicon_url()}">
    {self.header_footer_css}
</head>
<body>
    {self.header_code}
    
    {main_content}
    
    {self.footer_code}
</body>
</html>"""
        
        page_path = os.path.join(output_dir, f"{page_name}.php")
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        print(f"    ✓ {page_name}.php создана")
        return True

    def generate_website(self, user_prompt, site_name, num_images=24, output_dir="generated_website", data_dir="data", site_type="multipage"):
        """Основной метод генерации"""
        self.site_type = site_type
        self.num_images_to_generate = num_images  # Сохраняем для использования в generate_home_sections()

        # Определяем количество статей блога заранее (3 или 6 случайно)
        # Это нужно для правильной генерации изображений blog1-3 или blog1-6
        self.num_blog_articles = random.choice([3, 6])

        print("=" * 60)
        print(f"PHPGEN v77 - {'LANDING' if site_type == 'landing' else 'MULTIPAGE SITE'} GENERATOR")
        print("=" * 60)

        Path(output_dir).mkdir(exist_ok=True)

        print("\n[1/7] Загрузка БД...")
        self.load_database(data_dir)

        print("\n[2/7] Blueprint (название, цвета, layouts)...")
        if not self.create_blueprint(user_prompt, site_name):
            print("⚠️  Ошибка Blueprint (использован fallback)")

        print("\n[3/7] Header и Footer (без соц. сетей, единый hover)...")
        if not self.generate_header_footer():
            print("⚠️  Ошибка Header/Footer (использован fallback)")

        print("\n[4/7] Favicon...")
        self.generate_favicon(output_dir)

        # НОВАЯ ЛОГИКА: Предварительный выбор секций и подсчет необходимых изображений
        print("\n[5/7] Предварительное планирование контента...")
        self.selected_home_sections = self.select_home_sections()
        self.selected_services_variant = random.randint(1, 4)
        print(f"  ✓ Выбраны секции для Home: {', '.join(self.selected_home_sections)}")
        print(f"  ✓ Вариант Services страницы: {self.selected_services_variant}")

        # Подсчитываем необходимое количество изображений
        required_images_count = self.calculate_required_images()
        # Генерируем столько, сколько НЕОБХОДИМО для сайта (игнорируем num_images если он больше)
        # Если нужно 10, а запросили 14 - генерируем 10 (избегаем лишних)
        # Если нужно 14, а запросили 10 - генерируем 14 (всё необходимое)
        actual_num_images = required_images_count if required_images_count > 0 else num_images
        print(f"  ✓ Необходимо изображений: {required_images_count}, будет сгенерировано: {actual_num_images}")

        print("\n[6/7] Страницы...")

        if site_type == "landing":
            # Лендинг - только главная страница с секциями + служебные страницы
            pages_to_generate = ['index', 'contact', 'thanks_you', 'privacy', 'terms', 'cookie']
            print("  Режим: ЛЕНДИНГ (одна страница с секциями)")
        else:
            # Многостраничный сайт - все основные страницы включая blog
            print("  Режим: МНОГОСТРАНИЧНЫЙ САЙТ (все страницы + blog главная + статьи)")
            pages_to_generate = ['index', 'company', 'services', 'contact', 'blog', 'privacy', 'terms', 'cookie', 'thanks_you']

        # Генерируем каждую страницу с повышенным вниманием
        for page in pages_to_generate:
            print(f"  Генерация {page}.php...")
            success = self.generate_page(page, output_dir)
            if not success:
                print(f"    ⚠️  Ошибка генерации {page}.php, создан fallback")

        # Для многостраничного сайта генерируем страницы статей блога
        if site_type == "multipage":
            print(f"  Генерация страниц статей блога ({self.num_blog_articles} статей)...")
            for i in range(1, self.num_blog_articles + 1):
                blog_page = f'blog{i}'
                print(f"    Генерация {blog_page}.php...")
                success = self.generate_page(blog_page, output_dir)
                if not success:
                    print(f"      ⚠️  Ошибка генерации {blog_page}.php, создан fallback")

        print(f"\n[7/7] Изображения ({actual_num_images} шт)...")
        print(f"  📝 Статей блога: {self.num_blog_articles}")
        self.generate_images_for_site(output_dir, actual_num_images)

        print("\n[8/8] Дополнительные файлы...")
        self.generate_additional_files(output_dir)
        
        print("\n" + "=" * 60)
        print(f"✓ {'LANDING' if site_type == 'landing' else 'SITE'} CREATED: {output_dir}")
        print(f"✓ Name: {self.blueprint.get('site_name')}")
        print(f"✓ Colors: {self.blueprint.get('color_scheme', {}).get('primary')} (hover: {self.blueprint.get('color_scheme', {}).get('hover')})")
        print("=" * 60)

        print(f"\n🚀 Launch your site:")
        print(f"\n1. cd {output_dir}")
        print(f"2. php -S localhost:8000")
        print(f"3. Open: http://localhost:8000/index.php")
        print(f"\n✨ Done! Unique design by PHPGEN v77 - Gosha Chepchik")
        
        return True
    
    def generate_additional_files(self, output_dir):
        """Генерация только необходимых дополнительных файлов"""
        # Больше НЕ создаем лишние файлы:
        # - 404.php, 500.php (не нужны)
        # - config.php, functions.php (не нужны)
        # - contact-form-handler.php (не нужен)
        
        print("  ✓ Дополнительные файлы не требуются")
        pass


if __name__ == "__main__":
    print("┌──────────────────────────────────────────────────────────┐")
    print("│         ____  _   _ ____   ____  _____ _   _             │")
    print("│        |  _ \\| | | |  _ \\ / ___|| ____| \\ | |            │")
    print("│        | |_) | |_| | |_) | |  _ |  _| |  \\| |            │")
    print("│        |  __/|  _  |  __/| |_| || |___| |\\  |            │")
    print("│        |_|   |_| |_|_|    \\____||_____|_| \\_|            │")
    print("│                                                          │")
    print("│                      PHPGEN v77                          │")
    print("│                  by Gosha Chepchik                       │")
    print("└──────────────────────────────────────────────────────────┘")
    print()
    
    print("📝 Опишите сайт:")
    print("   (Для завершения введите 'END')")
    print("-" * 60)
    
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    
    user_prompt = "\n".join(lines)
    
    if not user_prompt.strip():
        print("❌ Промпт пустой!")
        exit(1)
    
    print()
    print("-" * 60)
    
    print("\n🎯 Тип сайта:")
    print("   1. Лендинг (одна страница)")
    print("   2. Многостраничный сайт")
    site_type_choice = input("Выберите (1 или 2): ").strip()

    site_type = "landing" if site_type_choice == "1" else "multipage"

    print("\n✏️  Название сайта:")
    print("   (Введите название для вашего сайта)")
    site_name = input(">>> ").strip()

    if not site_name:
        print("❌ Название не может быть пустым!")
        exit(1)

    print("\n🖼️  Количество изображений:")
    print("   (Минимум 17)")
    print("   (По умолчанию: 24 - все изображения)")
    num_images_input = input(">>> ").strip()

    if num_images_input:
        try:
            num_images = int(num_images_input)
            if num_images < 10:
                print("⚠️  Минимум 17 изображений! Установлено: 17")
                num_images = 10
        except ValueError:
            print("⚠️  Некорректное число! Установлено: 24")
            num_images = 24
    else:
        num_images = 24

    print("\n📁 Путь к папке data:")
    print("   (по умолчанию: data)")
    data_dir = input(">>> ").strip()
    
    if not data_dir:
        data_dir = "data"
    
    print("\n📁 Папка для сохранения сайта:")
    print("   (по умолчанию: generated_website)")
    output_dir = input(">>> ").strip()
    
    if not output_dir:
        output_dir = "generated_website"
    
    print()
    print("=" * 60)
    print(f"🚀 Старт генерации...")
    print(f"✏️  Название: {site_name}")
    print(f"🖼️  Изображений: {num_images}")
    print(f"📂 Папка данных: {data_dir}")
    print(f"📂 Папка вывода: {output_dir}")
    print(f"🎯 Тип: {'ЛЕНДИНГ' if site_type == 'landing' else 'МНОГОСТРАНИЧНЫЙ'}")
    print("=" * 60)
    print()

    generator = PHPWebsiteGenerator()

    try:
        success = generator.generate_website(user_prompt, site_name=site_name, num_images=num_images, output_dir=output_dir, data_dir=data_dir, site_type=site_type)

        if success:
            print("\n✨ Готово!")
        else:
            print("\n⚠️  Генерация завершена с предупреждениями")

        # Воспроизводим звуковое уведомление
        print("\n🔔 Воспроизведение звукового сигнала...")
        play_notification_sound()

        # Ждем 6 секунд перед закрытием
        print("⏱️  Консоль закроется через 6 секунд...")
        time.sleep(6)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        # Воспроизводим звук и ждем даже при прерывании
        play_notification_sound()
        time.sleep(6)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        # Воспроизводим звук и ждем даже при ошибке
        play_notification_sound()
        time.sleep(6)