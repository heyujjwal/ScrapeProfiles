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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

app = Flask(__name__)

# Reduced timeout for better reliability
SCRAPING_TIMEOUT = 180  # 3 minutes
SEARCH_TIMEOUT = 30     # 30 seconds per search

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "LinkedIn Scraper API is running"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/test-google', methods=['GET'])
def test_google_access():
    """Test endpoint to check Google access"""
    driver = None
    try:
        driver = create_stealth_driver()
        driver.get("https://www.google.com")
        time.sleep(3)
        
        result = {
            "url": driver.current_url,
            "title": driver.title,
            "blocked": is_blocked(driver),
            "has_search_box": len(driver.find_elements(By.NAME, "q")) > 0,
            "page_length": len(driver.page_source)
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cleanup_driver(driver)

@app.route('/scrape', methods=['POST'])
def scrape_linkedin_profiles():
    try:
        data = request.get_json()
        if not data or 'company' not in data:
            return jsonify({"error": "Company name not provided"}), 400
        
        company_name = data['company']
        row_number = data.get('row_number', 2)
        
        # Use timeout control
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(scrape_with_google, company_name, row_number)
            try:
                result = future.result(timeout=SCRAPING_TIMEOUT)
                return jsonify(result)
            except FutureTimeoutError:
                return jsonify(create_timeout_result(company_name, row_number)), 200
                
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify(create_error_result(data, str(e))), 200

def create_stealth_driver():
    """Create a stealth Chrome driver optimized for production"""
    options = webdriver.ChromeOptions()
    
    # Essential headless options
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # Memory optimization
    options.add_argument('--memory-pressure-off')
    options.add_argument('--max_old_space_size=4096')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    
    # Anti-detection (most important)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic browser simulation
    options.add_argument('--window-size=1366,768')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Performance optimizations
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--disable-javascript')  # We don't need JS for basic searches
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        # Anti-detection scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        # Set timeouts
        driver.set_page_load_timeout(SEARCH_TIMEOUT)
        driver.implicitly_wait(10)
        
        return driver
    except Exception as e:
        print(f"Failed to create driver: {e}")
        raise

def scrape_with_google(company_name, row_number):
    """Main scraping function using only Google"""
    driver = None
    try:
        print(f"Starting scrape for company: {company_name}")
        driver = create_stealth_driver()
        
        # Navigate to Google
        driver.get("https://www.google.com")
        time.sleep(random.uniform(2, 4))
        
        # Handle consent popup
        handle_consent(driver)
        
        # Check if blocked
        if is_blocked(driver):
            print("Google access is blocked")
            return create_blocked_result(company_name, row_number)
        
        print("Successfully accessed Google")
        
        # Search for SDE profiles
        print("Searching for Software Engineers...")
        sde_query = f'site:linkedin.com/in/ "Software Engineer" "{company_name}" India'
        sde_profiles = search_google(driver, sde_query, 5)
        
        time.sleep(random.uniform(3, 6))  # Longer delay between searches
        
        # Search for HR profiles
        print("Searching for HR/Talent Acquisition...")
        hr_query = f'site:linkedin.com/in/ ("Talent Acquisition" OR "HR" OR "Human Resources") "{company_name}" India'
        hr_profiles = search_google(driver, hr_query, 2)
        
        # Format results
        excel_data = format_for_excel(company_name, row_number, sde_profiles, hr_profiles)
        
        return {
            "excel_data": excel_data,
            "debug": {
                "search_engine_used": "google",
                "sde_profiles_found": len(sde_profiles),
                "hr_profiles_found": len(hr_profiles),
                "sde_profiles": sde_profiles[:3],  # Limit debug output
                "hr_profiles": hr_profiles[:2]
            }
        }
        
    except Exception as e:
        print(f"Scraping failed: {e}")
        return create_error_result({"company": company_name, "row_number": row_number}, str(e))
    finally:
        cleanup_driver(driver)

def search_google(driver, query, max_results):
    """Perform Google search with enhanced reliability"""
    try:
        print(f"Executing search: {query}")
        
        # Find search box
        wait = WebDriverWait(driver, 15)
        search_box = wait.until(EC.presence_of_element_located((By.NAME, "q")))
        
        # Clear and enter query with human-like typing
        search_box.clear()
        time.sleep(random.uniform(0.5, 1))
        
        # Type with realistic delays
        for char in query:
            search_box.send_keys(char)
            time.sleep(random.uniform(0.02, 0.08))
        
        time.sleep(random.uniform(0.5, 1))
        search_box.send_keys(Keys.RETURN)
        
        # Wait for results
        time.sleep(random.uniform(3, 5))
        
        # Check if blocked after search
        if is_blocked(driver):
            print("Blocked after search")
            return []
        
        # Find results using multiple selectors
        results = []
        selectors = ["div.g", ".tF2Cxc", "div[data-ved]", ".MjjYud"]
        
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    results = elements[:max_results * 2]  # Get extra for filtering
                    break
            except:
                continue
        
        if not results:
            print("No search results found")
            return []
        
        # Extract profiles
        profiles = []
        seen_urls = set()
        
        for result in results:
            if len(profiles) >= max_results:
                break
                
            # Check for LinkedIn content
            if 'linkedin.com/in/' not in result.get_attribute('outerHTML').lower():
                continue
            
            name, url = extract_profile_info(result)
            if url and url not in seen_urls and len(url) > 20:  # Basic validation
                profiles.append({"name": name or "LinkedIn Profile", "url": url})
                seen_urls.add(url)
        
        print(f"Found {len(profiles)} profiles")
        return profiles
        
    except Exception as e:
        print(f"Search error: {e}")
        return []

def extract_profile_info(result_element):
    """Extract name and URL from search result"""
    try:
        # Extract URL
        linkedin_url = None
        links = result_element.find_elements(By.TAG_NAME, 'a')
        
        for link in links:
            href = link.get_attribute('href')
            if href and 'linkedin.com/in/' in href:
                linkedin_url = clean_url(href)
                if linkedin_url:
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
                    if text and 3 <= len(text) <= 100:
                        profile_name = clean_name(text)
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
        
        return profile_name, linkedin_url
        
    except Exception as e:
        print(f"Profile extraction error: {e}")
        return None, None

def clean_url(url):
    """Clean Google redirect URLs"""
    if not url or 'linkedin.com/in/' not in url:
        return None
    
    # Handle Google redirects
    if '/url?' in url:
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            if 'url' in params:
                decoded = urllib.parse.unquote(params['url'][0])
                if 'linkedin.com/in/' in decoded:
                    return decoded.split('&')[0].split('?')[0]
        except:
            pass
    
    # Direct LinkedIn URL
    if 'linkedin.com/in/' in url:
        return url.split('?')[0].split('&')[0]
    
    return None

def clean_name(name):
    """Clean profile name"""
    if not name:
        return ""
    
    # Remove common suffixes
    patterns = [r' - .*', r' \| .*', r' @ .*', r' at .*', r'\(.*\)']
    cleaned = name
    
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    cleaned = ' '.join(cleaned.split())
    return cleaned.strip() if len(cleaned.strip()) >= 3 else name.strip()

def handle_consent(driver):
    """Handle Google consent popup"""
    try:
        consent_selectors = [
            '//button[@id="L2AGLb"]',
            '//button[contains(text(), "Accept")]',
            '//button[contains(text(), "I agree")]'
        ]
        
        for selector in consent_selectors:
            try:
                button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                button.click()
                time.sleep(1)
                return
            except:
                continue
    except:
        pass

def is_blocked(driver):
    """Check if Google has blocked access"""
    try:
        page_text = driver.page_source.lower()
        current_url = driver.current_url.lower()
        
        # Check for blocking indicators
        blocking_signs = [
            "unusual traffic", "captcha", "verify you are human",
            "recaptcha", "automated queries", "suspicious activity"
        ]
        
        for sign in blocking_signs:
            if sign in page_text:
                print(f"Blocking detected: {sign}")
                return True
        
        # Check URL patterns
        if any(pattern in current_url for pattern in ["sorry.google.com", "consent.google.com"]):
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking blocking: {e}")
        return False

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
    """Safely cleanup driver"""
    if driver:
        try:
            driver.quit()
        except:
            pass

def create_timeout_result(company_name, row_number):
    """Create timeout result"""
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
    """Create blocked result"""
    return {
        "error": "Google access blocked",
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
    """Create error result"""
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