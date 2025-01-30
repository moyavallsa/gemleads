const axios = require('axios');
const cheerio = require('cheerio');

async function scrapeBusinessData(what, where) {
  try {
    const baseUrl = 'https://www.goldenpages.ie';
    const searchUrl = `${baseUrl}/q/business/advanced/where/${where}/what/${what}/1`;
    
    const response = await axios.get(searchUrl);
    const $ = cheerio.load(response.data);
    
    const businesses = [];
    
    $('.listing').each((i, element) => {
      const business = {
        name: $(element).find('.listing-name').text().trim(),
        phone: $(element).find('.phone').text().trim(),
        address: $(element).find('.address').text().trim(),
        category: $(element).find('.category').text().trim()
      };
      
      businesses.push(business);
    });
    
    return {
      success: true,
      data: businesses,
      message: `Found ${businesses.length} businesses`
    };
  } catch (error) {
    console.error('Scraping error:', error);
    return {
      success: false,
      error: 'Failed to fetch business data'
    };
  }
}

exports.handler = async function(event, context) {
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method not allowed' })
    };
  }

  try {
    const { what, where } = JSON.parse(event.body);
    
    if (!what || !where) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Please provide both business type and location' })
      };
    }

    const result = await scrapeBusinessData(what, where);

    return {
      statusCode: 200,
      body: JSON.stringify(result)
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: error.message })
    };
  }
}; 