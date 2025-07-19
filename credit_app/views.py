from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Sum, Count, F 
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd 

from .models import Customer, Loan
from .serializers import (
    RegisterCustomerSerializer, RegisterCustomerResponseSerializer,
    CheckEligibilityRequestSerializer, CheckEligibilityResponseSerializer,
    CreateLoanRequestSerializer, CreateLoanResponseSerializer,
    ViewLoanDetailResponseSerializer, LoanListItemSerializer
)

def calculate_emi(principal, annual_interest_rate, tenure_months):
    """Calculates EMI using compound interest formula."""
    if annual_interest_rate == 0:
        return principal / tenure_months
    
    monthly_interest_rate = (annual_interest_rate / 12) / 100
   
    monthly_interest_rate = Decimal(str(monthly_interest_rate)) 

   
    if monthly_interest_rate == 0:
        return principal / tenure_months

    emi = principal * monthly_interest_rate * (1 + monthly_interest_rate)**tenure_months / \
          ((1 + monthly_interest_rate)**tenure_months - 1)
    return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) 

def calculate_credit_score(customer_id):
    """Calculates credit score based on historical loan data."""
    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        print(f"DEBUG: Customer {customer_id} not found for credit score calculation.")
        return 0 # Or raise an error

    loans = Loan.objects.filter(customer=customer)
    print(f"DEBUG: Customer {customer_id} - Total loans fetched: {loans.count()}")

    credit_score = 0

   
    on_time_loans = loans.filter(emis_paid_on_time__gte=F('tenure')).count()
    print(f"DEBUG: Customer {customer_id} - On-time loans (count): {on_time_loans}")
    if on_time_loans > 0:
        credit_score += 20 # Example weight
    print(f"DEBUG: Customer {customer_id} - Score after on-time: {credit_score}")

   
    total_loans = loans.count()
    print(f"DEBUG: Customer {customer_id} - Total loans (count): {total_loans}")
    if total_loans > 0:
        credit_score += min(20, total_loans * 5) # Max 20 points for number of loans
    print(f"DEBUG: Customer {customer_id} - Score after total loans: {credit_score}")

    
    current_year = date.today().year
   
    active_loans_current_year = loans.filter(
        start_date__year=current_year,
        loan_status='active'
    ).count()
    print(f"DEBUG: Customer {customer_id} - Active loans current year: {active_loans_current_year}")
    if active_loans_current_year > 0:
        credit_score += min(10, active_loans_current_year * 2)
    print(f"DEBUG: Customer {customer_id} - Score after current year activity: {credit_score}")

    
    total_approved_amount = loans.aggregate(Sum('loan_amount'))['loan_amount__sum'] or Decimal('0.00')
    print(f"DEBUG: Customer {customer_id} - Total approved amount: {total_approved_amount}")
    if total_approved_amount > 0:
        credit_score += min(20, int(total_approved_amount / 10000)) # Example: 1 point per 10k approved
    print(f"DEBUG: Customer {customer_id} - Score after approved volume: {credit_score}")

   
    total_active_loan_principal = Loan.objects.filter(
        customer=customer, loan_status='active'
    ).aggregate(Sum('loan_amount'))['loan_amount__sum'] or Decimal('0.00')

    
    if (customer.current_debt + total_active_loan_principal) > customer.approved_limit:
        credit_score = 0
        print(f"DEBUG: Customer {customer_id} - Credit score set to 0 due to total active loans > approved limit.")

    print(f"DEBUG: Customer {customer_id} - Final calculated credit score: {credit_score}")
    
    return max(0, min(100, credit_score))


class RegisterCustomerView(APIView):
    def post(self, request):
        serializer = RegisterCustomerSerializer(data=request.data)
        if serializer.is_valid():
            first_name = serializer.validated_data['first_name']
            last_name = serializer.validated_data['last_name']
            monthly_income = serializer.validated_data['monthly_income']
            phone_number = serializer.validated_data['phone_number']
            age = serializer.validated_data['age'] 

            
            approved_limit = (36 * monthly_income / 100000).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * 100000
            
            with transaction.atomic():
                customer = Customer.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    monthly_salary=monthly_income,
                    approved_limit=approved_limit,
                    current_debt=0 
                )

            response_data = {
                "customer_id": customer.customer_id,
                "name": f"{customer.first_name} {customer.last_name}",
                "age": age,
                "monthly_income": customer.monthly_salary,
                "approved_limit": customer.approved_limit,
                "phone_number": customer.phone_number,
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CheckEligibilityView(APIView):
    def post(self, request):
        serializer = CheckEligibilityRequestSerializer(data=request.data)
        if serializer.is_valid():
            customer_id = serializer.validated_data['customer_id']
            loan_amount = serializer.validated_data['loan_amount']
            interest_rate = serializer.validated_data['interest_rate']
            tenure = serializer.validated_data['tenure']

            try:
                customer = Customer.objects.get(customer_id=customer_id)
            except Customer.DoesNotExist:
                return Response({"message": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

            # Initialize all variables that might be referenced later,
            # especially in early return paths.
            approval = False
            corrected_interest_rate = None
            message = ""
            monthly_installment = Decimal('0.00') # Initialize monthly_installment here

            # Calculate total current EMIs from active loans *first*
            total_current_emis = Loan.objects.filter(
                customer=customer, loan_status='active'
            ).aggregate(Sum('monthly_repayment'))['monthly_repayment__sum'] or Decimal('0.00')

            projected_emi = calculate_emi(loan_amount, interest_rate, tenure)

            
            print(f"DEBUG: Total current EMIs: {total_current_emis}")
            print(f"DEBUG: Projected new EMI: {projected_emi}")
            print(f"DEBUG: 50% of monthly salary: {customer.monthly_salary / 2}")
            if total_current_emis + projected_emi > (customer.monthly_salary / 2):
                message = "Sum of all current EMIs + new loan EMI exceeds 50% of monthly salary. Loan not approved."
                return Response({
                    "customer_id": customer_id,
                    "approval": False,
                    "interest_rate": interest_rate,
                    "corrected_interest_rate": corrected_interest_rate, 
                    "tenure": tenure,
                    "monthly_installment": monthly_installment,
                    "message": message
                }, status=status.HTTP_200_OK)

            
            credit_score = calculate_credit_score(customer_id)
            print(f"DEBUG: Credit Score for customer {customer_id}: {credit_score}")

            
            if credit_score > 50: 
                approval = True
                if interest_rate <= 12: 
                    corrected_interest_rate = interest_rate
                else:
                    corrected_interest_rate = Decimal('12.00') 
            elif 30 < credit_score <= 50: 
                if interest_rate > 12: 
                    approval = True
                    corrected_interest_rate = interest_rate
                else:
                    corrected_interest_rate = Decimal('12.00') 
                    message = "Interest rate too low for credit score. Corrected to 12%."
            elif 10 < credit_score <= 30: 
                if interest_rate > 16: 
                    approval = True
                    corrected_interest_rate = interest_rate
                else:
                    corrected_interest_rate = Decimal('16.00') 
                    message = "Interest rate too low for credit score. Corrected to 16%."
            else: 
                approval = False
                message = "Credit score too low for loan approval."

            
            total_current_loan_amount = Loan.objects.filter(customer=customer, loan_status='active').aggregate(Sum('loan_amount'))['loan_amount__sum'] or Decimal('0.00')
          
            if (total_current_loan_amount + loan_amount) > customer.approved_limit and approval: 
                approval = False
                message = "Loan amount exceeds approved limit."
                corrected_interest_rate = None 

          
            if approval:
                final_interest_rate = corrected_interest_rate if corrected_interest_rate else interest_rate
                monthly_installment = calculate_emi(loan_amount, final_interest_rate, tenure)


            response_data = {
                "customer_id": customer_id,
                "approval": approval,
                "interest_rate": interest_rate,
                "corrected_interest_rate": corrected_interest_rate,
                "tenure": tenure,
                "monthly_installment": monthly_installment,
                "message": message
            }
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateLoanView(APIView):
    def post(self, request):
        serializer = CreateLoanRequestSerializer(data=request.data)
        if serializer.is_valid():
            customer_id = serializer.validated_data['customer_id']
            loan_amount = serializer.validated_data['loan_amount']
            interest_rate = serializer.validated_data['interest_rate']
            tenure = serializer.validated_data['tenure']

            try:
                customer = Customer.objects.get(customer_id=customer_id)
            except Customer.DoesNotExist:
                return Response({"message": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)


            loan_approved = False
            message = ""
            final_interest_rate = interest_rate
            monthly_installment = None 
            loan_id = None 

            total_current_emis = Loan.objects.filter(
                customer=customer, loan_status='active'
            ).aggregate(Sum('monthly_repayment'))['monthly_repayment__sum'] or Decimal('0.00')

            projected_emi = calculate_emi(loan_amount, interest_rate, tenure)


            if total_current_emis + projected_emi > (customer.monthly_salary / 2):
                message = "Sum of all current EMIs + new loan EMI exceeds 50% of monthly salary. Loan not approved."
                return Response({
                    "loan_id": None,
                    "customer_id": customer_id,
                    "loan_approved": False,
                    "message": message,
                    "monthly_installment": None
                }, status=status.HTTP_200_OK)

            
            credit_score = calculate_credit_score(customer_id)

            if credit_score > 50: 
                loan_approved = True
                if interest_rate > 12: 
                    final_interest_rate = Decimal('12.00')
                    message = "Interest rate corrected to 12% for high credit score."
            elif 30 < credit_score <= 50: 
                if interest_rate > 12: 
                    loan_approved = True
                    final_interest_rate = interest_rate
                else:
                    loan_approved = False
                    message = "Interest rate too low for credit score (must be > 12%)."
            elif 10 < credit_score <= 30: 
                if interest_rate > 16: 
                    loan_approved = True
                    final_interest_rate = interest_rate
                else:
                    loan_approved = False
                    message = "Interest rate too low for credit score (must be > 16%)."
            else: 
                loan_approved = False
                message = "Credit score too low for loan approval."

            
            total_current_loan_amount = Loan.objects.filter(customer=customer, loan_status='active').aggregate(Sum('loan_amount'))['loan_amount__sum'] or Decimal('0.00')
            if (total_current_loan_amount + loan_amount) > customer.approved_limit and loan_approved: 
                loan_approved = False
                message = "Loan amount exceeds approved limit."

            if loan_approved:
                monthly_installment = calculate_emi(loan_amount, final_interest_rate, tenure)
                with transaction.atomic():
                    loan = Loan.objects.create(
                        customer=customer,
                        loan_amount=loan_amount,
                        tenure=tenure,
                        interest_rate=final_interest_rate,
                        monthly_repayment=monthly_installment,
                        emis_paid_on_time=0, 
                        start_date=date.today(),
                
                        end_date=date.today() + pd.DateOffset(months=tenure)
                    )
                    
                    customer.current_debt += loan_amount
                    customer.save()
                    loan_id = loan.loan_id
                    if not message: 
                        message = "Loan approved successfully."
            else:
                if not message: 
                    message = "Loan not approved due to eligibility criteria."

            response_data = {
                "loan_id": loan_id,
                "customer_id": customer_id,
                "loan_approved": loan_approved,
                "message": message,
                "monthly_installment": monthly_installment,
            }
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ViewLoanDetailView(APIView):
    def get(self, request, loan_id):
        try:
            loan = Loan.objects.get(loan_id=loan_id)
            customer = loan.customer

            customer_data = {
                "customer_id": customer.customer_id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "phone_number": customer.phone_number,
                "age": 0 
            }

            response_data = {
                "loan_id": loan.loan_id,
                "customer": customer_data,
                "loan_amount": loan.loan_amount,
                "interest_rate": loan.interest_rate,
                "monthly_installment": loan.monthly_repayment,
                "tenure": loan.tenure,
            }
            serializer = ViewLoanDetailResponseSerializer(response_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Loan.DoesNotExist:
            return Response({"message": "Loan not found."}, status=status.HTTP_404_NOT_FOUND)

class ViewCustomerLoansView(APIView):
    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(customer_id=customer_id)
        except Customer.DoesNotExist:
            return Response({"message": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        loans = Loan.objects.filter(customer=customer)
        loan_list = []
        for loan in loans:
            
            repayments_left = loan.tenure - loan.emis_paid_on_time
            
            if repayments_left < 0:
                repayments_left = 0

            loan_list.append({
                "loan_id": loan.loan_id,
                "loan_amount": loan.loan_amount,
                "interest_rate": loan.interest_rate,
                "monthly_installment": loan.monthly_repayment,
                "repayments_left": repayments_left,
            })
        serializer = LoanListItemSerializer(loan_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)