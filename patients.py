from flask import Blueprint, render_template, redirect, url_for, request, flash
from auth import login_required, therapist_required, get_current_user
from models import (get_patient, get_patients, create_patient, update_patient, 
                    get_patient_progress, add_progress_update, get_patient_therapists)

# Initialize patients blueprint
patients_bp = Blueprint('patients', __name__, url_prefix='/patients')

@patients_bp.route('/')
@login_required
def index():
    """Display list of patients based on user role."""
    user = get_current_user()
    
    if user.get('role') == 'admin':
        # Admin sees all patients
        patients = get_patients()
    else:
        # Therapists see only their assigned patients
        from models import get_therapist_patients
        patients = get_therapist_patients(user.get('id'))
    
    return render_template('patients/index.html', patients=patients)

@patients_bp.route('/view/<patient_id>')
@login_required
def view(patient_id):
    """View detailed patient information."""
    patient = get_patient(patient_id)
    
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('patients.index'))
    
    # Check if therapist has access to this patient
    user = get_current_user()
    if user.get('role') != 'admin':
        from models import get_therapist_patients
        therapist_patients = get_therapist_patients(user.get('id'))
        patient_ids = [p.get('id') for p in therapist_patients]
        
        if patient_id not in patient_ids:
            flash('You do not have access to this patient', 'danger')
            return redirect(url_for('patients.index'))
    
    # Get progress updates
    progress_updates = get_patient_progress(patient_id)
    
    # Get assigned therapists
    therapists = get_patient_therapists(patient_id)
    
    return render_template('patients/view.html', 
                          patient=patient, 
                          progress_updates=progress_updates,
                          therapists=therapists)

@patients_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Create a new patient."""
    # Only admins should be able to create patients
    user = get_current_user()
    if user.get('role') != 'admin':
        flash('Only administrators can create new patients', 'danger')
        return redirect(url_for('patients.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age', 0)
        medical_condition = request.form.get('medical_condition', '')
        treatment_plan = request.form.get('treatment_plan', '')
        contact_info = request.form.get('contact_info', '')
        
        # Form validation
        if not name:
            flash('Patient name is required', 'danger')
            return render_template('patients/new.html')
            
        try:
            # Convert age to integer
            age = int(age) if age else 0
            
            # Create patient
            patient_data = {
                'name': name,
                'age': age,
                'medical_condition': medical_condition,
                'treatment_plan': treatment_plan,
                'contact_info': contact_info
            }
            
            patient_id = create_patient(patient_data)
            
            if patient_id:
                flash('Patient created successfully', 'success')
                return redirect(url_for('patients.view', patient_id=patient_id))
            else:
                flash('Failed to create patient', 'danger')
                
        except ValueError:
            flash('Age must be a number', 'danger')
        except Exception as e:
            flash(f'Error creating patient: {str(e)}', 'danger')
    
    return render_template('patients/new.html')

@patients_bp.route('/edit/<patient_id>', methods=['GET', 'POST'])
@login_required
def edit(patient_id):
    """Edit patient information."""
    # Only admins should be able to edit patients
    user = get_current_user()
    if user.get('role') != 'admin':
        flash('Only administrators can edit patients', 'danger')
        return redirect(url_for('patients.view', patient_id=patient_id))
    
    patient = get_patient(patient_id)
    
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('patients.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age', 0)
        medical_condition = request.form.get('medical_condition', '')
        treatment_plan = request.form.get('treatment_plan', '')
        contact_info = request.form.get('contact_info', '')
        
        # Form validation
        if not name:
            flash('Patient name is required', 'danger')
            return render_template('patients/edit.html', patient=patient)
            
        try:
            # Convert age to integer
            age = int(age) if age else 0
            
            # Update patient
            patient_data = {
                'name': name,
                'age': age,
                'medical_condition': medical_condition,
                'treatment_plan': treatment_plan,
                'contact_info': contact_info
            }
            
            update_patient(patient_id, patient_data)
            
            flash('Patient updated successfully', 'success')
            return redirect(url_for('patients.view', patient_id=patient_id))
                
        except ValueError:
            flash('Age must be a number', 'danger')
        except Exception as e:
            flash(f'Error updating patient: {str(e)}', 'danger')
    
    return render_template('patients/edit.html', patient=patient)

@patients_bp.route('/<patient_id>/progress/new', methods=['GET', 'POST'])
@login_required
def add_progress(patient_id):
    """Add a progress update for a patient."""
    patient = get_patient(patient_id)
    
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('patients.index'))
    
    # Check if therapist has access to this patient
    user = get_current_user()
    if user.get('role') != 'admin':
        from models import get_therapist_patients
        therapist_patients = get_therapist_patients(user.get('id'))
        patient_ids = [p.get('id') for p in therapist_patients]
        
        if patient_id not in patient_ids:
            flash('You do not have access to this patient', 'danger')
            return redirect(url_for('patients.index'))
    
    if request.method == 'POST':
        date = request.form.get('date')
        status = request.form.get('status', '')
        notes = request.form.get('notes', '')
        
        # Form validation
        if not date or not status:
            flash('Date and status are required', 'danger')
            return render_template('patients/add_progress.html', patient=patient)
            
        try:
            # Add progress update
            progress_data = {
                'date': date,
                'status': status,
                'notes': notes
            }
            
            update_id = add_progress_update(patient_id, progress_data)
            
            if update_id:
                flash('Progress update added successfully', 'success')
                return redirect(url_for('patients.view', patient_id=patient_id))
            else:
                flash('Failed to add progress update', 'danger')
                
        except Exception as e:
            flash(f'Error adding progress update: {str(e)}', 'danger')
    
    return render_template('patients/add_progress.html', patient=patient)