const { GoldenPagesScraper } = require('../../app');

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

    const scraper = new GoldenPagesScraper();
    const [filename, message] = await scraper.scrape_business_data(what, where);

    return {
      statusCode: 200,
      body: JSON.stringify({
        success: true,
        filename: filename,
        message: message
      })
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: error.message })
    };
  }
}; 