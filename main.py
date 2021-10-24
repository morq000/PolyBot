#!/usr/bin/env python


#############################
# IMPORTS####################
#############################


import logging
import sqlite3
import pytz
import traceback
from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultContact,
	ReplyKeyboardRemove,
    Update,
    ParseMode,
    replykeyboardremove
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackQueryHandler,
    CallbackContext,
    PicklePersistence
)
from telegram.replymarkup import ReplyMarkup

from config import *
from google_drive_connector import *

#######################################
# LOGGING SETTINGS#####################
#######################################


def enable_logging(level=logging.INFO):
    """Enable logging"""
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=level)
    return logging.getLogger(__name__)

#######################################
# DATABASE INTERACTION#################
#######################################


def db_creation(db_file=DB_FILE):
    # TODO создание таблицы базы данных. Продумать структуру БД. add successful and not successful returns

    """Create DB for storing tasks"""
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS users '
        '('
        'user_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, username TEXT, is_bot TEXT, contact_time TEXT'
        ')'
    )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS applications '
        '('
        'application_id INTEGER PRIMARY KEY, creation_time TEXT NOT NULL, '
        'user_id INTEGER NOT NULL, first_name TEXT, last_name TEXT, interested_in TEXT, '
        'contact TEXT NOT NULL, application_status TEXT NOT NULL, subscribed TEXT, feedback TEXT'
        ')'
    )
    db.commit()


def add_client(user_id, first_name, last_name, username, is_bot, contact_time, db_file=DB_FILE):
    # TODO add successful and not successful returns
    """Add new client right after person pressed start button"""
    db = sqlite3.connect(db_file)
    cursor = db.cursor()

    # Check if this user is already in the database
    cursor.execute("""SELECT * FROM users WHERE user_id=?""", [user_id])

    # Add new user if this user id is not in the database
    if not cursor.fetchall():
        cursor.execute("""INSERT INTO users VALUES (?,?,?,?,?,?)""", [user_id, first_name, last_name, username, is_bot, contact_time])
        db.commit()

        logger.info(f'В базу данных добавлен новый пользователь {str([user_id, first_name, last_name, username])}, является ботом: {str(is_bot)}')


def add_new_application_to_DB(application_id, creation_time, user_id, first_name, last_name, interested_in,
                        contact, application_status, subscribed, feedback, db_file=DB_FILE):
    # TODO add successful and not successful returns
    """Add request for a new student or request to contact administrator"""

    new_application = [application_id, creation_time, user_id, first_name, last_name, interested_in, contact,
                       application_status, subscribed, feedback]
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    cursor.execute("""INSERT INTO applications VALUES (?,?,?,?,?,?,?,?,?,?)""", new_application)
    db.commit()

    # Log that the user has been added
    logger.info('New application added to the DB. Application ID: '+str(new_application[0]))



def change_application_status(application_id, application_status, feedback, subscribed='нет', db_file=DB_FILE) -> None:
    # TODO add successful and not successful returns
    """ Function for changing the application status (3 options: green=new, yellow=waiting, red=closed)"""

    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    cursor.execute("""UPDATE applications SET application_status=? subscribed=? feedback=? WHERE application_id=?""",
                   [application_status, subscribed, feedback, application_id])
    db.commit()


def get_applications(application_status=None, db_file=DB_FILE) -> list:
    # Todo add func to output current requests
    """Output the list of all requests. Status can be chosen: green, yellow, red or all of them"""

    db = sqlite3.connect(db_file)
    cursor = db.cursor()

    # Different SQL queries for getting applications with different status

    if not application_status:
        cursor.execute("""SELECT * FROM applications""")
    else:
        cursor.execute("""SELECT * FROM applications WHERE application_status=?""", [application_status])

    return cursor.fetchall()

######################################
# Helper classes #####################
######################################

# class ClientApplication:
#     """"Hepler class to make client application fields standard"""

    

#     def __init__() -> None:
#         pass

######################################
# MAIN BOT CLASS #####################
######################################


class PolyBot:
    """Main class that contains command handlers"""

    def __init__(self, token: str, roles: dict):

        # Bot token and user role settings
        self.token = token
        self.roles = roles

        # Making the bot persistent
        self.persistence = PicklePersistence(filename='polybot')

        # Create updater object and pass the bot token
        self.updater = Updater(token=self.token, persistence=self.persistence)

        # Create dispatcher object
        self.dispatcher = self.updater.dispatcher


        ##################################################
        # Constants for state definitions and callback patterns
        ##################################################


        self.MAIN_MENU, self.CLASSES, self.EVENTS, self.ROOM_RENT, self.BUY_OR_RENT_INSTRUMENTS, \
        self.PARTNERSHIP, self.CONTACT, self.FIND_US, self.START_OVER = map(chr, range(9))

        self.INDIVIDUAL_CLASSES, self.GROUP_CLASSES, self.CHILDREN_CLASSES, self.ONLINE_CLASSES, self.CLASS_TYPES, self.SHOWING = map(chr, range(50, 56))

        # State definitions for third and deeper levels of conversation about classes
        self.SELECT_AGE, self.SELECT_CALL_TIME, self.GO_BACK, self.GO_BACK_TO_GROUP = map(chr, range(100, 104))

        # Constants for types of classes
        self.INDIVIDUAL_SUBSCRIBE, self.GROUP_SUBSCRIBE, self.ONLINE_SUBSCRIBE, self.CHILDREN_SUBSCRIBE = ['индивидуальные', 'групповые', 'онлайн', 'для детей']

        # State definitions for data gathering conversation
        self.GATHER_USER_INFO, self.CHOOSE_INSTRUMENT, self.ENTER_AGE, self.LEAVE_CONTACT, self.BYEBYE, self.TALK_IN_TELEGRAM = map(chr, range(150, 156))

        # Musical instrument callback constants

        # Group of callback constants for individual classes
        self.GUITAR, self.VOCAL, self.PIANO, self.DRUMSET, self.FLUTE, self.ETHNIC, self.UKULELE, \
        self.ANOTHER_INSTRUMENT, self.FRAME_DRUMS, self.HANG, self.MUSIC_THEORY, self.DIDGE_VARGAN = \
            [
                'гитара', 'вокал', 'фоно/клавишные', 'ударная установка', 'флейта', 'этнические барабаны', 'укулеле',
             'другой инструмент', 'рамочные барабаны', 'ханг/равваст/глюкофон', 'теория музыки', 'диджериду/варган'
            ]

        # Group of callback constants for group classes
        self.ETHNIC_GROUP, self.FRAME_DRUMS_GROUP, self.HANG_GROUP, self.DRUMSET_GROUP, self.COMPOSERSHIP_GROUP, \
        self.OPENING_VOICE_GROUP, self.DIDGE_VARGAN_GROUP = \
            [
                'этнич. барабаны группа', 'рамочные барабаны группа', 'ханг/рав/глюк. группа', 'ударная уст. группа',
                'композ. мастер. группа', 'раскрытие голоса', 'дидж/варган группа'
            ]

        # Callback constants for children classes
        self.FASOLKA, self.CHILDREN_ENSEMBLE = [
            'ран. развитие, фасолька', 'дет. ансамбль'
        ]

        # Constants for text on buttons
        self.GUITAR_BUTTON_TEXT, self.VOCAL_BUTTON_TEXT, self.PIANO_BUTTON_TEXT, self.DRUMSET_BUTTON_TEXT, \
        self.FLUTE_BUTTON_TEXT, self.ETHNIC_BUTTON_TEXT, self.UKULELE_BUTTON_TEXT, self.ANOTHER_INSTRUMENT_BUTTON_TEXT, \
        self.FRAME_DRUMS_BUTTON_TEXT, self.HANG_BUTTON_TEXT, self.MUSIC_THEORY_BUTTON_TEXT, self.DIDGE_VARGAN_BUTTON_TEXT,\
        self.COMPOSERSHIP_BUTTON_TEXT, self.OPENING_VOICE_BUTTON_TEXT, self.FASOLKA_BUTTON_TEXT, self.CHILDREN_ENSEMBLE_BUTTON_TEXT = \
            ['Гитара (акустическая, классическая, электрогитара)', 'Вокал (эстрадный, академический)',
             'Фортепиано / Синтезатор', 'Ударная установка', 'Флейта (классическая поперечная, блок-флейта)',
             'Этнические барабаны (джембе, дарбука, кахон, конги)', 'Укулеле (гавайская гитара)',
             'Другой инструмент', 'Рамочные барабаны (бубен, тар, бендир)', 'Ханг (хэндпан), Равваст, Глюкофон',
             'Теория музыки. Сольфеджио', 'Диджериду, варган', 'Композиторское мастерство, развитие слуха',
             'Раскрытие голоса для взрослых (18+)', 'Раннее музыкальное развитие. Группа "Фасолька" (3-4, 4-5 и 5-6 лет)',
             'Детский вокальный ансамбль (6+)']

        # Callback constants for new applications not about classes (instrument rent, partnership etc.)
        self.APPLICATION_INSTRUMENT_RENT, self.APPLICATION_ROOM_RENT, self.APPLICATION_PARTNERSHIP, self.APPLICATION_CONTACT_US =\
            ['покупка или аренда инструмента', 'аренда помещения', 'сотрудничество', 'свяжитесь со мной']

        # Constants with text descriptions
        self.LESSONS_MAIN_TEXT = 'Основной принцип нашего обучения — КАЖДЫЙ может научиться. Всё, что необходимо от вас — это желание.' \
               '\nОбучение строится при индивидуальном подходе, исходя из Ваших особенностей и музыкальных предпочтений.' \
               '\n\nСтоимость индивидуальных занятий (60 минут):' \
               '\n- Абонемент на 8 занятий = 4500 р.;\n- Абонемент на 4 занятия = 2400 р;\n- 1 занятие = 650 р.'

        # Constants for admin menu states and callbacks

        self.EDIT_APPLICATION, self.SHOW_USERS, self.SHOW_APPLICATIONS, self.MAKE_MASS_MESSAGE = map(chr, range(200, 204))
        self.USER_LIST, self.APPLICATION_LIST, self.ADMIN_MENU = map(chr, range(250, 253))

        # Shortcut for conversation handler
        self.END = ConversationHandler.END


        ##################################################
        # Conversation handlers
        ##################################################

        self.gather_data_handler = ConversationHandler(
            entry_points=[
                # TODO add "leave a comment" question. Can be skipped. Then return to main menu.

                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.GUITAR),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.VOCAL),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.FLUTE),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.UKULELE),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.DRUMSET),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.ETHNIC),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.PIANO),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.FRAME_DRUMS),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.MUSIC_THEORY),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.HANG),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.ANOTHER_INSTRUMENT),

                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.ETHNIC_GROUP),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.FRAME_DRUMS_GROUP),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.DRUMSET_GROUP),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.DIDGE_VARGAN_GROUP),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.HANG_GROUP),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.COMPOSERSHIP_GROUP),
                CallbackQueryHandler(callback=self.gather_user_info, pattern=self.OPENING_VOICE_GROUP),

                # CallbackQueryHandler(
                #     callback=self.choose_instrument, pattern=self.GROUP_SUBSCRIBE
                # ),
                # CallbackQueryHandler(
                #     callback=self.choose_instrument, pattern=self.ONLINE_SUBSCRIBE
                # ),
                # CallbackQueryHandler(
                #     callback=self.choose_instrument, pattern=self.CHILDREN_SUBSCRIBE
                # ),
                CallbackQueryHandler(
                    callback=self.gather_user_info, pattern=self.APPLICATION_CONTACT_US,
                ),
                CallbackQueryHandler(
                    callback=self.gather_user_info, pattern=self.APPLICATION_ROOM_RENT,
                ),
                CallbackQueryHandler(
                    callback=self.gather_user_info, pattern=self.APPLICATION_INSTRUMENT_RENT,
                ),
                CallbackQueryHandler(
                    callback=self.gather_user_info, pattern=self.APPLICATION_PARTNERSHIP,
                ),
            ],
            states={
                self.GATHER_USER_INFO: [

                ],
                self.LEAVE_CONTACT: [
                    MessageHandler(Filters.text, self.leave_contact),
                ],
                self.BYEBYE: [
                    MessageHandler(Filters.regex(r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'), self.byebye),
                    CallbackQueryHandler(callback=self.byebye, pattern=self.TALK_IN_TELEGRAM),
                    MessageHandler(Filters.all, self.input_unrecognized)
                ],

            },
            fallbacks=[
				CommandHandler('stop', self.stop),
            ],
            map_to_parent={

            }
        )

        # self.classes_handler = ConversationHandler(
        #     entry_points=[
                
        #     ],
        #     states={
        #         self.CLASS_TYPES: [
        #             ],
                
                

        #     },
        #     fallbacks=[
        #         CommandHandler('stop', self.stop)
        #     ],
        #     map_to_parent={
        #         self.MAIN_MENU: self.MAIN_MENU
        #     }
        # )

        # Main conversation handler
        self.conversation_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', self.start),
                ],
            states={
                self.MAIN_MENU: [
                    # Nested conversation handlers
                    self.gather_data_handler,

                    # Set of main menu button handlers
					CallbackQueryHandler(
                    	callback=self.classes, pattern=self.CLASSES
                	),
                    CallbackQueryHandler(
                        callback=self.instrument_rent, pattern=self.BUY_OR_RENT_INSTRUMENTS
                    ),
                    CallbackQueryHandler(
                        callback=self.room_rent, pattern=self.ROOM_RENT
                    ),
                    CallbackQueryHandler(
                        callback=self.partnership, pattern=self.PARTNERSHIP
                    ),
                    CallbackQueryHandler(
                        callback=self.find_us, pattern=self.FIND_US
                    ),
                    CallbackQueryHandler(
                        callback=self.contact, pattern=self.CONTACT
                    ),
                    CallbackQueryHandler(
                        callback=self.start, pattern=self.START_OVER
                    ),
                    CallbackQueryHandler(
                        callback=self.events, pattern=self.EVENTS
                    ),
                    CommandHandler('start', self.start),
                ],
                self.CLASS_TYPES: [               
					CallbackQueryHandler(
						callback=self.individual_classes, pattern=self.INDIVIDUAL_CLASSES
						),
                    CallbackQueryHandler(
						callback=self.group_classes, pattern=self.GROUP_CLASSES
						),
                    CallbackQueryHandler(
						callback=self.children_classes, pattern=self.CHILDREN_CLASSES
						),
                    CallbackQueryHandler(
						callback=self.online_classes, pattern=self.ONLINE_CLASSES
						),
                    CallbackQueryHandler(
						callback=self.back_to_main, pattern=self.MAIN_MENU
						),                
                ],
				self.CHOOSE_INSTRUMENT: [
                    # Individual classes handlers
                    CallbackQueryHandler(
						callback=self.guitar, pattern=self.GUITAR
						),
                    CallbackQueryHandler(
						callback=self.ukulele, pattern=self.UKULELE
						),
                    CallbackQueryHandler(
						callback=self.vocal, pattern=self.VOCAL
						),
                    CallbackQueryHandler(
						callback=self.drumset, pattern=self.DRUMSET
						),
                    CallbackQueryHandler(
						callback=self.ethnic, pattern=self.ETHNIC
						),
                    CallbackQueryHandler(
						callback=self.frame_drums, pattern=self.FRAME_DRUMS
						),
                    CallbackQueryHandler(
						callback=self.piano, pattern=self.PIANO
						),
                    CallbackQueryHandler(
						callback=self.music_theory, pattern=self.MUSIC_THEORY),
                    CallbackQueryHandler(
						callback=self.hang, pattern=self.HANG
						),
                    CallbackQueryHandler(
						callback=self.flute, pattern=self.FLUTE
						),

                    # Group classes handlers
                    CallbackQueryHandler(
						callback=self.ethnic_group, pattern=self.ETHNIC_GROUP
						),
                    CallbackQueryHandler(
						callback=self.frame_group, pattern=self.FRAME_DRUMS_GROUP
						),
                    CallbackQueryHandler(
						callback=self.drumset_group, pattern=self.DRUMSET_GROUP
						),
                    CallbackQueryHandler(
						callback=self.composership_group, pattern=self.COMPOSERSHIP_GROUP
						),
                    CallbackQueryHandler(
						callback=self.opening_voice_group, pattern=self.OPENING_VOICE_GROUP
						),
                    CallbackQueryHandler(
						callback=self.didge_vargan_group, pattern=self.DIDGE_VARGAN_GROUP
						),
                    CallbackQueryHandler(
						callback=self.hang_group, pattern=self.HANG_GROUP
						),
                    CallbackQueryHandler(
						callback=self.classes, pattern=self.CLASSES
						),
                ],
				self.SHOWING: [
                    self.gather_data_handler,
                    CallbackQueryHandler(callback=self.individual_classes, pattern=self.GO_BACK),
                    CallbackQueryHandler(callback=self.group_classes, pattern=self.GO_BACK_TO_GROUP)
                ]
            },
            fallbacks=[
                CommandHandler('stop', self.stop),
            ]
        )

        ###################################################
        # Admin menu conversation
        ###################################################

        self.admin_handler = ConversationHandler(
            entry_points=[
                CommandHandler('admin', self.show_admin_menu)
            ],
            states={
                self.ADMIN_MENU: [
                    CallbackQueryHandler(callback=self.output_applications, pattern=self.SHOW_APPLICATIONS),
                    CallbackQueryHandler(callback=self.output_users, pattern=self.SHOW_USERS),

                ],
                self.APPLICATION_LIST: [
                    CallbackQueryHandler(callback=self.show_admin_menu, pattern=self.ADMIN_MENU),
                    #CallbackQueryHandler(callback=self.edit_application, pattern=(r'/ \d+ /')),
                    CallbackQueryHandler(callback=self.edit_application, pattern=Filters.text),
               
                ],
                self.USER_LIST: [

                ],
                self.MAKE_MASS_MESSAGE: [

                ],
            },
            fallbacks=[
                CommandHandler('admin', self.show_admin_menu)
            ]
        )

        ###################################################
        # Adding handlers to the dispatcher
        ###################################################

        self.dispatcher.add_handler(self.conversation_handler)
        self.dispatcher.add_handler(self.admin_handler)
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('add_admin', self.add_admin_handler))

        ###################################################
        # Start listening to the updates
        ###################################################

        self.updater.start_polling()
        self.updater.idle()


    ########################################
    # Meta handlers ########################
    ########################################

    def stop(self, update: Update, context: CallbackContext) -> int:
        """End Conversation by command."""
        update.message.reply_text(text=f'Рад был пообщаться с вами.\nДо новых встреч!')

        return self.END

    def end(self, update: Update, context: CallbackContext) -> int:
        """End conversation from InlineKeyboardButton."""
        update.callback_query.answer()

        text = f'Рад был пообщаться с вами.\nДо новых встреч!'
        update.callback_query.edit_message_text(text=text)

        return self.END

    def cancel(self, update: Update, context: CallbackContext) -> None:
        pass

    ########################################
    # Little Santa's Helpers ###############
    ########################################

    def prettify_application_output(self, application: list) -> str:
        """Helper function to make pretty text output for user application"""

        status = application[7]
        if status == 'открытая':
            status = status + u'\U0001F34F'
        elif status == 'ожидает':
            status = status + u'\U0001F34B'
        elif status == 'закрытая':
            status = status + u'\U0001F345'

        text = f'<b>Время:</b>  %s\n' \
               f'<b>Имя и фамилия:</b>  %s %s\n' \
               f'<b>Запрос:</b>  %s\n' \
               f'<b>Контактные данные:</b>  %s\n' \
               f'<b>Статус заявки:</b>  %s\n' \
               f'<b>Ученик записался на занятие:</b>  %s\n' \
               f'<b>Комментарий:</b>  %s\n' \
               % (str(application[1]), str(application[3]),
                  str(application[4]), str(application[5]), str(application[6]),
                  str(status), str(application[8]), str(application[9]))

        return text

    def timezone_converter(self, time: datetime) -> datetime:
        """Converts UTC datetime object to Moscow timezone"""
        return time.astimezone(pytz.timezone('Europe/Moscow'))


    ########################################
    # DB Handlers ##########################
    ########################################

    

    def output_users(self, update: Update, context: CallbackContext) -> str:
        """Command handler to get the list of users"""

        if update.callback_query:
            update.callback_query.answer()

        db = sqlite3.connect(DB_FILE)
        cursor = db.cursor()
        cursor.execute("""SELECT * FROM users""")
        users = cursor.fetchall()
        update.effective_user.send_message(text=str(users))

        return self.USER_LIST

    ########################################
    # Admin menu handlers
    ########################################

    def show_admin_menu(self, update: Update, context: CallbackContext) -> str:
        """Entry point of Admin conversation handler. Show admin menu buttons after /admin command is issued"""
        if update.callback_query:
            update.callback_query.answer()

        # Print admin menu only if this username is in the Admin list.
        # Add admin chat_id to Admin chat list if it's not present there

        if str(update.effective_user.username) in ROLES['ADMINS']:

            # When user logs in as admin we check if his chat_id is in the Admin chat list and add if not.
            if update.effective_chat.id not in ADMIN_CHAT_IDS:
                ADMIN_CHAT_IDS.append(update.effective_chat.id)

            buttons = [
                [InlineKeyboardButton(text='Входящие заявки', callback_data=self.SHOW_APPLICATIONS)],
                [InlineKeyboardButton(text='База клиентов', callback_data=self.SHOW_USERS)],
                [InlineKeyboardButton(text='Рассылка сообщений', callback_data=self.MAKE_MASS_MESSAGE)],
                       ]
            keyboard = InlineKeyboardMarkup(buttons)

            if update.callback_query:
                update.callback_query.edit_message_text(text='<b>Меню администратора</b>', parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                update.effective_user.send_message(text='<b>Меню администратора</b>', parse_mode=ParseMode.HTML, reply_markup=keyboard)

            return self.ADMIN_MENU
        else:
            update.effective_user.send_message('Мои инструкции говорят, что вам сюда не нужно ' + u'\U0001F916')

    def output_applications(self, update: Update, context: CallbackContext) -> object:
        # TODO make callback for working with an application as an object
        """Command handler to get the list of applications"""

        
        update.callback_query.answer()
        update.callback_query.edit_message_text("---Входящие заявки---")

        # Check if specific type of application status is provided. Then connect to DB to get the list of applications.
        if context.args:
            application_status = context.args[0]
            applications = get_applications(application_status)
        else:
            applications = get_applications()

        # Output each application with a button to handle it
        for application in applications:
            text = self.prettify_application_output(application)
            # buttons = [
            #     [
            #         InlineKeyboardButton(text='Открыть заявку', callback_data=application[0])
            #     ],
            # ]
            # keyboard = InlineKeyboardMarkup(buttons)
            update.effective_user.send_message(text=text, parse_mode=ParseMode.HTML)

        # Add GO BACK button at the end
        buttons = [
                [
                    InlineKeyboardButton(text='Назад в меню', callback_data=self.ADMIN_MENU)
                ],
            ]
        keyboard = InlineKeyboardMarkup(buttons)
        update.effective_user.send_message("---Конец списка заявок---", reply_markup=keyboard)

        return self.APPLICATION_LIST

    def edit_application(self, update: Update, context: CallbackContext) -> str:
        """Shows Application edit menu after admin clicks the Edit button"""
        
        update.callback_query.answer()

        app_id = update.callback_query.data

        buttons = [
            InlineKeyboardButton(text="123", callback_data="321")
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        update.callback_query.edit_message_text('Жопа')

        return self.ADMIN_MENU

    def add_admin_handler(self, update: Update, context: CallbackContext):
        pass

    ########################################
    # Upper level handlers
    ########################################

    def start(self, update: Update, context: CallbackContext) -> str:
        """Entry point to the conversation.
        Greeting the user when /start command is issued.
        Outputting the main menu"""

        # Adding client to the database
        add_client(update.effective_user.id, update.effective_user.first_name, update.effective_user.last_name,
                   update.effective_user.username, update.effective_user.is_bot, update.effective_message.date)

        # Answer callback query if we go back to main menu from inline buttons
        if update.callback_query:
            update.callback_query.answer()

        buttons = [
            [
                InlineKeyboardButton(text=u'\U0001F3B9'+' Обучение игре на инструментах', callback_data=self.CLASSES),
            ],
            [
                InlineKeyboardButton(text=u'\U0001F3B8'+u'\U0001F4B0'+' Покупка и аренда инструментов',
                                     callback_data=self.BUY_OR_RENT_INSTRUMENTS),
            ],
            [
                InlineKeyboardButton(text=u'\U0001F483' + ' Концерты и мероприятия '+u'\U0001F57A',
                                     callback_data=self.EVENTS),
            ],
            [
                InlineKeyboardButton(text=u'\U0001F3DB'+' Аренда зала', callback_data=self.ROOM_RENT),
                InlineKeyboardButton(text=u'\U0001F91D'+' Сотрудничество', callback_data=self.PARTNERSHIP),
            ],
            [
                InlineKeyboardButton(text=u'\U0001F310'+' Как нас найти', callback_data=self.FIND_US),
                InlineKeyboardButton(text=u'\U0000270F'+' Связаться с нами', callback_data=self.CONTACT),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        text = "Выберите интересующую вас тему"

        if update.callback_query:
            update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
        else:
            update.message.reply_text(text=text, reply_markup=keyboard)

        return self.MAIN_MENU

    def classes(self, update: Update, context: CallbackContext) -> str:
        """Callback function that prints the keyboard with the list of available classes"""

        # Answer previous callback query
        update.callback_query.answer()

        buttons = [
            [
                InlineKeyboardButton(text=u'\U0001F3B5'+' Индивидуальные занятия', callback_data=self.INDIVIDUAL_CLASSES),
            ],
            [
                InlineKeyboardButton(text=u'\U0001F3B6'+' Групповые занятия', callback_data=self.GROUP_CLASSES),
            ],
            [
                InlineKeyboardButton(text=u'\U0001F476'+' Занятия для детей', callback_data=self.CHILDREN_CLASSES),
            ],
            [
                InlineKeyboardButton(text=u'\U0001F4BB'+' Онлайн-занятия', callback_data=self.ONLINE_CLASSES),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+' Назад в главное меню', callback_data=self.MAIN_MENU),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        #update.effective_chat.send_photo(photo=open('logo.jpg', 'rb'))
        update.callback_query.edit_message_text(text='Какое направление обучения вас интересует?', reply_markup=keyboard)

        return self.CLASS_TYPES

    def events(self, update: Update, context: CallbackContext) -> str:
        """"Command handler that print information about upcoming events"""
        update.callback_query.answer()

        buttons = [
                [
                    InlineKeyboardButton(text=u'\U00002934'+' Назад в главное меню', callback_data=self.START_OVER),
                ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        update.callback_query.edit_message_text(
            text=f'Подгрузка инфы о предстоящих концертах, а также описание доступных мероприятий:\n'
                 f'\n- Выездные музыкальные семинары и интенсивы'
                 f'\n- Музыкальные дни рождения'
                 f'\n- Чайные церемонии'
                 f'\n- Киноклуб'
                 f'\n- Барабанный круг'
                 f'\n- Свободная импровизация'
                 f'\n- Твоя сцена'
                 f'\n- Музыкальные тренинги'
                 f'\n- Мастер-классы'
                 f'\n- Музыкотерапия', reply_markup=keyboard)

        return self.MAIN_MENU

    def room_rent(self, update: Update, context: CallbackContext) -> str:
        """Callback function that prints room rent options"""
        update.callback_query.answer()

        buttons = [
            [
                InlineKeyboardButton(text='Оставить заявку', callback_data=self.APPLICATION_ROOM_RENT),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+' Назад в главное меню', callback_data=self.START_OVER),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        text = 'У вас есть интересная идея и вам нужно помещение для ее реализации? ' \
               'Студии «Полиритм» есть что вам предложить!\n\nНа нашей площадке можно организовать:' \
               '\n- камерные концерты;\n- конференции;\n- мастер-классы, интенсивы, занятия, ретриты;' \
               '\n- творческие встречи;\n- спектакли;\n- детские и взрослые творческие дни рождения.' \
               '\n\nОборудование:\n- современный проектор;\n- мощная звуковая аппаратура;' \
               '\n- столы, стулья, магнитная доска, канцелярия;\n- большое зеркало.'

        update.callback_query.edit_message_text(
            text=text, reply_markup=keyboard)

        return self.MAIN_MENU

    def instrument_rent(self, update: Update, context: CallbackContext) -> str:
        """Callback function that prints instrument rent options"""
        update.callback_query.answer()

        buttons = [
            [
                InlineKeyboardButton(text='Оставить заявку', callback_data=self.APPLICATION_INSTRUMENT_RENT),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Назад в главное меню', callback_data=self.START_OVER),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        update.callback_query.edit_message_text(
            text=f'Вы можете купить или арендовать такие-то инструменты на такие-то условиях.\n Фото, список, что-то еще.', reply_markup=keyboard)

        return self.MAIN_MENU

    def partnership(self, update: Update, context: CallbackContext) -> str:
        update.callback_query.answer()

        buttons = [
            [
                InlineKeyboardButton(text='Оставить заявку', callback_data=self.APPLICATION_PARTNERSHIP),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Назад в главное меню', callback_data=self.START_OVER),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        text = 'Студия «Полиритм» открыта для сотрудничества и всегда поддерживает интересные идеи!' \
               '\n\nНа нашей площадке можно:\n- Проводить лекции и мастер-классы (как музыкальные, так и по другим видам искусств)' \
               '\n- Организовывать концерты и творческие встречи\n- Играть камерные спектакли\n- Проводить интерактивные занятия' \
               '\n- Организовывать просмотр фильмов и видеороликов' \
               '\n\nНа нашей сцене уже звучали концерты и выступления таких коллективов и музыкантов, ' \
               'как этнопроект «Миндаль», сказитель былин Александр Маточкин, дуэт «Пау Вау» (сантур и хэндпан), ' \
               'Аврора и Tomato Blues, Паша Аеон (хэндпан) и многие другие!' \
               '\nА также проводились мастер-классы по перкуссии от Данилы Прокопьева («Маркшейдер Кунст»), ' \
               'Йоэля Гонсалеса и других замечательных мастеров.'

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.MAIN_MENU

    def find_us(self, update: Update, context: CallbackContext) -> str:
        update.callback_query.answer()

        buttons = [
            [
                InlineKeyboardButton(text=u'\U00002934'+'Назад в главное меню', callback_data=self.START_OVER),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        text = 'Наш адрес:\nг. Псков, ул. Школьная, дом 4 (2-й этаж), школа музыки "Полиритм".' \
               '\n\nЕсли калитка закрыта, вход через большие серые ворота со шлагбаумом.' \
               '\n\nКарта:\n\nhttps://bit.ly/3x8ZIKM'
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.MAIN_MENU

    def contact(self, update: Update, context: CallbackContext) -> str:
        update.callback_query.answer()

        buttons = [
            [
                InlineKeyboardButton(text='Отправьте нам сообщение!', callback_data=self.APPLICATION_CONTACT_US),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Назад в главное меню', callback_data=self.START_OVER),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        update.callback_query.edit_message_text(text='Хотите задать нам вопрос или поделиться мнением? ', reply_markup=keyboard)

        return self.MAIN_MENU

    ###########################################################
    # Group of individual music classes description handlers
    ###########################################################

    def individual_classes(self, update: Update, context: CallbackContext) -> str:
        """"Handler for submenu level 1 Individual classes"""

        update.callback_query.answer()

        text = 'Выберите интересующий вас инструмент:'

        buttons = [
            [
                InlineKeyboardButton(text=self.GUITAR_BUTTON_TEXT, callback_data=self.GUITAR),
            ],
            [
                InlineKeyboardButton(text=self.UKULELE_BUTTON_TEXT, callback_data=self.UKULELE),
            ],
            [
                InlineKeyboardButton(text=self.ETHNIC_BUTTON_TEXT, callback_data=self.ETHNIC),
            ],
            [
                InlineKeyboardButton(text=self.FRAME_DRUMS_BUTTON_TEXT, callback_data=self.FRAME_DRUMS),
            ],
            [
                InlineKeyboardButton(text=self.HANG_BUTTON_TEXT, callback_data=self.HANG),
            ],
            [
                InlineKeyboardButton(text=self.FLUTE_BUTTON_TEXT, callback_data=self.FLUTE),
            ],
            [
                InlineKeyboardButton(text=self.PIANO_BUTTON_TEXT, callback_data=self.PIANO),
            ],
            [
                InlineKeyboardButton(text=self.VOCAL_BUTTON_TEXT, callback_data=self.VOCAL),
            ],
            [
                InlineKeyboardButton(text=self.DRUMSET_BUTTON_TEXT, callback_data=self.DRUMSET),
            ],
            [
                InlineKeyboardButton(text=self.MUSIC_THEORY_BUTTON_TEXT, callback_data=self.MUSIC_THEORY),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Назад', callback_data=self.CLASSES),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.CHOOSE_INSTRUMENT

    def guitar(self, update: Update, context: CallbackContext):
        """Prints info page about individual guitar classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT
        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.GUITAR)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def ukulele(self, update: Update, context: CallbackContext):
        """Prints info page about individual ukulele classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.UKULELE)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def vocal(self, update: Update, context: CallbackContext):
        """Prints info page about individual vocal classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.VOCAL)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def drumset(self, update: Update, context: CallbackContext):
        """Prints info page about individual drumming classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.DRUMSET)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def ethnic(self, update: Update, context: CallbackContext):
        """Prints info page about individual ethnic drum classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT
        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.ETHNIC)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def frame_drums(self, update: Update, context: CallbackContext):
        """Prints info page about individual frame drum classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.FRAME_DRUMS)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def piano(self, update: Update, context: CallbackContext):
        """Prints info page about individual piano classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.PIANO)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def music_theory(self, update: Update, context: CallbackContext):
        """Prints info page about individual music theory classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.MUSIC_THEORY)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def hang(self, update: Update, context: CallbackContext):
        """Prints info page about individual hang classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT
        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.HANG)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def flute(self, update: Update, context: CallbackContext):
        """Prints info page about individual flute classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.FLUTE)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    ############################################
    # Group of Group Music Classes handlers ####
    ############################################

    def group_classes(self, update: Update, context: CallbackContext) -> str:
        """"""
        update.callback_query.answer()

        text = 'Какое направление обучения вас интересует?'
        buttons = [
            [
                InlineKeyboardButton(text=self.ETHNIC_BUTTON_TEXT, callback_data=self.ETHNIC_GROUP)
            ],
            [
                InlineKeyboardButton(text=self.FRAME_DRUMS_BUTTON_TEXT, callback_data=self.FRAME_DRUMS_GROUP)
            ],
            [
                InlineKeyboardButton(text=self.HANG_BUTTON_TEXT, callback_data=self.HANG_GROUP)
            ],
            [
                InlineKeyboardButton(text=self.DRUMSET_BUTTON_TEXT, callback_data=self.DRUMSET_GROUP)
            ],
            [
                InlineKeyboardButton(text=self.DIDGE_VARGAN_BUTTON_TEXT, callback_data=self.DIDGE_VARGAN_GROUP)
            ],
            [
                InlineKeyboardButton(text=self.COMPOSERSHIP_BUTTON_TEXT, callback_data=self.COMPOSERSHIP_GROUP)
            ],
            [
                InlineKeyboardButton(text=self.OPENING_VOICE_BUTTON_TEXT, callback_data=self.OPENING_VOICE_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Вернуться назад', callback_data=self.CLASSES),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.CHOOSE_INSTRUMENT

    def ethnic_group(self, update: Update, context: CallbackContext) -> str:
        """Prints info page about group ethnic drum classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.ETHNIC_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK_TO_GROUP)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def frame_group(self, update: Update, context: CallbackContext) -> str:
        """Prints info page about group frame drum classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.FRAME_DRUMS_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK_TO_GROUP)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def drumset_group(self, update: Update, context: CallbackContext) -> str:
        """Prints info page about group drumset classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.DRUMSET_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK_TO_GROUP)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def composership_group(self, update: Update, context: CallbackContext) -> str:
        """Prints info page about group composership classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.COMPOSERSHIP_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK_TO_GROUP)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def opening_voice_group(self, update: Update, context: CallbackContext) -> str:
        """Prints info page about group opening voice classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.OPENING_VOICE_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK_TO_GROUP)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def didge_vargan_group(self, update: Update, context: CallbackContext) -> str:
        """Prints info page about group didgeridoo and vargan classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.DIDGE_VARGAN_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK_TO_GROUP)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def hang_group(self, update: Update, context: CallbackContext) -> str:
        """Prints info page about group hang and RAV classes and has Subscribe and Go back buttons"""

        update.callback_query.answer()

        text = self.LESSONS_MAIN_TEXT

        buttons = [
            [
                InlineKeyboardButton(text='Записаться на обучение', callback_data=self.HANG_GROUP)
            ],
            [
                InlineKeyboardButton(text=u'\U00002934' + 'Вернуться назад', callback_data=self.GO_BACK_TO_GROUP)
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    #########################################################
    #########################################################

    def online_classes(self, update: Update, context: CallbackContext) -> str:

        update.callback_query.answer()
        text = 'Информация об онлайн-обучении с ценами на обучение'
        buttons = [
            [
                InlineKeyboardButton(text='Хочу записаться на обучение', callback_data=self.ONLINE_SUBSCRIBE),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Назад', callback_data=self.CLASSES),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def children_classes(self, update: Update, context: CallbackContext) -> str:
        update.callback_query.answer()
        buttons = [
            [
                InlineKeyboardButton(text='Хочу записаться на обучение', callback_data=self.CHILDREN_SUBSCRIBE),
            ],
            [
                InlineKeyboardButton(text=u'\U00002934'+'Назад', callback_data=self.CLASSES),
            ],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        text = "Школа музыки «Полиритм» приглашает детей от 3,5 до 6 лет в группу раннего музыкального развития." \
               "\n\nЗанятия проходят в игровой форме:\n- Элементы ритмики/логоритмики" \
               "\n- Упражнения на развитие музыкального слуха и голоса\n- Знакомство с музыкальными инструментами" \
               "\n- Элементы театрализации\n- Прослушивание классической музыки\n- Музыкальные игры" \
               "\n\nМноголетние исследования ученых доказали, что дети, занимающиеся музыкой, опережают сверстников" \
               " в интеллектуальном, психомоторном и социальном развитии. А музыкально-ритмические игры формируют" \
               " у детей способность концентрировать внимание, развивают речь, память, слух," \
               " мышление и другие психические процессы." \
               "\n\nРасписание:\n\nСуббота 10:00 - 10:30 - младшая группа (3,5 - 4 года)" \
               "\n\nСуббота 10:45 - 11:25 - старшая группа (5 - 6 лет)\n\nЗапись на занятия ОБЯЗАТЕЛЬНА!" \
               "\nСтоимость 1 занятия: 300 р.\nСтоимость абонемента на 4 занятия: 1000 р." \
               "\n\n* Пропущенные занятия по абонементу возвращаются только при наличии справки о болезни. " \
               "О пропуске занятия просим предупреждать преподавателя за сутки."

        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

        return self.SHOWING

    def back_to_main(self, update: Update, context: CallbackContext) -> str:

        update.callback_query.answer()
        self.start(update, context)
        return self.MAIN_MENU

    ##################################################################
    # Handlers that gather user info after Subscribe button is clicked
    ##################################################################

    def gather_user_info(self, update: Update, context: CallbackContext) -> str:
        # Ask for user name and save previous callback result(type of request or musical instrument)

        update.callback_query.answer()
        context.user_data['interested_in'] = update.callback_query.data

        # # Check if callback came from non-classes section. In this case field context.user_data['type_of_classes'] is not needed
        # if update.callback_query.data in [self.APPLICATION_PARTNERSHIP, self.APPLICATION_INSTRUMENT_RENT, self.APPLICATION_ROOM_RENT, self.APPLICATION_CONTACT_US]:
        #     context.user_data['type_of_classes'] = 'Отсутствует'

        update.callback_query.edit_message_text(text='Пожалуйста, введите ваше имя:')

        return self.LEAVE_CONTACT

    # def choose_instrument(self, update: Update, context: CallbackContext) -> str:
    #     # Print the menu for choosing instrument after user presses "Subscribe" button
    #
    #     update.callback_query.answer()
    #     context.user_data['type_of_classes'] = update.callback_query.data
    #
    #     # If user have chosen children classes we don't need to choose the instrument
    #     if context.user_data['type_of_classes'] == self.CHILDREN_SUBSCRIBE:
    #         return self.gather_user_info(update, context)
    #
    #     # Keyboard for choosing musical instrument that user is interested in
    #     buttons = [
    #         [
    #             InlineKeyboardButton(text='Гитара', callback_data=self.GUITAR)
    #         ],
    #         [
    #             InlineKeyboardButton(text='Вокал', callback_data=self.VOCAL)
    #         ],
    #         [
    #             InlineKeyboardButton(text='Фортепиано', callback_data=self.PIANO)
    #         ],
    #         [
    #             InlineKeyboardButton(text='Флейта', callback_data=self.FLUTE)
    #         ],
    #         [
    #             InlineKeyboardButton(text='Укулеле', callback_data=self.UKULELE)
    #         ],
    #         [
    #             InlineKeyboardButton(text='Ударная установка', callback_data=self.DRUMSET)
    #         ],
    #         [
    #             InlineKeyboardButton(text='Этнические барабаны', callback_data=self.ETHNIC)
    #         ],
    #         [
    #             InlineKeyboardButton(text='Другой инструмент', callback_data=self.ANOTHER_INSTRUMENT)
    #         ],
    #     ]
    #     text = 'Обучение какому инструменту вас интересует?'
    #     keyboard = InlineKeyboardMarkup(buttons)
    #     update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    #
    #     return self.GATHER_USER_INFO

    def leave_contact(self, update: Update, context: CallbackContext) -> str:
        # This callback asks for user phone number or contact via Telegram chat

        # Check if this field already exixts
        if not('name' in context.user_data):
            context.user_data['name'] = update.message.text

        text = 'Введите телефон в формате +7......... и нажмите Enter.' \
             '\n\nЕсли вам удобнее, чтобы администратор связался с вами в Telegram, нажмите кнопку ниже.'

        buttons = [
            [InlineKeyboardButton(text='Свяжитесь со мной в Telegram', callback_data=self.TALK_IN_TELEGRAM)],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        update.message.reply_text(text=text, reply_markup=keyboard)

        return self.BYEBYE

    def byebye(self, update: Update, context: CallbackContext) -> str:
        """Outputs a goodbye message to user and calls add_new_application() method to add new application to the DB"""

        text = f"Спасибо за ваш запрос, {context.user_data['name']}!\nАдминистратор свяжется с вами в ближайшее время."

        if update.callback_query:
            update.callback_query.answer()
            context.user_data['contact'] = 'https://t.me/' + update.effective_user.username
            update.callback_query.edit_message_text(text=text)
        else:
            context.user_data['contact'] = update.message.text
            update.message.reply_text(text=text)

        
        application = [update.update_id, str(self.timezone_converter(update.effective_message.date)), update.effective_user.id,
                       update.effective_user.first_name, update.effective_user.last_name,
                       context.user_data['interested_in'], context.user_data['contact'], 'открытая', 'нет', '-']
        
        # Add new application to the DB
        add_new_application_to_DB(*application)

        # Add new application to Google sheet
        # Update_Id field not added
        add_application_to_drive(application[1:])

        # Sending new application to admin in new message
        message_text = self.prettify_application_output(application)
        for chat_id in ADMIN_CHAT_IDS:
            context.bot.send_message(chat_id=chat_id, text='Поступила новая заявка: \n\n'+message_text, parse_mode=ParseMode.HTML)

        return self.END

    # Input handler if user input is not recognized

    def input_unrecognized(self, update: Update, context: CallbackContext) -> None:

        text = 'Простите, но я не смог распознать ваше сообщение.\nПожалуйста, попробуйте снова.'
        update.message.reply_text(text=text)

        self.leave_contact(update, context)


#######################################################
# Launching the bot####################################
#######################################################

def main():
    """Start the bot"""
    PolyBot(token=TOKEN, roles=ROLES)


if __name__ == '__main__':
    logger = enable_logging()
    db_creation()
    main()
