"""
Notification module for Bozloader.
Handles email and Discord webhook notifications.
"""

import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request
import urllib.error

from config import Config


def send_email(to_email: str, subject: str, html_body: str, text_body: str = None):
    """Send an email notification."""
    if not Config.EMAIL_ENABLED:
        return
    
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        print("Email not configured - skipping notification")
        return
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = Config.SMTP_FROM
    msg['To'] = to_email
    
    if text_body:
        msg.attach(MIMEText(text_body, 'plain'))
    
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        if Config.SMTP_USE_TLS:
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(Config.SMTP_SERVER, Config.SMTP_PORT)
        
        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        server.sendmail(Config.SMTP_FROM, to_email, msg.as_string())
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise


def send_discord_notification(message: str, embed: dict = None):
    """Send a Discord webhook notification."""
    if not Config.DISCORD_ENABLED or not Config.DISCORD_WEBHOOK_URL:
        return
    
    payload = {"content": message}
    
    if embed:
        payload["embeds"] = [embed]
    
    data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(
        Config.DISCORD_WEBHOOK_URL,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Discord notification sent: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"Failed to send Discord notification: {e}")
        raise


def send_upload_notification(uploader_email: str, filename: str, media_type: str, upload_id: str):
    """Send notifications when a new upload is received."""
    
    media_type_display = "Movie" if media_type == "movie" else "TV Show"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #5DCDCD 0%, #3BA5A5 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .highlight {{ background: #E83D5F; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; }}
            .footer {{ text-align: center; margin-top: 20px; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎬 {Config.APP_NAME}</h1>
            </div>
            <div class="content">
                <h2>Upload Request Received!</h2>
                <p>Hi there,</p>
                <p>Your upload request has been received and is pending review.</p>
                <p><strong>File:</strong> {filename}</p>
                <p><strong>Type:</strong> <span class="highlight">{media_type_display}</span></p>
                <p>You'll receive another email once your upload has been approved or denied.</p>
                <p>Thanks for your contribution!</p>
            </div>
            <div class="footer">
                <p>— {Config.APP_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    {Config.APP_NAME} - Upload Request Received
    
    Hi there,
    
    Your upload request has been received and is pending review.
    
    File: {filename}
    Type: {media_type_display}
    
    You'll receive another email once your upload has been approved or denied.
    
    Thanks for your contribution!
    
    — {Config.APP_NAME}
    """
    
    try:
        send_email(
            to_email=uploader_email,
            subject=f"Upload Request Received - {Config.APP_NAME}",
            html_body=html_body,
            text_body=text_body
        )
    except Exception as e:
        print(f"Failed to send upload email to user: {e}")
    
    admin_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #FFD166 0%, #E8B33D 100%); color: #333; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .btn {{ display: inline-block; background: #5DCDCD; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 15px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📬 New Upload Pending Review</h1>
            </div>
            <div class="content">
                <h2>New {media_type_display} Upload</h2>
                <p><strong>File:</strong> {filename}</p>
                <p><strong>Uploader:</strong> {uploader_email}</p>
                <p><strong>Type:</strong> {media_type_display}</p>
                <a href="{Config.APP_URL}/admin" class="btn">Review Upload</a>
            </div>
            <div class="footer">
                <p>— {Config.APP_NAME} Admin</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    for admin_email in Config.ADMIN_EMAILS:
        try:
            send_email(
                to_email=admin_email,
                subject=f"🎬 New Upload Pending - {filename}",
                html_body=admin_html
            )
        except Exception as e:
            print(f"Failed to send admin email: {e}")
    
    if Config.DISCORD_ENABLED:
        emoji = "🎬" if media_type == "movie" else "📺"
        embed = {
            "title": f"{emoji} New Upload - {Config.APP_NAME}",
            "color": 6147277,
            "fields": [
                {"name": "📁 File", "value": filename, "inline": False},
                {"name": "📂 Type", "value": media_type_display, "inline": True},
                {"name": "👤 Uploader", "value": uploader_email, "inline": True}
            ],
            "footer": {"text": f"Review at {Config.APP_URL}/admin"}
        }
        
        try:
            send_discord_notification("", embed=embed)
        except Exception as e:
            print(f"Failed to send Discord notification: {e}")


def send_approval_notification(uploader_email: str, filename: str, media_type: str):
    """Send notification when upload is approved."""
    
    media_type_display = "Movie" if media_type == "movie" else "TV Show"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #4CAF50 0%, #388E3C 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .success-badge {{ background: #4CAF50; color: white; padding: 8px 16px; border-radius: 20px; font-weight: bold; display: inline-block; }}
            .footer {{ text-align: center; margin-top: 20px; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ {Config.APP_NAME}</h1>
            </div>
            <div class="content">
                <h2><span class="success-badge">APPROVED</span></h2>
                <p>Great news! Your upload has been approved and added to Plex.</p>
                <p><strong>File:</strong> {filename}</p>
                <p><strong>Type:</strong> {media_type_display}</p>
                <p>It should appear in your Plex library shortly.</p>
                <p>Thanks for your contribution! 🎉</p>
            </div>
            <div class="footer">
                <p>— {Config.APP_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    {Config.APP_NAME} - Upload Approved!
    
    Great news! Your upload has been approved and added to Plex.
    
    File: {filename}
    Type: {media_type_display}
    
    It should appear in your Plex library shortly.
    
    Thanks for your contribution!
    
    — {Config.APP_NAME}
    """
    
    send_email(
        to_email=uploader_email,
        subject=f"✅ Upload Approved - {Config.APP_NAME}",
        html_body=html_body,
        text_body=text_body
    )
    
    if Config.DISCORD_ENABLED:
        embed = {
            "title": f"✅ Upload Approved",
            "color": 5025616,
            "fields": [
                {"name": "📁 File", "value": filename, "inline": False},
                {"name": "📂 Added to", "value": f"Plex {media_type_display}s Library", "inline": True}
            ]
        }
        
        try:
            send_discord_notification("", embed=embed)
        except Exception as e:
            print(f"Failed to send Discord notification: {e}")


def send_denial_notification(uploader_email: str, filename: str, notes: str = ""):
    """Send notification when upload is denied."""
    
    notes_section = f"<p><strong>Notes:</strong> {notes}</p>" if notes else ""
    notes_text = f"\nNotes: {notes}" if notes else ""
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #E83D5F 0%, #C42848 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .denied-badge {{ background: #E83D5F; color: white; padding: 8px 16px; border-radius: 20px; font-weight: bold; display: inline-block; }}
            .footer {{ text-align: center; margin-top: 20px; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>❌ {Config.APP_NAME}</h1>
            </div>
            <div class="content">
                <h2><span class="denied-badge">NOT APPROVED</span></h2>
                <p>Unfortunately, your upload was not approved.</p>
                <p><strong>File:</strong> {filename}</p>
                {notes_section}
                <p>Please contact the admin if you have questions.</p>
            </div>
            <div class="footer">
                <p>— {Config.APP_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    {Config.APP_NAME} - Upload Not Approved
    
    Unfortunately, your upload was not approved.
    
    File: {filename}{notes_text}
    
    Please contact the admin if you have questions.
    
    — {Config.APP_NAME}
    """
    
    send_email(
        to_email=uploader_email,
        subject=f"❌ Upload Not Approved - {Config.APP_NAME}",
        html_body=html_body,
        text_body=text_body
    )
    
    if Config.DISCORD_ENABLED:
        embed = {
            "title": f"❌ Upload Denied",
            "color": 15220031,
            "fields": [
                {"name": "📁 File", "value": filename, "inline": False}
            ]
        }
        if notes:
            embed["fields"].append({"name": "📝 Notes", "value": notes, "inline": False})
        
        try:
            send_discord_notification("", embed=embed)
        except Exception as e:
            print(f"Failed to send Discord notification: {e}")
