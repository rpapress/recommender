from bot.db.connect import db
from datetime import datetime


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, nullable=False)
    is_from_client = db.Column(db.Boolean, nullable=False)  # True for client (incoming), False for manager (outgoing)
    webhook_type = db.Column(db.String(50), nullable=False)  # incoming or outgoing
    
    # Sender information (only applicable for incoming messages)
    # client
    sender_name = db.Column(db.String(100), nullable=True)
    sender_chat_id = db.Column(db.String(50))

    # manager
    sender_contact_name = db.Column(db.String(100), nullable=True)
    instance_wid = db.Column(db.String(50), nullable=False) 
    
    # Message content
    message_type = db.Column(db.String(50))  # text, audio, etc.
    message_text = db.Column(db.Text)  # applicable for text messages
    message_description = db.Column(db.Text)
    message_title = db.Column(db.String(100))
    message_preview_type = db.Column(db.String(50))
    message_thumbnail = db.Column(db.Text)  # optional, for storing thumbnails
    message_url = db.Column(db.String(255))  # for links in the message
    mime_type = db.Column(db.String(50))  # applicable for audio messages

    send_by_api = db.Column(db.Boolean, nullable=False, default=False)
    
    instance_id = db.Column(db.String(50), nullable=False)
    instance_type = db.Column(db.String(50), nullable=False, default="whatsapp")
    id_message = db.Column(db.String(50), nullable=False)
    

    timestamp = db.Column(db.DateTime, default=datetime.now)
    create_at = db.Column(db.DateTime, default=datetime.now)

    recommended_response = db.relationship('RecommendedResponse', back_populates='message', uselist=False)

    def __repr__(self):
        return f"<Message id={self.id} type={self.webhook_type} receipt_id={self.receipt_id}>"

class OutgoingMessageStatus(db.Model):
    __tablename__ = 'outgoing_message_statuses'
    
    id = db.Column(db.Integer, primary_key=True)
    # нужно будет вернуть pk, а чтобы это вернуть нужно receipt_id в message корректно передавать
    # message_id = db.Column(db.String(50), db.ForeignKey('messages.id_message'), nullable=False)
    message_id = db.Column(db.String(50), nullable=False)
    chat_id = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # delivered, read, etc.
    send_by_api = db.Column(db.Boolean, nullable=False, default=False)
    
    create_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<OutgoingMessageStatus id={self.id} message_id={self.message_id} status={self.status}>"
    

class ChatContext(db.Model):
    __tablename__ = 'chat_contexts'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(50), nullable=False)
    messages = db.Column(db.JSON, nullable=False, default=list)
    last_update = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<ChatContext chat_id={self.chat_id}>"
    


class RecommendedResponse(db.Model):
    __tablename__ = 'recommended_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    client_phone_number = db.Column(db.String(50), nullable=False)  # Номер телефона клиента
    response_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Связь с сообщением
    message = db.relationship('Message', back_populates='recommended_response')