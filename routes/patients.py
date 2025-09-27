from flask import Blueprint, render_template, redirect, url_for, request, flash
from routes.auth import login_required, therapist_required, get_current_user
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
        return render_template('patients/index.html', patients=patients)
    elif user.get('role') == 'patient':
        # Redirect patients to their dashboard
        return redirect(url_for('patients.dashboard'))
    else:
        # Therapists see only their assigned patients
        from models import get_therapist_patients
        patients = get_therapist_patients(user.get('id'))
        return render_template('patients/index.html', patients=patients)

@patients_bp.route('/dashboard')
@login_required
def dashboard():
    """Patient dashboard - shows their own information and progress."""
    user = get_current_user()
    
    # Only patients can access this dashboard
    if user.get('role') != 'patient':
        flash('Access denied: This is a patient-only area', 'danger')
        return redirect(url_for('home'))
    
    # Get patient's own medical records (if any)
    from models import get_db
    db = get_db()
    
    # Try to find medical records for this patient (by email or name matching)
    patient_records = []
    medical_records = db.collection('patients').where('type', '==', 'medical_record').stream()
    
    user_email = user.get('email', '').lower()
    user_name = user.get('name', '').lower()
    
    for record in medical_records:
        record_data = record.to_dict()
        record_contact = record_data.get('contact_info', '').lower()
        record_name = record_data.get('name', '').lower()
        
        # Check if this record might belong to the logged-in patient
        if (user_email in record_contact or 
            user_name in record_name or 
            record_name in user_name):
            record_data['id'] = record.id
            patient_records.append(record_data)
    
    # Get progress updates for the patient's records
    progress_updates = []
    for record in patient_records:
        from models import get_patient_progress
        updates = get_patient_progress(record['id'])
        for update in updates:
            update['patient_name'] = record.get('name')
            progress_updates.append(update)
    
    # Sort progress updates by date (most recent first)
    progress_updates.sort(key=lambda x: x.get('date', ''), reverse=True)
    progress_updates = progress_updates[:5]  # Show only recent 5
    
    from datetime import datetime
    return render_template('patients/dashboard.html', 
                          user=user,
                          patient_records=patient_records,
                          progress_updates=progress_updates,
                          now=datetime.now())

@patients_bp.route('/mindlink', methods=['GET', 'POST'])
@login_required
def mindlink():
    """MindLink Community Forum - A safe space for patients to share and support each other."""
    user = get_current_user()
    
    # Only patients can access MindLink
    if user.get('role') != 'patient':
        flash('MindLink is exclusively for patients. Please contact your therapist for support.', 'info')
        return redirect(url_for('home'))
    
    from models import get_db
    from datetime import datetime
    import firebase_admin
    from firebase_admin import firestore
    
    db = get_db()
    
    # Handle new post submission
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        is_anonymous = request.form.get('is_anonymous') == 'on'
        
        if not content:
            flash('Please share something with the community', 'warning')
        elif len(content) < 10:
            flash('Please share a bit more to help others connect with your experience', 'warning')
        else:
            try:
                # Create new forum post
                post_data = {
                    'content': content,
                    'author_id': user.get('id') if not is_anonymous else 'anonymous',
                    'author_name': user.get('name') if not is_anonymous else 'Anonymous Friend',
                    'is_anonymous': is_anonymous,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'likes': 0,
                    'support_count': 0,
                    'type': 'mindlink_post'
                }
                
                db.collection('mindlink_posts').add(post_data)
                flash('Thank you for sharing! Your voice matters and helps others feel less alone. 💚', 'success')
                
            except Exception as e:
                flash('Something went wrong sharing your post. Please try again.', 'danger')
                print(f"Error creating MindLink post: {e}")
    
    # Get all forum posts (most recent first)
    try:
        posts_ref = db.collection('mindlink_posts').order_by('created_at', direction=firestore.Query.DESCENDING).limit(20)
        posts = []
        
        for post_doc in posts_ref.stream():
            post_data = post_doc.to_dict()
            post_data['id'] = post_doc.id
            
            # Convert timestamp to readable format
            if 'created_at' in post_data and post_data['created_at']:
                created_at = post_data['created_at']
                if hasattr(created_at, 'timestamp'):
                    post_data['created_at_readable'] = datetime.fromtimestamp(created_at.timestamp()).strftime('%B %d, %Y at %I:%M %p')
                else:
                    post_data['created_at_readable'] = 'Recently'
            else:
                post_data['created_at_readable'] = 'Recently'
            
            posts.append(post_data)
            
    except Exception as e:
        posts = []
        print(f"Error fetching MindLink posts: {e}")
    
    # Get community stats
    try:
        total_posts = len(list(db.collection('mindlink_posts').stream()))
        active_members = len(set([post.get('author_id') for post in posts if post.get('author_id') != 'anonymous']))
    except:
        total_posts = 0
        active_members = 0
    
    return render_template('patients/mindlink.html', 
                          user=user,
                          posts=posts,
                          total_posts=total_posts,
                          active_members=active_members,
                          now=datetime.now())

@patients_bp.route('/mindlink/support/<post_id>', methods=['POST'])
@login_required
def support_post(post_id):
    """Add support to a MindLink post."""
    user = get_current_user()
    
    if user.get('role') != 'patient':
        return redirect(url_for('home'))
    
    try:
        from models import get_db
        from firebase_admin import firestore
        
        db = get_db()
        post_ref = db.collection('mindlink_posts').document(post_id)
        
        # Increment support count
        post_ref.update({
            'support_count': firestore.Increment(1)
        })
        
        flash('💚 Support sent! You\'re helping someone feel less alone today.', 'success')
        
    except Exception as e:
        flash('Unable to send support right now. Please try again.', 'danger')
        print(f"Error supporting post: {e}")
    
    return redirect(url_for('patients.mindlink'))

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