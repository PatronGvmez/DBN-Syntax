from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from functools import wraps
import firebase_admin
from firebase_admin import auth
from models import get_user, get_db, create_user, get_user_by_email, update_user
import re

# Initialize authentication blueprint
auth_bp = Blueprint('auth', __name__)

# Form validation
def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Authentication decorators
def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if not user or user.get('role') != 'admin':
            flash('You must be an admin to access this page', 'danger')
            return redirect(url_for('home'))
            
        return f(*args, **kwargs)
    return decorated_function

def therapist_required(f):
    """Decorator to require therapist role for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if not user or user.get('role') != 'therapist':
            flash('You must be a therapist to access this page', 'danger')
            return redirect(url_for('home'))
            
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get the current user based on session."""
    if 'user_id' in session:
        return get_user(session['user_id'])
    return None

# Authentication routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return render_template('auth/login.html')
            
        try:
            # Get user data from Firestore using email
            user_data = get_user_by_email(email)
            
            if user_data:
                # Authenticate with Firebase using the user ID
                try:
                    firebase_user = auth.get_user(user_data['id'])
                    # In a real app, we would verify the password with Firebase
                    # Here we're simplifying for the example
                    
                    session['user_id'] = user_data['id']
                    flash(f'Welcome back, {user_data.get("name", "")}!', 'success')
                    
                    # Redirect based on role
                    if user_data.get('role') == 'admin':
                        return redirect(url_for('admin.dashboard'))
                    elif user_data.get('role') == 'therapist':
                        return redirect(url_for('therapists.dashboard'))
                    elif user_data.get('role') == 'patient':
                        return redirect(url_for('patients.dashboard'))  # Redirect to patient dashboard
                    else:
                        # Default fallback
                        return redirect(url_for('home'))
                except Exception as auth_error:
                    flash(f'Authentication failed: {str(auth_error)}', 'danger')
            else:
                flash('User account not found', 'danger')
                
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone', '')
        
        # Form validation
        if not all([name, email, password, confirm_password]):
            flash('Please fill out all required fields', 'danger')
            return render_template('auth/register.html', 
                                   name=name, email=email, phone=phone)
        
        if not validate_email(email):
            flash('Please enter a valid email address', 'danger')
            return render_template('auth/register.html', 
                                   name=name, email=email, phone=phone)
                                   
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register.html', 
                                   name=name, email=email, phone=phone)
                                   
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'danger')
            return render_template('auth/register.html', 
                                   name=name, email=email, phone=phone)
        
        try:
            # Create user (as therapist by default)
            user_id = create_user(
                email=email,
                password=password,
                role='therapist',  # Default role
                name=name,
                phone=phone
            )
            
            if user_id:
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Registration failed', 'danger')
                
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

@auth_bp.route('/profile')
@login_required
def profile():
    """Redirect to role-specific profile page."""
    user = get_current_user()
    role = user.get('role')
    
    if role == 'admin':
        return redirect(url_for('admin.profile'))
    elif role == 'therapist':
        return redirect(url_for('therapists.profile'))
    elif role == 'patient':
        return redirect(url_for('patients.profile'))
    else:
        flash('Unknown user role', 'danger')
        return redirect(url_for('home'))

@auth_bp.route('/profile/edit')
@login_required
def edit_profile():
    """Redirect to role-specific edit profile page."""
    user = get_current_user()
    role = user.get('role')
    
    if role == 'admin':
        return redirect(url_for('admin.edit_profile'))
    elif role == 'therapist':
        return redirect(url_for('therapists.edit_profile'))
    elif role == 'patient':
        return redirect(url_for('patients.edit_profile'))
    else:
        flash('Unknown user role', 'danger')
        return redirect(url_for('home'))