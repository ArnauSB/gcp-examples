import logging
from flask import Flask, jsonify
import os

HOST = os.getenv('SERVER_HOST', '0.0.0.0')
PORT = int(os.getenv('SERVER_PORT', 443))
CERT_PATH = "server.crt"
KEY_PATH = "server.key"

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

@app.route('/status', methods=['GET'])
def status():
    """Returns a simple success message for health checks."""
    logger.info("Received request on /status")
    return jsonify({
        "status": "up",
        "message": "HTTPS server is running and secure",
        "certificate_issuer": "Arnau Root CA"
    })

if __name__ == '__main__':
    if not all(os.path.exists(f) for f in [CERT_PATH, KEY_PATH]):
        logger.error(f"Missing certificate files ({CERT_PATH} or {KEY_PATH}).")
    else:
        logger.info(f"Starting HTTPS server at https://{HOST}:{PORT}/status")
        try:
            app.run(host=HOST, port=PORT, ssl_context=(CERT_PATH, KEY_PATH))
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
