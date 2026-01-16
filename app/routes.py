"""
Bozloader - A Plex Upload Manager
Custom web application for friends to upload movies/TV shows to a Plex server.
"""

import os
import shutil
import sqlite3
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

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Configuration
class Config:
    APP_NAME = os.getenv('APP_NAME', 'Bozloader')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    
    # Storage paths (inside container)
    PENDING_MOVIES = '/data/pending/movies'
    PENDING_TV = '/data/pending/tv'
    PLEX_MOVIES = '/data/plex/movies'
    PLEX_TV = '/data/plex/tv'
    
    # Plex settings
    PLEX_URL = os.getenv('PLEX_URL', 'http://10.0.0.195:32400')
    PLEX_TOKEN = os.getenv('PLEX_TOKEN', '')
    
    # Email settings
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
    
    # Discord webhook (optional)
    DISCORD_WEBHOOK = os.getenv('DISCORD_WEBHOOK', '')
    
    # Upload instructions
    UPLOAD_INSTRUCTIONS_MOVIES = os.getenv(
        'UPLOAD_INSTRUCTIONS_MOVIES',
        'Upload your movie files here. Please name files: MovieTitle (Year).ext'
    )
    UPLOAD_INSTRUCTIONS_TV = os.getenv(
        'UPLOAD_INSTRUCTIONS_TV',
        'Upload your TV show files here. Please include show name and episode info.'
    )


# Database setup
DATABASE = '/app/database/bozloader.db'


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database with required tables."""
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = sqlite3.connect(DATABASE)
    
    # Uploads table
    db.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            media_type TEXT NOT NULL,
            uploader_email TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Check if admin exists, if not create with default password
    cursor = db.execute('SELECT COUNT(*) FROM admin')
    if cursor.fetchone()[0] == 0:
        # Default password is "admin" - must be changed on first login
        default_hash = hashlib.sha256('admin'.encode()).hexdigest()
        db.execute('INSERT INTO admin (password_hash, must_change_password) VALUES (?, 1)', 
                   (default_hash,))
    
    db.commit()
    db.close()


def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def admin_required(f):
    """Decorator to require admin login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def get_user_email():
    """Get user email from Cloudflare Access headers or fallback."""
    return request.headers.get('Cf-Access-Authenticated-User-Email', 'anonymous@unknown.com')


def get_file_size_str(size_bytes):
    """Convert bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def send_email(to_email, subject, body):
    """Send an email notification."""
    if not Config.SMTP_USER or not Config.SMTP_PASSWORD:
        print(f"Email not configured. Would send to {to_email}: {subject}")
        return
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart()
        msg['From'] = Config.SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_discord_notification(message):
    """Send a Discord webhook notification."""
    if not Config.DISCORD_WEBHOOK:
        return
    
    try:
        import urllib.request
        import json
        
        data = json.dumps({'content': message}).encode('utf-8')
        req = urllib.request.Request(
            Config.DISCORD_WEBHOOK,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")


def trigger_plex_scan():
    """Trigger a Plex library scan."""
    if not Config.PLEX_TOKEN:
        print("Plex token not configured")
        return
    
    try:
        import urllib.request
        
        url = f"{Config.PLEX_URL}/library/sections/all/refresh?X-Plex-Token={Config.PLEX_TOKEN}"
        req = urllib.request.Request(url, method='GET')
        urllib.request.urlopen(req)
        print("Plex scan triggered")
    except Exception as e:
        print(f"Failed to trigger Plex scan: {e}")


# ============ Routes ============

@app.route('/')
def index():
    """Main upload page."""
    user_email = get_user_email()
    return render_template(
        'index.html',
        user_email=user_email,
        app_name=Config.APP_NAME,
        movie_instructions=Config.UPLOAD_INSTRUCTIONS_MOVIES,
        tv_instructions=Config.UPLOAD_INSTRUCTIONS_TV
    )


@app.route('/upload', methods=['POST'])
def upload():
    """Handle file uploads."""
    user_email = get_user_email()
    media_type = request.form.get('media_type', 'movie')
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    # Determine destination folder
    if media_type == 'tv':
        dest_folder = Config.PENDING_TV
    else:
        dest_folder = Config.PENDING_MOVIES
    
    os.makedirs(dest_folder, exist_ok=True)
    
    # Save file
    original_filename = file.filename
    safe_filename = secure_filename(original_filename)
    
    # Add timestamp to prevent overwrites
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_filename}"
    filepath = os.path.join(dest_folder, filename)
    
    file.save(filepath)
    file_size = os.path.getsize(filepath)
    
    # Record in database
    db = get_db()
    db.execute('''
        INSERT INTO uploads (filename, original_filename, media_type, uploader_email, file_size, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (filename, original_filename, media_type, user_email, file_size, request.form.get('notes', '')))
    db.commit()
    
    # Send notifications
    send_email(
        Config.ADMIN_EMAIL,
        f"New Upload - {Config.APP_NAME}",
        f"New {media_type} upload from {user_email}:\n\n"
        f"File: {original_filename}\n"
        f"Size: {get_file_size_str(file_size)}\n"
        f"Notes: {request.form.get('notes', 'None')}\n\n"
        f"Review at: https://upload.boznet.org/admin"
    )
    
    send_discord_notification(
        f"🎬 **New Upload**\n"
        f"📁 {original_filename}\n"
        f"📂 {media_type.title()}\n"
        f"👤 {user_email}\n"
        f"📊 {get_file_size_str(file_size)}"
    )
    
    flash(f'Upload successful! "{original_filename}" is pending approval.', 'success')
    return redirect(url_for('index'))


# ============ Admin Authentication Routes ============

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        password_hash = hash_password(password)
        
        db = get_db()
        admin = db.execute('SELECT * FROM admin WHERE id = 1').fetchone()
        
        if admin and admin['password_hash'] == password_hash:
            session['admin_logged_in'] = True
            db.execute('UPDATE admin SET last_login = ? WHERE id = 1', (datetime.now(),))
            db.commit()
            
            # Check if password needs to be changed
            if admin['must_change_password']:
                return redirect(url_for('admin_change_password'))
            
            return redirect(url_for('admin'))
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
            return redirect(url_for('admin'))
    
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
def admin():
    """Admin panel - list pending uploads."""
    db = get_db()
    
    pending = db.execute('''
        SELECT * FROM uploads WHERE status = 'pending' ORDER BY upload_date DESC
    ''').fetchall()
    
    recent = db.execute('''
        SELECT * FROM uploads WHERE status != 'pending' ORDER BY upload_date DESC LIMIT 20
    ''').fetchall()
    
    return render_template(
        'admin.html',
        pending=pending,
        recent=recent,
        app_name=Config.APP_NAME,
        get_file_size_str=get_file_size_str
    )


@app.route('/admin/approve/<int:upload_id>', methods=['POST'])
@admin_required
def approve(upload_id):
    """Approve an upload and move to Plex folder."""
    db = get_db()
    upload = db.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,)).fetchone()
    
    if not upload:
        flash('Upload not found', 'error')
        return redirect(url_for('admin'))
    
    # Determine source and destination
    if upload['media_type'] == 'tv':
        src_folder = Config.PENDING_TV
        dest_folder = Config.PLEX_TV
    else:
        src_folder = Config.PENDING_MOVIES
        dest_folder = Config.PLEX_MOVIES
    
    src_path = os.path.join(src_folder, upload['filename'])
    
    # Use original filename for Plex
    dest_path = os.path.join(dest_folder, upload['original_filename'])
    
    try:
        os.makedirs(dest_folder, exist_ok=True)
        shutil.move(src_path, dest_path)
        
        db.execute('UPDATE uploads SET status = ? WHERE id = ?', ('approved', upload_id))
        db.commit()
        
        # Notify uploader
        send_email(
            upload['uploader_email'],
            f"Upload Approved - {Config.APP_NAME}",
            f"Great news! Your upload \"{upload['original_filename']}\" has been approved.\n\n"
            f"It should appear in Plex shortly.\n\n"
            f"Thanks for the contribution!"
        )
        
        send_discord_notification(f"✅ **Approved:** {upload['original_filename']}")
        
        # Trigger Plex scan
        trigger_plex_scan()
        
        flash(f'Approved: {upload["original_filename"]}', 'success')
    except Exception as e:
        flash(f'Error moving file: {e}', 'error')
    
    return redirect(url_for('admin'))


@app.route('/admin/deny/<int:upload_id>', methods=['POST'])
@admin_required
def deny(upload_id):
    """Deny an upload and delete the file."""
    db = get_db()
    upload = db.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,)).fetchone()
    
    if not upload:
        flash('Upload not found', 'error')
        return redirect(url_for('admin'))
    
    # Determine source folder
    if upload['media_type'] == 'tv':
        src_folder = Config.PENDING_TV
    else:
        src_folder = Config.PENDING_MOVIES
    
    src_path = os.path.join(src_folder, upload['filename'])
    
    try:
        if os.path.exists(src_path):
            os.remove(src_path)
        
        db.execute('UPDATE uploads SET status = ? WHERE id = ?', ('denied', upload_id))
        db.commit()
        
        # Notify uploader
        send_email(
            upload['uploader_email'],
            f"Upload Not Approved - {Config.APP_NAME}",
            f"Unfortunately, your upload \"{upload['original_filename']}\" was not approved.\n\n"
            f"Please contact the admin if you have questions."
        )
        
        send_discord_notification(f"❌ **Denied:** {upload['original_filename']}")
        
        flash(f'Denied: {upload["original_filename"]}', 'success')
    except Exception as e:
        flash(f'Error removing file: {e}', 'error')
    
    return redirect(url_for('admin'))


@app.route('/my-uploads')
def my_uploads():
    """Show user's upload history."""
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


@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'app': Config.APP_NAME})


# Initialize database on startup
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)
