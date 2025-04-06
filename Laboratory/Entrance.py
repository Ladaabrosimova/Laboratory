import random
import pymysql
import string
import io
import os
import csv
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QMessageBox, QTableWidgetItem, QLineEdit, QLabel, QPushButton, QDialog, QProgressBar, QHBoxLayout, QWidget)
from PyQt6.QtGui import QPixmap, QImage, QMovie
from PyQt6.QtCore import QTimer
from captcha.image import ImageCaptcha
from вход import Ui_MainWindow
from главное1 import Ui_MainWindow1
from главное2 import Ui_MainWindow2
from главное3 import Ui_MainWindow3
from главное4 import Ui_MainWindow4
from Report import ReportApp
from Order import Order


def connect_to_database():
    """Создает и возвращает соединение с базой данных"""
    return pymysql.connect(
        host="localhost",
        user="root",
        database="laboratory"
    )


class CaptchaDialog(QDialog):
    """Диалог для ввода CAPTCHA."""
    def __init__(self, parent=None, error_message=""):
        super().__init__(parent)
        self.setWindowTitle("Введите CAPTCHA")
        self.captcha_text = ""

        self.error_label = QLabel(error_message, self)
        self.captcha_label = QLabel(self)
        self.captcha_input = QLineEdit(self)
        self.captcha_input.setPlaceholderText("Введите CAPTCHA")

        self.refresh_button = QPushButton("Обновить CAPTCHA", self)
        self.submit_button = QPushButton("OK", self)

        self.refresh_button.clicked.connect(self.generate_captcha)
        self.submit_button.clicked.connect(self.validate_captcha)

        layout = QVBoxLayout()
        layout.addWidget(self.error_label)
        layout.addWidget(self.captcha_label)
        layout.addWidget(self.captcha_input)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

        self.generate_captcha()

    def generate_captcha(self):
        """Генерация CAPTCHA."""
        self.captcha_text = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        image = ImageCaptcha(width=200, height=80)

        io_buffer = io.BytesIO()
        image.write(self.captcha_text, io_buffer, format='png')
        io_buffer.seek(0)

        img = QImage()
        img.loadFromData(io_buffer.read())
        self.captcha_label.setPixmap(QPixmap.fromImage(img))
        print(self.captcha_text)

    def validate_captcha(self):
        """Проверка введенной CAPTCHA."""
        if self.captcha_input.text().strip().lower() == self.captcha_text.lower():
            self.accept()
        else:
            self.reject()


class AuthSystem(QMainWindow):
    """Система аутентификации пользователей."""
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setFixedSize(596, 376)
        self.db_connection = connect_to_database()

        self.failed_attempts = 0
        self.captcha_attempts = 0
        self.block_until = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_block_status)

        self.ui.pushButton.clicked.connect(self.authenticate_user)
        self.ui.pushButton_3.clicked.connect(self.toggle_password_visibility)
        self.ui.lineEdit_2.setEchoMode(QLineEdit.EchoMode.Password)

        self.role_id = None
        self.current_user = None

    def toggle_password_visibility(self):
        """Переключение видимости пароля."""
        if self.ui.lineEdit_2.echoMode() == QLineEdit.EchoMode.Password:
            self.ui.lineEdit_2.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.ui.lineEdit_2.setEchoMode(QLineEdit.EchoMode.Password)

    def update_block_status(self):
        """Обновление статуса блокировки пользователя."""
        if self.block_until and datetime.now() < self.block_until:
            remaining_time = int((self.block_until - datetime.now()).total_seconds())
            self.ui.statusbar.showMessage(f"Вход заблокирован на {remaining_time} секунд.")
        else:
            self.block_until = None
            self.timer.stop()
            self.ui.statusbar.clearMessage()

    def authenticate_user(self):
        """Аутентификация пользователя."""
        if self.block_until and datetime.now() < self.block_until:
            self.update_block_status()
            return

        login = self.ui.lineEdit.text()
        password = self.ui.lineEdit_2.text()

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT password, id_role, lastname, name FROM users WHERE login = %s", (login,))
            user_result = cursor.fetchone()

            if user_result and user_result[0] == password:
                self.role_id = user_result[1]
                self.current_user = (user_result[2], user_result[3])
                cursor.execute("UPDATE users SET lastenter=%s WHERE login=%s",
                               (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), login))
                self.db_connection.commit()
                self.open_role_based_window()
                self.failed_attempts = 0
                self.captcha_attempts = 0
            else:
                self.failed_attempts += 1
                self.show_captcha_dialog()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить запрос: {str(e)}")

    def show_captcha_dialog(self):
        """Отображение окна CAPTCHA."""
        captcha_dialog = CaptchaDialog(self, "Неверные учетные данные. Введите CAPTCHA:")
        if captcha_dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Попробуйте снова", "Попробуйте ввести данные еще раз.")
            self.captcha_attempts = 0
        else:
            self.captcha_attempts += 1
            if self.captcha_attempts >= 3:
                self.block_until = datetime.now() + timedelta(seconds=10)
                self.timer.start(1000)
                QMessageBox.warning(self, "Ошибка", "Вход заблокирован на 10 секунд.")
                return
            QMessageBox.warning(self, "Ошибка", "Неверная CAPTCHA")

    def open_role_based_window(self):
        """Открытие окна на основании роли пользователя."""
        if self.role_id == 1:
            image_name = "laborant_1.jpeg"
            self.laborant_window = LaborantWindow(self.current_user, self.get_image_path(image_name), self)
            self.laborant_window.show()
        elif self.role_id == 2:
            image_name = "Бухгалтер.jpeg"
            self.accountant_window = AccountantWindow(self.current_user, self.get_image_path(image_name), self.db_connection, self)
            self.accountant_window.show()
        elif self.role_id == 3:
            image_name = "laborant_2.png"
            self.specialist_window = SpecialistWindow(self.current_user, self.get_image_path(image_name), self)
            self.specialist_window.show()
        elif self.role_id == 4:
            image_name = "Администратор.png"
            self.admin_window = AdminWindow(self.current_user, self.get_image_path(image_name), self)
            self.admin_window.show()
        self.clear_login_fields()
        self.hide()

    def get_image_path(self, image_name):
        """Получение пути к изображению."""
        return os.path.join(os.getcwd(), "imag", image_name)

    def clear_login_fields(self):
        """Очистка полей ввода логина и пароля."""
        self.ui.lineEdit.clear()
        self.ui.lineEdit_2.clear()


class LaborantWindow(QMainWindow):
    """Окно для лаборанта."""
    def __init__(self, user, image_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(596, 376)
        self.ui = Ui_MainWindow1()
        self.ui.setupUi(self)
        self.ui.label_2.setText(f"{user[0]} {user[1]}")
        self.image_path = image_path
        self.load_user_image(image_path)

        self.ui.pushButton.clicked.connect(self.open_order_window)
        self.ui.pushButton_2.clicked.connect(self.open_reports_window)
        self.ui.pushButton_3.clicked.connect(self.go_to_auth)

    def go_to_auth(self):
        """Возврат к системе аутентификации."""
        self.parent().show()
        self.close()

    def load_user_image(self, image_path):
        """Загрузка изображения пользователя."""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise FileNotFoundError(f"Изображение {image_path} не найдено.")
            self.ui.label.setPixmap(pixmap)
            self.ui.label.setScaledContents(True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить изображение: {e}")

    def open_reports_window(self):
        """Открытие окна отчетов."""
        self.reports_window = ReportApp(
            db_connection=self.parent().db_connection,
            user_text=self.ui.label_2.text(),
            image_path=self.image_path,
            auth_window=self.parent(),
            parent=self
        )
        self.reports_window.show()
        self.hide()

    def open_order_window(self):
        """Открытие окна заказов."""
        self.orders_window = Order(
            db_connection=self.parent().db_connection,
            user_text=self.ui.label_2.text(),
            image_path=self.image_path,
            auth_window=self.parent(),
            parent=self
        )
        self.orders_window.show()
        self.hide()


class AccountantWindow(QMainWindow):
    """Окно бухгалтера"""
    def __init__(self, user, image_path, db_connection, parent=None):
        super().__init__(parent)
        self.setFixedSize(596, 376)
        self.ui = Ui_MainWindow3()
        self.ui.setupUi(self)
        self.ui.label_4.setText(f"{user[0]} {user[1]}")

        self.image_path = image_path
        self.load_user_image(image_path)
        self.load_report_logs()

        self.db_connection = db_connection

        self.ui.pushButton_3.clicked.connect(self.go_to_auth)
        self.ui.pushButton_2.clicked.connect(self.generate_reports)

    def load_user_image(self, image_path):
        """Загрузка изображения пользователя."""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise FileNotFoundError(f"Изображение {image_path} не найдено.")
            self.ui.label_2.setPixmap(pixmap)
            self.ui.label_2.setScaledContents(True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить изображение: {e}")

    def go_to_auth(self):
        """Возврат к системе аутентификации."""
        self.parent().show()
        self.close()

    def load_report_logs(self):
        """Загрузка журналов отчетов из базы данных."""
        try:
            cursor = self.parent().db_connection.cursor()
            cursor.execute("SELECT * FROM report_logs")

            results = cursor.fetchall()

            self.ui.tableWidget.clear()
            self.ui.tableWidget.setRowCount(0)

            self.ui.tableWidget.setColumnCount(4)
            self.ui.tableWidget.setHorizontalHeaderLabels(["ID", "Тип отчета", "Начало периода", "Конец периода"])

            for row_data in results:
                row_position = self.ui.tableWidget.rowCount()
                self.ui.tableWidget.insertRow(row_position)
                for column, data in enumerate(row_data):
                    item = QTableWidgetItem(str(data))
                    self.ui.tableWidget.setItem(row_position, column, item)

            self.ui.tableWidget.setColumnWidth(0, 50)
            self.ui.tableWidget.setColumnWidth(1, 200)
            self.ui.tableWidget.setColumnWidth(2, 120)
            self.ui.tableWidget.setColumnWidth(3, 120)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке данных из БД: {e}")

    def validate_dates(self):
        """Проверка корректности введенных дат"""
        start_date = self.ui.dateEdit.date()
        end_date = self.ui.dateEdit_2.date()

        # Проверка на пустые значения
        if start_date.isNull() or end_date.isNull():
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, введите обе даты")
            return False

        # Преобразование QDate в datetime.date
        start_date_dt = start_date.toPyDate()
        end_date_dt = end_date.toPyDate()

        # Проверка, что начальная дата не позже конечной
        if start_date_dt > end_date_dt:
            QMessageBox.warning(self, "Ошибка", "Дата начала не может быть позже даты окончания")
            return False

        return (start_date_dt, end_date_dt)

    def get_insurance_companies(self):
        """Получение списка страховых компаний из базы данных"""
        cursor = self.db_connection.cursor()
        query = "SELECT id, name FROM insurance_company"
        cursor.execute(query)
        companies = cursor.fetchall()
        cursor.close()
        return companies

    def get_patients_services(self, company_id, start_date, end_date):
        """Получение данных о пациентах и услугах для указанной страховой компании за период"""
        cursor = self.db_connection.cursor()
        query = """
        SELECT 
            p.id as patient_id,
            CONCAT(p.lastname, ' ', p.name, ' ', p.middlename) as patient_name,
            s.id as service_id,
            s.name as service_name,
            s.price as service_price,
            o.date_create as service_date
        FROM 
            orders o
            JOIN biomaterial b ON o.id_biomaterial = b.id
            JOIN patient p ON b.id_patient = p.id
            JOIN ipolicies ip ON ip.id_patient = p.id
            JOIN services s ON o.id_services = s.id
        WHERE 
            ip.id_company = %s
            AND o.date_create BETWEEN %s AND %s
            AND o.approved = 1
        ORDER BY 
            p.lastname, p.name, p.middlename, o.date_create
        """

        cursor.execute(query, (company_id, start_date, end_date))
        data = cursor.fetchall()
        cursor.close()

        # Группировка данных по пациентам
        patients = {}
        for row in data:
            patient_id = row[0]
            if patient_id not in patients:
                patients[patient_id] = {
                    'name': row[1],
                    'services': [],
                    'total': 0
                }

            service = {
                'name': row[3],
                'price': float(row[4]),
                'date': row[5]
            }

            patients[patient_id]['services'].append(service)
            patients[patient_id]['total'] += service['price']

        return patients

    def generate_csv_report(self, company_name, start_date, end_date, patients_data):
        """Генерация CSV-отчета для страховой компании"""
        try:
            safe_company_name = "".join(c if c.isalnum() else "_" for c in company_name)
            filename = Path(f"accounts/Счет_{safe_company_name}_{start_date}_{end_date}.csv")

            # Открытие файла с явным указанием кодировки
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')

                # Заголовок отчета
                writer.writerow(["Страховая компания:", company_name])
                writer.writerow(["Период:", f"с {start_date} по {end_date}"])
                writer.writerow([])

                # Заголовки столбцов с данными
                writer.writerow(["Пациент", "Услуга", "Дата оказания", "Стоимость"])

                total_amount = 0

                # Запись данных по пациентам и услугам
                for patient_id, patient_data in patients_data.items():
                    writer.writerow([patient_data['name'], "", "", ""])

                    for service in patient_data['services']:
                        writer.writerow([
                            "",
                            service['name'],
                            str(service['date']),
                            f"{service['price']:.2f}"
                        ])

                    # Итоговая сумма по пациенту
                    writer.writerow(["", "", "Итого по пациенту:", f"{patient_data['total']:.2f}"])
                    writer.writerow([])

                    total_amount += patient_data['total']

                # Общая сумма к оплате
                writer.writerow(["", "", "Общая сумма к оплате:", f"{total_amount:.2f}"])

            return str(filename)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при создании CSV файла:\n{str(e)}")
            return None

    def save_invoice_to_db(self, company_id, start_date, end_date, total_amount):
        """Сохранение информации о счете в базу данных"""
        cursor = self.db_connection.cursor()
        query = """
        INSERT INTO insurance_invoices 
        (id_company, period_start, period_end, total_amount) 
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (company_id, start_date, end_date, total_amount))
        self.db_connection.commit()
        cursor.close()

    def generate_reports(self):
        """Основной метод генерации отчетов"""
        try:
            # Проверка корректности дат
            dates = self.validate_dates()
            if not dates:
                return

            start_date, end_date = dates
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Получение списка страховых компаний
            companies = self.get_insurance_companies()

            if not companies:
                QMessageBox.information(self, "Информация", "Нет страховых компаний в базе данных")
                return

            # Генерация отчетов для каждой компании
            for company in companies:
                patients_data = self.get_patients_services(company[0], start_date_str, end_date_str)

                if not patients_data:
                    continue  # Пропуск компаний без услуг за указанный период

                # Расчет общей суммы
                total_amount = sum(patient['total'] for patient in patients_data.values())

                # Генерация CSV-отчета
                csv_file = self.generate_csv_report(
                    company[1],
                    start_date_str,
                    end_date_str,
                    patients_data
                )

                # Сохранение информации в базу данных
                self.save_invoice_to_db(
                    company[0],
                    start_date_str,
                    end_date_str,
                    total_amount
                )

            QMessageBox.information(
                self,
                "Успех",
                "Счета успешно сформированы и сохранены в папке 'accounts'"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при формировании отчетов:\n{str(e)}")
            print(f"Ошибка generate_reports: {e}")


class SpecialistWindow(QMainWindow):
    """Окно лаборанта-исследователя"""
    def __init__(self, user, image_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(596, 376)
        self.ui = Ui_MainWindow2()
        self.ui.setupUi(self)
        self.ui.label_2.setText(f"{user[0]} {user[1]}")
        self.image_path = image_path
        self.load_user_image(image_path)

        self.ui.pushButton_3.clicked.connect(self.go_to_auth)
        self.db_connection = connect_to_database()
        self.services = []  # Список услуг
        self.analyzers_data = []  # Данные анализаторов

        # Загрузка данных при старте
        self.load_services()
        self.load_filters()
        self.load_analyzers()

        # Подключение сигналов к слотам
        self.ui.sesrch_services_LineEdit.textChanged.connect(self.apply_filters)
        self.ui.status_ComboBox.currentIndexChanged.connect(self.apply_filters)
        self.ui.approved_ComboBox.currentIndexChanged.connect(self.apply_filters)
        self.ui.analyzers_ComboBox.currentIndexChanged.connect(self.load_services_for_analyzer)

    def load_user_image(self, image_path):
        """Загрузка изображения пользователя."""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise FileNotFoundError(f"Изображение {image_path} не найдено.")
            self.ui.label.setPixmap(pixmap)
            self.ui.label.setScaledContents(True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить изображение: {e}")

    def go_to_auth(self):
        """Возврат к системе аутентификации."""
        self.parent().show()
        self.close()

    def load_services(self):
        """Загружает список услуг из базы данных"""
        cursor = self.db_connection.cursor()
        query = """
            SELECT o.id, b.tube_code, s.name, o.status_order, o.result, o.approved
            from orders o 
            JOIN biomaterial b on b.id = o.id_biomaterial
            JOIN services s on s.id = o.id_services
        """
        cursor.execute(query)
        self.services = cursor.fetchall()
        cursor.close()

        # Очистка layout перед добавлением новых данных
        for i in reversed(range(self.ui.servicesLayout.count())):
            widget = self.ui.servicesLayout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Добавление карточек услуг
        for service in self.services:
            self.add_service_card(service)

    def load_filters(self):
        """Инициализация фильтров в интерфейсе"""
        # Фильтр по статусу
        self.ui.status_ComboBox.addItem("All")
        self.ui.status_ComboBox.addItem("Finished")
        self.ui.status_ComboBox.addItem("Rejected")
        self.ui.status_ComboBox.addItem("New")
        self.ui.status_ComboBox.addItem("Approved")

        # Фильтр по одобрению
        self.ui.approved_ComboBox.addItem("All")
        self.ui.approved_ComboBox.addItem("Одобрено")
        self.ui.approved_ComboBox.addItem("Не одобрено")

    def add_service_card(self, service):
        """Создает карточку услуги в интерфейсе"""
        service_id, tube_code, name, status_order, result, approved = service

        card = QWidget()
        layout = QHBoxLayout()

        # Элементы карточки с фиксированной шириной
        barcode_label = QLabel(f"{tube_code}")
        barcode_label.setFixedWidth(40)

        name_label = QLabel(f"{name}")
        name_label.setFixedWidth(170)

        status_label = QLabel(f"{status_order}")
        status_label.setFixedWidth(60)

        result_label = QLabel(f"{result}")
        result_label.setFixedWidth(60)

        # Цветовая индикация статуса
        color_map = {
            "Approved": "green",
            "Rejected": "red",
            "New": "blue",
            "Finished": "orange"
        }
        status_color = color_map.get(status_order, "black")
        status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")

        layout.addWidget(barcode_label)
        layout.addWidget(name_label)
        layout.addWidget(status_label)
        layout.addWidget(result_label)

        # Кнопки действий для завершенных услуг
        if status_order == "Finished":
            approve_btn = QPushButton("Принять")
            reject_btn = QPushButton("Отказать")

            approve_btn.setFixedWidth(80)
            reject_btn.setFixedWidth(80)

            # Блокировка кнопок в зависимости от статуса одобрения
            if approved == "Одобрено":
                approve_btn.setEnabled(False)
                reject_btn.setEnabled(True)
            elif approved == "Не одобрено":
                approve_btn.setEnabled(True)
                reject_btn.setEnabled(False)
            else:
                approve_btn.setEnabled(True)
                reject_btn.setEnabled(True)

            # Подключение обработчиков кнопок
            approve_btn.clicked.connect(lambda _, sid=service_id: self.update_status(sid, "Одобрено"))
            reject_btn.clicked.connect(lambda _, sid=service_id: self.update_status(sid, "Не одобрено"))

            layout.addWidget(approve_btn)
            layout.addWidget(reject_btn)

        layout.addStretch()
        card.setLayout(layout)
        self.ui.servicesLayout.addWidget(card)

    def apply_filters(self):
        """Применяет фильтры к списку услуг"""
        try:
            cursor = self.db_connection.cursor()
            query = """
                SELECT o.id, b.tube_code, s.name, o.status_order, o.result, o.approved
                from orders o 
                JOIN biomaterial b on b.id = o.id_biomaterial
                JOIN services s on s.id = o.id_services
            """
            params = []

            # Фильтр по поисковому запросу
            search_text = self.ui.sesrch_services_LineEdit.text().strip()
            if search_text:
                query += " WHERE s.name LIKE %s OR b.barcode LIKE %s"
                params.append(f"%{search_text}%")
                params.append(f"%{search_text}%")

            # Фильтр по одобрению
            selected_approve = self.ui.approved_ComboBox.currentText()
            if selected_approve != "All":
                if "WHERE" in query:
                    query += " AND o.approved = %s"
                else:
                    query += " WHERE o.approved = %s"
                params.append(1 if selected_approve == "Одобрено" else 0)

            # Фильтр по статусу
            selected_status = self.ui.status_ComboBox.currentText()
            if selected_status != "All":
                if "WHERE" in query:
                    query += " AND o.status_order = %s"
                else:
                    query += " WHERE o.status_order = %s"
                params.append(selected_status)

            cursor.execute(query, params)
            self.services = cursor.fetchall()
            cursor.close()

            # Обновление отображения
            for i in reversed(range(self.ui.servicesLayout.count())):
                widget = self.ui.servicesLayout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            for service in self.services:
                self.add_service_card(service)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при создании заказа: {e}")

    def update_status(self, service_id, new_status):
        try:
            # Получение значений в зависимости от нового статуса
            if new_status == "Одобрено":
                status_order = "Approved"
                approved_value = 1
            elif new_status == "Не одобрено":
                status_order = "Rejected"
                approved_value = 0
            else:
                return

            # Обновление статуса в базе данных
            cursor = self.db_connection.cursor()
            update_query = """
                    UPDATE orders 
                    SET status_order = %s, approved = %s
                    WHERE id = %s
                """
            cursor.execute(update_query, (status_order, approved_value, service_id))
            self.db_connection.commit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении статуса: {e}")
        finally:
            cursor.close()

        self.apply_filters()

    def load_analyzers(self):
        """Загружает список анализаторов из базы данных"""
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT id, name FROM analyzer")
        self.analyzers_data = cursor.fetchall()
        for analyzer in self.analyzers_data:
            self.ui.analyzers_ComboBox.addItem(analyzer[1])
        cursor.close()

    def load_services_for_analyzer(self):
        """Загружает услуги для выбранного анализатора"""
        try:
            analyzer_id = self.ui.analyzers_ComboBox.currentIndex() + 1
            cursor = self.db_connection.cursor()
            query = """
                SELECT
                    a.id AS analyzer_id,
                    o.id AS order_id,
                    b.tube_code,
                    s.name,
                    o.status_order,
                    o.result
                FROM analyzer a
                JOIN analayzers_services als ON a.id = als.id_analyzer
                JOIN services s ON als.id_services = s.id
                JOIN orders o ON o.id_services = s.id
                JOIN biomaterial b ON o.id_biomaterial = b.id
                WHERE o.status_order = 'New' AND a.id = %s
            """
            cursor.execute(query, (analyzer_id,))
            services = cursor.fetchall()
            cursor.close()

            self.clear_layout(self.ui.available_services_verticalLayout)

            # Добавление карточек услуг анализатора
            for service in services:
                self.add_analyzer_card(service)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке услуг анализатора: {e}")

    def add_analyzer_card(self, service):
        """Создает карточку услуги для анализатора"""
        analyzer_id, order_id, tube_code, name, status_order, result = service

        card = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Левая часть карточки (фиксированные поля)
        fixed_part = QWidget()
        fixed_layout = QHBoxLayout(fixed_part)
        fixed_layout.setContentsMargins(10, 0, 0, 0)

        barcode_label = QLabel(f"{tube_code}")
        barcode_label.setFixedWidth(40)
        fixed_layout.addWidget(barcode_label)

        name_label = QLabel(f"{name}")
        name_label.setFixedWidth(170)
        fixed_layout.addWidget(name_label)

        status_label = QLabel(f"{status_order}")
        status_label.setFixedWidth(60)
        fixed_layout.addWidget(status_label)

        result_label = QLabel(f"{result}")
        result_label.setFixedWidth(70)
        fixed_layout.addWidget(result_label)

        # Правая часть карточки (динамическая)
        dynamic_part = QWidget()
        dynamic_layout = QHBoxLayout(dynamic_part)
        dynamic_layout.setContentsMargins(0, 0, 20, 0)
        # dynamic_layout.addStretch()

        # Кнопка исследования
        explore_button = QPushButton("Исследовать")
        explore_button.setFixedWidth(100)
        explore_button.clicked.connect(
            lambda _, sid=order_id: self.start_experiment(sid, explore_button, dynamic_layout))
        dynamic_layout.addWidget(explore_button)

        layout.addWidget(fixed_part)
        layout.addWidget(dynamic_part)

        card.setLayout(layout)
        self.ui.available_services_verticalLayout.addWidget(card)

    def start_experiment(self, order_id, explore_button, dynamic_layout):
        """Запускает процесс исследования"""
        try:
            self.ui.analyzers_ComboBox.setEnabled(False)
            # Проверка статуса анализатора
            analyzer_id = self.ui.analyzers_ComboBox.currentIndex() + 1
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT status FROM analyzer WHERE id = %s", (analyzer_id,))
            status = cursor.fetchone()[0]
            cursor.close()

            if status == "Working":
                QtWidgets.QMessageBox.warning(self, "Внимание", "Анализатор занят!")
                return

            # Установка статуса "В работе"
            cursor = self.db_connection.cursor()
            cursor.execute("UPDATE analyzer SET status = 'Working' WHERE id = %s", (analyzer_id,))
            self.db_connection.commit()
            cursor.close()

            explore_button.setEnabled(False)
            explore_button.setText('')

            # Создание анимации загрузки
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 5, 10, 0)

            # Загрузка GIF-анимации
            gif_path = "loader.gif"
            if not os.path.exists(gif_path):
                raise FileNotFoundError(f"GIF файл не найден: {gif_path}")

            movie = QMovie(gif_path)
            if not movie.isValid():
                raise ValueError("Неверный GIF файл")

            gif_label = QLabel()
            gif_label.setMovie(movie)
            movie.start()
            container_layout.addWidget(gif_label)

            # Настройка прогресс-бара
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_bar.setFixedWidth(170)
            progress_bar.setFixedHeight(20)
            container_layout.addWidget(progress_bar)

            # Замена кнопки на индикаторы
            explore_button.setParent(None)
            explore_button.deleteLater()
            dynamic_layout.insertWidget(dynamic_layout.count() - 1, container)

            # Запуск таймера для имитации процесса
            timer = QTimer(self)
            timer.timeout.connect(lambda: self.update_progress(progress_bar, timer, order_id, analyzer_id))
            timer.start(150)

        except Exception as e:
            self.ui.analyzers_ComboBox.setEnabled(True)
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при запуске исследования: {str(e)}")

    def update_progress(self, progress_bar, timer, order_id, analyzer_id):
        """Обновляет прогресс исследования"""
        try:
            current_value = progress_bar.value()
            if current_value < 100:
                progress_bar.setValue(current_value + 1)
            else:
                timer.stop()
                self.finish_experiment(order_id, analyzer_id)
        except Exception as e:
            self.reset_analyzer_status(analyzer_id)
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении прогресса: {e}")

    def finish_experiment(self, order_id, analyzer_id):
        """Завершает процесс исследования и сохраняет результат"""
        try:
            # Генерация случайного результата
            integer_part = random.randint(0, 3)
            decimal_part = random.randint(0, 99999)
            random_number = integer_part + decimal_part / 100000
            result = f"{random_number:.5f}"

            # Получение среднего значения для услуги
            cursor = self.db_connection.cursor()
            cursor.execute("""select s.average_deviation 
                              from services s 
                              JOIN orders o on o.id_services = s.id
                              WHERE o.id = %s
                              """,(order_id,))
            average_deviation = float(cursor.fetchall()[0][0])

            result_value = float(result)

            # Проверка на значительное отклонение
            if (result_value >= 5 * average_deviation) or (result_value <= average_deviation / 5):
                QtWidgets.QMessageBox.critical(
                    self,
                    "Внимание!",
                    f"Результат {result} отклоняется от среднего ({average_deviation}) в 5 раз!"
                )

            # Сохранение результата
            cursor.execute("""
                UPDATE orders 
                SET status_order = 'Finished', 
                    result = %s 
                WHERE id = %s
            """, (result, order_id))

            # Возврат анализатора в свободное состояние
            cursor.execute("UPDATE analyzer SET status = 'Free' WHERE id = %s", (analyzer_id,))
            self.db_connection.commit()
            cursor.close()

            # Обновление интерфейса
            self.load_services_for_analyzer()
            self.load_services()
            self.ui.analyzers_ComboBox.setEnabled(True)
        except Exception as e:
            self.reset_analyzer_status(analyzer_id)
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при завершении исследования: {e}")

    def clear_layout(self, layout):
        """Очищает указанный layout"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def reset_analyzer_status(self, analyzer_id):
        """Сбрасывает статус анализатора в 'Free'"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("UPDATE analyzer SET status = 'Free' WHERE id = %s", (analyzer_id,))
            self.db_connection.commit()
            cursor.close()
        except Exception as e:
            print(f"Ошибка при сбросе статуса: {e}")


class AdminWindow(QMainWindow):
    """Окно администратора."""

    def __init__(self, user, image_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(596, 376)
        self.ui = Ui_MainWindow4()
        self.ui.setupUi(self)
        self.ui.label_4.setText(f"{user[0]} {user[1]}")
        self.image_path = image_path
        self.load_user_image(image_path)

        self.ui.pushButton.clicked.connect(self.open_reports_window)
        self.ui.pushButton_3.clicked.connect(self.go_to_auth)
        self.populate_user_table()

    def load_user_image(self, image_path):
        """Загрузка изображения пользователя."""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise FileNotFoundError(f"Изображение {image_path} не найдено.")
            self.ui.label_2.setPixmap(pixmap)
            self.ui.label_2.setScaledContents(True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить изображение: {e}")

    def go_to_auth(self):
        """Возврат к системе аутентификации."""
        self.parent().show()
        self.close()

    def open_reports_window(self):
        """Открытие окна отчетов."""
        self.reports_window = ReportApp(
            db_connection=self.parent().db_connection,
            user_text=self.ui.label_4.text(),
            image_path=self.image_path,
            auth_window=self.parent(),
            parent=self
        )
        self.reports_window.show()
        self.hide()

    def populate_user_table(self):
        """Заполнение таблицы пользователей."""
        try:
            cursor = self.parent().db_connection.cursor()
            cursor.execute("SELECT lastname, name, lastenter FROM users")

            results = cursor.fetchall()

            self.ui.tableWidget.clear()
            self.ui.tableWidget.setRowCount(len(results))
            self.ui.tableWidget.setColumnCount(3)
            self.ui.tableWidget.setHorizontalHeaderLabels(["Фамилия", "Имя", "Дата последнего входа"])

            for row_index, row_data in enumerate(results):
                for column_index, item in enumerate(row_data):
                    self.ui.tableWidget.setItem(row_index, column_index, QTableWidgetItem(str(item)))

            self.ui.tableWidget.setColumnWidth(0, 150)
            self.ui.tableWidget.setColumnWidth(1, 100)
            self.ui.tableWidget.setColumnWidth(2, 227)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке данных пользователей: {e}")
