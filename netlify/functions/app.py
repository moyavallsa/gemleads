from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import pandas as pd
from datetime import datetime

app = Flask(__name__)

def scrape_business_data(what, where):
    base_url = "https://www.goldenpages.ie"
    search_url = f"{base_url}/q/business/advanced/where/{where}/what/{what}/1"
    
    try:
        response = requests.get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        businesses = []
        listings = soup.find_all('div', class_='listing')
        
        for listing in listings:
            business = {
                'name': listing.find('h2', class_='listing-name').text.strip() if listing.find('h2', class_='listing-name') else '',
                'phone': listing.find('span', class_='phone').text.strip() if listing.find('span', class_='phone') else '',
                'address': listing.find('div', class_='address').text.strip() if listing.find('div', class_='address') else '',
                'category': listing.find('div', class_='category').text.strip() if listing.find('div', class_='category') else ''
            }
            businesses.append(business)
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(businesses)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"business_data_{what}_{where}_{len(businesses)}results_{timestamp}.csv"
        df.to_csv(filename, index=False)
        
        return filename, f"Found {len(businesses)} businesses. Data saved to {filename}"
        
    except Exception as e:
        return None, f"Error: {str(e)}"

@app.route('/search_businesses', methods=['POST'])
def search_businesses():
    data = request.get_json()
    what = data.get('what')
    where = data.get('where')
    
    if not what or not where:
        return jsonify({'error': 'Please provide both business type and location'}), 400
    
    filename, message = scrape_business_data(what, where)
    
    if filename:
        return jsonify({
            'success': True,
            'filename': filename,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gem Leads - Business Search</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            input, button { margin: 10px 0; padding: 8px; width: 100%; }
            button { background: #4CAF50; color: white; border: none; cursor: pointer; }
            button:hover { background: #45a049; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Gem Leads</h1>
            <form id="searchForm">
                <input type="text" id="what" placeholder="Business Type (e.g., Plumber)" required>
                <input type="text" id="where" placeholder="Location (e.g., Dublin)" required>
                <button type="submit">Search</button>
            </form>
            <div id="results"></div>
        </div>
        <script>
            document.getElementById('searchForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const results = document.getElementById('results');
                results.textContent = 'Searching...';
                
                try {
                    const response = await fetch('/search_businesses', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            what: document.getElementById('what').value,
                            where: document.getElementById('where').value
                        })
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        results.textContent = data.message;
                        if (data.filename) {
                            const link = document.createElement('a');
                            link.href = '/download/' + data.filename;
                            link.textContent = 'Download Results';
                            results.appendChild(document.createElement('br'));
                            results.appendChild(link);
                        }
                    } else {
                        results.textContent = data.error || 'An error occurred';
                    }
                } catch (error) {
                    results.textContent = 'An error occurred while processing your request';
                }
            });
        </script>
    </body>
    </html>
    '''

def handler(event, context):
    return app(event, context) 