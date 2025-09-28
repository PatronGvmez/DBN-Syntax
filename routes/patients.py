from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from routes.auth import login_required, therapist_required, get_current_user
from models import (get_patient, get_patients, create_patient, update_patient, 
                    get_patient_progress, add_progress_update, get_patient_therapists, update_user)

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
    
    # Check profile completion status
    from models import get_patient_profile_completion
    profile_status = get_patient_profile_completion(user.get('id'))
    
    from datetime import datetime
    return render_template('patients/dashboard.html', 
                          user=user,
                          patient_records=patient_records,
                          progress_updates=progress_updates,
                          profile_status=profile_status,
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

@patients_bp.route('/my-therapist', methods=['GET', 'POST'])
@login_required
def my_therapist():
    """Patient therapist assignment and information page."""
    user = get_current_user()
    
    # Only patients can access this page
    if user.get('role') != 'patient':
        flash('This page is for patients only.', 'warning')
        return redirect(url_for('home'))
    
    from models import (get_patient_assignment_request, create_patient_assignment_request, 
                       get_patient_assigned_therapist, get_patient_full_profile, update_patient_profile)
    
    patient_id = user.get('id')
    
    # Get patient's existing profile data for form pre-population
    patient_profile = get_patient_full_profile(patient_id)
    
    # Check if patient already has an assignment request or assigned therapist
    try:
        assignment_request = get_patient_assignment_request(patient_id)
        assigned_therapist = get_patient_assigned_therapist(patient_id)
    except Exception as e:
        # Handle database connection issues gracefully
        assignment_request = None
        assigned_therapist = None
        error_msg = str(e)
        if "requires an index" in error_msg:
            flash('Database configuration issue detected. Please contact support if this persists.', 'warning')
        else:
            flash(f'Unable to load therapist assignment data: {str(e)}', 'warning')
    
    # Handle form submission for new assignment request
    if request.method == 'POST':
        # Only allow form submission if no active request exists
        if assignment_request and assignment_request.get('status') in ['pending', 'approved']:
            flash('You already have an active assignment request.', 'info')
            return redirect(url_for('patients.my_therapist'))
        
        # Get form data
        age = request.form.get('age', '')
        gender = request.form.get('gender', '')
        medical_condition = request.form.get('medical_condition', '')
        severity = request.form.get('severity', '')
        therapy_type_preference = request.form.get('therapy_type_preference', '')
        previous_therapy = request.form.get('previous_therapy', '')
        communication_preference = request.form.get('communication_preference', '')
        availability = request.form.get('availability', '')
        special_requirements = request.form.get('special_requirements', '')
        goals = request.form.get('goals', '')
        emergency_contact = request.form.get('emergency_contact', '')
        
        # Debug: Print form data
        print(f"Form data received: age={age}, gender={gender}, medical_condition={medical_condition}")
        
        # Basic validation
        required_fields = {'age': age, 'gender': gender, 'medical_condition': medical_condition, 
                          'severity': severity, 'therapy_type_preference': therapy_type_preference}
        missing_fields = [field for field, value in required_fields.items() if not value or (isinstance(value, str) and not value.strip())]
        
        if missing_fields:
            flash(f'Please fill in all required fields: {", ".join(missing_fields)}', 'danger')
            return render_template('patients/my_therapist.html', 
                                 user=user,
                                 patient_profile=patient_profile,
                                 assignment_request=assignment_request,
                                 assigned_therapist=assigned_therapist)
        
        try:
            # Validate age
            if not age or not str(age).isdigit():
                raise ValueError(f"Invalid age value: '{age}'. Age must be a number.")
            
            age_int = int(age)
            if age_int < 1 or age_int > 120:
                raise ValueError(f"Age must be between 1 and 120, got: {age_int}")
                
            # Update patient profile with form data (save to profile for future use)
            profile_updates = {
                'personal_info': {
                    'gender': gender,
                    'emergency_contact_name': emergency_contact.split(' - ')[0] if ' - ' in emergency_contact and emergency_contact else emergency_contact,
                    'emergency_contact_phone': emergency_contact.split(' - ')[1] if ' - ' in emergency_contact and len(emergency_contact.split(' - ')) > 1 else '',
                },
                'medical_info': {
                    'medical_history': medical_condition,
                },
                'mental_health': {
                    'therapy_goals': goals,
                    'previous_therapy': previous_therapy,
                    'current_symptoms': medical_condition,
                },
                'lifestyle': {
                    'special_requirements': special_requirements,
                }
            }
            
            # Calculate age from date of birth if available, otherwise store age directly
            if age_int:
                from datetime import datetime
                current_year = datetime.now().year
                birth_year = current_year - age_int
                profile_updates['personal_info']['age'] = age_int
                # Only update DOB if not already set
                if not (patient_profile and patient_profile.get('personal_info', {}).get('date_of_birth')):
                    profile_updates['personal_info']['date_of_birth'] = f"{birth_year}-01-01"
            
            # Merge with existing profile data to avoid overwriting
            if patient_profile:
                print(f"Merging with existing profile data...")
                for category, fields in profile_updates.items():
                    existing_category = patient_profile.get(category, {})
                    for field, value in fields.items():
                        # Handle both string and non-string values
                        try:
                            if value is not None:
                                if isinstance(value, str) and value.strip():
                                    existing_category[field] = value
                                    print(f"Updated {category}.{field} with string value: {value}")
                                elif not isinstance(value, str) and value:
                                    existing_category[field] = value
                                    print(f"Updated {category}.{field} with non-string value: {value} (type: {type(value)})")
                        except Exception as field_error:
                            print(f"Error processing field {category}.{field} with value {value} (type: {type(value)}): {field_error}")
                            raise field_error
                    profile_updates[category] = existing_category
            
            # Save profile updates
            user_id = session.get('user_id')
            print(f"Saving profile updates for user {user_id}...")
            update_result = update_patient_profile(user_id, profile_updates)
            print(f"Profile update result: {update_result}")
            
            # Create patient info object for assignment request
            patient_info = {
                'age': age_int,
                'gender': gender,
                'medical_condition': medical_condition,
                'severity': severity,
                'therapy_type_preference': therapy_type_preference,
                'previous_therapy': previous_therapy,
                'communication_preference': communication_preference,
                'availability': availability,
                'special_requirements': special_requirements,
                'goals': goals,
                'emergency_contact': emergency_contact,
                'submitted_by': user.get('name'),
                'submitted_email': user.get('email')
            }
            
            # Create assignment request
            request_id = create_patient_assignment_request(patient_id, patient_info)
            
            if request_id:
                flash('Your therapist assignment request has been submitted successfully! Your profile has also been updated with this information. Please wait for an administrator to review and assign you to a suitable therapist.', 'success')
                return redirect(url_for('patients.my_therapist'))
            else:
                flash('Failed to submit assignment request. You may already have an active request.', 'danger')
                
        except ValueError as e:
            error_msg = f'Please enter a valid age: {str(e)}'
            flash(error_msg, 'danger')
            print(f"ValueError in assignment request: {e}")
        except AttributeError as e:
            error_msg = f'Data format error: {str(e)}. Please check your input values.'
            flash(error_msg, 'danger')
            print(f"AttributeError in assignment request: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            # Show specific error message to help with debugging
            error_msg = f'Error submitting request: {str(e)}'
            flash(error_msg, 'danger')
            print(f"Error creating assignment request: {e}")
            import traceback
            traceback.print_exc()
    
    # Refresh assignment request after potential creation
    try:
        assignment_request = get_patient_assignment_request(patient_id)
    except Exception as e:
        assignment_request = None
        print(f"Error refreshing assignment request: {e}")
    
    return render_template('patients/my_therapist.html', 
                          user=user,
                          patient_profile=patient_profile,
                          assignment_request=assignment_request,
                          assigned_therapist=assigned_therapist)

@patients_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """Handle patient profile completion."""
    user = get_current_user()
    
    # Only patients can access this
    if user.get('role') != 'patient':
        flash('This page is for patients only.', 'warning')
        return redirect(url_for('home'))
    
    from models import update_patient_profile, get_patient_full_profile, get_patient_profile_completion
    
    if request.method == 'POST':
        try:
            # Get save type (partial or complete)
            save_type = request.form.get('save_type', 'complete')
            # Get user ID from session (more reliable than user object)
            user_id = session.get('user_id')
            
            # Organize form data by categories
            profile_data = {
                'personal_info': {
                    'date_of_birth': request.form.get('date_of_birth', ''),
                    'gender': request.form.get('gender', ''),
                    'phone': request.form.get('phone', ''),
                    'address': request.form.get('address', ''),
                    'emergency_contact_name': request.form.get('emergency_contact_name', ''),
                    'emergency_contact_phone': request.form.get('emergency_contact_phone', ''),
                    'emergency_contact_relationship': request.form.get('emergency_contact_relationship', '')
                },
                'medical_info': {
                    'primary_physician': request.form.get('primary_physician', ''),
                    'insurance_provider': request.form.get('insurance_provider', ''),
                    'insurance_id': request.form.get('insurance_id', ''),
                    'allergies': request.form.get('allergies', ''),
                    'current_medications': request.form.get('current_medications', ''),
                    'medical_history': request.form.get('medical_history', '')
                },
                'mental_health': {
                    'mental_health_history': request.form.get('mental_health_history', ''),
                    'current_symptoms': request.form.get('current_symptoms', ''),
                    'therapy_goals': request.form.get('therapy_goals', ''),
                    'previous_therapy': request.form.get('previous_therapy', ''),
                    'support_system': request.form.get('support_system', '')
                },
                'lifestyle': {
                    'occupation': request.form.get('occupation', ''),
                    'education_level': request.form.get('education_level', ''),
                    'marital_status': request.form.get('marital_status', ''),
                    'living_situation': request.form.get('living_situation', ''),
                    'substance_use': request.form.get('substance_use', '')
                }
            }
            
            # Update profile
            success = update_patient_profile(user_id, profile_data)
            
            if success:
                # Get updated completion status
                profile_status = get_patient_profile_completion(user_id)
                completion_percentage = profile_status.completion_percentage if profile_status else 0
                
                if save_type == 'partial':
                    # Return JSON response for partial saves
                    return jsonify({
                        'success': True,
                        'message': 'Progress saved successfully! You can continue filling out your profile later.',
                        'completion_percentage': completion_percentage
                    })
                else:
                    # Complete save - validate required fields
                    required_fields = ['date_of_birth', 'gender', 'phone']
                    missing_fields = []
                    
                    for field in required_fields:
                        if not request.form.get(field, '').strip():
                            missing_fields.append(field.replace('_', ' ').title())
                    
                    if missing_fields:
                        return jsonify({
                            'success': False,
                            'message': f'Please fill in required fields: {", ".join(missing_fields)}'
                        })
                    
                    # Complete profile submission
                    flash('Profile completed successfully! Thank you for providing your information.', 'success')
                    return redirect(url_for('patients.dashboard'))
            else:
                if save_type == 'partial':
                    return jsonify({
                        'success': False,
                        'message': 'Failed to save progress. Please try again.'
                    })
                else:
                    flash('Failed to update profile. Please try again.', 'danger')
                
        except Exception as e:
            print(f"Error updating profile: {e}")
            import traceback
            traceback.print_exc()
            
            if request.form.get('save_type') == 'partial':
                return jsonify({
                    'success': False,
                    'message': f'An error occurred while saving progress: {str(e)}'
                })
            else:
                flash(f'An error occurred while updating your profile: {str(e)}', 'danger')
    
    # Get user ID from session 
    user_id = session.get('user_id')
    
    # Get current profile data for form
    current_profile = get_patient_full_profile(user_id)
    
    # Get profile completion status
    profile_status = get_patient_profile_completion(user_id)
    
    return render_template('patients/complete_profile.html', 
                          user=user,
                          current_profile=current_profile,
                          profile_status=profile_status)

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

@patients_bp.route('/profile')
@login_required
def profile():
    """Display patient profile."""
    user = get_current_user()
    
    # Only patients can access their own profile
    if user.get('role') != 'patient':
        flash('Access denied: This is a patient-only area', 'danger')
        return redirect(url_for('home'))
    
    # Get patient profile data
    from models import get_patient_full_profile, get_patient_profile_completion
    patient_profile = get_patient_full_profile(user.get('id'))
    profile_status = get_patient_profile_completion(user.get('id'))
    
    return render_template('patients/profile.html', 
                          user=user, 
                          patient_profile=patient_profile,
                          profile_status=profile_status)

@patients_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit patient profile."""
    user = get_current_user()
    
    # Only patients can access their own profile
    if user.get('role') != 'patient':
        flash('Access denied: This is a patient-only area', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone', '')
        
        if not name:
            flash('Name is required', 'danger')
            return render_template('patients/edit_profile.html', user=user)
            
        try:
            # Update user in Firestore
            user_id = update_user(session['user_id'], {
                'name': name,
                'phone': phone
            })
            
            if user_id:
                flash('Profile updated successfully', 'success')
                return redirect(url_for('patients.profile'))
            else:
                flash('Failed to update profile: User not found', 'danger')
            
        except Exception as e:
            flash(f'Failed to update profile: {str(e)}', 'danger')
    
    return render_template('patients/edit_profile.html', user=user)