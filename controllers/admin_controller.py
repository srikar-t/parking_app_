from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
from models.db_models import DATABASE_NAME 

admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=? AND role='admin'", (username, password))
        admin = cursor.fetchone()
        conn.close()

        if admin:
            session['user_id'] = admin[0]
            session['role'] = admin[3]
            session['username'] = admin[1] 
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_bp.admin_dashboard')) 
        else:
            flash('Invalid admin credentials. Please try again.', 'danger')
            return render_template('admin/admin_login.html')
    return render_template('admin/admin_login.html')

@admin_bp.route('/dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        flash('Please log in as an administrator to access the dashboard.', 'warning')
        return redirect(url_for('admin_bp.admin_login')) 
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM parking_lots")
    parking_lots = cursor.fetchall()

    # --- Parking Spot Search Logic ---
    search_query = request.args.get('search_query', '').strip() 
    
    if search_query:
        # Prepare the query for filtering
        # Check if the search_query is purely numeric to search by Spot ID
        if search_query.isdigit():
            # If it's a digit, try to search by Spot ID and also by Lot Name (just in case)
            # Use a single query with OR condition
            cursor.execute('''
                SELECT 
                    ps.id, 
                    pl.prime_location_name, 
                    ps.status 
                FROM parking_spots ps
                JOIN parking_lots pl ON ps.lot_id = pl.id
                WHERE ps.id = ? OR pl.prime_location_name LIKE ?
                ORDER BY pl.prime_location_name, ps.id
            ''', (int(search_query), '%' + search_query + '%'))
        else:
            # If it's not a digit, only search by Lot Name
            cursor.execute('''
                SELECT 
                    ps.id, 
                    pl.prime_location_name, 
                    ps.status 
                FROM parking_spots ps
                JOIN parking_lots pl ON ps.lot_id = pl.id
                WHERE pl.prime_location_name LIKE ?
                ORDER BY pl.prime_location_name, ps.id
            ''', ('%' + search_query + '%',)) # Tuple with single element
        parking_spots = cursor.fetchall()
    else:
        # If no search query, fetch all parking spots
        cursor.execute('''
            SELECT 
                ps.id, 
                pl.prime_location_name, 
                ps.status 
            FROM parking_spots ps
            JOIN parking_lots pl ON ps.lot_id = pl.id
            ORDER BY pl.prime_location_name, ps.id
        ''')
        parking_spots = cursor.fetchall()

    cursor.execute("SELECT id, username FROM users WHERE role = 'user' ORDER BY username")
    registered_users = cursor.fetchall()

    # Chart Data for Admin Dashboard
    cursor.execute("SELECT COUNT(*) FROM parking_spots WHERE status = 'A'")
    total_available_spots = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM parking_spots WHERE status = 'O'")
    total_occupied_spots = cursor.fetchone()[0]

    cursor.execute('''
        SELECT 
            pl.prime_location_name,
            COUNT(CASE WHEN ps.status = 'A' THEN 1 ELSE NULL END) AS available_count,
            COUNT(CASE WHEN ps.status = 'O' THEN 1 ELSE NULL END) AS occupied_count
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON pl.id = ps.lot_id
        GROUP BY pl.prime_location_name
        ORDER BY pl.prime_location_name
    ''')
    spots_per_lot_data = cursor.fetchall()

    conn.close()
        
    return render_template('admin/admin_dashboard.html', 
                           parking_lots=parking_lots, 
                           parking_spots=parking_spots, 
                           registered_users=registered_users,
                           total_available_spots=total_available_spots,
                           total_occupied_spots=total_occupied_spots,
                           spots_per_lot_data=spots_per_lot_data)


@admin_bp.route('/create_lot', methods=['GET', 'POST'])
def create_lot():
    if 'role' not in session or session['role'] != 'admin':
        flash('Please log in as an administrator to create a parking lot.', 'warning')
        return redirect(url_for('admin_bp.admin_login')) 

    if request.method == 'POST':
        prime_location_name = request.form['prime_location_name']
        price = float(request.form['price'])
        address = request.form['address']
        pincode = request.form['pincode']
        maximum_number_of_spots = int(request.form['maximum_number_of_spots'])

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO parking_lots 
                (prime_location_name, price, address, pincode, maximum_number_of_spots)
                VALUES (?, ?, ?, ?, ?)
            ''', (prime_location_name, price, address, pincode, maximum_number_of_spots))
            
            lot_id = cursor.lastrowid

            for _ in range(maximum_number_of_spots):
                cursor.execute('''
                    INSERT INTO parking_spots (lot_id, status)
                    VALUES (?, 'A')
                ''', (lot_id,))

            conn.commit()
            flash(f'Parking Lot "{prime_location_name}" created successfully with {maximum_number_of_spots} spots!', 'success')
            return redirect(url_for('admin_bp.admin_dashboard')) 
        except sqlite3.IntegrityError as e:
            flash(f'Error: A parking lot with the location name "{prime_location_name}" already exists. Details: {e}', 'danger')
            return render_template('admin/create_lot.html')
        except Exception as e:
            flash(f'An unexpected error occurred while creating the lot: {e}', 'danger')
            return render_template('admin/create_lot.html')
        finally:
            conn.close()

    return render_template('admin/create_lot.html')

@admin_bp.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    if 'role' not in session or session['role'] != 'admin':
        flash('Please log in as an administrator to edit a parking lot.', 'warning')
        return redirect(url_for('admin_bp.admin_login')) 

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    lot = None 

    if request.method == 'POST':
        prime_location_name = request.form['prime_location_name']
        price = float(request.form['price'])
        address = request.form['address']
        pincode = request.form['pincode']
        new_maximum_number_of_spots = int(request.form['maximum_number_of_spots'])

        try:
            cursor.execute("SELECT maximum_number_of_spots FROM parking_lots WHERE id = ?", (lot_id,))
            current_max_spots = cursor.fetchone()[0]

            cursor.execute('''
                UPDATE parking_lots SET 
                prime_location_name = ?, 
                price = ?, 
                address = ?, 
                pincode = ?, 
                maximum_number_of_spots = ?
                WHERE id = ?
            ''', (prime_location_name, price, address, pincode, new_maximum_number_of_spots, lot_id))
            
            if new_maximum_number_of_spots > current_max_spots:
                spots_to_add = new_maximum_number_of_spots - current_max_spots
                for _ in range(spots_to_add):
                    cursor.execute("INSERT INTO parking_spots (lot_id, status) VALUES (?, 'A')", (lot_id,))
                flash(f'Added {spots_to_add} new spots to lot "{prime_location_name}".', 'info')
            elif new_maximum_number_of_spots < current_max_spots:
                cursor.execute("SELECT COUNT(*) FROM parking_spots WHERE lot_id = ? AND status = 'A'", (lot_id,))
                available_spots = cursor.fetchone()[0]

                spots_to_remove = current_max_spots - new_maximum_number_of_spots
                
                if spots_to_remove > available_spots:
                    conn.rollback() 
                    flash(f'Cannot decrease spots for "{prime_location_name}". There are too many occupied spots or not enough available spots to remove {spots_to_remove} spots.', 'danger')
                    cursor.execute("SELECT * FROM parking_lots WHERE id = ?", (lot_id,))
                    lot = cursor.fetchone() 
                    return render_template('admin/edit_lot.html', lot=lot)
                
                cursor.execute('''
                    DELETE FROM parking_spots 
                    WHERE id IN (
                        SELECT id FROM parking_spots 
                        WHERE lot_id = ? AND status = 'A' 
                        LIMIT ?
                    )
                ''', (lot_id, spots_to_remove))
                flash(f'Removed {spots_to_remove} spots from lot "{prime_location_name}".', 'info')

            conn.commit()
            flash(f'Parking Lot "{prime_location_name}" updated successfully!', 'success')
            return redirect(url_for('admin_bp.admin_dashboard')) 
        except sqlite3.IntegrityError as e:
            conn.rollback() 
            flash(f'Error: A parking lot with the location name "{prime_location_name}" already exists. Details: {e}', 'danger')
            cursor.execute("SELECT * FROM parking_lots WHERE id = ?", (lot_id,))
            lot = cursor.fetchone() 
            return render_template('admin/edit_lot.html', lot=lot) 
        except Exception as e:
            conn.rollback() 
            flash(f'An unexpected error occurred while updating the lot: {e}', 'danger')
            cursor.execute("SELECT * FROM parking_lots WHERE id = ?", (lot_id,))
            lot = cursor.fetchone() 
            return render_template('admin/edit_lot.html', lot=lot) 
        finally:
            conn.close() 

    cursor.execute("SELECT * FROM parking_lots WHERE id = ?", (lot_id,))
    lot = cursor.fetchone()
    conn.close()

    if lot is None:
        flash('Parking lot not found.', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard')) 
        
    return render_template('admin/edit_lot.html', lot=lot)

@admin_bp.route('/delete_lot/<int:lot_id>', methods=['POST'])
def delete_lot(lot_id):
    if 'role' not in session or session['role'] != 'admin':
        flash('Please log in as an administrator to delete a parking lot.', 'warning')
        return redirect(url_for('admin_bp.admin_login')) 

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM parking_spots WHERE lot_id = ? AND status = 'O'", (lot_id,))
        occupied_spots_count = cursor.fetchone()[0]

        if occupied_spots_count > 0:
            flash(f'Cannot delete parking lot ID {lot_id}. It still has {occupied_spots_count} occupied spot(s).', 'danger')
        else:
            cursor.execute("SELECT prime_location_name FROM parking_lots WHERE id = ?", (lot_id,))
            lot_name_result = cursor.fetchone() 
            lot_name = lot_name_result[0] if lot_name_result else str(lot_id) 

            cursor.execute("DELETE FROM parking_lots WHERE id = ?", (lot_id,))
            
            conn.commit()
            flash(f'Parking Lot "{lot_name}" and its spots deleted successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred while deleting the parking lot: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin_bp.admin_dashboard')) 

@admin_bp.route('/logout')
def admin_logout():
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('username', None)
    flash('You have been logged out as Admin.', 'info')
    return redirect(url_for('admin_bp.admin_login'))
