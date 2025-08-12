# app.py (增强日志版)
import os
import uuid
import threading
import json
import sys # 导入sys模块以便打印到stderr
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename

from backend.main import EntropySearch, NumpyEncoder

# --- Application Setup ---
UPLOAD_FOLDER = '/tmp/entropy_search_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

SEARCH_JOBS = {}

# --- Core Search Logic (Adapted for Threading) ---
def run_background_search(job_id: str, info: dict):
    """This function runs in a separate thread."""
    print(f"✅ [Job {job_id}] Background thread started.", file=sys.stdout)
    try:
        SEARCH_JOBS[job_id]['status'] = 'running'
        SEARCH_JOBS[job_id]['status_message'] = 'Initializing search worker...'
        
        worker = EntropySearch(info["ms2_tolerance_in_da"])
        
        SEARCH_JOBS[job_id]['status_message'] = f'Loading library: {info["file_library"]}'
        print(f"  [Job {job_id}] Loading library file...", file=sys.stdout)
        worker.load_spectral_library(info["file_library"])
        print(f"  [Job {job_id}] Library loaded successfully.", file=sys.stdout)

        SEARCH_JOBS[job_id]['status_message'] = f'Searching query file: {info["file_query"]}'
        print(f"  [Job {job_id}] Starting search on query file...", file=sys.stdout)
        worker.search_file_single_core(
            info["file_query"], info["top_n"], info["ms1_tolerance_in_da"], info["ms2_tolerance_in_da"]
        )
        print(f"  [Job {job_id}] Search completed.", file=sys.stdout)
        
        SEARCH_JOBS[job_id]['worker'] = worker
        SEARCH_JOBS[job_id]['status'] = 'finished'
        SEARCH_JOBS[job_id]['status_message'] = 'Search complete! Redirecting...'
        print(f"✅ [Job {job_id}] Task marked as finished.", file=sys.stdout)

    except Exception as e:
        # 捕获并打印任何在线程中发生的错误
        print(f"❌ [Job {job_id}] An exception occurred in the background thread!", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        SEARCH_JOBS[job_id]['status'] = 'error'
        SEARCH_JOBS[job_id]['status_message'] = f"An error occurred: {e}"

# --- 其他 Flask 代码保持不变 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def handle_search():
    job_id = str(uuid.uuid4())
    job_path = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    os.makedirs(job_path, exist_ok=True)

    query_file = request.files['file_query']
    library_file = request.files['file_library']
    query_filepath = os.path.join(job_path, secure_filename(query_file.filename))
    library_filepath = os.path.join(job_path, secure_filename(library_file.filename))
    query_file.save(query_filepath)
    library_file.save(library_filepath)
    print(f"✅ [Job {job_id}] Files saved to {job_path}", file=sys.stdout)

    search_info = {
        "file_query": query_filepath,
        "file_library": library_filepath,
        "ms1_tolerance_in_da": float(request.form.get('ms1_tolerance_in_da', 0.01)),
        "ms2_tolerance_in_da": float(request.form.get('ms2_tolerance_in_da', 0.02)),
        "top_n": int(request.form.get('top_n', 100)),
        "cores": 1,
        "charge": 0
    }

    SEARCH_JOBS[job_id] = {'status': 'queued', 'status_message': 'Waiting to start...'}
    print(f"✅ [Job {job_id}] Job queued. Starting background thread...", file=sys.stdout)
    thread = threading.Thread(target=run_background_search, args=(job_id, search_info))
    thread.start()

    return redirect(url_for('status', job_id=job_id))

@app.route('/status/<job_id>')
def status(job_id):
    return render_template('status.html', job_id=job_id)

@app.route('/results/<job_id>')
def results(job_id):
    job = SEARCH_JOBS.get(job_id)
    if not job or job['status'] != 'finished':
        return "Job not found or not finished.", 404
    
    worker = job.get('worker')
    all_spectra = []
    if worker and hasattr(worker, 'all_spectra'):
        for spec in worker.all_spectra:
            display_spec = {k: v for k, v in spec.items() if k not in ['peaks', 'identity_search', 'open_search', 'neutral_loss_search', 'hybrid_search']}
            if display_spec.get('scan_number') is not None:
                all_spectra.append(display_spec)

    results_json_str = json.dumps(all_spectra, cls=NumpyEncoder)
    return render_template('results.html', results=json.loads(results_json_str), job_id=job_id)

@app.route('/api/status/<job_id>')
def api_status(job_id):
    job = SEARCH_JOBS.get(job_id, {})
    return jsonify({
        'status': job.get('status', 'not_found'),
        'message': job.get('status_message', 'Job ID not found.')
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)