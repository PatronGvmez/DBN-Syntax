from flask import Blueprint, render_template, redirect, url_for, request, flash
from auth import login_required, admin_required, get_current_user
from models import create_user, get_patients, get_user

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
    therapists_ref = db.collection('users').where('role', '==', 'therapist').stream()
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
    
    return render_template('admin/dashboard.html', 
                          user=user,
                          patient_count=patient_count,
                          therapist_count=therapist_count,
                          recent_updates=recent_updates)

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
    from models import get_db
    db = get_db()
    therapists_ref = db.collection('users').where('role', '==', 'therapist').stream()
    
    therapists = []
    for therapist in therapists_ref:
        data = therapist.to_dict()
        data['id'] = therapist.id
        therapists.append(data)
    
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