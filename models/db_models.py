import sqlite3

DATABASE_NAME = "parking_app.db"

def create_tables():
    """
    Creates all necessary tables for the application and the Admin user.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    # Create parking_lots table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prime_location_name TEXT NOT NULL UNIQUE,
            price REAL NOT NULL,
            address TEXT,
            pincode TEXT,
            maximum_number_of_spots INTEGER NOT NULL
        )
    ''')

    # Create parking_spots table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id) ON DELETE CASCADE
        )
    ''')

    # Create reserve_parking_spots table
    # ADDED 'parking_cost REAL' column here
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reserve_parking_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            parking_timestamp TEXT NOT NULL,
            leaving_timestamp TEXT,
            parking_cost_per_unit REAL,
            parking_cost REAL,  -- New column for total calculated cost
            FOREIGN KEY (spot_id) REFERENCES parking_spots (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Add Admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    admin_exists = cursor.fetchone()
    if not admin_exists:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ('admin', 'adminpassword', 'admin'))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()
    print(f"Database '{DATABASE_NAME}' and tables created successfully.")
