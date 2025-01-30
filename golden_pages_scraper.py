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
import re
from email_validator import validate_email, EmailNotValidError

class GoldenPagesScraper:
    def __init__(self):
        self.base_url = "https://www.goldenpages.ie"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        }
        self.session.headers.update(self.headers)
        
        # Initialize rate limiting
        self.last_request_time = 0
        self.min_request_interval = 3  # Seconds between requests

        # Initialize progress tracking
        self.total_processed = 0
        self.successful_scrapes = 0
        self.failed_scrapes = 0
        self.start_time = time.time()

        # Set up downloads directory
        self.downloads_dir = "downloads"
        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir)

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
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

    def wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            print(f"Rate limiting: Waiting {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def make_request_with_retry(self, url, max_retries=3):
        """Make a request with retry logic and proper rate limiting."""
        for attempt in range(max_retries):
            try:
                self.wait_for_rate_limit()
                print(f"Attempt {attempt + 1}: Requesting URL: {url}")
                
                response = self.session.get(url, timeout=15)
                print(f"Response status: {response.status_code}")
                
                if response.ok:
                    return BeautifulSoup(response.content, 'lxml')
                    
                if response.status_code == 429:  # Too Many Requests
                    wait_time = (attempt + 1) * 5
                    print(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                    
                if response.status_code == 403:  # Forbidden
                    print("Access forbidden. Might need to adjust request headers.")
                    break
                    
                time.sleep((attempt + 1) * 2)  # Exponential backoff
                
            except requests.exceptions.RequestException as e:
                print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    
        return None

    def extract_county(self, location_text):
        """Extract county from location text."""
        if not location_text:
            return None
        
        # List of Irish counties
        counties = [
            'Carlow', 'Cavan', 'Clare', 'Cork', 'Donegal', 'Dublin',
            'Galway', 'Kerry', 'Kildare', 'Kilkenny', 'Laois', 'Leitrim',
            'Limerick', 'Longford', 'Louth', 'Mayo', 'Meath', 'Monaghan',
            'Offaly', 'Roscommon', 'Sligo', 'Tipperary', 'Waterford',
            'Westmeath', 'Wexford', 'Wicklow'
        ]
        
        # Look for county in location text
        for county in counties:
            if county.lower() in location_text.lower():
                return county
        
        return None

    def clean_email(self, email):
        """Clean and validate email addresses."""
        if not email:
            return None
            
        try:
            # Remove mailto: prefix and clean
            email = email.replace('mailto:', '').strip().lower()
            
            # Match only the email part before any additional domains
            pattern = r'^([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+?\.(com|ie))'
            match = re.match(pattern, email)
            
            if match:
                clean_email = match.group(1)
                
                # Validate length
                if len(clean_email) > 14:
                    return None
                    
                return clean_email
            
        except Exception as e:
            print(f"Error cleaning email: {e}")
            return None
        
        return None

    def extract_business_details(self, business_url, county):
        """Extract only essential business information: name, phone, email, location."""
        try:
            print(f"\n{'='*50}")
            print(f"Processing business at: {business_url}")
            
            soup = self.make_request_with_retry(business_url)
            if not soup:
                return {}

            details = {
                'name': None,
                'phone': None,
                'email': None,
                'location': None
            }
            
            # Extract business name
            business_name = soup.find('h1')
            if business_name:
                name = business_name.text.strip()
                # Remove any "Sponsored" text and numbers from the start
                name = ' '.join(word for word in name.split() if not word.isdigit() and word != "Sponsored")
                details['name'] = name.strip()
                print(f"Found business name: {details['name']}")

            # Extract phone numbers - only unique numbers
            phone_numbers = set()
            phone_elems = soup.find_all('a', {'class': 'link_listing_number'})
            for phone in phone_elems:
                number = phone.get_text(strip=True)
                if number:
                    phone_numbers.add(number)
            
            if phone_numbers:
                details['phone'] = list(phone_numbers)[0] if phone_numbers else None  # Only keep first phone number
                print(f"Found phone number: {details['phone']}")

            # Extract email - only keep the first valid email
            email_elems = soup.find_all('a', {'href': lambda x: x and 'mailto:' in x})
            for email_elem in email_elems:
                raw_email = email_elem['href'].replace('mailto:', '')
                clean_email = self.clean_email(raw_email)
                if clean_email:
                    details['email'] = clean_email
                    print(f"Found email: {clean_email}")
                    break

            # Extract location
            location_elem = soup.find('div', {'class': 'listing_address'})
            if location_elem:
                details['location'] = location_elem.get_text(strip=True)
                print(f"Found location: {details['location']}")

            print("-"*50)
            print("Summary:")
            print(f"Phone: {'Yes' if details.get('phone') else 'No'}")
            print(f"Email: {'Yes' if details.get('email') else 'No'}")
            print("="*50)

            return details

        except Exception as e:
            print(f"Error extracting business details: {e}")
            return {}

    def scrape_business_data(self, what, where):
        """Scrape business data based on search criteria."""
        try:
            print(f"\nStarting search for {what} in {where}")
            businesses = []
            processed_count = 0
            page_num = 1
            
            while True:
                search_url = f"https://www.goldenpages.ie/q/business/advanced/where/{where}/what/{what}/{page_num}"
                print(f"Searching page {page_num}")
                
                soup = self.make_request_with_retry(search_url)
                if not soup:
                    break
                
                # Extract business listings
                listings = soup.find_all('div', class_='listing')
                
                if not listings:
                    print("No listings found on this page")
                    break
                
                for listing in listings:
                    try:
                        link = listing.find('h2').find('a')
                        if not link:
                            continue
                            
                        business_url = link['href']
                        if not business_url.startswith('http'):
                            business_url = f"https://www.goldenpages.ie{business_url}"
                        
                        business_data = self.extract_business_details(business_url, where)
                        
                        if business_data:
                            businesses.append(business_data)
                            processed_count += 1
                            print(f"Added business: {business_data.get('name', 'Unknown')} ({where}) - Progress: {processed_count}")
                    
                    except Exception as e:
                        print(f"Error processing listing: {str(e)}")
                        continue
                
                # Check if there's a next page
                next_button = soup.find('a', class_='next')
                if not next_button:
                    print("No next page button found")
                    break
                    
                page_num += 1
                time.sleep(3)
            
            if not businesses:
                return None, "No businesses found"
                
            # Save to CSV with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"business_data_{what.lower()}_{where.lower()}_{len(businesses)}results_{timestamp}.csv"
            
            # Create DataFrame with only the required columns
            df = pd.DataFrame(businesses)[['name', 'phone', 'email', 'location']]
            df.to_csv(os.path.join('downloads', filename), index=False, encoding='utf-8-sig')
            
            success_message = f"Successfully scraped {len(businesses)} businesses"
            return filename, success_message
            
        except Exception as e:
            return None, f"Error scraping data: {str(e)}"

    def process_business_page(self, url):
        try:
            soup = self.make_request_with_retry(url)
            if not soup:
                return None

            business_data = {
                'name': None,
                'phone': None,
                'email': None,
                'location': None
            }

            # Extract business name
            name_element = soup.find('h1', class_='business-name')
            if name_element:
                business_data['name'] = name_element.text.strip()

            # Extract phone numbers
            phone_elements = soup.find_all('a', {'data-phone': True})
            phone_numbers = []
            for phone in phone_elements:
                phone_number = phone.get('data-phone')
                if phone_number and phone_number not in phone_numbers:
                    phone_numbers.append(phone_number)
            if phone_numbers:
                business_data['phone'] = ', '.join(phone_numbers)

            # Extract email
            email_elements = soup.find_all('a', href=lambda x: x and 'mailto:' in x)
            cleaned_emails = set()
            for email_elem in email_elements:
                email = email_elem['href'].replace('mailto:', '').strip()
                cleaned = self.clean_email(email)
                if cleaned:
                    cleaned_emails.add(cleaned)
            
            if cleaned_emails:
                business_data['email'] = ', '.join(cleaned_emails)

            # Extract location
            location_element = soup.find('span', class_='address')
            if location_element:
                business_data['location'] = location_element.text.strip()

            return business_data if any(business_data.values()) else None

        except Exception as e:
            print(f"Error processing business page: {str(e)}")
            return None 