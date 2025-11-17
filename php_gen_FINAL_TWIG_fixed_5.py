import requests
import json
import os
import re
import zipfile
import shutil
import base64
import random
from pathlib import Path
from byteplussdkarkruntime import Ark
from byteplussdkarkruntime.types.images.images import SequentialImageGenerationOptions
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла (если есть)
load_dotenv()

class PHPWebsiteGenerator:
    def __init__(self):
        # API ключи (жестко заданные - всегда работают!)
        self.api_key = "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"
        self.bytedance_key = "03324c9d-d15f-4b35-a234-2bdd0b30a569"
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.code_model = "google/gemini-2.5-pro"
        self.max_tokens = 8000  
        self.use_symfony = False
        self.use_twig = True  # Использовать Twig Template Engine
        self.site_type = "landing"  # "landing" или "multipage"
        self.blueprint = {}
        self.header_code = ""
        self.footer_code = ""
        self.header_footer_css = ""
        self.database_content = ""
        self.template_sites = []
        self.generated_images = []
        self.primary_color = ""  # Основной цвет сайта
        
        # Инициализация Ark клиента для ByteDance Seedream-4.0
        print(f"🔑 Инициализация ByteDance Ark SDK...")
        print(f"   API Key: {self.bytedance_key[:20]}...")
        
        self.ark_client = Ark(
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
            api_key=self.bytedance_key
        )
        print(f"✓ Ark SDK готов\n")
        
    def call_api(self, prompt, max_tokens=8000, model=None):
        """Вызов API OpenRouter с retry логикой и обработкой всех типов ошибок"""
        if model is None:
            model = self.code_model
        
        if max_tokens > 8000:
            max_tokens = 8000  # Ограничение для бесплатной модели
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://php-generator.local",
            "X-Title": "PHP Website Generator"
        }
        
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }
        
        # Retry до 5 раз при ошибках
        for attempt in range(5):
            try:
                response = requests.post(
                    self.api_url, 
                    headers=headers, 
                    data=json.dumps(data), 
                    timeout=240,  # Увеличен таймаут до 4 минут
                    verify=True   # SSL проверка
                )
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content']
                
            except requests.exceptions.ChunkedEncodingError as e:
                # Ошибка "Response ended prematurely"
                if attempt < 4:
                    print(f"    ⚠️  Соединение прервано, попытка {attempt + 2}/5...")
                    import time
                    time.sleep(5)  # Увеличенная пауза
                    continue
                else:
                    print(f"    ✗ Соединение прервано после 5 попыток")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                # Ошибки соединения
                if attempt < 4:
                    print(f"    ⚠️  Ошибка соединения, попытка {attempt + 2}/5...")
                    import time
                    time.sleep(5)
                    continue
                else:
                    print(f"    ✗ Ошибка соединения после 5 попыток")
                    return None
                    
            except requests.exceptions.SSLError as e:
                # SSL ошибка - пробуем еще раз
                if attempt < 4:
                    print(f"    ⚠️  SSL ошибка, попытка {attempt + 2}/5...")
                    import time
                    time.sleep(3)
                    continue
                else:
                    print(f"    ✗ SSL ошибка после 5 попыток")
                    return None
                    
            except requests.exceptions.Timeout as e:
                # Таймаут
                if attempt < 4:
                    print(f"    ⚠️  Таймаут запроса, попытка {attempt + 2}/5...")
                    import time
                    time.sleep(5)
                    continue
                else:
                    print(f"    ✗ Таймаут после 5 попыток")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code >= 500:
                    if attempt < 4:
                        print(f"    ⚠️  Ошибка сервера {e.response.status_code}, попытка {attempt + 2}/5...")
                        import time
                        time.sleep(3)
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
                    print(f"    ⚠️  Некорректный ответ API, попытка {attempt + 2}/5...")
                    import time
                    time.sleep(3)
                    continue
                else:
                    print(f"    ✗ Некорректный ответ после 5 попыток")
                    return None
                    
            except Exception as e:
                # Любые другие ошибки
                error_msg = str(e)
                if attempt < 4:
                    print(f"    ⚠️  Ошибка: {error_msg[:50]}, попытка {attempt + 2}/5...")
                    import time
                    time.sleep(3)
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
            "Travel": "WanderHub, TripNest, JourneyCraft, TravelFlow, RoutePoint, TourSpot"
        }
        
        # Получаем примеры для конкретной тематики
        examples = theme_specific_examples.get(theme, "TechWave, CloudNest, DataSphere, CodeCraft, ByteForge")
        
        prompt = f"""Generate a unique, creative website name for a {theme} company based in {country}.

CRITICAL REQUIREMENTS:
- The name MUST be directly related to {theme} industry
- The name should reflect the nature of {theme} business
- 1-3 words maximum
- DO NOT use generic tech words like "Digital", "Tech", "Cyber", "Web", "Net" unless the theme is IT/Technology
- DO NOT use the exact words "{theme}" or "{country}" in the name
- Use creative combinations, metaphors, or related terms specific to {theme}

Examples of good names for {theme}: {examples}

Industry-specific guidance for {theme}:
{self._get_industry_guidance(theme)}

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
            if theme not in ['IT', 'Technology', 'Software', 'Digital'] and any(word in site_name.lower() for word in forbidden_for_non_it):
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
            "Travel": "Focus on journey, destinations, adventure, exploration. Avoid tech terms."
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
            "Travel": ["WanderHub", "TripNest", "JourneyCraft", "TravelFlow", "RoutePoint"]
        }
        names = fallback_names.get(theme, ["TechWave", "CloudNest", "DataSphere", "CodeCraft", "ByteForge"])
        return random.choice(names)
    
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
    
    def generate_image_via_bytedance(self, prompt, filename, output_dir):
        """Генерация изображения через ByteDance Ark SDK"""
        print(f"    🎨 {filename}...", end=" ", flush=True)
        
        try:
            # Генерация изображения через Ark API
            imagesResponse = self.ark_client.images.generate(
                model="seedream-4-0-250828",
                prompt=f"{prompt}, professional photography, high quality, photorealistic, 4K, no text, no words, no letters",
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
                    print(f"✗ (Error: {event.error})")
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
                
                print("✓")
                return filename
            else:
                print("⚠️")
                return None
                
        except Exception as e:
            print(f"✗ ({str(e)[:50]})")
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
    
    def generate_images_for_site(self, output_dir):
        """Генерация изображений для сайта в папке images/"""
        # Создаем папку images
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        theme = self.blueprint.get('theme', 'business')
        site_name = self.blueprint.get('site_name', 'Company')
        
        images_to_generate = [
            {
                'filename': 'hero.jpg',
                'prompt': f"Professional wide banner photo for {theme}, clean background, photorealistic"
            },
            {
                'filename': 'about.jpg',
                'prompt': f"Professional business photo for {theme}, people in natural setting"
            },
            {
                'filename': 'service1.jpg',
                'prompt': f"{theme} service illustration, professional, clean design"
            },
            {
                'filename': 'service2.jpg',
                'prompt': f"{theme} teamwork, collaboration, modern office"
            },
            {
                'filename': 'service3.jpg',
                'prompt': f"{theme} innovation, technology, future"
            },
            {
                'filename': 'gallery1.jpg',
                'prompt': f"Showcase photo for {theme}, interesting composition"
            },
            {
                'filename': 'gallery2.jpg',
                'prompt': f"Professional image for {theme}, different angle"
            },
            {
                'filename': 'gallery3.jpg',
                'prompt': f"Quality service photo for {theme}"
            },
            {
                'filename': 'gallery4.jpg',
                'prompt': f"Professional showcase for {theme}"
            }
        ]
        
        self.generated_images = []
        
        for img_data in images_to_generate:
            # Сначала пробуем ByteDance
            result = self.generate_image_via_bytedance(
                img_data['prompt'],
                img_data['filename'],
                images_dir  # Изображения в папке images/
            )
            
            # Если не получилось, создаем placeholder
            if not result:
                result = self.generate_placeholder_image(
                    img_data['filename'],
                    images_dir,  # Изображения в папке images/
                    img_data['prompt']
                )
            
            if result:
                # Сохраняем путь с префиксом images/
                self.generated_images.append(f"images/{result}")
    
    def load_database(self, data_dir="data"):
        """Загрузка данных из папки data (работа с любым путем)"""
        # Нормализуем путь для Windows/Linux
        data_dir = os.path.normpath(data_dir)
        
        if not os.path.exists(data_dir):
            # Пробуем найти в разных местах
            possible_paths = [
                data_dir,
                os.path.join(".", data_dir),
                os.path.join(os.getcwd(), data_dir),
                os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd(), data_dir)
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
    
    def create_blueprint(self, user_prompt):
        """Создание Blueprint сайта с улучшенной обработкой"""
        # Улучшенное извлечение темы и страны из промпта
        country = "USA"
        theme = "Business"
        
        # Ищем явное указание country и theme
        country_match = re.search(r'country[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)
        theme_match = re.search(r'theme[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)
        
        if country_match:
            country = country_match.group(1).strip()
        
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
            
        # Ищем страну в тексте
        if 'singapore' in user_prompt.lower():
            country = "Singapore"
        elif 'usa' in user_prompt.lower() or 'america' in user_prompt.lower():
            country = "USA"
        elif 'uk' in user_prompt.lower() or 'britain' in user_prompt.lower():
            country = "UK"
        elif 'germany' in user_prompt.lower():
            country = "Germany"
        elif 'france' in user_prompt.lower():
            country = "France"
        elif 'japan' in user_prompt.lower():
            country = "Japan"
        elif 'china' in user_prompt.lower():
            country = "China"
        
        # Генерируем уникальное название сайта через API
        print(f"  Определена тема: {theme}")
        print(f"  Определена страна: {country}")
        print("  Генерация уникального названия...")
        site_name = self.generate_unique_site_name(country, theme)
        print(f"  ✓ Название: {site_name}")
        
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
        
        # Сразу создаем fallback blueprint (гарантированно рабочий)
        self.blueprint = {
            "site_name": site_name,
            "tagline": tagline,
            "theme": theme,
            "country": country,
            "color_scheme": color_scheme,
            "header_layout": header_layout,
            "footer_layout": footer_layout,
            "sections": sections,
            "menu": ["Home", "Services", "About", "Blog", "Contact"],
            "pages": ["index", "about", "services", "contact", "blog1", "blog2", "blog3", "privacy", "terms", "cookie", "thanks"]
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
            menu = self.blueprint.get('menu', ['Home', 'Services', 'About', 'Blog', 'Contact'])
            colors = self.blueprint.get('color_scheme', {})
            header_layout = self.blueprint.get('header_layout', 'left-aligned')
            footer_layout = self.blueprint.get('footer_layout', 'columns-3')
            
            hover_color = colors.get('hover', 'blue-700')
            primary_color = colors.get('primary', 'blue-600')
            theme = self.blueprint.get('theme', 'business')
            
            # Определяем страницы в зависимости от типа сайта
            if self.site_type == "landing":
                nav_pages = [
                    ('Home', 'index.php'),
                    ('Contact', 'index.php#contact')
                ]
            else:
                nav_pages = [
                    ('Home', 'index.php'),
                    ('About', 'about.php'),
                    ('Services', 'services.php'),
                    ('Blog', 'blog.php'),
                    ('Contact', 'contact.php')
                ]
            
            # Случайный выбор варианта header (2 варианта)
            header_variant = random.randint(1, 2)
            
            if header_variant == 1:
                # Вариант 1: Меню справа (классический)
                self.header_code = f"""<header class="bg-white shadow-md sticky top-0 z-50">
    <div class="container mx-auto px-6 py-4">
        <div class="flex justify-between items-center">
            <!-- Logo -->
            <div class="text-2xl font-bold text-{primary_color}">
                {site_name}
            </div>
            
            <!-- Desktop Navigation - Right Aligned -->
            <nav class="hidden md:flex space-x-8">
                {' '.join([f'<a href="{page[1]}" class="text-gray-700 hover:text-{hover_color} transition-colors">{page[0]}</a>' for page in nav_pages])}
            </nav>
            
            <!-- Mobile Menu Button -->
            <button id="mobile-menu-btn" class="md:hidden text-gray-700 hover:text-{hover_color}">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
        </div>
        
        <!-- Mobile Navigation -->
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
            <!-- Logo -->
            <div class="text-2xl font-bold text-{primary_color} mb-4">
                {site_name}
            </div>
            
            <!-- Desktop Navigation - Center Aligned -->
            <nav class="hidden md:flex space-x-8">
                {' '.join([f'<a href="{page[1]}" class="text-gray-700 hover:text-{hover_color} transition-colors">{page[0]}</a>' for page in nav_pages])}
            </nav>
            
            <!-- Mobile Menu Button -->
            <button id="mobile-menu-btn" class="md:hidden text-gray-700 hover:text-{hover_color} absolute right-6 top-4">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
        </div>
        
        <!-- Mobile Navigation -->
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
            
            # ГАРАНТИРОВАННЫЙ FOOTER (всегда создается, даже если API не отвечает)
            footer_links = [
                ('Home', 'index.php'),
                ('Privacy Policy', 'privacy.php'),
                ('Terms of Service', 'terms.php'),
                ('Cookie Policy', 'cookie.php')
            ]
            
            if self.site_type == "multipage":
                footer_links.insert(1, ('About', 'about.php'))
                footer_links.insert(2, ('Services', 'services.php'))
                footer_links.insert(3, ('Blog', 'blog.php'))
                footer_links.insert(4, ('Contact', 'contact.php'))
            
            # Разделяем ссылки на основные страницы и policy страницы
            main_links = [link for link in footer_links if link[0] not in ['Privacy Policy', 'Terms of Service', 'Cookie Policy']]
            policy_links = [link for link in footer_links if link[0] in ['Privacy Policy', 'Terms of Service', 'Cookie Policy']]
            
            # Случайный выбор варианта footer (4 варианта - убран вариант 3)
            footer_variant = random.choice([1, 2, 4, 5])  # Пропускаем вариант 3
            
            if footer_variant == 1:
                # Вариант 1: Классический 3-колоночный (название + основные ссылки + policy)
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-12 mt-auto">
    <div class="container mx-auto px-6">
        <div class="grid md:grid-cols-3 gap-8">
            <!-- Company Info -->
            <div>
                <h3 class="text-xl font-bold mb-4">{site_name}</h3>
                <p class="text-gray-400">Your trusted partner in {theme}.</p>
            </div>
            
            <!-- Main Links -->
            <div>
                <h4 class="text-lg font-semibold mb-4">Quick Links</h4>
                <ul class="space-y-2">
                    {' '.join([f'<li><a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a></li>' for link in main_links])}
                </ul>
            </div>
            
            <!-- Policy Links -->
            <div>
                <h4 class="text-lg font-semibold mb-4">Legal</h4>
                <ul class="space-y-2">
                    {' '.join([f'<li><a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a></li>' for link in policy_links])}
                </ul>
            </div>
        </div>
        
        <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 {site_name}. All rights reserved.</p>
        </div>
    </div>
</footer>"""
            
            elif footer_variant == 2:
                # Вариант 2: Горизонтальный (ссылки слева, policy справа, название сверху)
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-12 mt-auto">
    <div class="container mx-auto px-6">
        <div class="text-center mb-8">
            <h3 class="text-2xl font-bold">{site_name}</h3>
            <p class="text-gray-400 mt-2">Your trusted partner in {theme}.</p>
        </div>
        
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <!-- Main Links (horizontal) -->
            <nav class="flex flex-wrap gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in main_links])}
            </nav>
            
            <!-- Policy Links (horizontal) -->
            <nav class="flex flex-wrap gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in policy_links])}
            </nav>
        </div>
        
        <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 {site_name}. All rights reserved.</p>
        </div>
    </div>
</footer>"""
            
            elif footer_variant == 4:
                # Вариант 4: 2 колонки (основные ссылки слева вертикально, policy + контакт справа)
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-12 mt-auto">
    <div class="container mx-auto px-6">
        <div class="grid md:grid-cols-2 gap-8">
            <!-- Left: Company + Main Links -->
            <div>
                <h3 class="text-xl font-bold mb-4">{site_name}</h3>
                <p class="text-gray-400 mb-6">Your trusted partner in {theme}.</p>
                <nav class="flex flex-col space-y-2">
                    {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in main_links])}
                </nav>
            </div>
            
            <!-- Right: Legal Links -->
            <div>
                <h4 class="text-lg font-semibold mb-4">Legal Information</h4>
                <nav class="flex flex-col space-y-2">
                    {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in policy_links])}
                </nav>
                <div class="mt-6">
                    <p class="text-gray-400">Email: contact@{site_name.lower().replace(' ', '')}.com</p>
                    <p class="text-gray-400">Phone: +1 (555) 123-4567</p>
                </div>
            </div>
        </div>
        
        <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 {site_name}. All rights reserved.</p>
        </div>
    </div>
</footer>"""
            
            else:  # footer_variant == 5
                # Вариант 5: Минималистичный (все в одну строку горизонтально, без названия компании вверху)
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-8 mt-auto">
    <div class="container mx-auto px-6">
        <div class="flex flex-col md:flex-row justify-between items-center gap-6">
            <!-- Left: Site Name + Copyright -->
            <div class="text-center md:text-left">
                <p class="font-bold text-lg">{site_name}</p>
                <p class="text-gray-400 text-sm">&copy; 2025 All rights reserved.</p>
            </div>
            
            <!-- Center: Main Links -->
            <nav class="flex flex-wrap justify-center gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors text-sm">{link[0]}</a>' for link in main_links])}
            </nav>
            
            <!-- Right: Policy Links -->
            <nav class="flex flex-wrap justify-center gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors text-sm">{link[0]}</a>' for link in policy_links])}
            </nav>
        </div>
    </div>
</footer>"""
            
            footer_variants_map = {1: 1, 2: 2, 4: 3, 5: 4}
            print(f"  ✓ Footer создан (вариант {footer_variants_map.get(footer_variant, footer_variant)}/4) с навигацией (без соц. сетей)")
            
            # CSS для header и footer (обязательный footer на всех страницах)
            self.header_footer_css = f"""<script src="https://cdn.tailwindcss.com"></script>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html {{ height: 100%; scroll-behavior: smooth; }}
    body {{
        font-family: 'Inter', system-ui, sans-serif;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
    }}
    main {{ flex: 1 0 auto; }}
    footer {{ flex-shrink: 0; margin-top: auto; }}
    /* Обеспечиваем footer всегда внизу */
    #root, .page-wrapper {{ min-height: 100vh; display: flex; flex-direction: column; }}
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
            <a href="about.php" class="text-gray-400 hover:text-blue-400">About</a>
            <a href="services.php" class="text-gray-400 hover:text-blue-400">Services</a>
            <a href="contact.php" class="text-gray-400 hover:text-blue-400">Contact</a>
            <a href="privacy.php" class="text-gray-400 hover:text-blue-400">Privacy</a>
            <a href="terms.php" class="text-gray-400 hover:text-blue-400">Terms</a>
        </div>
        <p class="text-gray-400 text-sm mt-4">&copy; 2025 {site_name}. All rights reserved.</p>
    </div>
</footer>"""
            
            # Минимальный CSS
            self.header_footer_css = """<script src="https://cdn.tailwindcss.com"></script>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { height: 100%; }
    body { 
        font-family: 'Inter', system-ui, sans-serif; 
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
        
        favicon_path = os.path.join(output_dir, 'favicon.svg')
        with open(favicon_path, 'w', encoding='utf-8') as f:
            f.write(favicon_svg)
        print(f"✓ Favicon создан: {letter} ({hex_color})")
    
    def generate_contact_page(self, output_dir):
        """Генерация готовой Contact страницы с профессиональной формой"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        main_content = f"""<main>
    <!-- Contact Page -->
    <section class="py-20 bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <!-- Page Header -->
            <div class="text-center mb-16">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Get In Touch</h1>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">
                    Have a question or want to work together? We'd love to hear from you.
                </p>
            </div>

            <div class="grid md:grid-cols-2 gap-12 max-w-6xl mx-auto">
                <!-- Contact Form -->
                <div class="bg-white rounded-2xl shadow-xl p-8 md:p-10">
                    <h2 class="text-3xl font-bold mb-6">Send us a message</h2>
                    <form action="thanks_you.php" method="POST" class="space-y-6">
                        <div>
                            <label for="name" class="block text-gray-700 font-semibold mb-2">
                                Your Name <span class="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                id="name"
                                name="name"
                                required
                                class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none"
                                placeholder="John Doe"
                            >
                        </div>

                        <div>
                            <label for="email" class="block text-gray-700 font-semibold mb-2">
                                Your Email <span class="text-red-500">*</span>
                            </label>
                            <input
                                type="email"
                                id="email"
                                name="email"
                                required
                                class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none"
                                placeholder="john@example.com"
                            >
                        </div>

                        <div>
                            <label for="phone" class="block text-gray-700 font-semibold mb-2">
                                Phone Number
                            </label>
                            <input
                                type="tel"
                                id="phone"
                                name="phone"
                                class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none"
                                placeholder="+1 (555) 123-4567"
                            >
                        </div>

                        <div>
                            <label for="message" class="block text-gray-700 font-semibold mb-2">
                                Your Message <span class="text-red-500">*</span>
                            </label>
                            <textarea
                                id="message"
                                name="message"
                                rows="5"
                                required
                                class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none resize-none"
                                placeholder="Tell us about your project..."
                            ></textarea>
                        </div>

                        <button
                            type="submit"
                            class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                        >
                            Send Message
                        </button>
                    </form>
                </div>

                <!-- Contact Information -->
                <div class="space-y-8">
                    <div class="bg-white rounded-2xl shadow-xl p-8">
                        <h2 class="text-3xl font-bold mb-6">Contact Information</h2>

                        <div class="space-y-6">
                            <!-- Email -->
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                    </svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">Email</h3>
                                    <a href="mailto:contact@{site_name.lower().replace(' ', '')}.com" class="text-gray-600 hover:text-{primary} transition">
                                        contact@{site_name.lower().replace(' ', '')}.com
                                    </a>
                                </div>
                            </div>

                            <!-- Phone -->
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                                    </svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">Phone</h3>
                                    <a href="tel:+15551234567" class="text-gray-600 hover:text-{primary} transition">
                                        +1 (555) 123-4567
                                    </a>
                                </div>
                            </div>

                            <!-- Address -->
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                    </svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">Address</h3>
                                    <p class="text-gray-600">
                                        123 Business Street<br>
                                        Suite 100<br>
                                        New York, NY 10001
                                    </p>
                                </div>
                            </div>

                            <!-- Business Hours -->
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">Business Hours</h3>
                                    <p class="text-gray-600">
                                        Monday - Friday: 9:00 AM - 6:00 PM<br>
                                        Saturday: 10:00 AM - 4:00 PM<br>
                                        Sunday: Closed
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Social Links / Additional Info -->
                    <div class="bg-gradient-to-br from-{primary} to-{hover} rounded-2xl shadow-xl p-8 text-white">
                        <h3 class="text-2xl font-bold mb-4">Why Choose Us?</h3>
                        <ul class="space-y-3">
                            <li class="flex items-center">
                                <svg class="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                </svg>
                                Quick response within 24 hours
                            </li>
                            <li class="flex items-center">
                                <svg class="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                </svg>
                                Professional and friendly team
                            </li>
                            <li class="flex items-center">
                                <svg class="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                </svg>
                                Free initial consultation
                            </li>
                            <li class="flex items-center">
                                <svg class="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                </svg>
                                Customized solutions for your needs
                            </li>
                        </ul>
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
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
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

    def generate_home_sections(self):
        """Генерация случайных секций для Home страницы"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        # Все доступные секции (кроме Hero - она статична)
        all_sections = {
            'image_text_about': f"""
    <!-- Секция 'Изображение и Текст': О нас -->
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h2 class="text-4xl font-bold mb-6">About Us</h2>
                    <p class="text-gray-700 mb-4 text-lg">
                        We are dedicated to providing exceptional {theme} services that help our clients achieve their goals.
                        With years of experience and a commitment to excellence, we deliver results that matter.
                    </p>
                    <p class="text-gray-700 mb-6">
                        Our team of professionals brings expertise, innovation, and a customer-first approach to every project.
                        We understand that every client is unique, and we tailor our solutions to meet your specific needs.
                    </p>
                    <a href="about.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg font-semibold transition">
                        Learn More
                    </a>
                </div>
                <div>
                    <img src="images/about.jpg" alt="About Us" class="rounded-xl shadow-lg w-full h-96 object-cover">
                </div>
            </div>
        </div>
    </section>""",

            'gallery_centered': f"""
    <!-- Галерея: Заголовок по центру, галерея ниже -->
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-12">
                <h2 class="text-4xl font-bold mb-4">Our Gallery</h2>
                <p class="text-gray-600 text-lg">Explore our latest projects and achievements</p>
            </div>
            <div class="grid md:grid-cols-4 gap-6">
                <div class="group relative overflow-hidden rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300">
                    <img src="images/gallery1.jpg" alt="Gallery 1" class="w-full h-64 object-cover">
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-70 transition-all duration-300 flex items-center justify-center">
                        <p class="text-white text-center px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            Professional Excellence
                        </p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300">
                    <img src="images/gallery2.jpg" alt="Gallery 2" class="w-full h-64 object-cover">
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-70 transition-all duration-300 flex items-center justify-center">
                        <p class="text-white text-center px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            Quality Service
                        </p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300">
                    <img src="images/gallery3.jpg" alt="Gallery 3" class="w-full h-64 object-cover">
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-70 transition-all duration-300 flex items-center justify-center">
                        <p class="text-white text-center px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            Innovation
                        </p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300">
                    <img src="images/gallery4.jpg" alt="Gallery 4" class="w-full h-64 object-cover">
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-70 transition-all duration-300 flex items-center justify-center">
                        <p class="text-white text-center px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            Trusted Partner
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </section>""",

            'cards_3_animated': f"""
    <!-- Секция из 3 карточек с анимацией -->
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Our Services</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="group bg-white border border-gray-200 rounded-xl p-8 hover:shadow-2xl hover:scale-105 transition-all duration-300 cursor-pointer">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-{primary} transition-colors">
                        <svg class="w-8 h-8 text-{primary} group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4 group-hover:text-{primary} transition-colors">Fast Service</h3>
                    <p class="text-gray-600 mb-6">Quick turnaround times without compromising on quality. We deliver results when you need them.</p>
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-3 rounded-lg font-semibold transition opacity-0 group-hover:opacity-100">
                        Get Started
                    </a>
                </div>
                <div class="group bg-white border border-gray-200 rounded-xl p-8 hover:shadow-2xl hover:scale-105 transition-all duration-300 cursor-pointer">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-{primary} transition-colors">
                        <svg class="w-8 h-8 text-{primary} group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4 group-hover:text-{primary} transition-colors">Quality Assured</h3>
                    <p class="text-gray-600 mb-6">Every project undergoes rigorous quality checks to ensure excellence in every detail.</p>
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-3 rounded-lg font-semibold transition opacity-0 group-hover:opacity-100">
                        Get Started
                    </a>
                </div>
                <div class="group bg-white border border-gray-200 rounded-xl p-8 hover:shadow-2xl hover:scale-105 transition-all duration-300 cursor-pointer">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-{primary} transition-colors">
                        <svg class="w-8 h-8 text-{primary} group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4 group-hover:text-{primary} transition-colors">Expert Team</h3>
                    <p class="text-gray-600 mb-6">Our experienced professionals bring knowledge and dedication to every project we undertake.</p>
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-3 rounded-lg font-semibold transition opacity-0 group-hover:opacity-100">
                        Get Started
                    </a>
                </div>
            </div>
        </div>
    </section>""",

            'image_text_alternating': f"""
    <!-- Секция 'Изображение и Текст': чередующиеся блоки -->
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <!-- Блок 1: Изображение слева, текст справа -->
            <div class="grid md:grid-cols-2 gap-12 items-center mb-20">
                <div>
                    <img src="images/service1.jpg" alt="Our Approach" class="rounded-xl shadow-lg w-full h-80 object-cover">
                </div>
                <div>
                    <h3 class="text-3xl font-bold mb-4">Our Approach</h3>
                    <p class="text-gray-700 mb-4">
                        We believe in a personalized approach to every project. Understanding your unique needs
                        allows us to deliver tailored solutions that exceed expectations.
                    </p>
                    <p class="text-gray-700">
                        Our methodology combines industry best practices with innovative thinking to ensure
                        optimal results for your business.
                    </p>
                </div>
            </div>

            <!-- Блок 2: Текст слева, изображение справа -->
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h3 class="text-3xl font-bold mb-4">Why Choose Us</h3>
                    <p class="text-gray-700 mb-4">
                        With years of experience in the {theme} industry, we've built a reputation for
                        reliability, quality, and exceptional customer service.
                    </p>
                    <p class="text-gray-700">
                        Our commitment to your success drives everything we do, from initial consultation
                        to project completion and beyond.
                    </p>
                </div>
                <div>
                    <img src="images/service2.jpg" alt="Why Choose Us" class="rounded-xl shadow-lg w-full h-80 object-cover">
                </div>
            </div>
        </div>
    </section>""",

            'cards_6_grid': f"""
    <!-- Секция из 6 карточек: два ряда по три -->
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-4">What We Offer</h2>
            <p class="text-gray-600 text-center mb-12 text-lg">Comprehensive solutions tailored to your needs</p>
            <div class="grid md:grid-cols-3 gap-6">
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">Consultation</h4>
                    <p class="text-gray-600 mb-4">Expert advice to help you make informed decisions about your project.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">Planning</h4>
                    <p class="text-gray-600 mb-4">Strategic planning to ensure your project's success from start to finish.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">Implementation</h4>
                    <p class="text-gray-600 mb-4">Professional execution with attention to every detail of your project.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">Testing</h4>
                    <p class="text-gray-600 mb-4">Thorough testing to ensure quality and reliability in all deliverables.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">Support</h4>
                    <p class="text-gray-600 mb-4">Ongoing support to help you get the most from your investment.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">Optimization</h4>
                    <p class="text-gray-600 mb-4">Continuous improvement to keep your solution performing at its best.</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
            </div>
        </div>
    </section>""",

            'gallery_horizontal': f"""
    <!-- Галерея: горизонтальная галерея из 4-5 карточек -->
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold mb-12">Our Work</h2>
            <div class="grid md:grid-cols-5 gap-4">
                <div class="group relative overflow-hidden rounded-lg shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/gallery1.jpg" alt="Project 1" class="w-full h-48 object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                        <p class="text-white font-semibold">Project Alpha</p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-lg shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/gallery2.jpg" alt="Project 2" class="w-full h-48 object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                        <p class="text-white font-semibold">Project Beta</p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-lg shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/gallery3.jpg" alt="Project 3" class="w-full h-48 object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                        <p class="text-white font-semibold">Project Gamma</p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-lg shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/gallery4.jpg" alt="Project 4" class="w-full h-48 object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                        <p class="text-white font-semibold">Project Delta</p>
                    </div>
                </div>
                <div class="group relative overflow-hidden rounded-lg shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/service1.jpg" alt="Project 5" class="w-full h-48 object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                        <p class="text-white font-semibold">Project Epsilon</p>
                    </div>
                </div>
            </div>
        </div>
    </section>""",

            'cards_3_carousel_bg': f"""
    <!-- Секция из 3 карточек с фоновой каруселью -->
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Featured Solutions</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="relative overflow-hidden rounded-xl shadow-lg h-96 group">
                    <img src="images/service1.jpg" alt="Solution 1" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent"></div>
                    <div class="relative h-full flex flex-col justify-end p-8">
                        <h3 class="text-white text-2xl font-bold mb-3">Enterprise Solutions</h3>
                        <p class="text-white/90 mb-4">Scalable solutions designed for large-scale operations and complex requirements.</p>
                        <a href="contact.php" class="inline-block bg-white text-{primary} px-6 py-3 rounded-lg font-semibold hover:bg-gray-100 transition w-fit">
                            Contact Us
                        </a>
                    </div>
                </div>
                <div class="relative overflow-hidden rounded-xl shadow-lg h-96 group">
                    <img src="images/service2.jpg" alt="Solution 2" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent"></div>
                    <div class="relative h-full flex flex-col justify-end p-8">
                        <h3 class="text-white text-2xl font-bold mb-3">Custom Development</h3>
                        <p class="text-white/90 mb-4">Tailored solutions built specifically for your unique business needs and goals.</p>
                        <a href="contact.php" class="inline-block bg-white text-{primary} px-6 py-3 rounded-lg font-semibold hover:bg-gray-100 transition w-fit">
                            Contact Us
                        </a>
                    </div>
                </div>
                <div class="relative overflow-hidden rounded-xl shadow-lg h-96 group">
                    <img src="images/service3.jpg" alt="Solution 3" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent"></div>
                    <div class="relative h-full flex flex-col justify-end p-8">
                        <h3 class="text-white text-2xl font-bold mb-3">Consulting Services</h3>
                        <p class="text-white/90 mb-4">Expert guidance to help you navigate challenges and achieve your objectives.</p>
                        <a href="contact.php" class="inline-block bg-white text-{primary} px-6 py-3 rounded-lg font-semibold hover:bg-gray-100 transition w-fit">
                            Contact Us
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </section>""",

            'carousel_workflow': f"""
    <!-- Карусель: этапы работы -->
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-4">Our Process</h2>
            <p class="text-gray-600 text-center mb-12 text-lg">Simple, transparent, and effective</p>
            <div class="relative max-w-5xl mx-auto">
                <div class="grid md:grid-cols-4 gap-6">
                    <div class="text-center">
                        <div class="w-20 h-20 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4 text-white text-2xl font-bold shadow-lg">
                            1
                        </div>
                        <div class="w-12 h-12 bg-{primary}/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
                            </svg>
                        </div>
                        <h4 class="font-bold mb-2">Consultation</h4>
                        <p class="text-gray-600 text-sm">We discuss your needs and goals</p>
                    </div>
                    <div class="text-center">
                        <div class="w-20 h-20 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4 text-white text-2xl font-bold shadow-lg">
                            2
                        </div>
                        <div class="w-12 h-12 bg-{primary}/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                            </svg>
                        </div>
                        <h4 class="font-bold mb-2">Planning</h4>
                        <p class="text-gray-600 text-sm">We create a detailed project plan</p>
                    </div>
                    <div class="text-center">
                        <div class="w-20 h-20 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4 text-white text-2xl font-bold shadow-lg">
                            3
                        </div>
                        <div class="w-12 h-12 bg-{primary}/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                            </svg>
                        </div>
                        <h4 class="font-bold mb-2">Development</h4>
                        <p class="text-gray-600 text-sm">We build your solution</p>
                    </div>
                    <div class="text-center">
                        <div class="w-20 h-20 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4 text-white text-2xl font-bold shadow-lg">
                            4
                        </div>
                        <div class="w-12 h-12 bg-{primary}/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                            </svg>
                        </div>
                        <h4 class="font-bold mb-2">Delivery</h4>
                        <p class="text-gray-600 text-sm">We deliver and support your project</p>
                    </div>
                </div>
            </div>
        </div>
    </section>""",

            'carousel_blog': f"""
    <!-- Карусель: слайдер с новостями/статьями из блога -->
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="flex justify-between items-center mb-12">
                <h2 class="text-4xl font-bold">Latest from Our Blog</h2>
                <a href="blog.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                    View All →
                </a>
            </div>
            <div class="grid md:grid-cols-3 gap-8">
                <article class="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow">
                    <img src="images/service1.jpg" alt="Blog Post 1" class="w-full h-48 object-cover">
                    <div class="p-6">
                        <p class="text-gray-500 text-sm mb-2">November 15, 2025</p>
                        <h3 class="text-xl font-bold mb-3">The Future of {theme}</h3>
                        <p class="text-gray-600 mb-4">Explore the latest innovations and what they mean for your business...</p>
                        <a href="blog1.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                            Read More →
                        </a>
                    </div>
                </article>
                <article class="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow">
                    <img src="images/service2.jpg" alt="Blog Post 2" class="w-full h-48 object-cover">
                    <div class="p-6">
                        <p class="text-gray-500 text-sm mb-2">November 10, 2025</p>
                        <h3 class="text-xl font-bold mb-3">Top 5 Trends in {theme}</h3>
                        <p class="text-gray-600 mb-4">Stay competitive with these emerging trends in the industry...</p>
                        <a href="blog2.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                            Read More →
                        </a>
                    </div>
                </article>
                <article class="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow">
                    <img src="images/service3.jpg" alt="Blog Post 3" class="w-full h-48 object-cover">
                    <div class="p-6">
                        <p class="text-gray-500 text-sm mb-2">November 5, 2025</p>
                        <h3 class="text-xl font-bold mb-3">How to Choose the Right Service</h3>
                        <p class="text-gray-600 mb-4">A comprehensive guide to selecting the best solution for your needs...</p>
                        <a href="blog3.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                            Read More →
                        </a>
                    </div>
                </article>
            </div>
        </div>
    </section>""",

            'contact_form_multistep': f"""
    <!-- Контактная форма: многошаговая -->
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6 max-w-3xl">
            <div class="text-center mb-12">
                <h2 class="text-4xl font-bold mb-4">Get Started Today</h2>
                <p class="text-gray-600 text-lg">Tell us about your project in 3 simple steps</p>
            </div>
            <div class="bg-gray-50 rounded-xl p-8 shadow-lg">
                <!-- Progress Steps -->
                <div class="flex justify-between mb-8">
                    <div class="flex items-center">
                        <div class="w-10 h-10 bg-{primary} text-white rounded-full flex items-center justify-center font-bold">1</div>
                        <span class="ml-2 font-semibold text-{primary}">Contact Info</span>
                    </div>
                    <div class="flex items-center">
                        <div class="w-10 h-10 bg-gray-300 text-white rounded-full flex items-center justify-center font-bold">2</div>
                        <span class="ml-2 text-gray-500">Project Details</span>
                    </div>
                    <div class="flex items-center">
                        <div class="w-10 h-10 bg-gray-300 text-white rounded-full flex items-center justify-center font-bold">3</div>
                        <span class="ml-2 text-gray-500">Submit</span>
                    </div>
                </div>
                <!-- Form -->
                <form action="thanks_you.php" method="POST" class="space-y-6">
                    <div>
                        <label for="name" class="block text-gray-700 font-semibold mb-2">Your Name</label>
                        <input type="text" id="name" name="name" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                    </div>
                    <div>
                        <label for="email" class="block text-gray-700 font-semibold mb-2">Your Email</label>
                        <input type="email" id="email" name="email" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                    </div>
                    <div>
                        <label for="message" class="block text-gray-700 font-semibold mb-2">Tell Us About Your Project</label>
                        <textarea id="message" name="message" rows="4" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent"></textarea>
                    </div>
                    <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-semibold transition">
                        Send Message
                    </button>
                </form>
            </div>
        </div>
    </section>""",

            'cards_6_slider': f"""
    <!-- Секция из 6 карточек: слайдер -->
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="flex justify-between items-center mb-12">
                <h2 class="text-4xl font-bold">Our Locations</h2>
                <div class="flex gap-4">
                    <button class="w-10 h-10 bg-{primary} text-white rounded-full flex items-center justify-center hover:bg-{hover} transition">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                        </svg>
                    </button>
                    <button class="w-10 h-10 bg-{primary} text-white rounded-full flex items-center justify-center hover:bg-{hover} transition">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="grid md:grid-cols-3 gap-6">
                <div class="bg-white rounded-xl p-6 shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/gallery1.jpg" alt="Location 1" class="w-full h-40 object-cover rounded-lg mb-4">
                    <h4 class="text-xl font-bold mb-2">New York Office</h4>
                    <p class="text-gray-600 mb-4">Our headquarters serving the East Coast market with dedicated professionals.</p>
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-2 rounded-lg font-semibold transition">
                        Contact
                    </a>
                </div>
                <div class="bg-white rounded-xl p-6 shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/gallery2.jpg" alt="Location 2" class="w-full h-40 object-cover rounded-lg mb-4">
                    <h4 class="text-xl font-bold mb-2">San Francisco Office</h4>
                    <p class="text-gray-600 mb-4">West Coast hub bringing innovation and technology expertise to your doorstep.</p>
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-2 rounded-lg font-semibold transition">
                        Contact
                    </a>
                </div>
                <div class="bg-white rounded-xl p-6 shadow-md hover:shadow-xl transition-shadow">
                    <img src="images/gallery3.jpg" alt="Location 3" class="w-full h-40 object-cover rounded-lg mb-4">
                    <h4 class="text-xl font-bold mb-2">Chicago Office</h4>
                    <p class="text-gray-600 mb-4">Central location serving clients across the Midwest with excellence.</p>
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-2 rounded-lg font-semibold transition">
                        Contact
                    </a>
                </div>
            </div>
        </div>
    </section>"""
        }

        # Выбираем 5-6 случайных секций
        section_keys = list(all_sections.keys())
        random.shuffle(section_keys)
        num_sections = random.randint(5, 6)
        selected_sections = section_keys[:num_sections]

        print(f"  ✓ Выбрано {num_sections} случайных секций для Home страницы: {', '.join(selected_sections)}")

        # Возвращаем выбранные секции
        return '\n'.join([all_sections[key] for key in selected_sections])

    def generate_page(self, page_name, output_dir):
        """Генерация страницы с максимальным качеством"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        
        # Для policy страниц используем готовый контент
        if page_name in ['privacy', 'terms', 'cookie']:
            return self.generate_policy_page(page_name, output_dir)
        
        # Для blog страниц используем готовый контент
        if page_name in ['blog1', 'blog2', 'blog3']:
            return self.generate_blog_page(page_name, output_dir)
        
        # Для главной страницы blog (список статей)
        if page_name == 'blog':
            return self.generate_blog_main_page(output_dir)

        # Для Contact страницы используем готовый профессиональный шаблон
        if page_name == 'contact':
            return self.generate_contact_page(output_dir)

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
  * "Learn More" button that links to about.php: <a href="about.php" class="...">Learn More</a>
  * Responsive grid layout (text left, image right on desktop; stacked on mobile)
- Services showcase section (3 services) with CTA buttons to contact.php
- Testimonials section (2-3 testimonials with circular avatar badges containing initials, NO images)
- For testimonials: use colored circles with white text initials (e.g. JD, MS) instead of photos
- Call-to-action section at the end with button to contact.php
- ALL other CTA buttons on the page MUST link to contact.php (except the About Us "Learn More" which goes to about.php)
- Use images for hero, about section, and services (images/hero.jpg, images/about.jpg, images/service1.jpg)
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Include proper spacing, padding, and responsive design
- NO emojis, NO prices, NO currency symbols

CRITICAL: About Us section MUST have images/about.jpg image and "Learn More" button linking to about.php
CRITICAL: Every OTHER button on this page MUST have href="contact.php"
CRITICAL: Testimonials MUST use avatar circles with initials, NOT images

Return ONLY the content for <main> tag (not full HTML)."""
            },
            'about': {
                'title': 'About Us',
                'prompt': f"""Create a professional ABOUT page for {site_name} - a {theme} business.

REQUIREMENTS:
- Heading section with page title
- Company story/mission section
- Team or values section
- Image + text layout (use images/about.jpg)
- MUST include a call-to-action button at the bottom that redirects to contact.php: <a href="contact.php" class="...">Contact Us</a>
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Responsive design
- NO emojis, NO prices

CRITICAL: Page MUST have a CTA button at the bottom that links to contact.php

Return ONLY the content for <main> tag."""
            },
            'services': {
                'title': 'Services',
                'prompt': f"""Create a professional SERVICES page for {site_name} - a {theme} business.

REQUIREMENTS:
- Grid of service cards (3-4 services)
- Each card: image, title, description
- Use images: images/service1.jpg, images/service2.jpg, images/service3.jpg
- Call-to-action buttons linking to contact.php
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Responsive grid layout
- NO emojis, NO prices, NO currency

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
- NO emojis

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

            # Hero секция (статичная - всегда присутствует)
            hero_section = f"""<main>
    <!-- Hero Section (Static) -->
    <section class="relative py-32 bg-gradient-to-br from-{primary}/10 via-white to-{primary}/5">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto text-center">
                <h1 class="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-{primary} to-{hover} bg-clip-text text-transparent">
                    Welcome to {site_name}
                </h1>
                <p class="text-xl md:text-2xl text-gray-600 mb-8">
                    Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.
                </p>
                <div class="flex flex-col sm:flex-row gap-4 justify-center">
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        Get Started
                    </a>
                    <a href="about.php" class="inline-block bg-white hover:bg-gray-50 text-{primary} border-2 border-{primary} px-8 py-4 rounded-lg text-lg font-semibold transition">
                        Learn More
                    </a>
                </div>
            </div>
        </div>
        <!-- Decorative elements -->
        <div class="absolute top-0 right-0 w-64 h-64 bg-{primary}/10 rounded-full blur-3xl"></div>
        <div class="absolute bottom-0 left-0 w-96 h-96 bg-{hover}/10 rounded-full blur-3xl"></div>
    </section>
"""

            # Добавляем случайные секции
            random_sections = self.generate_home_sections()

            # Собираем main_content
            main_content = hero_section + random_sections + "\n</main>"
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
        if not self.header_code or not self.footer_code:
            print(f"    ⚠️  Header/Footer не найдены, регенерация...")
            self.generate_header_footer()
        
        # Собираем полную страницу
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config['title']} - {site_name}</title>
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
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
    <!-- Hero Section -->
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
    
    <!-- Features Section -->
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Why Choose Us</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="text-center p-6">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Quality Service</h3>
                    <p class="text-gray-600">We deliver exceptional quality in everything we do.</p>
                </div>
                <div class="text-center p-6">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Fast Delivery</h3>
                    <p class="text-gray-600">Quick turnaround times without compromising quality.</p>
                </div>
                <div class="text-center p-6">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Expert Team</h3>
                    <p class="text-gray-600">Experienced professionals dedicated to your success.</p>
                </div>
            </div>
        </div>
    </section>
    
    <!-- About Preview Section -->
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center max-w-6xl mx-auto">
                <div>
                    <h2 class="text-4xl font-bold mb-6">About {site_name}</h2>
                    <p class="text-xl text-gray-600 mb-8">
                        We are dedicated to providing excellent service and building lasting relationships with our clients. 
                        Our team brings years of experience and expertise to every project.
                    </p>
                    <a href="about.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                        Learn More
                    </a>
                </div>
                <div class="rounded-xl overflow-hidden shadow-lg">
                    <img src="images/about.jpg" alt="About Us" class="w-full h-full object-cover">
                </div>
            </div>
        </div>
    </section>
    
    <!-- Services Section -->
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
    
    <!-- Testimonials Section -->
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
    
    <!-- Final CTA Section -->
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
            'about': f"""<main>
    <section class="py-20">
        <div class="container mx-auto px-6">
            <h1 class="text-5xl font-bold text-center mb-12">About {site_name}</h1>
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
        """Генерация blog страниц с вариациями (с/без картинки, с/без стрелок)"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        blog_titles = {
            'blog1': f'The Future of {theme}',
            'blog2': f'Top 5 Trends in {theme}',
            'blog3': f'How to Choose the Right {theme} Service'
        }

        blog_contents = {
            'blog1': f"""
            <p class="text-lg text-gray-700 mb-6">
                The {theme} industry is evolving rapidly, and staying ahead of the curve is essential for success.
                In this article, we explore the latest innovations and what they mean for your business.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Key Innovations</h2>
            <p class="text-gray-700 mb-6">
                Recent technological advances have transformed how we approach {theme}. From automation to
                personalized services, the landscape is changing faster than ever before.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">What This Means For You</h2>
            <p class="text-gray-700 mb-6">
                Understanding these changes can help you make better decisions for your needs. Whether you're
                looking to upgrade your current setup or start fresh, staying informed is crucial.
            </p>
            """,
            'blog2': f"""
            <p class="text-lg text-gray-700 mb-6">
                The {theme} sector is constantly evolving. Here are the top 5 trends you need to know about
                to stay competitive in today's market.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">1. Digital Transformation</h2>
            <p class="text-gray-700 mb-6">
                More businesses are embracing digital solutions to streamline operations and improve customer experience.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">2. Sustainability Focus</h2>
            <p class="text-gray-700 mb-6">
                Environmental responsibility is becoming a key differentiator in the {theme} industry.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">3. Personalization</h2>
            <p class="text-gray-700 mb-6">
                Customers expect tailored solutions that meet their specific needs and preferences.
            </p>
            """,
            'blog3': f"""
            <p class="text-lg text-gray-700 mb-6">
                Choosing the right {theme} service can be challenging. This guide will help you make an
                informed decision that's right for your needs.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Assess Your Needs</h2>
            <p class="text-gray-700 mb-6">
                Start by clearly defining what you need from a {theme} service. Consider your budget,
                timeline, and specific requirements.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Research Options</h2>
            <p class="text-gray-700 mb-6">
                Take time to research different providers and compare their offerings. Look for reviews,
                testimonials, and case studies.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Make Contact</h2>
            <p class="text-gray-700 mb-6">
                Don't hesitate to reach out to providers directly. A good consultation can help you
                determine if they're the right fit for your needs.
            </p>
            """
        }

        blog_images = {
            'blog1': 'images/service1.jpg',
            'blog2': 'images/service2.jpg',
            'blog3': 'images/service3.jpg'
        }

        # Определяем навигацию между blog страницами
        blog_nav = {
            'blog1': {'prev': None, 'next': 'blog2.php'},
            'blog2': {'prev': 'blog1.php', 'next': 'blog3.php'},
            'blog3': {'prev': 'blog2.php', 'next': None}
        }

        # Вариации: blog1 - без картинки со стрелками, blog2 - с картинкой без стрелок, blog3 - без картинки без стрелок
        blog_variations = {
            'blog1': {'has_image': False, 'has_arrows': True},
            'blog2': {'has_image': True, 'has_arrows': False},
            'blog3': {'has_image': False, 'has_arrows': False}
        }

        current_nav = blog_nav.get(page_name, {'prev': None, 'next': None})
        current_variation = blog_variations.get(page_name, {'has_image': True, 'has_arrows': True})

        # Создаем навигационные кнопки (только если has_arrows=True)
        nav_buttons = ''
        if current_variation['has_arrows']:
            nav_buttons = '<div class="flex justify-between items-center mt-12 pt-8 border-t border-gray-200">'

            if current_nav['prev']:
                nav_buttons += f'''
                    <a href="{current_nav['prev']}" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition">
                        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                        </svg>
                        Previous Article
                    </a>
                '''
            else:
                nav_buttons += '<div></div>'

            if current_nav['next']:
                nav_buttons += f'''
                    <a href="{current_nav['next']}" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition">
                        Next Article
                        <svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </a>
                '''
            else:
                nav_buttons += '<div></div>'

            nav_buttons += '</div>'
        else:
            # Без стрелок - простые текстовые ссылки
            nav_links = []
            if current_nav['prev']:
                nav_links.append(f'<a href="{current_nav["prev"]}" class="text-{primary} hover:text-{hover} font-semibold transition">Previous Article</a>')
            if current_nav['next']:
                nav_links.append(f'<a href="{current_nav["next"]}" class="text-{primary} hover:text-{hover} font-semibold transition">Next Article</a>')

            if nav_links:
                nav_buttons = f'<div class="flex justify-between items-center mt-12 pt-8 border-t border-gray-200">{" <span class=\"text-gray-400\">|</span> ".join(nav_links)}</div>'

        # Создаем секцию с картинкой (если has_image=True)
        image_section = ''
        if current_variation['has_image']:
            image_section = f'''
        <div class="mb-8 rounded-xl overflow-hidden">
            <img src="{blog_images[page_name]}" alt="{blog_titles[page_name]}" class="w-full h-96 object-cover">
        </div>
        '''

        main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">{blog_titles[page_name]}</h1>
        <p class="text-gray-500 mb-8">Published on November 15, 2025 by {site_name} Team</p>

        {image_section}

        <div class="prose prose-lg max-w-none">
            {blog_contents[page_name]}
        </div>

        {nav_buttons}

        <!-- Call to Action -->
        <div class="mt-12 p-8 bg-gradient-to-br from-{primary}/10 to-{primary}/5 rounded-xl text-center">
            <h3 class="text-2xl font-bold mb-4">Interested in Our Services?</h3>
            <p class="text-gray-700 mb-6">Get in touch with us today to learn how we can help your business grow.</p>
            <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                Contact Us
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
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
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
        """Генерация главной страницы blog со списком статей"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')
        
        blog_articles = [
            {
                'title': f'The Future of {theme}',
                'url': 'blog1.php',
                'excerpt': f'Explore the latest innovations in {theme} and what they mean for your business.',
                'date': 'November 15, 2025',
                'image': 'images/service1.jpg'
            },
            {
                'title': f'Top 5 Trends in {theme}',
                'url': 'blog2.php',
                'excerpt': f'Stay competitive with these emerging trends in the {theme} industry.',
                'date': 'November 10, 2025',
                'image': 'images/service2.jpg'
            },
            {
                'title': f'How to Choose the Right {theme} Service',
                'url': 'blog3.php',
                'excerpt': f'A comprehensive guide to selecting the best {theme} solution for your needs.',
                'date': 'November 5, 2025',
                'image': 'images/service3.jpg'
            }
        ]
        
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
                        Read More
                        <svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            <h1 class="text-5xl md:text-6xl font-bold mb-6">Our Blog</h1>
            <p class="text-xl md:text-2xl text-gray-600">Insights, tips, and news about {theme}</p>
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

<!-- CTA Section -->
<section class="py-20 bg-gray-50">
    <div class="container mx-auto px-6">
        <div class="max-w-4xl mx-auto text-center">
            <h2 class="text-4xl font-bold mb-6">Want to Learn More?</h2>
            <p class="text-xl text-gray-600 mb-8">Contact us to discuss your specific needs and how we can help.</p>
            <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                Get in Touch
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
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
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
        
        titles = {
            'privacy': 'Privacy Policy',
            'terms': 'Terms of Service',
            'cookie': 'Cookie Policy'
        }
        
        # УНИКАЛЬНЫЙ контент для каждой страницы
        if page_name == 'privacy':
            main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold text-center mb-4">{titles[page_name]}</h1>
        <p class="text-gray-500 text-center mb-12">Last updated: November 14, 2025</p>
        
        <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed">
        
        <h2 class="text-2xl font-bold mt-8 mb-4">1. Introduction</h2>
        <p>{site_name} ("us", "we", or "our") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you visit our website.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">2. Information We Collect</h2>
        <p>We may collect information about you in a variety of ways. The information we may collect includes:</p>
        
        <h3 class="text-xl font-semibold mt-6 mb-3">Personal Data</h3>
        <ul class="list-disc pl-6 my-4">
            <li>Name and contact information (email address, phone number)</li>
            <li>Demographic information (age, gender, interests)</li>
            <li>Payment information for transactions</li>
            <li>Any other information you voluntarily provide</li>
        </ul>
        
        <h3 class="text-xl font-semibold mt-6 mb-3">Usage Data</h3>
        <ul class="list-disc pl-6 my-4">
            <li>IP address and browser type</li>
            <li>Pages visited and time spent on pages</li>
            <li>Referring website addresses</li>
            <li>Device information</li>
        </ul>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">3. How We Use Your Information</h2>
        <p>We use the information we collect to:</p>
        <ul class="list-disc pl-6 my-4">
            <li>Provide, operate, and maintain our website and services</li>
            <li>Improve and personalize your experience</li>
            <li>Communicate with you about updates, offers, and news</li>
            <li>Process transactions and send transaction notifications</li>
            <li>Monitor and analyze usage patterns and trends</li>
            <li>Detect, prevent, and address technical issues and fraud</li>
        </ul>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">4. Data Security</h2>
        <p>We implement appropriate security measures to protect your personal information. However, no method of transmission over the Internet is 100% secure, and we cannot guarantee absolute security.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">5. Your Rights</h2>
        <p>You have the right to access, update, or delete your personal information at any time. You may also opt-out of marketing communications.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">6. Contact Us</h2>
        <p>If you have any questions about this Privacy Policy, please contact us at:</p>
        <p class="mt-2">Email: privacy@{site_name.lower().replace(' ', '')}.com</p>
        </div>
    </div>
</section>
</main>"""
        
        elif page_name == 'terms':
            main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold text-center mb-4">{titles[page_name]}</h1>
        <p class="text-gray-500 text-center mb-12">Last updated: November 14, 2025</p>
        
        <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed">
        
        <h2 class="text-2xl font-bold mt-8 mb-4">1. Agreement to Terms</h2>
        <p>By accessing and using {site_name}'s website, you accept and agree to be bound by the terms and provisions of this agreement. If you do not agree to these Terms of Service, please do not use this website.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">2. Use License</h2>
        <p>Permission is granted to temporarily access the materials on {site_name}'s website for personal, non-commercial use only. This is the grant of a license, not a transfer of title, and under this license you may not:</p>
        <ul class="list-disc pl-6 my-4">
            <li>Modify or copy the materials</li>
            <li>Use the materials for any commercial purpose</li>
            <li>Attempt to decompile or reverse engineer any software</li>
            <li>Remove any copyright or proprietary notations</li>
            <li>Transfer the materials to another person</li>
        </ul>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">3. User Responsibilities</h2>
        <p>As a user of our website, you agree to:</p>
        <ul class="list-disc pl-6 my-4">
            <li>Provide accurate and complete information</li>
            <li>Maintain the security of your account credentials</li>
            <li>Notify us immediately of any unauthorized use</li>
            <li>Not engage in any activity that disrupts or interferes with our services</li>
            <li>Comply with all applicable laws and regulations</li>
        </ul>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">4. Disclaimer</h2>
        <p>The materials on {site_name}'s website are provided on an 'as is' basis. {site_name} makes no warranties, expressed or implied, and hereby disclaims all other warranties including, without limitation, implied warranties or conditions of merchantability, fitness for a particular purpose, or non-infringement of intellectual property.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">5. Limitations of Liability</h2>
        <p>In no event shall {site_name} or its suppliers be liable for any damages arising out of the use or inability to use the materials on our website.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">6. Modifications</h2>
        <p>{site_name} may revise these Terms of Service at any time without notice. By using this website, you agree to be bound by the current version of these terms.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">7. Contact Information</h2>
        <p>For questions about these Terms of Service, please contact us at:</p>
        <p class="mt-2">Email: legal@{site_name.lower().replace(' ', '')}.com</p>
        </div>
    </div>
</section>
</main>"""
        
        elif page_name == 'cookie':
            main_content = f"""<main>
<section class="py-20 bg-white">
    <div class="container mx-auto px-6 max-w-4xl">
        <h1 class="text-4xl md:text-5xl font-bold text-center mb-4">{titles[page_name]}</h1>
        <p class="text-gray-500 text-center mb-12">Last updated: November 14, 2025</p>
        
        <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed">
        
        <h2 class="text-2xl font-bold mt-8 mb-4">1. What Are Cookies</h2>
        <p>Cookies are small text files that are placed on your device when you visit our website. They help us provide you with a better experience by remembering your preferences and understanding how you use our site.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">2. Types of Cookies We Use</h2>
        
        <h3 class="text-xl font-semibold mt-6 mb-3">Essential Cookies</h3>
        <p>These cookies are necessary for the website to function properly. They enable basic functions like page navigation and access to secure areas of the website.</p>
        
        <h3 class="text-xl font-semibold mt-6 mb-3">Analytics Cookies</h3>
        <p>We use analytics cookies to understand how visitors interact with our website. This helps us improve our content and user experience. These cookies collect information anonymously.</p>
        
        <h3 class="text-xl font-semibold mt-6 mb-3">Functionality Cookies</h3>
        <p>These cookies allow our website to remember choices you make (such as your language preference) and provide enhanced, personalized features.</p>
        
        <h3 class="text-xl font-semibold mt-6 mb-3">Advertising Cookies</h3>
        <p>We may use advertising cookies to deliver relevant advertisements to you and track the effectiveness of our marketing campaigns.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">3. Third-Party Cookies</h2>
        <p>In addition to our own cookies, we may use various third-party cookies to report usage statistics, deliver advertisements, and provide social media features.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">4. Managing Cookies</h2>
        <p>You can control and/or delete cookies as you wish. You can delete all cookies that are already on your computer and you can set most browsers to prevent them from being placed. However, if you do this, you may have to manually adjust some preferences every time you visit our site.</p>
        
        <h3 class="text-xl font-semibold mt-6 mb-3">How to Control Cookies</h3>
        <ul class="list-disc pl-6 my-4">
            <li>Browser settings: Most browsers allow you to refuse or accept cookies</li>
            <li>Third-party tools: Use browser extensions or privacy tools</li>
            <li>Opt-out links: Some third-party services provide opt-out mechanisms</li>
        </ul>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">5. Updates to This Policy</h2>
        <p>We may update this Cookie Policy from time to time. We encourage you to review this page periodically for any changes.</p>
        
        <h2 class="text-2xl font-bold mt-8 mb-4">6. Contact Us</h2>
        <p>If you have questions about our use of cookies, please contact us at:</p>
        <p class="mt-2">Email: cookies@{site_name.lower().replace(' ', '')}.com</p>
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
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
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
    
    
    # ============= МЕТОДЫ ДЛЯ TWIG TEMPLATE ENGINE =============
    
    def create_twig_templates(self, output_dir):
        """Создание Twig шаблонов для сайта"""
        templates_dir = os.path.join(output_dir, 'templates')
        os.makedirs(templates_dir, exist_ok=True)
        
        print("  🎨 Создание Twig шаблонов...")
        
        # Создаем базовый layout
        self.create_base_layout_twig(templates_dir)
        
        # Создаем компоненты
        self.create_twig_components(templates_dir)
        
        # Создаем страницы
        self.create_twig_pages(templates_dir)
        
        print("  ✓ Twig шаблоны созданы")
    
    def create_base_layout_twig(self, templates_dir):
        """Создание базового Twig layout"""
        site_name = self.blueprint.get('site_name', 'Company')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')
        theme = self.blueprint.get('theme', 'business')
        
        base_layout = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{{{ page_title }}}} - {site_name}</title>
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ height: 100%; }}
        body {{ 
            font-family: 'Inter', system-ui, sans-serif; 
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        main {{ flex: 1; }}
        footer {{ margin-top: auto; }}
    </style>
</head>
<body>
    <!-- Header -->
    <header class="bg-white shadow-md sticky top-0 z-50">
        <div class="container mx-auto px-6 py-4">
            <div class="flex justify-between items-center">
                <div class="text-2xl font-bold text-{primary}">
                    {site_name}
                </div>
                <nav class="hidden md:flex space-x-8">
                    {{% for item in navigation %}}
                    <a href="{{{{ item.url }}}}" class="text-gray-700 hover:text-{hover} transition-colors">{{{{ item.name }}}}</a>
                    {{% endfor %}}
                </nav>
                <button id="mobile-menu-btn" class="md:hidden text-gray-700 hover:text-{hover}">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                    </svg>
                </button>
            </div>
            <nav id="mobile-menu" class="hidden md:hidden mt-4 pb-4">
                {{% for item in navigation %}}
                <a href="{{{{ item.url }}}}" class="block py-2 text-gray-700 hover:text-{hover} transition-colors">{{{{ item.name }}}}</a>
                {{% endfor %}}
            </nav>
        </div>
        <script>
            document.getElementById('mobile-menu-btn').addEventListener('click', function() {{
                document.getElementById('mobile-menu').classList.toggle('hidden');
            }});
        </script>
    </header>

    {{% block content %}}
    {{% endblock %}}

    <footer class="bg-gray-900 text-white py-12 mt-auto">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-3 gap-8">
                <div>
                    <h3 class="text-xl font-bold mb-4">{site_name}</h3>
                    <p class="text-gray-400">Your trusted partner in {theme}.</p>
                </div>
                <div>
                    <h4 class="text-lg font-semibold mb-4">Quick Links</h4>
                    <ul class="space-y-2">
                        {{% for item in footer_links %}}
                        <li><a href="{{{{ item.url }}}}" class="text-gray-400 hover:text-{hover} transition-colors">{{{{ item.name }}}}</a></li>
                        {{% endfor %}}
                    </ul>
                </div>
                <div>
                    <h4 class="text-lg font-semibold mb-4">Contact</h4>
                    <p class="text-gray-400">Email: contact@{site_name.lower().replace(' ', '')}.com</p>
                    <p class="text-gray-400">Phone: +1 (555) 123-4567</p>
                </div>
            </div>
            <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
                <p>&copy; 2025 {site_name}. All rights reserved.</p>
            </div>
        </div>
    </footer>
</body>
</html>"""
        
        with open(os.path.join(templates_dir, 'base.twig'), 'w', encoding='utf-8') as f:
            f.write(base_layout)
    
    def create_twig_components(self, templates_dir):
        """Создание Twig компонентов"""
        components_dir = os.path.join(templates_dir, 'components')
        os.makedirs(components_dir, exist_ok=True)
        
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')
        
        # Hero Section
        hero = f"""<section class="py-20 bg-gradient-to-br from-{primary}/10 to-white">
    <div class="container mx-auto px-6">
        <div class="max-w-4xl mx-auto text-center">
            <h1 class="text-5xl md:text-6xl font-bold mb-6">{{{{ hero.title }}}}</h1>
            <p class="text-xl md:text-2xl text-gray-600 mb-8">{{{{ hero.subtitle }}}}</p>
            {{% if hero.cta_text %}}
            <a href="{{{{ hero.cta_url }}}}" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                {{{{ hero.cta_text }}}}
            </a>
            {{% endif %}}
        </div>
    </div>
</section>"""
        
        with open(os.path.join(components_dir, 'hero.twig'), 'w', encoding='utf-8') as f:
            f.write(hero)
        
        # Service Card
        service = f"""<div class="bg-white p-8 rounded-xl shadow-lg hover:shadow-xl transition">
    {{% if service.image %}}
    <img src="{{{{ service.image }}}}" alt="{{{{ service.title }}}}" class="w-full h-48 object-cover rounded-lg mb-4">
    {{% endif %}}
    <h3 class="text-2xl font-bold mb-4">{{{{ service.title }}}}</h3>
    <p class="text-gray-600 mb-4">{{{{ service.description }}}}</p>
    {{% if service.link %}}
    <a href="{{{{ service.link }}}}" class="text-{primary} hover:text-{hover} font-semibold">Learn More →</a>
    {{% endif %}}
</div>"""
        
        with open(os.path.join(components_dir, 'service_card.twig'), 'w', encoding='utf-8') as f:
            f.write(service)
        
        # Contact Form
        form = f"""<form action="thanks_you.php" method="POST" class="space-y-6">
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
</form>"""
        
        with open(os.path.join(components_dir, 'contact_form.twig'), 'w', encoding='utf-8') as f:
            f.write(form)
    
    def create_twig_pages(self, templates_dir):
        """Создание Twig страниц"""
        pages_dir = os.path.join(templates_dir, 'pages')
        os.makedirs(pages_dir, exist_ok=True)
        
        site_name = self.blueprint.get('site_name', 'Company')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')
        
        # Index Page
        index = f"""{{% extends "base.twig" %}}

{{% block content %}}
<main>
    {{% include "components/hero.twig" with {{
        'hero': {{
            'title': 'Welcome to {site_name}',
            'subtitle': 'Your trusted partner in excellence',
            'cta_text': 'Get Started',
            'cta_url': 'contact.php'
        }}
    }} %}}
    
    <section class="py-20">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Our Services</h2>
            <div class="grid md:grid-cols-3 gap-8">
                {{% for service in services %}}
                {{% include "components/service_card.twig" with {{'service': service}} %}}
                {{% endfor %}}
            </div>
        </div>
    </section>
    
    <section class="py-20 bg-gradient-to-br from-{primary}/10 to-{primary}/5">
        <div class="container mx-auto px-6 text-center">
            <h2 class="text-4xl font-bold mb-6">Ready to Get Started?</h2>
            <p class="text-xl text-gray-600 mb-8">Contact us today to learn how we can help.</p>
            <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                Contact Us
            </a>
        </div>
    </section>
</main>
{{% endblock %}}"""
        
        with open(os.path.join(pages_dir, 'index.twig'), 'w', encoding='utf-8') as f:
            f.write(index)
        
        # Contact Page
        contact = f"""{{% extends "base.twig" %}}

{{% block content %}}
<main>
    <section class="py-20">
        <div class="container mx-auto px-6">
            <h1 class="text-5xl font-bold text-center mb-12">Contact Us</h1>
            <div class="max-w-2xl mx-auto">
                {{% include "components/contact_form.twig" %}}
            </div>
        </div>
    </section>
</main>
{{% endblock %}}"""
        
        with open(os.path.join(pages_dir, 'contact.twig'), 'w', encoding='utf-8') as f:
            f.write(contact)
    
    def create_composer_json(self, output_dir):
        """Создание composer.json для Twig"""
        composer = {
            "name": "php-website-generator/twig-site",
            "description": "Generated PHP website with Twig templates",
            "type": "project",
            "require": {
                "php": ">=7.4",
                "twig/twig": "^3.0"
            }
        }
        
        import json
        with open(os.path.join(output_dir, 'composer.json'), 'w', encoding='utf-8') as f:
            json.dump(composer, f, indent=4)
        
        print("  ✓ composer.json создан")
    
    def create_twig_renderer_php(self, output_dir):
        """PHP файл для рендеринга Twig"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        
        if self.site_type == "landing":
            nav = "['name' => 'Home', 'url' => 'index.php'], ['name' => 'Contact', 'url' => 'index.php#contact']"
            footer = "['name' => 'Home', 'url' => 'index.php'], ['name' => 'Privacy', 'url' => 'privacy.php'], ['name' => 'Terms', 'url' => 'terms.php']"
        else:
            nav = "['name' => 'Home', 'url' => 'index.php'], ['name' => 'About', 'url' => 'about.php'], ['name' => 'Services', 'url' => 'services.php'], ['name' => 'Blog', 'url' => 'blog1.php'], ['name' => 'Contact', 'url' => 'contact.php']"
            footer = "['name' => 'Home', 'url' => 'index.php'], ['name' => 'About', 'url' => 'about.php'], ['name' => 'Services', 'url' => 'services.php'], ['name' => 'Contact', 'url' => 'contact.php'], ['name' => 'Privacy', 'url' => 'privacy.php']"
        
        php = f"""<?php
require_once 'vendor/autoload.php';

use Twig\\Loader\\FilesystemLoader;
use Twig\\Environment;

$loader = new FilesystemLoader('templates');
$twig = new Environment($loader, ['cache' => false]);

$globalData = [
    'site_name' => '{site_name}',
    'theme' => '{theme}',
    'navigation' => [{nav}],
    'footer_links' => [{footer}]
];

$indexData = array_merge($globalData, [
    'page_title' => 'Home',
    'services' => [
        ['title' => 'Service One', 'description' => 'Comprehensive solution.', 'image' => 'images/service1.jpg', 'link' => 'contact.php'],
        ['title' => 'Service Two', 'description' => 'Professional expertise.', 'image' => 'images/service2.jpg', 'link' => 'contact.php'],
        ['title' => 'Service Three', 'description' => 'Innovative solutions.', 'image' => 'images/service3.jpg', 'link' => 'contact.php']
    ]
]);

file_put_contents('index_twig.php', $twig->render('pages/index.twig', $indexData));
echo "✓ index_twig.php\n";

$contactData = array_merge($globalData, ['page_title' => 'Contact Us']);
file_put_contents('contact_twig.php', $twig->render('pages/contact.twig', $contactData));
echo "✓ contact_twig.php\n";

echo "\n✨ Twig templates rendered!\n";
?>"""
        
        with open(os.path.join(output_dir, 'render_twig.php'), 'w', encoding='utf-8') as f:
            f.write(php)
        
        print("  ✓ render_twig.php создан")
    
    def create_readme_twig(self, output_dir):
        """README для Twig"""
        readme = f"""# {self.blueprint.get('site_name', 'Website')} - Twig Edition

🎨 Этот сайт использует **Twig Template Engine** для профессиональной работы с шаблонами.

## 🚀 Быстрый старт

### 1. Установка Twig

```bash
composer install
```

### 2. Рендеринг шаблонов

```bash
php render_twig.php
```

Будут созданы:
- `index_twig.php` - главная страница
- `contact_twig.php` - страница контактов

### 3. Запуск сервера

```bash
php -S localhost:8000
```

Откройте: http://localhost:8000/index_twig.php

## 📁 Структура

```
.
├── templates/              # Twig шаблоны
│   ├── base.twig          # Базовый layout
│   ├── components/        # Компоненты
│   │   ├── hero.twig
│   │   ├── service_card.twig
│   │   └── contact_form.twig
│   └── pages/             # Страницы
│       ├── index.twig
│       └── contact.twig
├── images/                # Изображения
├── composer.json          # Зависимости
└── render_twig.php        # Рендеринг
```

## 🎨 Синтаксис Twig

**Переменные:**
```twig
{{{{ variable }}}}
```

**Условия:**
```twig
{{% if condition %}}...{{% endif %}}
```

**Циклы:**
```twig
{{% for item in items %}}...{{% endfor %}}
```

**Наследование:**
```twig
{{% extends "base.twig" %}}
{{% block content %}}...{{% endblock %}}
```

**Компоненты:**
```twig
{{% include "components/hero.twig" %}}
```

## 📚 Документация

- Twig: https://twig.symfony.com/doc/
- Tailwind: https://tailwindcss.com/docs

## ✏️ Редактирование

1. Измените файлы в `templates/`
2. Запустите `php render_twig.php`
3. Обновите страницу в браузере

## 🔧 Troubleshooting

**Ошибка: "Class 'Twig' not found"**
→ Запустите: `composer install`

**Изменения не видны:**
→ Запустите: `php render_twig.php`
→ Очистите кэш браузера

Сгенерировано PHP Website Generator v2.3 с Twig Integration
"""
        
        with open(os.path.join(output_dir, 'README_TWIG.md'), 'w', encoding='utf-8') as f:
            f.write(readme)
        
        print("  ✓ README_TWIG.md создан")
    
    # ============= КОНЕЦ МЕТОДОВ TWIG =============
    
    
    def generate_website(self, user_prompt, output_dir="generated_website", data_dir="data", site_type="multipage"):
        """Основной метод генерации"""
        self.site_type = site_type
        
        print("=" * 60)
        print(f"ГЕНЕРАТОР PHP {'ЛЕНДИНГОВ' if site_type == 'landing' else 'САЙТОВ'} v2.2")
        print("=" * 60)
        
        Path(output_dir).mkdir(exist_ok=True)
        
        print("\n[1/7] Загрузка БД...")
        self.load_database(data_dir)
        
        print("\n[2/7] Blueprint (уникальное название, цвета, layouts)...")
        if not self.create_blueprint(user_prompt):
            print("⚠️  Ошибка Blueprint (использован fallback)")
        
        print("\n[3/7] Header и Footer (без соц. сетей, единый hover)...")
        if not self.generate_header_footer():
            print("⚠️  Ошибка Header/Footer (использован fallback)")
        
        print("\n[4/7] Favicon...")
        self.generate_favicon(output_dir)
        
        print("\n[5/7] Изображения...")
        self.generate_images_for_site(output_dir)
        
        print("\n[6/7] Страницы...")
        
        if site_type == "landing":
            # Лендинг - только главная страница с секциями + служебные страницы
            pages_to_generate = ['index', 'thanks_you', 'privacy', 'terms', 'cookie']
            print("  Режим: ЛЕНДИНГ (одна страница с секциями)")
        else:
            # Многостраничный сайт - все основные страницы включая blog
            pages_to_generate = ['index', 'about', 'services', 'contact', 'blog', 'blog1', 'blog2', 'blog3', 'privacy', 'terms', 'cookie', 'thanks_you']
            print("  Режим: МНОГОСТРАНИЧНЫЙ САЙТ (все страницы + blog главная + статьи)")
        
        # Генерируем каждую страницу с повышенным вниманием
        for page in pages_to_generate:
            print(f"  Генерация {page}.php...")
            success = self.generate_page(page, output_dir)
            if not success:
                print(f"    ⚠️  Ошибка генерации {page}.php, создан fallback")
        
        print("\n[7/7] Twig шаблоны и дополнительные файлы...")
        
        # Создаём Twig шаблоны если включено
        if self.use_twig:
            self.create_twig_templates(output_dir)
            self.create_composer_json(output_dir)
            self.create_twig_renderer_php(output_dir)
            self.create_readme_twig(output_dir)
            print("  ✓ Twig интеграция завершена")
        self.generate_additional_files(output_dir)
        
        print("\n" + "=" * 60)
        print(f"✓ {'ЛЕНДИНГ' if site_type == 'landing' else 'САЙТ'} СОЗДАН: {output_dir}")
        print(f"✓ Название: {self.blueprint.get('site_name')}")
        print(f"✓ Цвета: {self.blueprint.get('color_scheme', {}).get('primary')} (hover: {self.blueprint.get('color_scheme', {}).get('hover')})")
        print("=" * 60)
        
        print(f"\n🚀 Запуск сайта:")
        print(f"\n1. cd {output_dir}")
        print(f"2. php -S localhost:8000")
        print(f"3. Откройте: http://localhost:8000/index.php")
        print(f"\n✨ Готово! Уникальный дизайн!")
        
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
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║        ГЕНЕРАТОР PHP САЙТОВ v2.3 TWIG Edition             ║")
    print("║        Уникальные названия + цвета + дизайны              ║")
    print("║        Работа с папкой data (любой путь)                  ║")
    print("║        + Исправлена форма Contact и Blog страницы         ║")
    print("╚═══════════════════════════════════════════════════════════╝")
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
    print(f"📂 Папка данных: {data_dir}")
    print(f"📂 Папка вывода: {output_dir}")
    print(f"🎯 Тип: {'ЛЕНДИНГ' if site_type == 'landing' else 'МНОГОСТРАНИЧНЫЙ'}")
    print("=" * 60)
    print()
    
    generator = PHPWebsiteGenerator()
    
    try:
        success = generator.generate_website(user_prompt, output_dir=output_dir, data_dir=data_dir, site_type=site_type)
        
        if success:
            print("\n✨ Готово!")
        else:
            print("\n⚠️  Генерация завершена с предупреждениями")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
