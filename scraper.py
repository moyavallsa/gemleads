import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Optional
import time
import urllib.parse
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.safari.options import Options
from bs4 import BeautifulSoup

class GoldenPagesScraper:
    BASE_URL = "https://www.goldenpages.ie"
    
    def __init__(self):
        # Set up Safari options
        self.options = Options()
        
        # Initialize the driver
        self.driver = None
        
    def _init_driver(self):
        """Initialize the Safari driver if not already initialized."""
        if self.driver is None:
            self.driver = webdriver.Safari(options=self.options)
            self.driver.set_window_size(1920, 1080)
            
    def _quit_driver(self):
        """Quit the Safari driver if it exists."""
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
        
    def get_towns(self) -> List[str]:
        """Return a list of major Irish towns."""
        towns = [
            'Dublin', 'Cork', 'Galway', 'Limerick', 'Waterford',
            'Drogheda', 'Dundalk', 'Swords', 'Blackrock', 'Tralee',
            'Kilkenny', 'Navan', 'Ennis', 'Carlow', 'Naas',
            'Sligo', 'Monaghan', 'Mullingar', 'Wexford', 'Athlone',
            'Celbridge', 'Clonmel', 'Bray', 'Greystones', 'Malahide'
        ]
        return sorted(towns)

    def _add_random_delay(self, min_seconds=1, max_seconds=3):
        """Add a random delay between actions to appear more human-like."""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def scrape_business_data(self, town: str) -> List[Dict]:
        """Scrape business data for a specific town."""
        businesses = []
        try:
            self._init_driver()
            
            # Navigate to the homepage
            self.driver.get(self.BASE_URL)
            self._add_random_delay()
            
            # Find and fill the search form
            try:
                # Wait for the search input to be present
                location_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "where"))
                )
                location_input.clear()
                location_input.send_keys(town)
                self._add_random_delay(0.5, 1)
                location_input.send_keys(Keys.RETURN)
                
            except TimeoutException:
                raise Exception("Could not find the search form")
            
            # Wait for results to load
            time.sleep(3)  # Give time for the results to load
            
            page_num = 1
            while True:
                print(f"Scraping page {page_num} for {town}...")
                
                try:
                    # Wait for listings to be present
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "listing"))
                    )
                except TimeoutException:
                    print("No listings found or page took too long to load")
                    break
                
                # Get the page source and parse with BeautifulSoup
                soup = BeautifulSoup(self.driver.page_source, 'lxml')
                
                # Find all business listings
                listings = soup.find_all('div', class_='listing')
                
                if not listings:
                    print("No more listings found")
                    break
                
                for listing in listings:
                    try:
                        # Extract business information
                        business = {
                            'Name': self._safe_extract(listing, 'h2.listing-title'),
                            'Business Type': self._safe_extract(listing, 'p.category'),
                            'Location': self._safe_extract(listing, 'p.address'),
                            'Phone Number': self._safe_extract(listing, 'p.phone'),
                            'Email': self._safe_extract(listing, 'p.email')
                        }
                        
                        if any(business.values()):
                            businesses.append(business)
                            
                    except Exception as e:
                        print(f"Error processing listing: {e}")
                        continue
                
                # Check for next page
                try:
                    next_button = self.driver.find_element(By.CLASS_NAME, "next")
                    if not next_button.is_displayed() or not next_button.is_enabled():
                        break
                    next_button.click()
                    self._add_random_delay()
                    page_num += 1
                except NoSuchElementException:
                    break
                except Exception as e:
                    print(f"Error navigating to next page: {e}")
                    break
                
        except Exception as e:
            print(f"Error scraping data: {e}")
            raise e
        
        finally:
            self._quit_driver()
        
        return businesses

    def _safe_extract(self, element: BeautifulSoup, selector: str) -> str:
        """Safely extract text from an HTML element."""
        try:
            found = element.select_one(selector)
            return found.get_text(strip=True) if found else ''
        except Exception:
            return ''

class ScraperGUI:
    def __init__(self):
        self.scraper = GoldenPagesScraper()
        self.root = tk.Tk()
        self.root.title("Golden Pages Scraper")
        self.root.geometry("500x400")
        self.setup_gui()

    def setup_gui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Golden Pages Business Scraper",
            font=('Helvetica', 14, 'bold')
        )
        title_label.pack(pady=10)

        # Town selection
        town_frame = ttk.Frame(main_frame)
        town_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(town_frame, text="Select Town:").pack(side=tk.LEFT, padx=5)
        self.town_var = tk.StringVar()
        self.town_dropdown = ttk.Combobox(
            town_frame, 
            textvariable=self.town_var,
            values=self.scraper.get_towns(),
            state='readonly',
            width=30
        )
        self.town_dropdown.pack(side=tk.LEFT, padx=5)

        # Progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress_label = ttk.Label(progress_frame, text="")
        self.progress_label.pack(pady=5)

        # Log area
        self.log_area = scrolledtext.ScrolledText(
            main_frame,
            height=10,
            width=50,
            wrap=tk.WORD,
            font=('Courier', 9)
        )
        self.log_area.pack(pady=10, fill=tk.BOTH, expand=True)

        # Scrape button
        self.scrape_button = ttk.Button(
            main_frame,
            text="Scrape Data",
            command=self.start_scraping
        )
        self.scrape_button.pack(pady=10)

    def log_message(self, message: str):
        """Add a message to the log area."""
        self.log_area.insert(tk.END, f"{message}\n")
        self.log_area.see(tk.END)
        self.root.update()

    def start_scraping(self):
        town = self.town_var.get()
        if not town:
            messagebox.showerror("Error", "Please select a town")
            return

        try:
            # Update UI
            self.scrape_button.config(state='disabled')
            self.progress_label.config(text=f"Scraping data for {town}...")
            self.log_area.delete(1.0, tk.END)
            self.root.update()
            
            # Log start
            self.log_message(f"Starting scrape for {town}...")
            
            # Perform scraping
            businesses = self.scraper.scrape_business_data(town)
            
            if not businesses:
                self.log_message("No businesses found.")
                messagebox.showerror("Error", f"No businesses found in {town}")
                return

            # Create DataFrame and save to CSV
            df = pd.DataFrame(businesses)
            filename = f"business_data_{town.lower().replace(' ', '_')}.csv"
            df.to_csv(filename, index=False)
            
            # Log completion
            self.log_message(f"Successfully scraped {len(businesses)} businesses.")
            self.log_message(f"Data saved to: {filename}")
            
            # Show success message
            messagebox.showinfo(
                "Success", 
                f"Successfully scraped {len(businesses)} businesses in {town}.\n"
                f"Data saved to: {filename}"
            )
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            self.scrape_button.config(state='normal')
            self.progress_label.config(text="")
            self.root.update()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ScraperGUI()
    app.run() 