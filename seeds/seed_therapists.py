#!/usr/bin/env python3
"""
Seed script for creating therapist users in Firestore.
This script creates 5 therapist users with proper credentials.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import initialize_firebase, create_user, get_db
import firebase_admin
from firebase_admin import firestore

def seed_therapists():
    """Create therapist users in the therapists collection."""
    print("🔧 Seeding Therapist Users...")
    
    # Initialize Firebase if not already done
    initialize_firebase()
    
    # Therapist users data - passwords are only used for Firebase Auth, NOT stored in database
    therapists_data = [
        {
            'email': 'sarah.johnson@dbnsyntax.com',
            'password': 'therapist123',  # This password will NOT be saved to Firestore
            'role': 'therapist',
            'name': 'Dr. Sarah Johnson',
            'phone': '+1-555-0101'
        },
        {
            'email': 'michael.chen@dbnsyntax.com',
            'password': 'therapist123',
            'role': 'therapist',
            'name': 'Dr. Michael Chen',
            'phone': '+1-555-0102'
        },
        {
            'email': 'emily.rodriguez@dbnsyntax.com',
            'password': 'therapist123',
            'role': 'therapist',
            'name': 'Dr. Emily Rodriguez',
            'phone': '+1-555-0103'
        },
        {
            'email': 'david.williams@dbnsyntax.com',
            'password': 'therapist123',
            'role': 'therapist',
            'name': 'Dr. David Williams',
            'phone': '+1-555-0104'
        },
        {
            'email': 'lisa.brown@dbnsyntax.com',
            'password': 'therapist123',
            'role': 'therapist',
            'name': 'Dr. Lisa Brown',
            'phone': '+1-555-0105'
        }
    ]
    
    created_therapists = []
    db = get_db()
    
    for therapist_data in therapists_data:
        try:
            # Check if therapist already exists in Firestore
            existing_therapists = list(db.collection('therapists').where('email', '==', therapist_data['email']).where('type', '==', 'user_account').stream())
            
            if existing_therapists:
                print(f"❌ Therapist {therapist_data['email']} already exists. Skipping...")
                created_therapists.append(existing_therapists[0].id)
                continue
            
            # Check if user exists in Firebase Auth but not in Firestore
            try:
                from firebase_admin import auth
                firebase_user = auth.get_user_by_email(therapist_data['email'])
                print(f"⚠️  Therapist {therapist_data['email']} exists in Firebase Auth, using existing user ID: {firebase_user.uid}")
                created_therapists.append(firebase_user.uid)
                continue
            except:
                # User doesn't exist in Firebase Auth, proceed to create
                pass
            
            # Create therapist user
            user_id = create_user(
                email=therapist_data['email'],
                password=therapist_data['password'],
                role=therapist_data['role'],
                name=therapist_data['name'],
                phone=therapist_data['phone']
            )
            
            if user_id:
                print(f"✅ Therapist created successfully!")
                print(f"   - Email: {therapist_data['email']}")
                print(f"   - Name: {therapist_data['name']}")
                print(f"   - User ID: {user_id}")
                created_therapists.append(user_id)
            else:
                print(f"❌ Failed to create therapist: {therapist_data['email']}")
                
        except Exception as e:
            if "EMAIL_EXISTS" in str(e):
                try:
                    from firebase_admin import auth
                    firebase_user = auth.get_user_by_email(therapist_data['email'])
                    print(f"⚠️  Therapist {therapist_data['email']} exists in Firebase Auth, using existing user ID: {firebase_user.uid}")
                    created_therapists.append(firebase_user.uid)
                except Exception as auth_error:
                    print(f"❌ Error handling existing therapist {therapist_data['email']}: {str(auth_error)}")
            else:
                print(f"❌ Error creating therapist {therapist_data['email']}: {str(e)}")
    
    return created_therapists

if __name__ == "__main__":
    print("🌱 Starting Therapists Seed Process...")
    therapist_ids = seed_therapists()
    
    if therapist_ids:
        print(f"✅ Therapists seeding completed! Created {len(therapist_ids)} therapists.")
    else:
        print("❌ Therapists seeding failed!")
        sys.exit(1)