"""
Bozloader - A Plex Upload Manager
Custom web application for friends to upload movies/TV shows to a Plex server.
"""

import os
import shutil
import sqlite3
import uuid
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_from_directory, g, session
)
from werkzeug.utils import secure_filename

from config import Config
from notifications import send_upload_notification, send_approval_notification, send_denial_notification
from plex_integration import trigger_plex_scan

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY if Config.SECRET_KEY != 'change-this-to-a-random-secret-key' else secrets.token_hex(32)

# Database setup
DATABASE = Config.DATABASE_PATH


def get_db():
    """Get database connection."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close database connection on app teardown."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database schema."""
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                media_type TEXT NOT NULL,
                uploader_email TEXT NOT NULL,
                upload_date TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reviewed_date TEXT,
                file_size INTEGER,
                notes TEXT
            )
        ''')
        
        # Admin table for authentication
        db.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                password_hash TEXT NOT NULL,
                must_change_password INTEGER DEFAULT 1,
                created_at TEXT,
                last_login TEXT
            )
        ''')
        
        # Check if admin exists, if not create with default password
        cursor = db.execute('SELECT COUNT(*) FROM admin')
        if cursor.fetchone()[0] == 0:
            # Default password is "admin" - must be changed on first login
            default_hash = hashlib.sha256('admin'.encode()).hexdigest()
            db.execute('INSERT INTO admin (password_hash, must_change_password, created_at) VALUES (?, 1, ?)', 
                       (default_hash, datetime.now().isoformat()))
        
        db.commit()


def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def get_user_email():
    """Get user email from Cloudflare Access headers or fallback."""
    cf_email = request.headers.get('Cf-Access-Authenticated-User-Email')
    if cf_email:
        return cf_email
    return request.headers.get('X-User-Email', 'anonymous@example.com')


def admin_required(f):
    """Decorator to require admin login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    """Check if file extension is allowed."""
    allowed_extensions = {
        'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm',
        'm4v', 'mpg', 'mpeg', 'ts', 'vob', 'iso'
    }
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_file_size_str(size_bytes):
    """Convert bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


@app.route('/')
def index():
    """Main upload page."""
    user_email = get_user_email()
    return render_template(
        'upload.html',
        user_email=user_email,
        movie_instructions=Config.UPLOAD_INSTRUCTIONS_MOVIES,
        tv_instructions=Config.UPLOAD_INSTRUCTIONS_TV,
        app_name=Config.APP_NAME
    )


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400

    file = request.files['file']
    media_type = request.form.get('media_type', 'movie')
    user_email = get_user_email()

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Please upload video files only.'}), 400

    upload_id = str(uuid.uuid4())
    original_filename = file.filename
    secure_name = secure_filename(original_filename)

    if media_type == 'tv':
        upload_path = Path(Config.PENDING_TV_PATH)
    else:
        upload_path = Path(Config.PENDING_MOVIES_PATH)

    upload_path.mkdir(parents=True, exist_ok=True)

    final_filename = f"{upload_id}_{secure_name}"
    file_path = upload_path / final_filename

    try:
        file.save(str(file_path))
        file_size = os.path.getsize(file_path)
    except Exception as e:
        return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

    db = get_db()
    db.execute('''
        INSERT INTO uploads (id, filename, original_filename, media_type, uploader_email, upload_date, file_size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (upload_id, final_filename, original_filename, media_type, user_email, datetime.now().isoformat(), file_size))
    db.commit()

    try:
        send_upload_notification(
            uploader_email=user_email,
            filename=original_filename,
            media_type=media_type,
            upload_id=upload_id
        )
    except Exception as e:
        app.logger.error(f"Failed to send notification: {e}")

    return jsonify({
        'success': True,
        'message': 'Upload successful! You will receive an email when your upload is reviewed.',
        'upload_id': upload_id
    })


# ============ Admin Authentication Routes ============

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_panel'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        password_hash = hash_password(password)
        
        db = get_db()
        admin = db.execute('SELECT * FROM admin WHERE id = 1').fetchone()
        
        if admin and admin['password_hash'] == password_hash:
            session['admin_logged_in'] = True
            db.execute('UPDATE admin SET last_login = ? WHERE id = 1', (datetime.now().isoformat(),))
            db.commit()
            
            # Check if password needs to be changed
            if admin['must_change_password']:
                return redirect(url_for('admin_change_password'))
            
            return redirect(url_for('admin_panel'))
        else:
            flash('Invalid password', 'error')
    
    return render_template('admin_login.html', app_name=Config.APP_NAME)


@app.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    """Force password change page."""
    db = get_db()
    admin = db.execute('SELECT must_change_password FROM admin WHERE id = 1').fetchone()
    force_change = admin['must_change_password'] if admin else False
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters', 'error')
        elif new_password != confirm_password:
            flash('Passwords do not match', 'error')
        elif new_password == 'admin':
            flash('Please choose a different password', 'error')
        else:
            new_hash = hash_password(new_password)
            db.execute('UPDATE admin SET password_hash = ?, must_change_password = 0 WHERE id = 1',
                       (new_hash,))
            db.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('admin_panel'))
    
    return render_template('admin_change_password.html', 
                          app_name=Config.APP_NAME, 
                          force_change=force_change)


@app.route('/admin/logout')
def admin_logout():
    """Log out of admin session."""
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


# ============ Admin Panel Routes ============

@app.route('/admin')
@admin_required
def admin_panel():
    """Admin panel for reviewing uploads."""
    db = get_db()

    pending = db.execute('''
        SELECT * FROM uploads WHERE status = 'pending' ORDER BY upload_date DESC
    ''').fetchall()

    processed = db.execute('''
        SELECT * FROM uploads WHERE status != 'pending' ORDER BY reviewed_date DESC LIMIT 50
    ''').fetchall()

    return render_template(
        'admin.html',
        pending=pending,
        processed=processed,
        app_name=Config.APP_NAME,
        get_file_size_str=get_file_size_str
    )


@app.route('/admin/approve/<upload_id>', methods=['POST'])
@admin_required
def approve_upload(upload_id):
    """Approve an upload and move to Plex library."""
    db = get_db()

    upload = db.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,)).fetchone()

    if not upload:
        return jsonify({'error': 'Upload not found'}), 404

    if upload['status'] != 'pending':
        return jsonify({'error': 'Upload already processed'}), 400

    if upload['media_type'] == 'tv':
        source_dir = Path(Config.PENDING_TV_PATH)
        dest_dir = Path(Config.PLEX_TV_PATH)
        library_name = Config.PLEX_TV_LIBRARY
    else:
        source_dir = Path(Config.PENDING_MOVIES_PATH)
        dest_dir = Path(Config.PLEX_MOVIES_PATH)
        library_name = Config.PLEX_MOVIES_LIBRARY

    source_path = source_dir / upload['filename']

    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / upload['original_filename']

    try:
        shutil.move(str(source_path), str(dest_path))
    except Exception as e:
        return jsonify({'error': f'Failed to move file: {str(e)}'}), 500

    db.execute('''
        UPDATE uploads SET status = 'approved', reviewed_date = ? WHERE id = ?
    ''', (datetime.now().isoformat(), upload_id))
    db.commit()

    try:
        trigger_plex_scan(library_name)
    except Exception as e:
        app.logger.error(f"Failed to trigger Plex scan: {e}")

    try:
        send_approval_notification(
            uploader_email=upload['uploader_email'],
            filename=upload['original_filename'],
            media_type=upload['media_type']
        )
    except Exception as e:
        app.logger.error(f"Failed to send approval notification: {e}")

    return jsonify({'success': True, 'message': 'Upload approved and added to Plex!'})


@app.route('/admin/deny/<upload_id>', methods=['POST'])
@admin_required
def deny_upload(upload_id):
    """Deny an upload and delete the file."""
    db = get_db()
    notes = request.form.get('notes', '')

    upload = db.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,)).fetchone()

    if not upload:
        return jsonify({'error': 'Upload not found'}), 404

    if upload['status'] != 'pending':
        return jsonify({'error': 'Upload already processed'}), 400

    if upload['media_type'] == 'tv':
        source_dir = Path(Config.PENDING_TV_PATH)
    else:
        source_dir = Path(Config.PENDING_MOVIES_PATH)

    source_path = source_dir / upload['filename']

    try:
        if source_path.exists():
            os.remove(str(source_path))
    except Exception as e:
        app.logger.error(f"Failed to delete file: {e}")

    db.execute('''
        UPDATE uploads SET status = 'denied', reviewed_date = ?, notes = ? WHERE id = ?
    ''', (datetime.now().isoformat(), notes, upload_id))
    db.commit()

    try:
        send_denial_notification(
            uploader_email=upload['uploader_email'],
            filename=upload['original_filename'],
            notes=notes
        )
    except Exception as e:
        app.logger.error(f"Failed to send denial notification: {e}")

    return jsonify({'success': True, 'message': 'Upload denied and file deleted.'})


@app.route('/status/<upload_id>')
def upload_status(upload_id):
    """Check status of an upload."""
    db = get_db()
    upload = db.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,)).fetchone()

    if not upload:
        return jsonify({'error': 'Upload not found'}), 404

    return jsonify({
        'id': upload['id'],
        'filename': upload['original_filename'],
        'status': upload['status'],
        'media_type': upload['media_type'],
        'upload_date': upload['upload_date'],
        'reviewed_date': upload['reviewed_date']
    })


@app.route('/my-uploads')
def my_uploads():
    """Show uploads for current user."""
    user_email = get_user_email()
    db = get_db()

    uploads = db.execute('''
        SELECT * FROM uploads WHERE uploader_email = ? ORDER BY upload_date DESC
    ''', (user_email,)).fetchall()

    return render_template(
        'my_uploads.html',
        uploads=uploads,
        user_email=user_email,
        app_name=Config.APP_NAME,
        get_file_size_str=get_file_size_str
    )


@app.route('/static/img/<path:filename>')
def serve_image(filename):
    """Serve static images."""
    return send_from_directory('static/img', filename)


@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'app': Config.APP_NAME})


@app.errorhandler(413)
def too_large(e):
    """Handle file too large error."""
    return jsonify({'error': 'File too large'}), 413


@app.errorhandler(500)
def server_error(e):
    """Handle server errors."""
    return jsonify({'error': 'Internal server error'}), 500


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)
