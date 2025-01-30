import google.generativeai as genai
from typing import Dict, List, Optional
import pandas as pd
import base64
from config import GEMINI_API_KEY, GEMINI_MODEL, TEMPERATURE
from PIL import Image
import io
import re

class GeminiAnalyzer:
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro-vision')
        self.temperature = TEMPERATURE
        self.businesses = []

    def analyze_business_screenshot(self, screenshot_path: str, business_name: str) -> Dict:
        """
        Analyze a screenshot of a business page and extract structured data.
        
        Args:
            screenshot_path (str): Path to the screenshot image
            business_name (str): Name of the business being analyzed
            
        Returns:
            Dict: Structured business data extracted from the screenshot
        """
        try:
            # Load and prepare the image
            image = Image.open(screenshot_path)
            
            # Create prompt for Gemini
            prompt = f"""
            Analyze this screenshot of the business '{business_name}' and extract the following information in a structured format:
            
            1. Business contact details:
               - Full business name
               - Phone numbers (all available)
               - Email addresses (all available)
               - Website URL
               - Social media links
               - Physical address
            
            2. Business information:
               - Business categories/services
               - Opening hours (if visible)
               - Description of services
               - Areas served
               - Professional certifications/memberships
            
            3. Additional details:
               - Payment methods accepted
               - Languages spoken
               - Years in business
               - Any special features or unique selling points
            
            Please format your response as a structured JSON with these fields (leave empty if not found):
            {{
                "name": "",
                "phone_numbers": [],
                "emails": [],
                "website": "",
                "social_media": {{"facebook": "", "twitter": "", "linkedin": "", "instagram": ""}},
                "address": "",
                "categories": [],
                "opening_hours": "",
                "description": "",
                "areas_served": [],
                "certifications": [],
                "payment_methods": [],
                "languages": [],
                "years_in_business": "",
                "special_features": []
            }}
            """
            
            # Get Gemini's analysis
            response = self.model.generate_content([prompt, image])
            
            # Parse the response and extract the JSON data
            business_data = self._parse_gemini_response(response.text)
            
            # Store the processed business
            self.businesses.append(business_data)
            
            return business_data
            
        except Exception as e:
            print(f"Error analyzing business screenshot: {e}")
            return {}

    def save_to_csv(self, output_file: str) -> None:
        """
        Save all processed businesses to a CSV file.
        
        Args:
            output_file (str): Path to save the CSV file
        """
        try:
            df = pd.DataFrame(self.businesses)
            
            # Convert list and dict columns to strings
            for col in df.columns:
                if df[col].apply(type).eq(list).any() or df[col].apply(type).eq(dict).any():
                    df[col] = df[col].apply(str)
            
            df.to_csv(output_file, index=False)
            print(f"Business data saved to {output_file}")
            
        except Exception as e:
            print(f"Error saving to CSV: {e}")

    def _parse_gemini_response(self, response_text: str) -> Dict:
        """Parse Gemini's JSON response into a dictionary."""
        try:
            # Clean up the response text
            response_text = response_text.strip()
            
            # Try to find a JSON array first (for email abbreviations)
            if response_text.startswith('[') and response_text.endswith(']'):
                import json
                return json.loads(response_text)
            
            # Otherwise look for a JSON object
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
                
            json_str = response_text[start_idx:end_idx]
            
            # Use json.loads instead of eval for safer parsing
            import json
            return json.loads(json_str)
            
        except Exception as e:
            print(f"Error parsing Gemini response: {str(e)}")
            print(f"Response text: {response_text}")
            return []  # Return empty list for email abbreviations, empty dict for other cases

    def clean_domain(self, email: str) -> str:
        """Clean email domain by removing duplicated domains and unwanted suffixes."""
        try:
            if not email or '@' not in email:
                return email
                
            local, domain = email.split('@', 1)
            
            # Remove numbers before 'info'
            if 'info' in local:
                local = re.sub(r'^\d+info', 'info', local)
            
            # Handle common domain duplications
            if '.ie' in domain:
                # Split at first occurrence of .ie and add it back
                base_domain = domain.split('.ie')[0]
                domain = f"{base_domain}.ie"
            elif '.com' in domain:
                # Split at first occurrence of .com and add it back
                base_domain = domain.split('.com')[0]
                domain = f"{base_domain}.com"
                
            return f"{local}@{domain}"
            
        except Exception as e:
            print(f"Error cleaning domain: {e}")
            return email

    def abbreviate_emails(self, emails: List[str]) -> List[Dict[str, str]]:
        """
        Clean email addresses by removing domain duplications and numbers before 'info'.
        
        Args:
            emails (List[str]): List of email addresses to process
            
        Returns:
            List[Dict[str, str]]: List of dictionaries containing original and cleaned emails
        """
        try:
            if not emails:
                return []
                
            # First clean the domains
            cleaned_emails = [self.clean_domain(email) for email in emails if email]
            cleaned_emails = list(set(cleaned_emails))  # Remove duplicates
            
            results = []
            for email in cleaned_emails:
                if not email or '@' not in email:
                    continue
                    
                # Clean the email
                cleaned_email = self.clean_domain(email)
                
                # Check if the email had numbers before 'info' that were removed
                had_numbers = 'info' in email.lower() and re.search(r'^\d+info', email.split('@')[0].lower())
                
                if cleaned_email != email:
                    explanation = []
                    if had_numbers:
                        explanation.append("Removed numbers before 'info'")
                    if cleaned_email.count('.') < email.count('.'):
                        explanation.append("Removed duplicated domain suffix")
                    
                    results.append({
                        "original": email,
                        "abbreviated": cleaned_email,
                        "explanation": " and ".join(explanation)
                    })
                else:
                    results.append({
                        "original": email,
                        "abbreviated": email,
                        "explanation": "No changes needed"
                    })
                
            return results
            
        except Exception as e:
            print(f"Error processing emails: {e}")
            return [] 