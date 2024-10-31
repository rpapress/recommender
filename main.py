from whatsapp_chatbot_python import BaseStates, GreenAPIBot, Notification


bot = GreenAPIBot(
    "7103942473",
    "0040cb8ba8f642de98fbba29668639e01635e4934a624d778c"
)

class States(BaseStates):
    CHAT_FORMATS = "chat_formats"

@bot.router.message(text_message=["start", "/start", "Start"], state=None)
def start_message_handler(notification: Notification) -> None:
    notification.answer(
        (
            'мы начали эту гонку\n'
            'жмякай 1, 2, 3'
        )
    )

@bot.router.message(text_message=["1", "about WorkBot", "Start"], state=None)
def about_workBot_handler(notification: Notification) -> None:
    notification.answer(
        (
            'единичка'
        ), link_preview=False
    )

@bot.router.message(text_message=["2", "How ti send messages"], state=None)
def how_to_send_messages_workBot_handler(notification: Notification) -> None:
    notification.answer(
        (
            "ты нажал 2"
        ), link_preview=False
    )
@bot.router.message(text_message=["3", "How ti send messages"], state=None)
def how_to_send_messages_workBot_handler(notification: Notification) -> None:
    notification.answer(
        (
            "а это ТРИ"
        ), link_preview=False
    )

@bot.router.message(command='menu')
def menu_handler(notification: Notification) -> None:
    sender = notification.sender

    state = notification.state_manager.get_state(sender)
    if not state:
        return start_message_handler
    else:
        notification.state_manager.delete_state(sender)



bot.run_forever()