# 🐕 Bozloader

**A friendly Plex upload manager for sharing media with friends**

Bozloader is a self-hosted web application that lets your friends upload movies and TV shows to your Plex server with an approval workflow. Built with a playful dog theme and designed for homelab enthusiasts.

## ✨ Features

- **🎬 Separate Upload Forms** - Movies and TV shows go to different folders
- **📧 Email Notifications** - Uploaders get notified when uploads are received, approved, or denied
- **💬 Discord Integration** - Optional webhook notifications for new uploads
- **👨‍💼 Admin Panel** - Review and approve/deny uploads with one click
- **📺 Auto Plex Integration** - Approved files automatically move to Plex library folders and trigger a scan
- **☁️ Cloudflare Access Ready** - No separate login needed, reads email from CF headers
- **📱 Responsive Design** - Works great on mobile and desktop
- **🐳 Docker Ready** - Easy deployment with Docker Compose
- **📖 Open Source** - Customize it for your homelab!

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- A Plex Media Server
- (Optional) Cloudflare Access for authentication
- (Optional) SMTP server for email notifications
- (Optional) Discord webhook for notifications

### Installation

1. **Clone the repository**
```bash
   git clone https://github.com/aclarkson2013/bozloader.git
   cd bozloader
```

2. **Create your configuration**
```bash
   cp .env.example .env
   nano .env  # Edit with your settings
```

3. **Update docker-compose.yml volume paths**
   
   Edit `docker-compose.yml` to map your actual storage paths.

4. **Start the application**
```bash
   docker compose up -d
```

5. **Access Bozloader**
   
   Open http://localhost:8082 in your browser

## ⚙️ Configuration

All configuration is done through environment variables in the `.env` file.

### Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `your-random-secret-key` |
| `ADMIN_EMAILS` | Comma-separated admin emails | `admin@example.com` |

### Email Configuration
```env
EMAIL_ENABLED=True
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourdomain.com
```

**For Gmail:** Use an App Password, not your regular password.

### Plex Integration
```env
PLEX_URL=http://192.168.0.50:32400
PLEX_TOKEN=your-plex-token
PLEX_MOVIES_LIBRARY=Movies
PLEX_TV_LIBRARY=TV Shows
```

## 📁 File Structure
```
bozloader/
├── app/
│   ├── main.py              # Flask application
│   ├── config.py            # Configuration loader
│   ├── notifications.py     # Email & Discord
│   ├── plex_integration.py  # Plex API
│   ├── static/img/          # Logo
│   └── templates/           # HTML templates
├── docs/                    # Documentation
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## 🔒 Security

### Cloudflare Access Integration

Bozloader reads the user email from Cloudflare Access headers. Users authenticate through Cloudflare Access with no separate login required.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Named after Bosley, the goodest boy 🐕
- Built for the homelab community

---

Made with ❤️ for Plex enthusiasts
