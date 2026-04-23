from flask import Flask, render_template, jsonify
import json
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    try:
        if not os.path.exists('starlink_data.json'):
            return jsonify({"error": "No data found", "data": []})
            
        with open('starlink_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e), "data": []})

if __name__ == '__main__':
    app.run(debug=True, port=9000, host='0.0.0.0')
