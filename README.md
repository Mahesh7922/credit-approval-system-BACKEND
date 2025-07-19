## Credit Approval System

This project implements a backend credit approval system using Django and Django Rest Framework. It processes customer and loan data, calculates credit scores, and provides API endpoints for customer registration, loan eligibility checks, loan creation, and viewing loan details. The entire application is containerized using Docker and utilizes PostgreSQL as its database, with Celery handling background data ingestion.

### Features

* **Customer Registration:** Register new customers with automatically calculated approved credit limits.

* **Loan Eligibility Check:** Determine loan eligibility based on a dynamically calculated credit score and monthly EMI burden.

* **Loan Creation:** Process and approve new loans if eligibility criteria are met, updating customer debt.

* **Loan Details View:** Retrieve detailed information for a specific loan, including customer details.

* **Customer Loans View:** Retrieve all current loan details for a given customer.

* **Data Ingestion:** Background tasks to ingest initial customer and loan data from Excel/CSV files.

### Testing Video:
* Link : https://drive.google.com/file/d/1ZSh3e0EOzcPuGXqUGP60YgiZwxDPj-pU/view?usp=sharing

### Technologies Used

* **Python 3.9+**

* **Django 4+**

* **Django Rest Framework (DRF)**

* **PostgreSQL:** Relational database for storing customer and loan data.

* **Celery:** Distributed task queue for background data ingestion.

* **Redis:** Message broker and backend for Celery.

* **Pandas:** For reading and processing Excel/CSV data during ingestion.

* **Docker & Docker Compose:** For containerization and orchestration of the application services.

### Setup and Installation

Follow these steps to get the project up and running on your local machine.

#### Prerequisites

* [Docker](https://docs.docker.com/get-docker/)

* [Docker Compose](https://docs.docker.com/compose/install/) (usually comes with Docker Desktop)

#### 1. Clone the Repository


git clone https://github.com/Mahesh7922/credit-approval-system-BACKEND.git
cd credit-approval-system-BACKEND


#### 2. Prepare Data Files

Place your `customer_data.xlsx` (or `customer_data.xlsx - Sheet1.csv`) and `loan_data.xlsx` (or `loan_data.xlsx - Sheet1.csv`) files in the root directory of the project (the same directory as `docker-compose.yml` and `manage.py`). Ensure the column headers in these files exactly match the `snake_case` names expected by the ingestion script (e.g., `customer_id`, `monthly_salary`, `loan_id`, `monthly_repayment`).

**Note** on **`current_debt`:** The `customer_data.xlsx` file provided in the assignment does not contain a `current_debt` column. The ingestion script is designed to default `current_debt` to `0.00` if this column is missing from the input file.

#### 3. Build and Run Docker Containers

First, remove any old Docker volumes to ensure a clean database start (especially if you've run it before):


docker-compose down -v


Then, build the Docker images and start the services in detached mode:


docker-compose up --build -d


This will start three services: `db` (PostgreSQL), `redis` (Redis), `web` (Django application), and `celery_worker` (Celery background worker).

#### 4. Apply Database Migrations

Once the containers are running, apply the Django database migrations to create the necessary tables:


docker-compose exec web python manage.py makemigrations credit_app
docker-compose exec web python manage.py migrate


#### 5. Ingest Initial Data

Now, trigger the background tasks to ingest data from your Excel/CSV files. It's crucial to monitor the `celery_worker` logs for any errors during this step.

Open a **separate terminal** to monitor logs:


docker-compose logs -f celery_worker


In your **main terminal**, run the ingestion command:


docker-compose exec web python manage.py ingest_data


Check the `celery_worker` logs for messages like "Customer data ingestion complete." and "Loan data ingestion complete." If you see `KeyError` or "Customer with ID X not found" warnings, it means the data wasn't fully ingested (refer to troubleshooting).

#### 6. Verify Data Ingestion (Optional)

You can connect to the PostgreSQL database directly to verify that data has been loaded:


docker exec -it credit_approval_system-db-1 psql -U postgres -d postgres


(Replace `credit_approval_system-db-1` with your actual DB container name if different, found via `docker ps`)

Then, run SQL queries:

```sql
SELECT * FROM credit_app_customer;
SELECT * FROM credit_app_loan;
\q  -- Type this to exit psql
```

### API Endpoints

The API is accessible via `http://localhost:8000/`.

#### 1. Register Customer

* **URL:** `/register`

* **Method:** `POST`

* **Description:** Adds a new customer to the system. The `approved_limit` is calculated as `36 * monthly_salary` (rounded to nearest lakh).

* **Request Body Example:**

    ```json
    {
      "first_name": "John",
      "last_name": "Doe",
      "age": 30,
      "monthly_income": 50000,
      "phone_number": "9876543210"
    }
    ```

* **Success Response (201 Created):**

    ```json
    {
      "customer_id": 1,
      "name": "John Doe",
      "age": 30,
      "monthly_income": 50000.00,
      "approved_limit": 1800000.00,
      "phone_number": "9876543210"
    }
    ```

#### 2. Check Loan Eligibility

* **URL:** `/check-eligibility`

* **Method:** `POST`

* **Description:** Determines if a loan can be approved for a customer based on their credit score and financial situation.

* **Request Body Example:**

    ```json
    {
      "customer_id": 1,
      "loan_amount": 100000.00,
      "interest_rate": 10.50,
      "tenure": 12
    }
    ```

* **Success Response (200 OK - Approved Example):**

    ```json
    {
      "customer_id": 1,
      "approval": true,
      "interest_rate": 10.50,
      "corrected_interest_rate": 10.50,
      "tenure": 12,
      "monthly_installment": 8838.21,
      "message": "Loan approved"
    }
    ```

* **Success Response (200 OK - Denied Example):**

    ```json
    {
      "customer_id": 3,
      "approval": false,
      "interest_rate": 22.00,
      "corrected_interest_rate": null,
      "tenure": 6,
      "monthly_installment": 0.00,
      "message": "Credit score too low for loan approval."
    }
    ```

#### 3. Create Loan

* **URL:** `/create-loan`

* **Method:** `POST`

* **Description:** Processes a new loan application. If eligible, the loan is created and customer's `current_debt` is updated.

* **Request Body Example:**

    ```json
    {
      "customer_id": 1,
      "loan_amount": 100000.00,
      "interest_rate": 10.50,
      "tenure": 12
    }
    ```

* **Success Response (200 OK - Loan Approved):**

    ```json
    {
      "loan_id": 1001,
      "customer_id": 1,
      "loan_approved": true,
      "message": "Loan approved successfully.",
      "monthly_installment": 8838.21
    }
    ```

* **Success Response (200 OK - Loan Denied):**

    ```json
    {
      "loan_id": null,
      "customer_id": 3,
      "loan_approved": false,
      "message": "Credit score too low for loan approval.",
      "monthly_installment": null
    }
    ```

#### 4. View Loan Details

* **URL:** `/view-loan/<int:loan_id>`

* **Method:** `GET`

* **Description:** Retrieves detailed information for a specific loan and its associated customer.

* **Example URL:** `http://localhost:8000/view-loan/101`

* **Success Response (200 OK):**

    ```json
    {
      "loan_id": 101,
      "customer": {
        "id": 1,
        "first_name": "Alice",
        "last_name": "Smith",
        "phone_number": "9876511111",
        "age": 0
      },
      "loan_amount": 100000.00,
      "interest_rate": 10.00,
      "monthly_installment": 8791.59,
      "tenure": 12
    }
    ```

* **Error Response (404 Not Found):**

    ```json
    {
      "message": "Loan not found."
    }
    ```

#### 5. View Customer Loans

* **URL:** `/view-loans/<int:customer_id>`

* **Method:** `GET`

* **Description:** Retrieves all current and past loan details for a specific customer.

* **Example URL:** `http://localhost:8000/view-loans/1`

* **Success Response (200 OK):**

    ```json
    [
      {
        "loan_id": 101,
        "loan_amount": 100000.00,
        "interest_rate": 10.00,
        "monthly_installment": 8791.59,
        "repayments_left": 0
      },
      {
        "loan_id": 102,
        "loan_amount": 50000.00,
        "interest_rate": 11.00,
        "monthly_installment": 8609.96,
        "repayments_left": 3
      }
    ]
    ```

* **Error Response (404 Not Found):**

    ```json
    {
      "message": "Customer not found."
    }
    ```

### Credit Score Logic

The credit score (out of 100) is calculated based on the following components:

* **Past Loans paid on time:** Contribution based on completed loans with all EMIs paid.

* **Number of loans taken in past:** Contribution based on the total count of loans.

* **Loan activity in current year:** Contribution based on active loans in the current year.

* **Loan approved volume:** Contribution based on the total principal amount of approved loans.

* **Current Debt vs. Approved Limit:** If the sum of a customer's active loan principals plus their `current_debt` (from the customer record) exceeds their `approved_limit`, the credit score is immediately set to 0.

Loan approval and interest rate correction are then determined by the calculated credit score and the customer's monthly salary vs. total EMI burden.

### Troubleshooting

* **`KeyError` during ingestion:** Ensure column names in your Excel/CSV files exactly match those in `credit_app/tasks.py` (case-sensitive).

* **`UnboundLocalError`:** Check variable initialization and order of operations in your views.

* **`IntegrityError: duplicate key`:** This usually means you're trying to insert a `customer_id` or `loan_id` that already exists. A `docker-compose down -v` followed by `docker-compose up --build -d` will clear the database.

* **`Repository not found` during `git push`:** Double-check your GitHub repository URL for typos (e.g., extra characters like `]`).

* **"Customer not found for loan" warnings during ingestion:** This indicates that the `customer_data.xlsx` ingestion failed or didn't complete before `loan_data.xlsx` ingestion, or that a customer ID in `loan_data.xlsx` doesn't exist in `customer_data.xlsx`.
