IT SERVICE DESK AND INCIDENT MANAGEMENT SYSTEM
Independent academic project starter

IMPORTANT POSITIONING
This is a separate, independently developed academic project. Do not describe it as work assigned, supervised, or completed at Outworks unless that is independently true and documented. The internship certificate and this project are separate items.

REQUIREMENTS
- Python 3.10 or newer recommended
- Internet connection for the first installation of Flask only

WINDOWS SETUP
1. Extract this folder.
2. Open Command Prompt in this folder.
3. Create a virtual environment (recommended):
   py -m venv .venv
   .venv\Scripts\activate
4. Install Flask:
   py -m pip install -r requirements.txt
5. Start the application:
   py app.py
6. Open the local address printed in the terminal (normally http://127.0.0.1:5000).
7. Create 3-5 sample tickets and test search, filters, status/priority updates, and deletion.
8. Take your own screenshots for the report. Do not claim a test passed unless you actually perform it.

FILES
app.py                 Flask routes, validation, SQLite database operations
templates/index.html   User interface and ticket forms
static/style.css       Responsive styling
service_desk.db        Created automatically on first run

FEATURES
- Create incident tickets
- Store records in SQLite
- List and search tickets
- Filter tickets by status
- Update ticket status and priority
- Delete tickets
- Dashboard counts
- Basic input validation

NOT FOR PRODUCTION
This is a local educational prototype. It does not include login/authentication, role-based access, CSRF protection, email notifications, deployment hardening, or multi-user access controls. Use only fictional sample data.
