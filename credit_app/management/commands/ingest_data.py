from django.core.management.base import BaseCommand
from credit_app.tasks import ingest_customer_data_task, ingest_loan_data_task
import os

class Command(BaseCommand):
    help = 'Ingests initial customer and loan data from Excel files.'

    def handle(self, *args, **options):
        customer_file = os.path.join(os.getcwd(), 'customer_data.xlsx') 
        loan_file = os.path.join(os.getcwd(), 'loan_data.xlsx') 

        if os.path.exists(customer_file):
            self.stdout.write(self.style.SUCCESS(f'Queuing customer data ingestion from {customer_file}...'))
            ingest_customer_data_task.delay(customer_file)
        else:
            self.stdout.write(self.style.ERROR(f'Customer data file not found: {customer_file}'))

        if os.path.exists(loan_file):
            self.stdout.write(self.style.SUCCESS(f'Queuing loan data ingestion from {loan_file}...'))
            ingest_loan_data_task.delay(loan_file)
        else:
            self.stdout.write(self.style.ERROR(f'Loan data file not found: {loan_file}'))

        self.stdout.write(self.style.SUCCESS('Data ingestion tasks queued. Check Celery worker logs for status.'))