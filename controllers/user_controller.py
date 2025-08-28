from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
# Import DATABASE_NAME from the models module
from models.db_models import DATABASE_NAME 

# Create a Blueprint for user routes
user_bp = Blueprint('user_bp', __name__)

@user_bp.route('/register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username, password, 'user'))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('user_bp.user_login')) # Note the blueprint prefix
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different username.', 'danger')
            return render_template('user/user_register.html') 
        except Exception as e:
            flash(f'An error occurred during registration: {e}', 'danger')
            return render_template('user/user_register.html')
        finally:
            conn.close()
    return render_template('user/user_register.html')

@user_bp.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=? AND role='user'", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['role'] = user[3]
            session['username'] = user[1] 
            flash('Logged in successfully!', 'success')
            return redirect(url_for('user_bp.user_dashboard')) # Note the blueprint prefix
        else:
            flash('Invalid username or password. Please try again.', 'danger')
            return render_template('user/user_login.html')
    return render_template('user/user_login.html')

@user_bp.route('/dashboard')
def user_dashboard():
    if 'role' not in session or session['role'] != 'user':
        flash('Please log in as a user to access the dashboard.', 'warning')
        return redirect(url_for('user_bp.user_login')) # Note the blueprint prefix
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 
            pl.id, 
            pl.prime_location_name, 
            pl.price, 
            pl.address, 
            pl.pincode,
            pl.maximum_number_of_spots,
            COUNT(CASE WHEN ps.status = 'A' THEN 1 ELSE NULL END) AS available_spots
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON pl.id = ps.lot_id
        GROUP BY pl.id
        ORDER BY pl.prime_location_name
    ''')
    available_parking_lots = cursor.fetchall()

    user_id = session['user_id']
    cursor.execute('''
        SELECT 
            rps.id, 
            ps.id, 
            pl.prime_location_name, 
            rps.parking_timestamp, 
            pl.price
        FROM reserve_parking_spots rps
        JOIN parking_spots ps ON rps.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE rps.user_id = ? AND rps.leaving_timestamp IS NULL
    ''', (user_id,))
    current_booking = cursor.fetchone()

    # Chart Data for User Dashboard
    cursor.execute('''
        SELECT 
            SUM(parking_cost), 
            SUM(JULIANDAY(leaving_timestamp) - JULIANDAY(parking_timestamp)) * 24 
        FROM reserve_parking_spots 
        WHERE user_id = ? AND leaving_timestamp IS NOT NULL
    ''', (user_id,))
    user_summary_data = cursor.fetchone()
    total_parking_cost = user_summary_data[0] if user_summary_data and user_summary_data[0] is not None else 0
    total_parking_hours = user_summary_data[1] if user_summary_data and user_summary_data[1] is not None else 0

    cursor.execute('''
        SELECT 
            pl.prime_location_name,
            COUNT(rps.id) AS booking_count
        FROM reserve_parking_spots rps
        JOIN parking_spots ps ON rps.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE rps.user_id = ? AND rps.leaving_timestamp IS NOT NULL
        GROUP BY pl.prime_location_name
        ORDER BY booking_count DESC
    ''', (user_id,))
    user_bookings_per_lot_data = cursor.fetchall()

    cursor.execute('''
        SELECT 
            rps.id, 
            ps.id, 
            pl.prime_location_name, 
            rps.parking_timestamp, 
            rps.leaving_timestamp,
            rps.parking_cost_per_unit,
            rps.parking_cost 
        FROM reserve_parking_spots rps
        JOIN parking_spots ps ON rps.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE rps.user_id = ? AND rps.leaving_timestamp IS NOT NULL
        ORDER BY rps.leaving_timestamp DESC
    ''', (user_id,))
    past_bookings = cursor.fetchall()

    conn.close()
    
    return render_template('user/user_dashboard.html', 
                           available_parking_lots=available_parking_lots,
                           current_booking=current_booking,
                           past_bookings=past_bookings,
                           total_parking_cost=total_parking_cost, 
                           total_parking_hours=total_parking_hours, 
                           user_bookings_per_lot_data=user_bookings_per_lot_data)

@user_bp.route('/book_spot/<int:lot_id>', methods=['POST'])
def book_spot(lot_id):
    if 'role' not in session or session['role'] != 'user':
        flash('Please log in as a user to book a spot.', 'warning')
        return redirect(url_for('user_bp.user_login')) # Note the blueprint prefix

    user_id = session['user_id']
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM parking_spots WHERE lot_id = ? AND status = 'A' LIMIT 1", (lot_id,))
        available_spot = cursor.fetchone()

        if available_spot:
            spot_id = available_spot[0]
            parking_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("UPDATE parking_spots SET status = 'O' WHERE id = ?", (spot_id,))

            cursor.execute("SELECT price FROM parking_lots WHERE id = ?", (lot_id,))
            parking_cost_per_unit = cursor.fetchone()[0]

            cursor.execute('''
                INSERT INTO reserve_parking_spots 
                (spot_id, user_id, parking_timestamp, parking_cost_per_unit)
                VALUES (?, ?, ?, ?)
            ''', (spot_id, user_id, parking_timestamp, parking_cost_per_unit))
            
            conn.commit()
            flash(f'Spot booked successfully in Lot ID {lot_id}! Your spot ID is {spot_id}.', 'success')
        else:
            flash(f'No available spots found in Lot ID {lot_id}. Please choose another lot.', 'danger')
    except Exception as e:
        conn.rollback()
        flash(f'An error occurred while booking the spot: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('user_bp.user_dashboard')) # Note the blueprint prefix

@user_bp.route('/release_spot/<int:booking_id>', methods=['POST'])
def release_spot(booking_id):
    if 'role' not in session or session['role'] != 'user':
        flash('Please log in as a user to release a spot.', 'warning')
        return redirect(url_for('user_bp.user_login')) # Note the blueprint prefix

    user_id = session['user_id']
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT rps.spot_id, rps.parking_timestamp, pl.price
            FROM reserve_parking_spots rps
            JOIN parking_spots ps ON rps.spot_id = ps.id
            JOIN parking_lots pl ON ps.lot_id = pl.id
            WHERE rps.id = ? AND rps.user_id = ? AND rps.leaving_timestamp IS NULL
        ''', (booking_id, user_id))
        booking_details = cursor.fetchone()

        if booking_details:
            spot_id = booking_details[0]
            parking_timestamp_str = booking_details[1]
            parking_cost_per_unit = booking_details[2]
            
            leaving_timestamp = datetime.now()
            leaving_timestamp_str = leaving_timestamp.strftime('%Y-%m-%d %H:%M:%S')

            parking_timestamp_dt = datetime.strptime(parking_timestamp_str, '%Y-%m-%d %H:%M:%S')
            duration_seconds = (leaving_timestamp - parking_timestamp_dt).total_seconds()
            duration_hours = duration_seconds / 3600.0 
            
            if duration_hours < (1/60): 
                duration_hours = (1/60) 

            total_cost = duration_hours * parking_cost_per_unit
            
            cursor.execute('''
                UPDATE reserve_parking_spots SET 
                leaving_timestamp = ?, 
                parking_cost = ? 
                WHERE id = ?
            ''', (leaving_timestamp_str, total_cost, booking_id))

            cursor.execute("UPDATE parking_spots SET status = 'A' WHERE id = ?", (spot_id,))
            
            conn.commit()
            flash(f'Spot ID {spot_id} released successfully! Total cost: ${total_cost:.2f}', 'success')
        else:
            flash('Booking not found or already released.', 'danger')
    except Exception as e:
        conn.rollback()
        flash(f'An error occurred while releasing the spot: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('user_bp.user_dashboard')) # Note the blueprint prefix

@user_bp.route('/logout')
def user_logout():
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('user_bp.user_login')) # Note the blueprint prefix
