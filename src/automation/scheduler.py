"""
Automated Task Scheduler
Handles all scheduled tasks: daily NAV updates, reports, newsletters
"""

import schedule
import time
import os
from datetime import datetime, time as dt_time
from dotenv import load_dotenv
import pytz

from src.automation.nav_calculator import NAVCalculator
from src.automation.email_service import EmailService
from src.database.models import Database, SystemLog

load_dotenv()


class TaskScheduler:
    """Manages all automated tasks"""
    
    def __init__(self):
        self.nav_calculator = NAVCalculator()
        self.email_service = EmailService()
        self.db = Database()
        
        # Get settings from environment
        self.timezone = pytz.timezone(os.getenv('TIMEZONE', 'America/New_York'))
        self.market_close_time = os.getenv('MARKET_CLOSE_TIME', '16:00')
        self.auto_update_enabled = os.getenv('AUTO_UPDATE_ENABLED', 'true').lower() == 'true'
        self.notify_on_error = os.getenv('NOTIFY_ON_ERROR', 'true').lower() == 'true'
    
    def daily_nav_update(self):
        """
        Daily NAV update task
        Runs at market close (4:00 PM ET by default)
        """
        print(f"\n{'='*60}")
        print(f"AUTOMATED DAILY NAV UPDATE - {datetime.now()}")
        print(f"{'='*60}\n")
        
        try:
            # Check if market is open (only update on trading days)
            if not self._is_trading_day():
                print("⏸️  Market is closed today (weekend/holiday)")
                self._log_event('INFO', 'DailyUpdate', 'Skipped - Market closed')
                return
            
            # Perform the update
            result = self.nav_calculator.fetch_and_update_nav()
            
            if result['status'] == 'success':
                print("\n✅ Daily NAV update completed successfully!")
                
                # Validate data
                validation = self.nav_calculator.validate_data()
                if not validation['valid']:
                    print("\n⚠️  Validation warnings found:")
                    for error in validation['errors']:
                        print(f"   - {error}")
                    
                    if self.notify_on_error:
                        self._send_error_notification(
                            "Daily NAV Validation Warning",
                            f"Validation errors: {', '.join(validation['errors'])}"
                        )
                
            else:
                print(f"\n❌ Daily NAV update failed: {result.get('error')}")
                
                if self.notify_on_error:
                    self._send_error_notification(
                        "Daily NAV Update Failed",
                        result.get('error', 'Unknown error')
                    )
        
        except Exception as e:
            print(f"\n❌ Unexpected error in daily update: {str(e)}")
            self._log_event('ERROR', 'DailyUpdate', f'Unexpected error: {str(e)}')
            
            if self.notify_on_error:
                self._send_error_notification(
                    "Daily NAV Update Error",
                    str(e)
                )
    
    def weekly_newsletter(self):
        """
        Weekly newsletter task
        Runs on Sunday at 6:00 PM by default
        """
        print(f"\n{'='*60}")
        print(f"AUTOMATED WEEKLY NEWSLETTER - {datetime.now()}")
        print(f"{'='*60}\n")
        
        try:
            # Generate and send newsletter
            self.email_service.send_weekly_newsletter()
            print("✅ Weekly newsletter sent successfully!")
            
        except Exception as e:
            print(f"❌ Newsletter failed: {str(e)}")
            self._log_event('ERROR', 'Newsletter', f'Failed: {str(e)}')
            
            if self.notify_on_error:
                self._send_error_notification(
                    "Weekly Newsletter Failed",
                    str(e)
                )
    
    def monthly_reports(self):
        """
        Monthly reports task
        Runs on last day of month at 8:00 PM by default
        """
        print(f"\n{'='*60}")
        print(f"AUTOMATED MONTHLY REPORTS - {datetime.now()}")
        print(f"{'='*60}\n")
        
        try:
            # Generate and send monthly reports
            self.email_service.send_monthly_reports()
            print("✅ Monthly reports sent successfully!")
            
        except Exception as e:
            print(f"❌ Monthly reports failed: {str(e)}")
            self._log_event('ERROR', 'MonthlyReports', f'Failed: {str(e)}')
            
            if self.notify_on_error:
                self._send_error_notification(
                    "Monthly Reports Failed",
                    str(e)
                )
    
    def _is_trading_day(self) -> bool:
        """Check if today is a trading day"""
        try:
            is_open = self.nav_calculator.brokerage.is_market_open()
            return is_open
        except:
            # If can't check, assume it's a trading day (safer to update)
            return True
    
    def _send_error_notification(self, subject: str, error: str):
        """Send error notification email"""
        try:
            notify_email = os.getenv('NOTIFY_EMAIL')
            if notify_email:
                self.email_service.send_alert_email(
                    recipient=notify_email,
                    subject=f"Tovito Trader Alert: {subject}",
                    message=error
                )
        except Exception as e:
            print(f"Failed to send error notification: {str(e)}")
    
    def _log_event(self, log_type: str, category: str, message: str):
        """Log event to database"""
        session = self.db.get_session()
        try:
            log = SystemLog(
                log_type=log_type,
                category=category,
                message=message
            )
            session.add(log)
            session.commit()
        finally:
            session.close()
    
    def setup_schedules(self):
        """Set up all scheduled tasks"""
        
        if not self.auto_update_enabled:
            print("⚠️  Auto-update is disabled in settings")
            return
        
        print("Setting up automated schedules...")
        
        # Daily NAV update at market close (4:00 PM ET)
        schedule.every().day.at(self.market_close_time).do(self.daily_nav_update)
        print(f"✅ Daily NAV update scheduled for {self.market_close_time} ET")
        
        # Weekly newsletter (Sunday 6:00 PM)
        newsletter_day = os.getenv('WEEKLY_NEWSLETTER_DAY', 'sunday').lower()
        newsletter_time = os.getenv('NEWSLETTER_TIME', '18:00')
        
        if newsletter_day == 'sunday':
            schedule.every().sunday.at(newsletter_time).do(self.weekly_newsletter)
        elif newsletter_day == 'saturday':
            schedule.every().saturday.at(newsletter_time).do(self.weekly_newsletter)
        elif newsletter_day == 'friday':
            schedule.every().friday.at(newsletter_time).do(self.weekly_newsletter)
        
        print(f"✅ Weekly newsletter scheduled for {newsletter_day.title()} {newsletter_time}")
        
        # Monthly reports (last day of month, 8:00 PM)
        # Note: We'll check daily if it's the last day of the month
        schedule.every().day.at("20:00").do(self._check_monthly_reports)
        print(f"✅ Monthly reports scheduled for last day of month at 20:00")
        
        print("\n🎉 All schedules configured!")
        print("\nScheduled tasks:")
        for job in schedule.jobs:
            print(f"  - {job}")
    
    def _check_monthly_reports(self):
        """Check if today is last day of month and send reports"""
        today = datetime.now().date()
        
        # Check if tomorrow is first day of next month
        from datetime import timedelta
        tomorrow = today + timedelta(days=1)
        
        if tomorrow.day == 1:
            print("\n📅 Last day of month detected - running monthly reports...")
            self.monthly_reports()
    
    def run(self):
        """
        Main loop - runs scheduled tasks
        Call this to start the automation service
        """
        print(f"\n{'='*60}")
        print("TOVITO TRADER AUTOMATION SERVICE STARTING")
        print(f"{'='*60}\n")
        print(f"Timezone: {self.timezone}")
        print(f"Auto-update: {'Enabled' if self.auto_update_enabled else 'Disabled'}")
        print(f"Error notifications: {'Enabled' if self.notify_on_error else 'Disabled'}")
        print()
        
        self.setup_schedules()
        
        print(f"\n{'='*60}")
        print("AUTOMATION SERVICE RUNNING")
        print("Press Ctrl+C to stop")
        print(f"{'='*60}\n")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            print("\n\n👋 Automation service stopped by user")
        except Exception as e:
            print(f"\n\n❌ Automation service crashed: {str(e)}")
            self._log_event('ERROR', 'Scheduler', f'Service crashed: {str(e)}')


# Manual test functions
def test_daily_update():
    """Test daily update manually"""
    scheduler = TaskScheduler()
    scheduler.daily_nav_update()


def test_schedules():
    """Test that schedules are set up correctly"""
    scheduler = TaskScheduler()
    scheduler.setup_schedules()
    
    print("\n📋 Next scheduled tasks:")
    for job in schedule.jobs:
        print(f"  - {job.next_run} - {job}")


if __name__ == "__main__":
    """
    Run the automation service
    """
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            print("Running test update...")
            test_daily_update()
        elif sys.argv[1] == 'schedules':
            print("Testing schedules...")
            test_schedules()
    else:
        # Run the full automation service
        scheduler = TaskScheduler()
        scheduler.run()
