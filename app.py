from flask import Flask, redirect, url_for
import sqlite3
from models.db_models import create_tables, DATABASE_NAME

# Import blueprints from your controller files
from controllers.admin_controller import admin_bp
from controllers.user_controller import user_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # Keep this secret key for session and flash messages

# Create database tables on application startup
create_tables()

# Register blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(user_bp, url_prefix='/user')

# Root URL redirection - now redirects to the user login blueprint
@app.route('/')
def index():
    return redirect(url_for('user_bp.user_login')) # Note the blueprint prefix

if __name__ == '__main__':
    app.run(debug=True)
