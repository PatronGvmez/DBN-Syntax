#!/usr/bin/env python3
"""
Seed script for creating an admin user in Firestore.
This script creates 1 admin user with proper credentials.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import initialize_firebase, create_user, get_db
import firebase_admin
from firebase_admin import firestore

def seed_admin():
    """Create admin user in the admins collection."""
    print("🔧 Seeding Admin User...")
    
    # Initialize Firebase if not already done
    initialize_firebase()
    
    # Admin user data - password is only used for Firebase Auth, NOT stored in database
    admin_data = {
        'email': 'admin@dbnsyntax.com',
        'password': 'admin123',  # This password will NOT be saved to Firestore
        'role': 'admin',
        'name': 'System Administrator',
        'phone': '+1-555-0001'
    }
    
    try:
        # Check if admin already exists in Firestore
        db = get_db()
        existing_admins = list(db.collection('admins').where('email', '==', admin_data['email']).where('type', '==', 'user_account').stream())
        
        if existing_admins:
            print(f"❌ Admin user {admin_data['email']} already exists. Skipping...")
            return existing_admins[0].id
        
        # Check if user exists in Firebase Auth but not in Firestore
        try:
            from firebase_admin import auth
            firebase_user = auth.get_user_by_email(admin_data['email'])
            print(f"⚠️  Admin {admin_data['email']} exists in Firebase Auth, using existing user ID: {firebase_user.uid}")
            return firebase_user.uid
        except:
            # User doesn't exist in Firebase Auth, proceed to create
            pass
        
        # Create admin user
        user_id = create_user(
            email=admin_data['email'],
            password=admin_data['password'],
            role=admin_data['role'],
            name=admin_data['name'],
            phone=admin_data['phone']
        )
        
        if user_id:
            print(f"✅ Admin user created successfully!")
            print(f"   - Email: {admin_data['email']}")
            print(f"   - Name: {admin_data['name']}")
            print(f"   - User ID: {user_id}")
            return user_id
        else:
            print("❌ Failed to create admin user")
            return None
            
    except Exception as e:
        if "EMAIL_EXISTS" in str(e):
            try:
                from firebase_admin import auth
                firebase_user = auth.get_user_by_email(admin_data['email'])
                print(f"⚠️  Admin {admin_data['email']} exists in Firebase Auth, using existing user ID: {firebase_user.uid}")
                return firebase_user.uid
            except Exception as auth_error:
                print(f"❌ Error handling existing admin {admin_data['email']}: {str(auth_error)}")
                return None
        else:
            print(f"❌ Error creating admin user: {str(e)}")
            return None

if __name__ == "__main__":
    print("🌱 Starting Admin Seed Process...")
    admin_id = seed_admin()
    
    if admin_id:
        print("✅ Admin seeding completed successfully!")
    else:
        print("❌ Admin seeding failed!")
        sys.exit(1)