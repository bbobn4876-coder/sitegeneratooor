# PHPGEN v38 - Quick Reference Guide

## Finding Things in the Code

### Translation & Language
- **Language Detection**: Lines 3693-3695
  - Extract language/country/theme from user input via regex
  
- **Language Mapping**: Lines 350-458
  - Function: `get_language_for_country(country)`
  - Maps 40+ European countries to languages
  
- **Blueprint Storage**: Line 3878
  - `self.blueprint["language"] = language`
  - Used throughout generation: `self.blueprint.get('language', 'English')`

### Page Sections & Their Translations

| Section | Prompt Type | Lines | API Call |
|---------|-------------|-------|----------|
| Navigation Menu | menu_content | 1255-1276 | Line 3919 |
| Footer | footer_content | 1188-1215 | Line 4017 |
| Our Process | process_steps | 828-842 | Used in home page |
| Why Choose Us | approach_content | 861-883 | Used in home page |
| Blog Section | blog_section_headers | 1310-1325 | Line 2803 |
| Contact Form | contact_page_content | 1111-1144 | Line 4472 |
| Blog Articles | blog_article_full | 1217-1240 | Line 1334 |

### API Content Types (Complete List)
All defined in `generate_theme_content_via_api()` function (lines 794-1440)

**Important**: Every prompt includes this critical language instruction:
```
CRITICAL LANGUAGE REQUIREMENT: You MUST generate ALL content EXCLUSIVELY 
in {language} language...
```
(See line 825)

### Main Workflow Entry Point
- **User Input**: Lines 7133-7180
- **Main Function**: `generate_website()` (Line 7031)
- **Steps**: 1. Load DB, 2. Create Blueprint, 3. Header/Footer, 4. Images, 5. Pages, 6. Blog, 7. Extra

### Key Classes & Methods

```python
# Main Class
class PHPWebsiteGenerator:  # Line 318
    
    # Language Methods
    def get_language_for_country(self, country)  # Line 350
    
    # API Methods
    def call_api(self, prompt, max_tokens, model)  # Line 460
    def generate_theme_content_via_api(self, theme, content_type, num_items)  # Line 794
    
    # Setup Methods
    def load_database(self, data_dir)  # Line 3558
    def create_blueprint(self, user_prompt, site_name)  # Line 3686
    def generate_header_footer(self)  # Line 3895
    
    # Page Generation
    def generate_page(self, page_name, output_dir)  # Line 5979
    def generate_contact_page(self, output_dir)  # Line 4622
    def generate_blog_page(self, page_name, output_dir)  # Line 6444
    def generate_blog_main_page(self, output_dir)  # Line 6634
    
    # Main Entry
    def generate_website(self, user_prompt, site_name, ...)  # Line 7031
```

## How Translations Flow

1. **User Input** (lines 7133-7180)
   - User describes site, mentions country/language
   
2. **Extract Information** (lines 3693-3695)
   - Regex search for "language:", "country:", "theme:"
   
3. **Determine Language** (lines 3836-3841)
   - If explicit: use it
   - Else: call `get_language_for_country(country)`
   
4. **Store in Blueprint** (line 3878)
   - `blueprint["language"] = language`
   
5. **Use in API Calls** (line 807)
   - `language = self.blueprint.get('language', 'English')`
   - Append to every prompt (line 825)
   
6. **Generate Content** (line 794+)
   - API generates JSON with translated content
   - Content cached by key: `{theme}_{type}_{items}_{language}`
   
7. **Embed in PHP** (throughout)
   - Translated strings inserted directly into PHP files

## Finding Specific Content Types

### To find the prompt for a content type:
```bash
grep -n "elif content_type == \"CONTENT_TYPE_NAME\"" phpgen_version38.py
```

Examples:
```bash
grep -n "elif content_type == \"menu_content\"" phpgen_version38.py
# Returns: 1255 (for the prompt definition)

grep -n "elif content_type == \"contact_page_content\"" phpgen_version38.py
# Returns: 1111
```

### To find where a content type is used:
```bash
grep -n "generate_theme_content_via_api.*menu_content" phpgen_version38.py
# Returns: 3919 (where menu translations are fetched)
```

## Important Configuration

### API Settings (Line 319-327)
- URL: https://openrouter.ai/api/v1/chat/completions
- Model: google/gemini-2.5-pro
- Max tokens: 16000
- Retry logic: 5 attempts (lines 482+)

### ByteDance Image API (Line 340-348)
- Model: seedream-4-0-250828
- Key in code at line 322

### Cache Key Format (Line 810)
```python
cache_key = f"{theme}_{content_type}_{num_items}_{language}"
```

## Debugging Tips

### To trace language through a page generation:
1. Check user input extraction (lines 3693-3695)
2. Check blueprint creation (line 3878)
3. Check API call construction (line 825)
4. Check generated content (output PHP file)

### To find all API calls for a language:
```bash
grep -n "language_instruction\|language_requirement" phpgen_version38.py
```

### To see all supported languages:
Lines 355-450 - country_language_map dictionary

## Pages Generated

### Landing Site (if site_type == "landing")
- index.php (home)
- thanks_you.php
- privacy.php, terms.php, cookie.php

### Multipage Site (if site_type == "multipage")
- index.php (home)
- company.php
- services.php
- contact.php
- blog.php (main blog page)
- blog1.php - blog6.php (individual articles)
- privacy.php, terms.php, cookie.php
- thanks_you.php

## Blueprint Keys Used for Translations

```python
self.blueprint.get('language', 'English')     # Language
self.blueprint.get('theme', 'business')       # Business type
self.blueprint.get('country', 'USA')          # Country
self.blueprint.get('site_name')               # Site name
self.blueprint.get('color_scheme')            # Colors
self.blueprint.get('contact_data')            # Contact info
```

## For Adding New Languages

1. Add country-language mapping to `country_language_map` (line 355+)
2. The system will automatically use that language for API calls
3. No other changes needed - API handles the translation

Example:
```python
# Add to country_language_map dictionary
'newcountry': 'NewLanguage', 'new_country_in_russian': 'NewLanguage',
```

## Common Issues & Solutions

### Problem: Content in English instead of target language
- Check: user input was parsed correctly (print blueprint["language"])
- Check: API was called with language requirement (search for language_instruction)
- Check: API returned valid JSON (check error logs)

### Problem: Menu items not translated
- Check: menu_content API call at line 3919
- Check: fallback values at line 3923-3929
- Verify: language was in blueprint before header/footer generation

### Problem: Contact form labels in English
- Check: contact_page_content at line 4472
- Check: fallback at line 4475
- Verify: language passed to generate_theme_content_via_api

---

For detailed information, see: TRANSLATION_ARCHITECTURE.md
