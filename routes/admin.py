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
    print("DEBUG: patient_assignments route called!")
    print("This should NOT be the route hit when clicking 'Assignments' in nav")
    
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
        return redirect(url_for('admin.assignment_requests'))
    
    try:
        # Assign therapist to patient
        from models import assign_patient as assign_patient_func
        assign_patient_func(therapist_id, patient_id)
        
        flash('Therapist assigned successfully', 'success')
    except Exception as e:
        flash(f'Error assigning therapist: {str(e)}', 'danger')
    
    return redirect(url_for('admin.assignment_requests'))

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
    
    return redirect(url_for('admin.assignment_requests'))

@admin_bp.route('/assignment-requests')
@login_required
@admin_required
def assignment_requests():
    """View and manage patient assignment requests."""
    from models import get_pending_assignment_requests, get_users_by_role
    
    try:
        # Get pending requests
        pending_requests = get_pending_assignment_requests()
        print(f"DEBUG: Found {len(pending_requests)} pending requests")
        
        # Debug: Print the structure of the first request
        if pending_requests:
            print("DEBUG: First request keys:", list(pending_requests[0].keys()))
            print("DEBUG: First request data:", pending_requests[0])
            
            # Check if medical_condition exists
            if 'medical_condition' in pending_requests[0]:
                print("DEBUG: medical_condition exists:", pending_requests[0]['medical_condition'])
            else:
                print("DEBUG: medical_condition field missing!")
                print("DEBUG: Available fields with 'condition' or 'medical':", [key for key in pending_requests[0].keys() if 'condition' in key.lower() or 'medical' in key.lower()])
        else:
            print("DEBUG: No pending requests found")
        
        # Get available therapists
        therapists = get_users_by_role('therapist')
        print(f"DEBUG: Found {len(therapists)} therapists")
        
        return render_template('admin/assignment_requests.html', 
                              pending_requests=pending_requests,
                              therapists=therapists)
                              
    except Exception as e:
        print(f"ERROR in assignment_requests route: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>Error</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

@admin_bp.route('/approve-assignment/<request_id>/<therapist_id>', methods=['POST'])
@login_required
@admin_required
def approve_assignment(request_id, therapist_id):
    """Approve a patient assignment request."""
    try:
        from models import approve_patient_assignment_request, get_user
        
        # Get therapist info for confirmation
        therapist = get_user(therapist_id)
        therapist_name = therapist.get('name') if therapist else 'Unknown'
        
        success = approve_patient_assignment_request(request_id, therapist_id)
        
        if success:
            flash(f'Patient assignment approved successfully. Assigned to {therapist_name}.', 'success')
        else:
            flash('Failed to approve assignment. The request may have already been processed.', 'danger')
            
    except Exception as e:
        flash(f'Error approving assignment: {str(e)}', 'danger')
        print(f"Error in approve_assignment: {e}")
    
    return redirect(url_for('admin.assignment_requests'))

@admin_bp.route('/reject-assignment/<request_id>', methods=['POST'])
@login_required
@admin_required
def reject_assignment(request_id):
    """Reject a patient assignment request."""
    try:
        from models import reject_patient_assignment_request
        
        success = reject_patient_assignment_request(request_id)
        
        if success:
            flash('Assignment request rejected successfully.', 'info')
        else:
            flash('Failed to reject assignment request.', 'danger')
            
    except Exception as e:
        flash(f'Error rejecting assignment: {str(e)}', 'danger')
        print(f"Error in reject_assignment: {e}")
    
    return redirect(url_for('admin.assignment_requests'))

@admin_bp.route('/edit-assignment/<patient_id>/<current_therapist_id>')
@login_required
@admin_required
def edit_assignment_form(patient_id, current_therapist_id):
    """Get the edit assignment form."""
    try:
        from models import get_user, get_users_by_role, get_patient_assigned_therapist
        
        # Get patient info
        patient = get_user(patient_id)
        current_therapist = get_user(current_therapist_id)
        therapists = get_users_by_role('therapist')
        
        if not patient or not current_therapist:
            return '<div class="alert alert-danger">Patient or therapist not found.</div>'
        
        # Return HTML for the edit form
        html = f'''
        <form method="POST" action="{url_for('admin.update_assignment', patient_id=patient_id, current_therapist_id=current_therapist_id)}">
            <div class="mb-3">
                <h6>Patient: {patient.get('name', 'Unknown')}</h6>
                <p class="text-muted">Currently assigned to: {current_therapist.get('name', 'Unknown')}</p>
            </div>
            <div class="mb-3">
                <label for="new_therapist_id" class="form-label">Reassign to:</label>
                <select class="form-select" id="new_therapist_id" name="new_therapist_id" required>
                    <option value="">-- Select new therapist --</option>
        '''
        
        for therapist in therapists:
            if therapist.get('id') != current_therapist_id:  # Don't show current therapist
                html += f'<option value="{therapist.get("id")}">{therapist.get("name")} - {therapist.get("email", "")}</option>'
        
        html += '''
                </select>
            </div>
            <div class="mb-3">
                <label for="reassignment_reason" class="form-label">Reason for reassignment:</label>
                <textarea class="form-control" id="reassignment_reason" name="reassignment_reason" rows="3" 
                          placeholder="Optional: Explain why this reassignment is necessary"></textarea>
            </div>
            <div class="d-flex justify-content-end gap-2">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="submit" class="btn btn-warning">Update Assignment</button>
            </div>
        </form>
        '''
        
        return html
        
    except Exception as e:
        print(f"Error in edit_assignment_form: {e}")
        return '<div class="alert alert-danger">Error loading edit form. Please try again.</div>'

@admin_bp.route('/update-assignment/<patient_id>/<current_therapist_id>', methods=['POST'])
@login_required
@admin_required
def update_assignment(patient_id, current_therapist_id):
    """Update a patient's therapist assignment."""
    try:
        from models import (update_patient_therapist_assignment, get_user, 
                          log_assignment_change)
        
        new_therapist_id = request.form.get('new_therapist_id')
        reassignment_reason = request.form.get('reassignment_reason', '')
        
        if not new_therapist_id:
            flash('Please select a new therapist.', 'danger')
            return redirect(url_for('admin.assignment_requests'))
        
        # Get user info for logging
        patient = get_user(patient_id)
        old_therapist = get_user(current_therapist_id)
        new_therapist = get_user(new_therapist_id)
        
        if not all([patient, old_therapist, new_therapist]):
            flash('One or more users not found.', 'danger')
            return redirect(url_for('admin.assignment_requests'))
        
        # Update the assignment
        success = update_patient_therapist_assignment(patient_id, current_therapist_id, new_therapist_id)
        
        if success:
            # Log the change
            admin_user = get_current_user()
            log_assignment_change(
                patient_id=patient_id,
                old_therapist_id=current_therapist_id,
                new_therapist_id=new_therapist_id,
                admin_id=admin_user.get('id'),
                reason=reassignment_reason
            )
            
            flash(f'Assignment updated successfully. {patient.get("name")} reassigned from {old_therapist.get("name")} to {new_therapist.get("name")}.', 'success')
        else:
            flash('Failed to update assignment. Please try again.', 'danger')
            
    except Exception as e:
        flash(f'Error updating assignment: {str(e)}', 'danger')
        print(f"Error in update_assignment: {e}")
    
    return redirect(url_for('admin.assignment_requests'))

@admin_bp.route('/assigned-patients')
@login_required
@admin_required
def assigned_patients():
    """View all patients with their current therapist assignments."""
    try:
        from models import get_all_assigned_patients
        
        assigned_patients = get_all_assigned_patients()
        print(f"INFO: Loading {len(assigned_patients)} assigned patients")
        
        return render_template('admin/assigned_patients.html', 
                              assigned_patients=assigned_patients)
        
    except Exception as e:
        print(f"ERROR in assigned_patients route: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading assigned patients: {str(e)}', 'danger')
        return redirect(url_for('admin.dashboard'))

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