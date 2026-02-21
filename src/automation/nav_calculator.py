"""
NAV Calculation and Daily Update Automation
Core engine for calculating Net Asset Value and updating investor positions
"""

from datetime import datetime, date
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

from src.database.models import Database, Investor, DailyNAV, Transaction, SystemLog
from src.api.brokerage import get_brokerage_client, get_combined_balance, get_configured_providers

load_dotenv()


class NAVCalculator:
    """Handles all NAV calculations and daily updates"""

    def __init__(self, db_path: str = None, brokerage_provider: str = None):
        self.db = Database(db_path)
        # Keep a single client reference for non-balance operations (e.g. is_market_open)
        self.brokerage = get_brokerage_client(brokerage_provider)
        self.tax_rate = float(os.getenv('TAX_RATE', 0.37))
    
    def fetch_and_update_nav(self, update_date: date = None) -> Dict:
        """
        Main automation function: Fetch from Tradier and update NAV
        
        Args:
            update_date: Date to update (defaults to today)
            
        Returns:
            dict: Update results with status and data
        """
        if update_date is None:
            update_date = date.today()
        
        session = self.db.get_session()
        
        try:
            # 1. Fetch balance from all configured brokerages
            providers = get_configured_providers()
            print(f"Fetching account balance from {', '.join(providers)}...")
            balance_data = get_combined_balance()
            total_portfolio_value = balance_data['total_equity']

            # Log per-brokerage breakdown for audit trail
            for prov, detail in balance_data.get('brokerage_details', {}).items():
                print(f"  {prov}: ${detail.get('total_equity', 0):,.2f}")
            print(f"Combined portfolio balance: ${total_portfolio_value:,.2f}")
            
            # 2. Get total shares from database
            total_shares = self._get_total_active_shares(session)
            print(f"✅ Total active shares: {total_shares:,.4f}")
            
            # 3. Calculate NAV per share
            if total_shares > 0:
                nav_per_share = total_portfolio_value / total_shares
            else:
                nav_per_share = 1.0  # Default if no shares
            
            print(f"✅ NAV per share: ${nav_per_share:.4f}")
            
            # 4. Calculate daily changes
            daily_change_dollars = 0.0
            daily_change_percent = 0.0
            
            previous_nav = session.query(DailyNAV).filter(
                DailyNAV.date < update_date
            ).order_by(DailyNAV.date.desc()).first()
            
            if previous_nav:
                daily_change_dollars = total_portfolio_value - previous_nav.total_portfolio_value
                if previous_nav.total_portfolio_value > 0:
                    daily_change_percent = (daily_change_dollars / previous_nav.total_portfolio_value) * 100
            
            # 5. Save to database
            nav_record = DailyNAV(
                date=update_date,
                nav_per_share=nav_per_share,
                total_portfolio_value=total_portfolio_value,
                total_shares=total_shares,
                daily_change_dollars=daily_change_dollars,
                daily_change_percent=daily_change_percent,
                source='API'
            )
            
            # Check if record exists (update if so)
            existing = session.query(DailyNAV).filter(DailyNAV.date == update_date).first()
            if existing:
                existing.nav_per_share = nav_per_share
                existing.total_portfolio_value = total_portfolio_value
                existing.total_shares = total_shares
                existing.daily_change_dollars = daily_change_dollars
                existing.daily_change_percent = daily_change_percent
                existing.source = 'API'
                print(f"✅ Updated existing NAV record for {update_date}")
            else:
                session.add(nav_record)
                print(f"✅ Created new NAV record for {update_date}")
            
            session.commit()
            
            # 6. Log success
            log = SystemLog(
                log_type='SUCCESS',
                category='DailyUpdate',
                message=f'NAV updated successfully for {update_date}',
                details=f'Portfolio: ${total_portfolio_value:,.2f}, NAV: ${nav_per_share:.4f}, Change: ${daily_change_dollars:+,.2f} ({daily_change_percent:+.2f}%)'
            )
            session.add(log)
            session.commit()
            
            result = {
                'status': 'success',
                'date': update_date,
                'portfolio_value': total_portfolio_value,
                'total_shares': total_shares,
                'nav_per_share': nav_per_share,
                'daily_change_dollars': daily_change_dollars,
                'daily_change_percent': daily_change_percent,
                'timestamp': balance_data['timestamp']
            }
            
            print(f"\n🎉 Daily NAV Update Complete!")
            print(f"   Date: {update_date}")
            print(f"   Portfolio Value: ${total_portfolio_value:,.2f}")
            print(f"   NAV per Share: ${nav_per_share:.4f}")
            print(f"   Daily Change: ${daily_change_dollars:+,.2f} ({daily_change_percent:+.2f}%)")
            
            return result
            
        except Exception as e:
            # Log error
            log = SystemLog(
                log_type='ERROR',
                category='DailyUpdate',
                message=f'NAV update failed for {update_date}',
                details=str(e)
            )
            session.add(log)
            session.commit()
            
            print(f"❌ Error updating NAV: {str(e)}")
            
            return {
                'status': 'error',
                'date': update_date,
                'error': str(e)
            }
        
        finally:
            session.close()
    
    def _get_total_active_shares(self, session) -> float:
        """Get total shares for all active investors"""
        investors = session.query(Investor).filter(Investor.status == 'Active').all()
        return sum(inv.current_shares for inv in investors)
    
    def get_current_nav(self) -> Optional[float]:
        """Get the most recent NAV per share"""
        session = self.db.get_session()
        try:
            latest_nav = session.query(DailyNAV).order_by(DailyNAV.date.desc()).first()
            return latest_nav.nav_per_share if latest_nav else None
        finally:
            session.close()
    
    def get_investor_value(self, investor_id: str) -> Dict:
        """
        Calculate current value and metrics for an investor
        
        Args:
            investor_id: Investor ID
            
        Returns:
            dict: Current position details
        """
        session = self.db.get_session()
        
        try:
            investor = session.query(Investor).filter(Investor.investor_id == investor_id).first()
            if not investor:
                raise ValueError(f"Investor {investor_id} not found")
            
            # Get current NAV
            current_nav = self.get_current_nav()
            if not current_nav:
                raise ValueError("No NAV data available")
            
            # Calculate values
            current_value = investor.current_shares * current_nav
            unrealized_gain = max(0, current_value - investor.net_investment)
            tax_liability = unrealized_gain * self.tax_rate
            after_tax_value = current_value - tax_liability
            
            # Calculate return
            if investor.net_investment > 0:
                total_return_percent = ((current_value - investor.net_investment) / investor.net_investment) * 100
                after_tax_return_percent = ((after_tax_value - investor.net_investment) / investor.net_investment) * 100
            else:
                total_return_percent = 0.0
                after_tax_return_percent = 0.0
            
            return {
                'investor_id': investor_id,
                'name': investor.name,
                'current_shares': investor.current_shares,
                'share_price': current_nav,
                'current_value': current_value,
                'net_investment': investor.net_investment,
                'unrealized_gain': unrealized_gain,
                'tax_liability': tax_liability,
                'after_tax_value': after_tax_value,
                'total_return_percent': total_return_percent,
                'after_tax_return_percent': after_tax_return_percent
            }
            
        finally:
            session.close()
    
    def get_all_investor_values(self) -> List[Dict]:
        """Get current values for all active investors"""
        session = self.db.get_session()
        
        try:
            active_investors = session.query(Investor).filter(Investor.status == 'Active').all()
            return [self.get_investor_value(inv.investor_id) for inv in active_investors]
        finally:
            session.close()
    
    def validate_data(self) -> Dict:
        """
        Validate that all data is consistent
        
        Returns:
            dict: Validation results
        """
        session = self.db.get_session()
        
        try:
            # Get latest NAV
            latest_nav = session.query(DailyNAV).order_by(DailyNAV.date.desc()).first()
            if not latest_nav:
                return {
                    'valid': False,
                    'errors': ['No NAV data found']
                }
            
            # Get all active investors
            investors = session.query(Investor).filter(Investor.status == 'Active').all()
            
            # Calculate total shares from investors
            investor_total_shares = sum(inv.current_shares for inv in investors)
            
            # Compare with NAV record
            shares_match = abs(investor_total_shares - latest_nav.total_shares) < 0.01
            
            # Calculate percentages
            total_portfolio_value = latest_nav.total_portfolio_value
            investor_values = []
            total_percentage = 0.0
            
            for inv in investors:
                value = inv.current_shares * latest_nav.nav_per_share
                percentage = (value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                total_percentage += percentage
                investor_values.append({
                    'investor': inv.name,
                    'shares': inv.current_shares,
                    'value': value,
                    'percentage': percentage
                })
            
            percentages_valid = abs(total_percentage - 100.0) < 0.01
            
            errors = []
            if not shares_match:
                errors.append(f"Share mismatch: Investors={investor_total_shares:.4f}, NAV={latest_nav.total_shares:.4f}")
            if not percentages_valid:
                errors.append(f"Percentages don't sum to 100%: {total_percentage:.2f}%")
            
            return {
                'valid': len(errors) == 0,
                'date': latest_nav.date,
                'portfolio_value': total_portfolio_value,
                'nav_per_share': latest_nav.nav_per_share,
                'total_shares': latest_nav.total_shares,
                'investor_shares': investor_total_shares,
                'shares_match': shares_match,
                'total_percentage': total_percentage,
                'percentages_valid': percentages_valid,
                'investor_values': investor_values,
                'errors': errors
            }
            
        finally:
            session.close()


# Test function
if __name__ == "__main__":
    """Test NAV calculation"""
    
    print("Testing NAV Calculator...\n")
    
    calculator = NAVCalculator()
    
    # Test daily update
    print("=" * 60)
    print("Testing Automated Daily NAV Update")
    print("=" * 60)
    result = calculator.fetch_and_update_nav()
    
    if result['status'] == 'success':
        print("\n✅ Daily update successful!")
    else:
        print(f"\n❌ Daily update failed: {result.get('error')}")
    
    # Test validation
    print("\n" + "=" * 60)
    print("Testing Data Validation")
    print("=" * 60)
    validation = calculator.validate_data()
    
    if validation['valid']:
        print("✅ All validation checks passed!")
    else:
        print("❌ Validation errors found:")
        for error in validation['errors']:
            print(f"   - {error}")
