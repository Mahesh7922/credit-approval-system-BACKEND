from django.db import models

class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, unique=True)
    monthly_salary = models.IntegerField(max_length=12)
    approved_limit = models.IntegerField(max_length=12)
    current_debt = models.IntegerField(max_length=12, default=0)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Loan(models.Model):
    loan_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    loan_amount = models.IntegerField(max_length=12)
    tenure = models.IntegerField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    monthly_repayment = models.IntegerField(max_length=12)
    emis_paid_on_time = models.IntegerField(default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    loan_status = models.CharField(max_length=20, default='active')

    def __str__(self):
        return f"Loan {self.loan_id} for {self.customer.first_name}"