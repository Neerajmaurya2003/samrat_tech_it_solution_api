
import os
from dotenv import load_dotenv 
from flask import Flask,request,jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta
from flask_cors import CORS
from sqlalchemy.sql import func
from email.message import EmailMessage
import smtplib
from datetime import datetime
import re

load_dotenv()
app=Flask(__name__)
CORS(app,origins=os.getenv('COMPANY_URI'))

app.config['SQLALCHEMY_DATABASE_URI']=os.getenv('DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
DUPLICATE_TIME_WINDOW = timedelta(minutes=10)
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
PHONE_REGEX = r'^[6-9]\d{9}$' 

db=SQLAlchemy(app)

def is_valid_email(email):
    return re.match(EMAIL_REGEX, email)

def is_valid_phone(phone):
    return re.match(PHONE_REGEX, phone)

def normalize_phone(phone):
    phone = phone.replace(" ", "").replace("-", "")
    if phone.startswith("+91"):
        phone = phone[3:]
    return phone

class ContactSubmissions(db.Model):

    __tablename__="contact_submissions"

    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(100),nullable=False)
    message=db.Column(db.Text,nullable=False)
    contact_no=db.Column(db.String(20),nullable=False)
    submitted_at=db.Column(db.DateTime(timezone=True),default=func.now(),onupdate=func.now())

    def __repr__(self):
        return f'<submission {self.name}'
    
with app.app_context():
    db.create_all()


# Route to Add Details in the database
@app.route("/contact",methods=['POST'])
def handle_contact_form():
    data=request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    contact_no = normalize_phone(data.get("contact_no", ""))
    message = data.get("message", "").strip()
    if not name or not email or not contact_no or not message:
        return jsonify({
            "error": "All fields are required"
        }), 400
    if len(name) < 2:
        return jsonify({
            "error": "Name must be at least 2 characters long"
        }), 400
    if not is_valid_email(email):
        return jsonify({
            "error": "Invalid email format"
        }), 400
    if not is_valid_phone(contact_no):
        return jsonify({
            "error": "Invalid contact number. Must be a 10-digit Indian mobile number"
        }), 400
    if len(message) < 10:
        return jsonify({
            "error": "Message must be at least 10 characters long"
        }), 400
    
    
    recent_submission = (
    ContactSubmissions.query
    .filter(
        (ContactSubmissions.email == email) |
        (ContactSubmissions.contact_no == contact_no),
        ContactSubmissions.submitted_at >= func.now() - DUPLICATE_TIME_WINDOW
    )
    .order_by(ContactSubmissions.submitted_at.desc())
    .first()
    )

    if recent_submission:
        return jsonify({
        "error": "You can submit again after 10 minutes"
    }), 429
    new_submission=ContactSubmissions(
        name=name,
        email=email,
        message=message,
        contact_no=contact_no
    )

    try:
        db.session.add(new_submission)
        sendmail(data)
        db.session.commit()
        return jsonify({"message":"Contact Form Saved Successfully"}),201
    except Exception as e:
        db.session.rollback()
        print(f'Database Error {e}')
        return jsonify({"error":"Internal Server Error"}),500


@app.route("/")
def hello():
    return {"message":"App is running"}


def sendmail(data):
    msg = EmailMessage()
    msg['From'] = os.getenv('SENDER_MAIL')
    msg['To'] = os.getenv('RECIEVER_MAIL')
    msg['Subject'] = 'New Submission'
    msg.set_content(
        f"""
New Submission on Contact us Section of Samrat Tech IT Solutions

        Name = {data['name']}
        email = {data['email']}
        contact = {data['contact_no']}
        message = {data['message']}
        timestamp ={str(datetime.now())}
        """
    )
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(os.getenv('SENDER_MAIL'), os.getenv('SENDER_PASSWORD'))
        server.send_message(msg)
    print("Email Sent successfully")


if __name__ =='__main__':
    app.run(debug=True,port=5000)
