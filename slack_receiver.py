
import os
from flask import Flask, request, jsonify, render_template
import json
import datetime
import logging
from flask_socketio import SocketIO, emit
from expense_analyzer import analyze_expense
from sheets_logger import log_expense

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

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

@app.route('/')
def index():
    return render_template('index.html')

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
    expense_data = analyze_expense(event)
    log_expense(expense_data)
    logger.info("Expense logged successfully")

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
