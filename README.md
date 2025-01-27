# GemLeads

A web application that allows users to search and scrape business information from Golden Pages Ireland. The application provides a user-friendly interface to search for businesses by type and location, and automatically extracts contact information including email addresses.

## Features

- Search businesses by type and location
- Extract business information including:
  - Business name
  - Business type/category
  - Location
  - Phone number
  - Email address (from business detail pages)
  - Website
  - Description
- Export results to CSV
- Modern and responsive UI
- Rate limiting and respectful scraping
- Error handling and retry logic

## Installation

1. Clone the repository:
```bash
git clone https://github.com/moyavallsa/gemleads.git
cd gemleads
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Open your web browser and navigate to `http://127.0.0.1:5000`

3. Use the search form to:
   - Enter the type of business you're looking for (e.g., "Plumber", "Hairdresser")
   - Enter the location (e.g., "Dublin", "Cork")
   - Click "Search" to start the scraping process

4. Once the scraping is complete:
   - View the results on the page
   - Download the results as a CSV file

## Project Structure

```
gemleads/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── templates/         # HTML templates
│   ├── base.html     # Base template with navigation
│   ├── index.html    # LinkedIn search page
│   └── golden_pages.html  # Golden Pages search page
├── downloads/         # Directory for downloaded CSV files
└── README.md         # Project documentation
```

## Dependencies

- Flask: Web framework
- Selenium: Web automation
- BeautifulSoup4: HTML parsing
- Pandas: Data handling and CSV export
- Requests: HTTP requests
- Chrome WebDriver: Browser automation

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational purposes only. Make sure to review and comply with Golden Pages' terms of service and robots.txt when using this tool. Implement appropriate delays and respect rate limits to avoid overwhelming their servers. 