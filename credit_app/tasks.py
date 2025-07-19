import pandas as pd
from celery import shared_task
from django.db import transaction
from .models import Customer, Loan
from datetime import datetime

@shared_task
def ingest_customer_data_task(file_path):
    df = pd.read_excel(file_path)
    customers_to_create = []
    for index, row in df.iterrows():

        approved_limit = round(36 * row['Monthly Salary'] / 100000) * 100000
        customers_to_create.append(
            Customer(
                customer_id=row['Customer ID'],
                first_name=row['First Name'],
                last_name=row['Last Name'],
                phone_number=str(row['Phone Number']),  
                monthly_salary=row['Monthly Salary'],
                approved_limit=approved_limit,
                current_debt=0  
            )
        )
    with transaction.atomic():
        Customer.objects.bulk_create(customers_to_create, ignore_conflicts=True)
    print("Customer data ingestion complete.")

@shared_task
def ingest_loan_data_task(file_path):
    df = pd.read_excel(file_path)
    loans_to_create = []
    for index, row in df.iterrows():
        try:
            customer = Customer.objects.get(customer_id=row['Customer ID'])
            
            start_date = pd.to_datetime(row['Date of Approval']).date()
            end_date = pd.to_datetime(row['End Date']).date()
            

            current_date = datetime.now().date()
            loan_status = 'active'
            if end_date < current_date:
                if row['EMIs paid on Time'] == row['Tenure']:
                    loan_status = 'paid'
                else:
                    loan_status = 'default'
            
            loans_to_create.append(
                Loan(
                    loan_id=row['Loan ID'],
                    customer=customer,
                    loan_amount=row['Loan Amount'],
                    tenure=row['Tenure'],
                    interest_rate=row['Interest Rate'],
                    monthly_repayment=row['Monthly payment'],  
                    emis_paid_on_time=row['EMIs paid on Time'],
                    start_date=start_date,
                    end_date=end_date,
                    loan_status=loan_status
                )
            )
            

            if loan_status == 'active':
                with transaction.atomic():
                    customer.current_debt += int(row['Loan Amount'])
                    customer.save()
                    
        except Customer.DoesNotExist:
            print(f"Customer with ID {row['Customer ID']} not found for loan {row['Loan ID']}")
            continue
        
    with transaction.atomic():
        Loan.objects.bulk_create(loans_to_create, ignore_conflicts=True)
    print("Loan data ingestion complete.")