"""
Clear all appointments from the database.
"""

from database import get_db, Appointment, engine
from sqlalchemy import text

def clear_all_appointments():
    """Delete all appointments from the database."""
    db = next(get_db())
    
    try:
        # Count before deletion
        count = db.query(Appointment).count()
        print(f"📊 Found {count} appointment(s) in database")
        
        if count == 0:
            print("✅ Database is already empty!")
            return
        
        # Confirm deletion
        confirmation = input(f"⚠️  Are you sure you want to delete ALL {count} appointments? (yes/no): ")
        
        if confirmation.lower() != 'yes':
            print("❌ Deletion cancelled")
            return
        
        # Delete all appointments
        deleted = db.query(Appointment).delete()
        db.commit()
        
        print(f"✅ Successfully deleted {deleted} appointment(s)")
        print("🔄 Resetting auto-increment counter...")
        
        # Reset SQLite auto-increment counter (only if table exists)
        try:
            # Check if sqlite_sequence table exists
            result = db.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
            )).fetchone()
            
            if result:
                db.execute(text("DELETE FROM sqlite_sequence WHERE name='appointments'"))
                db.commit()
                print("✅ Auto-increment counter reset")
            else:
                print("ℹ️  No auto-increment counter to reset (table not found)")
        
        except Exception as reset_error:
            print(f"⚠️  Could not reset auto-increment: {reset_error}")
            print("ℹ️  This is normal if AUTOINCREMENT is not used")
        
        print("✅ Database cleared successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error clearing database: {e}")
    
    finally:
        db.close()


def reset_database():
    """Drop and recreate the entire database."""
    print("⚠️  WARNING: This will DROP and RECREATE the entire database!")
    confirmation = input("Type 'RESET' to confirm: ")
    
    if confirmation != 'RESET':
        print("❌ Reset cancelled")
        return
    
    from database import Base
    
    try:
        # Drop all tables
        print("🗑️  Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        
        # Recreate all tables
        print("🔨 Creating fresh tables...")
        Base.metadata.create_all(bind=engine)
        
        print("✅ Database reset successfully!")
        print("ℹ️  Next appointment ID will start from 1")
        
    except Exception as e:
        print(f"❌ Error resetting database: {e}")


def view_database_stats():
    """Display database statistics."""
    db = next(get_db())
    
    try:
        total = db.query(Appointment).count()
        active = db.query(Appointment).filter(Appointment.canceled == False).count()
        canceled = db.query(Appointment).filter(Appointment.canceled == True).count()
        
        print()
        print("=" * 50)
        print("📊 Database Statistics")
        print("=" * 50)
        print(f"Total Appointments:     {total}")
        print(f"Active Appointments:    {active}")
        print(f"Canceled Appointments:  {canceled}")
        print("=" * 50)
        
        if total > 0:
            print()
            print("Recent Appointments:")
            print("-" * 50)
            appointments = db.query(Appointment).order_by(Appointment.id.desc()).limit(5).all()
            for apt in appointments:
                status = "❌ CANCELED" if apt.canceled else "✅ ACTIVE"
                print(f"#{apt.id}: {apt.patient_name} - {apt.reason} ({status})")
            print("-" * 50)
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("🗑️  Database Cleanup Utility")
    print("=" * 50)
    print()
    print("Options:")
    print("1. Clear all appointments (keeps table structure)")
    print("2. Reset entire database (drops and recreates)")
    print("3. View database statistics")
    print("4. Cancel")
    print()
    
    choice = input("Select option (1/2/3/4): ")
    
    if choice == "1":
        clear_all_appointments()
    elif choice == "2":
        reset_database()
    elif choice == "3":
        view_database_stats()
    else:
        print("❌ Operation cancelled")