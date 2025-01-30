from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import os
from datetime import datetime
import time
import random
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import argparse
from shutil import which
from gemini_analyzer import GeminiAnalyzer
from pathlib import Path
from golden_pages_scraper import GoldenPagesScraper

app = Flask(__name__)

# Configure downloads directory
DOWNLOADS_DIR = os.environ.get('DOWNLOADS_DIR', str(Path.home() / "Downloads"))
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

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
            'Upgrade-Insecure-Requests': '1'
        }
        self.session.headers.update(self.headers)
        
        # Optional Selenium WebDriver initialization
        self.driver = None
        try:
            # Initialize Chrome options for dynamic content
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Try to initialize WebDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Selenium WebDriver initialized successfully.")
        except Exception as e:
            print(f"Could not initialize Selenium WebDriver. Falling back to requests-based scraping: {e}")
        
        # Initialize rate limiting
        self.last_request_time = 0
        self.min_request_interval = 2  # seconds

        # Initialize progress tracking
        self.total_processed = 0
        self.successful_scrapes = 0
        self.failed_scrapes = 0
        self.start_time = time.time()

        # Initialize proxy support (disabled by default)
        self.proxies = []  # Empty list means no proxies
        self.current_proxy_index = 0
        self.use_proxies = False  # Disabled by default

        # Website extraction patterns
        self.website_patterns = [
            {'class': 'business-website-button'},
            {'class': 'website-button'},
            {'class': 'visit-website'},
            {'class': 'website-url'},
            {'data-type': 'website'},
            {'rel': 'nofollow', 'href': True},
            {'target': '_blank', 'href': True}
        ]

        # Email extraction patterns
        self.email_patterns = [
            r'[\w\.-]+\s*@\s*[\w\.-]+\.\w+',  # Standard email with optional spaces
            r'[\w\.-]+\[at\][\w\.-]+\.\w+',    # [at] format
            r'[\w\.-]+\(at\)[\w\.-]+\.\w+',    # (at) format
            r'[\w\.-]+AT[\w\.-]+DOT\w+',       # AT and DOT format
            r'[\w\.-]+\s*@\s*(?:gmail|yahoo|hotmail|outlook|live|icloud|me|eircom)\.(?:com|ie)'  # Common providers
        ]
        
        # Set up downloads directory
        self.downloads_dir = DOWNLOADS_DIR
        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir)

    def __del__(self):
        # Safely close the WebDriver if it exists
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"Error closing WebDriver: {e}")

    def rotate_proxy(self):
        """Rotate to next proxy if enabled."""
        if self.use_proxies and self.proxies:
            proxy = self.proxies[self.current_proxy_index]
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            print(f"Rotated to proxy: {proxy}")
        else:
            self.session.proxies = {}  # Clear any existing proxies

    def wait_for_rate_limit(self):
        """Wait to respect rate limiting."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        self.last_request_time = time.time()

    def make_request_with_retry(self, url, max_retries=3):
        """Make request with retry logic."""
        for attempt in range(max_retries):
            try:
                self.wait_for_rate_limit()
                print(f"Attempt {attempt + 1}: Requesting URL: {url}")
                
                # Add more headers to mimic browser
                headers = self.headers.copy()
                headers['Referer'] = self.base_url
                headers['Origin'] = self.base_url
                
                response = self.session.get(url, headers=headers, timeout=15)
                
                print(f"Response status: {response.status_code}")
                
                if response.ok:
                    # Log response content length for debugging
                    print(f"Response content length: {len(response.content)} bytes")
                    return response
                
                if response.status_code == 403:  # Forbidden - likely IP block
                    print("Received 403 Forbidden. Rotating proxy...")
                    self.rotate_proxy()
                
                if response.status_code == 429:  # Too Many Requests
                    print("Rate limited. Waiting before retry...")
                    time.sleep(5 * (attempt + 1))
                
                time.sleep((attempt + 1) * 2)  # Exponential backoff
            
            except requests.exceptions.RequestException as e:
                print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                if isinstance(e, requests.exceptions.ConnectionError):
                    print("Connection error. Checking network...")
                elif isinstance(e, requests.exceptions.Timeout):
                    print("Request timed out. Checking connection...")
                
                if attempt == max_retries - 1:
                    raise
                
                self.rotate_proxy()  # Try a different proxy
                time.sleep((attempt + 1) * 2)
        
        return None

    def update_progress(self, success=True):
        """Update progress metrics."""
        self.total_processed += 1
        if success:
            self.successful_scrapes += 1
        else:
            self.failed_scrapes += 1
        elapsed_time = time.time() - self.start_time
        rate = self.total_processed / elapsed_time if elapsed_time > 0 else 0
        print(f"Processed: {self.total_processed}, Success: {self.successful_scrapes}, "
              f"Failed: {self.failed_scrapes}, Rate: {rate:.2f}/s")

    def validate_business_data(self, data):
        """Validate scraped business data."""
        required_fields = ['name', 'location', 'county']
        for field in required_fields:
            if not data.get(field):
                return False
                
        if 'website' in data:
            if not self.is_valid_website(data['website']):
                data.pop('website')
                
        if 'email' in data:
            if not self.is_valid_email(data['email']):
                data.pop('email')
                
        return True

    def extract_business_details(self, business_url, county):
        """Extract detailed business information from a specific business page."""
        try:
            print("\n" + "="*50)
            print(f"Processing business at: {business_url}")
            
            response = self.make_request_with_retry(business_url)
            if not response:
                return {}

            soup = BeautifulSoup(response.content, 'lxml')
            details = {}
            
            # Extract business name
            business_name = soup.find('h1')
            if business_name:
                details['name'] = business_name.text.strip()
                print(f"Found business name: {details['name']}")

            # Extract phone numbers
            phone_patterns = [
                ('a', {'href': lambda x: x and 'tel:' in x}),
                (['span', 'div', 'p'], {'class': lambda x: x and any(term in str(x).lower() for term in ['phone', 'tel', 'mobile', 'contact'])}),
                (['span', 'div', 'p'], {'text': lambda x: x and any(term in str(x).lower() for term in ['phone:', 'tel:', 'mobile:', 'call:'])})
            ]
            
            found_phones = set()
            for tag, attrs in phone_patterns:
                elements = soup.find_all(tag, attrs)
                for elem in elements:
                    if 'href' in elem.attrs and 'tel:' in elem['href']:
                        phone = elem['href'].replace('tel:', '').strip()
                        found_phones.add(phone)
                    else:
                        text = elem.get_text(strip=True)
                        phone_matches = re.findall(r'[\(]?\d{2,3}[\)]?\s*\d{3,4}[\s-]?\d{4}', text)
                        found_phones.update(phone_matches)
            
            if found_phones:
                phones = list(found_phones)
                details['phone'] = phones[0]
                if len(phones) > 1:
                    details['additional_phones'] = phones[1:]
                print(f"Found phone number(s): {phones}")

            # Extract email addresses with proper domain handling
            email_patterns = [
                ('a', {'href': lambda x: x and 'mailto:' in x}),
                (['span', 'div', 'p'], {'class': lambda x: x and any(term in str(x).lower() for term in ['email', 'mail', 'contact'])}),
                (['span', 'div', 'p'], {'text': lambda x: x and 'email' in str(x).lower()})
            ]
            
            found_emails = set()
            for tag, attrs in email_patterns:
                elements = soup.find_all(tag, attrs)
                for elem in elements:
                    if 'href' in elem.attrs and 'mailto:' in elem['href']:
                        email = elem['href'].replace('mailto:', '').strip()
                        # Extract email up to first .com or .ie
                        if '.com' in email:
                            email = email.split('.com')[0] + '.com'
                        elif '.ie' in email:
                            email = email.split('.ie')[0] + '.ie'
                        if email:
                            found_emails.add(email.lower())
                    else:
                        text = elem.get_text(strip=True)
                        # Extract emails and clean them
                        email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}', text)
                        for email in email_matches:
                            if '.com' in email:
                                email = email.split('.com')[0] + '.com'
                            elif '.ie' in email:
                                email = email.split('.ie')[0] + '.ie'
                            if email:
                                found_emails.add(email.lower())
            
            if found_emails:
                emails = list(found_emails)
                details['email'] = emails[0]
                if len(emails) > 1:
                    details['additional_emails'] = emails[1:]
                print(f"Found email(s): {emails}")

            # Extract website
            website_elements = soup.find_all('a', href=True)
            for elem in website_elements:
                href = elem['href'].lower()
                if (
                    ('website' in str(elem).lower() or 'globe' in str(elem).lower()) and
                    href.startswith('http') and
                    'goldenpages' not in href and
                    'facebook' not in href and
                    'twitter' not in href and
                    'linkedin' not in href
                ):
                    details['website'] = href
                    print(f"Found website: {href}")
                    break

            # Extract location and categories
            location_elem = soup.find(['div', 'span', 'p'], {'class': lambda x: x and 'address' in str(x).lower()})
            if location_elem:
                details['location'] = location_elem.get_text(strip=True)
                print(f"Found location: {details['location']}")

            categories_elem = soup.find(['div', 'span'], {'class': lambda x: x and 'categor' in str(x).lower()})
            if categories_elem:
                details['categories'] = categories_elem.get_text(strip=True)
                print(f"Found categories: {details['categories']}")

            # Add county information
            if county:
                details['county'] = county

            # Summary
            print("-"*50)
            print("Summary:")
            print(f"Phone: {'Yes' if 'phone' in details else 'No'}")
            print(f"Email: {'Yes' if 'email' in details else 'No'}")
            print(f"Website: {'Yes' if 'website' in details else 'No'}")
            print("="*50 + "\n")

            return details

        except Exception as e:
            print(f"Error extracting business details: {e}")
            return {}

    def is_valid_email(self, email):
        """Validate email format and domain."""
        if not email:
            return False
        
        # Common email domains to look for
        valid_domains = [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'live.com', 'icloud.com', 'me.com', 'yahoo.ie', 'hotmail.ie',
            'eircom.net', 'gmail.ie', 'googlemail.com', 'apple.com'
        ]
        
        try:
            # Basic pattern matching
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return False
            
            # Check domain
            domain = email.split('@')[1].lower()
            if domain in valid_domains:
                return True
                
            # Also accept business domains (anything not in common domains)
            return True
            
        except:
            return False

    def is_valid_website(self, url):
        """
        Validate website URL with strict rules.
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid website URL, False otherwise
        """
        if not url:
            return False
            
        try:
            # Clean the URL
            url = url.strip().lower()
            
            # Must start with http or https
            if not url.startswith(('http://', 'https://')):
                return False
            
            # Exclude common non-website URLs
            excluded_domains = [
                'goldenpages.ie',
                'getlocal.ie',
                'go.gpi.ie',
                'tel:',
                'mailto:',
                'javascript:',
                'whatsapp:',
                'facebook.com/goldenpages',
                'twitter.com/goldenpages',
                'instagram.com/goldenpages',
                'linkedin.com/company/golden-pages',
                'youtube.com/goldenpages',
                'pinterest.com/goldenpages'
            ]
            
            # Check if it's not a Golden Pages related link
            if any(domain in url for domain in excluded_domains):
                return False
            
            # Basic URL validation
            parsed = urllib.parse.urlparse(url)
            
            # Check for valid scheme and netloc (domain)
            if not all([parsed.scheme in ['http', 'https'], parsed.netloc]):
                return False
            
            # Check for suspicious or invalid domains
            suspicious_patterns = [
                r'\.php\?',  # PHP with query parameters
                r'redirect',  # Redirect URLs
                r'click\.php',  # Click trackers
                r'track\.php',  # Tracking scripts
                r'goto\.',  # Goto redirects
                r'ad\.php',  # Ad scripts
                r'/ads/',  # Ad directories
                r'banner\.php',  # Banner scripts
            ]
            
            if any(re.search(pattern, url) for pattern in suspicious_patterns):
                return False
            
            # Check for common file extensions that aren't websites
            invalid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx']
            if any(url.endswith(ext) for ext in invalid_extensions):
                return False
            
            return True
            
        except:
            return False

    def extract_email_from_text(self, text):
        """Extract email from text content."""
        if not text:
            return None
            
        found_emails = set()
        
        # Clean text
        text = text.lower()
        text = text.replace(' at ', '@').replace('[at]', '@').replace('(at)', '@')
        text = text.replace(' dot ', '.').replace('[dot]', '.').replace('(dot)', '.')
        text = text.replace('AT', '@').replace('DOT', '.')
        text = text.replace(' @ ', '@').replace(' . ', '.')
        
        # Common email domains
        domains = [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'live.com', 'icloud.com', 'me.com', 'yahoo.ie', 'hotmail.ie',
            'eircom.net', 'gmail.ie', 'googlemail.com', 'apple.com'
        ]
        
        # Pattern 1: Look for standard email format with common domains
        for domain in domains:
            pattern = rf'[\w\.-]+@{re.escape(domain)}'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for email in matches:
                if self.is_valid_email(email):
                    found_emails.add(email.lower())

        # Pattern 2: Look for any valid email format
        pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        matches = re.findall(pattern, text)
        for email in matches:
            if self.is_valid_email(email):
                found_emails.add(email.lower())

        # Pattern 3: Look for obfuscated emails
        obfuscated_patterns = [
            r'[\w\.-]+\s*(?:@|\[at\]|\(at\)|AT)\s*[\w\.-]+\s*(?:\.|\[dot\]|\(dot\)|DOT)\s*\w+',
            r'[\w\.-]+\s*@\s*[\w\.-]+\s*\.\s*\w+',
            r'[\w\.-]+\s*\[at\]\s*[\w\.-]+\s*\[dot\]\s*\w+'
        ]
        
        for pattern in obfuscated_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = match.replace('[at]', '@').replace('(at)', '@').replace('AT', '@')
                cleaned = cleaned.replace('[dot]', '.').replace('(dot)', '.').replace('DOT', '.')
                cleaned = cleaned.replace(' ', '')
                if self.is_valid_email(cleaned):
                    found_emails.add(cleaned.lower())

        return list(found_emails) if found_emails else None

    def scrape_business_data(self, what, where):
        """Scrape business data from Golden Pages with improved pagination and county filtering."""
        businesses = []
        seen_urls = set()  # To avoid duplicate business URLs
        seen_websites = set()  # To track seen website URLs
        try:
            print(f"Starting search for {what} in {where}")
            
            # Validate inputs
            if not what or not where:
                raise ValueError("Both 'what' and 'where' parameters are required")
            
            # Reset progress tracking
            self.total_processed = 0
            self.successful_scrapes = 0
            self.failed_scrapes = 0
            self.start_time = time.time()
            
            # Construct the search URL
            search_url = f"{self.base_url}/q/business/advanced/where/{urllib.parse.quote(where.replace(' ', '+'))}/what/{urllib.parse.quote(what.replace(' ', '+'))}/1"
            print(f"Search URL: {search_url}")
            
            # Get the search results page with retry
            response = self.make_request_with_retry(search_url)
            if not response:
                raise ConnectionError(f"Failed to access search page for URL: {search_url}")

            # Parse the initial page to get total results
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find the total results count
            results_info = soup.find('div', {'class': 'results_info'})
            if results_info:
                results_text = results_info.get_text(strip=True)
                total_results = re.search(r'of\s+(\d+)\s+results?', results_text)
                if total_results:
                    total_count = int(total_results.group(1))
                    print(f"Found {total_count} total results")
                else:
                    total_count = 0
            else:
                listings = soup.find_all('div', {'class': 'listing_container'})
                total_count = len(listings)
                print(f"No results counter found, but found {total_count} listings on first page")

            if total_count == 0:
                return None, f"No businesses found for {what} in {where}"

            page_num = 1
            while True:
                print(f"Scraping page {page_num}")
                
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
                            
                            # Skip if we've already seen this exact business URL
                            if business_url in seen_urls:
                                continue
                            seen_urls.add(business_url)

                        # Get location and extract county
                        location = listing.find('div', {'class': 'listing_address'})
                        location_text = location.get_text(strip=True) if location else ''
                        business_data['location'] = location_text
                        county = self.extract_county(location_text)
                        
                        # Only process businesses in the specified county
                        if county and county.lower() != where.lower():
                            continue

                        business_data['county'] = county

                        # Get categories
                        categories = listing.find('div', {'class': 'listing_categories'})
                        business_data['categories'] = categories.get_text(strip=True) if categories else ''

                        # Get additional details if business URL exists
                        if business_url:
                            additional_details = self.extract_business_details(business_url, county)
                            if additional_details:
                                # First, try to extract website from info@ email
                                if 'email' in additional_details:
                                    email = additional_details['email'].lower()
                                    if email.startswith('info@'):
                                        domain = email.split('@')[1]
                                        website = f"https://www.{domain}"
                                        if self.is_valid_website(website):
                                            # Only add the website if we haven't seen it before
                                            if website.lower() not in seen_websites:
                                                additional_details['website'] = website
                                                seen_websites.add(website.lower())
                                                print(f"Extracted website from email: {website}")

                                # Then check the scraped website
                                if 'website' in additional_details:
                                    website = additional_details['website'].lower()
                                    if website in seen_websites:
                                        # If we've seen this website before, remove it from the details
                                        print(f"Duplicate website found: {website} - leaving website field blank")
                                        additional_details.pop('website')
                                    else:
                                        seen_websites.add(website)

                                # Update business data with all other details
                                for key, value in additional_details.items():
                                    if value:  # Only add non-empty values
                                        business_data[key] = value

                        # Validate and add the business data
                        if self.validate_business_data(business_data):
                            businesses.append(business_data)
                            self.update_progress(success=True)
                            print(f"Added business: {name} ({county}) - Progress: {len(businesses)}/{total_count}")
                            if business_data.get('website'):
                                print(f"Found website: {business_data['website']}")
                            if business_data.get('email'):
                                print(f"Found email: {business_data['email']}")
                        else:
                            self.update_progress(success=False)
                            print(f"Skipped invalid business data: {name}")

                    except Exception as e:
                        print(f"Error processing listing: {e}")
                        self.update_progress(success=False)
                        continue

                # Look for next page
                next_button = soup.find('button', {
                    'class': 'btn_normal btn_pagination clickable',
                    'id': 'btn_pagination_next'
                })
                
                if not next_button:
                    print("No next page button found")
                    break

                next_url = next_button.get('data-url')
                if not next_url:
                    print("No next page URL found")
                    break

                if not next_url.startswith('http'):
                    next_url = self.base_url + next_url

                print(f"Moving to next page: {next_url}")
                
                response = self.make_request_with_retry(next_url)
                if not response:
                    print("Failed to get next page")
                    break

                soup = BeautifulSoup(response.content, 'lxml')
                page_num += 1

            if not businesses:
                return None, "No businesses found"

            # Save to CSV with timestamp and total count
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"business_data_{what.lower().replace(' ', '_')}_{where.lower().replace(' ', '_')}_{len(businesses)}results_{timestamp}.csv"
            
            # Define column order
            columns = ['name', 'phone', 'email', 'website', 'location', 'county', 'categories']
            
            # Create DataFrame with specified column order
            df = pd.DataFrame(businesses)
            
            # Reorder columns, only including those that exist
            existing_columns = [col for col in columns if col in df.columns]
            df = df[existing_columns]
            
            # Save to CSV in Downloads folder
            full_path = os.path.join(self.downloads_dir, filename)
            df.to_csv(full_path, index=False, encoding='utf-8-sig')
            
            return os.path.basename(filename), (
                f"Successfully scraped {len(businesses)} businesses in {where}. "
                f"Success rate: {(self.successful_scrapes / self.total_processed * 100):.1f}% "
                f"({self.successful_scrapes}/{self.total_processed})"
            )

        except Exception as e:
            print(f"Error during scraping: {e}")
            return None, f"Error scraping data: {str(e)}"

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
        
        # Clean and split the location text
        location_parts = location_text.replace(',', '').split()
        
        # Look for county in location parts
        for county in counties:
            if county.lower() in [part.lower() for part in location_parts]:
                return county
                
        return None

    def scrape_entire_sitemap(self, output_file='full_golden_pages_businesses.csv', max_businesses=10):
        """
        Simplified sitemap scraping for debugging.
        
        Args:
            output_file (str): Filename to save the complete business data
            max_businesses (int, optional): Limit the number of businesses to scrape
        
        Returns:
            tuple: (filename, total_businesses_scraped, errors)
        """
        print("Starting sitemap scraping...")
        sitemap_url = f"{self.base_url}/business/sitemap"
        
        # Ensure downloads directory exists
        os.makedirs('downloads', exist_ok=True)
        logging_file = os.path.join('downloads', 'sitemap_debug_log.txt')
        
        # Track scraping progress
        total_businesses = 0
        successful_businesses = 0
        errors = []
        all_businesses = []
        
        try:
            # Open logging file
            with open(logging_file, 'w', encoding='utf-8') as log_file:
                def log(message):
                    print(message)
                    log_file.write(message + '\n')
                    log_file.flush()
                
                log(f"Fetching sitemap from: {sitemap_url}")
                
                # Fetch sitemap page
                response = self.make_request_with_retry(sitemap_url)
                if not response:
                    log("Failed to fetch sitemap!")
                    return None, None, "Could not access sitemap"
                
                # Parse sitemap
                soup = BeautifulSoup(response.content, 'lxml')
                
                # Find business links
                business_links = soup.find_all('a', href=lambda href: href and '/business/' in href)
                log(f"Found {len(business_links)} potential business pages")
                
                # Limit businesses for testing
                business_links = business_links[:max_businesses]
                
                for link in business_links:
                    try:
                        business_url = link['href']
                        if not business_url.startswith('http'):
                            business_url = f"{self.base_url}{business_url}"
                        
                        log(f"Processing business URL: {business_url}")
                        
                        # Extract business details
                        business_details = self.extract_business_details(business_url, None)
                        
                        if business_details:
                            business_details['source_url'] = business_url
                            all_businesses.append(business_details)
                            successful_businesses += 1
                            log(f"Successfully scraped: {business_details.get('name', 'Unknown Business')}")
                        
                        total_businesses += 1
                        
                        # Small delay to be respectful
                        time.sleep(0.5)
                    
                    except Exception as e:
                        log(f"Error processing business: {e}")
                        errors.append({'url': business_url, 'error': str(e)})
                
                # Save to CSV
                if all_businesses:
                    df = pd.DataFrame(all_businesses)
                    full_path = os.path.join('downloads', output_file)
                    df.to_csv(full_path, index=False, encoding='utf-8-sig')
                    log(f"Saved {len(all_businesses)} businesses to {full_path}")
                
                return (
                    output_file, 
                    {
                        'total_processed': total_businesses,
                        'successful': successful_businesses,
                        'errors': len(errors)
                    },
                    errors
                )
        
        except Exception as e:
            print(f"Sitemap scraping failed: {e}")
            return None, None, str(e)

# Initialize the scraper
scraper = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search_businesses', methods=['POST'])
def search_businesses():
    data = request.get_json()
    if not data or 'what' not in data or 'where' not in data:
        return jsonify({'error': 'Please provide both business type and location'}), 400
        
    what = data['what']
    where = data['where']
    
    scraper = GoldenPagesScraper()
    filename, message = scraper.scrape_business_data(what, where)
    
    if filename:
        # Clean any email addresses during scraping
        file_path = os.path.join(DOWNLOADS_DIR, filename)
        
        if os.path.exists(file_path):
            # Read the CSV
            df = pd.read_csv(file_path)
            
            # Clean emails if they exist
            if 'email' in df.columns:
                df['email'] = df['email'].apply(lambda x: clean_email(x) if pd.notnull(x) else x)
            
            # Save back to CSV
            df.to_csv(file_path, index=False)
        
        return jsonify({
            'success': True,
            'message': message,
            'filename': filename
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400

def clean_email(email: str) -> str:
    """Clean email by removing numbers before 'info' and fixing domain duplications."""
    try:
        if not email or '@' not in email:
            return email
            
        local, domain = email.split('@', 1)
        
        # Remove numbers before 'info'
        if 'info' in local:
            local = re.sub(r'^\d+info', 'info', local)
        
        # Handle common domain duplications
        if '.ie' in domain:
            base_domain = domain.split('.ie')[0]
            domain = f"{base_domain}.ie"
        elif '.com' in domain:
            base_domain = domain.split('.com')[0]
            domain = f"{base_domain}.com"
            
        return f"{local}@{domain}"
        
    except Exception as e:
        print(f"Error cleaning email: {e}")
        return email

@app.route('/download/<filename>')
def download(filename):
    """Download the CSV file."""
    try:
        file_path = os.path.join(DOWNLOADS_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found: {filename}'}), 404
            
        return send_file(
            file_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/scrape_sitemap', methods=['POST'])
def scrape_sitemap():
    print("Sitemap scraping route triggered!")
    try:
        global scraper
        if scraper is None:
            print("Initializing new scraper...")
            scraper = GoldenPagesScraper()
        
        print("Calling scrape_entire_sitemap method...")
        filename, stats, errors = scraper.scrape_entire_sitemap()
        
        print(f"Scraping result - Filename: {filename}")
        print(f"Scraping result - Stats: {stats}")
        print(f"Scraping result - Errors: {errors}")
        
        if filename:
            return jsonify({
                'success': True,
                'filename': filename,
                'stats': stats,
                'errors': errors
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Sitemap scraping failed'
            }), 500
    
    except Exception as e:
        print(f"Sitemap scraping route error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/scrape')
def scrape():
    what = request.args.get('what')
    where = request.args.get('where')
    
    if not what or not where:
        return jsonify({'error': 'Please provide both business type and location'}), 400
    
    global scraper
    if scraper is None:
        scraper = GoldenPagesScraper()
    
    filename, message = scraper.scrape_business_data(what, where)
    
    if filename:
        return jsonify({
            'success': True,
            'message': message,
            'filename': filename
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')  # Set a good size for screenshots
    return webdriver.Chrome(options=chrome_options)

def scrape_business(driver, url, analyzer):
    try:
        driver.get(url)
        time.sleep(2)  # Wait for page to load
        
        # Take screenshot of the business page
        screenshot_path = f"screenshots/{int(time.time())}.png"
        os.makedirs("screenshots", exist_ok=True)
        driver.save_screenshot(screenshot_path)
        
        # Get business name for the analyzer
        business_name = driver.find_element(By.CSS_SELECTOR, 'h1').text
        
        # Use Gemini to analyze the screenshot and extract data
        business_data = analyzer.analyze_business_screenshot(screenshot_path, business_name)
        
        # Clean up screenshot after analysis
        os.remove(screenshot_path)
        
        return business_data
        
    except Exception as e:
        print(f"Error scraping business: {e}")
        return None

def scrape_search_results(search_term, location):
    analyzer = GeminiAnalyzer()
    driver = setup_driver()
    
    try:
        # Format the search URL
        search_url = f"https://www.goldenpages.ie/q/{search_term}/{location}/"
        driver.get(search_url)
        time.sleep(2)
        
        # Get all business links
        business_links = driver.find_elements(By.CSS_SELECTOR, '.listing h2 a')
        business_urls = [link.get_attribute('href') for link in business_links]
        
        print(f"Found {len(business_urls)} businesses to process")
        
        # Process each business
        for url in business_urls:
            print(f"Processing business at {url}")
            business_data = scrape_business(driver, url, analyzer)
            if business_data:
                print(f"Successfully processed business: {business_data.get('name', 'Unknown')}")
        
        # Save all processed businesses to CSV
        analyzer.save_to_csv(f"results_{search_term}_{location}.csv")
        
    except Exception as e:
        print(f"Error during scraping: {e}")
    
    finally:
        driver.quit()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5007))
    app.run(host='0.0.0.0', port=port) 