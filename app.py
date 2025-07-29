import time
import os
import re
import urllib.parse
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Initialize the Flask app
app = Flask(__name__)

# Health check endpoint for Render
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

# Main scrape endpoint with timeout protection
@app.route('/scrape', methods=['POST'])
def scrape_linkedin_profiles():
    try:
        data = request.get_json()
        if not data or 'company' not in data:
            return jsonify({"error": "Company name not provided"}), 400
        
        company_name = data['company']
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(scrape_with_selenium, company_name)
            try:
                # Set a total timeout for the entire scraping process
                result = future.result(timeout=240) 
                return jsonify(result)
            except FutureTimeoutError:
                print("!!! Main scraping process timed out !!!")
                return jsonify(create_empty_result(company_name, "Timeout Error", "Process took too long."))
                
    except Exception as e:
        print(f"!!! Unexpected error in main endpoint: {e} !!!")
        return jsonify(create_empty_result(
            data.get('company', 'Unknown') if 'data' in locals() else 'Unknown', 
            "Endpoint Error", 
            str(e)
        ))

def get_chrome_options():
    """Configure Chrome options for both local and production environments"""
    options = webdriver.ChromeOptions()
    
    # Check if we're in a production environment (like Render, Heroku, etc.)
    is_production = os.environ.get('NODE_ENV') == 'production' or os.environ.get('PORT') is not None
    
    # Always create a custom user data directory to avoid conflicts
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix='chrome_user_data_')
    print(f"Using temp Chrome profile: {temp_dir}")
    options.add_argument(f'--user-data-dir={temp_dir}')
    
    if is_production:
        print("Configuring Chrome for production environment...")
        # Production settings for cloud deployment
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        
    else:
        print("Configuring Chrome for local development...")
        # Local development settings - using temporary profile for stability
        options.add_argument("--start-maximized")
        # Note: We're using temp profile instead of your real profile to avoid conflicts
    
    # Essential Chrome flags to fix DevTools issues
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-ipc-flooding-protection')
    
    # ANTI-CAPTCHA / STEALTH OPTIONS
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # More realistic browser behavior
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-client-side-phishing-detection')
    options.add_argument('--disable-crash-reporter')
    options.add_argument('--disable-oopr-debug-crash-dump')
    options.add_argument('--no-crash-upload')
    options.add_argument('--disable-low-res-tiling')
    options.add_argument('--log-level=3')
    
    # Language and location settings
    options.add_argument("--lang=en-US,en;q=0.9")
    options.add_argument('--accept-lang=en-US,en;q=0.9')
    
    # Realistic user agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    ]
    import random
    selected_ua = random.choice(user_agents)
    options.add_argument(f'--user-agent={selected_ua}')
    
    return options

def initialize_chrome_driver():
    """Initialize Chrome driver with multiple fallback strategies"""
    driver = None
    
    # Strategy 1: Try with optimized options
    try:
        print("Attempting Chrome driver initialization - Strategy 1...")
        options = get_chrome_options()
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✓ Chrome driver initialized successfully!")
        return driver
    except Exception as e:
        print(f"Strategy 1 failed: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # Strategy 2: Try with minimal options
    try:
        print("Attempting Chrome driver initialization - Strategy 2 (minimal options)...")
        options = webdriver.ChromeOptions()
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix='chrome_minimal_')
        
        options.add_argument(f'--user-data-dir={temp_dir}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--remote-debugging-port=9223')  # Different port
        options.add_argument('--window-size=1920,1080')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✓ Chrome driver initialized with minimal options!")
        return driver
    except Exception as e:
        print(f"Strategy 2 failed: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # Strategy 3: Try with headless mode forced
    try:
        print("Attempting Chrome driver initialization - Strategy 3 (forced headless)...")
        options = webdriver.ChromeOptions()
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix='chrome_headless_')
        
        options.add_argument(f'--user-data-dir={temp_dir}')
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✓ Chrome driver initialized in headless mode!")
        return driver
    except Exception as e:
        print(f"Strategy 3 failed: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    raise Exception("All Chrome driver initialization strategies failed")

def scrape_with_selenium(company_name):
    """Main scraping function with environment-aware Chrome settings"""
    
    sde_query = f'site:linkedin.com/in/ "Software Engineer" "{company_name}" "India"'
    hr_query = f'site:linkedin.com/in/ "Talent Acquisition" OR "Recruiter" "{company_name}" "India"'
    
    driver = None
    try:
        print("Starting Chrome driver...")
        driver = initialize_chrome_driver()
        
        # Additional stealth measures - more comprehensive
        # driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        
        
        driver.execute_script("""
            window.navigator.chrome = {
                runtime: {},
            };
        """)
        
        driver.execute_script("""
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' }),
                }),
            });
        """)
        
        # Set realistic screen properties
        driver.execute_script("""
            Object.defineProperty(window, 'outerHeight', {
                get: () => 1080,
            });
            Object.defineProperty(window, 'outerWidth', {
                get: () => 1920,
            });
        """)
        
        wait = WebDriverWait(driver, 15)  # Increased timeout

        # Scrape SDE profiles
        print(f"\n--- Searching for SDEs ---")
        sde_profiles = scrape_google(driver, wait, sde_query, 5)
        
        # Scrape HR profiles if SDE search didn't fail
        hr_profiles = []
        if sde_profiles is not None:
             time.sleep(5) # Increased delay to avoid rate limiting
             print(f"\n--- Searching for HR ---")
             hr_profiles = scrape_google(driver, wait, hr_query, 2)
        else: # If the first search failed (e.g. CAPTCHA), don't try again
             sde_profiles = []

        return format_for_excel(company_name, "Completed", sde_profiles, hr_profiles)

    except Exception as e:
        print(f"!!! Error in scrape_with_selenium: {e} !!!")
        # Enhanced debugging
        page_source_for_debug = ""
        current_url = ""
        if driver:
            try:
                current_url = driver.current_url
                page_source_for_debug = driver.page_source[:5000]
            except:
                pass

        debug_info = f"Error: {str(e)}\nCurrent URL: {current_url}\nPage source: {page_source_for_debug}"
        return create_empty_result(company_name, "Scraping Error", debug_info)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def scrape_google(driver, wait, query, max_results):
    """Performs a single Google search and returns found profiles with CAPTCHA handling."""
    try:
        # Add random delay to seem more human-like
        import random
        time.sleep(random.uniform(2, 5))
        
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&gl=us&hl=en"
        print(f"Navigating to: {search_url}")
        driver.get(search_url)
        
        # Wait a bit for the page to load
        time.sleep(random.uniform(3, 6))

        # Check for CAPTCHA/blocking page
        page_text = driver.page_source.lower()
        captcha_keywords = ["unusual traffic", "recaptcha", "captcha", "blocked", "verify you're not a robot"]
        
        if any(keyword in page_text for keyword in captcha_keywords):
            print("!!! CAPTCHA or block page detected !!!")
            
            # Try to handle CAPTCHA automatically
            if handle_captcha_page(driver, wait):
                print("✓ CAPTCHA handling attempted, retrying search...")
                time.sleep(20)
                # Retry the search after handling CAPTCHA
                driver.get(search_url)
                time.sleep(5)
                page_text = driver.page_source.lower()
                
                # Check again if CAPTCHA is still there
                if any(keyword in page_text for keyword in captcha_keywords):
                    print("!!! CAPTCHA still present, switching to alternative search method !!!")
                    return search_alternative_method(query, max_results)
            else:
                print("!!! Could not handle CAPTCHA, switching to alternative method !!!")
                return search_alternative_method(query, max_results)

        # Wait for search results container to be present
        try:
            wait.until(EC.presence_of_element_located((By.ID, "search")))
        except:
            print("Search container not found, trying alternative approach...")
            time.sleep(3)
        
        # Multiple selectors to try
        selectors = [
            "div.yuRUbf",          # Primary selector
            "div.g",               # Fallback selector
            "div[data-ved]",       # Alternative selector
            ".rc"                  # Old style selector
        ]
        
        search_results = []
        for selector in selectors:
            search_results = driver.find_elements(By.CSS_SELECTOR, selector)
            if search_results:
                print(f"Found {len(search_results)} results with selector: {selector}")
                break
        
        if not search_results:
            print("No search results found with any selector")
            return []

        profiles = []
        for result in search_results:
            if len(profiles) >= max_results:
                break
            try:
                # Try multiple approaches to find the link and title
                link_element = None
                name = ""
                url = ""
                
                # Method 1: Direct anchor tag
                try:
                    link_element = result.find_element(By.TAG_NAME, 'a')
                    url = link_element.get_attribute('href')
                except:
                    pass
                
                # Method 2: Try h3 parent approach
                if not url:
                    try:
                        h3_element = result.find_element(By.TAG_NAME, 'h3')
                        link_element = h3_element.find_element(By.XPATH, '..')
                        url = link_element.get_attribute('href')
                    except:
                        pass
                
                # Get the name/title
                try:
                    name = result.find_element(By.TAG_NAME, 'h3').text
                except:
                    try:
                        name = result.find_element(By.CSS_SELECTOR, 'h3, .LC20lb').text
                    except:
                        name = "Unknown"
                
                if url and 'linkedin.com/in/' in url:
                    profile = {"name": name.strip(), "url": url}
                    profiles.append(profile)
                    print(f"  -> Found: {profile}")
                    
            except Exception as e:
                print(f"Error processing result: {e}")
                continue
        
        return profiles
        
    except Exception as e:
        print(f"!!! Failed to scrape query '{query}'. Error: {e} !!!")
        return None

def handle_captcha_page(driver, wait):
    """
    A more robust attempt to handle a CAPTCHA page by looking inside iframes.

    NOTE: This method attempts to solve the most common "I'm not a robot" checkbox.
    It will NOT work if a visual puzzle (e.g., "select all traffic lights") is presented.
    The success rate is still low, as these systems are designed to detect automated clicks.
    """
    try:
        print("Attempting to handle CAPTCHA page with iframe search...")
        
        # CAPTCHAs are almost always in an iframe. We need to switch to it first.
        # This waits up to 10 seconds for an iframe with 'recaptcha' or 'hcaptcha' in its source.
        short_wait = WebDriverWait(driver, 20)
        iframe_locator = (By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@src, 'hcaptcha')]")
        
        try:
            short_wait.until(EC.frame_to_be_available_and_switch_to_it(iframe_locator))
            print("✓ Switched to CAPTCHA iframe.")
        except Exception:
            print("!!! Could not find a CAPTCHA iframe. The block may be a simple page.")
            # Fallback to just pressing enter on the page if no iframe is found
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ENTER)
            time.sleep(5)
            return True

        # Now inside the iframe, try to click the checkbox.
        checkbox_locator = (By.CSS_SELECTOR, "div.recaptcha-checkbox-border")
        try:
            checkbox = short_wait.until(EC.element_to_be_clickable(checkbox_locator))
            print("Found CAPTCHA checkbox, clicking...")
            checkbox.click()
            time.sleep(5)
        except Exception:
            print("!!! Could not find or click the checkbox inside the iframe.")
            # Switch back to the main page before failing
            driver.switch_to.default_content()
            return False

        # IMPORTANT: Always switch back to the main document context
        driver.switch_to.default_content()
        print("✓ Switched back to main content.")
        
        # Give it a moment to see if the puzzle was solved or a new one appeared
        time.sleep(5)
        return True

    except Exception as e:
        print(f"!!! An unexpected error occurred in handle_captcha_page: {e}")
        # Ensure we are not stuck in an iframe
        try:
            driver.switch_to.default_content()
        except:
            pass
        return False
    
def search_alternative_method(query, max_results):
    """Alternative search method using different search engines"""
    print("Using alternative search method...")
    
    # Method 1: Try DuckDuckGo with requests (no Selenium needed)
    try:
        import requests
        from bs4 import BeautifulSoup
        
        print("Trying DuckDuckGo via requests...")
        search_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            results = soup.find_all('a', class_='result__a')
            
            profiles = []
            for result in results[:max_results * 2]:
                try:
                    url = result.get('href')
                    name = result.get_text(strip=True)
                    
                    if url and 'linkedin.com/in/' in url and len(profiles) < max_results:
                        profiles.append({"name": name, "url": url})
                        print(f"  -> Found via DuckDuckGo: {name}")
                except:
                    continue
            
            if profiles:
                return profiles
                
    except Exception as e:
        print(f"DuckDuckGo requests method failed: {e}")
    
    # Method 2: Try Bing with requests
    try:
        print("Trying Bing via requests...")
        search_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            results = soup.find_all('h2')
            
            profiles = []
            for result in results[:max_results * 2]:
                try:
                    link = result.find('a')
                    if link:
                        url = link.get('href')
                        name = link.get_text(strip=True)
                        
                        if url and 'linkedin.com/in/' in url and len(profiles) < max_results:
                            profiles.append({"name": name, "url": url})
                            print(f"  -> Found via Bing: {name}")
                except:
                    continue
            
            if profiles:
                return profiles
                
    except Exception as e:
        print(f"Bing requests method failed: {e}")
    
    print("All alternative search methods failed")
    return []

def create_empty_result(company_name, status, debug_info=""):
    """Creates a standardized empty/error result, including debug info."""
    return {
        "excel_data": [{
            "Company Name": company_name,
            "Status": status,
            **{f"SDE {i} Name": "" for i in range(1, 6)},
            **{f"SDE {i} URL": "" for i in range(1, 6)},
            **{f"HR {i} Name": "" for i in range(1, 3)},
            **{f"HR {i} URL": "" for i in range(1, 3)}
        }],
        "debug_info": debug_info
    }

def format_for_excel(company_name, status, sde_profiles, hr_profiles):
    """Formats the final data into the structure n8n expects."""
    row = {
        "Company Name": company_name,
        "Status": status,
        **{f"SDE {i} Name": "" for i in range(1, 6)},
        **{f"SDE {i} URL": "" for i in range(1, 6)},
        **{f"HR {i} Name": "" for i in range(1, 3)},
        **{f"HR {i} URL": "" for i in range(1, 3)}
    }

    for i, profile in enumerate(sde_profiles[:5]):
        row[f"SDE {i+1} Name"] = profile['name']
        row[f"SDE {i+1} URL"] = profile['url']
        
    for i, profile in enumerate(hr_profiles[:2]):
        row[f"HR {i+1} Name"] = profile['name']
        row[f"HR {i+1} URL"] = profile['url']
        
    return {"excel_data": [row]}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)