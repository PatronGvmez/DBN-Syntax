#!/usr/bin/env python3
"""
Main seed script for populating the Firestore database.
This script runs all individual seed files to create sample data.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import initialize_firebase, create_patient, get_db
from seeds.seed_admin import seed_admin
from seeds.seed_therapists import seed_therapists  
from seeds.seed_patients import seed_patients
import firebase_admin
from firebase_admin import firestore

def create_sample_patients_data(therapist_ids):
    """Create sample patient medical records (not user accounts)."""
    print("🔧 Creating Sample Patient Medical Records...")
    
    patients_medical_data = [
        {
            'name': 'Alice Thompson',
            'age': 28,
            'medical_condition': 'Anxiety Disorder',
            'treatment_plan': 'Cognitive Behavioral Therapy, weekly sessions',
            'contact_info': 'alice.thompson@email.com, +1-555-0301'
        },
        {
            'name': 'Carlos Martinez',
            'age': 34,
            'medical_condition': 'Depression',
            'treatment_plan': 'Psychotherapy and medication management',
            'contact_info': 'carlos.martinez@email.com, +1-555-0302'
        },
        {
            'name': 'Jennifer Lee',
            'age': 26,
            'medical_condition': 'PTSD',
            'treatment_plan': 'EMDR therapy, bi-weekly sessions',
            'contact_info': 'jennifer.lee@email.com, +1-555-0303'
        },
        {
            'name': 'Michael Davis',
            'age': 31,
            'medical_condition': 'Bipolar Disorder',
            'treatment_plan': 'Mood stabilization therapy',
            'contact_info': 'michael.davis@email.com, +1-555-0304'
        },
        {
            'name': 'Sarah Wilson',
            'age': 29,
            'medical_condition': 'Social Anxiety',
            'treatment_plan': 'Group therapy and exposure therapy',
            'contact_info': 'sarah.wilson@email.com, +1-555-0305'
        }
    ]
    
    created_patients = []
    db = get_db()
    
    for patient_data in patients_medical_data:
        try:
            # Check if patient already exists (by name)
            existing_patients = list(db.collection('patients').where('name', '==', patient_data['name']).stream())
            
            if existing_patients:
                print(f"❌ Patient record for {patient_data['name']} already exists. Skipping...")
                created_patients.append(existing_patients[0].id)
                continue
            
            # Create patient medical record
            patient_id = create_patient(patient_data)
            
            if patient_id:
                print(f"✅ Patient record created successfully!")
                print(f"   - Name: {patient_data['name']}")
                print(f"   - Condition: {patient_data['medical_condition']}")
                print(f"   - Patient ID: {patient_id}")
                created_patients.append(patient_id)
            else:
                print(f"❌ Failed to create patient record: {patient_data['name']}")
                
        except Exception as e:
            print(f"❌ Error creating patient record {patient_data['name']}: {str(e)}")
    
    return created_patients

def assign_sample_patients_to_therapists(patient_ids, therapist_ids):
    """Assign the sample patients to therapists."""
    print("🔧 Creating Sample Patient-Therapist Assignments...")
    
    if not patient_ids or not therapist_ids:
        print("❌ No patients or therapists available for assignment")
        return
    
    from models import assign_patient
    
    # Assign patients to therapists in a round-robin fashion
    assignments_created = 0
    
    for i, patient_id in enumerate(patient_ids):
        therapist_id = therapist_ids[i % len(therapist_ids)]
        
        try:
            assignment_id = assign_patient(therapist_id, patient_id)
            if assignment_id:
                print(f"✅ Assigned patient {patient_id} to therapist {therapist_id}")
                assignments_created += 1
            else:
                print(f"❌ Failed to assign patient {patient_id} to therapist {therapist_id}")
        except Exception as e:
            print(f"❌ Error assigning patient {patient_id}: {str(e)}")
    
    print(f"✅ Created {assignments_created} patient-therapist assignments")

def main():
    """Run all seed scripts in the correct order."""
    print("🌱 Starting Database Seeding Process...")
    print("=" * 50)
    
    try:
        # Initialize Firebase
        initialize_firebase()
        
        # 1. Seed Admin User
        print("\n1️⃣  SEEDING ADMIN USER")
        admin_id = seed_admin()
        if not admin_id:
            print("❌ Failed to seed admin user. Exiting...")
            sys.exit(1)
        
        # 2. Seed Therapists
        print("\n2️⃣  SEEDING THERAPIST USERS")
        therapist_ids = seed_therapists()
        if not therapist_ids:
            print("❌ Failed to seed therapist users. Exiting...")
            sys.exit(1)
        
        # 3. Seed Patient Users
        print("\n3️⃣  SEEDING PATIENT USERS")
        patient_user_ids = seed_patients()
        if not patient_user_ids:
            print("❌ Failed to seed patient users. Exiting...")
            sys.exit(1)
        
        # 4. Create Sample Patient Medical Records
        print("\n4️⃣  CREATING SAMPLE PATIENT MEDICAL RECORDS")
        patient_record_ids = create_sample_patients_data(therapist_ids)
        if not patient_record_ids:
            print("❌ Failed to create patient medical records. Exiting...")
            sys.exit(1)
        
        # 5. Assign Patients to Therapists
        print("\n5️⃣  ASSIGNING PATIENTS TO THERAPISTS")
        assign_sample_patients_to_therapists(patient_record_ids, therapist_ids)
        
        print("\n" + "=" * 50)
        print("✅ DATABASE SEEDING COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print(f"📊 SUMMARY:")
        print(f"   - Admin Users: 1")
        print(f"   - Therapist Users: {len(therapist_ids)}")
        print(f"   - Patient Users: {len(patient_user_ids)}")
        print(f"   - Patient Medical Records: {len(patient_record_ids)}")
        print(f"   - Patient Assignments: Created")
        print("=" * 50)
        
        print("\n🔑 DEFAULT LOGIN CREDENTIALS:")
        print("   Admin: admin@dbnsyntax.com / admin123")
        print("   Therapist: sarah.johnson@dbnsyntax.com / therapist123")
        print("   Patient: john.smith@email.com / patient123")
        
    except Exception as e:
        print(f"\n❌ SEEDING FAILED: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()