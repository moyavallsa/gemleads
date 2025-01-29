import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class GoldenPagesScraper:
    def __init__(self):
        self.base_url = "https://www.goldenpages.ie"
        self.session = requests.Session()
        self.headers = {
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
        }
        self.session.headers.update(self.headers)
        
        # Initialize Chrome options for dynamic content
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
        
    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def wait_for_element(self, by, value, timeout=20):
        """Wait for element with increased timeout and better error handling."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                return element
            except TimeoutException:
                if attempt < max_attempts - 1:
                    print(f"Attempt {attempt + 1} failed, retrying...")
                    self.driver.refresh()
                    time.sleep(2)
                else:
                    print(f"Element not found after {max_attempts} attempts: {value}")
                    return None
            except Exception as e:
                print(f"Error waiting for element: {e}")
                return None

    def extract_business_details(self, business_url):
        """Extract detailed business information from a specific business page."""
        try:
            response = self.session.get(business_url)
            if not response.ok:
                return {}

            soup = BeautifulSoup(response.content, 'lxml')
            details = {}

            # Extract business hours
            hours_div = soup.find('div', {'class': 'business-hours'})
            if hours_div:
                details['hours'] = hours_div.get_text(strip=True)

            # Extract payment methods
            payment_div = soup.find('div', {'class': 'payment-methods'})
            if payment_div:
                details['payment_methods'] = payment_div.get_text(strip=True)

            # Extract additional contact info
            contact_div = soup.find('div', {'class': 'contact-info'})
            if contact_div:
                # Extract phone numbers
                phone_links = contact_div.find_all('a', href=lambda x: x and 'tel:' in x)
                details['phone_numbers'] = [link['href'].replace('tel:', '') for link in phone_links]

                # Extract email
                email_link = contact_div.find('a', href=lambda x: x and 'mailto:' in x)
                if email_link:
                    details['email'] = email_link['href'].replace('mailto:', '')

                # Extract website
                website_link = contact_div.find('a', {'class': 'website-link'})
                if website_link:
                    details['website'] = website_link['href']

            # Extract social media links
            social_div = soup.find('div', {'class': 'social-links'})
            if social_div:
                social_links = social_div.find_all('a')
                details['social_media'] = [link['href'] for link in social_links]

            return details

        except Exception as e:
            print(f"Error extracting business details: {e}")
            return {}

    def scrape_business_data(self, what, where):
        """Scrape business data from Golden Pages with improved error handling and pagination."""
        businesses = []
        try:
            print(f"Starting search for {what} in {where}")
            
            # Construct the search URL
            search_url = f"{self.base_url}/q/business/advanced/where/{where.replace(' ', '+')}/what/{what.replace(' ', '+')}/1"
            
            # Get the search results page
            response = self.session.get(search_url)
            if not response.ok:
                return None, f"Failed to access search page: {response.status_code}"

            soup = BeautifulSoup(response.content, 'lxml')
            
            page_num = 1
            while True:
                print(f"Scraping page {page_num}")
                
                # Find all business listings
                listings = soup.find_all('div', {'class': 'listing_container'})
                
                if not listings:
                    print("No listings found on this page")
                    break

                for listing in listings:
                    try:
                        business_data = {}
                        
                        # Get business name and URL
                        title_elem = listing.find('h3', {'class': 'listing_title'})
                        if not title_elem:
                            continue

                        name = title_elem.get_text(strip=True)
                        # Remove leading numbers and "Sponsored" text
                        name = ' '.join(word for word in name.split() if not word.isdigit() and word != "Sponsored")
                        business_data['name'] = name
                        
                        # Get business URL
                        business_url = None
                        title_link = title_elem.find('a')
                        if title_link:
                            business_url = self.base_url + title_link['href'] if title_link['href'].startswith('/') else title_link['href']
                            business_data['url'] = business_url

                        # Get location
                        location = listing.find('div', {'class': 'listing_address'})
                        business_data['location'] = location.get_text(strip=True) if location else ''

                        # Get phone number
                        phone = listing.find('a', {'class': 'link_listing_number'})
                        business_data['phone'] = phone.get_text(strip=True) if phone else ''

                        # Get categories
                        categories = listing.find('div', {'class': 'listing_categories'})
                        business_data['categories'] = categories.get_text(strip=True) if categories else ''

                        # Get description
                        description = listing.find('div', {'class': 'listing_summary'})
                        business_data['description'] = description.get_text(strip=True) if description else ''

                        # Get website
                        links = listing.find('div', {'class': 'listing_links'})
                        if links:
                            website_link = links.find('a', text='Website')
                            if website_link:
                                business_data['website'] = website_link['href']

                        # Get additional details if business URL exists
                        if business_url:
                            additional_details = self.extract_business_details(business_url)
                            business_data.update(additional_details)
                            time.sleep(random.uniform(1, 2))  # Be nice to the server

                        businesses.append(business_data)
                        print(f"Added business: {name}")

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
                    next_url = self.base_url + next_url

                # Get the next page
                response = self.session.get(next_url)
                if not response.ok:
                    print(f"Failed to get next page: {response.status_code}")
                    break

                soup = BeautifulSoup(response.content, 'lxml')
                page_num += 1
                time.sleep(random.uniform(1, 2))  # Be nice to the server

            if not businesses:
                return None, "No businesses found"

            # Create downloads directory if it doesn't exist
            if not os.path.exists('downloads'):
                os.makedirs('downloads')

            # Save to CSV with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"downloads/business_data_{what.lower().replace(' ', '_')}_{where.lower().replace(' ', '_')}_{timestamp}.csv"
            
            df = pd.DataFrame(businesses)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            
            return os.path.basename(filename), f"Successfully scraped {len(businesses)} businesses"

        except Exception as e:
            print(f"Error during scraping: {e}")
            return None, f"Error scraping data: {str(e)}"

        finally:
            # Don't quit the driver here, as it will be reused for subsequent searches
            pass 