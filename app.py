from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import random
import urllib.parse
import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import platform

# Initialize the Flask app
app = Flask(__name__)

# Timeout configuration
SCRAPING_TIMEOUT = 240  # 4 minutes total timeout
INDIVIDUAL_SEARCH_TIMEOUT = 60  # 1 minute per search

class TimeoutException(Exception):
    pass

# Health check endpoint for Render
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "LinkedIn Scraper API is running"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/test-google', methods=['GET'])
def test_google_access():
    """Test endpoint to check Google access from production"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get("https://www.google.com")
        time.sleep(3)
        
        result = {
            "url": driver.current_url,
            "title": driver.title,
            "blocked": is_captcha_or_blocked(driver),
            "has_search_box": len(driver.find_elements(By.NAME, "q")) > 0,
            "page_length": len(driver.page_source)
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

# Define the /scrape endpoint with timeout protection
@app.route('/scrape', methods=['POST'])
def scrape_linkedin_profiles():
    try:
        data = request.get_json()
        if not data or 'company' not in data:
            return jsonify({"error": "Company name not provided"}), 400
        
        company_name = data['company']
        row_number = data.get('row_number', 2)
        
        # Use thread pool for timeout control (cross-platform)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(scrape_with_selenium, company_name, row_number)
            try:
                result = future.result(timeout=SCRAPING_TIMEOUT)
                return jsonify(result)
            except FutureTimeoutError:
                return jsonify({
                    "error": "Scraping timeout - operation took too long",
                    "excel_data": [{
                        "row_number": row_number,
                        "Company Name": company_name,
                        "Status": "Timeout Error",
                        **{f"SDE {i} Name": "" for i in range(1, 6)},
                        **{f"SDE {i} URL": "" for i in range(1, 6)},
                        **{f"HR {i} Name": "" for i in range(1, 3)},
                        **{f"HR {i} URL": "" for i in range(1, 3)}
                    }]
                }), 200
                
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({
            "error": str(e),
            "excel_data": [{
                "row_number": data.get('row_number', 2) if data else 2,
                "Company Name": data.get('company', '') if data else '',
                "Status": "Error",
                **{f"SDE {i} Name": "" for i in range(1, 6)},
                **{f"SDE {i} URL": "" for i in range(1, 6)},
                **{f"HR {i} Name": "" for i in range(1, 3)},
                **{f"HR {i} URL": "" for i in range(1, 3)}
            }]
        }), 200

def scrape_with_selenium(company_name, row_number):
    """Main scraping function with multiple fallback strategies"""
    
    # Try multiple approaches in order of preference
    strategies = [
        ("google_with_stealth", "Google with stealth mode"),
        ("duckduckgo", "DuckDuckGo search"),
        ("bing", "Bing search"),
        ("google_basic", "Google basic (fallback)")
    ]
    
    for strategy_name, strategy_desc in strategies:
        print(f"\n=== TRYING STRATEGY: {strategy_desc} ===")
        
        try:
            if strategy_name == "google_with_stealth":
                result = scrape_with_stealth_google(company_name, row_number)
            elif strategy_name == "duckduckgo":
                result = scrape_with_duckduckgo(company_name, row_number)
            elif strategy_name == "bing":
                result = scrape_with_bing(company_name, row_number)
            else:  # google_basic
                result = scrape_with_basic_google(company_name, row_number)
            
            # Check if we got results
            if result and result.get("debug", {}).get("sde_profiles_found", 0) > 0:
                print(f"SUCCESS with {strategy_desc}")
                return result
            else:
                print(f"No results with {strategy_desc}, trying next strategy...")
                
        except Exception as e:
            print(f"Strategy {strategy_desc} failed: {e}")
            continue
    
    # If all strategies fail, return empty result
    print("All strategies failed, returning empty result")
    return create_empty_result(company_name, row_number, "All search strategies failed")

def scrape_with_stealth_google(company_name, row_number):
    """Advanced stealth mode for Google"""
    options = webdriver.ChromeOptions()
    
    # Stealth options
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Anti-detection measures
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Additional stealth options
    options.add_argument('--disable-extensions-file-access-check')
    options.add_argument('--disable-extensions-http-throttling')
    options.add_argument('--disable-client-side-phishing-detection')
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        # Execute stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        return perform_search_operations(driver, company_name, row_number, "google")
        
    except Exception as e:
        print(f"Stealth Google failed: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def scrape_with_duckduckgo(company_name, row_number):
    """Use DuckDuckGo as alternative search engine"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        return perform_search_operations(driver, company_name, row_number, "duckduckgo")
        
    except Exception as e:
        print(f"DuckDuckGo failed: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def scrape_with_bing(company_name, row_number):
    """Use Bing as alternative search engine"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        return perform_search_operations(driver, company_name, row_number, "bing")
        
    except Exception as e:
        print(f"Bing failed: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def scrape_with_basic_google(company_name, row_number):
    """Basic Google scraping as last resort"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        return perform_search_operations(driver, company_name, row_number, "google")
        
    except Exception as e:
        print(f"Basic Google failed: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def perform_search_operations(driver, company_name, row_number, search_engine):
    """Perform actual search operations based on search engine"""
    
    # Define queries
    sde_query = f'site:linkedin.com/in/ "Software Engineer" "{company_name}" "India"'
    hr_queries = [
        f'site:linkedin.com/in/ "Talent Acquisition" "{company_name}" "India"',
        f'site:linkedin.com/in/ "HR" "{company_name}" "India"'
    ]
    
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    wait = WebDriverWait(driver, 15)
    
    try:
        # Navigate to search engine
        if search_engine == "duckduckgo":
            driver.get("https://duckduckgo.com")
            time.sleep(3)
        elif search_engine == "bing":
            driver.get("https://www.bing.com")
            time.sleep(3)
        else:  # google
            driver.get("https://www.google.com")
            time.sleep(3)
            
            # Handle Google consent
            handle_cookie_consent(driver, wait)
        
        # Check for blocking
        if search_engine == "google" and is_captcha_or_blocked(driver):
            print(f"{search_engine.upper()} is blocked")
            return None
        
        print(f"Successfully accessed {search_engine.upper()}")
        
        # Search for SDE profiles
        print("=== SEARCHING FOR SOFTWARE ENGINEERS ===")
        if search_engine == "duckduckgo":
            sde_profiles = search_duckduckgo(driver, wait, sde_query, 5)
        elif search_engine == "bing":
            sde_profiles = search_bing(driver, wait, sde_query, 5)
        else:
            sde_profiles = quick_scrape_google(driver, wait, sde_query, 5)
        
        time.sleep(2)
        
        # Search for HR profiles
        print("=== SEARCHING FOR HR/TALENT ACQUISITION ===")
        hr_profiles = []
        
        for hr_query in hr_queries:
            if len(hr_profiles) >= 2:
                break
                
            print(f"Trying HR query: {hr_query}")
            if search_engine == "duckduckgo":
                hr_results = search_duckduckgo(driver, wait, hr_query, 2)
            elif search_engine == "bing":
                hr_results = search_bing(driver, wait, hr_query, 2)
            else:
                hr_results = quick_scrape_google(driver, wait, hr_query, 2)
            
            for profile in hr_results:
                if len(hr_profiles) >= 2:
                    break
                if not any(existing['url'] == profile['url'] for existing in hr_profiles):
                    hr_profiles.append(profile)
            
            time.sleep(1)
        
        # Format response
        excel_formatted = format_for_excel(company_name, row_number, sde_profiles, hr_profiles)
        
        return {
            "excel_data": excel_formatted,
            "debug": {
                "search_engine_used": search_engine,
                "sde_profiles_found": len(sde_profiles),
                "hr_profiles_found": len(hr_profiles),
                "sde_profiles": sde_profiles,
                "hr_profiles": hr_profiles
            }
        }
        
    except Exception as e:
        print(f"Search operations failed for {search_engine}: {e}")
        return None

def search_duckduckgo(driver, wait, query, max_results):
    """Search using DuckDuckGo"""
    try:
        # Find search box
        search_box = wait.until(EC.presence_of_element_located((By.ID, "searchbox_input")))
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)
        time.sleep(3)
        
        # Find results
        results = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='result']")[:max_results * 2]
        
        profiles = []
        seen_urls = set()
        
        for result in results:
            if len(profiles) >= max_results:
                break
                
            if 'linkedin.com' not in result.get_attribute('outerHTML').lower():
                continue
            
            name, url = extract_profile_info_generic(result)
            if url and url not in seen_urls:
                profiles.append({"name": name, "url": url})
                seen_urls.add(url)
        
        return profiles
        
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
        return []

def search_bing(driver, wait, query, max_results):
    """Search using Bing"""
    try:
        # Find search box
        search_box = wait.until(EC.presence_of_element_located((By.ID, "sb_form_q")))
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)
        time.sleep(3)
        
        # Find results
        results = driver.find_elements(By.CSS_SELECTOR, ".b_algo")[:max_results * 2]
        
        profiles = []
        seen_urls = set()
        
        for result in results:
            if len(profiles) >= max_results:
                break
                
            if 'linkedin.com' not in result.get_attribute('outerHTML').lower():
                continue
            
            name, url = extract_profile_info_generic(result)
            if url and url not in seen_urls:
                profiles.append({"name": name, "url": url})
                seen_urls.add(url)
        
        return profiles
        
    except Exception as e:
        print(f"Bing search error: {e}")
        return []

def extract_profile_info_generic(result_element):
    """Generic profile extraction that works across search engines"""
    # Extract URL
    linkedin_url = None
    links = result_element.find_elements(By.TAG_NAME, 'a')
    
    for link in links:
        href = link.get_attribute('href')
        if href and 'linkedin.com/in/' in href:
            linkedin_url = clean_google_url(href) or href
            break
    
    if not linkedin_url:
        return None, None
    
    # Extract name from various elements
    name_selectors = ['h3', 'h2', '.b_title', 'cite + h3', 'a h3']
    profile_name = None
    
    for selector in name_selectors:
        try:
            elements = result_element.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = element.text.strip()
                if text and 3 <= len(text) <= 100 and 'linkedin' not in text.lower():
                    profile_name = re.sub(r'\s+', ' ', text)
                    break
            if profile_name:
                break
        except:
            continue
    
    # Fallback name from URL
    if not profile_name and linkedin_url:
        url_parts = linkedin_url.split('/')
        if len(url_parts) > 4:
            profile_name = url_parts[4].replace('-', ' ').title()
        else:
            profile_name = "LinkedIn Profile"
    
    return profile_name, linkedin_url

def create_empty_result(company_name, row_number, status):
    """Create empty result structure"""
    return {
        "excel_data": [{
            "row_number": row_number,
            "Company Name": company_name,
            "Status": status,
            **{f"SDE {i} Name": "" for i in range(1, 6)},
            **{f"SDE {i} URL": "" for i in range(1, 6)},
            **{f"HR {i} Name": "" for i in range(1, 3)},
            **{f"HR {i} URL": "" for i in range(1, 3)}
        }],
        "debug": {
            "sde_profiles_found": 0,
            "hr_profiles_found": 0,
            "sde_profiles": [],
            "hr_profiles": []
        }
    }

def format_for_excel(company_name, row_number, sde_profiles, hr_profiles):
    """Format the scraped data for Excel import"""
    excel_row = {
        "row_number": row_number,
        "Company Name": company_name,
        "Status": "Completed"
    }
    
    # Add SDE profiles (up to 5)
    for i in range(5):
        sde_num = i + 1
        if i < len(sde_profiles):
            clean_name = clean_profile_name(sde_profiles[i]['name'])
            excel_row[f"SDE {sde_num} Name"] = clean_name
            excel_row[f"SDE {sde_num} URL"] = sde_profiles[i]['url']
        else:
            excel_row[f"SDE {sde_num} Name"] = ""
            excel_row[f"SDE {sde_num} URL"] = ""
    
    # Add HR profiles (up to 2)
    for i in range(2):
        hr_num = i + 1
        if i < len(hr_profiles):
            clean_name = clean_profile_name(hr_profiles[i]['name'])
            excel_row[f"HR {hr_num} Name"] = clean_name
            excel_row[f"HR {hr_num} URL"] = hr_profiles[i]['url']
        else:
            excel_row[f"HR {hr_num} Name"] = ""
            excel_row[f"HR {hr_num} URL"] = ""
    
    return [excel_row]

def clean_profile_name(name):
    """Clean profile name by removing job titles and extra information"""
    if not name:
        return ""
    
    patterns_to_remove = [
        r' - .*',  r' \| .*',  r' @ .*',   r' at .*',  r'\(.*\)',
    ]
    
    cleaned_name = name
    for pattern in patterns_to_remove:
        cleaned_name = re.sub(pattern, '', cleaned_name, flags=re.IGNORECASE)
    
    cleaned_name = ' '.join(cleaned_name.split())
    
    if len(cleaned_name.strip()) < 3:
        return name.strip()
    
    return cleaned_name.strip()

def handle_cookie_consent(driver, wait):
    """Handle Google's cookie consent popup quickly"""
    try:
        consent_selectors = ['//button[@id="L2AGLb"]', '//button[contains(text(), "Accept")]']
        
        for selector in consent_selectors:
            try:
                consent_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                consent_button.click()
                time.sleep(1)
                return True
            except:
                continue
        return False
    except:
        return False

def is_captcha_or_blocked(driver):
    """Enhanced blocking detection with detailed logging"""
    try:
        page_text = driver.page_source.lower()
        page_title = driver.title.lower()
        current_url = driver.current_url.lower()
        
        blocking_indicators = [
            "unusual traffic",
            "captcha", 
            "i'm not a robot",
            "verify you are human",
            "recaptcha",
            "our systems have detected",
            "automated queries",
            "robot",
            "suspicious activity"
        ]
        
        # Check page content
        for indicator in blocking_indicators:
            if indicator in page_text:
                print(f"BLOCKING DETECTED: Found '{indicator}' in page content")
                return True
            if indicator in page_title:
                print(f"BLOCKING DETECTED: Found '{indicator}' in page title")
                return True
        
        # Check URL for blocking patterns
        blocking_url_patterns = [
            "sorry.google.com",
            "ipv4.google.com",
            "ipv6.google.com",
            "consent.google.com"
        ]
        
        for pattern in blocking_url_patterns:
            if pattern in current_url:
                print(f"BLOCKING DETECTED: URL contains '{pattern}'")
                return True
        
        # Check for absence of search elements (indicating a blocked page)
        try:
            search_elements = driver.find_elements(By.NAME, "q")
            if not search_elements:
                print("POTENTIAL BLOCKING: No search box found")
                # Don't return True here as this might be a false positive
        except:
            pass
        
        print("No blocking detected")
        return False
        
    except Exception as e:
        print(f"Error checking for blocking: {e}")
        return False

def clean_google_url(url):
    """Clean Google redirect URLs"""
    if not url or 'linkedin.com/in/' not in url:
        return None
    
    if '/url?' not in url:
        return url
    
    try:
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        for param in ['url', 'q']:
            if param in query_params:
                decoded_url = urllib.parse.unquote(query_params[param][0])
                if 'linkedin.com/in/' in decoded_url:
                    return decoded_url.split('&')[0]  # Remove additional params
    except:
        pass
    
    return None

def extract_profile_info(result_element):
    """Extract both name and URL from result element"""
    # Extract URL first
    linkedin_url = None
    links = result_element.find_elements(By.TAG_NAME, 'a')
    
    for link in links:
        href = link.get_attribute('href')
        cleaned_url = clean_google_url(href)
        if cleaned_url:
            linkedin_url = cleaned_url.split('?')[0].rstrip('/')
            break
    
    if not linkedin_url:
        return None, None
    
    # Extract name
    name_selectors = ['h3', 'h3 span', '.LC20lb', '.DKV0Md']
    profile_name = None
    
    for selector in name_selectors:
        try:
            elements = result_element.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = element.text.strip()
                if text and 3 <= len(text) <= 100 and 'linkedin' not in text.lower():
                    profile_name = re.sub(r'\s+', ' ', text)
                    break
            if profile_name:
                break
        except:
            continue
    
    # Fallback name from URL
    if not profile_name and linkedin_url:
        url_parts = linkedin_url.split('/')
        if len(url_parts) > 4:
            profile_name = url_parts[4].replace('-', ' ').title()
        else:
            profile_name = "LinkedIn Profile"
    
    return profile_name, linkedin_url

def quick_scrape_google(driver, wait, query, max_results):
    """Optimized scraping with enhanced debugging and error handling"""
    try:
        print(f"Starting search for: {query}")
        driver.get("https://www.google.com")
        time.sleep(2)
        
        # Check current page content
        current_url = driver.current_url
        page_title = driver.title
        print(f"Current URL: {current_url}")
        print(f"Page title: {page_title}")
        
        # Check if we're blocked before searching
        if is_captcha_or_blocked(driver):
            print("BLOCKED: Detected blocking before search")
            return []
        
        # Find and use search box with better error handling
        search_box = None
        search_selectors = [
            (By.NAME, "q"),
            (By.CSS_SELECTOR, "textarea[name='q']"),
            (By.CSS_SELECTOR, "input[name='q']"),
            (By.CSS_SELECTOR, "textarea[title='Search']"),
            (By.CSS_SELECTOR, "input[title='Search']")
        ]
        
        for by, selector in search_selectors:
            try:
                search_box = wait.until(EC.presence_of_element_located((by, selector)))
                print(f"Found search box with selector: {selector}")
                break
            except:
                continue
        
        if not search_box:
            print("ERROR: Could not find search box")
            return []
        
        # Perform search with human-like typing
        search_box.clear()
        time.sleep(0.5)
        
        # Type slowly to avoid detection
        for char in query:
            search_box.send_keys(char)
            time.sleep(random.uniform(0.05, 0.1))
        
        time.sleep(1)
        search_box.send_keys(Keys.RETURN)
        time.sleep(3)
        
        # Check URL after search
        search_url = driver.current_url
        print(f"Search URL: {search_url}")
        
        # Enhanced blocking check
        if is_captcha_or_blocked(driver):
            print("BLOCKED: Detected blocking after search")
            print("Page source snippet:", driver.page_source[:500])
            return []
        
        # Wait for results to load
        time.sleep(2)
        
        # Try multiple result selectors with detailed logging
        selectors = [
            "div.g",           # Standard results
            ".tF2Cxc",         # New Google layout  
            "div[data-ved]",   # Alternative
            ".yuRUbf",         # Result wrapper
            ".MjjYud",         # Another class
            "div.kvH3mc"       # Alternative
        ]
        
        search_results = []
        used_selector = None
        
        for selector in selectors:
            try:
                results = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"Selector '{selector}': found {len(results)} elements")
                
                if results:
                    # Check if any contain LinkedIn
                    linkedin_count = 0
                    for result in results[:5]:
                        if 'linkedin.com' in result.get_attribute('outerHTML').lower():
                            linkedin_count += 1
                    
                    print(f"LinkedIn results found: {linkedin_count}")
                    
                    if linkedin_count > 0:
                        search_results = results[:max_results * 3]  # Get more for filtering
                        used_selector = selector
                        break
            except Exception as e:
                print(f"Selector '{selector}' failed: {e}")
                continue
        
        if not search_results:
            print("ERROR: No search results found with any selector")
            # Debug: Print page source snippet
            page_source = driver.page_source
            print("Page source length:", len(page_source))
            if len(page_source) > 0:
                print("Page source snippet:", page_source[:1000])
            return []
        
        print(f"Processing {len(search_results)} results with selector '{used_selector}'")
        
        profiles = []
        seen_urls = set()
        
        for i, result in enumerate(search_results):
            if len(profiles) >= max_results:
                break
                
            print(f"Processing result {i+1}")
            
            # Check for LinkedIn content
            result_html = result.get_attribute('outerHTML')
            if 'linkedin.com' not in result_html.lower():
                print(f"  No LinkedIn content in result {i+1}")
                continue
            
            name, url = extract_profile_info(result)
            print(f"  Extracted: name='{name}', url='{url}'")
            
            if not url:
                print(f"  No URL found in result {i+1}")
                continue
                
            if url in seen_urls:
                print(f"  Duplicate URL: {url}")
                continue
            
            profiles.append({"name": name, "url": url})
            seen_urls.add(url)
            print(f"  ✓ Added profile: {name}")
        
        print(f"Final result: {len(profiles)} profiles found")
        return profiles
                
    except Exception as e:
        print(f"Quick scrape error: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)