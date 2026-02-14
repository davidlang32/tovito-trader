"""
Export All Transactions to Excel (FIXED)

Shows complete transaction history from database in Excel format.

Usage:
    python scripts/export_transactions_excel.py
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime


def export_transactions_to_excel():
    """Export all transactions to Excel"""
    
    db_path = Path(__file__).parent.parent / 'data' / 'tovito.db'
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        
        print("=" * 80)
        print("EXPORT TRANSACTIONS TO EXCEL")
        print("=" * 80)
        print()
        
        # Get all transactions
        query = """
            SELECT 
                t.transaction_id,
                t.date,
                t.investor_id,
                i.name as investor_name,
                t.transaction_type,
                t.amount,
                t.share_price,
                t.shares_transacted,
                t.notes,
                t.created_at
            FROM transactions t
            LEFT JOIN investors i ON t.investor_id = i.investor_id
            ORDER BY t.date, t.created_at
        """
        
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("⚠️  No transactions found in database")
            conn.close()
            return False
        
        print(f"Found {len(df)} transactions in database")
        print()
        
        # Summary by type
        print("TRANSACTION SUMMARY BY TYPE:")
        print("-" * 40)
        for trans_type in df['transaction_type'].unique():
            type_data = df[df['transaction_type'] == trans_type]
            count = len(type_data)
            total = type_data['amount'].sum()
            print(f"  {trans_type}: {count} transactions, ${total:,.2f}")
        print()
        
        # Summary by investor
        print("TRANSACTION SUMMARY BY INVESTOR:")
        print("-" * 40)
        for investor in df['investor_name'].unique():
            if pd.notna(investor):
                inv_data = df[df['investor_name'] == investor]
                count = len(inv_data)
                total = inv_data['amount'].sum()
                print(f"  {investor}: {count} transactions, ${total:,.2f}")
        print()
        
        # Export to Excel
        output_dir = Path(__file__).parent.parent / 'data' / 'exports'
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f'transactions_export_{timestamp}.xlsx'
        
        # Create Excel writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # All transactions
            df.to_excel(writer, sheet_name='All Transactions', index=False)
            
            # Summary by type (FIXED - flatten MultiIndex)
            type_summary = df.groupby('transaction_type').agg({
                'amount': ['count', 'sum'],
                'shares_transacted': 'sum'
            })
            # Flatten MultiIndex columns
            type_summary.columns = ['_'.join(col).strip() for col in type_summary.columns.values]
            type_summary = type_summary.reset_index()
            # Rename columns for clarity
            type_summary.columns = ['Transaction Type', 'Count', 'Total Amount', 'Total Shares']
            type_summary.to_excel(writer, sheet_name='Summary by Type', index=False)
            
            # Summary by investor (FIXED - flatten MultiIndex)
            inv_summary = df.groupby('investor_name').agg({
                'amount': ['count', 'sum'],
                'shares_transacted': 'sum'
            })
            # Flatten MultiIndex columns
            inv_summary.columns = ['_'.join(col).strip() for col in inv_summary.columns.values]
            inv_summary = inv_summary.reset_index()
            # Rename columns for clarity
            inv_summary.columns = ['Investor Name', 'Count', 'Total Amount', 'Total Shares']
            inv_summary.to_excel(writer, sheet_name='Summary by Investor', index=False)
            
            # Date range
            date_range = pd.DataFrame({
                'Metric': ['First Transaction', 'Last Transaction', 'Date Range (Days)', 'Total Transactions', 'Total Amount'],
                'Value': [
                    df['date'].min(),
                    df['date'].max(),
                    (pd.to_datetime(df['date'].max()) - pd.to_datetime(df['date'].min())).days,
                    len(df),
                    f"${df['amount'].sum():,.2f}"
                ]
            })
            date_range.to_excel(writer, sheet_name='Overview', index=False)
        
        print(f"✅ Excel file created: {output_file}")
        print()
        print(f"   Location: {output_file.relative_to(Path.cwd())}")
        print()
        
        # Display first few transactions
        print("FIRST 10 TRANSACTIONS:")
        print("-" * 80)
        display_cols = ['date', 'investor_name', 'transaction_type', 'amount', 'shares_transacted']
        print(df[display_cols].head(10).to_string(index=False))
        print()
        
        if len(df) > 10:
            print(f"... and {len(df) - 10} more transactions (see Excel file)")
            print()
        
        print("=" * 80)
        print("EXCEL FILE CONTAINS 4 SHEETS:")
        print("=" * 80)
        print("  1. All Transactions - Complete transaction history")
        print("  2. Summary by Type - Grouped by transaction type")
        print("  3. Summary by Investor - Grouped by investor")
        print("  4. Overview - Date ranges and totals")
        print()
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = export_transactions_to_excel()
    if success:
        print("✅ Export complete!")
    else:
        print("❌ Export failed")
