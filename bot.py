import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import asyncio
from database import Database

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
WAITING_NAME, WAITING_SURNAME, WAITING_MESSAGE, WAITING_REPLY, EDIT_NAME, EDIT_SURNAME = range(6)

# Admin ID
ADMIN_ID = 1125355606

class TainaPoshtaBot:
    def __init__(self, token: str):
        self.token = token
        self.db = Database()
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup all command and message handlers"""
        
        # Registration conversation
        registration_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start_command)],
            states={
                WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_name)],
                WAITING_SURNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_surname)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_command)],
        )
        
        # Edit name conversation
        edit_name_handler = ConversationHandler(
            entry_points=[CommandHandler('editname', self.edit_name_command)],
            states={
                EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_edit_name)],
                EDIT_SURNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_edit_surname)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_command)],
        )
        
        self.application.add_handler(registration_handler)
        self.application.add_handler(edit_name_handler)
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('send', self.send_command))
        self.application.add_handler(CommandHandler('admin', self.admin_command))
        self.application.add_handler(CommandHandler('users', self.admin_users_command))
        self.application.add_handler(CommandHandler('deleteuser', self.admin_delete_user_command))
        self.application.add_handler(CommandHandler('myinfo', self.myinfo_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        # Check if user already exists
        user = self.db.get_user(user_id)
        
        if user:
            if user['approved']:
                await update.message.reply_text(
                    "🕊️ Вітаю в Таємній Пошті!\n\n"
                    "Використовуй /send щоб надіслати анонімне послання.\n"
                    "Використовуй /help для допомоги."
                )
            else:
                await update.message.reply_text(
                    "⏳ Твоя реєстрація очікує підтвердження адміністратора.\n"
                    "Будь ласка, почекай трохи."
                )
            return ConversationHandler.END
        
        # New user - start registration
        await update.message.reply_text(
            "🕊️ Вітаю в Таємній Пошті!\n\n"
            "Це бот для анонімних повідомлень у нашій молодіжній спільноті.\n\n"
            "Щоб почати, потрібно зареєструватися.\n"
            "Введи своє ім'я:"
        )
        return WAITING_NAME

    async def process_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user's first name"""
        name = update.message.text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("❌ Ім'я занадто коротке. Спробуй ще раз:")
            return WAITING_NAME
        
        context.user_data['name'] = name
        await update.message.reply_text(f"Добре, {name}! Тепер введи своє прізвище:")
        return WAITING_SURNAME

    async def process_surname(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user's surname and complete registration"""
        surname = update.message.text.strip()
        
        if len(surname) < 2:
            await update.message.reply_text("❌ Прізвище занадто коротке. Спробуй ще раз:")
            return WAITING_SURNAME
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        name = context.user_data['name']
        
        # Save to database
        self.db.add_user(user_id, name, surname, username)
        
        await update.message.reply_text(
            f"✅ Дякую, {name} {surname}!\n\n"
            "Твоя реєстрація відправлена адміністратору на розгляд.\n"
            "Очікуй підтвердження. Ми повідомимо тебе, коли зможеш користуватися ботом! 🕊️"
        )
        
        # Notify admin
        await self.notify_admin_new_user(user_id, name, surname, username, update.effective_user)
        
        return ConversationHandler.END

    async def edit_name_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /editname command"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user:
            await update.message.reply_text(
                "❌ Ти ще не зареєстрований.\n"
                "Використовуй /start для реєстрації."
            )
            return ConversationHandler.END
        
        # Store current name for reference
        context.user_data['current_first_name'] = user['first_name']
        context.user_data['current_last_name'] = user['last_name']
        
        await update.message.reply_text(
            f"📝 Редагування профілю\n\n"
            f"Зараз твоє ім'я: {user['first_name']} {user['last_name']}\n\n"
            f"Введи нове ім'я або /cancel щоб скасувати:"
        )
        return EDIT_NAME

    async def process_edit_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process edited first name"""
        name = update.message.text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("❌ Ім'я занадто коротке. Спробуй ще раз:")
            return EDIT_NAME
        
        context.user_data['edit_name'] = name
        await update.message.reply_text(f"Добре! Тепер введи нове прізвище:")
        return EDIT_SURNAME

    async def process_edit_surname(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process edited surname and send to admin for approval"""
        surname = update.message.text.strip()
        
        if len(surname) < 2:
            await update.message.reply_text("❌ Прізвище занадто коротке. Спробуй ще раз:")
            return EDIT_SURNAME
        
        user_id = update.effective_user.id
        name = context.user_data['edit_name']
        
        # Get current user info
        user = self.db.get_user(user_id)
        old_name = f"{user['first_name']} {user['last_name']}"
        new_name = f"{name} {surname}"
        
        # Send to admin for approval
        await self.notify_admin_name_change(user_id, old_name, new_name, name, surname, user['username'])
        
        await update.message.reply_text(
            f"✅ Запит на зміну імені надіслано!\n\n"
            f"Старе ім'я: {old_name}\n"
            f"Нове ім'я: {new_name}\n\n"
            f"Очікуй підтвердження адміністратора."
        )
        
        # Clear context
        context.user_data.pop('edit_name', None)
        
        return ConversationHandler.END

    async def myinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user their current information"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user:
            await update.message.reply_text(
                "❌ Ти ще не зареєстрований.\n"
                "Використовуй /start для реєстрації."
            )
            return
        
        status = "✅ Підтверджений" if user['approved'] else "⏳ Очікує підтвердження"
        username_text = f"@{user['username']}" if user['username'] else "немає"
        
        await update.message.reply_text(
            f"👤 Твоя інформація:\n\n"
            f"Ім'я: {user['first_name']} {user['last_name']}\n"
            f"Username: {username_text}\n"
            f"Статус: {status}\n\n"
            f"💡 Щоб змінити ім'я, використовуй /editname"
        )

    async def notify_admin_new_user(self, user_id: int, name: str, surname: str, username: str, user_obj):
        """Notify admin about new registration"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Підтвердити", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        username_text = f"@{username}" if username else "немає username"
        
        # Get additional user info from Telegram profile
        first_name_tg = user_obj.first_name if user_obj.first_name else "не вказано"
        last_name_tg = user_obj.last_name if user_obj.last_name else ""
        full_name_tg = f"{first_name_tg} {last_name_tg}".strip()
        
        # Language code
        lang = user_obj.language_code if user_obj.language_code else "не вказано"
        
        await self.application.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 Нова реєстрація!\n\n"
                 f"📝 Вказане ім'я: {name} {surname}\n"
                 f"👤 Ім'я в Telegram: {full_name_tg}\n"
                 f"🆔 Username: {username_text}\n"
                 f"🔢 ID: {user_id}\n"
                 f"🌐 Мова: {lang}\n\n"
                 f"⚠️ Перевір, чи збігається вказане ім'я з реальним!",
            reply_markup=reply_markup
        )

    async def notify_admin_name_change(self, user_id: int, old_name: str, new_name: str, new_first: str, new_last: str, username: str):
        """Notify admin about name change request"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Підтвердити", callback_data=f"approve_name_{user_id}_{new_first}_{new_last}"),
                InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_name_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        username_text = f"@{username}" if username else "немає username"
        
        await self.application.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔄 Запит на зміну імені!\n\n"
                 f"👤 Користувач: {old_name}\n"
                 f"🆔 Username: {username_text}\n"
                 f"🔢 ID: {user_id}\n\n"
                 f"📝 Хоче змінити на: {new_name}\n\n"
                 f"⚠️ Перевір, чи це не спроба підробити чуже ім'я!",
            reply_markup=reply_markup
        )

    async def send_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /send command - show list of users"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['approved']:
            await update.message.reply_text(
                "❌ Ти ще не підтверджений адміністратором.\n"
                "Зачекай на підтвердження або напиши /start для реєстрації."
            )
            return
        
        # Get all approved users except sender
        users = self.db.get_approved_users(exclude_user_id=user_id)
        
        if not users:
            await update.message.reply_text(
                "😔 Поки що немає інших підтверджених користувачів.\n"
                "Зачекай, поки хтось ще приєднається!"
            )
            return
        
        # Create inline keyboard with users
        keyboard = []
        for user in users:
            button_text = f"{user['first_name']} {user['last_name']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_{user['user_id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💌 Кому хочеш надіслати анонімне повідомлення?\n"
            "Вибери отримувача зі списку:",
            reply_markup=reply_markup
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Name change approval
        if data.startswith('approve_name_'):
            if query.from_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Тільки адміністратор може це зробити.")
                return
            
            parts = data.split('_')
            user_id = int(parts[2])
            new_first = parts[3]
            new_last = parts[4]
            
            # Update name in database
            self.db.update_user_name(user_id, new_first, new_last)
            
            await query.edit_message_text(
                f"✅ Зміну імені підтверджено!\n\n"
                f"Нове ім'я: {new_first} {new_last}"
            )
            
            # Notify user
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Твій запит на зміну імені підтверджено!\n\n"
                         f"Твоє нове ім'я: {new_first} {new_last}\n\n"
                         f"Тепер інші користувачі бачитимуть тебе під цим ім'ям."
                )
            except Exception as e:
                logger.error(f"Could not notify user about name change: {e}")
        
        elif data.startswith('reject_name_'):
            if query.from_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Тільки адміністратор може це зробити.")
                return
            
            user_id = int(data.split('_')[2])
            user = self.db.get_user(user_id)
            
            await query.edit_message_text(
                f"❌ Зміну імені відхилено для користувача {user['first_name']} {user['last_name']}"
            )
            
            # Notify user
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text="❌ На жаль, твій запит на зміну імені відхилено.\n"
                         "Якщо є питання, зв'яжись з адміністратором."
                )
            except Exception as e:
                logger.error(f"Could not notify user about name change rejection: {e}")
        
        # Admin approval/rejection
        elif data.startswith('approve_'):
            if query.from_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Тільки адміністратор може це зробити.")
                return
            
            user_id = int(data.split('_')[1])
            self.db.approve_user(user_id)
            user = self.db.get_user(user_id)
            
            await query.edit_message_text(
                f"✅ Користувач {user['first_name']} {user['last_name']} підтверджений!"
            )
            
            # Notify user
            await self.application.bot.send_message(
                chat_id=user_id,
                text="🎉 Твою реєстрацію підтверджено!\n\n"
                     "Тепер ти можеш користуватися ботом.\n"
                     "Використовуй /send щоб надіслати анонімне повідомлення."
            )
        
        elif data.startswith('reject_'):
            if query.from_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Тільки адміністратор може це зробити.")
                return
            
            user_id = int(data.split('_')[1])
            user = self.db.get_user(user_id)
            self.db.delete_user(user_id)
            
            await query.edit_message_text(
                f"❌ Користувач {user['first_name']} {user['last_name']} відхилений."
            )
            
            # Notify user
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text="😔 На жаль, твою реєстрацію не підтверджено.\n"
                         "Якщо є питання, зв'яжись з адміністратором групи."
                )
            except Exception as e:
                logger.error(f"Could not notify rejected user: {e}")
        
        # Admin delete user from list
        elif data.startswith('delete_'):
            if query.from_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Тільки адміністратор може це зробити.")
                return
            
            user_id_to_delete = int(data.split('_')[1])
            
            # Don't allow admin to delete themselves
            if user_id_to_delete == ADMIN_ID:
                await query.answer("❌ Ти не можеш видалити себе!", show_alert=True)
                return
            
            user = self.db.get_user(user_id_to_delete)
            
            if not user:
                await query.edit_message_text("❌ Користувача не знайдено.")
                return
            
            # Delete user
            self.db.delete_user(user_id_to_delete)
            
            await query.edit_message_text(
                f"✅ Користувача {user['first_name']} {user['last_name']} (ID: {user_id_to_delete}) видалено!"
            )
            
            # Notify deleted user
            try:
                await self.application.bot.send_message(
                    chat_id=user_id_to_delete,
                    text="❌ Твій доступ до бота було скасовано адміністратором.\n"
                         "Якщо є питання, зв'яжись з лідером молодіжної групи."
                )
            except Exception as e:
                logger.error(f"Could not notify deleted user: {e}")
        
        # User selection for sending message
        elif data.startswith('select_'):
            recipient_id = int(data.split('_')[1])
            recipient = self.db.get_user(recipient_id)
            
            context.user_data['recipient_id'] = recipient_id
            context.user_data['reply_to_message'] = None  # This is a new message, not a reply
            
            await query.edit_message_text(
                f"💌 Ти обрав: {recipient['first_name']} {recipient['last_name']}\n\n"
                "Тепер напиши своє повідомлення. Воно буде надіслане анонімно.\n\n"
                "❗️ Пам'ятай: повідомлення повинно бути корисним!"
            )
        
        # Reply to anonymous message
        elif data.startswith('reply_'):
            message_id = int(data.split('_')[1])
            
            # Get the original message to find who sent it
            message = self.db.get_message(message_id)
            
            if not message:
                await query.edit_message_text("❌ Повідомлення не знайдено.")
                return
            
            # Store the message_id to reply to
            context.user_data['reply_to_message'] = message_id
            context.user_data['recipient_id'] = message['sender_id']  # Reply goes back to sender
            
            await query.answer()
            await self.application.bot.send_message(
                chat_id=query.from_user.id,
                text="✍️ Напиши свою відповідь. Вона буде надіслана анонімно тій людині, "
                     "яка надіслала тобі повідомлення."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages (for sending anonymous messages)"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['approved']:
            await update.message.reply_text(
                "❌ Спочатку потрібно зареєструватися та отримати підтвердження.\n"
                "Використовуй /start"
            )
            return
        
        # Check if user has selected a recipient
        if 'recipient_id' not in context.user_data:
            await update.message.reply_text(
                "Використовуй /send щоб вибрати, кому надіслати повідомлення."
            )
            return
        
        recipient_id = context.user_data['recipient_id']
        message_text = update.message.text
        reply_to_message = context.user_data.get('reply_to_message')
        
        # Save message to database
        try:
            # If this is a reply, link it to the original message
            thread_id = None
            if reply_to_message:
                # Get the thread starter (original message)
                thread_id = self.db.get_thread_starter(reply_to_message)
            
            message_id = self.db.save_message(user_id, recipient_id, message_text, thread_id)
            
            # Prepare the message for recipient
            if reply_to_message:
                message_for_recipient = (
                    f"💬 Відповідь на твоє анонімне повідомлення:\n\n"
                    f"{message_text}\n\n"
                    f"───────────────\n"
                    f"Людина, якій ти писав(ла), відповіла! 🕊️"
                )
            else:
                message_for_recipient = (
                    f"💌 Тобі надійшло анонімне повідомлення:\n\n"
                    f"{message_text}\n\n"
                    f"───────────────\n"
                    f"Хтось із нашої спільноти думає про тебе! 🕊️"
                )
            
            # Add reply button
            keyboard = [[InlineKeyboardButton("💬 Відповісти анонімно", callback_data=f"reply_{message_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send anonymous message to recipient
            await self.application.bot.send_message(
                chat_id=recipient_id,
                text=message_for_recipient,
                reply_markup=reply_markup
            )
            
            await update.message.reply_text(
                "✅ Твоє повідомлення надіслано!\n\n"
                "Хочеш надіслати ще одне? Використовуй /send"
            )
            
            # Clear recipient from context
            context.user_data.pop('recipient_id', None)
            context.user_data.pop('reply_to_message', None)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await update.message.reply_text(
                "❌ Не вдалося надіслати повідомлення. Спробуй пізніше."
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        
        if user_id == ADMIN_ID:
            # Admin help
            await update.message.reply_text(
                "📖 Довідка для адміністратора\n\n"
                "👤 Команди для користувачів:\n"
                "🔹 /start - Реєстрація в боті\n"
                "🔹 /send - Надіслати анонімне повідомлення\n"
                "🔹 /editname - Змінити своє ім'я\n"
                "🔹 /myinfo - Подивитись свою інформацію\n"
                "🔹 /help - Показати цю довідку\n\n"
                "👨‍💼 Команди адміністратора:\n"
                "🔹 /admin - Статистика боту\n"
                "🔹 /users - Список всіх користувачів (з можливістю видалення)\n"
                "🔹 /deleteuser [ID] - Видалити користувача за ID\n\n"
                "💡 Використовуй бот для підтримки молоді! 🕊️"
            )
        else:
            # Regular user help
            await update.message.reply_text(
                "📖 Довідка по боту Таємна Пошта\n\n"
                "🔹 /start - Реєстрація в боті\n"
                "🔹 /send - Надіслати анонімне повідомлення\n"
                "🔹 /editname - Змінити своє ім'я\n"
                "🔹 /myinfo - Подивитись свою інформацію\n"
                "🔹 /help - Показати цю довідку\n\n"
                "❓ Як це працює:\n"
                "1. Зареєструйся і дочекайся підтвердження\n"
                "2. Використовуй /send щоб вибрати отримувача\n"
                "3. Напиши своє повідомлення\n"
                "4. Воно буде надіслано анонімно!\n"
                "5. Якщо хтось надішле тобі повідомлення - ти можеш відповісти анонімно\n\n"
                "💡 Використовуй бот для підтримки та добрих слів! 🕊️"
            )

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current operation"""
        await update.message.reply_text("❌ Операцію скасовано.")
        return ConversationHandler.END

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to see statistics"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Ця команда доступна тільки адміністратору.")
            return
        
        # User statistics
        total_users = self.db.get_total_users()
        approved_users = self.db.get_approved_count()
        pending_users = total_users - approved_users
        
        # Message statistics
        total_messages = self.db.get_total_messages()
        messages_week = self.db.get_messages_last_week()
        messages_today = self.db.get_messages_today()
        
        await update.message.reply_text(
            f"📊 Статистика боту:\n\n"
            f"👥 Користувачі:\n"
            f"• Всього: {total_users}\n"
            f"• Підтверджених: {approved_users}\n"
            f"• Очікують: {pending_users}\n\n"
            f"💌 Повідомлення:\n"
            f"• За сьогодні: {messages_today}\n"
            f"• За тиждень: {messages_week}\n"
            f"• Всього: {total_messages}\n\n"
            f"💡 /users - список користувачів\n"
            f"💡 /deleteuser - видалити користувача"
        )

    async def admin_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to see all users with delete buttons"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Ця команда доступна тільки адміністратору.")
            return
        
        all_users = self.db.get_all_users()
        
        if not all_users:
            await update.message.reply_text("📋 Користувачів ще немає.")
            return
        
        # Create list with buttons to delete users
        keyboard = []
        message_text = "👥 Список всіх користувачів:\n\n"
        
        for user in all_users:
            status = "✅" if user['approved'] else "⏳"
            username_text = f"@{user['username']}" if user['username'] else "немає"
            message_text += f"{status} {user['first_name']} {user['last_name']}\n   ID: {user['user_id']} | {username_text}\n\n"
            
            button_text = f"🗑 {user['first_name']} {user['last_name']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_{user['user_id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message_text + "💡 Натисни на користувача щоб видалити:",
            reply_markup=reply_markup
        )

    async def admin_delete_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to delete user - shows list with buttons"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Ця команда доступна тільки адміністратору.")
            return
        
        all_users = self.db.get_all_users()
        
        if not all_users:
            await update.message.reply_text("📋 Користувачів ще немає.")
            return
        
        # Create list with buttons to delete users
        keyboard = []
        message_text = "🗑 Видалення користувачів\n\n"
        message_text += "Натисни на користувача щоб видалити:\n\n"
        
        for user in all_users:
            status = "✅" if user['approved'] else "⏳"
            username_text = f"@{user['username']}" if user['username'] else "немає"
            
            button_text = f"🗑 {user['first_name']} {user['last_name']} ({status})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_{user['user_id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )

    def run(self):
        """Run the bot"""
        logger.info("Starting Taina Poshta Bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")
    
    bot = TainaPoshtaBot(TOKEN)
    bot.run()
