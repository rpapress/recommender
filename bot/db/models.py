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
    sender_name = db.Column(db.String(100))
    sender_chat_id = db.Column(db.String(50))

    # manager
    sender_contact_name = db.Column(db.String(100))
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

    instance_id = db.Column(db.String(50), nullable=False)
    instance_type = db.Column(db.String(50), nullable=False, default="whatsapp")
    id_message = db.Column(db.String(50), nullable=False, unique=True)
    

    timestamp = db.Column(db.DateTime, default=datetime.now)
    create_at = db.Column(db.DateTime, default=datetime.now)

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

class BotCounter(db.Model):
    __tablename__ = 'bot_counters'
    
    id = db.Column(db.Integer, primary_key=True)
    manager_chat_id = db.Column(db.String(50), nullable=False, unique=True)
    bot_reply_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f"<BotCounter manager_chat_id={self.manager_chat_id} bot_reply_count={self.bot_reply_count}>"


# # -----------------------------------------------------------------------------------------------
# # Save context for ChatGPT
# class ChatHistory(db.Model):
#     __tablename__ = 'chat_history'
    
#     id = db.Column(db.Integer, primary_key=True)
#     phone_number = db.Column(db.String(15), db.ForeignKey('clients.phone_number'), nullable=False)
#     user_message = db.Column(db.Text, nullable=False)
#     gpt_response = db.Column(db.Text, nullable=False)
#     timestamp = db.Column(db.DateTime, default=datetime.now)

#     def __repr__(self):
#         return f'<ChatHistory {self.id} - {self.phone_number}>'