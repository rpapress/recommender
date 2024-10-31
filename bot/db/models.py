from bot.db.connect import db
from datetime import datetime


# -----------------------------------------------------------------------------------------------
# WhatsApp main model
class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    is_manager = db.Column(db.Boolean, nullable=False, default=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    first_message = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(50), nullable=True)
    name_in_whatsapp = db.Column(db.String(80), nullable=True)
    name_user_input = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='не отвечен')
    source = db.Column(db.String(100), nullable=True)
    client_first_contact_datetime = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<Client {self.phone_number}>'

# # -----------------------------------------------------------------------------------------------
# # Manager table
# class Manager(db.Model):
#     __tablename__ = 'managers'

#     id = db.Column(db.Integer, primary_key=True)
#     phone_number = db.Column(db.String(15), unique=True, nullable=False)
#     name_in_whatsapp = db.Column(db.String(100), nullable=True)
#     source = db.Column(db.String(50), nullable=True)
#     created_at = db.Column(db.DateTime, default=datetime.now)

#     def __repr__(self):
#         return f'<Manager {self.name_in_whatsapp}, Phone: {self.phone_number}>'
    
# -----------------------------------------------------------------------------------------------
# WhatsApp support model
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(15), db.ForeignKey('clients.phone_number'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), nullable=False)
    source_url = db.Column(db.String(255), nullable=True)

    timestamp = db.Column(db.String(50), nullable=True)
    message_id = db.Column(db.String(255), nullable=True)
    send_by_api = db.Column(db.Boolean, nullable=False, default=False)
    received_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<Notification {self.receipt_id}>'

# class OutgoingMessage(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     phone_number = db.Column(db.String(20), nullable=False)
#     message_text = db.Column(db.String, nullable=False)
#     status = db.Column(db.String(20), nullable=False)
#     timestamp = db.Column(db.DateTime, default=datetime.now)

# -----------------------------------------------------------------------------------------------
# Save context for ChatGPT
class ChatHistory(db.Model):
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(15), db.ForeignKey('clients.phone_number'), nullable=False)
    user_message = db.Column(db.Text, nullable=False)
    gpt_response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<ChatHistory {self.id} - {self.phone_number}>'