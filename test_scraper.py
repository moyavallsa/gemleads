from app import GoogleSearchScraper
import time
import random
import urllib.parse

def test_scraper():
    print("\n=== Starting LinkedIn Profile Scraper Test ===\n")
    
    # LinkedIn credentials
    linkedin_email = input("Enter your LinkedIn email: ")
    linkedin_password = input("Enter your LinkedIn password: ")
    
    try:
        print("Initializing scraper...")
        scraper = GoogleSearchScraper()
        print("✓ Scraper initialized successfully")
        
        # Login to LinkedIn
        if not scraper.login_to_linkedin(linkedin_email, linkedin_password):
            print("Failed to login to LinkedIn. Exiting...")
            return
        
        # Test queries with more targeted search terms
        test_queries = [
            {
                'job': 'Software Engineer',
                'location': 'Dublin',
                'query': 'site:ie.linkedin.com/in/ AND "Software Engineer" AND Dublin AND (email OR "contact me" OR "@gmail.com" OR "@yahoo.com" OR "@hotmail.com")'
            },
            {
                'job': 'Sales Manager',
                'location': 'Dublin',
                'query': 'site:ie.linkedin.com/in/ AND "Sales Manager" AND Dublin AND (email OR "contact me" OR "@gmail.com" OR "@yahoo.com" OR "@hotmail.com")'
            }
        ]
        
        all_results = []
        
        for test in test_queries:
            print(f"\n=== Testing search for {test['job']} in {test['location']} ===")
            
            # Construct Google search URL
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(test['query'])}"
            
            try:
                # Add random delay between searches
                time.sleep(random.uniform(3, 6))
                
                results = scraper.scrape_google_results(search_url, max_pages=2)
                
                if results:
                    all_results.extend(results)
                    print(f"\nResults for this search:")
                    for profile in results:
                        print("\n-------------------")
                        print(f"Name: {profile.get('name', 'N/A')}")
                        print(f"Position: {profile.get('position', 'N/A')}")
                        print(f"Email: {profile.get('email', 'N/A')}")
                        if profile.get('alternate_emails'):
                            print(f"Alternate Emails: {', '.join(profile['alternate_emails'])}")
                        print(f"URL: {profile.get('url', 'N/A')}")
                    
                    print(f"\nFound {len(results)} profiles with contact information")
                
            except Exception as e:
                print(f"Error with search: {str(e)}")
                continue
            
            # Add longer delay between different job searches
            time.sleep(random.uniform(5, 8))
        
        print("\n=== Final Summary ===")
        print(f"Total profiles found: {len(all_results)}")
        
        profiles_with_emails = len([p for p in all_results if p.get('email')])
        print(f"Profiles with primary email: {profiles_with_emails}")
        
        profiles_with_alternate = len([p for p in all_results if p.get('alternate_emails')])
        print(f"Profiles with alternate emails: {profiles_with_alternate}")
        
        # Print success rate
        if all_results:
            success_rate = (profiles_with_emails / len(all_results)) * 100
            print(f"Success rate: {success_rate:.1f}%")
            
    except Exception as e:
        print(f"\nError in test execution: {str(e)}")
        
    finally:
        try:
            scraper.driver.quit()
            print("\nChromeDriver closed successfully")
        except:
            pass
            
if __name__ == "__main__":
    test_scraper() 