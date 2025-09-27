import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from datetime import datetime
from flask import session

# Firebase initialization
firebase_app = None

def initialize_firebase():
    global firebase_app
    if not firebase_app:
        try:
            cred = credentials.Certificate(r"jsonFile/dutsyntax-e73be-firebase-adminsdk-fbsvc-80eb57142b.json")
            firebase_app = firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully with service account key.")
        except Exception as e:
            print(f"Error initializing Firebase: {e}")

def get_db():
    """Returns a Firestore database client."""
    return firestore.client()

# User model functions
def create_user(email, password, role='therapist', name='', phone=''):
    """Creates a new user in Firebase Authentication and appropriate Firestore collection."""
    try:
        # Create user in Firebase Auth (password is stored securely by Firebase)
        user = auth.create_user(
            email=email,
            password=password,
            display_name=name,
        )
        
        # Determine collection based on role
        collection_name = _get_collection_by_role(role)
        
        # Create user profile in appropriate Firestore collection
        # NOTE: Password is NOT stored here - only Firebase Auth handles passwords
        db = get_db()
        user_data = {
            'type': 'user_account',  # Distinguish from medical records
            'email': email,
            'name': name,
            'phone': phone,
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP,
        }
        db.collection(collection_name).document(user.uid).set(user_data)
        
        return user.uid
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def _get_collection_by_role(role):
    """Returns the appropriate collection name based on user role."""
    if role == 'admin':
        return 'admins'
    elif role == 'therapist':
        return 'therapists'
    elif role == 'patient':
        return 'patients'  # Single collection for patient users and medical records
    else:
        return 'therapists'  # Default fallback

def get_user(user_id):
    """Retrieves a user by ID from appropriate Firestore collection."""
    if not user_id:
        return None
    
    db = get_db()
    
    # Try to find user in all possible collections
    collections = ['admins', 'therapists', 'patients']
    
    for collection_name in collections:
        user_ref = db.collection(collection_name).document(user_id)
        user = user_ref.get()
        
        if user.exists:
            data = user.to_dict()
            # Return if it's a user account OR if no type field (backward compatibility)
            if data.get('type') == 'user_account' or 'type' not in data:
                # Skip medical records (they have medical_condition field)
                if 'medical_condition' not in data:
                    # Add the document ID to the data
                    data['id'] = user_id
                    return data
    
    return None

def get_user_by_email(email):
    """Retrieves a user by email from appropriate Firestore collection."""
    if not email:
        return None
    
    db = get_db()
    collections = ['admins', 'therapists', 'patients']
    
    for collection_name in collections:
        users = db.collection(collection_name).where('email', '==', email).stream()
        for user in users:
            data = user.to_dict()
            # Return if it's a user account OR if no type field (backward compatibility)
            if data.get('type') == 'user_account' or 'type' not in data:
                # Skip medical records (they have medical_condition field)
                if 'medical_condition' not in data:
                    data['id'] = user.id
                    return data
    
    return None

def update_user(user_id, data):
    """Updates a user in the appropriate Firestore collection."""
    if not user_id:
        return None
    
    db = get_db()
    collections = ['admins', 'therapists', 'patients']
    
    for collection_name in collections:
        user_ref = db.collection(collection_name).document(user_id)
        user = user_ref.get()
        
        if user.exists:
            user_data = user.to_dict()
            # Only update if it's a user account, not a medical record
            if user_data.get('type') == 'user_account':
                data['updated_at'] = firestore.SERVER_TIMESTAMP
                user_ref.update(data)
                return user_id
    
    return None

def get_all_therapists():
    """Retrieves all therapist user accounts from Firestore."""
    db = get_db()
    therapists = db.collection('therapists').where('type', '==', 'user_account').stream()
    
    result = []
    for therapist in therapists:
        data = therapist.to_dict()
        data['id'] = therapist.id
        result.append(data)
    
    return result

def get_all_admins():
    """Retrieves all admin user accounts from Firestore."""
    db = get_db()
    admins = db.collection('admins').where('type', '==', 'user_account').stream()
    
    result = []
    for admin in admins:
        data = admin.to_dict()
        data['id'] = admin.id
        result.append(data)
    
    return result

# Patient model functions
def create_patient(data):
    """Creates a new patient medical record in Firestore."""
    db = get_db()
    patient_ref = db.collection('patients').document()
    
    patient_data = {
        'type': 'medical_record',  # Distinguish from user accounts
        'name': data.get('name', ''),
        'age': data.get('age', 0),
        'medical_condition': data.get('medical_condition', ''),
        'treatment_plan': data.get('treatment_plan', ''),
        'contact_info': data.get('contact_info', ''),
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    
    patient_ref.set(patient_data)
    return patient_ref.id

def get_patient(patient_id):
    """Retrieves a patient medical record by ID from Firestore."""
    db = get_db()
    patient_ref = db.collection('patients').document(patient_id)
    patient = patient_ref.get()
    
    if patient.exists:
        data = patient.to_dict()
        # Only return if it's a medical record, not a user account
        if data.get('type') == 'medical_record':
            data['id'] = patient_id
            return data
    return None

def update_patient(patient_id, data):
    """Updates a patient in Firestore."""
    db = get_db()
    patient_ref = db.collection('patients').document(patient_id)
    
    data['updated_at'] = firestore.SERVER_TIMESTAMP
    patient_ref.update(data)
    return patient_id

def get_patients():
    """Retrieves all patient medical records from Firestore."""
    db = get_db()
    patients = db.collection('patients').where('type', '==', 'medical_record').stream()
    
    result = []
    for patient in patients:
        data = patient.to_dict()
        data['id'] = patient.id
        result.append(data)
    
    return result

# Progress update functions
def add_progress_update(patient_id, data):
    """Adds a progress update for a patient."""
    if not patient_id:
        return None
        
    db = get_db()
    update_ref = db.collection('progress_updates').document()
    
    therapist_id = session.get('user_id')
    
    update_data = {
        'patient_id': patient_id,
        'therapist_id': therapist_id,
        'date': data.get('date', datetime.now().strftime('%Y-%m-%d')),
        'status': data.get('status', ''),
        'notes': data.get('notes', ''),
        'created_at': firestore.SERVER_TIMESTAMP
    }
    
    update_ref.set(update_data)
    return update_ref.id

def get_patient_progress(patient_id):
    """Retrieves progress updates for a specific patient."""
    db = get_db()
    updates = db.collection('progress_updates').where('patient_id', '==', patient_id).order_by('date', direction=firestore.Query.DESCENDING).stream()
    
    result = []
    for update in updates:
        data = update.to_dict()
        data['id'] = update.id
        
        # Get therapist name
        if 'therapist_id' in data:
            therapist = get_user(data['therapist_id'])
            if therapist:
                data['therapist_name'] = therapist.get('name', 'Unknown Therapist')
        
        result.append(data)
    
    return result

# Assignment functions
def assign_patient(therapist_id, patient_id):
    """Assigns a patient to a therapist."""
    db = get_db()
    assign_ref = db.collection('assignments').document()
    
    assignment_data = {
        'therapist_id': therapist_id,
        'patient_id': patient_id,
        'assigned_at': firestore.SERVER_TIMESTAMP
    }
    
    assign_ref.set(assignment_data)
    return assign_ref.id

def get_therapist_patients(therapist_id):
    """Retrieves patients assigned to a specific therapist."""
    db = get_db()
    assignments = db.collection('assignments').where('therapist_id', '==', therapist_id).stream()
    
    patient_ids = [assignment.to_dict()['patient_id'] for assignment in assignments]
    patients = []
    
    for patient_id in patient_ids:
        patient = get_patient(patient_id)
        if patient:
            patients.append(patient)
    
    return patients

def get_patient_therapists(patient_id):
    """Retrieves therapists assigned to a specific patient."""
    db = get_db()
    assignments = db.collection('assignments').where('patient_id', '==', patient_id).stream()
    
    therapist_ids = [assignment.to_dict()['therapist_id'] for assignment in assignments]
    therapists = []
    
    for therapist_id in therapist_ids:
        therapist = get_user(therapist_id)
        if therapist:
            therapist['id'] = therapist_id
            therapists.append(therapist)
    
    return therapists

def unassign_patient(therapist_id, patient_id):
    """Removes a patient-therapist assignment."""
    db = get_db()
    assignments = db.collection('assignments').where('therapist_id', '==', therapist_id).where('patient_id', '==', patient_id).stream()
    
    for assignment in assignments:
        assignment.reference.delete()
    
    return True

# MindLink Community Functions
def create_mindlink_post(author_id, author_name, content, is_anonymous=False):
    """Create a new MindLink community post."""
    try:
        db = get_db()
        post_data = {
            'content': content,
            'author_id': author_id if not is_anonymous else 'anonymous',
            'author_name': author_name if not is_anonymous else 'Anonymous Friend',
            'is_anonymous': is_anonymous,
            'created_at': firestore.SERVER_TIMESTAMP,
            'likes': 0,
            'support_count': 0,
            'type': 'mindlink_post',
            'status': 'active'  # For moderation: active, flagged, hidden
        }
        
        doc_ref = db.collection('mindlink_posts').add(post_data)
        return doc_ref[1].id  # Return the document ID
        
    except Exception as e:
        print(f"Error creating MindLink post: {e}")
        return None

def get_mindlink_posts(limit=20):
    """Get recent MindLink community posts."""
    try:
        db = get_db()
        posts_ref = (db.collection('mindlink_posts')
                    .where('status', '==', 'active')
                    .order_by('created_at', direction=firestore.Query.DESCENDING)
                    .limit(limit))
        
        posts = []
        for post_doc in posts_ref.stream():
            post_data = post_doc.to_dict()
            post_data['id'] = post_doc.id
            posts.append(post_data)
            
        return posts
        
    except Exception as e:
        print(f"Error getting MindLink posts: {e}")
        return []

def support_mindlink_post(post_id):
    """Add support to a MindLink post."""
    try:
        db = get_db()
        post_ref = db.collection('mindlink_posts').document(post_id)
        
        # Increment support count
        post_ref.update({
            'support_count': firestore.Increment(1)
        })
        
        return True
        
    except Exception as e:
        print(f"Error supporting MindLink post: {e}")
        return False

def get_mindlink_stats():
    """Get MindLink community statistics."""
    try:
        db = get_db()
        
        # Get total posts
        posts = list(db.collection('mindlink_posts').where('status', '==', 'active').stream())
        total_posts = len(posts)
        
        # Get unique active members (excluding anonymous)
        unique_authors = set()
        for post_doc in posts:
            post_data = post_doc.to_dict()
            author_id = post_data.get('author_id')
            if author_id and author_id != 'anonymous':
                unique_authors.add(author_id)
        
        active_members = len(unique_authors)
        
        return {
            'total_posts': total_posts,
            'active_members': active_members
        }
        
    except Exception as e:
        print(f"Error getting MindLink stats: {e}")
        return {'total_posts': 0, 'active_members': 0}

def migrate_existing_patients():
    """Add profile structure to existing patient accounts."""
    try:
        db = get_db()
        
        # Get all patient user accounts
        patients_collection = db.collection('patients')
        patient_docs = patients_collection.where('type', '==', 'user_account').stream()
        
        updated_count = 0
        
        for patient_doc in patient_docs:
            patient_data = patient_doc.to_dict()
            
            # Check if profile already exists
            if 'profile' not in patient_data:
                # Add empty profile structure
                patient_data['profile'] = {
                    'personal_info': {},
                    'medical_info': {},
                    'mental_health': {},
                    'lifestyle': {},
                    'created_at': firestore.SERVER_TIMESTAMP
                }
                
                # Update the document
                patient_doc.reference.set(patient_data)
                updated_count += 1
                print(f"Added profile structure to patient: {patient_data.get('name', patient_doc.id)}")
        
        print(f"Migration completed. Updated {updated_count} patient records.")
        return updated_count
        
    except Exception as e:
        print(f"Error migrating existing patients: {e}")
        return 0

# Patient Profile Management Functions
def get_patient_profile_completion(user_id):
    """Check patient profile completion status."""
    try:
        db = get_db()
        
        # Get patient user account
        patient = get_user(user_id)
        if not patient or patient.get('role') != 'patient':
            return {'is_complete': True, 'missing_fields': []}
        
        # Define required profile fields
        required_fields = {
            'personal_info': {
                'date_of_birth': 'Date of Birth',
                'gender': 'Gender', 
                'phone': 'Phone Number',
                'address': 'Address',
                'emergency_contact_name': 'Emergency Contact Name',
                'emergency_contact_phone': 'Emergency Contact Phone',
                'emergency_contact_relationship': 'Emergency Contact Relationship'
            },
            'medical_info': {
                'primary_physician': 'Primary Physician',
                'insurance_provider': 'Insurance Provider',
                'insurance_id': 'Insurance ID',
                'allergies': 'Allergies',
                'current_medications': 'Current Medications',
                'medical_history': 'Medical History'
            },
            'mental_health': {
                'mental_health_history': 'Mental Health History',
                'current_symptoms': 'Current Symptoms',
                'therapy_goals': 'Therapy Goals',
                'previous_therapy': 'Previous Therapy Experience',
                'support_system': 'Support System'
            },
            'lifestyle': {
                'occupation': 'Occupation',
                'education_level': 'Education Level',
                'marital_status': 'Marital Status',
                'living_situation': 'Living Situation',
                'substance_use': 'Substance Use History'
            }
        }
        
        missing_fields = []
        profile_data = patient.get('profile', {})
        
        # Check each category and field
        for category, fields in required_fields.items():
            category_data = profile_data.get(category, {})
            for field_key, field_name in fields.items():
                if not category_data.get(field_key):
                    missing_fields.append({
                        'category': category,
                        'field': field_key,
                        'name': field_name
                    })
        
        is_complete = len(missing_fields) == 0
        completion_percentage = max(0, 100 - int((len(missing_fields) / len([f for cat in required_fields.values() for f in cat])) * 100))
        
        return {
            'is_complete': is_complete,
            'missing_fields': missing_fields,
            'completion_percentage': completion_percentage,
            'total_fields': len([f for cat in required_fields.values() for f in cat]),
            'completed_fields': len([f for cat in required_fields.values() for f in cat]) - len(missing_fields)
        }
        
    except Exception as e:
        print(f"Error checking patient profile completion: {e}")
        return {'is_complete': True, 'missing_fields': []}

def update_patient_profile(user_id, profile_data):
    """Update patient profile with comprehensive information."""
    try:
        db = get_db()
        
        # Find the user in the correct collection (same logic as get_user)
        collections = ['admins', 'therapists', 'patients']
        user_ref = None
        current_data = None
        
        for collection_name in collections:
            temp_user_ref = db.collection(collection_name).document(user_id)
            user_doc = temp_user_ref.get()
            
            if user_doc.exists:
                data = user_doc.to_dict()
                # Check if it's a user account (not a medical record)
                if data.get('type') == 'user_account' or 'type' not in data:
                    if 'medical_condition' not in data:  # Skip medical records
                        user_ref = temp_user_ref
                        current_data = data
                        break
        
        if not user_ref or not current_data:
            return False
        
        # Ensure user is a patient
        if current_data.get('role') != 'patient':
            return False
        
        # Initialize profile if it doesn't exist
        if 'profile' not in current_data:
            current_data['profile'] = {}
        
        # Update profile sections
        for category, fields in profile_data.items():
            if category not in current_data['profile']:
                current_data['profile'][category] = {}
            
            # Update fields in this category (allow empty values for partial saves)
            for field_key, field_value in fields.items():
                current_data['profile'][category][field_key] = field_value
        
        # Add metadata
        from firebase_admin import firestore
        current_data['profile']['last_updated'] = firestore.SERVER_TIMESTAMP
        current_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # Save updated data
        user_ref.set(current_data)
        
        return True
        
    except Exception as e:
        print(f"Error updating patient profile: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_patient_full_profile(user_id):
    """Get complete patient profile information."""
    try:
        patient = get_user(user_id)
        if not patient or patient.get('role') != 'patient':
            return None
        
        # Get profile data with default structure
        profile = patient.get('profile', {})
        
        return {
            'user': patient,
            'personal_info': profile.get('personal_info', {}),
            'medical_info': profile.get('medical_info', {}),
            'mental_health': profile.get('mental_health', {}),
            'lifestyle': profile.get('lifestyle', {}),
            'last_updated': profile.get('last_updated')
        }
        
    except Exception as e:
        print(f"Error getting patient full profile: {e}")
        return None

def get_users_by_role(role):
    """Get all users by their role."""
    try:
        db = get_db()
        
        # Map role to collection
        collection_name = {
            'admin': 'admins',
            'therapist': 'therapists', 
            'patient': 'patients'
        }.get(role)
        
        if not collection_name:
            return []
        
        users = []
        user_docs = db.collection(collection_name).where('type', '==', 'user_account').stream()
        
        for user_doc in user_docs:
            user_data = user_doc.to_dict()
            user_data['id'] = user_doc.id
            users.append(user_data)
            
        return users
        
    except Exception as e:
        print(f"Error getting users by role: {e}")
        return []

# Patient Assignment Functions
def create_patient_assignment_request(patient_id, patient_info):
    """Create a new patient assignment request."""
    try:
        db = get_db()
        
        # Check if patient already has an active request
        existing_requests = list(db.collection('patient_assignment_requests')
                               .where('patient_id', '==', patient_id)
                               .where('status', 'in', ['pending', 'approved'])
                               .stream())
        
        if existing_requests:
            return None  # Patient already has active request
        
        request_data = {
            'patient_id': patient_id,
            'patient_info': patient_info,
            'status': 'pending',  # pending, approved, rejected
            'created_at': firestore.SERVER_TIMESTAMP,
            'assigned_therapist_id': None,
            'assigned_at': None,
            'type': 'assignment_request'
        }
        
        doc_ref = db.collection('patient_assignment_requests').add(request_data)
        return doc_ref[1].id
        
    except Exception as e:
        print(f"Error creating patient assignment request: {e}")
        return None

def get_patient_assignment_request(patient_id):
    """Get patient's assignment request status."""
    try:
        db = get_db()
        
        # Get the most recent request for this patient
        requests = (db.collection('patient_assignment_requests')
                   .where('patient_id', '==', patient_id)
                   .order_by('created_at', direction=firestore.Query.DESCENDING)
                   .limit(1)
                   .stream())
        
        for request_doc in requests:
            request_data = request_doc.to_dict()
            request_data['id'] = request_doc.id
            return request_data
            
        return None
        
    except Exception as e:
        print(f"Error getting patient assignment request: {e}")
        return None

def get_patient_assigned_therapist(patient_id):
    """Get patient's assigned therapist information."""
    try:
        # First check if patient has an approved assignment request
        assignment_request = get_patient_assignment_request(patient_id)
        
        if (assignment_request and 
            assignment_request.get('status') == 'approved' and 
            assignment_request.get('assigned_therapist_id')):
            
            therapist_id = assignment_request.get('assigned_therapist_id')
            therapist = get_user(therapist_id)
            
            if therapist:
                return {
                    'therapist': therapist,
                    'assigned_at': assignment_request.get('assigned_at'),
                    'assignment_id': assignment_request.get('id')
                }
        
        # Fallback: Check old assignments collection for backward compatibility
        from models import get_patient_therapists
        therapists = get_patient_therapists(patient_id)
        if therapists:
            return {
                'therapist': therapists[0],  # Return first assigned therapist
                'assigned_at': None,
                'assignment_id': None
            }
            
        return None
        
    except Exception as e:
        print(f"Error getting patient assigned therapist: {e}")
        return None

def approve_patient_assignment_request(request_id, therapist_id):
    """Approve a patient assignment request and assign therapist."""
    try:
        db = get_db()
        
        # Update the assignment request
        request_ref = db.collection('patient_assignment_requests').document(request_id)
        request_ref.update({
            'status': 'approved',
            'assigned_therapist_id': therapist_id,
            'assigned_at': firestore.SERVER_TIMESTAMP
        })
        
        # Also create an entry in the assignments collection for backward compatibility
        request_data = request_ref.get().to_dict()
        patient_id = request_data.get('patient_id')
        
        if patient_id:
            assignment_data = {
                'patient_id': patient_id,
                'therapist_id': therapist_id,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            db.collection('assignments').add(assignment_data)
        
        return True
        
    except Exception as e:
        print(f"Error approving patient assignment request: {e}")
        return False

def get_pending_assignment_requests():
    """Get all pending patient assignment requests for admin review."""
    try:
        db = get_db()
        
        requests = []
        pending_requests = (db.collection('patient_assignment_requests')
                          .where('status', '==', 'pending')
                          .order_by('created_at', direction=firestore.Query.DESCENDING)
                          .stream())
        
        for request_doc in pending_requests:
            request_data = request_doc.to_dict()
            request_data['id'] = request_doc.id
            
            # Get patient info
            patient_id = request_data.get('patient_id')
            if patient_id:
                patient = get_user(patient_id)
                request_data['patient'] = patient
            
            requests.append(request_data)
            
        return requests
        
    except Exception as e:
        print(f"Error getting pending assignment requests: {e}")
        return []