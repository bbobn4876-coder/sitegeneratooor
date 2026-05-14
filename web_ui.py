#!/usr/bin/env python3
import os
import sys
import json
import queue
import threading
import subprocess
from flask import Flask, render_template, request, Response, jsonify

app = Flask(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generator_config.json')


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(data):
    cfg = load_config()
    cfg.update(data)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


@app.route('/')
def index():
    cfg = load_config()
    return render_template('index.html',
                           api_key=cfg.get('api_key', ''),
                           bytedance_key=cfg.get('bytedance_key', ''))


@app.route('/save_config', methods=['POST'])
def save_config_route():
    data = request.get_json()
    save_config({
        'api_key': data.get('api_key', ''),
        'bytedance_key': data.get('bytedance_key', ''),
    })
    return jsonify({'ok': True})


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    site_description = data.get('site_description', '')
    site_type = data.get('site_type', 'landing')
    site_name = data.get('site_name', '')
    api_key = data.get('api_key', '')
    bytedance_key = data.get('bytedance_key', '')

    if api_key or bytedance_key:
        save_config({'api_key': api_key, 'bytedance_key': bytedance_key})

    env = os.environ.copy()
    if api_key:
        env['OPENROUTER_API_KEY'] = api_key
    if bytedance_key:
        env['BYTEDANCE_KEY'] = bytedance_key

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'phpgen_version82.py')

    input_data = f"{site_description}\n{site_type}\n{site_name}\n"

    q = queue.Queue()

    def run():
        try:
            proc = subprocess.Popen(
                [sys.executable, script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            proc.stdin.write(input_data)
            proc.stdin.close()
            for line in proc.stdout:
                q.put(('line', line.rstrip('\n')))
            proc.wait()
            q.put(('done', proc.returncode))
        except Exception as e:
            q.put(('error', str(e)))

    t = threading.Thread(target=run, daemon=True)
    t.start()

    def stream():
        while True:
            item = q.get()
            kind, value = item
            if kind == 'line':
                payload = json.dumps({'type': 'line', 'text': value})
                yield f"data: {payload}\n\n"
            elif kind == 'done':
                payload = json.dumps({'type': 'done', 'code': value})
                yield f"data: {payload}\n\n"
                break
            elif kind == 'error':
                payload = json.dumps({'type': 'error', 'text': value})
                yield f"data: {payload}\n\n"
                break

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
