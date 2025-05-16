from flask import Blueprint, render_template, redirect, url_for, request, flash
from auth import login_required, therapist_required, admin_required, get_current_user
from models import get_user, get_therapist_patients

# Initialize therapists blueprint
therapists_bp = Blueprint('therapists', __name__, url_prefix='/therapists')

@therapists_bp.route('/dashboard')
@login_required
@therapist_required
def dashboard():
    """Display therapist dashboard."""
    user = get_current_user()
    
    # Get assigned patients
    patients = get_therapist_patients(user.get('id'))
    
    # Sort patients by name
    patients.sort(key=lambda x: x.get('name', ''))
    
    # Get some stats
    patient_count = len(patients)
    
    # Get patients with recent progress updates
    from models import get_patient_progress
    recent_updates = []
    
    for patient in patients:
        updates = get_patient_progress(patient.get('id'))
        if updates:
            recent_updates.append({
                'patient': patient,
                'update': updates[0]  # Most recent update
            })
    
    # Sort by most recent update
    recent_updates.sort(key=lambda x: x['update'].get('date', ''), reverse=True)
    recent_updates = recent_updates[:5]  # Limit to 5
    
    return render_template('therapists/dashboard.html', 
                          user=user,
                          patients=patients,
                          patient_count=patient_count,
                          recent_updates=recent_updates)

@therapists_bp.route('/')
@login_required
@admin_required
def index():
    """Display list of therapists (admin only)."""
    # Get all therapists
    from models import get_db
    db = get_db()
    therapists_ref = db.collection('users').where('role', '==', 'therapist').stream()
    
    therapists = []
    for therapist in therapists_ref:
        data = therapist.to_dict()
        data['id'] = therapist.id
        
        # Get patient count
        patients = get_therapist_patients(therapist.id)
        data['patient_count'] = len(patients)
        
        therapists.append(data)
    
    # Sort therapists by name
    therapists.sort(key=lambda x: x.get('name', ''))
    
    return render_template('therapists/index.html', therapists=therapists)

@therapists_bp.route('/view/<therapist_id>')
@login_required
@admin_required
def view(therapist_id):
    """View detailed therapist information (admin only)."""
    therapist = get_user(therapist_id)
    
    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))
    
    # Add ID to the therapist data
    therapist['id'] = therapist_id
    
    # Get assigned patients
    patients = get_therapist_patients(therapist_id)
    
    return render_template('therapists/view.html', 
                          therapist=therapist, 
                          patients=patients)

@therapists_bp.route('/<therapist_id>/patients')
@login_required
@admin_required
def therapist_patients(therapist_id):
    """View patients assigned to a therapist (admin only)."""
    therapist = get_user(therapist_id)
    
    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))
    
    # Add ID to the therapist data
    therapist['id'] = therapist_id
    
    # Get assigned patients
    patients = get_therapist_patients(therapist_id)
    
    # Get all patients for potential assignment
    from models import get_patients
    all_patients = get_patients()
    
    # Filter out already assigned patients
    assigned_ids = [p.get('id') for p in patients]
    unassigned_patients = [p for p in all_patients if p.get('id') not in assigned_ids]
    
    return render_template('therapists/patients.html', 
                          therapist=therapist, 
                          patients=patients,
                          unassigned_patients=unassigned_patients)

@therapists_bp.route('/<therapist_id>/assign', methods=['POST'])
@login_required
@admin_required
def assign_patient(therapist_id):
    """Assign a patient to a therapist (admin only)."""
    therapist = get_user(therapist_id)
    
    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))
    
    patient_id = request.form.get('patient_id')
    
    if not patient_id:
        flash('No patient selected', 'danger')
        return redirect(url_for('therapists.therapist_patients', therapist_id=therapist_id))
    
    try:
        # Assign patient to therapist
        from models import assign_patient as assign_patient_func
        assign_patient_func(therapist_id, patient_id)
        
        flash('Patient assigned successfully', 'success')
    except Exception as e:
        flash(f'Error assigning patient: {str(e)}', 'danger')
    
    return redirect(url_for('therapists.therapist_patients', therapist_id=therapist_id))

@therapists_bp.route('/<therapist_id>/unassign/<patient_id>', methods=['POST'])
@login_required
@admin_required
def unassign_patient(therapist_id, patient_id):
    """Remove a patient-therapist assignment (admin only)."""
    therapist = get_user(therapist_id)
    
    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))
    
    try:
        # Unassign patient from therapist
        from models import unassign_patient as unassign_patient_func
        unassign_patient_func(therapist_id, patient_id)
        
        flash('Patient unassigned successfully', 'success')
    except Exception as e:
        flash(f'Error unassigning patient: {str(e)}', 'danger')
    
    return redirect(url_for('therapists.therapist_patients', therapist_id=therapist_id))