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

# Initialize the Flask app
app = Flask(__name__)

# Define the /scrape endpoint
@app.route('/scrape', methods=['POST'])
def scrape_linkedin_profiles():
    data = request.get_json()
    if not data or 'company' not in data:
        return jsonify({"error": "Company name not provided"}), 400
    
    company_name = data['company']
    row_number = data.get('row_number', 2)  # Default to 2 if not provided
    
    # Define search queries for different roles
    sde_query = f'site:linkedin.com/in/ "Software Engineer" "{company_name}" "India"'
    hr_queries = [
        f'site:linkedin.com/in/ "Talent Acquisition" "{company_name}" "India"',
        f'site:linkedin.com/in/ "HR" "{company_name}" "India"',
        f'site:linkedin.com/in/ "Human Resources" "{company_name}" "India"',
        f'site:linkedin.com/in/ "Recruiter" "{company_name}" "India"'
    ]
    
    # Create a temporary profile directory for automation
    temp_profile_dir = os.path.join(os.getcwd(), "temp_chrome_profile")
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') 
    options.add_argument(f"--user-data-dir={temp_profile_dir}")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-extensions')
    options.add_argument("--start-maximized")
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')

    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        wait = WebDriverWait(driver, 15)

        print("Navigating to Google homepage...")
        driver.get("https://www.google.com")
        time.sleep(3)

        # Handle cookie consent
        handle_cookie_consent(driver, wait)
        
        # Check for CAPTCHA
        if is_captcha_or_blocked(driver):
            print("Detected CAPTCHA. Please solve it manually.")
            input("Press Enter after solving CAPTCHA...")
            time.sleep(2)

        # Scrape Software Engineers (5 profiles)
        print(f"=== SEARCHING FOR SOFTWARE ENGINEERS ===")
        sde_profiles = improved_scrape_google(driver, wait, sde_query, 5)
        
        # Add delay between searches to avoid being blocked
        time.sleep(random.uniform(3, 6))
        
        # Scrape HR/Talent Acquisition profiles (2 profiles total)
        print(f"=== SEARCHING FOR HR/TALENT ACQUISITION ===")
        hr_profiles = []
        
        for hr_query in hr_queries:
            if len(hr_profiles) >= 2:
                break
                
            print(f"Trying HR query: {hr_query}")
            hr_results = improved_scrape_google(driver, wait, hr_query, 3)
            
            # Add unique profiles
            for profile in hr_results:
                if len(hr_profiles) >= 2:
                    break
                if not any(existing['url'] == profile['url'] for existing in hr_profiles):
                    hr_profiles.append(profile)
            
            # Add delay between HR queries
            if len(hr_profiles) < 2 and hr_query != hr_queries[-1]:
                time.sleep(random.uniform(2, 4))
        
        # Format the response for Excel
        excel_formatted = format_for_excel(company_name, row_number, sde_profiles, hr_profiles)
        
        return jsonify({
            "excel_data": excel_formatted,
            "debug": {
                "sde_profiles_found": len(sde_profiles),
                "hr_profiles_found": len(hr_profiles),
                "sde_profiles": sde_profiles,
                "hr_profiles": hr_profiles
            }
        })

    except Exception as e:
        print(f"An overall error occurred: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        try:
            import shutil
            if os.path.exists(temp_profile_dir):
                shutil.rmtree(temp_profile_dir, ignore_errors=True)
        except:
            pass


def format_for_excel(company_name, row_number, sde_profiles, hr_profiles):
    """Format the scraped data for Excel import"""
    excel_row = {
        "row_number": row_number,
        "Company Name": company_name,
        "Status": "Done"
    }
    
    # Add SDE profiles (up to 5)
    for i in range(5):
        sde_num = i + 1
        if i < len(sde_profiles):
            # Clean the name - remove extra job title info
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
            # Clean the name - remove extra job title info
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
    
    # Remove common job title patterns
    patterns_to_remove = [
        r' - .*',  # Everything after first dash
        r' \| .*',  # Everything after pipe
        r' @ .*',   # Everything after @
        r' at .*',  # Everything after 'at'
        r'\(.*\)',  # Everything in parentheses
    ]
    
    cleaned_name = name
    for pattern in patterns_to_remove:
        cleaned_name = re.sub(pattern, '', cleaned_name, flags=re.IGNORECASE)
    
    # Clean up extra spaces and capitalize properly
    cleaned_name = ' '.join(cleaned_name.split())
    
    # If name becomes too short after cleaning, use original
    if len(cleaned_name.strip()) < 3:
        return name.strip()
    
    return cleaned_name.strip()


def handle_cookie_consent(driver, wait):
    """Handle Google's cookie consent popup"""
    try:
        consent_selectors = [
            '//button[contains(text(), "Accept all")]',
            '//button[contains(text(), "I agree")]',
            '//button[@id="L2AGLb"]'
        ]
        
        for selector in consent_selectors:
            try:
                consent_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                print("Cookie consent button found. Clicking...")
                consent_button.click()
                time.sleep(2)
                return True
            except:
                continue
        
        print("No cookie consent popup found")
        return False
                
    except Exception as e:
        print(f"Error handling cookie consent: {e}")
        return False


def is_captcha_or_blocked(driver):
    """Check if the current page is a CAPTCHA or blocking page"""
    page_text = driver.page_source.lower()
    blocking_indicators = [
        "unusual traffic",
        "captcha",
        "i'm not a robot",
        "verify you are human",
        "recaptcha",
        "our systems have detected"
    ]
    
    return any(indicator in page_text for indicator in blocking_indicators)


def human_like_typing(element, text):
    """Type text in a more human-like manner"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))


def clean_google_url(url):
    """Clean Google redirect URLs to get the actual LinkedIn URL"""
    if not url:
        return None
    
    # Direct LinkedIn URL
    if 'linkedin.com/in/' in url and '/url?' not in url:
        return url
    
    # Google redirect URL
    if '/url?' in url:
        try:
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Try different parameter names
            for param in ['url', 'q', 'sa']:
                if param in query_params:
                    decoded_url = urllib.parse.unquote(query_params[param][0])
                    if 'linkedin.com/in/' in decoded_url:
                        return decoded_url
        except:
            pass
    
    # Extract LinkedIn URL from any string
    linkedin_pattern = r'https?://[^/]*linkedin\.com/in/[^/\s&]+'
    match = re.search(linkedin_pattern, url)
    if match:
        return match.group(0)
    
    return None


def extract_profile_name(result_element):
    """Extract profile name from various possible elements"""
    name_selectors = [
        'h3',                           # Main title
        'h3 span',                      # Title spans
        'h3 .LC20lb',                   # Google title class
        '.LC20lb',                      # Direct title class
        '.DKV0Md',                      # Google result title
        'span[role="heading"]',         # Heading spans
        'div[role="heading"]',          # Heading divs
        '.yuRUbf h3',                   # Nested h3
        '.tF2Cxc h3',                   # Alternative nested h3
        'cite + h3',                    # H3 after cite
        'a h3',                         # H3 inside links
        'a span',                       # Spans inside links
    ]
    
    for selector in name_selectors:
        try:
            elements = result_element.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = element.text.strip()
                if text and 3 <= len(text) <= 100:
                    # Clean up the name
                    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
                    text = text.replace(' - LinkedIn', '').replace('LinkedIn', '').strip()
                    
                    # Avoid generic text
                    generic_terms = ['search', 'results', 'more', 'about', 'images', 'videos']
                    if not any(term in text.lower() for term in generic_terms):
                        return text
        except:
            continue
    
    return None


def extract_linkedin_url_from_result(result_element):
    """Extract LinkedIn URL from a search result element"""
    # Find all links
    links = result_element.find_elements(By.TAG_NAME, 'a')
    
    for link in links:
        href = link.get_attribute('href')
        cleaned_url = clean_google_url(href)
        if cleaned_url and 'linkedin.com/in/' in cleaned_url:
            return cleaned_url
    
    # Also check in data attributes and onclick handlers
    try:
        onclick = result_element.get_attribute('onclick')
        if onclick and 'linkedin.com/in/' in onclick:
            linkedin_match = re.search(r'https?://[^/]*linkedin\.com/in/[^/\s&]+', onclick)
            if linkedin_match:
                return linkedin_match.group(0)
    except:
        pass
    
    # Check in the innerHTML for any LinkedIn URLs
    try:
        inner_html = result_element.get_attribute('innerHTML')
        if inner_html and 'linkedin.com/in/' in inner_html:
            linkedin_match = re.search(r'https?://[^/]*linkedin\.com/in/[^/\s&"\']+', inner_html)
            if linkedin_match:
                return clean_google_url(linkedin_match.group(0))
    except:
        pass
    
    return None


def improved_scrape_google(driver, wait, query, max_results):
    """Improved scraping with better URL and name extraction"""
    try:
        # Navigate to Google search
        driver.get("https://www.google.com")
        time.sleep(3)
        
        # Find search box
        try:
            search_box = wait.until(EC.presence_of_element_located((By.NAME, "q")))
            print("Found search box by name 'q'")
        except:
            try:
                search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[title='Search']")))
                print("Found search box by title 'Search'")
            except:
                search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='q']")))
                print("Found search box as textarea")
        
        # Search
        search_box.clear()
        time.sleep(1)
        human_like_typing(search_box, query)
        time.sleep(1)
        search_box.send_keys(Keys.RETURN)
        time.sleep(4)
        
        print(f"Current URL after search: {driver.current_url}")
        
        # Check for blocking
        if is_captcha_or_blocked(driver):
            print("Hit CAPTCHA after search!")
            return []
        
        # Wait for results and try multiple selectors
        selectors_to_try = [
            "div.g",                    # Standard Google results
            ".tF2Cxc",                  # New Google layout
            "div[data-ved]",            # Alternative with data-ved
            ".yuRUbf",                  # Result wrapper
            ".MjjYud",                  # Another Google class
            "div.kvH3mc",               # Alternative class
            "[jscontroller] .g",        # Nested results
        ]
        
        search_results = []
        used_selector = None
        
        for selector in selectors_to_try:
            try:
                results = driver.find_elements(By.CSS_SELECTOR, selector)
                if results:
                    # Check if these contain LinkedIn content
                    linkedin_count = 0
                    for result in results[:5]:
                        if 'linkedin.com' in result.get_attribute('outerHTML').lower():
                            linkedin_count += 1
                    
                    print(f"Selector '{selector}': {len(results)} elements, {linkedin_count} with LinkedIn")
                    
                    if linkedin_count > 0:
                        search_results = results
                        used_selector = selector
                        break
            except Exception as e:
                print(f"Selector '{selector}' failed: {e}")
                continue
        
        if not search_results:
            print("No suitable search results found!")
            return []
        
        print(f"Using selector '{used_selector}' with {len(search_results)} results")
        
        profiles = []
        seen_urls = set()
        
        for i, result in enumerate(search_results):
            if len(profiles) >= max_results:
                break
                
            print(f"\n--- Processing result {i+1} ---")
            
            # Check if this result contains LinkedIn content
            result_html = result.get_attribute('outerHTML')
            if 'linkedin.com' not in result_html.lower():
                print("  No LinkedIn content, skipping")
                continue
            
            # Extract LinkedIn URL
            linkedin_url = extract_linkedin_url_from_result(result)
            if not linkedin_url:
                print("  No LinkedIn URL found")
                continue
            
            # Skip duplicates
            if linkedin_url in seen_urls:
                print(f"  Duplicate URL: {linkedin_url}")
                continue
            
            # Extract profile name
            profile_name = extract_profile_name(result)
            if not profile_name:
                print(f"  No name found for URL: {linkedin_url}")
                # Use a fallback name based on URL
                url_parts = linkedin_url.split('/')
                if len(url_parts) > 4:
                    profile_name = url_parts[4].replace('-', ' ').title()
                else:
                    profile_name = "LinkedIn Profile"
            
            # Clean up the LinkedIn URL (remove tracking parameters)
            linkedin_url = linkedin_url.split('?')[0].rstrip('/')
            
            profile = {
                "name": profile_name,
                "url": linkedin_url
            }
            
            profiles.append(profile)
            seen_urls.add(linkedin_url)
            
            print(f"  ✓ Found: {profile_name} -> {linkedin_url}")
        
        print(f"\n=== FINAL RESULTS: Found {len(profiles)} unique profiles ===")
        for i, profile in enumerate(profiles, 1):
            print(f"  {i}. {profile['name']}: {profile['url']}")
        
        return profiles
                
    except Exception as e:
        print(f"Error in improved_scrape_google: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

# Example API call:
# curl -X POST http://localhost:5001/scrape \
#   -H "Content-Type: application/json" \
#   -d '{"company": "Microsoft", "row_number": 2}'