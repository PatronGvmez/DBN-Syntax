from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from routes.auth import login_required, admin_required, get_current_user
from models import create_user, get_patients, get_user, update_user

# Initialize admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Display admin dashboard."""
    user = get_current_user()
    
    # Get statistics
    from models import get_db
    db = get_db()
    
    # Count patients
    patients_ref = db.collection('patients').stream()
    patient_count = sum(1 for _ in patients_ref)
    
    # Count therapists
    therapists_ref = db.collection('therapists').stream()
    therapist_count = sum(1 for _ in therapists_ref)
    
    # Get recent progress updates
    updates_ref = db.collection('progress_updates').order_by('created_at', direction='DESCENDING').limit(5).stream()
    recent_updates = []
    
    for update in updates_ref:
        data = update.to_dict()
        data['id'] = update.id
        
        # Get patient name
        patient = None
        if 'patient_id' in data:
            from models import get_patient
            patient = get_patient(data['patient_id'])
        
        # Get therapist name
        therapist = None
        if 'therapist_id' in data:
            therapist = get_user(data['therapist_id'])
        
        recent_updates.append({
            'update': data,
            'patient': patient,
            'therapist': therapist
        })
    
    from datetime import datetime
    return render_template('admin/dashboard.html', 
                          user=user,
                          patient_count=patient_count,
                          therapist_count=therapist_count,
                          recent_updates=recent_updates,
                          now=datetime.now())

@admin_bp.route('/therapists/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_therapist():
    """Create a new therapist account."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone', '')
        
        # Form validation
        if not all([name, email, password]):
            flash('Please fill out all required fields', 'danger')
            return render_template('admin/new_therapist.html', 
                                   name=name, email=email, phone=phone)
        
        try:
            # Create therapist account
            user_id = create_user(
                email=email,
                password=password,
                role='therapist',
                name=name,
                phone=phone
            )
            
            if user_id:
                flash('Therapist account created successfully', 'success')
                return redirect(url_for('therapists.index'))
            else:
                flash('Failed to create therapist account', 'danger')
                
        except Exception as e:
            flash(f'Error creating therapist account: {str(e)}', 'danger')
    
    return render_template('admin/new_therapist.html')

@admin_bp.route('/patients/assignments')
@login_required
@admin_required
def patient_assignments():
    """Manage patient-therapist assignments."""
    # Get all patients
    patients = get_patients()
    
    # Get all therapists
    from models import get_all_therapists
    therapists = get_all_therapists()
    
    # Sort therapists by name
    therapists.sort(key=lambda x: x.get('name', ''))
    
    # For each patient, get assigned therapists
    from models import get_patient_therapists
    for patient in patients:
        patient['therapists'] = get_patient_therapists(patient.get('id'))
    
    return render_template('admin/patient_assignments.html', 
                          patients=patients,
                          therapists=therapists)

@admin_bp.route('/patients/<patient_id>/assign', methods=['POST'])
@login_required
@admin_required
def assign_patient(patient_id):
    """Assign a therapist to a patient."""
    therapist_id = request.form.get('therapist_id')
    
    if not therapist_id:
        flash('No therapist selected', 'danger')
        return redirect(url_for('admin.patient_assignments'))
    
    try:
        # Assign therapist to patient
        from models import assign_patient as assign_patient_func
        assign_patient_func(therapist_id, patient_id)
        
        flash('Therapist assigned successfully', 'success')
    except Exception as e:
        flash(f'Error assigning therapist: {str(e)}', 'danger')
    
    return redirect(url_for('admin.patient_assignments'))

@admin_bp.route('/patients/<patient_id>/unassign/<therapist_id>', methods=['POST'])
@login_required
@admin_required
def unassign_patient(patient_id, therapist_id):
    """Remove a patient-therapist assignment."""
    try:
        # Unassign therapist from patient
        from models import unassign_patient as unassign_patient_func
        unassign_patient_func(therapist_id, patient_id)
        
        flash('Therapist unassigned successfully', 'success')
    except Exception as e:
        flash(f'Error unassigning therapist: {str(e)}', 'danger')
    
    return redirect(url_for('admin.patient_assignments'))

@admin_bp.route('/assignment-requests')
@login_required
@admin_required
def assignment_requests():
    """View and manage patient assignment requests."""
    from models import get_pending_assignment_requests, get_users_by_role
    
    # Get pending requests
    pending_requests = get_pending_assignment_requests()
    
    # Get available therapists
    therapists = get_users_by_role('therapist')
    
    return render_template('admin/assignment_requests.html', 
                          pending_requests=pending_requests,
                          therapists=therapists)

@admin_bp.route('/approve-assignment/<request_id>/<therapist_id>')
@login_required
@admin_required
def approve_assignment(request_id, therapist_id):
    """Approve a patient assignment request."""
    try:
        from models import approve_patient_assignment_request
        
        success = approve_patient_assignment_request(request_id, therapist_id)
        
        if success:
            flash('Patient assignment approved successfully', 'success')
        else:
            flash('Failed to approve assignment', 'danger')
            
    except Exception as e:
        flash(f'Error approving assignment: {str(e)}', 'danger')
    
    return redirect(url_for('admin.assignment_requests'))

@admin_bp.route('/profile')
@login_required
@admin_required
def profile():
    """Display admin profile."""
    user = get_current_user()
    return render_template('admin/profile.html', user=user)

@admin_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile():
    """Edit admin profile."""
    user = get_current_user()
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone', '')
        
        if not name:
            flash('Name is required', 'danger')
            return render_template('admin/edit_profile.html', user=user)
            
        try:
            # Update user in Firestore
            user_id = update_user(session['user_id'], {
                'name': name,
                'phone': phone
            })
            
            if user_id:
                flash('Profile updated successfully', 'success')
                return redirect(url_for('admin.profile'))
            else:
                flash('Failed to update profile: User not found', 'danger')
            
        except Exception as e:
            flash(f'Failed to update profile: {str(e)}', 'danger')
    
    return render_template('admin/edit_profile.html', user=user)