"""
TOVITO TRADER - Alerts Tab
Dashboard UI component for alert monitoring

Add to main dashboard by importing and creating:
    from alerts_tab import AlertsTab
    self.alerts_tab = AlertsTab(self.tabview.tab("🚨 Alerts"), self.db)
"""

import customtkinter as ctk
from datetime import datetime, timedelta
import threading
import json

# Import our modules
from alert_system import AlertEngine, AlertType, AlertPriority, Alert
from alert_notifications import NotificationManager

# Colors (match main dashboard - import from main if possible)
try:
    from tovito_dashboard import COLORS, THEMES
except ImportError:
    # Fallback colors if imported standalone
    COLORS = {
        'bg_dark': '#0d0d0d',
        'bg_card': '#1a1a1a',
        'accent': '#262626',
        'highlight': '#e94560',
        'text': '#f5f5f5',
        'text_secondary': '#808080',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'danger': '#ef4444',
    }

PRIORITY_COLORS = {
    'critical': '#ff0000',
    'high': '#ff6b35',
    'medium': '#ffc107',
    'low': '#4ecca3',
}


class AlertCard(ctk.CTkFrame):
    """Individual alert display card"""
    
    def __init__(self, parent, alert: Alert, on_acknowledge=None, **kwargs):
        bg_color = PRIORITY_COLORS.get(alert.priority.value, COLORS['bg_card'])
        super().__init__(parent, fg_color=COLORS['bg_card'], corner_radius=8, 
                        border_width=2, border_color=bg_color, **kwargs)
        
        self.alert = alert
        self.on_acknowledge = on_acknowledge
        
        # Header row
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))
        
        # Priority badge
        priority_badge = ctk.CTkLabel(
            header,
            text=f"[{alert.priority.value.upper()}]",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=bg_color
        )
        priority_badge.pack(side="left")
        
        # Symbol
        if alert.symbol:
            ctk.CTkLabel(
                header,
                text=alert.symbol,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLORS['text']
            ).pack(side="left", padx=(10, 0))
        
        # Time
        ctk.CTkLabel(
            header,
            text=alert.timestamp.strftime("%H:%M:%S"),
            font=ctk.CTkFont(size=10),
            text_color=COLORS['text_secondary']
        ).pack(side="right")
        
        # Message
        ctk.CTkLabel(
            self,
            text=alert.message,
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text'],
            wraplength=400,
            justify="left"
        ).pack(fill="x", padx=10, pady=5, anchor="w")
        
        # Details (expandable)
        if alert.details:
            details_text = " | ".join(f"{k}: {v}" for k, v in list(alert.details.items())[:3])
            ctk.CTkLabel(
                self,
                text=details_text[:80],
                font=ctk.CTkFont(size=10),
                text_color=COLORS['text_secondary']
            ).pack(fill="x", padx=10, pady=(0, 5), anchor="w")
        
        # Action buttons
        if not alert.acknowledged:
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            ctk.CTkButton(
                btn_frame,
                text="✓ Acknowledge",
                width=100,
                height=24,
                font=ctk.CTkFont(size=11),
                fg_color=COLORS['success'],
                command=self._acknowledge
            ).pack(side="left")
            
            ctk.CTkButton(
                btn_frame,
                text="Snooze 30m",
                width=80,
                height=24,
                font=ctk.CTkFont(size=11),
                fg_color=COLORS['accent'],
                command=lambda: self._snooze(30)
            ).pack(side="left", padx=5)
    
    def _acknowledge(self):
        self.alert.acknowledged = True
        if self.on_acknowledge:
            self.on_acknowledge(self.alert.id)
        self.destroy()
    
    def _snooze(self, minutes):
        if self.on_acknowledge:
            self.on_acknowledge(self.alert.id, snooze_minutes=minutes)
        self.destroy()


class AlertsTab(ctk.CTkFrame):
    """Alerts monitoring tab for dashboard"""
    
    def __init__(self, parent, db_manager, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.db = db_manager
        self.alert_engine = None
        self.notification_manager = None
        self.is_flashing = False
        
        self.create_widgets()
        self.initialize_alert_system()
    
    def create_widgets(self):
        """Create all UI components"""
        # Top control bar
        self.control_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_card'], corner_radius=10)
        self.control_frame.pack(fill="x", padx=10, pady=10)
        
        control_inner = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        control_inner.pack(fill="x", padx=15, pady=10)
        
        # Status indicator
        self.status_indicator = ctk.CTkLabel(
            control_inner,
            text="● STOPPED",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['danger']
        )
        self.status_indicator.pack(side="left")
        
        # Last check time
        self.last_check_label = ctk.CTkLabel(
            control_inner,
            text="Last check: Never",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_secondary']
        )
        self.last_check_label.pack(side="left", padx=20)
        
        # Control buttons
        self.stop_btn = ctk.CTkButton(
            control_inner,
            text="⏹ Stop",
            width=80,
            fg_color=COLORS['danger'],
            command=self.stop_monitoring,
            state="disabled"
        )
        self.stop_btn.pack(side="right", padx=5)
        
        self.start_btn = ctk.CTkButton(
            control_inner,
            text="▶ Start",
            width=80,
            fg_color=COLORS['success'],
            command=self.start_monitoring
        )
        self.start_btn.pack(side="right", padx=5)
        
        self.check_now_btn = ctk.CTkButton(
            control_inner,
            text="🔄 Check Now",
            width=100,
            command=self.run_check_now
        )
        self.check_now_btn.pack(side="right", padx=5)
        
        self.snooze_all_btn = ctk.CTkButton(
            control_inner,
            text="😴 Snooze All",
            width=100,
            fg_color=COLORS['accent'],
            command=self.snooze_all_alerts
        )
        self.snooze_all_btn.pack(side="right", padx=5)
        
        # Main content area - two columns
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.content_frame.columnconfigure(0, weight=2)
        self.content_frame.columnconfigure(1, weight=1)
        self.content_frame.rowconfigure(0, weight=1)
        
        # Left side - Active Alerts
        self.alerts_frame = ctk.CTkFrame(self.content_frame, fg_color=COLORS['bg_card'], corner_radius=10)
        self.alerts_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        ctk.CTkLabel(
            self.alerts_frame,
            text="🚨 Active Alerts",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        self.alerts_scroll = ctk.CTkScrollableFrame(
            self.alerts_frame,
            fg_color="transparent"
        )
        self.alerts_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.no_alerts_label = ctk.CTkLabel(
            self.alerts_scroll,
            text="No active alerts\n\nClick 'Start' to begin monitoring",
            text_color=COLORS['text_secondary'],
            font=ctk.CTkFont(size=12)
        )
        self.no_alerts_label.pack(pady=50)
        
        # Right side - Positions & Config
        self.right_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        self.right_frame.rowconfigure(0, weight=1)
        self.right_frame.rowconfigure(1, weight=1)
        self.right_frame.columnconfigure(0, weight=1)
        
        # Positions panel
        self.positions_frame = ctk.CTkFrame(self.right_frame, fg_color=COLORS['bg_card'], corner_radius=10)
        self.positions_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        ctk.CTkLabel(
            self.positions_frame,
            text="📊 Current Positions",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        self.positions_scroll = ctk.CTkScrollableFrame(
            self.positions_frame,
            fg_color="transparent",
            height=200
        )
        self.positions_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Config panel
        self.config_frame = ctk.CTkFrame(self.right_frame, fg_color=COLORS['bg_card'], corner_radius=10)
        self.config_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        
        ctk.CTkLabel(
            self.config_frame,
            text="⚙️ Quick Settings",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        config_inner = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        config_inner.pack(fill="x", padx=15, pady=10)
        
        # Check interval
        ctk.CTkLabel(config_inner, text="Check interval:").pack(anchor="w")
        self.interval_var = ctk.StringVar(value="300")
        interval_frame = ctk.CTkFrame(config_inner, fg_color="transparent")
        interval_frame.pack(fill="x", pady=5)
        
        self.interval_entry = ctk.CTkEntry(interval_frame, width=80, textvariable=self.interval_var)
        self.interval_entry.pack(side="left")
        ctk.CTkLabel(interval_frame, text="seconds").pack(side="left", padx=5)
        
        # Notification toggles
        ctk.CTkLabel(config_inner, text="Notifications:").pack(anchor="w", pady=(10, 5))
        
        self.sound_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(config_inner, text="Sound", variable=self.sound_var,
                       command=self.update_config).pack(anchor="w")
        
        self.email_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(config_inner, text="Email", variable=self.email_var,
                       command=self.update_config).pack(anchor="w")
        
        self.discord_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(config_inner, text="Discord", variable=self.discord_var,
                       command=self.update_config).pack(anchor="w")
        
        # Test button
        ctk.CTkButton(
            config_inner,
            text="🧪 Test Notifications",
            width=140,
            command=self.test_notifications
        ).pack(anchor="w", pady=10)
    
    def initialize_alert_system(self):
        """Initialize the alert engine and notification manager"""
        try:
            db_path = self.db.db_path if self.db.connected else None
            self.alert_engine = AlertEngine(db_path=db_path)
            
            # Set up notification manager
            self.notification_manager = NotificationManager(self.alert_engine.config)
            self.notification_manager.on_visual_alert = self.on_visual_alert
            
            # Set callback for when alerts are triggered
            self.alert_engine.on_alert = self.on_alert_triggered
            
            # Load config into UI
            config = self.alert_engine.config
            self.interval_var.set(str(config.get('check_interval_seconds', 300)))
            notif = config.get('notifications', {})
            self.sound_var.set(notif.get('sound', True))
            self.email_var.set(notif.get('email', True))
            self.discord_var.set(notif.get('discord', False))
            
        except Exception as e:
            print(f"Error initializing alert system: {e}")
    
    def on_alert_triggered(self, alert: Alert):
        """Called when an alert is triggered"""
        # Send notifications
        if self.notification_manager:
            self.notification_manager.notify(alert)
        
        # Update UI (must be done on main thread)
        self.after(0, lambda: self.add_alert_card(alert))
    
    def on_visual_alert(self, alert: Alert):
        """Visual alert callback - flash the UI"""
        if alert.priority == AlertPriority.CRITICAL:
            self.flash_critical()
    
    def flash_critical(self):
        """Flash the alerts frame for critical alerts"""
        if self.is_flashing:
            return
        
        self.is_flashing = True
        original_color = self.alerts_frame.cget("fg_color")
        
        def flash(count=0):
            if count >= 6 or not self.is_flashing:
                self.alerts_frame.configure(fg_color=original_color)
                self.is_flashing = False
                return
            
            color = COLORS['danger'] if count % 2 == 0 else original_color
            self.alerts_frame.configure(fg_color=color)
            self.after(250, lambda: flash(count + 1))
        
        flash()
    
    def add_alert_card(self, alert: Alert):
        """Add an alert card to the UI"""
        # Hide "no alerts" message
        self.no_alerts_label.pack_forget()
        
        # Create card
        card = AlertCard(
            self.alerts_scroll,
            alert,
            on_acknowledge=self.acknowledge_alert
        )
        card.pack(fill="x", pady=5)
    
    def acknowledge_alert(self, alert_id: str, snooze_minutes: int = None):
        """Handle alert acknowledgment"""
        if self.alert_engine:
            self.alert_engine.acknowledge_alert(alert_id)
            
            if snooze_minutes:
                # Find the alert and snooze its type/symbol
                for alert in self.alert_engine.alerts:
                    if alert.id == alert_id:
                        if alert.symbol:
                            self.alert_engine.snooze_symbol(alert.symbol, snooze_minutes)
                        break
        
        # Check if any alerts left
        self.update_alerts_display()
    
    def update_alerts_display(self):
        """Update the alerts display"""
        if not self.alert_engine:
            return
        
        active = [a for a in self.alert_engine.alerts if not a.acknowledged]
        
        if not active:
            # Clear and show no alerts message
            for widget in self.alerts_scroll.winfo_children():
                widget.destroy()
            
            self.no_alerts_label = ctk.CTkLabel(
                self.alerts_scroll,
                text="No active alerts ✓",
                text_color=COLORS['success'],
                font=ctk.CTkFont(size=12)
            )
            self.no_alerts_label.pack(pady=50)
    
    def update_positions_display(self):
        """Update the positions panel"""
        if not self.alert_engine:
            return
        
        # Clear current
        for widget in self.positions_scroll.winfo_children():
            widget.destroy()
        
        positions = self.alert_engine.positions
        
        if not positions:
            ctk.CTkLabel(
                self.positions_scroll,
                text="No positions",
                text_color=COLORS['text_secondary']
            ).pack(pady=20)
            return
        
        for pos in positions:
            frame = ctk.CTkFrame(self.positions_scroll, fg_color=COLORS['bg_dark'], corner_radius=5)
            frame.pack(fill="x", pady=2)
            
            # Symbol and change
            change_color = COLORS['success'] if pos.day_change_percent >= 0 else COLORS['danger']
            
            ctk.CTkLabel(
                frame,
                text=pos.symbol[:12],
                font=ctk.CTkFont(size=11, weight="bold"),
                width=100
            ).pack(side="left", padx=5, pady=5)
            
            ctk.CTkLabel(
                frame,
                text=f"{pos.day_change_percent:+.1f}%",
                font=ctk.CTkFont(size=11),
                text_color=change_color,
                width=60
            ).pack(side="left", padx=5)
            
            ctk.CTkLabel(
                frame,
                text=f"${pos.market_value:,.0f}",
                font=ctk.CTkFont(size=11),
                text_color=COLORS['text_secondary']
            ).pack(side="right", padx=5, pady=5)
    
    def start_monitoring(self):
        """Start the alert monitoring"""
        if not self.alert_engine:
            return
        
        try:
            interval = int(self.interval_var.get())
        except:
            interval = 300
        
        self.alert_engine.start_monitoring(interval)
        
        # Update UI
        self.status_indicator.configure(text="● RUNNING", text_color=COLORS['success'])
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        # Start UI update timer
        self.update_status_loop()
    
    def stop_monitoring(self):
        """Stop the alert monitoring"""
        if self.alert_engine:
            self.alert_engine.stop_monitoring()
        
        self.is_flashing = False
        
        # Update UI
        self.status_indicator.configure(text="● STOPPED", text_color=COLORS['danger'])
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
    
    def run_check_now(self):
        """Run an immediate check"""
        if not self.alert_engine:
            return
        
        self.check_now_btn.configure(state="disabled", text="Checking...")
        
        def do_check():
            alerts = self.alert_engine.run_check()
            self.after(0, lambda: self.on_check_complete(alerts))
        
        threading.Thread(target=do_check, daemon=True).start()
    
    def on_check_complete(self, alerts):
        """Called when check completes"""
        self.check_now_btn.configure(state="normal", text="🔄 Check Now")
        self.update_positions_display()
        self.update_status_display()
        
        if not alerts:
            # Brief success indicator
            self.status_indicator.configure(text="● OK", text_color=COLORS['success'])
            self.after(2000, self.update_status_display)
    
    def snooze_all_alerts(self):
        """Snooze all alerts for 30 minutes"""
        if self.alert_engine:
            self.alert_engine.snooze_all(30)
            
            # Clear current alerts from display
            for widget in self.alerts_scroll.winfo_children():
                widget.destroy()
            
            self.no_alerts_label = ctk.CTkLabel(
                self.alerts_scroll,
                text="All alerts snoozed for 30 minutes 😴",
                text_color=COLORS['warning'],
                font=ctk.CTkFont(size=12)
            )
            self.no_alerts_label.pack(pady=50)
    
    def update_config(self):
        """Update configuration from UI"""
        if not self.alert_engine:
            return
        
        config = self.alert_engine.config
        config['notifications']['sound'] = self.sound_var.get()
        config['notifications']['email'] = self.email_var.get()
        config['notifications']['discord'] = self.discord_var.get()
        
        try:
            config['check_interval_seconds'] = int(self.interval_var.get())
        except:
            pass
        
        self.alert_engine.save_config(config)
        
        if self.notification_manager:
            self.notification_manager.update_config(config)
    
    def test_notifications(self):
        """Test all notification channels"""
        if self.notification_manager:
            results = self.notification_manager.test_all()
            
            msg = "Notification Test Results:\n\n"
            for channel, result in results.items():
                status = "✓" if result == True else ("disabled" if result == 'disabled' else "✗")
                msg += f"{channel}: {status}\n"
            
            # Show results in a popup
            popup = ctk.CTkToplevel(self)
            popup.title("Test Results")
            popup.geometry("300x200")
            
            ctk.CTkLabel(
                popup,
                text=msg,
                font=ctk.CTkFont(size=12),
                justify="left"
            ).pack(padx=20, pady=20)
            
            ctk.CTkButton(
                popup,
                text="OK",
                command=popup.destroy
            ).pack(pady=10)
    
    def update_status_loop(self):
        """Periodic UI status update"""
        if not self.alert_engine or not self.alert_engine.is_running:
            return
        
        self.update_status_display()
        self.after(5000, self.update_status_loop)  # Every 5 seconds
    
    def update_status_display(self):
        """Update status labels"""
        if not self.alert_engine:
            return
        
        status = self.alert_engine.get_status()
        
        if status['last_check']:
            last = datetime.fromisoformat(status['last_check'])
            self.last_check_label.configure(
                text=f"Last check: {last.strftime('%H:%M:%S')}"
            )
        
        if status['is_running']:
            self.status_indicator.configure(text="● RUNNING", text_color=COLORS['success'])
        
        if status['snooze_until']:
            snooze_time = datetime.fromisoformat(status['snooze_until'])
            if snooze_time > datetime.now():
                mins = int((snooze_time - datetime.now()).total_seconds() / 60)
                self.status_indicator.configure(
                    text=f"● SNOOZED ({mins}m)",
                    text_color=COLORS['warning']
                )
