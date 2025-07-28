from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import random
import urllib.parse
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json

app = Flask(__name__)

# Configuration
SCRAPING_TIMEOUT = 200
SEARCH_TIMEOUT = 45

# User agents pool for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "LinkedIn Scraper API is running"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/test-google', methods=['GET'])
def test_google_access():
    """Enhanced test endpoint with multiple strategies"""
    strategies = ["direct", "with_delay", "alternative_search"]
    results = {}
    
    for strategy in strategies:
        driver = None
        try:
            print(f"Testing strategy: {strategy}")
            driver = create_ultra_stealth_driver()
            
            if strategy == "direct":
                driver.get("https://www.google.com")
                time.sleep(3)
            elif strategy == "with_delay":
                driver.get("https://www.google.com")
                time.sleep(random.uniform(5, 8))
                simulate_human_behavior(driver)
            else:  # alternative_search
                # Try different Google domains
                domains = ["https://www.google.com", "https://www.google.co.in"]
                for domain in domains:
                    try:
                        driver.get(domain)
                        time.sleep(4)
                        break
                    except:
                        continue
            
            results[strategy] = {
                "url": driver.current_url,
                "title": driver.title,
                "blocked": is_blocked_advanced(driver),
                "has_search_box": len(driver.find_elements(By.NAME, "q")) > 0,
                "page_length": len(driver.page_source)
            }
            
        except Exception as e:
            results[strategy] = {"error": str(e)}
        finally:
            cleanup_driver(driver)
    
    return jsonify(results), 200

@app.route('/scrape', methods=['POST'])
def scrape_linkedin_profiles():
    try:
        data = request.get_json()
        if not data or 'company' not in data:
            return jsonify({"error": "Company name not provided"}), 400
        
        company_name = data['company']
        row_number = data.get('row_number', 2)
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(scrape_with_multiple_strategies, company_name, row_number)
            try:
                result = future.result(timeout=SCRAPING_TIMEOUT)
                return jsonify(result)
            except FutureTimeoutError:
                return jsonify(create_timeout_result(company_name, row_number)), 200
                
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify(create_error_result(data, str(e))), 200

def create_ultra_stealth_driver():
    """Create maximum stealth Chrome driver"""
    options = webdriver.ChromeOptions()
    
    # Core stealth options
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # Advanced anti-detection
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Randomize user agent
    user_agent = random.choice(USER_AGENTS)
    options.add_argument(f'--user-agent={user_agent}')
    
    # Randomize window size
    width = random.randint(1200, 1920)
    height = random.randint(800, 1080)
    options.add_argument(f'--window-size={width},{height}')
    
    # Additional stealth measures
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-extensions')
    options.add_argument('--no-first-run')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-sync')
    options.add_argument('--disable-background-networking')
    
    # Memory optimization
    options.add_argument('--memory-pressure-off')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    
    # Proxy rotation (if needed)
    # options.add_argument('--proxy-server=your-proxy-here')
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        # Execute advanced stealth scripts
        stealth_scripts = [
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
            "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})",
            "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})",
            "Object.defineProperty(navigator, 'deviceMemory', {get: () => 8})",
            "Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4})",
            "window.chrome = {runtime: {}}",
            "Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})})"
        ]
        
        for script in stealth_scripts:
            try:
                driver.execute_script(script)
            except:
                pass
        
        # Set realistic timeouts
        driver.set_page_load_timeout(SEARCH_TIMEOUT)
        driver.implicitly_wait(8)
        
        return driver
    except Exception as e:
        print(f"Failed to create driver: {e}")
        raise

def simulate_human_behavior(driver):
    """Simulate human-like behavior on the page"""
    try:
        # Random mouse movements
        actions = ActionChains(driver)
        
        # Move to random positions
        for _ in range(3):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            actions.move_by_offset(x, y)
            time.sleep(random.uniform(0.1, 0.3))
        
        actions.perform()
        
        # Random scroll
        driver.execute_script(f"window.scrollTo(0, {random.randint(100, 300)})")
        time.sleep(random.uniform(1, 2))
        
    except:
        pass

def scrape_with_multiple_strategies(company_name, row_number):
    """Try multiple approaches to avoid detection"""
    
    strategies = [
        {"name": "stealth_search", "delay": (3, 6)},
        {"name": "slow_search", "delay": (8, 12)},
        {"name": "alternative_domain", "delay": (5, 8)},
    ]
    
    for strategy in strategies:
        print(f"\n=== TRYING STRATEGY: {strategy['name']} ===")
        
        try:
            if strategy['name'] == "stealth_search":
                result = stealth_search_approach(company_name, row_number, strategy['delay'])
            elif strategy['name'] == "slow_search":
                result = slow_search_approach(company_name, row_number, strategy['delay'])
            else:  # alternative_domain
                result = alternative_domain_approach(company_name, row_number, strategy['delay'])
            
            if result and result.get("debug", {}).get("sde_profiles_found", 0) > 0:
                print(f"SUCCESS with {strategy['name']}")
                return result
            else:
                print(f"No results with {strategy['name']}")
                
        except Exception as e:
            print(f"Strategy {strategy['name']} failed: {e}")
            continue
    
    print("All strategies failed")
    return create_blocked_result(company_name, row_number)

def stealth_search_approach(company_name, row_number, delay_range):
    """Ultra stealth search with maximum anti-detection"""
    driver = None
    try:
        driver = create_ultra_stealth_driver()
        
        # Navigate with random delay
        driver.get("https://www.google.com")
        time.sleep(random.uniform(*delay_range))
        
        # Simulate human behavior
        simulate_human_behavior(driver)
        
        # Handle consent with delay
        handle_consent_advanced(driver)
        
        if is_blocked_advanced(driver):
            print("Blocked on initial access")
            return None
        
        # Wait longer before searching
        time.sleep(random.uniform(3, 6))
        
        # Search with maximum stealth
        sde_profiles = perform_stealth_search(driver, company_name, "SDE", 5)
        
        if sde_profiles:
            time.sleep(random.uniform(8, 15))  # Long delay between searches
            hr_profiles = perform_stealth_search(driver, company_name, "HR", 2)
        else:
            hr_profiles = []
        
        return format_results(company_name, row_number, sde_profiles, hr_profiles, "stealth_search")
        
    except Exception as e:
        print(f"Stealth search failed: {e}")
        return None
    finally:
        cleanup_driver(driver)

def slow_search_approach(company_name, row_number, delay_range):
    """Very slow, human-like search approach"""
    driver = None
    try:
        driver = create_ultra_stealth_driver()
        
        # Very slow navigation
        driver.get("https://www.google.com")
        time.sleep(random.uniform(*delay_range))
        
        # Extended human simulation
        for _ in range(3):
            simulate_human_behavior(driver)
            time.sleep(random.uniform(2, 4))
        
        handle_consent_advanced(driver)
        
        if is_blocked_advanced(driver):
            return None
        
        # Search with very long delays
        sde_profiles = perform_ultra_slow_search(driver, company_name, "SDE", 3)  # Reduced count
        
        if sde_profiles:
            time.sleep(random.uniform(15, 25))  # Very long delay
            hr_profiles = perform_ultra_slow_search(driver, company_name, "HR", 1)  # Reduced count
        else:
            hr_profiles = []
        
        return format_results(company_name, row_number, sde_profiles, hr_profiles, "slow_search")
        
    except Exception as e:
        print(f"Slow search failed: {e}")
        return None
    finally:
        cleanup_driver(driver)

def alternative_domain_approach(company_name, row_number, delay_range):
    """Try different Google domains"""
    domains = ["https://www.google.co.in", "https://www.google.com"]
    
    for domain in domains:
        driver = None
        try:
            print(f"Trying domain: {domain}")
            driver = create_ultra_stealth_driver()
            
            driver.get(domain)
            time.sleep(random.uniform(*delay_range))
            
            simulate_human_behavior(driver)
            handle_consent_advanced(driver)
            
            if is_blocked_advanced(driver):
                print(f"Blocked on {domain}")
                continue
            
            # Quick search to test
            sde_profiles = perform_stealth_search(driver, company_name, "SDE", 5)
            
            if sde_profiles:
                time.sleep(random.uniform(8, 12))
                hr_profiles = perform_stealth_search(driver, company_name, "HR", 1)
                return format_results(company_name, row_number, sde_profiles, hr_profiles, f"domain_{domain}")
                
        except Exception as e:
            print(f"Domain {domain} failed: {e}")
            continue
        finally:
            cleanup_driver(driver)
    
    return None

def perform_stealth_search(driver, company_name, role_type, max_results):
    """Perform search with maximum stealth"""
    try:
        if role_type == "SDE":
            query = f'site:linkedin.com/in/ "Software Engineer" "{company_name}" India'
        else:
            query = f'site:linkedin.com/in/ ("HR" OR "Talent Acquisition") "{company_name}" India'
        
        print(f"Executing stealth search: {query}")
        
        # Find search box with multiple attempts
        wait = WebDriverWait(driver, 20)
        search_box = None
        
        selectors = [
            (By.NAME, "q"),
            (By.CSS_SELECTOR, "textarea[name='q']"),
            (By.CSS_SELECTOR, "input[name='q']")
        ]
        
        for by, selector in selectors:
            try:
                search_box = wait.until(EC.presence_of_element_located((by, selector)))
                break
            except:
                continue
        
        if not search_box:
            print("Could not find search box")
            return []
        
        # Clear with human-like behavior
        search_box.click()
        time.sleep(random.uniform(0.5, 1))
        search_box.clear()
        time.sleep(random.uniform(0.3, 0.8))
        
        # Type very slowly with random pauses
        for i, char in enumerate(query):
            search_box.send_keys(char)
            # Random pause every few characters
            if i % random.randint(5, 10) == 0:
                time.sleep(random.uniform(0.1, 0.3))
            else:
                time.sleep(random.uniform(0.03, 0.08))
        
        # Wait before pressing enter
        time.sleep(random.uniform(1, 2))
        search_box.send_keys(Keys.RETURN)
        
        # Wait for results with longer timeout
        time.sleep(random.uniform(5, 8))
        
        # Check for blocking after search
        if is_blocked_advanced(driver):
            print("Blocked after search")
            return []
        
        # Extract results with enhanced selectors
        return extract_results_advanced(driver, max_results)
        
    except Exception as e:
        print(f"Stealth search error: {e}")
        return []

def perform_ultra_slow_search(driver, company_name, role_type, max_results):
    """Ultra slow search with maximum delays"""
    try:
        # Same as stealth search but with much longer delays
        result = perform_stealth_search(driver, company_name, role_type, max_results)
        
        # Additional delay after search
        if result:
            time.sleep(random.uniform(5, 10))
        
        return result
        
    except Exception as e:
        print(f"Ultra slow search error: {e}")
        return []

def extract_results_advanced(driver, max_results):
    """Enhanced result extraction with multiple selectors"""
    try:
        # Try multiple result selectors
        selectors = [
            "div.g:has(a[href*='linkedin.com/in/'])",
            ".tF2Cxc:has(a[href*='linkedin.com/in/'])",
            "div[data-ved]:has(a[href*='linkedin.com/in/'])",
            ".MjjYud:has(a[href*='linkedin.com/in/'])",
            # Fallback selectors
            "div.g", ".tF2Cxc", "div[data-ved]", ".MjjYud"
        ]
        
        results = []
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Filter for LinkedIn results
                    linkedin_results = []
                    for elem in elements[:max_results * 3]:
                        if 'linkedin.com/in/' in elem.get_attribute('outerHTML').lower():
                            linkedin_results.append(elem)
                    
                    if linkedin_results:
                        results = linkedin_results[:max_results * 2]
                        break
            except:
                continue
        
        if not results:
            print("No results found with any selector")
            return []
        
        # Extract profiles
        profiles = []
        seen_urls = set()
        
        for result in results:
            if len(profiles) >= max_results:
                break
            
            name, url = extract_profile_info_advanced(result)
            if url and url not in seen_urls and len(url) > 25:
                profiles.append({"name": name or "LinkedIn Profile", "url": url})
                seen_urls.add(url)
                print(f"Found profile: {name}")
        
        return profiles
        
    except Exception as e:
        print(f"Result extraction error: {e}")
        return []

def extract_profile_info_advanced(result_element):
    """Advanced profile extraction with better error handling"""
    try:
        # Extract URL with multiple strategies
        linkedin_url = None
        
        # Try different link extraction methods
        link_selectors = ['a[href*="linkedin.com/in/"]', 'a']
        
        for selector in link_selectors:
            try:
                links = result_element.find_elements(By.CSS_SELECTOR, selector)
                for link in links:
                    href = link.get_attribute('href')
                    if href and 'linkedin.com/in/' in href:
                        cleaned_url = clean_url_advanced(href)
                        if cleaned_url:
                            linkedin_url = cleaned_url
                            break
                if linkedin_url:
                    break
            except:
                continue
        
        if not linkedin_url:
            return None, None
        
        # Extract name with multiple strategies
        name_selectors = [
            'h3', 'h3 span', '.LC20lb', '.DKV0Md', 
            '[role="heading"]', 'h2', 'h1'
        ]
        
        profile_name = None
        for selector in name_selectors:
            try:
                elements = result_element.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    if text and 3 <= len(text) <= 150 and not any(word in text.lower() for word in ['linkedin', 'search', 'google']):
                        profile_name = clean_name_advanced(text)
                        break
                if profile_name:
                    break
            except:
                continue
        
        # Fallback name from URL
        if not profile_name and linkedin_url:
            try:
                url_parts = linkedin_url.split('/')
                if len(url_parts) > 4:
                    profile_name = url_parts[4].replace('-', ' ').title()
            except:
                profile_name = "LinkedIn Profile"
        
        return profile_name, linkedin_url
        
    except Exception as e:
        print(f"Profile extraction error: {e}")
        return None, None

def clean_url_advanced(url):
    """Advanced URL cleaning with better handling"""
    if not url or 'linkedin.com/in/' not in url:
        return None
    
    try:
        # Handle various Google redirect patterns
        if '/url?' in url:
            patterns = [
                r'[?&]url=([^&]+)',
                r'[?&]q=([^&]+)',
                r'/url\?.*?url=([^&]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    decoded = urllib.parse.unquote(match.group(1))
                    if 'linkedin.com/in/' in decoded:
                        return decoded.split('&')[0].split('?')[0]
        
        # Direct LinkedIn URL
        if 'linkedin.com/in/' in url:
            return url.split('?')[0].split('&')[0].split('#')[0]
        
    except Exception as e:
        print(f"URL cleaning error: {e}")
    
    return None

def clean_name_advanced(name):
    """Advanced name cleaning"""
    if not name:
        return ""
    
    # Remove common patterns
    patterns = [
        r' - .*$', r' \| .*$', r' @ .*$', r' at .*$', 
        r'\(.*\)$', r' \u2013 .*$', r' \u2014 .*$'
    ]
    
    cleaned = name
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean extra whitespace
    cleaned = ' '.join(cleaned.split())
    
    # Return original if cleaned is too short
    return cleaned.strip() if len(cleaned.strip()) >= 3 else name.strip()

def handle_consent_advanced(driver):
    """Advanced consent handling with multiple strategies"""
    try:
        consent_strategies = [
            ('//button[@id="L2AGLb"]', "click"),
            ('//button[contains(text(), "Accept")]', "click"),
            ('//button[contains(text(), "I agree")]', "click"),
            ('//div[@id="lb"]', "click"),
            ('[aria-label*="Accept"]', "click")
        ]
        
        for selector, action in consent_strategies:
            try:
                if selector.startswith('//'):
                    element = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    element = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                
                # Human-like click
                time.sleep(random.uniform(0.5, 1))
                element.click()
                time.sleep(random.uniform(1, 2))
                return True
                
            except:
                continue
        
        return False
        
    except Exception as e:
        print(f"Consent handling error: {e}")
        return False

def is_blocked_advanced(driver):
    """Advanced blocking detection"""
    try:
        page_source = driver.page_source.lower()
        current_url = driver.current_url.lower()
        page_title = driver.title.lower()
        
        # Enhanced blocking indicators
        blocking_indicators = [
            "unusual traffic", "captcha", "verify you are human",
            "recaptcha", "automated queries", "suspicious activity",
            "detected unusual traffic", "sorry", "blocked",
            "access denied", "forbidden", "rate limit"
        ]
        
        # Check page content
        for indicator in blocking_indicators:
            if indicator in page_source or indicator in page_title:
                print(f"Blocking detected: {indicator}")
                return True
        
        # Check URL patterns
        blocking_urls = [
            "sorry.google.com", "consent.google.com", 
            "accounts.google.com", "support.google.com"
        ]
        
        for pattern in blocking_urls:
            if pattern in current_url:
                print(f"Blocking URL detected: {pattern}")
                return True
        
        # Check for missing essential elements
        try:
            search_elements = driver.find_elements(By.NAME, "q")
            if not search_elements:
                print("No search box found - potential blocking")
                return True
        except:
            pass
        
        return False
        
    except Exception as e:
        print(f"Blocking detection error: {e}")
        return False

def format_results(company_name, row_number, sde_profiles, hr_profiles, strategy_used):
    """Format results with debug info"""
    excel_data = format_for_excel(company_name, row_number, sde_profiles, hr_profiles)
    
    return {
        "excel_data": excel_data,
        "debug": {
            "strategy_used": strategy_used,
            "sde_profiles_found": len(sde_profiles),
            "hr_profiles_found": len(hr_profiles),
            "sde_profiles": sde_profiles[:5],
            "hr_profiles": hr_profiles[:2]
        }
    }

def format_for_excel(company_name, row_number, sde_profiles, hr_profiles):
    """Format data for Excel"""
    row = {
        "row_number": row_number,
        "Company Name": company_name,
        "Status": "Completed"
    }
    
    # Add SDE profiles (up to 5)
    for i in range(5):
        if i < len(sde_profiles):
            row[f"SDE {i+1} Name"] = sde_profiles[i]['name']
            row[f"SDE {i+1} URL"] = sde_profiles[i]['url']
        else:
            row[f"SDE {i+1} Name"] = ""
            row[f"SDE {i+1} URL"] = ""
    
    # Add HR profiles (up to 2)
    for i in range(2):
        if i < len(hr_profiles):
            row[f"HR {i+1} Name"] = hr_profiles[i]['name']
            row[f"HR {i+1} URL"] = hr_profiles[i]['url']
        else:
            row[f"HR {i+1} Name"] = ""
            row[f"HR {i+1} URL"] = ""
    
    return [row]

def cleanup_driver(driver):
    """Enhanced driver cleanup"""
    if driver:
        try:
            driver.execute_script("window.stop();")
            driver.quit()
        except:
            try:
                driver.quit()
            except:
                pass

def create_timeout_result(company_name, row_number):
    return {
        "error": "Operation timed out",
        "excel_data": [{
            "row_number": row_number,
            "Company Name": company_name,
            "Status": "Timeout",
            **{f"SDE {i} Name": "" for i in range(1, 6)},
            **{f"SDE {i} URL": "" for i in range(1, 6)},
            **{f"HR {i} Name": "" for i in range(1, 3)},
            **{f"HR {i} URL": "" for i in range(1, 3)}
        }]
    }

def create_blocked_result(company_name, row_number):
    return {
        "error": "All strategies blocked by Google",
        "excel_data": [{
            "row_number": row_number,
            "Company Name": company_name,
            "Status": "Blocked",
            **{f"SDE {i} Name": "" for i in range(1, 6)},
            **{f"SDE {i} URL": "" for i in range(1, 6)},
            **{f"HR {i} Name": "" for i in range(1, 3)},
            **{f"HR {i} URL": "" for i in range(1, 3)}
        }]
    }

def create_error_result(data, error_msg):
    company_name = data.get('company', '') if data else ''
    row_number = data.get('row_number', 2) if data else 2
    
    return {
        "error": error_msg,
        "excel_data": [{
            "row_number": row_number,
            "Company Name": company_name,
            "Status": "Error",
            **{f"SDE {i} Name": "" for i in range(1, 6)},
            **{f"SDE {i} URL": "" for i in range(1, 6)},
            **{f"HR {i} Name": "" for i in range(1, 3)},
            **{f"HR {i} URL": "" for i in range(1, 3)}
        }]
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)