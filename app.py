from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import os
from datetime import datetime
import time
import random
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

class GoldenPagesScraper:
    BASE_URL = "https://www.goldenpages.ie"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        })

    def get_towns(self):
        """Return a list of major Irish towns."""
        towns = [
            'Dublin', 'Cork', 'Galway', 'Limerick', 'Waterford',
            'Drogheda', 'Dundalk', 'Swords', 'Blackrock', 'Tralee',
            'Kilkenny', 'Navan', 'Ennis', 'Carlow', 'Naas',
            'Sligo', 'Monaghan', 'Mullingar', 'Wexford', 'Athlone',
            'Celbridge', 'Clonmel', 'Bray', 'Greystones', 'Malahide'
        ]
        return sorted(towns)

    def scrape_business_data(self, where, what=''):
        """Scrape business data for a specific location and business type."""
        businesses = []
        seen_businesses = set()  # Track seen business names to avoid duplicates
        try:
            print(f"Searching for '{what}' in '{where}'")
            
            # Set up Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Initialize Chrome driver
            print("Initializing Chrome driver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            try:
                # Visit the homepage
                print("Visiting homepage...")
                driver.get(self.BASE_URL)
                time.sleep(2)
                
                # Find and fill the search form
                what_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "what"))
                )
                what_input.clear()
                what_input.send_keys(what)
                
                where_input = driver.find_element(By.ID, "where")
                where_input.clear()
                where_input.send_keys(where)
                
                # Submit the form
                print("Submitting search form...")
                where_input.submit()
                time.sleep(3)
                
                # Get the current URL after form submission
                current_url = driver.current_url
                print(f"Redirected to: {current_url}")
                
                # Extract the search results URL from the meta tags
                meta_url = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:url"]').get_attribute('content')
                if meta_url:
                    print(f"Found search results URL: {meta_url}")
                    current_url = meta_url
                
                # Now use requests to continue scraping with the correct URL
                self.session.headers.update({
                    'Referer': self.BASE_URL,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                
                page_num = 1
                while True:
                    print(f"Scraping page {page_num}")
                    
                    # Get the page content
                    response = self.session.get(current_url)
                    
                    if not response.ok:
                        print(f"Failed to get page {page_num}: {response.status_code}")
                        break
                    
                    soup = BeautifulSoup(response.content, 'lxml')
                    
                    # Find all business listings
                    listings = soup.find_all('div', {'class': 'listing_container'})
                    
                    if not listings:
                        print("No listings found on this page")
                        print("Page content:")
                        print(soup.prettify()[:1000])
                        break
                    
                    print(f"Found {len(listings)} listings on page {page_num}")
                    
                    for listing in listings:
                        try:
                            # Extract business information
                            listing_content = listing.find('div', {'class': 'listing_content'})
                            if not listing_content:
                                continue
                            
                            # Get business name and URL
                            name_elem = listing_content.find('h3', {'class': 'listing_title'})
                            if name_elem:
                                # Get the text and URL from the link inside the title
                                title_link = name_elem.find('a', {'class': 'listing_title_link'})
                                if title_link:
                                    name = title_link.get_text(strip=True)
                                    business_url = title_link.get('href')
                                    if business_url and not business_url.startswith('http'):
                                        business_url = self.BASE_URL + business_url
                                else:
                                    name = name_elem.get_text(strip=True)
                                    business_url = ''
                                
                                # Clean up the name
                                name = re.sub(r'^\d+\.\s*', '', name)  # Remove leading number
                                name = re.sub(r'\s*Sponsored\s*$', '', name)  # Remove "Sponsored" text
                                name = re.sub(r'This is a verified listing\.Find out more$', '', name)  # Remove verification text
                                name = name.strip()
                            else:
                                continue
                            
                            # Skip if we've already seen this business
                            if name.lower() in seen_businesses:
                                continue
                            seen_businesses.add(name.lower())
                            
                            # Get location
                            location_elem = listing_content.find('div', {'class': 'listing_address'})
                            location = location_elem.get_text(strip=True) if location_elem else ''
                            
                            # Get phone number
                            phone_elem = listing_content.find('a', {'class': 'link_listing_number'})
                            phone = phone_elem.get_text(strip=True) if phone_elem else ''
                            
                            # Get business categories
                            categories_elem = listing_content.find('div', {'class': 'listing_categories'})
                            business_type = ''
                            if categories_elem:
                                categories = categories_elem.find_all('a')
                                business_type = ', '.join([cat.get_text(strip=True) for cat in categories])
                            
                            # Get description
                            desc_elem = listing_content.find('div', {'class': 'listing_summary'})
                            description = desc_elem.get_text(strip=True) if desc_elem else ''
                            
                            # Get website
                            website = ''
                            links_div = listing_content.find('div', {'class': 'listing_links'})
                            if links_div:
                                website_elem = links_div.find('a', text='Website')
                                if website_elem:
                                    website = website_elem.get('href', '')
                            
                            # Visit the business page to get email
                            email = ''
                            if business_url:
                                try:
                                    print(f"Visiting business page: {business_url}")
                                    business_response = self.session.get(business_url)
                                    if business_response.ok:
                                        business_soup = BeautifulSoup(business_response.content, 'lxml')
                                        
                                        # Try to find email in contact information
                                        contact_info = business_soup.find('div', {'class': ['contact_info', 'business_contact', 'contact-details']})
                                        if contact_info:
                                            # Look for email in text content
                                            text_content = contact_info.get_text()
                                            email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text_content)
                                            if email_matches:
                                                email = email_matches[0]
                                            else:
                                                # Look for email links
                                                email_links = contact_info.find_all('a', href=re.compile(r'mailto:'))
                                                if email_links:
                                                    email = email_links[0].get('href', '').replace('mailto:', '')
                                        
                                        # If no email found in contact info, try other sections
                                        if not email:
                                            # Try to find email in any text content
                                            text_content = business_soup.get_text()
                                            email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text_content)
                                            if email_matches:
                                                email = email_matches[0]
                                            else:
                                                # Try to find any mailto links
                                                email_links = business_soup.find_all('a', href=re.compile(r'mailto:'))
                                                if email_links:
                                                    email = email_links[0].get('href', '').replace('mailto:', '')
                                
                                    # Add a small delay between requests
                                    time.sleep(random.uniform(1, 2))
                                    
                                except Exception as e:
                                    print(f"Error getting email from business page: {e}")
                            
                            business = {
                                'Name': name,
                                'Business Type': business_type,
                                'Location': location,
                                'Phone Number': phone,
                                'Email': email,
                                'Website': website,
                                'Description': description,
                                'Golden Pages URL': business_url
                            }
                            
                            businesses.append(business)
                            print(f"Added business: {name} (Email: {email})")
                        
                        except Exception as e:
                            print(f"Error processing listing: {e}")
                            continue
                    
                    # Look for next page link
                    next_page = soup.find('a', {'class': 'next_page'})
                    if not next_page:
                        print("No more pages available")
                        break
                    
                    # Get the next page URL
                    next_url = next_page.get('href')
                    if not next_url:
                        break
                        
                    if not next_url.startswith('http'):
                        next_url = self.BASE_URL + next_url
                    
                    # Update current URL for next iteration
                    current_url = next_url
                    page_num += 1
                    time.sleep(random.uniform(2, 3))
                
                print(f"Successfully scraped {len(businesses)} businesses")
                return businesses
                
            finally:
                try:
                    driver.quit()
                except:
                    pass
            
        except Exception as e:
            print(f"Error scraping data: {e}")
            raise e

class GoogleSearchScraper:
    def __init__(self):
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Initialize Chrome driver with webdriver-manager
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            print(f"Error initializing Chrome driver: {e}")
            raise

    def wait_and_find_element(self, by, value, timeout=10):
        """Wait for and find an element with retry logic."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            print(f"Timeout waiting for element: {value}")
            return None

    def scrape_google_results(self, search_query, max_pages=3):
        """Scrape LinkedIn profiles from Google search results, navigating through multiple pages."""
        profiles = []
        try:
            print(f"Starting search with query: {search_query}")
            self.driver.get(search_query)
            time.sleep(3)  # Initial wait for page load
            
            page = 1
            while page <= max_pages:
                print(f"Scraping page {page} of Google results")
                
                # Wait for search results to load
                try:
                    # Try different selectors for search results
                    search_results = []
                    selectors = ['div.g', 'div.tF2Cxc', 'div.yuRUbf']
                    for selector in selectors:
                        search_results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if search_results:
                            break
                    
                    if not search_results:
                        print("No search results found on this page")
                        break
                    
                    print(f"Found {len(search_results)} results on page {page}")
                    
                    for result in search_results:
                        try:
                            # Find LinkedIn profile links
                            link_elem = result.find_element(By.CSS_SELECTOR, 'a')
                            href = link_elem.get_attribute('href')
                            
                            if not href:
                                continue
                                
                            if ('linkedin.com/in/' in href or 'linkedin.com/pub/' in href) and 'linkedin.com/jobs' not in href:
                                print(f"Found LinkedIn profile: {href}")
                                
                                # Get title and description from Google result
                                try:
                                    title = result.find_element(By.CSS_SELECTOR, 'h3').text
                                except NoSuchElementException:
                                    continue
                                    
                                try:
                                    description = result.find_element(By.CSS_SELECTOR, 'div.VwiC3b').text
                                except NoSuchElementException:
                                    description = ''
                                
                                # Extract name and position from title
                                name = title.split(' - ')[0].strip()
                                position = title.split(' - ')[1].strip() if ' - ' in title else ''
                                
                                # Store the data without visiting LinkedIn
                                profile_data = {
                                    'name': name,
                                    'profile_url': href,
                                    'current_position': position,
                                    'description': description[:500]
                                }
                                
                                profiles.append(profile_data)
                                print(f"Added profile data for: {name}")
                                
                                # Random delay between profiles
                                time.sleep(random.uniform(1, 2))
                        
                        except Exception as e:
                            print(f"Error processing search result: {e}")
                            continue
                    
                    # Try to go to next page
                    try:
                        next_button = self.driver.find_element(By.ID, 'pnnext')
                        if not next_button.is_displayed():
                            print("No more pages available")
                            break
                        
                        next_button.click()
                        page += 1
                        time.sleep(random.uniform(2, 3))
                        
                    except NoSuchElementException:
                        print("No more pages available")
                        break
                        
                except Exception as e:
                    print(f"Error processing page {page}: {e}")
                    break
            
            print(f"Successfully scraped {len(profiles)} profiles")
            return profiles
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            return []
            
        finally:
            try:
                self.driver.quit()
            except:
                pass

# Initialize the scraper
scraper_google = None

@app.route('/')
def index():
    """Render the LinkedIn search page."""
    return render_template('index.html')

@app.route('/golden-pages')
def golden_pages():
    """Render the Golden Pages search page."""
    return render_template('golden_pages.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    """Handle the scraping request."""
    try:
        # Get the generated search query
        search_query = request.form.get('query')
        if not search_query:
            return jsonify({'error': 'No search query provided'}), 400
        
        # Initialize a new scraper instance for this request
        global scraper_google
        scraper_google = GoogleSearchScraper()
        
        # Scrape the results
        results = scraper_google.scrape_google_results(search_query)
        
        if not results:
            return jsonify({'error': 'No profiles found'}), 404
        
        # Create output directory if it doesn't exist
        os.makedirs('downloads', exist_ok=True)
        
        # Generate timestamp for unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"downloads/linkedin_profiles_{timestamp}.csv"
        
        # Save to CSV
        df = pd.DataFrame(results)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        return jsonify({
            'success': True,
            'message': f'Successfully scraped {len(results)} profiles',
            'filename': os.path.basename(filename),
            'profiles': results
        })
        
    except Exception as e:
        print(f"Error in scrape route: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    """Download the CSV file."""
    try:
        return send_file(
            f"downloads/{filename}",
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/email_searcher')
def email_searcher():
    """Render the email searcher page."""
    return render_template('email_searcher.html')

@app.route('/search_businesses', methods=['POST'])
def search_businesses():
    """Handle the business search request."""
    what = request.form.get('what', '').strip()
    where = request.form.get('where', '').strip()
    
    if not where:  # 'where' is required, 'what' can be empty
        return jsonify({
            'error': 'Please provide a location to search in'
        }), 400
    
    try:
        print(f"Starting search for businesses: {what} in {where}")
        scraper = GoldenPagesScraper()
        businesses = scraper.scrape_business_data(where=where, what=what)
        
        if not businesses:
            return jsonify({
                'error': f'No businesses found for "{what}" in {where}'
            }), 404
        
        # Create downloads directory if it doesn't exist
        os.makedirs('downloads', exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        search_terms = f"{what}_{where}".lower().replace(' ', '_') if what else f"{where}".lower().replace(' ', '_')
        filename = f"business_data_{search_terms}_{timestamp}.csv"
        filepath = os.path.join('downloads', filename)
        
        # Save to CSV with UTF-8-BOM encoding for Excel compatibility
        df = pd.DataFrame(businesses)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        return jsonify({
            'message': f'Successfully scraped {len(businesses)} businesses',
            'filename': filename,
            'total_results': len(businesses)
        })
        
    except Exception as e:
        print(f"Error in search_businesses: {str(e)}")
        return jsonify({
            'error': f'An error occurred while searching: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 