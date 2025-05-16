from flask import Flask, render_template, redirect, url_for, flash, request, session
from dotenv import load_dotenv
import os
from datetime import datetime

# Import custom modules
from auth import auth_bp, login_required, admin_required, get_current_user
from models import initialize_firebase, get_db
from patients import patients_bp
from therapists import therapists_bp
from admin import admin_bp

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize Firebase
initialize_firebase()

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(patients_bp)
app.register_blueprint(therapists_bp)
app.register_blueprint(admin_bp)

# Global template context
@app.context_processor
def inject_user():
    user_data = None
    if 'user_id' in session:
        user_data = get_current_user()
    return {'user': user_data}

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Home route
@app.route('/')
def home():
    if 'user_id' in session:
        user_data = get_current_user()
        if user_data:
            if user_data.get('role') == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('therapists.dashboard'))
    return render_template('index.html')

# Main execution
if __name__ == '__main__':
    app.run(debug=True)