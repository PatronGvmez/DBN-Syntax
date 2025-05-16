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
            # Use environment variables for Firebase configuration
            project_id = os.getenv('FIREBASE_PROJECT_ID')
            private_key = os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n')
            client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
            
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key,
                "client_email": client_email,
            })
            
            firebase_app = firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully")
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            
            # For local development without proper Firebase credentials
            cred = credentials.Certificate("firebase_config.json")
            firebase_app = firebase_admin.initialize_app(cred)
            print("Firebase initialized with local credentials")

def get_db():
    """Returns a Firestore database client."""
    return firestore.client()

# User model functions
def create_user(email, password, role='therapist', name='', phone=''):
    """Creates a new user in Firebase Authentication and Firestore."""
    try:
        # Create user in Firebase Auth
        user = auth.create_user(
            email=email,
            password=password,
            display_name=name,
        )
        
        # Create user in Firestore
        db = get_db()
        db.collection('users').document(user.uid).set({
            'email': email,
            'name': name,
            'phone': phone,
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP,
        })
        
        return user.uid
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def get_user(user_id):
    """Retrieves a user by ID from Firestore."""
    if not user_id:
        return None
    
    db = get_db()
    user_ref = db.collection('users').document(user_id)
    user = user_ref.get()
    
    if user.exists:
        return user.to_dict()
    return None

# Patient model functions
def create_patient(data):
    """Creates a new patient in Firestore."""
    db = get_db()
    patient_ref = db.collection('patients').document()
    
    patient_data = {
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
    """Retrieves a patient by ID from Firestore."""
    db = get_db()
    patient_ref = db.collection('patients').document(patient_id)
    patient = patient_ref.get()
    
    if patient.exists:
        data = patient.to_dict()
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
    """Retrieves all patients from Firestore."""
    db = get_db()
    patients = db.collection('patients').stream()
    
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