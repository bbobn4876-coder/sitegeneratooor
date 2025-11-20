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
        self.api_key = ""
        self.bytedance_key = "03324c9d-d15f-4b35-a234-2bdd0b30a569"
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.code_model = "google/gemini-2.5-pro"
        self.max_tokens = 16000
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
        self.num_blog_articles = 3  # Количество статей блога (3 или 6)
        self.theme_content_cache = {}  # Кэш для контента на основе темы

        # Инициализация Ark клиента для ByteDance Seedream-4.0
        print(f"🔑 Инициализация ByteDance Ark SDK...")
        print(f"   API Key: {self.bytedance_key[:20]}...")
        
        self.ark_client = Ark(
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
            api_key=self.bytedance_key
        )
        print(f"✓ Ark SDK готов\n")
        
    def call_api(self, prompt, max_tokens=16000, model=None):
        """Вызов API OpenRouter с retry логикой и обработкой всех типов ошибок"""
        if model is None:
            model = self.code_model
        
        if max_tokens > 16000:
            max_tokens = 16000  # Ограничение для бесплатной модели
            
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
            "Travel": "WanderHub, TripNest, JourneyCraft, TravelFlow, RoutePoint, TourSpot",
            "IT Training": "SkillForge, CodeAcademy, LearnTech, DevMentor, TechSkills, ByteLearn",
            "Legal Consulting": "LawCounsel, JusticePoint, LegalWise, RightAdvice, LawGuide, CounselHub",
            "Furniture Store": "HomeCraft, FurnishNest, ComfortSpace, StyleHaven, WoodWorks, DecorHub",
            "Online Stores": "StyleCart, FashionFlow, TrendHub, ChicShop, ModaVault, DressPoint",
            "Online Courses": "LearnOnline, CourseHub, SkillStream, EduPath, KnowledgeFlow, StudyWave",
            "Travel Service Ratings": "TripRate, TravelScore, JourneyReview, RateVoyage, TourInsight, TripVerdict",
            "Technology": "TechWave, InnovateLab, FutureCore, DigitalEdge, NextGen, TechVision",
            "Car Sales": "AutoHub, DrivePoint, CarSelect, MotorNest, WheelCraft, VehicleFlow",
            "Psychology": "MindCare, TherapyHub, MentalWell, PsychoSupport, MindFlow, ThoughtSpace"
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
            "Psychology": "Focus on mind, mental health, therapy, wellness, counseling. Avoid tech terms."
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
            "Psychology": ["MindCare", "TherapyHub", "MentalWell", "PsychoSupport", "MindFlow"]
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
                'phones': ['+31 20 123 4567', '+31 10 987 6543', '+31 30 555 7890'],
                'cities': ['Amsterdam', 'Rotterdam', 'Utrecht', 'The Hague', 'Eindhoven', 'Groningen'],
                'streets': ['Damrak', 'Kalverstraat', 'Leidsestraat', 'Nieuwendijk', 'Rokin'],
                'postal_codes': ['1012', '3011', '3512', '2511', '5611']
            },
            'usa': {
                'phones': ['+1 (555) 123-4567', '+1 (555) 987-6543', '+1 (555) 555-7890'],
                'cities': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia'],
                'streets': ['Main Street', 'Broadway', 'Park Avenue', 'Wall Street', 'Market Street'],
                'postal_codes': ['10001', '90001', '60601', '77001', '85001']
            },
            'uk': {
                'phones': ['+44 20 1234 5678', '+44 161 987 6543', '+44 131 555 7890'],
                'cities': ['London', 'Manchester', 'Birmingham', 'Edinburgh', 'Liverpool', 'Bristol'],
                'streets': ['High Street', 'King Street', 'Oxford Street', 'Queen Street', 'Victoria Road'],
                'postal_codes': ['SW1A', 'M1 1AD', 'B1 1AA', 'EH1 1YZ', 'L1 8JQ']
            },
            'germany': {
                'phones': ['+49 30 1234 5678', '+49 89 9876 543', '+49 40 555 7890'],
                'cities': ['Berlin', 'Munich', 'Hamburg', 'Frankfurt', 'Cologne', 'Stuttgart'],
                'streets': ['Hauptstraße', 'Bahnhofstraße', 'Marktplatz', 'Kirchstraße', 'Schulstraße'],
                'postal_codes': ['10115', '80331', '20095', '60311', '50667']
            },
            'france': {
                'phones': ['+33 1 23 45 67 89', '+33 4 98 76 54 32', '+33 5 55 57 89 01'],
                'cities': ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Nice', 'Bordeaux'],
                'streets': ['Rue de la Paix', 'Avenue des Champs-Élysées', 'Rue Royale', 'Boulevard Haussmann'],
                'postal_codes': ['75001', '69001', '13001', '31000', '06000']
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
            'phone': '+1 (555) 123-4567',
            'address': '123 Business Street, Suite 100, New York, NY 10001'
        }

    def generate_theme_content_via_api(self, theme, content_type, num_items=4):
        """
        Генерирует контент на основе темы через API

        Args:
            theme: Тема сайта (например, "Travel", "Restaurant", "Cryptocurrency")
            content_type: Тип контента ("process_steps", "featured_solutions", "approach_content", "services")
            num_items: Количество элементов для генерации

        Returns:
            Структурированный контент в виде списка словарей или словаря
        """
        # Проверяем кэш
        cache_key = f"{theme}_{content_type}_{num_items}"
        if cache_key in self.theme_content_cache:
            return self.theme_content_cache[cache_key]

        # Специальные инструкции для определенных тем
        theme_specific_instructions = ""
        if theme == "Furniture Store":
            theme_specific_instructions = "\nIMPORTANT: Do NOT mention any prices, costs, or pricing information. Focus on quality, style, and features only."
        elif theme == "Online Stores":
            theme_specific_instructions = "\nIMPORTANT: This is a women's clothing store. Focus on women's fashion, apparel, and accessories."

        # Создаем промпт в зависимости от типа контента
        if content_type == "process_steps":
            prompt = f"""Generate {num_items} process steps for a {theme} business/website.
Return the result as a JSON array of objects, where each object has:
- "title": short step title (2-4 words)
- "description": detailed step description (1-2 sentences)

Make the content highly specific to the {theme} industry. Use industry-specific terminology and realistic workflow.{theme_specific_instructions}

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

Make the content highly specific to the {theme} industry. Focus on real solutions that such a business would offer.{theme_specific_instructions}

Example format:
[
  {{"title": "Solution Name", "description": "Description of the solution.", "image": "service1.jpg"}},
  ...
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        elif content_type == "approach_content":
            prompt = f"""Generate approach/philosophy content for a {theme} business.
Return the result as a JSON object with these exact keys:
- "approach_title": Section title (e.g., "Our Approach")
- "approach_text1": First paragraph about approach (2-3 sentences)
- "approach_text2": Second paragraph about approach (2-3 sentences)
- "why_title": Why choose us section title (e.g., "Why Choose Us")
- "why_text1": First paragraph about why choose (2-3 sentences, include "{theme}" in the text)
- "why_text2": Second paragraph about why choose (2-3 sentences)

Make the content highly specific to the {theme} industry and business model.{theme_specific_instructions}

Example format:
{{
  "approach_title": "Our Approach",
  "approach_text1": "...",
  "approach_text2": "...",
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

Make the content highly specific to the {theme} industry. These should be core services that such a business would realistically offer.{theme_specific_instructions}

Example format:
[
  {{"title": "Service Name", "description": "Description of the service."}},
  ...
]

Return ONLY valid JSON, no additional text or markdown formatting."""

        else:
            return None

        # Вызываем API
        print(f"    🤖 Генерация контента для темы '{theme}' ({content_type})...")
        response = self.call_api(prompt, max_tokens=2000)

        if not response:
            print(f"    ✗ API не вернул ответ для {content_type}")
            return None

        try:
            # Очищаем ответ от markdown форматирования если есть
            response = response.strip()
            if response.startswith('```'):
                # Удаляем markdown code blocks
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response
                response = response.replace('```json', '').replace('```', '').strip()

            # Парсим JSON
            content = json.loads(response)

            # Сохраняем в кэш
            self.theme_content_cache[cache_key] = content

            print(f"    ✓ Контент успешно сгенерирован для '{theme}'")
            return content

        except json.JSONDecodeError as e:
            print(f"    ✗ Ошибка парсинга JSON для {content_type}: {e}")
            print(f"    Ответ API: {response[:200]}...")
            return None

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
                'approach_title': 'Our Approach',
                'approach_text1': 'We create personalized travel experiences that go beyond typical tourist destinations. Understanding your travel style and preferences allows us to craft unforgettable journeys.',
                'approach_text2': 'Our expert travel planners combine local knowledge with global expertise to design itineraries that match your dreams and exceed your expectations.',
                'why_title': 'Why Choose Us',
                'why_text1': f'With years of experience in the {theme} industry, we\'ve helped thousands of travelers discover amazing destinations and create lasting memories.',
                'why_text2': 'Our dedication to exceptional service means you can travel with confidence, knowing every detail has been carefully planned and arranged for your comfort.'
            }

        # Restaurant / Food
        elif any(word in theme_lower for word in ['restaurant', 'cafe', 'food', 'dining', 'cuisine']):
            return {
                'approach_title': 'Our Philosophy',
                'approach_text1': 'We believe exceptional dining starts with the finest ingredients and passionate chefs who bring authentic flavors to every dish.',
                'approach_text2': 'Our culinary approach honors traditional recipes while embracing innovation, creating memorable dining experiences that delight all senses.',
                'why_title': 'Why Dine With Us',
                'why_text1': f'With years of culinary excellence in the {theme} industry, we\'ve earned a reputation for outstanding food, warm hospitality, and unforgettable moments.',
                'why_text2': 'From sourcing fresh ingredients to crafting each dish with care, our commitment to quality shines through in every meal we serve.'
            }

        # Fitness / Gym / Sports
        elif any(word in theme_lower for word in ['fitness', 'gym', 'sport', 'workout', 'training']):
            return {
                'approach_title': 'Our Training Philosophy',
                'approach_text1': 'We understand that every fitness journey is unique. Our personalized approach focuses on your individual goals, abilities, and lifestyle.',
                'approach_text2': 'Combining proven training methods with cutting-edge fitness science, we create programs that deliver real, sustainable results.',
                'why_title': 'Why Train With Us',
                'why_text1': f'With extensive experience in the {theme} industry, our certified trainers have helped countless members achieve and exceed their fitness goals.',
                'why_text2': 'Your success is our motivation. We provide ongoing support, expert guidance, and a welcoming community to keep you inspired every step of the way.'
            }

        # Real Estate / Property
        elif any(word in theme_lower for word in ['real estate', 'property', 'realty', 'housing']):
            return {
                'approach_title': 'Our Approach',
                'approach_text1': 'We take a personalized approach to real estate, taking time to understand your unique needs, preferences, and long-term investment goals.',
                'approach_text2': 'Our market expertise and dedication to client service ensure you make informed decisions whether buying, selling, or investing in property.',
                'why_title': 'Why Choose Us',
                'why_text1': f'With deep knowledge of the {theme} market, we\'ve built a strong reputation for integrity, professionalism, and exceptional results.',
                'why_text2': 'From first consultation to closing and beyond, we\'re committed to making your real estate journey smooth, successful, and stress-free.'
            }

        # Education / School / Courses
        elif any(word in theme_lower for word in ['education', 'school', 'course', 'learning', 'training', 'academy']):
            return {
                'approach_title': 'Our Teaching Approach',
                'approach_text1': 'We believe effective learning combines engaging instruction, hands-on practice, and personalized support tailored to each student\'s needs.',
                'approach_text2': 'Our curriculum blends theoretical knowledge with practical skills, preparing students for real-world success in their chosen fields.',
                'why_title': 'Why Learn With Us',
                'why_text1': f'With proven expertise in the {theme} field, our instructors bring both academic knowledge and industry experience to every class.',
                'why_text2': 'Your educational success matters to us. We provide comprehensive support, flexible learning options, and a pathway to achieving your career goals.'
            }

        # Healthcare / Medical / Clinic
        elif any(word in theme_lower for word in ['health', 'medical', 'clinic', 'doctor', 'care', 'hospital']):
            return {
                'approach_title': 'Our Care Philosophy',
                'approach_text1': 'We provide compassionate, patient-centered healthcare that treats you as a whole person, not just a set of symptoms.',
                'approach_text2': 'Our medical team combines clinical expertise with genuine care, ensuring you receive personalized treatment in a comfortable, supportive environment.',
                'why_title': 'Why Choose Us',
                'why_text1': f'With years of experience in {theme}, we\'ve earned the trust of our community through quality care, professional excellence, and genuine compassion.',
                'why_text2': 'Your health and wellbeing are our priority. We\'re committed to providing accessible, comprehensive care that helps you live your healthiest life.'
            }

        # Cryptocurrency / Blockchain / Crypto
        elif any(word in theme_lower for word in ['crypto', 'cryptocurrency', 'blockchain', 'bitcoin', 'ethereum', 'defi', 'nft', 'web3']):
            return {
                'approach_title': 'Our Platform',
                'approach_text1': 'We\'ve built a cutting-edge cryptocurrency platform that combines institutional-grade security with an intuitive user experience for traders of all levels.',
                'approach_text2': 'Our technology infrastructure ensures lightning-fast execution, deep liquidity, and 24/7 uptime so you never miss market opportunities.',
                'why_title': 'Why Trade With Us',
                'why_text1': f'As leaders in the {theme} space, we provide the most secure and reliable platform with advanced features trusted by millions of users worldwide.',
                'why_text2': 'Your assets are protected by multi-layered security, cold storage, and insurance. Our dedicated support team is available around the clock to assist you.'
            }

        # Default / Business / Technology
        else:
            return {
                'approach_title': 'Our Approach',
                'approach_text1': 'We believe in a personalized approach to every project. Understanding your unique needs allows us to deliver tailored solutions that exceed expectations.',
                'approach_text2': 'Our methodology combines industry best practices with innovative thinking to ensure optimal results for your business.',
                'why_title': 'Why Choose Us',
                'why_text1': f'With years of experience in the {theme} industry, we\'ve built a reputation for reliability, quality, and exceptional customer service.',
                'why_text2': 'Our commitment to your success drives everything we do, from initial consultation to project completion and beyond.'
            }

    def generate_image_text_alternating_section(self, site_name, theme, primary, hover):
        """Генерирует секцию Image Text Alternating с тематическим контентом"""
        content = self.generate_theme_content_via_api(theme, "approach_content", 1)

        # Fallback если API не вернул результат
        if not content:
            content = self.get_theme_based_approach_content(theme)

        # Проверяем наличие изображений
        has_service1 = self._has_image('service1.jpg')
        has_service2 = self._has_image('service2.jpg')

        # Первая секция (approach)
        if has_service1:
            section1 = f"""
            <div class="grid md:grid-cols-2 gap-12 items-center mb-20">
                <div>
                    <img src="images/service1.jpg" alt="{content['approach_title']}" class="rounded-xl shadow-lg w-full h-80 object-cover">
                </div>
                <div>
                    <h3 class="text-3xl font-bold mb-4">{content['approach_title']}</h3>
                    <p class="text-gray-700 mb-4">
                        {content['approach_text1']}
                    </p>
                    <p class="text-gray-700">
                        {content['approach_text2']}
                    </p>
                </div>
            </div>"""
        else:
            section1 = f"""
            <div class="mb-20">
                <h3 class="text-3xl font-bold mb-4">{content['approach_title']}</h3>
                <p class="text-gray-700 mb-4">
                    {content['approach_text1']}
                </p>
                <p class="text-gray-700">
                    {content['approach_text2']}
                </p>
            </div>"""

        # Вторая секция (why)
        if has_service2:
            section2 = f"""
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h3 class="text-3xl font-bold mb-4">{content['why_title']}</h3>
                    <p class="text-gray-700 mb-4">
                        {content['why_text1']}
                    </p>
                    <p class="text-gray-700">
                        {content['why_text2']}
                    </p>
                </div>
                <div>
                    <img src="images/service2.jpg" alt="{content['why_title']}" class="rounded-xl shadow-lg w-full h-80 object-cover">
                </div>
            </div>"""
        else:
            section2 = f"""
            <div>
                <h3 class="text-3xl font-bold mb-4">{content['why_title']}</h3>
                <p class="text-gray-700 mb-4">
                    {content['why_text1']}
                </p>
                <p class="text-gray-700">
                    {content['why_text2']}
                </p>
            </div>"""

        return f"""
    <section class="py-20 bg-gray-50">
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
                {'title': 'Flight Booking', 'description': 'Book flights to destinations worldwide with competitive prices and flexible options.'},
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
            return [
                {'title': 'Consultation', 'description': 'Expert advice to help you make informed decisions about your project.'},
                {'title': 'Planning', 'description': 'Strategic planning to ensure your project\'s success from start to finish.'},
                {'title': 'Implementation', 'description': 'Professional execution with attention to every detail of your project.'},
                {'title': 'Testing', 'description': 'Thorough testing to ensure quality and reliability in all deliverables.'},
                {'title': 'Support', 'description': 'Ongoing support to help you get the most from your investment.'},
                {'title': 'Optimization', 'description': 'Continuous improvement to keep your solution performing at its best.'}
            ]

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

        # Генерируем карточки только для доступных решений
        cards_html = ""
        for sol in available_solutions:
            cards_html += f"""
                <div class="relative overflow-hidden rounded-xl shadow-lg h-96 group">
                    <img src="images/{sol['image']}" alt="{sol['title']}" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent"></div>
                    <div class="relative h-full flex flex-col justify-end p-8">
                        <h3 class="text-white text-2xl font-bold mb-3">{sol['title']}</h3>
                        <p class="text-white/90 mb-4">{sol['description']}</p>
                        <a href="contact.php" class="inline-block bg-white text-{primary} px-6 py-3 rounded-lg font-semibold hover:bg-gray-100 transition w-fit">
                            Contact Us
                        </a>
                    </div>
                </div>"""

        # Адаптируем grid в зависимости от количества карточек
        grid_class = f"md:grid-cols-{len(available_solutions)}" if len(available_solutions) <= 3 else "md:grid-cols-3"

        return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Featured Solutions</h2>
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

        if variation == 1:
            return f"""
    <section class="py-20 bg-gradient-to-br from-gray-50 to-white relative overflow-hidden">
        <div class="absolute top-0 right-0 w-96 h-96 bg-{primary}/5 rounded-full blur-3xl"></div>
        <div class="absolute bottom-0 left-0 w-96 h-96 bg-{hover}/5 rounded-full blur-3xl"></div>

        <div class="container mx-auto px-6 relative z-10">
            <div class="text-center mb-16">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">Our Process</h2>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">Simple, transparent, and effective workflow designed for your success</p>
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

            <div class="text-center mt-16">
                <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">
                    Start Your Project
                </a>
            </div>
        </div>
    </section>"""

        elif variation == 2:
            return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-20">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">Our Process</h2>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">A proven methodology to transform your ideas into reality</p>
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
                                <div class="text-{primary} font-bold text-lg mb-2">Step 1</div>
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
                                <div class="text-{primary} font-bold text-lg mb-2">Step 2</div>
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
                                <div class="text-{primary} font-bold text-lg mb-2">Step 3</div>
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
                                <div class="text-{primary} font-bold text-lg mb-2">Step 4</div>
                                <h3 class="text-xl font-bold mb-3">{steps[3]['title']}</h3>
                                <p class="text-gray-600">{steps[3]['description']}</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="text-center mt-16">
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">
                        Get Started Today
                    </a>
                </div>
            </div>
        </div>
    </section>"""

        else:
            return f"""
    <section class="py-20 bg-gradient-to-b from-white to-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-20">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">Our Process</h2>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">Every great project starts with a solid plan</p>
            </div>

            <div class="max-w-4xl mx-auto space-y-12">
                <div class="flex flex-col md:flex-row items-center gap-8 group">
                    <div class="md:w-1/2 md:text-right">
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">STEP 01</div>
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
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">STEP 02</div>
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
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">STEP 03</div>
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
                        <div class="inline-block bg-{primary} text-white px-4 py-2 rounded-full text-sm font-bold mb-4">STEP 04</div>
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

            <div class="text-center mt-16">
                <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">
                    Start Your Journey
                </a>
            </div>
        </div>
    </section>"""

    def generate_what_we_offer_section(self, site_name, theme, primary, hover):
        """Генерирует одну из 3 вариаций секции What We Offer (6 карточек)"""
        variation = random.randint(1, 3)
        services = self.generate_theme_content_via_api(theme, "services", 6)

        # Fallback если API не вернул результат
        if not services:
            services = self.get_theme_based_what_we_offer(theme)

        if variation == 1:
            return f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-4">What We Offer</h2>
            <p class="text-gray-600 text-center mb-12 text-lg">Comprehensive solutions tailored to your needs</p>
            <div class="grid md:grid-cols-3 gap-6">
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[0]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[0]['description']}</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[1]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[1]['description']}</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[2]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[2]['description']}</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[3]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[3]['description']}</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[4]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[4]['description']}</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
                <div class="bg-gradient-to-br from-{primary}/5 to-white border border-gray-200 rounded-xl p-6">
                    <h4 class="text-xl font-bold mb-3">{services[5]['title']}</h4>
                    <p class="text-gray-600 mb-4">{services[5]['description']}</p>
                    <a href="contact.php" class="text-{primary} hover:text-{hover} font-semibold transition">
                        Learn More →
                    </a>
                </div>
            </div>
        </div>
    </section>"""

        elif variation == 2:
            return f"""
    <section class="py-20 bg-gradient-to-br from-gray-50 to-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">What We Offer</h2>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">Discover our range of professional services designed to elevate your business</p>
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
                    <a href="contact.php" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition group-hover:translate-x-2 transform duration-300">
                        Explore <span class="ml-2">→</span>
                    </a>
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[1]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[1]['description']}</p>
                    <a href="contact.php" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition group-hover:translate-x-2 transform duration-300">
                        Explore <span class="ml-2">→</span>
                    </a>
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[2]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[2]['description']}</p>
                    <a href="contact.php" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition group-hover:translate-x-2 transform duration-300">
                        Explore <span class="ml-2">→</span>
                    </a>
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[3]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[3]['description']}</p>
                    <a href="contact.php" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition group-hover:translate-x-2 transform duration-300">
                        Explore <span class="ml-2">→</span>
                    </a>
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[4]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[4]['description']}</p>
                    <a href="contact.php" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition group-hover:translate-x-2 transform duration-300">
                        Explore <span class="ml-2">→</span>
                    </a>
                </div>

                <div class="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border-2 border-transparent hover:border-{primary}/20">
                    <div class="w-14 h-14 bg-{primary} rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-2xl font-bold mb-4">{services[5]['title']}</h3>
                    <p class="text-gray-600 leading-relaxed mb-6">{services[5]['description']}</p>
                    <a href="contact.php" class="inline-flex items-center text-{primary} hover:text-{hover} font-semibold transition group-hover:translate-x-2 transform duration-300">
                        Explore <span class="ml-2">→</span>
                    </a>
                </div>
            </div>
        </div>
    </section>"""

        else:
            return f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl md:text-5xl font-bold mb-4">What We Offer</h2>
                <p class="text-xl text-gray-600 max-w-3xl mx-auto">Six core services that drive exceptional results</p>
            </div>

            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        01
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[0]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed mb-6">{services[0]['description']}</p>
                        <div class="flex items-center text-{primary} font-semibold group-hover:translate-x-2 transition-transform">
                            Get Started <span class="ml-2">→</span>
                        </div>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        02
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[1]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed mb-6">{services[1]['description']}</p>
                        <div class="flex items-center text-{primary} font-semibold group-hover:translate-x-2 transition-transform">
                            Get Started <span class="ml-2">→</span>
                        </div>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        03
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[2]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed mb-6">{services[2]['description']}</p>
                        <div class="flex items-center text-{primary} font-semibold group-hover:translate-x-2 transition-transform">
                            Get Started <span class="ml-2">→</span>
                        </div>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        04
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[3]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed mb-6">{services[3]['description']}</p>
                        <div class="flex items-center text-{primary} font-semibold group-hover:translate-x-2 transition-transform">
                            Get Started <span class="ml-2">→</span>
                        </div>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        05
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[4]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed mb-6">{services[4]['description']}</p>
                        <div class="flex items-center text-{primary} font-semibold group-hover:translate-x-2 transition-transform">
                            Get Started <span class="ml-2">→</span>
                        </div>
                    </div>
                </div>

                <div class="group relative bg-white rounded-xl p-8 shadow-md hover:shadow-xl transition-all duration-300">
                    <div class="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-{primary} to-{hover} rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                        06
                    </div>
                    <div class="pt-4">
                        <h3 class="text-2xl font-bold mb-4 text-gray-900">{services[5]['title']}</h3>
                        <p class="text-gray-600 leading-relaxed mb-6">{services[5]['description']}</p>
                        <div class="flex items-center text-{primary} font-semibold group-hover:translate-x-2 transition-transform">
                            Get Started <span class="ml-2">→</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="text-center mt-16">
                <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-1">
                    Discuss Your Project
                </a>
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
        location_cards = ""
        for i, location in enumerate(locations, 1):
            location_cards += f"""
                    <div class="w-full md:w-1/3 flex-shrink-0 px-3">
                        <div class="bg-white rounded-xl p-6 shadow-md hover:shadow-xl transition-shadow">
                            <img src="images/location{i}.jpg" alt="{location['city']}" class="w-full h-40 object-cover rounded-lg mb-4">
                            <h4 class="text-xl font-bold mb-2">{location['city']} Office</h4>
                            <p class="text-gray-600 mb-4">{location['description']}</p>
                            <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-6 py-2 rounded-lg font-semibold transition">
                                Contact
                            </a>
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

                // Update indicators
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
    
    def generate_image_via_bytedance(self, prompt, filename, output_dir):
        """Генерация изображения через ByteDance Ark SDK"""
        # Убрали вывод отсюда - он делается в generate_images_for_site

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

        # Создаем детальные контекстные промпты в зависимости от СТРАНЫ (не темы!)
        country_lower = country.lower()

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
            ethnicity_context = "European people, Dutch ethnicity, Caucasian, Northern European features, NO Asian appearance"
        elif any(word in country_lower for word in european_countries):
            location_context = "in Europe, European cities, historic architecture, European landmarks"
            ethnicity_context = "European people, Caucasian, diverse European ethnicities, NO Asian appearance"
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
        images_to_generate = [
            # PRIORITY 1: Hero (обязательно - 1 шт)
            {
                'filename': 'hero.jpg',
                'priority': 'required',
                'prompt': f"Professional wide banner photograph for {theme} website. {location_context}. Clean composition, natural lighting, high quality, photorealistic, 8k resolution. {ethnicity_context} if people are visible. No text or logos."
            },
            # PRIORITY 2: Services (обязательно - 3 шт)
            {
                'filename': 'service1.jpg',
                'priority': 'required',
                'prompt': f"High-quality photograph representing {theme} services. {location_context}. Professional service delivery, real-world application, authentic setting, natural lighting, clean composition, photorealistic. {ethnicity_context} if people are shown."
            },
            {
                'filename': 'service2.jpg',
                'priority': 'required',
                'prompt': f"Professional teamwork photograph for {theme} business. {location_context}. {ethnicity_context} collaborating in modern office, natural interaction, authentic workplace, productive atmosphere, photorealistic, bright natural light."
            },
            {
                'filename': 'service3.jpg',
                'priority': 'required',
                'prompt': f"Professional service photograph for {theme} company. {location_context}. Expert professionals at work, quality service delivery, attention to detail, authentic workplace setting, natural lighting, photorealistic. {ethnicity_context} visible."
            },
        ]

        # PRIORITY 3: Blog (динамически - 3 или 6 шт в зависимости от self.num_blog_articles)
        blog_prompts = [
            f"Engaging blog header photograph related to {theme} topic. {location_context}. Creative composition, storytelling visual, authentic scene, natural colors, high quality, photorealistic. {ethnicity_context} if people present.",
            f"Inspiring blog featured photograph for {theme} article. {location_context}. Professional quality, engaging composition, relevant to topic, authentic setting, natural lighting, photorealistic.",
            f"Informative blog post photograph about {theme}. {location_context}. Clear visual storytelling, educational value, authentic scene, natural environment, high-quality photography, photorealistic.",
            f"Unique perspective blog photograph for {theme} content. {location_context}. Creative angle, interesting composition, authentic moment, natural lighting, professional photography, photorealistic.",
            f"Compelling blog content photograph representing {theme}. {location_context}. Strong visual narrative, authentic scene, engaging composition, natural colors, high quality, photorealistic.",
            f"Professional blog header photograph for {theme} article. {location_context}. Attractive composition, relevant content, authentic setting, clear subject, natural lighting, photorealistic."
        ]

        # Добавляем blog изображения в зависимости от количества статей
        for i in range(self.num_blog_articles):
            images_to_generate.append({
                'filename': f'blog{i+1}.jpg',
                'priority': 'required',
                'prompt': blog_prompts[i]
            })

        # PRIORITY 4: Company (опционально - 4 шт для Home страницы)
        images_to_generate.extend([
            {
                'filename': 'about.jpg',
                'priority': 'optional',
                'prompt': f"Professional business photograph showing {theme} company culture. {location_context}. {ethnicity_context} in natural professional setting, authentic workplace environment, candid moments, warm atmosphere, photorealistic."
            },
            {
                'filename': 'mission.jpg',
                'priority': 'optional',
                'prompt': f"Inspiring photograph representing company mission and vision for {theme} business. {location_context}. Forward-thinking perspective, aspirational imagery, professional setting, authentic motivation, natural lighting, photorealistic."
            },
            {
                'filename': 'values.jpg',
                'priority': 'optional',
                'prompt': f"Professional photograph showcasing company values and culture for {theme}. {location_context}. {ethnicity_context} demonstrating teamwork and collaboration, authentic workplace values, positive atmosphere, photorealistic."
            },
            {
                'filename': 'team.jpg',
                'priority': 'optional',
                'prompt': f"Professional team photograph for {theme} company. {location_context}. {ethnicity_context} in business setting, diverse professional team, confident and approachable, natural group composition, photorealistic."
            },
        ])

        # PRIORITY 5: Gallery (обязательно - 3 шт)
        images_to_generate.extend([
            {
                'filename': 'gallery1.jpg',
                'priority': 'required',
                'prompt': f"Showcase photograph highlighting {theme} work. {location_context}. Portfolio quality, interesting composition, professional execution, authentic project, natural lighting, photorealistic."
            },
            {
                'filename': 'gallery2.jpg',
                'priority': 'required',
                'prompt': f"Professional portfolio photograph of {theme} project. {location_context}. Different perspective, quality craftsmanship, authentic work, detailed shot, natural light, photorealistic."
            },
            {
                'filename': 'gallery3.jpg',
                'priority': 'required',
                'prompt': f"Quality showcase photograph for {theme} services. {location_context}. Professional presentation, real project example, clean composition, authentic work, photorealistic."
            },
            # ДОПОЛНИТЕЛЬНЫЕ: Gallery 4 (1 шт)
            {
                'filename': 'gallery4.jpg',
                'priority': 'optional',
                'prompt': f"Professional portfolio piece for {theme} company. {location_context}. High-quality craftsmanship, finished project, authentic work, professional photography, photorealistic."
            },
            # ДОПОЛНИТЕЛЬНЫЕ: Locations (6 шт)
            {
                'filename': 'location1.jpg',
                'priority': 'optional',
                'prompt': f"Beautiful cityscape photograph of a major city {location_context}. Iconic architecture, vibrant urban landscape, famous landmarks, clear blue sky, natural daylight, professional travel photography, photorealistic, 8k quality."
            },
            {
                'filename': 'location2.jpg',
                'priority': 'optional',
                'prompt': f"Stunning city view photograph {location_context}. Historic district, charming streets, cultural landmarks, authentic urban environment, golden hour lighting, professional cityscape photography, photorealistic."
            },
            {
                'filename': 'location3.jpg',
                'priority': 'optional',
                'prompt': f"Professional city photograph {location_context}. Modern business district, contemporary architecture, dynamic city life, clean composition, bright daylight, high-quality urban photography, photorealistic."
            },
            {
                'filename': 'location4.jpg',
                'priority': 'optional',
                'prompt': f"Attractive cityscape showing urban beauty {location_context}. Waterfront view, riverside or canal scene, scenic city landscape, natural lighting, professional travel photography, photorealistic, detailed."
            },
            {
                'filename': 'location5.jpg',
                'priority': 'optional',
                'prompt': f"Impressive city photograph {location_context}. Cultural center, historic buildings, city square or plaza, authentic urban setting, clear weather, professional cityscape photography, photorealistic."
            },
            {
                'filename': 'location6.jpg',
                'priority': 'optional',
                'prompt': f"High-quality urban photograph {location_context}. Residential and business areas, typical city architecture, local character, natural daylight, professional photography, photorealistic, vibrant colors."
            }
        ])

        self.generated_images = []

        # Разделяем изображения по приоритетам
        required_images = [img for img in images_to_generate if img.get('priority') == 'required']
        optional_images = [img for img in images_to_generate if img.get('priority') == 'optional']

        print(f"\n🖼️  Генерация изображений: {num_images} шт. (минимум 17 обязательных)")
        print(f"   📌 Обязательные: {len(required_images)} (hero + 3 services + {self.num_blog_articles} blog + 3 gallery)")
        print(f"   ⭐ Дополнительные: {len(optional_images)} (4 company, gallery4, 6 locations)")

        generated_count = 0

        # ЭТАП 1: Генерируем ВСЕ обязательные изображения (минимум 10 шт)
        print(f"\n   🔥 Этап 1/2: Генерация обязательных изображений...")
        for img_data in required_images:
            print(f"      → {img_data['filename']}...", end=' ')

            # Сначала пробуем ByteDance
            result = self.generate_image_via_bytedance(
                img_data['prompt'],
                img_data['filename'],
                images_dir
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

        # ЭТАП 2: Генерируем дополнительные изображения до лимита
        remaining = num_images - generated_count
        if remaining > 0:
            print(f"\n   ⭐ Этап 2/2: Генерация дополнительных изображений (осталось {remaining})...")
            for img_data in optional_images[:remaining]:
                print(f"      → {img_data['filename']}...", end=' ')

                # Сначала пробуем ByteDance
                result = self.generate_image_via_bytedance(
                    img_data['prompt'],
                    img_data['filename'],
                    images_dir
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
    
    def create_blueprint(self, user_prompt, site_name):
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
        prompt_lower = user_prompt.lower()
        if any(word in prompt_lower for word in ['netherlands', 'dutch', 'holland', 'amsterdam', 'нидерланды', 'голландия']):
            country = "Netherlands"
        elif 'singapore' in prompt_lower:
            country = "Singapore"
        elif 'usa' in prompt_lower or 'america' in prompt_lower:
            country = "USA"
        elif 'uk' in prompt_lower or 'britain' in prompt_lower:
            country = "UK"
        elif 'germany' in prompt_lower or 'german' in prompt_lower:
            country = "Germany"
        elif 'france' in prompt_lower or 'french' in prompt_lower:
            country = "France"
        elif 'italy' in prompt_lower or 'italian' in prompt_lower:
            country = "Italy"
        elif 'spain' in prompt_lower or 'spanish' in prompt_lower:
            country = "Spain"
        elif 'japan' in prompt_lower or 'japanese' in prompt_lower:
            country = "Japan"
        elif 'china' in prompt_lower or 'chinese' in prompt_lower:
            country = "China"

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

            # Определяем страницы в зависимости от типа сайта
            if self.site_type == "landing":
                nav_pages = [
                    ('Home', 'index.php'),
                    ('Contact', 'index.php#contact')
                ]
            else:
                nav_pages = [
                    ('Home', 'index.php'),
                    ('Company', 'company.php'),
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
            
            # ГАРАНТИРОВАННЫЙ FOOTER (всегда создается, даже если API не отвечает)
            footer_links = [
                ('Home', 'index.php'),
                ('Privacy Policy', 'privacy.php'),
                ('Terms of Service', 'terms.php'),
                ('Cookie Policy', 'cookie.php')
            ]
            
            if self.site_type == "multipage":
                footer_links.insert(1, ('Company', 'company.php'))
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
            <div>
                <h3 class="text-xl font-bold mb-4">{site_name}</h3>
                <p class="text-gray-400">Your trusted partner in {theme}.</p>
            </div>
            
            <div>
                <h4 class="text-lg font-semibold mb-4">Quick Links</h4>
                <ul class="space-y-2">
                    {' '.join([f'<li><a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a></li>' for link in main_links])}
                </ul>
            </div>
            
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
            <nav class="flex flex-wrap gap-4">
                {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in main_links])}
            </nav>
            
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
                # Получаем контактные данные из blueprint
                contact_data = self.blueprint.get('contact_data', {'phone': '+1 (555) 123-4567', 'address': '123 Business Street'})
                self.footer_code = f"""<footer class="bg-gray-900 text-white py-12 mt-auto">
    <div class="container mx-auto px-6">
        <div class="grid md:grid-cols-2 gap-8">
            <div>
                <h3 class="text-xl font-bold mb-4">{site_name}</h3>
                <p class="text-gray-400 mb-6">Your trusted partner in {theme}.</p>
                <nav class="flex flex-col space-y-2">
                    {' '.join([f'<a href="{link[1]}" class="text-gray-400 hover:text-{hover_color} transition-colors">{link[0]}</a>' for link in main_links])}
                </nav>
            </div>

            <div>
                <h4 class="text-lg font-semibold mb-4">Legal Information</h4>
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
            <p>&copy; 2025 {site_name}. All rights reserved.</p>
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
                <p class="text-gray-400 text-sm">&copy; 2025 All rights reserved.</p>
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

        # Выбираем случайный вариант из 9
        variation = random.randint(1, 9)

        if variation <= 3:
            # Баннер снизу (3 вариации)
            if variation == 1:
                # Баннер 1: Классический по центру
                return f"""
<!-- Cookie Notice Banner (Bottom Center) -->
<div id="cookie-notice" class="fixed bottom-0 left-0 right-0 bg-gray-900 text-white py-4 px-6 shadow-lg z-50 hidden">
    <div class="container mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-3">
            <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <p class="text-sm">We use cookies to enhance your browsing experience. By continuing, you agree to our <a href="cookie.php" class="underline hover:text-{primary} transition">Cookie Policy</a>.</p>
        </div>
        <div class="flex gap-3">
            <button onclick="acceptCookies()" class="bg-{primary} hover:bg-{hover} text-white px-6 py-2 rounded-lg text-sm font-semibold transition">
                Accept
            </button>
            <button onclick="dismissCookieNotice()" class="bg-gray-700 hover:bg-gray-600 text-white px-6 py-2 rounded-lg text-sm font-semibold transition">
                Decline
            </button>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice Banner (Full Width) -->
<div id="cookie-notice" class="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-{primary} shadow-2xl py-6 px-6 z-50 hidden">
    <div class="container mx-auto">
        <div class="flex flex-col md:flex-row items-center justify-between gap-4">
            <div class="flex items-start gap-4">
                <div class="text-4xl">🍪</div>
                <div>
                    <h3 class="font-bold text-lg mb-1">Cookie Consent</h3>
                    <p class="text-gray-600 text-sm">This website uses cookies to ensure you get the best experience. <a href="cookie.php" class="text-{primary} underline hover:text-{hover} transition">Learn more</a></p>
                </div>
            </div>
            <div class="flex gap-3 flex-shrink-0">
                <button onclick="acceptCookies()" class="bg-{primary} hover:bg-{hover} text-white px-8 py-3 rounded-lg font-semibold transition shadow-lg">
                    Accept All
                </button>
                <button onclick="dismissCookieNotice()" class="border-2 border-gray-300 hover:border-gray-400 text-gray-700 px-8 py-3 rounded-lg font-semibold transition">
                    Decline
                </button>
            </div>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice Banner (Minimal) -->
<div id="cookie-notice" class="fixed bottom-0 left-0 right-0 bg-{primary} text-white py-3 px-6 z-50 hidden">
    <div class="container mx-auto flex items-center justify-between">
        <p class="text-sm">🍪 We use cookies. <a href="cookie.php" class="underline font-semibold hover:opacity-80 transition">Cookie Policy</a></p>
        <div class="flex gap-2">
            <button onclick="acceptCookies()" class="bg-white text-{primary} px-4 py-1 rounded font-semibold text-sm hover:opacity-90 transition">
                OK
            </button>
            <button onclick="dismissCookieNotice()" class="border border-white text-white px-4 py-1 rounded font-semibold text-sm hover:bg-white hover:text-{primary} transition">
                ✕
            </button>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice Popup (Bottom Right Card) -->
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-white rounded-xl shadow-2xl p-6 max-w-md z-50 hidden border border-gray-200">
    <div class="flex items-start gap-3 mb-4">
        <div class="w-10 h-10 bg-{primary}/10 rounded-full flex items-center justify-center flex-shrink-0">
            <svg class="w-6 h-6 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
            </svg>
        </div>
        <div>
            <h3 class="font-bold text-lg mb-2">Cookie Settings</h3>
            <p class="text-gray-600 text-sm">We use cookies to improve your experience. By using our site, you accept our <a href="cookie.php" class="text-{primary} underline hover:text-{hover}">cookie policy</a>.</p>
        </div>
        <button onclick="dismissCookieNotice()" class="text-gray-400 hover:text-gray-600 flex-shrink-0">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
        </button>
    </div>
    <div class="flex gap-3">
        <button onclick="acceptCookies()" class="flex-1 bg-{primary} hover:bg-{hover} text-white py-2 rounded-lg font-semibold transition">
            Accept
        </button>
        <button onclick="dismissCookieNotice()" class="flex-1 border-2 border-gray-300 hover:border-gray-400 text-gray-700 py-2 rounded-lg font-semibold transition">
            Decline
        </button>
    </div>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice Popup (Dark Gradient) -->
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-gradient-to-br from-gray-900 to-gray-800 text-white rounded-2xl shadow-2xl p-6 max-w-sm z-50 hidden">
    <div class="mb-4">
        <div class="flex items-center justify-between mb-3">
            <span class="text-3xl">🍪</span>
            <button onclick="dismissCookieNotice()" class="text-gray-400 hover:text-white">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
        <h3 class="font-bold text-xl mb-2">Cookies Notice</h3>
        <p class="text-gray-300 text-sm">We value your privacy. Read our <a href="cookie.php" class="text-{primary} underline hover:opacity-80">cookie policy</a> to learn more.</p>
    </div>
    <button onclick="acceptCookies()" class="w-full bg-{primary} hover:bg-{hover} text-white py-3 rounded-xl font-bold transition shadow-lg">
        Accept Cookies
    </button>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice Popup (Compact) -->
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-white rounded-lg shadow-xl p-5 max-w-xs z-50 hidden border-l-4 border-{primary}">
    <div class="flex items-center justify-between mb-3">
        <h4 class="font-bold text-gray-900">Cookie Notice</h4>
        <button onclick="dismissCookieNotice()" class="text-gray-400 hover:text-gray-600">✕</button>
    </div>
    <p class="text-gray-600 text-sm mb-4">We use cookies to personalize content. <a href="cookie.php" class="text-{primary} font-semibold hover:underline">Details</a></p>
    <button onclick="acceptCookies()" class="w-full bg-{primary} hover:bg-{hover} text-white py-2 rounded-lg font-semibold text-sm transition">
        Got it!
    </button>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice (Small Pill) -->
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-gray-900 text-white rounded-full px-5 py-3 shadow-lg z-50 hidden flex items-center gap-3">
    <span class="text-sm">🍪 Cookies</span>
    <button onclick="acceptCookies()" class="bg-{primary} hover:bg-{hover} text-white px-4 py-1 rounded-full text-xs font-semibold transition">
        OK
    </button>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice (Small Badge) -->
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-white border-2 border-{primary} rounded-xl px-4 py-3 shadow-lg z-50 hidden">
    <div class="flex items-center gap-2">
        <div class="w-8 h-8 bg-{primary} rounded-full flex items-center justify-center text-white font-bold text-sm">C</div>
        <div>
            <p class="text-xs text-gray-700 font-semibold">Cookies active</p>
            <button onclick="acceptCookies()" class="text-{primary} text-xs underline hover:no-underline">Agree</button>
        </div>
    </div>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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
<!-- Cookie Notice (Minimal Toast) -->
<div id="cookie-notice" class="fixed bottom-6 right-6 bg-{primary} text-white rounded-lg px-6 py-3 shadow-lg z-50 hidden flex items-center gap-3">
    <span class="text-sm font-medium">Cookies in use</span>
    <button onclick="acceptCookies()" class="text-white hover:opacity-80 font-bold text-lg">×</button>
</div>
<script>
function showCookieNotice() {{
    // Всегда показываем Cookie notice при загрузке страницы
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

        # Используем сохраненные контактные данные из blueprint (те же что и в footer)
        contact_data_1 = self.blueprint.get('contact_data', self.get_country_contact_data(country))
        # Для разнообразия можем генерировать дополнительные контакты, но основной остается из blueprint
        contact_data_2 = self.get_country_contact_data(country)
        contact_data_3 = self.get_country_contact_data(country)

        # Выбираем случайную вариацию от 1 до 5
        variation = random.randint(1, 5)

        # Вариация 1: Классический двухколоночный (форма слева, инфо справа)
        if variation == 1:
            main_content = f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Get In Touch</h1>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">
                    Have a question or want to work together? We'd love to hear from you.
                </p>
            </div>

            <div class="grid md:grid-cols-2 gap-12 max-w-6xl mx-auto">
                <div class="bg-white rounded-2xl shadow-xl p-8 md:p-10">
                    <h2 class="text-3xl font-bold mb-6">Send us a message</h2>
                    <form action="thanks_you.php" method="POST" class="space-y-6">
                        <div>
                            <label for="name" class="block text-gray-700 font-semibold mb-2">Your Name <span class="text-red-500">*</span></label>
                            <input type="text" id="name" name="name" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none" placeholder="John Doe">
                        </div>
                        <div>
                            <label for="email" class="block text-gray-700 font-semibold mb-2">Your Email <span class="text-red-500">*</span></label>
                            <input type="email" id="email" name="email" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none" placeholder="john@example.com">
                        </div>
                        <div>
                            <label for="phone" class="block text-gray-700 font-semibold mb-2">Phone Number</label>
                            <input type="tel" id="phone" name="phone" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none" placeholder="+1 (555) 123-4567">
                        </div>
                        <div>
                            <label for="message" class="block text-gray-700 font-semibold mb-2">Your Message <span class="text-red-500">*</span></label>
                            <textarea id="message" name="message" rows="5" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent transition-all outline-none resize-none" placeholder="Tell us about your project..."></textarea>
                        </div>
                        <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-semibold transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-0.5">Send Message</button>
                    </form>
                </div>

                <div class="space-y-8">
                    <div class="bg-white rounded-2xl shadow-xl p-8">
                        <h2 class="text-3xl font-bold mb-6">Contact Information</h2>
                        <div class="space-y-6">
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">Email</h3>
                                    <a href="mailto:{site_name.lower().replace(' ', '')}@gmail.com" class="text-gray-600 hover:text-{primary} transition">{site_name.lower().replace(' ', '')}@gmail.com</a>
                                </div>
                            </div>
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">Phone</h3>
                                    <a href="tel:{contact_data_1["phone"].replace(" ", "")}" class="text-gray-600 hover:text-{primary} transition">{contact_data_1["phone"]}</a>
                                </div>
                            </div>
                            <div class="flex items-start">
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                    <svg class="w-6 h-6 flex-shrink-0 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                                </div>
                                <div class="ml-4">
                                    <h3 class="font-semibold text-gray-900 mb-1">Address</h3>
                                    <p class="text-gray-600">{contact_data_1["address"]}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="bg-gradient-to-br from-{primary} to-{hover} rounded-2xl shadow-xl p-8 text-white">
                        <h3 class="text-2xl font-bold mb-4">Why Choose Us?</h3>
                        <ul class="space-y-3">
                            <li class="flex items-center"><svg class="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>Quick response within 24 hours</li>
                            <li class="flex items-center"><svg class="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>Professional and friendly team</li>
                            <li class="flex items-center"><svg class="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>Free initial consultation</li>
                        </ul>
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
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Contact Us</h1>
                <p class="text-xl text-gray-600 max-w-2xl mx-auto">Let's discuss your project and bring your ideas to life</p>
            </div>

            <div class="max-w-3xl mx-auto bg-white rounded-2xl shadow-2xl p-10 mb-16">
                <form action="thanks_you.php" method="POST" class="space-y-6">
                    <div class="grid md:grid-cols-2 gap-6">
                        <div>
                            <label for="name" class="block text-gray-700 font-semibold mb-2">Full Name <span class="text-red-500">*</span></label>
                            <input type="text" id="name" name="name" required class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none" placeholder="John Doe">
                        </div>
                        <div>
                            <label for="email" class="block text-gray-700 font-semibold mb-2">Email Address <span class="text-red-500">*</span></label>
                            <input type="email" id="email" name="email" required class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none" placeholder="john@example.com">
                        </div>
                    </div>
                    <div class="grid md:grid-cols-2 gap-6">
                        <div>
                            <label for="phone" class="block text-gray-700 font-semibold mb-2">Phone</label>
                            <input type="tel" id="phone" name="phone" class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none" placeholder="+1 (555) 123-4567">
                        </div>
                        <div>
                            <label for="company" class="block text-gray-700 font-semibold mb-2">Company</label>
                            <input type="text" id="company" name="company" class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none" placeholder="Your Company">
                        </div>
                    </div>
                    <div>
                        <label for="message" class="block text-gray-700 font-semibold mb-2">Message <span class="text-red-500">*</span></label>
                        <textarea id="message" name="message" rows="6" required class="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-{primary} transition-all outline-none resize-none" placeholder="Tell us about your project..."></textarea>
                    </div>
                    <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-bold transition-all shadow-lg hover:shadow-xl transform hover:scale-105">Send Message</button>
                </form>
            </div>

            <div class="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
                <div class="text-center p-8 bg-gradient-to-br from-{primary}/5 to-white rounded-xl hover:shadow-lg transition-shadow">
                    <div class="w-16 h-16 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Email Us</h3>
                    <p class="text-gray-600">{site_name.lower().replace(' ', '')}@gmail.com</p>
                </div>
                <div class="text-center p-8 bg-gradient-to-br from-{primary}/5 to-white rounded-xl hover:shadow-lg transition-shadow">
                    <div class="w-16 h-16 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Call Us</h3>
                    <p class="text-gray-600">{contact_data_2["phone"]}</p>
                </div>
                <div class="text-center p-8 bg-gradient-to-br from-{primary}/5 to-white rounded-xl hover:shadow-lg transition-shadow">
                    <div class="w-16 h-16 bg-{primary} rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    </div>
                    <h3 class="text-xl font-bold mb-2">Visit Us</h3>
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
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Let's Work Together</h1>
                <p class="text-xl mb-12 opacity-90">Transform your vision into reality. We're here to help you succeed.</p>

                <div class="space-y-8">
                    <div class="flex items-center">
                        <div class="w-14 h-14 bg-white/20 rounded-lg flex items-center justify-center mr-6 flex-shrink-0">
                            <svg class="w-7 h-7 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z"></path></svg>
                        </div>
                        <div>
                            <p class="text-sm opacity-75">Phone</p>
                            <p class="text-lg font-semibold">{contact_data_3["phone"]}</p>
                        </div>
                    </div>
                    <div class="flex items-center">
                        <div class="w-14 h-14 bg-white/20 rounded-lg flex items-center justify-center mr-6 flex-shrink-0">
                            <svg class="w-7 h-7 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"></path><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"></path></svg>
                        </div>
                        <div>
                            <p class="text-sm opacity-75">Email</p>
                            <p class="text-lg font-semibold">{site_name.lower().replace(' ', '')}@gmail.com</p>
                        </div>
                    </div>
                    <div class="flex items-center">
                        <div class="w-14 h-14 bg-white/20 rounded-lg flex items-center justify-center mr-6 flex-shrink-0">
                            <svg class="w-7 h-7 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path></svg>
                        </div>
                        <div>
                            <p class="text-sm opacity-75">Address</p>
                            <p class="text-lg font-semibold">{contact_data_3["address"]}</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-white p-12 md:p-20 flex flex-col justify-center">
                <h2 class="text-3xl font-bold mb-8">Send a Message</h2>
                <form action="thanks_you.php" method="POST" class="space-y-6">
                    <div>
                        <input type="text" name="name" required class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none text-lg" placeholder="Your Name *">
                    </div>
                    <div>
                        <input type="email" name="email" required class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none text-lg" placeholder="Your Email *">
                    </div>
                    <div>
                        <input type="tel" name="phone" class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none text-lg" placeholder="Phone Number">
                    </div>
                    <div>
                        <textarea name="message" rows="5" required class="w-full px-0 py-3 border-0 border-b-2 border-gray-300 focus:border-{primary} transition-all outline-none resize-none text-lg" placeholder="Your Message *"></textarea>
                    </div>
                    <button type="submit" class="bg-{primary} hover:bg-{hover} text-white px-12 py-4 rounded-full text-lg font-bold transition-all shadow-lg hover:shadow-xl transform hover:scale-105">Send Message</button>
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
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Start Your Journey</h1>
                <p class="text-xl text-gray-600">Tell us about your project and let's create something amazing together</p>
            </div>

            <div class="max-w-5xl mx-auto relative">
                <div class="bg-white rounded-3xl shadow-2xl p-10 md:p-16">
                    <form action="thanks_you.php" method="POST" class="space-y-8">
                        <div class="grid md:grid-cols-3 gap-6">
                            <div>
                                <label class="block text-sm font-bold text-gray-700 mb-3">NAME *</label>
                                <input type="text" name="name" required class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none">
                            </div>
                            <div>
                                <label class="block text-sm font-bold text-gray-700 mb-3">EMAIL *</label>
                                <input type="email" name="email" required class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none">
                            </div>
                            <div>
                                <label class="block text-sm font-bold text-gray-700 mb-3">PHONE</label>
                                <input type="tel" name="phone" class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none">
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-bold text-gray-700 mb-3">YOUR MESSAGE *</label>
                            <textarea name="message" rows="6" required class="w-full px-5 py-4 bg-gray-50 border-2 border-gray-200 rounded-xl focus:border-{primary} focus:bg-white transition-all outline-none resize-none"></textarea>
                        </div>
                        <div class="flex justify-center pt-4">
                            <button type="submit" class="bg-{primary} hover:bg-{hover} text-white px-16 py-5 rounded-xl text-lg font-bold transition-all shadow-xl hover:shadow-2xl transform hover:-translate-y-1">Submit</button>
                        </div>
                    </form>
                </div>

                <div class="grid md:grid-cols-3 gap-6 mt-12">
                    <div class="bg-white rounded-2xl shadow-xl p-6 text-center border-t-4 border-{primary}">
                        <div class="w-12 h-12 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-3">
                            <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                        </div>
                        <h3 class="font-bold text-gray-900 mb-1">Email</h3>
                        <p class="text-sm text-gray-600">{site_name.lower().replace(' ', '')}@gmail.com</p>
                    </div>
                    <div class="bg-white rounded-2xl shadow-xl p-6 text-center border-t-4 border-{primary}">
                        <div class="w-12 h-12 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-3">
                            <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                        </div>
                        <h3 class="font-bold text-gray-900 mb-1">Phone</h3>
                        <p class="text-sm text-gray-600">{contact_data_1["phone"]}</p>
                    </div>
                    <div class="bg-white rounded-2xl shadow-xl p-6 text-center border-t-4 border-{primary}">
                        <div class="w-12 h-12 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-3">
                            <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        </div>
                        <h3 class="font-bold text-gray-900 mb-1">Hours</h3>
                        <p class="text-sm text-gray-600">Mon-Fri: 9AM-6PM</p>
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
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Get Started</h1>
                <p class="text-xl text-gray-600">Fill out the form below and we'll get back to you shortly</p>
            </div>

            <div class="max-w-4xl mx-auto">
                <div class="bg-white rounded-3xl shadow-2xl p-10 md:p-16">
                    <form action="thanks_you.php" method="POST" class="space-y-8">
                        <div class="grid md:grid-cols-2 gap-8">
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                                    Full Name <span class="text-red-500 ml-1">*</span>
                                </label>
                                <input type="text" name="name" required class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none" placeholder="John Doe">
                            </div>
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                                    Email Address <span class="text-red-500 ml-1">*</span>
                                </label>
                                <input type="email" name="email" required class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none" placeholder="john@example.com">
                            </div>
                        </div>

                        <div class="grid md:grid-cols-2 gap-8">
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                                    Phone Number
                                </label>
                                <input type="tel" name="phone" class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none" placeholder="+1 (555) 123-4567">
                            </div>
                            <div>
                                <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                    <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
                                    Company
                                </label>
                                <input type="text" name="company" class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none" placeholder="Your Company">
                            </div>
                        </div>

                        <div>
                            <label class="block text-gray-700 font-bold mb-3 flex items-center">
                                <svg class="w-5 h-5 mr-2 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"></path></svg>
                                Your Message <span class="text-red-500 ml-1">*</span>
                            </label>
                            <textarea name="message" rows="6" required class="w-full px-5 py-4 border-2 border-gray-300 rounded-xl focus:border-{primary} focus:ring-2 focus:ring-{primary}/20 transition-all outline-none resize-none" placeholder="Tell us about your project and how we can help..."></textarea>
                        </div>

                        <div class="flex justify-center pt-4">
                            <button type="submit" class="bg-{primary} hover:bg-{hover} text-white px-16 py-5 rounded-xl text-lg font-bold transition-all shadow-xl hover:shadow-2xl transform hover:-translate-y-1 flex items-center">
                                Send Message
                                <svg class="w-6 h-6 ml-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                            </button>
                        </div>
                    </form>

                    <div class="mt-12 pt-8 border-t border-gray-200 grid md:grid-cols-3 gap-6 text-center">
                        <div>
                            <p class="text-sm text-gray-500 mb-1">Email</p>
                            <p class="font-semibold text-gray-900">{site_name.lower().replace(' ', '')}@gmail.com</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-500 mb-1">Phone</p>
                            <p class="font-semibold text-gray-900">{contact_data_2["phone"]}</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-500 mb-1">Response Time</p>
                            <p class="font-semibold text-gray-900">Within 24 hours</p>
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
        # Проверяем наличие hero.jpg для вариантов с изображением
        has_hero = self._has_image('hero.jpg')

        # Если нет hero.jpg, используем вариант без изображения (3)
        if not has_hero:
            hero_variant = 3
        else:
            hero_variant = random.randint(1, 5)

        # Вариация 1: Фотография справа
        if hero_variant == 1:
            return f"""<main>
    <section class="py-20 bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h1 class="text-5xl md:text-6xl font-bold mb-6">Welcome to {site_name}</h1>
                    <p class="text-xl text-gray-600 mb-8">Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.</p>
                    <div class="flex flex-col sm:flex-row gap-4">
                        <a href="company.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl text-center">
                            About Us
                        </a>
                        <a href="contact.php" class="inline-block bg-white hover:bg-gray-50 text-{primary} border-2 border-{primary} px-8 py-4 rounded-lg text-lg font-semibold transition text-center">
                            Contact
                        </a>
                    </div>
                </div>
                <div>
                    <img src="images/hero.jpg" alt="{site_name}" class="rounded-2xl shadow-2xl w-full h-96 object-cover">
                </div>
            </div>
        </div>
    </section>
"""

        # Вариация 2: Карусель с фотографиями на фоне
        elif hero_variant == 2:
            # Собираем доступные изображения для карусели
            carousel_images = []
            if self._has_image('hero.jpg'):
                carousel_images.append(('hero.jpg', 'Slide 1'))
            if self._has_image('about.jpg'):
                carousel_images.append(('about.jpg', 'Slide 2'))
            if self._has_image('service1.jpg'):
                carousel_images.append(('service1.jpg', 'Slide 3'))

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
                <h1 class="text-5xl md:text-7xl font-bold mb-6 drop-shadow-lg">Welcome to {site_name}</h1>
                <p class="text-xl md:text-2xl mb-8 drop-shadow-lg">Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.</p>
                <div class="flex flex-col sm:flex-row gap-4 justify-center">
                    <a href="company.php" class="inline-block bg-white hover:bg-gray-100 text-{primary} px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        About Us
                    </a>
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        Contact
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
                    Welcome to {site_name}
                </h1>
                <p class="text-xl md:text-2xl text-gray-600 mb-8">
                    Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.
                </p>
                <div class="flex flex-col sm:flex-row gap-4 justify-center">
                    <a href="company.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        About Us
                    </a>
                    <a href="contact.php" class="inline-block bg-white hover:bg-gray-50 text-{primary} border-2 border-{primary} px-8 py-4 rounded-lg text-lg font-semibold transition">
                        Contact
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
                <h1 class="text-6xl md:text-8xl font-bold mb-6 drop-shadow-2xl">Welcome to {site_name}</h1>
                <p class="text-2xl md:text-3xl mb-12 drop-shadow-lg">Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.</p>
                <div class="flex justify-center">
                    <a href="contact.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-12 py-5 rounded-lg text-xl font-bold transition shadow-2xl hover:shadow-3xl transform hover:-translate-y-1">
                        Contact Us
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
                    <img src="images/hero.jpg" alt="{site_name}" class="rounded-2xl shadow-2xl w-full h-96 object-cover">
                </div>
                <div class="order-1 md:order-2">
                    <h1 class="text-5xl md:text-6xl font-bold mb-6">Welcome to {site_name}</h1>
                    <p class="text-xl text-gray-600 mb-8">Your trusted partner in {theme}. We deliver exceptional results that exceed expectations.</p>
                    <div class="flex flex-col sm:flex-row gap-4">
                        <a href="company.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl text-center">
                            About Us
                        </a>
                        <a href="contact.php" class="inline-block bg-white hover:bg-gray-50 text-{primary} border-2 border-{primary} px-8 py-4 rounded-lg text-lg font-semibold transition text-center">
                            Contact
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </section>
"""

    def generate_thankyou_page(self, site_name, primary, hover):
        """Генерация Thanks You страницы с 6 вариациями"""
        thanks_variant = random.randint(1, 6)

        # Вариация 1: Простая с иконкой галочки
        if thanks_variant == 1:
            return f"""<main>
    <section class="min-h-screen flex items-center justify-center bg-gradient-to-br from-{primary}/5 to-white">
        <div class="container mx-auto px-6">
            <div class="max-w-2xl mx-auto text-center">
                <div class="w-24 h-24 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-8 shadow-lg">
                    <svg class="w-12 h-12 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                    </svg>
                </div>
                <h1 class="text-5xl md:text-6xl font-bold mb-6">Thank You!</h1>
                <p class="text-xl text-gray-600 mb-8">Your message has been sent successfully. We'll get back to you soon.</p>
                <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                    Return to Homepage
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
                    Success!
                </h1>
                <p class="text-2xl text-gray-700 mb-4 font-semibold">Thank you for reaching out!</p>
                <p class="text-lg text-gray-600 mb-10">We've received your message and will respond within 24 hours.</p>
                <div class="flex flex-col sm:flex-row gap-4 justify-center">
                    <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-lg text-lg font-semibold transition transform hover:scale-105 shadow-xl">
                        Back to Home
                    </a>
                    <a href="services.php" class="inline-block bg-white hover:bg-gray-50 text-{primary} border-2 border-{primary} px-10 py-4 rounded-lg text-lg font-semibold transition transform hover:scale-105">
                        View Services
                    </a>
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
                    <div class="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-10 h-10 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                    </div>
                    <h1 class="text-5xl font-bold mb-4">Message Sent Successfully!</h1>
                    <p class="text-xl text-gray-600">Thank you for contacting {site_name}</p>
                </div>

                <div class="bg-white rounded-2xl shadow-xl p-10 mb-12">
                    <h2 class="text-2xl font-bold mb-8 text-center">What Happens Next?</h2>
                    <div class="space-y-6">
                        <div class="flex items-start">
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">1</div>
                            <div class="ml-6">
                                <h3 class="text-xl font-bold mb-2">We Review Your Message</h3>
                                <p class="text-gray-600">Our team will carefully review your inquiry within the next few hours.</p>
                            </div>
                        </div>
                        <div class="flex items-start">
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">2</div>
                            <div class="ml-6">
                                <h3 class="text-xl font-bold mb-2">Personalized Response</h3>
                                <p class="text-gray-600">We'll prepare a detailed response tailored to your specific needs.</p>
                            </div>
                        </div>
                        <div class="flex items-start">
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">3</div>
                            <div class="ml-6">
                                <h3 class="text-xl font-bold mb-2">Get Back to You</h3>
                                <p class="text-gray-600">Expect a response from us within 24 hours via email.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="text-center">
                    <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        Return to Homepage
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
                <h1 class="text-7xl md:text-8xl font-bold mb-8 text-{primary}">Thanks!</h1>
                <div class="w-24 h-1 bg-{primary} mx-auto mb-8"></div>
                <p class="text-2xl text-gray-700 mb-4">We've received your message.</p>
                <p class="text-lg text-gray-600 mb-12">Our team will respond shortly.</p>
                <a href="index.php" class="text-{primary} hover:text-{hover} text-lg font-semibold transition border-b-2 border-{primary}">
                    ← Back to Home
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
                        <div class="inline-block p-4 bg-green-100 rounded-full mb-6">
                            <svg class="w-16 h-16 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                        </div>
                        <h1 class="text-5xl font-bold mb-4">Thank You!</h1>
                        <p class="text-xl text-gray-600">Your message has been successfully sent to our team.</p>
                    </div>

                    <div class="border-t border-gray-200 pt-8 mb-8">
                        <div class="grid md:grid-cols-3 gap-6 text-center">
                            <div>
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                                    <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                </div>
                                <p class="font-semibold text-gray-900">Response Time</p>
                                <p class="text-sm text-gray-600">Within 24 hours</p>
                            </div>
                            <div>
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                                    <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                    </svg>
                                </div>
                                <p class="font-semibold text-gray-900">Email</p>
                                <p class="text-sm text-gray-600">Check your inbox</p>
                            </div>
                            <div>
                                <div class="w-12 h-12 bg-{primary}/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                                    <svg class="w-6 h-6 text-{primary} flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                                    </svg>
                                </div>
                                <p class="font-semibold text-gray-900">Our Team</p>
                                <p class="text-sm text-gray-600">Ready to help</p>
                            </div>
                        </div>
                    </div>

                    <div class="text-center pt-4">
                        <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-10 py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                            Back to Homepage
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
                    <h1 class="text-6xl font-bold mb-6">Message Received!</h1>
                    <p class="text-2xl text-gray-700 mb-3">Thank you for contacting us.</p>
                    <p class="text-lg text-gray-600 mb-10">We'll be in touch very soon!</p>
                </div>

                <div class="bg-gray-50 rounded-2xl p-8 mb-10">
                    <h2 class="text-xl font-bold mb-6 text-center">While You Wait, Explore More</h2>
                    <div class="grid md:grid-cols-3 gap-4">
                        <a href="services.php" class="block p-6 bg-white rounded-xl hover:shadow-lg transition text-center">
                            <svg class="w-8 h-8 text-{primary} mx-auto mb-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                            </svg>
                            <p class="font-semibold text-gray-900">Our Services</p>
                        </a>
                        <a href="company.php" class="block p-6 bg-white rounded-xl hover:shadow-lg transition text-center">
                            <svg class="w-8 h-8 text-{primary} mx-auto mb-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                            </svg>
                            <p class="font-semibold text-gray-900">About Us</p>
                        </a>
                        <a href="blog.php" class="block p-6 bg-white rounded-xl hover:shadow-lg transition text-center">
                            <svg class="w-8 h-8 text-{primary} mx-auto mb-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                            </svg>
                            <p class="font-semibold text-gray-900">Blog</p>
                        </a>
                    </div>
                </div>

                <div class="text-center">
                    <a href="index.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-12 py-4 rounded-full text-lg font-bold transition shadow-xl hover:shadow-2xl transform hover:scale-105">
                        Return to Homepage
                    </a>
                </div>
            </div>
        </div>
    </section>
</main>"""

    def generate_home_sections(self):
        """Генерация случайных секций для Home страницы"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        country = self.blueprint.get('country', 'USA')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        # Все доступные секции (кроме Hero - она статична)
        all_sections = {
            'image_text_about': f"""
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
                    <a href="company.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg font-semibold transition">
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
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-12">
                <h2 class="text-4xl font-bold mb-4">Our Gallery</h2>
                <p class="text-gray-600 text-lg">Explore our latest projects and achievements</p>
            </div>
            <div class="grid md:grid-cols-3 gap-6">
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
            </div>
        </div>
    </section>""",

            'cards_3_animated': f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-12">Our Services</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="group bg-white border border-gray-200 rounded-xl p-8 hover:shadow-2xl hover:scale-105 transition-all duration-300 cursor-pointer">
                    <div class="w-16 h-16 bg-{primary}/10 rounded-full flex items-center justify-center mb-6 group-hover:bg-{primary} transition-colors">
                        <svg class="w-8 h-8 text-{primary} group-hover:text-white transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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
                        <svg class="w-8 h-8 text-{primary} group-hover:text-white transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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
                        <svg class="w-8 h-8 text-{primary} group-hover:text-white transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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

            'image_text_alternating': self.generate_image_text_alternating_section(site_name, theme, primary, hover),

            'cards_6_grid': self.generate_what_we_offer_section(site_name, theme, primary, hover),

            'gallery_horizontal': f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold mb-12">Our Work</h2>
            <div class="grid md:grid-cols-3 gap-6">
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
            </div>
        </div>
    </section>""",

            'cards_3_carousel_bg': self.generate_featured_solutions_section(site_name, theme, primary, hover),

            'carousel_workflow': self.generate_our_process_section(site_name, theme, primary, hover),

            'carousel_blog': f"""
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
                    <img src="images/blog1.jpg" alt="Blog Post 1" class="w-full h-48 object-cover">
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
                    <img src="images/blog2.jpg" alt="Blog Post 2" class="w-full h-48 object-cover">
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
                    <img src="images/blog3.jpg" alt="Blog Post 3" class="w-full h-48 object-cover">
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
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6 max-w-3xl">
            <div class="text-center mb-12">
                <h2 class="text-4xl font-bold mb-4">Get Started Today</h2>
                <p class="text-gray-600 text-lg">Tell us about your project and we'll get back to you soon</p>
            </div>
            <div class="bg-gray-50 rounded-xl p-8 shadow-lg">
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
                        <label for="phone" class="block text-gray-700 font-semibold mb-2">Phone Number</label>
                        <input type="tel" id="phone" name="phone" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent">
                    </div>
                    <div>
                        <label for="message" class="block text-gray-700 font-semibold mb-2">Tell Us About Your Project</label>
                        <textarea id="message" name="message" rows="4" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-{primary} focus:border-transparent"></textarea>
                    </div>
                    <button type="submit" class="w-full bg-{primary} hover:bg-{hover} text-white py-4 rounded-lg text-lg font-semibold transition shadow-lg hover:shadow-xl">
                        Send Message
                    </button>
                </form>
            </div>
        </div>
    </section>""",

            'cards_6_slider': self.generate_our_locations_section(country, primary, hover),

            # НОВЫЕ ТЕКСТОВЫЕ СЕКЦИИ (БЕЗ ИЗОБРАЖЕНИЙ)
            'stats_section': f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center text-white mb-16">Our Achievements</h2>
            <div class="grid md:grid-cols-4 gap-8">
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">500+</div>
                    <p class="text-white/80 text-lg">Projects Completed</p>
                </div>
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">15+</div>
                    <p class="text-white/80 text-lg">Years Experience</p>
                </div>
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">98%</div>
                    <p class="text-white/80 text-lg">Client Satisfaction</p>
                </div>
                <div class="text-center">
                    <div class="text-5xl font-bold text-white mb-2">50+</div>
                    <p class="text-white/80 text-lg">Team Members</p>
                </div>
            </div>
        </div>
    </section>""",

            'why_choose_us': f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl font-bold mb-4">Why Choose Us</h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">We deliver exceptional results through our commitment to quality, innovation, and customer satisfaction</p>
            </div>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="text-center p-6">
                    <div class="w-20 h-20 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-10 h-10 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-3">Proven Track Record</h3>
                    <p class="text-gray-600">Over 15 years of delivering successful projects across various industries</p>
                </div>
                <div class="text-center p-6">
                    <div class="w-20 h-20 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-10 h-10 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-3">Fast Delivery</h3>
                    <p class="text-gray-600">We understand deadlines and consistently deliver projects on time</p>
                </div>
                <div class="text-center p-6">
                    <div class="w-20 h-20 bg-{primary}/10 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-10 h-10 text-{primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold mb-3">Best Value</h3>
                    <p class="text-gray-600">Competitive pricing without compromising on quality or service</p>
                </div>
            </div>
        </div>
    </section>""",

            'timeline_process': f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl font-bold mb-4">Our Process</h2>
                <p class="text-gray-600 text-lg">A streamlined approach to deliver exceptional results</p>
            </div>
            <div class="max-w-4xl mx-auto">
                <div class="relative">
                    <div class="absolute left-1/2 transform -translate-x-1/2 h-full w-1 bg-{primary}/20"></div>
                    <div class="space-y-12">
                        <div class="flex items-center">
                            <div class="w-1/2 pr-8 text-right">
                                <h3 class="text-2xl font-bold mb-2">1. Discovery</h3>
                                <p class="text-gray-600">We analyze your needs and create a detailed project roadmap</p>
                            </div>
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center text-white font-bold z-10">1</div>
                            <div class="w-1/2 pl-8"></div>
                        </div>
                        <div class="flex items-center">
                            <div class="w-1/2 pr-8"></div>
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center text-white font-bold z-10">2</div>
                            <div class="w-1/2 pl-8">
                                <h3 class="text-2xl font-bold mb-2">2. Planning</h3>
                                <p class="text-gray-600">Strategic planning and resource allocation for optimal results</p>
                            </div>
                        </div>
                        <div class="flex items-center">
                            <div class="w-1/2 pr-8 text-right">
                                <h3 class="text-2xl font-bold mb-2">3. Execution</h3>
                                <p class="text-gray-600">Implementation with regular updates and quality checkpoints</p>
                            </div>
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center text-white font-bold z-10">3</div>
                            <div class="w-1/2 pl-8"></div>
                        </div>
                        <div class="flex items-center">
                            <div class="w-1/2 pr-8"></div>
                            <div class="w-12 h-12 bg-{primary} rounded-full flex items-center justify-center text-white font-bold z-10">4</div>
                            <div class="w-1/2 pl-8">
                                <h3 class="text-2xl font-bold mb-2">4. Delivery</h3>
                                <p class="text-gray-600">Final review, optimization, and successful project handover</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>""",

            'faq_section': f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl font-bold mb-4">Frequently Asked Questions</h2>
                <p class="text-gray-600 text-lg">Find answers to common questions about our services</p>
            </div>
            <div class="max-w-3xl mx-auto space-y-4">
                <div class="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition">
                    <h3 class="text-xl font-bold mb-2 text-{primary}">What services do you offer?</h3>
                    <p class="text-gray-600">We provide comprehensive {theme} services tailored to your specific needs, including consultation, implementation, and ongoing support.</p>
                </div>
                <div class="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition">
                    <h3 class="text-xl font-bold mb-2 text-{primary}">How long does a typical project take?</h3>
                    <p class="text-gray-600">Project timelines vary based on scope and complexity. We provide detailed timelines during the initial consultation phase.</p>
                </div>
                <div class="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition">
                    <h3 class="text-xl font-bold mb-2 text-{primary}">Do you offer support after project completion?</h3>
                    <p class="text-gray-600">Yes, we provide comprehensive post-project support and maintenance to ensure long-term success.</p>
                </div>
                <div class="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition">
                    <h3 class="text-xl font-bold mb-2 text-{primary}">What makes your company different?</h3>
                    <p class="text-gray-600">Our commitment to quality, personalized approach, and proven track record set us apart in the industry.</p>
                </div>
            </div>
        </div>
    </section>""",

            'approach_section': f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <div class="max-w-4xl mx-auto">
                <h2 class="text-4xl font-bold text-center mb-16">Our Approach</h2>
                <div class="space-y-8">
                    <div class="flex gap-6">
                        <div class="flex-shrink-0 w-16 h-16 bg-{primary} rounded-lg flex items-center justify-center text-white text-2xl font-bold">1</div>
                        <div>
                            <h3 class="text-2xl font-bold mb-3">Client-Centered Solutions</h3>
                            <p class="text-gray-600 text-lg">We prioritize understanding your unique challenges and goals to deliver customized solutions that drive real results.</p>
                        </div>
                    </div>
                    <div class="flex gap-6">
                        <div class="flex-shrink-0 w-16 h-16 bg-{primary} rounded-lg flex items-center justify-center text-white text-2xl font-bold">2</div>
                        <div>
                            <h3 class="text-2xl font-bold mb-3">Innovation & Excellence</h3>
                            <p class="text-gray-600 text-lg">We combine cutting-edge techniques with industry best practices to ensure superior outcomes.</p>
                        </div>
                    </div>
                    <div class="flex gap-6">
                        <div class="flex-shrink-0 w-16 h-16 bg-{primary} rounded-lg flex items-center justify-center text-white text-2xl font-bold">3</div>
                        <div>
                            <h3 class="text-2xl font-bold mb-3">Transparent Communication</h3>
                            <p class="text-gray-600 text-lg">Regular updates and open dialogue ensure you're always informed about your project's progress.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>""",

            'benefits_grid': f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-16">Key Benefits</h2>
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
                <div class="p-6 border-l-4 border-{primary} bg-gray-50">
                    <h3 class="text-xl font-bold mb-3">Cost Efficiency</h3>
                    <p class="text-gray-600">Maximize your ROI with our optimized processes and competitive pricing structure</p>
                </div>
                <div class="p-6 border-l-4 border-{primary} bg-gray-50">
                    <h3 class="text-xl font-bold mb-3">Scalability</h3>
                    <p class="text-gray-600">Solutions designed to grow with your business needs and adapt to market changes</p>
                </div>
                <div class="p-6 border-l-4 border-{primary} bg-gray-50">
                    <h3 class="text-xl font-bold mb-3">24/7 Support</h3>
                    <p class="text-gray-600">Round-the-clock assistance to ensure your operations run smoothly</p>
                </div>
                <div class="p-6 border-l-4 border-{primary} bg-gray-50">
                    <h3 class="text-xl font-bold mb-3">Expert Team</h3>
                    <p class="text-gray-600">Skilled professionals with extensive industry experience and certifications</p>
                </div>
                <div class="p-6 border-l-4 border-{primary} bg-gray-50">
                    <h3 class="text-xl font-bold mb-3">Quality Assurance</h3>
                    <p class="text-gray-600">Rigorous testing and quality control at every stage of development</p>
                </div>
                <div class="p-6 border-l-4 border-{primary} bg-gray-50">
                    <h3 class="text-xl font-bold mb-3">Innovation</h3>
                    <p class="text-gray-600">Stay ahead with the latest technologies and industry best practices</p>
                </div>
            </div>
        </div>
    </section>""",

            'testimonials_text': f"""
    <section class="py-20 bg-gray-50">
        <div class="container mx-auto px-6">
            <h2 class="text-4xl font-bold text-center mb-16">What Our Clients Say</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="bg-white p-8 rounded-xl shadow-md">
                    <div class="text-{primary} text-4xl mb-4">"</div>
                    <p class="text-gray-600 mb-6">Outstanding service and exceptional results. The team went above and beyond to ensure our project's success.</p>
                    <div class="flex items-center gap-2 mb-2">
                        <div class="text-yellow-400">★★★★★</div>
                    </div>
                    <p class="font-bold">John Anderson</p>
                    <p class="text-gray-500 text-sm">CEO, Tech Solutions</p>
                </div>
                <div class="bg-white p-8 rounded-xl shadow-md">
                    <div class="text-{primary} text-4xl mb-4">"</div>
                    <p class="text-gray-600 mb-6">Professional, reliable, and highly skilled. They delivered exactly what we needed, on time and within budget.</p>
                    <div class="flex items-center gap-2 mb-2">
                        <div class="text-yellow-400">★★★★★</div>
                    </div>
                    <p class="font-bold">Sarah Mitchell</p>
                    <p class="text-gray-500 text-sm">Director, Marketing Agency</p>
                </div>
                <div class="bg-white p-8 rounded-xl shadow-md">
                    <div class="text-{primary} text-4xl mb-4">"</div>
                    <p class="text-gray-600 mb-6">Excellent communication throughout the project. Their expertise and dedication made all the difference.</p>
                    <div class="flex items-center gap-2 mb-2">
                        <div class="text-yellow-400">★★★★★</div>
                    </div>
                    <p class="font-bold">Michael Chen</p>
                    <p class="text-gray-500 text-sm">Founder, StartupHub</p>
                </div>
            </div>
        </div>
    </section>""",

            'cta_centered': f"""
    <section class="py-20 bg-{primary}">
        <div class="container mx-auto px-6">
            <div class="max-w-3xl mx-auto text-center">
                <h2 class="text-4xl font-bold text-white mb-6">Ready to Get Started?</h2>
                <p class="text-white/90 text-xl mb-8">Let's discuss how we can help you achieve your goals and transform your business</p>
                <div class="flex flex-wrap gap-4 justify-center">
                    <a href="contact.php" class="inline-block bg-white text-{primary} px-8 py-4 rounded-lg font-bold text-lg hover:bg-gray-100 transition shadow-lg">
                        Contact Us Today
                    </a>
                    <a href="services.php" class="inline-block bg-transparent border-2 border-white text-white px-8 py-4 rounded-lg font-bold text-lg hover:bg-white hover:text-{primary} transition">
                        View Services
                    </a>
                </div>
            </div>
        </div>
    </section>""",

            'features_list': f"""
    <section class="py-20 bg-white">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div>
                    <h2 class="text-4xl font-bold mb-6">What Sets Us Apart</h2>
                    <p class="text-gray-600 text-lg mb-8">We combine expertise, innovation, and dedication to deliver exceptional results that exceed expectations.</p>
                    <div class="space-y-4">
                        <div class="flex gap-4">
                            <div class="flex-shrink-0 w-6 h-6 bg-{primary} rounded-full flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-bold text-lg mb-1">Industry-Leading Expertise</h3>
                                <p class="text-gray-600">Our team brings years of specialized experience to every project</p>
                            </div>
                        </div>
                        <div class="flex gap-4">
                            <div class="flex-shrink-0 w-6 h-6 bg-{primary} rounded-full flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-bold text-lg mb-1">Customized Solutions</h3>
                                <p class="text-gray-600">Tailored approaches designed specifically for your unique needs</p>
                            </div>
                        </div>
                        <div class="flex gap-4">
                            <div class="flex-shrink-0 w-6 h-6 bg-{primary} rounded-full flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-bold text-lg mb-1">Results-Driven Approach</h3>
                                <p class="text-gray-600">Focused on delivering measurable outcomes and ROI</p>
                            </div>
                        </div>
                        <div class="flex gap-4">
                            <div class="flex-shrink-0 w-6 h-6 bg-{primary} rounded-full flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-bold text-lg mb-1">Ongoing Partnership</h3>
                                <p class="text-gray-600">Long-term support and collaboration beyond project completion</p>
                            </div>
                        </div>
                    </div>
                </div>
                <div>
                    <div class="bg-gradient-to-br from-{primary} to-{hover} rounded-xl p-12 text-white">
                        <h3 class="text-3xl font-bold mb-6">Let's Build Something Great Together</h3>
                        <p class="text-white/90 mb-8">Contact us today to discuss your project and discover how we can help you achieve your goals.</p>
                        <a href="contact.php" class="inline-block bg-white text-{primary} px-8 py-4 rounded-lg font-bold hover:bg-gray-100 transition">
                            Start Your Project
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </section>""",
        }

        # Фильтруем секции, требующие gallery изображения
        # Gallery изображения gallery1-3 теперь required (минимум 10 изображений)
        # gallery4 optional, генерируется только при num_images >= 14
        # Секции gallery используют gallery1-3, всегда доступны при минимуме
        sections_requiring_gallery = {'gallery_centered', 'gallery_horizontal'}

        # Проверяем, сколько изображений будет сгенерировано
        # Приоритетные (required): hero(1) + services(3) + blog(3) + gallery(3) = 10
        # Gallery секции всегда доступны с минимумом 10 изображений
        has_gallery_images = hasattr(self, 'num_images_to_generate') and self.num_images_to_generate >= 10

        # Выбираем доступные секции
        available_section_keys = list(all_sections.keys())

        # Если gallery изображений не будет, убираем gallery секции (только при num_images < 10)
        if not has_gallery_images:
            available_section_keys = [k for k in available_section_keys if k not in sections_requiring_gallery]
            print(f"  ⚠️  Gallery секции исключены (недостаточно изображений: нужно минимум 10)")

        # Выбираем 5-6 случайных секций из доступных
        random.shuffle(available_section_keys)
        num_sections = random.randint(5, 6)
        # Убедимся что не выбираем больше, чем доступно
        num_sections = min(num_sections, len(available_section_keys))
        selected_sections = available_section_keys[:num_sections]

        # Если contact_form_multistep в выбранных секциях, переместить ее в конец
        if 'contact_form_multistep' in selected_sections:
            selected_sections.remove('contact_form_multistep')
            selected_sections.append('contact_form_multistep')

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
        if page_name in ['blog1', 'blog2', 'blog3', 'blog4', 'blog5', 'blog6']:
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
CRITICAL: Testimonials MUST use avatar circles with initials, NOT images

Return ONLY the content for <main> tag (not full HTML)."""
            },
            'company': {
                'title': 'Company',
                'prompt': f"""Create a professional COMPANY page for {site_name} - a {theme} business.

REQUIREMENTS:
- Heading section with page title
- Company story/mission section with rich text content (NO images required)
- Team or values section with descriptive text (NO images required)
- Use clean text layouts with proper typography and spacing
- MUST include a call-to-action button at the bottom that redirects to contact.php: <a href="contact.php" class="...">Contact Us</a>
- Modern, professional design with Tailwind CSS
- Color scheme: {colors.get('primary')} primary, {colors.get('hover')} hover
- Responsive design
- NO emojis, NO prices
- NO images (all content should be text-based with icons if needed)

CRITICAL:
- Page MUST have a CTA button at the bottom that links to contact.php
- DO NOT use any images - create compelling content using text, typography, and icons only
- Focus on storytelling through well-crafted text sections

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
                    <a href="company.php" class="inline-block bg-{primary} hover:bg-{hover} text-white px-8 py-4 rounded-lg text-lg font-semibold transition">
                        Learn More
                    </a>
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
        """Генерация blog страниц с вариациями (с/без картинки, с/без стрелок)"""
        site_name = self.blueprint.get('site_name', 'Company')
        theme = self.blueprint.get('theme', 'business')
        colors = self.blueprint.get('color_scheme', {})
        primary = colors.get('primary', 'blue-600')
        hover = colors.get('hover', 'blue-700')

        blog_titles = {
            'blog1': f'The Future of {theme}',
            'blog2': f'Top 5 Trends in {theme}',
            'blog3': f'How to Choose the Right {theme} Service',
            'blog4': f'Best Practices for {theme} Success',
            'blog5': f'Common {theme} Mistakes to Avoid',
            'blog6': f'The Complete {theme} Guide'
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
            """,
            'blog4': f"""
            <p class="text-lg text-gray-700 mb-6">
                Achieving success in {theme} requires following proven strategies and techniques. Learn from
                industry experts and implement these best practices to maximize your results.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Set Clear Goals</h2>
            <p class="text-gray-700 mb-6">
                Define specific, measurable objectives for your {theme} initiatives. Clear goals provide
                direction and help you track progress effectively.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Plan Strategically</h2>
            <p class="text-gray-700 mb-6">
                Develop a comprehensive plan that outlines the steps needed to achieve your goals. Include
                timelines, resources, and key milestones.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Execute Consistently</h2>
            <p class="text-gray-700 mb-6">
                Consistency is key to success. Implement your strategies methodically and make adjustments
                based on performance data and feedback.
            </p>
            """,
            'blog5': f"""
            <p class="text-lg text-gray-700 mb-6">
                Avoiding common pitfalls can save you time, money, and frustration. Discover the most frequent
                mistakes in {theme} and learn how to prevent them.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Mistake 1: Lack of Planning</h2>
            <p class="text-gray-700 mb-6">
                Rushing into {theme} projects without proper planning often leads to costly delays and
                suboptimal results. Take time to plan thoroughly.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Mistake 2: Ignoring Expert Advice</h2>
            <p class="text-gray-700 mb-6">
                Trying to handle everything yourself can backfire. Consult with professionals who have
                experience in {theme} to avoid common pitfalls.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Mistake 3: Cutting Corners</h2>
            <p class="text-gray-700 mb-6">
                Quality matters in {theme}. Choosing the cheapest option or skipping important steps often
                results in poor outcomes that cost more to fix later.
            </p>
            """,
            'blog6': f"""
            <p class="text-lg text-gray-700 mb-6">
                This comprehensive guide covers everything you need to know about {theme}. Whether you're a
                beginner or looking to deepen your knowledge, this resource has you covered.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Understanding the Basics</h2>
            <p class="text-gray-700 mb-6">
                Start with the fundamentals of {theme}. Learn key concepts, terminology, and principles
                that form the foundation of successful implementation.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Advanced Techniques</h2>
            <p class="text-gray-700 mb-6">
                Once you've mastered the basics, explore advanced strategies that can take your {theme}
                efforts to the next level. Discover professional tips and insider knowledge.
            </p>
            <h2 class="text-2xl font-bold mt-8 mb-4">Putting It All Together</h2>
            <p class="text-gray-700 mb-6">
                Learn how to integrate everything you've learned into a cohesive approach. Create a roadmap
                for success and start implementing your {theme} strategy today.
            </p>
            """
        }

        blog_images = {
            'blog1': 'images/blog1.jpg',
            'blog2': 'images/blog2.jpg',
            'blog3': 'images/blog3.jpg',
            'blog4': 'images/blog4.jpg',
            'blog5': 'images/blog5.jpg',
            'blog6': 'images/blog6.jpg'
        }

        # Определяем навигацию между blog страницами
        blog_nav = {
            'blog1': {'prev': None, 'next': 'blog2.php'},
            'blog2': {'prev': 'blog1.php', 'next': 'blog3.php'},
            'blog3': {'prev': 'blog2.php', 'next': 'blog4.php'},
            'blog4': {'prev': 'blog3.php', 'next': 'blog5.php'},
            'blog5': {'prev': 'blog4.php', 'next': 'blog6.php'},
            'blog6': {'prev': 'blog5.php', 'next': None}
        }

        # Вариации: случайный выбор картинки и стрелок для каждой статьи
        blog_variations = {
            'blog1': {'has_image': random.choice([True, False]), 'has_arrows': True},
            'blog2': {'has_image': random.choice([True, False]), 'has_arrows': False},
            'blog3': {'has_image': random.choice([True, False]), 'has_arrows': False},
            'blog4': {'has_image': random.choice([True, False]), 'has_arrows': True},
            'blog5': {'has_image': random.choice([True, False]), 'has_arrows': False},
            'blog6': {'has_image': random.choice([True, False]), 'has_arrows': True}
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
                        <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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
                        <svg class="w-5 h-5 ml-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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
                separator = ' <span class="text-gray-400">|</span> '
                nav_buttons = f'<div class="flex justify-between items-center mt-12 pt-8 border-t border-gray-200">{separator.join(nav_links)}</div>'

        # Создаем секцию с картинкой (если has_image=True И изображение сгенерировано)
        image_section = ''
        blog_img_filename = page_name + '.jpg'  # Например 'blog1.jpg'
        if current_variation['has_image'] and self._has_image(blog_img_filename):
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

        # Полный список статей (6 штук)
        all_blog_articles = [
            {
                'title': f'The Future of {theme}',
                'url': 'blog1.php',
                'excerpt': f'Explore the latest innovations in {theme} and what they mean for your business.',
                'date': 'November 15, 2025',
                'image': 'images/blog1.jpg'
            },
            {
                'title': f'Top 5 Trends in {theme}',
                'url': 'blog2.php',
                'excerpt': f'Stay competitive with these emerging trends in the {theme} industry.',
                'date': 'November 10, 2025',
                'image': 'images/blog2.jpg'
            },
            {
                'title': f'How to Choose the Right {theme} Service',
                'url': 'blog3.php',
                'excerpt': f'A comprehensive guide to selecting the best {theme} solution for your needs.',
                'date': 'November 5, 2025',
                'image': 'images/blog3.jpg'
            },
            {
                'title': f'Best Practices for {theme} Success',
                'url': 'blog4.php',
                'excerpt': f'Learn proven strategies and techniques to maximize your {theme} results.',
                'date': 'November 1, 2025',
                'image': 'images/blog4.jpg'
            },
            {
                'title': f'Common {theme} Mistakes to Avoid',
                'url': 'blog5.php',
                'excerpt': f'Discover the pitfalls that could derail your {theme} projects and how to avoid them.',
                'date': 'October 28, 2025',
                'image': 'images/blog5.jpg'
            },
            {
                'title': f'The Complete {theme} Guide',
                'url': 'blog6.php',
                'excerpt': f'Everything you need to know about {theme} in one comprehensive resource.',
                'date': 'October 25, 2025',
                'image': 'images/blog6.jpg'
            }
        ]

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
                        Read More
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
        <p class="mt-2">Email: {site_name.lower().replace(' ', '')}@gmail.com</p>
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
        <p class="mt-2">Email: {site_name.lower().replace(' ', '')}@gmail.com</p>
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
        <p class="mt-2">Email: {site_name.lower().replace(' ', '')}@gmail.com</p>
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
        print(f"PHPGEN v20 - {'LANDING' if site_type == 'landing' else 'MULTIPAGE SITE'} GENERATOR")
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

        print(f"\n[5/7] Изображения (приоритетная генерация {num_images} шт)...")
        print(f"  📝 Статей блога: {self.num_blog_articles}")
        self.generate_images_for_site(output_dir, num_images)

        print("\n[6/7] Страницы...")

        if site_type == "landing":
            # Лендинг - только главная страница с секциями + служебные страницы
            pages_to_generate = ['index', 'thanks_you', 'privacy', 'terms', 'cookie']
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

        print("\n[7/7] Дополнительные файлы...")
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
        print(f"\n✨ Done! Unique design by PHPGEN v12 - Gosha Chepchik")
        
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
    print("│                      PHPGEN v20                          │")
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
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
