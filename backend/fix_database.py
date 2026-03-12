from database import Database  # imports the Database class which manages the SQLite connection

def fix_existing_data():
    """Clear all data and re-import from Excel"""
    # ⚠️ this function wipes ALL events from the database — only run this during initial setup or data migration
    print("🔧 Starting database fix...")
    
    db = Database()           # creates a Database instance which also calls init_database() to ensure tables exist
    conn = db.get_connection() # opens a connection to the SQLite file
    cursor = conn.cursor()     # cursor is the object that executes SQL commands
    
    # 1. Delete all existing events and related data
    print("🗑️ Clearing existing data...")
    cursor.execute('DELETE FROM event_files')     # removes all file attachment records first — avoids foreign key errors
    cursor.execute('DELETE FROM status_history')  # removes all status change history records
    cursor.execute('DELETE FROM events')          # removes all event rows
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='events'")
    # resets the auto-increment counter for events so new IDs start from 1 again
    conn.commit()  # saves all four deletions to disk as one transaction
    conn.close()
    
    print("✅ Database cleared!")
    
    # 2. Re-import from Excel with correct mapping
    print("\n📥 Re-importing data from Excel...")
    from import_excel import import_excel_data  # imported here (not at top) to avoid circular import issues
    
    excel_path = r'C:\Users\tal_ba\Documents\DataAnalysis-Tal\מערכת תקלות-פיתוח\חוברת1.xlsx'
    # ⚠️ this is a hardcoded absolute path — must be updated if the Excel file is moved or run on a different machine
    import_excel_data(excel_path)  # calls the importer which reads the Excel and inserts rows into the database
    
    print("\n✅ Database fix completed!")

if __name__ == '__main__':
    fix_existing_data()  # only runs when this file is executed directly — not when imported by another module