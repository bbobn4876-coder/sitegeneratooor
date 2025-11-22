# Translation Architecture Summary - PHPGEN v38

## Overview
This is a **statically-generated** translation architecture where translations are generated via API at site generation time. The system uses OpenRouter API with Google Gemini-2.5-Pro model to generate multi-language content.

---

## 1. TRANSLATION DATA STORAGE

### Structure
- **No persistent translation files**: Translations are generated dynamically via API calls during site generation
- **Storage mechanism**: All translations are generated in-memory and embedded directly into PHP files
- **Language specification**: Set at blueprint creation time via `language` field

### Data Flow
```
User Input → Language Detection → Blueprint Creation → API Calls → PHP Content Generation
```

---

## 2. SUPPORTED LANGUAGES

**Currently supported: 40+ European languages**

### Language Mapping System
Located at: `/home/user/sitegeneratooor/phpgen_version38.py` (lines 355-450)

**Function**: `get_language_for_country()` - Maps countries to languages

**Supported Languages**:
- Albanian, Armenian, Belarusian, Bulgarian, Catalan, Croatian, Czech, Danish
- Dutch, Estonian, Finnish, French, Georgian, German, Greek, Hungarian
- Italian, Latvian, Lithuanian, Maltese, Norwegian, Polish, Portuguese
- Romanian, Russian, Serbian, Slovak, Slovenian, Spanish, Swedish
- Turkish, Ukrainian, Azerbaijani, Bosnian, Montenegrin, Macedonian
- And more...

**Example Mapping**:
```python
'germany': 'German', 'germanия': 'German',
'france': 'French', 'франция': 'French',
'russia': 'Russian', 'россия': 'Russian',
```

---

## 3. PAGE SECTIONS & IMPLEMENTATION

### Home Page (index.php)
**API Content Types Used**:
- `menu_content` - Navigation menu translations
- `hero_content` - Hero section
- `process_steps` - "Our Process" section (3 steps)
- `featured_solutions` - Services showcase
- `approach_content` - "Why Choose Us" section
- `blog_posts` - Blog preview
- `cta_content` - Call-to-action sections

**File Location**: Lines 6053-6078

### Company Page (company.php)
- Company story/mission section
- Team member cards (3 members with images)
- Call-to-action button to contact.php

**File Location**: Lines 6008-6049

### Services Page (services.php)
- Services list with descriptions
- Feature comparisons
- Service-specific CTAs

**Generated via**: `generate_theme_content_via_api()` with "services" content type

### Blog Pages (blog.php & blog1-6.php)
**Blog Main Page**:
- Blog section headers (translated)
- Article preview cards
- "View All" link

**Individual Blog Articles**:
- Article title, date, author
- Multiple content sections
- Article-specific meta information

**Content Type**: `blog_article_full` (lines 1217-1240)
**Function**: `generate_blog_article_full()` with content sections

### Contact Page (contact.php)
**Sections**:
- Page heading (translated)
- Contact form fields (all labels translated)
- Contact information section
- Address, phone, email displays

**Content Type**: `contact_page_content` (lines 1111-1144)
**Function**: `generate_contact_page()` (line 4622)

### Footer
**Translation Keys**:
- Tagline (company mission statement)
- Quick Links title
- Legal section title
- Privacy Policy, Terms of Service, Cookie Policy links
- "All rights reserved" text

**Content Type**: `footer_content` (lines 1188-1215)
**Function**: `generate_header_footer()` (line 3895)

---

## 4. HEADER/NAVIGATION COMPONENT

### Header Definition
**Location**: `/home/user/sitegeneratooor/phpgen_version38.py` (lines 3895-4048)
**Function**: `generate_header_footer()`

### Header Variations (2 Options)
1. **Menu Right Layout** (Variant 1):
   - Logo on left
   - Navigation menu on right
   - Mobile hamburger button

2. **Centered Menu Layout** (Variant 2):
   - Logo centered at top
   - Navigation menu centered below
   - Mobile hamburger button

### Navigation Menu Items (Translated)
```python
Navigation pages for multipage sites:
- Home (menu_content.get('home'))
- Company (menu_content.get('company'))
- Services (menu_content.get('services'))
- Blog (menu_content.get('blog'))
- Contact (menu_content.get('contact'))

For landing sites:
- Home (menu_content.get('home'))
- Contact (menu_content.get('contact'))
```

### Responsive Features
- **Desktop**: Hidden hamburger button, full navigation menu
- **Mobile**: Hamburger menu toggle, vertical navigation
- **Sticky**: Header remains fixed to top (z-50)

**File Location**: Lines 3951-4012

---

## 5. MAIN GENERATION SCRIPT

### Script: phpgen_version38.py (7,225 lines)
**Location**: `/home/user/sitegeneratooor/phpgen_version38.py`

### Main Class
**Class**: `PHPWebsiteGenerator` (line 318)

### Main Workflow Method
**Function**: `generate_website()` (line 7031)

**Workflow Steps**:
```
[1/7] Load Database
      └─ Loads template sites and data from /data directory

[2/7] Create Blueprint
      └─ Extract theme, country, language from user prompt
      └─ Generate color scheme, layouts, sections
      └─ Store in self.blueprint dictionary

[3/7] Generate Header & Footer
      └─ Create HTML header with navigation menu
      └─ Create HTML footer with links and tagline
      └─ Get translations via API: menu_content, footer_content

[4/7] Generate Favicon
      └─ Create favicon file

[5/7] Generate Images
      └─ Use ByteDance Ark API to generate site images
      └─ Priority images: hero, about, services, blog, gallery, team, locations

[6/7] Generate Pages
      └─ For landing sites: index, thanks_you, privacy, terms, cookie
      └─ For multipage sites: + company, services, contact, blog, blog1-6
      └─ Each page generated via API with language requirement

[7/7] Generate Additional Files
      └─ Currently minimal (fallback only)
```

### Key Configuration
```python
API Configuration:
- API URL: https://openrouter.ai/api/v1/chat/completions
- Model: google/gemini-2.5-pro
- Max tokens: 16000
- Retry logic: 5 attempts with exponential backoff

ByteDance Image Generation:
- Model: seedream-4-0-250828
- Image size: 2K
- Format: URL with watermark: False
```

---

## 6. CONTENT GENERATION VIA API

### Core API Method
**Function**: `call_api()` (line 460)
- Handles OpenRouter API calls
- Retry logic with 5 attempts
- Error handling for various connection issues
- Timeout: 240 seconds

### Content Generation Method
**Function**: `generate_theme_content_via_api()` (line 794)

### Content Types & Prompts

| Content Type | Purpose | Output Format |
|---|---|---|
| `menu_content` | Navigation menu | JSON object with home, company, services, blog, contact |
| `hero_content` | Hero section | JSON object with heading, subheading, button text |
| `process_steps` | Our Process section | JSON array of steps with title and description |
| `featured_solutions` | Services/solutions | JSON array with title, description, image reference |
| `approach_content` | Why Choose Us | JSON with approach_title, approach_text1/2, why_title, why_text1/2 |
| `services` | Service list | JSON array of services |
| `blog_posts` | Blog preview cards | JSON array with title, excerpt, date |
| `blog_article_full` | Full blog article | JSON with title, date, author, intro, sections array |
| `blog_page_content` | Blog page headers | JSON with heading, subheading, read_more, no_posts |
| `blog_section_headers` | Blog section title | JSON with section_heading, view_all_text |
| `contact_page_content` | Contact form & info | JSON with form labels, heading, contact info labels |
| `footer_content` | Footer text | JSON with tagline, quick_links, legal, policy links |
| `policy_content` | Privacy/Terms/Cookie | JSON with policy page titles |
| `features_comparison` | Features section | JSON with section_heading, features array, CTA content |
| `about_content` | About section | JSON with heading, description, button_text |
| `gallery_content` | Gallery section | JSON with heading, description |

### Language Injection in Prompts
**Critical Language Requirement** (added to every prompt):
```
CRITICAL LANGUAGE REQUIREMENT: You MUST generate ALL content EXCLUSIVELY 
in {language} language. Every single word, title, description, and text 
MUST be in {language}. Do NOT use English or any other language. 
This is MANDATORY and NON-NEGOTIABLE. Language: {language}.
```

**Location**: Line 825

### Caching Mechanism
**Cache Key Structure**: `{theme}_{content_type}_{num_items}_{language}`
**Storage**: `self.theme_content_cache` dictionary
**Purpose**: Avoid redundant API calls for identical requests

---

## 7. BLUEPRINT STRUCTURE

### Blueprint Dictionary
**Location**: Created in `create_blueprint()` (lines 3873-3886)

### Contents
```python
{
    "site_name": str,              # User-provided site name
    "tagline": str,                # Auto-generated tagline
    "theme": str,                  # Business type (e.g., "Restaurant", "IT")
    "country": str,                # Country for localization
    "language": str,               # Target language (e.g., "German", "French")
    "color_scheme": {
        "primary": str,            # Tailwind color class (e.g., "blue-600")
        "hover": str,              # Hover color class (e.g., "blue-700")
    },
    "header_layout": str,          # 'centered', 'left-aligned', 'split', 'minimal', 'bold'
    "footer_layout": str,          # 'columns-3', 'columns-4', 'centered', 'minimal', 'split'
    "sections": list,              # Random section variation selection
    "menu": list,                  # Menu items
    "pages": list,                 # All page names
    "contact_data": {              # Country-specific contact info
        "phone": str,
        "address": str,
        "email": str,
        "postal": str,
        "cities": list,
        "streets": list,
        "phones": list,
        "postal_codes": list
    }
}
```

---

## 8. LANGUAGE DETERMINATION FLOW

### Step 1: User Input Processing
**Location**: Lines 7133-7166 (main entry point)
- User describes website
- Optionally mentions language, country, or theme

### Step 2: Blueprint Creation
**Location**: `create_blueprint()` (line 3686)

### Sub-step 2a: Extract Information
```python
# Pattern matching in user prompt
language_match = re.search(r'language[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)
country_match = re.search(r'country[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)
theme_match = re.search(r'theme[:\s]+([^,\n]+)', user_prompt, re.IGNORECASE)
```

### Sub-step 2b: Language Resolution
```
If language explicitly mentioned:
  ├─ Use provided language
Else:
  ├─ Determine country from prompt (lines 3731-3833)
  └─ Call get_language_for_country(country)
      └─ Returns mapped language from dictionary
```

### Step 3: Store in Blueprint
**Location**: Line 3878
```python
self.blueprint["language"] = language
```

### Step 4: Use Throughout Generation
**Location**: Multiple functions access via:
```python
language = self.blueprint.get('language', 'English')
```

---

## 9. CONFIG & DATA FILES

### Data Directory Structure
**Default location**: `/home/user/sitegeneratooor/data/`

**Supported file types**:
- `.zip` - Extracted automatically
- `.php` - Template site files
- `.txt`, `.json`, `.csv`, `.md`, `.html` - Reference data

**Loading**: `load_database()` (line 3558)
**Analysis**: `analyze_php_site()` (line 3650)

### No Persistent Configuration Files
- Configuration is generated dynamically per site
- No config.php, database.json, or translation files stored
- All data embedded in generated PHP files

---

## 10. ARCHITECTURE DIAGRAM

```
User Input
    ↓
[Extract: Theme, Country, Language]
    ↓
Create Blueprint (language stored here)
    ↓
Generate Header/Footer
    ├─ Call API for menu_content (with language)
    └─ Call API for footer_content (with language)
    ↓
Generate Images (ByteDance Ark)
    ↓
For Each Page:
    ├─ Create prompt with language requirement
    └─ Call API (generate_theme_content_via_api)
        ├─ Append language instruction to prompt
        ├─ Cache results by {theme}_{type}_{items}_{language}
        └─ Return translated content
    ↓
Embed All Translations in PHP Files
    ↓
Output: Complete Website with All Content in Target Language
```

---

## 11. KEY FILES & LOCATIONS

| Component | File | Lines | Function |
|---|---|---|---|
| **Main Class** | phpgen_version38.py | 318 | PHPWebsiteGenerator |
| **Main Workflow** | phpgen_version38.py | 7031 | generate_website() |
| **Language Mapping** | phpgen_version38.py | 350-458 | get_language_for_country() |
| **API Calls** | phpgen_version38.py | 460-550 | call_api() |
| **Content Generation** | phpgen_version38.py | 794-1440 | generate_theme_content_via_api() |
| **Blueprint Creation** | phpgen_version38.py | 3686-3893 | create_blueprint() |
| **Header/Footer Gen** | phpgen_version38.py | 3895-4048 | generate_header_footer() |
| **Header Layout** | phpgen_version38.py | 3072-3092 | generate_header_layout(), generate_footer_layout() |
| **Page Generation** | phpgen_version38.py | 5979-6300 | generate_page() |
| **Home Page** | phpgen_version38.py | 6053-6079 | generate_page() - index section |
| **Contact Page** | phpgen_version38.py | 4622-4815 | generate_contact_page() |
| **Blog Pages** | phpgen_version38.py | 6444-6700 | generate_blog_page(), generate_blog_main_page() |
| **Database Load** | phpgen_version38.py | 3558-3648 | load_database() |

---

## 12. TRANSLATION WORKFLOW EXAMPLE

### Example: German Restaurant Website

**Input**: "Create a restaurant website for Berlin, Germany in German"

**Processing**:
```
1. Create Blueprint
   ├─ country: "Germany" (detected)
   ├─ language: "German" (from get_language_for_country("Germany"))
   ├─ theme: "Restaurant" (detected from context)
   └─ Store in blueprint
   
2. Generate Header/Footer
   ├─ Call API: generate_theme_content_via_api("Restaurant", "menu_content", 1)
   │   └─ Prompt includes: "Language: German"
   │   └─ Returns: {"home": "Startseite", "services": "Dienstleistungen", ...}
   │
   └─ Call API: generate_theme_content_via_api("Restaurant", "footer_content", 1)
       └─ Prompt includes: "Language: German"
       └─ Returns: {"tagline": "Ihr vertrauter Restaurant-Partner", ...}
   
3. Generate Home Page
   ├─ language_requirement = "...EXCLUSIVELY in German language..."
   ├─ Call API with prompt containing language_requirement
   └─ Returns: HTML with all German text
   
4. Generate Contact Page
   ├─ Call API: "contact_page_content" with language: German
   └─ Returns: Form fields and labels in German
   
5. Generate Blog Articles
   ├─ Call API: "blog_article_full" (article 1-6) with language: German
   └─ Returns: 6 articles, all content in German
   
6. Output
   └─ Complete PHP website with all content in German
      ├─ Navigation: "Startseite", "Über uns", "Dienstleistungen", "Blog", "Kontakt"
      ├─ Forms: "Ihr Name", "Ihre E-Mail", "Telefonnummer", "Ihre Nachricht"
      ├─ Buttons: "Kontaktieren Sie uns heute", "Mehr erfahren"
      └─ All content fully translated to German
```

---

## 13. IMPORTANT NOTES

### Static Site Generation
- Translations are generated **once** at site creation time
- Not dynamic or per-request translation
- All content is hardcoded into PHP files
- No runtime language detection or switching

### Language Scope
- Content is generated in **one language only** per site
- Cannot create multilingual sites (would require multiple generations)
- Language set at blueprint creation is used for entire site

### API Dependency
- All translations depend on OpenRouter API being available
- Requires internet connection during generation
- Fallback hardcoded values for critical components

### Caching
- Content is cached during single generation session
- Cache key includes language, theme, and content type
- Prevents redundant API calls within same session

