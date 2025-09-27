#!/usr/bin/env python3
"""
Seed script for creating patient users in Firestore.
This script creates 3 patient users with proper credentials.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import initialize_firebase, create_user, get_db
import firebase_admin
from firebase_admin import firestore

def seed_patients():
    """Create patient users in the patients_users collection."""
    print("🔧 Seeding Patient Users...")
    
    # Initialize Firebase if not already done
    initialize_firebase()
    
    # Patient users data - passwords are only used for Firebase Auth, NOT stored in database
    patients_data = [
        {
            'email': 'john.smith@email.com',
            'password': 'patient123',  # This password will NOT be saved to Firestore
            'role': 'patient',
            'name': 'John Smith',
            'phone': '+1-555-0201'
        },
        {
            'email': 'maria.garcia@email.com',
            'password': 'patient123',
            'role': 'patient',
            'name': 'Maria Garcia',
            'phone': '+1-555-0202'
        },
        {
            'email': 'robert.jones@email.com',
            'password': 'patient123',
            'role': 'patient',
            'name': 'Robert Jones',
            'phone': '+1-555-0203'
        }
    ]
    
    created_patients = []
    db = get_db()
    
    for patient_data in patients_data:
        try:
            # Check if patient already exists in Firestore
            existing_patients = list(db.collection('patients').where('email', '==', patient_data['email']).where('type', '==', 'user_account').stream())
            
            if existing_patients:
                print(f"❌ Patient {patient_data['email']} already exists. Skipping...")
                created_patients.append(existing_patients[0].id)
                continue
            
            # Check if user exists in Firebase Auth but not in Firestore
            try:
                from firebase_admin import auth
                firebase_user = auth.get_user_by_email(patient_data['email'])
                print(f"⚠️  Patient {patient_data['email']} exists in Firebase Auth, creating Firestore document...")
                
                # Create the Firestore document for this existing Firebase user
                db.collection('patients').document(firebase_user.uid).set({
                    'type': 'user_account',
                    'email': patient_data['email'],
                    'name': patient_data['name'],
                    'phone': patient_data['phone'],
                    'role': patient_data['role'],
                    'created_at': firestore.SERVER_TIMESTAMP,
                })
                
                print(f"✅ Patient Firestore document created!")
                print(f"   - Email: {patient_data['email']}")
                print(f"   - Name: {patient_data['name']}")
                print(f"   - User ID: {firebase_user.uid}")
                created_patients.append(firebase_user.uid)
                continue
            except:
                # User doesn't exist in Firebase Auth, proceed to create
                pass
            
            # Try to create patient user
            user_id = create_user(
                email=patient_data['email'],
                password=patient_data['password'],
                role=patient_data['role'],
                name=patient_data['name'],
                phone=patient_data['phone']
            )
            
            if user_id:
                print(f"✅ Patient created successfully!")
                print(f"   - Email: {patient_data['email']}")
                print(f"   - Name: {patient_data['name']}")
                print(f"   - User ID: {user_id}")
                created_patients.append(user_id)
            else:
                print(f"❌ Failed to create patient: {patient_data['email']}")
                
        except Exception as e:
            if "EMAIL_EXISTS" in str(e):
                # If user exists in Firebase Auth but not in Firestore, try to get the Firebase user
                try:
                    from firebase_admin import auth
                    firebase_user = auth.get_user_by_email(patient_data['email'])
                    print(f"⚠️  Patient {patient_data['email']} exists in Firebase Auth, using existing user ID: {firebase_user.uid}")
                    created_patients.append(firebase_user.uid)
                except Exception as auth_error:
                    print(f"❌ Error handling existing patient {patient_data['email']}: {str(auth_error)}")
            else:
                print(f"❌ Error creating patient {patient_data['email']}: {str(e)}")
    
    return created_patients

if __name__ == "__main__":
    print("🌱 Starting Patients Seed Process...")
    patient_ids = seed_patients()
    
    if patient_ids:
        print(f"✅ Patients seeding completed! Created {len(patient_ids)} patients.")
    else:
        print("❌ Patients seeding failed!")
        sys.exit(1)