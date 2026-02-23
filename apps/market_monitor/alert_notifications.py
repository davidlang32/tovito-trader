"""
TOVITO TRADER - Alert Notifications
Handles all notification channels: Sound, Visual, Email, Discord

Integrates with existing email_service.py
"""

import os
import json
import threading
from datetime import datetime, timezone
from typing import Optional, Callable
from pathlib import Path

# For sound
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# For HTTP requests (Discord)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class SoundNotifier:
    """Handles sound notifications"""
    
    # Sound types
    SOUNDS = {
        'critical': (2500, 500),   # High pitch, long
        'high': (1800, 300),       # Medium-high pitch
        'medium': (1200, 200),     # Medium pitch
        'low': (800, 150),         # Low pitch
        'success': (1500, 100),    # Quick beep
    }
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled and HAS_WINSOUND
    
    def play(self, sound_type: str = 'medium'):
        """Play a notification sound"""
        if not self.enabled:
            return
        
        freq, duration = self.SOUNDS.get(sound_type, self.SOUNDS['medium'])
        
        try:
            # Run in thread to not block
            threading.Thread(
                target=lambda: winsound.Beep(freq, duration),
                daemon=True
            ).start()
        except Exception as e:
            print(f"Sound error: {e}")
    
    def play_critical(self):
        """Play urgent alert sound (3 beeps)"""
        if not self.enabled:
            return
        
        def beep_sequence():
            try:
                for _ in range(3):
                    winsound.Beep(2500, 300)
                    winsound.Beep(0, 100)  # Pause
            except:
                pass
        
        threading.Thread(target=beep_sequence, daemon=True).start()


class DiscordNotifier:
    """Sends notifications to Discord via webhook"""
    
    # Color codes for embeds
    COLORS = {
        'critical': 0xFF0000,  # Red
        'high': 0xFFA500,      # Orange
        'medium': 0xFFFF00,    # Yellow
        'low': 0x00FF00,       # Green
    }
    
    def __init__(self, webhook_url: str = None, enabled: bool = True):
        self.webhook_url = webhook_url or os.getenv("DISCORD_ALERTS_WEBHOOK_URL", "")
        self.enabled = enabled and HAS_REQUESTS and bool(self.webhook_url)
    
    def send(self, title: str, message: str, priority: str = 'medium', 
             fields: dict = None, mention_everyone: bool = False):
        """Send a Discord notification"""
        if not self.enabled:
            return False
        
        color = self.COLORS.get(priority, self.COLORS['medium'])
        
        embed = {
            'title': title,
            'description': message,
            'color': color,
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'footer': {'text': 'Tovito Trader Alert System'}
        }
        
        if fields:
            embed['fields'] = [
                {'name': k, 'value': str(v), 'inline': True}
                for k, v in fields.items()
            ]
        
        payload = {
            'embeds': [embed]
        }
        
        if mention_everyone and priority == 'critical':
            payload['content'] = '@everyone 🚨 CRITICAL ALERT'
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            return response.status_code == 204
        except Exception as e:
            print(f"Discord error: {e}")
            return False
    
    def send_critical(self, message: str, fields: dict = None):
        """Send critical alert with @everyone mention"""
        return self.send(
            "🚨 CRITICAL ALERT",
            message,
            priority='critical',
            fields=fields,
            mention_everyone=True
        )


class EmailNotifier:
    """Sends email notifications - integrates with existing email_service.py"""
    
    def __init__(self, enabled: bool = True, email_service_path: str = None):
        self.enabled = enabled
        self.email_service = None
        
        # Try to import existing email service
        if email_service_path:
            try:
                import sys
                service_dir = str(Path(email_service_path).parent)
                if service_dir not in sys.path:
                    sys.path.insert(0, service_dir)
                
                from email_service import EmailService
                self.email_service = EmailService()
            except ImportError as e:
                print(f"Could not import email_service: {e}")
        
        # Fallback: use environment variables directly
        if not self.email_service:
            self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            self.smtp_port = int(os.getenv('SMTP_PORT', 587))
            self.smtp_user = os.getenv('SMTP_USER', '')
            self.smtp_pass = os.getenv('SMTP_PASS', '')
            self.from_email = os.getenv('FROM_EMAIL', self.smtp_user)
            self.to_email = os.getenv('ALERT_EMAIL', os.getenv('TO_EMAIL', ''))
    
    def send(self, subject: str, body: str, html: bool = False, 
             priority: str = 'medium') -> bool:
        """Send email notification"""
        if not self.enabled:
            return False
        
        # Add priority prefix to subject
        priority_prefix = {
            'critical': '🚨 CRITICAL: ',
            'high': '⚠️ ',
            'medium': 'ℹ️ ',
            'low': ''
        }
        full_subject = f"{priority_prefix.get(priority, '')}{subject}"
        
        # Use existing email service if available
        if self.email_service:
            try:
                return self.email_service.send_email(
                    to=self.to_email or os.getenv('ALERT_EMAIL'),
                    subject=full_subject,
                    body=body,
                    html=html
                )
            except Exception as e:
                print(f"Email service error: {e}")
                return False
        
        # Fallback: direct SMTP
        if not self.smtp_user or not self.to_email:
            print("Email not configured (missing SMTP credentials)")
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = full_subject
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Email error: {e}")
            return False
    
    def send_alert(self, alert) -> bool:
        """Send an alert as email"""
        subject = f"Tovito Alert: {alert.message[:50]}"
        
        body = f"""
TOVITO TRADER ALERT
{'='*50}

Type: {alert.alert_type.value.upper()}
Priority: {alert.priority.value.upper()}
Symbol: {alert.symbol or 'Portfolio'}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

MESSAGE:
{alert.message}

DETAILS:
"""
        for key, value in alert.details.items():
            body += f"  {key}: {value}\n"
        
        body += f"""
{'='*50}
This is an automated alert from Tovito Trader.
        """
        
        return self.send(subject, body, priority=alert.priority.value)


class NotificationManager:
    """Manages all notification channels"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # Initialize notifiers
        notif_config = self.config.get('notifications', {})
        
        self.sound = SoundNotifier(
            enabled=notif_config.get('sound', True)
        )
        
        self.discord = DiscordNotifier(
            webhook_url=notif_config.get('discord_webhook', ''),
            enabled=notif_config.get('discord', False)
        )
        
        self.email = EmailNotifier(
            enabled=notif_config.get('email', True),
            email_service_path=self.config.get('email_service_path')
        )
        
        # Visual callback (set by dashboard)
        self.on_visual_alert: Optional[Callable] = None
    
    def notify(self, alert, channels: list = None):
        """Send notification through specified channels"""
        if channels is None:
            channels = ['sound', 'visual', 'email', 'discord']
        
        results = {}
        
        # Sound
        if 'sound' in channels and self.sound.enabled:
            if alert.priority.value == 'critical':
                self.sound.play_critical()
            else:
                self.sound.play(alert.priority.value)
            results['sound'] = True
        
        # Visual (callback to dashboard)
        if 'visual' in channels and self.on_visual_alert:
            try:
                self.on_visual_alert(alert)
                results['visual'] = True
            except Exception as e:
                print(f"Visual alert error: {e}")
                results['visual'] = False
        
        # Email
        if 'email' in channels and self.email.enabled:
            results['email'] = self.email.send_alert(alert)
        
        # Discord
        if 'discord' in channels and self.discord.enabled:
            fields = {k: v for k, v in alert.details.items() if k not in ['goal_key']}
            
            if alert.priority.value == 'critical':
                results['discord'] = self.discord.send_critical(
                    alert.message, 
                    fields=fields
                )
            else:
                results['discord'] = self.discord.send(
                    f"Alert: {alert.symbol or 'Portfolio'}",
                    alert.message,
                    priority=alert.priority.value,
                    fields=fields
                )
        
        return results
    
    def test_all(self) -> dict:
        """Test all notification channels"""
        results = {}
        
        # Test sound
        if self.sound.enabled:
            try:
                self.sound.play('success')
                results['sound'] = True
            except:
                results['sound'] = False
        else:
            results['sound'] = 'disabled'
        
        # Test email
        if self.email.enabled:
            results['email'] = self.email.send(
                "Test Alert",
                "This is a test notification from Tovito Trader Alert System.",
                priority='low'
            )
        else:
            results['email'] = 'disabled'
        
        # Test Discord
        if self.discord.enabled:
            results['discord'] = self.discord.send(
                "Test Alert",
                "This is a test notification from Tovito Trader Alert System.",
                priority='low'
            )
        else:
            results['discord'] = 'disabled'
        
        return results
    
    def update_config(self, config: dict):
        """Update notification configuration"""
        self.config = config
        notif_config = config.get('notifications', {})
        
        self.sound.enabled = notif_config.get('sound', True) and HAS_WINSOUND
        
        self.discord.webhook_url = notif_config.get('discord_webhook', '')
        self.discord.enabled = notif_config.get('discord', False) and HAS_REQUESTS and bool(self.discord.webhook_url)
        
        self.email.enabled = notif_config.get('email', True)


# Quick test
if __name__ == "__main__":
    print("Testing Notification System...")
    
    manager = NotificationManager({
        'notifications': {
            'sound': True,
            'email': False,
            'discord': False
        }
    })
    
    print("\nTesting sound...")
    manager.sound.play('medium')
    
    print("\nNotification channels:")
    print(f"  Sound: {'enabled' if manager.sound.enabled else 'disabled'}")
    print(f"  Email: {'enabled' if manager.email.enabled else 'disabled'}")
    print(f"  Discord: {'enabled' if manager.discord.enabled else 'disabled'}")
