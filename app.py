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

def scrape_with_selenium(company_name):
    """Main scraping function with optimized Chrome settings"""
    
    sde_query = f'site:linkedin.com/in/ "Software Engineer" "{company_name}" "India"'
    hr_query = f'site:linkedin.com/in/ "Talent Acquisition" OR "Recruiter" "{company_name}" "India"'
    
    # --- ENHANCED CHROME OPTIONS ---
    options = webdriver.ChromeOptions()
    # Use the new, more reliable headless mode
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    # Make the browser look more "real"
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("--lang=en-US,en;q=0.9") # Set language to match server location
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    # --- OPTIONAL: FOR PRODUCTION-GRADE SCRAPING, ADD A PROXY ---
    # proxy_server = "http://user:password@proxy.server.com:port"
    # options.add_argument(f'--proxy-server={proxy_server}')

    driver = None
    try:
        print("Starting Chrome driver...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        wait = WebDriverWait(driver, 10)

        # Scrape SDE profiles
        print(f"\n--- Searching for SDEs ---")
        sde_profiles = scrape_google(driver, wait, sde_query, 5)
        
        # Scrape HR profiles if SDE search didn't fail
        hr_profiles = []
        if sde_profiles is not None:
             time.sleep(2) # Small delay
             print(f"\n--- Searching for HR ---")
             hr_profiles = scrape_google(driver, wait, hr_query, 2)
        else: # If the first search failed (e.g. CAPTCHA), don't try again
             sde_profiles = []

        return format_for_excel(company_name, "Completed", sde_profiles, hr_profiles)

    except Exception as e:
        print(f"!!! Error in scrape_with_selenium: {e} !!!")
        # --- ENHANCED DEBUGGING ---
        # If an error occurs, capture the HTML of the page for inspection
        page_source_for_debug = ""
        if driver:
            page_source_for_debug = driver.page_source[:5000] # Get first 5000 chars

        return create_empty_result(company_name, "Scraping Error", page_source_for_debug)
    finally:
        if driver:
            driver.quit()

def scrape_google(driver, wait, query, max_results):
    """Performs a single Google search and returns found profiles."""
    try:
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&gl=us&hl=en"
        print(f"Navigating to: {search_url}")
        driver.get(search_url)

        # Quick check for CAPTCHA/blocking page
        if "unusual traffic" in driver.page_source.lower() or "recaptcha" in driver.page_source.lower():
            print("!!! CAPTCHA or block page detected !!!")
            return None # Return None to signal a failure

        # Wait for search results container to be present
        wait.until(EC.presence_of_element_located((By.ID, "search")))
        
        # Use a reliable selector for the main search result block
        search_results = driver.find_elements(By.CSS_SELECTOR, "div.yuRUbf")
        print(f"Found {len(search_results)} result containers with primary selector.")
        
        if not search_results: # Fallback selector
            search_results = driver.find_elements(By.CSS_SELECTOR, "div.g")
            print(f"Found {len(search_results)} results with fallback selector 'div.g'.")

        profiles = []
        for result in search_results:
            if len(profiles) >= max_results:
                break
            try:
                link_element = result.find_element(By.TAG_NAME, 'a')
                url = link_element.get_attribute('href')
                name = result.find_element(By.TAG_NAME, 'h3').text
                
                if url and 'linkedin.com/in/' in url:
                    profile = {"name": name, "url": url}
                    profiles.append(profile)
                    print(f"  -> Found: {profile}")
            except Exception:
                continue
        
        return profiles
    except Exception as e:
        print(f"!!! Failed to scrape query '{query}'. Error: {e} !!!")
        return None # Return None to signal a failure

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