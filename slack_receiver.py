
import os
from flask import Flask, request, jsonify, render_template
import json
import datetime
import logging
from flask_socketio import SocketIO, emit
from expense_analyzer import analyze_expense
from sheets_logger import log_expense
from threading import Thread

import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

required_env_vars = [
    'SPREADSHEET_ID',
    'GOOGLE_CREDS_B64',
    'DROPBOX_ACCESS_TOKEN',
    'SLACK_BOT_TOKEN',
    'PORT'
]

# Create a custom logging handler that emits logs to the WebSocket
class SocketIOHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        socketio.emit('log', {'data': log_entry})

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
socketio_handler = SocketIOHandler()
socketio_handler.setFormatter(formatter)
logger.addHandler(socketio_handler)

@app.route('/health')
def health_check():
    try:
        # Test basic functionality
        port = os.environ.get('PORT', '5000')
        env_status = {
            'status': 'ok',
            'app': 'slack-expense-tracker',
            'time': datetime.datetime.utcnow().isoformat(),
            'port': port,
            'environment_vars': {var: 'set' if os.environ.get(var) else 'missing' for var in required_env_vars}
        }
        return jsonify(env_status), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/logs')
def index():
    return render_template('index.html')

def process_expense(event, logger):
    expense_data = analyze_expense(event, logger)
    log_expense(expense_data, logger)

@app.route('/slack/events', methods=['POST', 'OPTIONS'])
def slack_events():
    if request.method == 'OPTIONS':
        return handle_cors_preflight()

    if not request.is_json:
        logger.error('Request is not JSON')
        return jsonify({'error': 'Request is not JSON'}), 400

    data = request.get_json()
    logger.info(f"Received data: {json.dumps(data, indent=2)}")

    if 'challenge' in data:
        logger.info(f"Responding to challenge: {data['challenge']}")
        return jsonify({'challenge': data['challenge']})

    if 'event' not in data:
        logger.error('Missing event data')
        return jsonify({'error': 'Missing event data'}), 400

    event = data.get("event", {})
    logger.info("New expense event received. Starting processing in a new thread.")
    thread = Thread(target=process_expense, args=(event, logger))
    thread.start()

    return jsonify({'status': 'ok'}), 200

def handle_cors_preflight():
    response = app.make_response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
