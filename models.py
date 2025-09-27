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