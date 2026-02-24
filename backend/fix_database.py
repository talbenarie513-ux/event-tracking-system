from database import Database

def fix_existing_data():
    """Clear all data and re-import from Excel"""
    print("🔧 Starting database fix...")
    
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # 1. Delete all existing events and related data
    print("🗑️ Clearing existing data...")
    cursor.execute('DELETE FROM event_files')
    cursor.execute('DELETE FROM status_history')
    cursor.execute('DELETE FROM events')
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='events'")
    conn.commit()
    conn.close()
    
    print("✅ Database cleared!")
    
    # 2. Re-import from Excel with correct mapping
    print("\n📥 Re-importing data from Excel...")
    from import_excel import import_excel_data
    
    excel_path = r'C:\Users\tal_ba\Documents\DataAnalysis-Tal\מערכת תקלות-פיתוח\חוברת1.xlsx'
    import_excel_data(excel_path)
    
    print("\n✅ Database fix completed!")

if __name__ == '__main__':
    fix_existing_data()