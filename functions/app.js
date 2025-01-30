const { spawn } = require('child_process');
const path = require('path');

exports.handler = async function(event, context) {
  // Set up Python environment
  const python = spawn('python', ['app.py']);
  
  return new Promise((resolve, reject) => {
    python.stdout.on('data', (data) => {
      console.log(`stdout: ${data}`);
    });

    python.stderr.on('data', (data) => {
      console.error(`stderr: ${data}`);
    });

    python.on('close', (code) => {
      resolve({
        statusCode: 200,
        body: JSON.stringify({ message: "Flask app is running" })
      });
    });
  });
}; 