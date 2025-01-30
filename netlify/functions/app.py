from flask import Flask, request, jsonify, Response
from bs4 import BeautifulSoup
import requests
import pandas as pd
from datetime import datetime
import json
import base64

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
        
        # Create DataFrame
        df = pd.DataFrame(businesses)
        
        # Instead of saving to file, return the data directly
        return {
            'success': True,
            'data': businesses,
            'message': f"Found {len(businesses)} businesses"
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def handler(event, context):
    """Netlify function handler"""
    
    # Handle OPTIONS request for CORS
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 204,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'
            }
        }
    
    # Handle GET request - serve the HTML page
    if event['httpMethod'] == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*'
            },
            'body': '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Gem Leads - Business Search</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                    .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                    h1 { color: #2c3e50; text-align: center; }
                    input, button { margin: 10px 0; padding: 12px; width: 100%; border: 1px solid #ddd; border-radius: 4px; }
                    button { background: #3498db; color: white; border: none; cursor: pointer; font-weight: bold; }
                    button:hover { background: #2980b9; }
                    #results { margin-top: 20px; padding: 10px; }
                    .business-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 4px; }
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
                        results.innerHTML = '<p>Searching...</p>';
                        
                        try {
                            const response = await fetch('/.netlify/functions/app', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    what: document.getElementById('what').value,
                                    where: document.getElementById('where').value
                                })
                            });
                            
                            const data = await response.json();
                            if (data.success) {
                                results.innerHTML = `<h3>${data.message}</h3>`;
                                data.data.forEach(business => {
                                    results.innerHTML += `
                                        <div class="business-card">
                                            <h4>${business.name}</h4>
                                            <p><strong>Phone:</strong> ${business.phone}</p>
                                            <p><strong>Address:</strong> ${business.address}</p>
                                            <p><strong>Category:</strong> ${business.category}</p>
                                        </div>
                                    `;
                                });
                            } else {
                                results.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
                            }
                        } catch (error) {
                            results.innerHTML = '<p style="color: red;">An error occurred while processing your request</p>';
                        }
                    });
                </script>
            </body>
            </html>
            '''
        }
    
    # Handle POST request - perform the search
    if event['httpMethod'] == 'POST':
        try:
            body = json.loads(event['body'])
            what = body.get('what')
            where = body.get('where')
            
            if not what or not where:
                return {
                    'statusCode': 400,
                    'headers': {'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'Please provide both business type and location'})
                }
            
            result = scrape_business_data(what, where)
            
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(result)
            }
            
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': str(e)})
            }
    
    # Handle unsupported methods
    return {
        'statusCode': 405,
        'headers': {'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'error': 'Method not allowed'})
    } 