from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QDialog
import pymysql
from заказ import Ui_MainWindow
from AddPatient import Ui_AddPatient
from PyQt6.QtCore import QStringListModel, Qt
from PyQt6.QtGui import QPixmap, QIntValidator
import Levenshtein
from createBarcode import generate_barcode_pdf
from datetime import datetime
import random

class Order(QMainWindow):
    """Инициализация главного окна приложения"""

    def __init__(self, db_connection, user_text, image_path, auth_window, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.db_connection = db_connection
        self.auth_window = auth_window

        # Инициализация переменных для хранения данных
        self.all_patients = []
        self.selected_patient_data = []
        self.all_services = []
        self.selected_services_data = []
        self.all_extra_services = []
        self.selected_extra_services_data = []
        self.tube_code = None
        self.barcode_data = None
        self.random_tube_code = None
        self.random_barcode_data = None
        self.is_barcode_random = False

        # Получаем рекомендуемый код пробирки
        self.suggested_code = self.get_next_tube_code()

        # Загрузка данных
        self.load_patients()
        self.load_services()
        self.load_extra_services()

        # Настройка валидатора для поля tube_code
        self.ui.tube_code_LineEdit.setValidator(QIntValidator(0, 9999))

        # Подключение сигналов к слотам
        self.ui.patient_LineEdit.textChanged.connect(self.filter_patients)
        self.ui.patient_ListView.clicked.connect(self.on_patient_selected)
        self.ui.pushButton_4.clicked.connect(self.go_back)
        self.ui.pushButton_3.clicked.connect(self.go_to_auth)
        self.ui.service_LineEdit.textChanged.connect(self.filter_services)
        self.ui.service_ListView.clicked.connect(self.on_services_selected)
        self.ui.extra_service_LineEdit.textChanged.connect(self.filter_extra_services)
        self.ui.extra_service_ListView.clicked.connect(self.on_extra_services_selected)


        # Начальное состояние элементов интерфейса
        self.ui.patient_LineEdit.setEnabled(False)
        self.ui.service_LineEdit.setEnabled(False)
        self.ui.add_patient_Btn.setEnabled(False)
        self.ui.add_service_Btn.setEnabled(False)
        self.ui.extra_service_LineEdit.hide()
        self.ui.save_extra_service_Btn.hide()
        self.ui.information_TextEdit.setEnabled(False)
        self.ui.create_order_Btn.setEnabled(False)

        # Привязываем события к полю ввода
        self.ui.tube_code_LineEdit.focusInEvent = self.show_suggested_id
        self.ui.create_order_Btn.clicked.connect(self.create_order)
        self.ui.save_tube_code_Btn.clicked.connect(self.save_tube_code)
        self.ui.save_scan_code_Btn.clicked.connect(self.scan_barcode)
        self.ui.add_patient_Btn.clicked.connect(self.add_patient)
        self.ui.add_service_Btn.clicked.connect(self.add_service)
        self.ui.save_extra_service_Btn.clicked.connect(self.save_extra_service)
        self.ui.label_4.setText(user_text)
        self.image_path = image_path
        self.load_user_image()

    def go_back(self):
        self.parent().show()
        self.close()

    def go_to_auth(self):
        self.auth_window.show()
        self.close()

    def load_user_image(self):
        try:
            pixmap = QPixmap(self.image_path)
            if pixmap.isNull():
                raise FileNotFoundError(f"Изображение {self.image_path} не найдено.")
            self.ui.label_2.setPixmap(pixmap)
            self.ui.label_2.setScaledContents(True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить изображение: {e}")

    def get_next_tube_code(self):
        """Получает следующий доступный код пробирки из БД"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT MAX(id) FROM orders")
            result = cursor.fetchone()[0]
            cursor.close()

            next_id = (result + 1) if result else 1
            return str(next_id).zfill(4)
        except Exception as e:
            print(f"Ошибка БД: {e}")
            return "0001"

    def show_suggested_id(self, event):
        """Подставляет tube_code при фокусе, если поле пустое"""
        if not self.ui.tube_code_LineEdit.text():
            self.ui.tube_code_LineEdit.setText(self.suggested_code)
        super().focusInEvent(event)

    def load_patients(self):
        """Загружает список пациентов из БД"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id, CONCAT(lastname, ' ', name, ' ', middlename) AS full_name FROM patient")
            self.all_patients = cursor.fetchall()
            cursor.close()

            # Настройка модели для отображения пациентов
            self.patient_model = QStringListModel()
            self.patient_model.setStringList([full_name for _, full_name in self.all_patients])
            self.ui.patient_ListView.setModel(self.patient_model)

            self.ui.patient_ListView.raise_()

        except Exception as e:
            print(f"Ошибка загрузки пациентов: {e}")

    def filter_patients(self, text):
        """Фильтрует список пациентов с использованием нечёткого поиска (расстояние Левенштейна <= 3)"""
        if not text:
            self.ui.patient_ListView.hide()
            return

        text_lower = text.lower()
        filtered = []

        for patient_id, full_name in self.all_patients:
            # Приводим к нижнему регистру для регистронезависимого поиска
            name_lower = full_name.lower()

            # Если есть точное совпадение подстроки - добавляем без проверки расстояния
            if text_lower in name_lower:
                filtered.append(full_name)
                continue

            # Разбиваем ФИО на части для поиска по отдельности
            name_parts = name_lower.split()

            # Проверяем расстояние Левенштейна для каждой части имени
            for part in name_parts:
                distance = Levenshtein.distance(text_lower, part)
                if distance <= 3:
                    filtered.append(full_name)
                    break

        self.patient_model.setStringList(filtered)

        if filtered:
            self.ui.patient_ListView.show()
        else:
            self.ui.patient_ListView.hide()

    def on_patient_selected(self, index):
        """Обрабатывает выбор пациента из списка"""
        selected_text = self.patient_model.data(index, Qt.ItemDataRole.DisplayRole)
        self.ui.patient_LineEdit.setText(selected_text)
        self.ui.patient_ListView.hide()

        # Сохраняем ID выбранного пациента
        for patient_id, full_name in self.all_patients:
            if full_name == selected_text:
                self.selected_patient_data = patient_id, full_name
                break

        self.ui.information_TextEdit.append(f"Пациент: {self.selected_patient_data[1]}")

    def load_services(self):
        """Загружает список услуг из БД"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id, name FROM services")
            self.all_services = cursor.fetchall()
            cursor.close()

            # Настройка модели для отображения услуг
            self.services_model = QStringListModel()
            self.services_model.setStringList([name for _, name in self.all_services])
            self.ui.service_ListView.setModel(self.services_model)

            self.ui.service_ListView.raise_()

        except Exception as e:
            print(f"Ошибка загрузки услуг: {e}")

    def filter_services(self, text):
        """Фильтрует список услуг с использованием нечёткого поиска (расстояние Левенштейна <= 3)"""
        if not text:
            self.ui.service_ListView.hide()
            return

        text_lower = text.lower()
        filtered = []

        for services_id, name in self.all_services:
            # Приводим к нижнему регистру для регистронезависимого поиска
            name_lower = name.lower()

            # Если есть точное совпадение подстроки - добавляем без проверки расстояния
            if text_lower in name_lower:
                filtered.append(name)
                continue

            # Разбиваем наименование услуги на части для поиска по отдельности
            name_parts = name_lower.split()

            # Проверяем расстояние Левенштейна для каждой части имени
            for part in name_parts:
                distance = Levenshtein.distance(text_lower, part)
                if distance <= 3:
                    filtered.append(name)
                    break

        self.services_model.setStringList(filtered)

        if filtered:
            self.ui.service_ListView.show()
        else:
            self.ui.service_ListView.hide()

    def on_services_selected(self, index):
        """Обрабатывает выбор услуги из списка"""
        selected_text = self.services_model.data(index, Qt.ItemDataRole.DisplayRole)
        self.ui.service_LineEdit.setText(selected_text)
        self.ui.service_ListView.hide()

        # Сохраняем ID выбранного пациента
        for service_id, name in self.all_services:
            if name == selected_text:
                self.selected_services_data = service_id, name
                break

        self.ui.information_TextEdit.append(f"Услуга: {self.selected_services_data[1]}")

    def load_extra_services(self):
        """Загружает список дополнительных услуг"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id, name FROM services")
            self.all_extra_services = cursor.fetchall()
            cursor.close()

            # Настройка модели для отображения дополнительных услуг
            self.extra_services_model = QStringListModel()
            self.extra_services_model.setStringList([name for _, name in self.all_extra_services])
            self.ui.extra_service_ListView.setModel(self.extra_services_model)

            self.ui.extra_service_ListView.raise_()

        except Exception as e:
            print(f"Ошибка загрузки услуг: {e}")

    def filter_extra_services(self, text):
        """Фильтрует список дополнительных услуг с использованием нечёткого поиска (расстояние Левенштейна <= 3)"""
        if not text:
            self.ui.extra_service_ListView.hide()
            return

        text_lower = text.lower()
        filtered = []

        for services_id, name in self.all_extra_services:
            # Приводим к нижнему регистру для регистронезависимого поиска
            name_lower = name.lower()

            # Если есть точное совпадение подстроки - добавляем без проверки расстояния
            if text_lower in name_lower:
                filtered.append(name)
                continue

            # Разбиваем наменование услуги на части для поиска по отдельности
            name_parts = name_lower.split()

            # Проверяем расстояние Левенштейна для каждой части имени
            for part in name_parts:
                distance = Levenshtein.distance(text_lower, part)
                if distance <= 3:
                    filtered.append(name)
                    break

        self.extra_services_model.setStringList(filtered)

        if filtered:
            self.ui.extra_service_ListView.show()
        else:
            self.ui.extra_service_ListView.hide()

    def on_extra_services_selected(self, index):
        """Обрабатывает выбор дополнительных услуг из списка"""
        selected_text = self.extra_services_model.data(index, Qt.ItemDataRole.DisplayRole)
        self.ui.extra_service_LineEdit.setText(selected_text)
        self.ui.extra_service_ListView.hide()

        # Проверяем, что выбранная услуга не совпадает с основной услугой
        if hasattr(self, 'selected_services_data') and self.selected_services_data:
            main_service_name = self.selected_services_data[1]
            if selected_text == main_service_name:
                QMessageBox.warning(self, "Ошибка", "Эта услуга уже выбрана как основная!")
                self.ui.save_extra_service_Btn.hide()
                self.ui.extra_service_LineEdit.hide()
                self.ui.extra_service_LineEdit.clear()
                return

        for service_id, name in self.all_extra_services:
            if name == selected_text and [service_id, name] not in self.selected_extra_services_data:
                self.selected_extra_services_data.append([service_id, name])
                break

    def save_tube_code(self):
        """Сохраняет введенный код пробирки и генерирует штрих-код"""
        try:
            self.tube_code = self.ui.tube_code_LineEdit.text()

            # Проверка длины и числового формата
            if len(self.tube_code) != 4 or not self.tube_code.isdigit():
                QtWidgets.QMessageBox.critical(self, "Ошибка ввода",
                                               f"Код пробирки должен быть заполнен и состоять из 4 цифр!")
                return

            self.barcode_data = f"{self.tube_code}{datetime.today().strftime('%d%m%y')}{''.join(map(str, (random.randint(0, 9) for _ in range(6))))}"

            # Создание и отображение штрих-кода
            img_path = generate_barcode_pdf(self.barcode_data)
            print(img_path, " ", self.barcode_data)
            self.ui.barcode_Label.setPixmap(QPixmap(img_path))

            # Активация соответствующих элементов интерфейса
            self.ui.patient_LineEdit.setEnabled(True)
            self.ui.service_LineEdit.setEnabled(True)
            self.ui.add_patient_Btn.setEnabled(True)
            self.ui.add_service_Btn.setEnabled(True)
            self.ui.information_TextEdit.setEnabled(True)
            self.ui.information_TextEdit.setEnabled(True)
            self.ui.create_order_Btn.setEnabled(True)

            self.ui.save_tube_code_Btn.setEnabled(False)
            self.ui.save_scan_code_Btn.setEnabled(False)
            self.ui.tube_code_LineEdit.setEnabled(False)

        except Exception as e:
            print(f"Ошибка при : {e}")

    def scan_barcode(self):
        """Генерирует случайный штрих-код"""
        try:
            self.is_barcode_random = True
            self.random_tube_code = ''.join(map(str, (random.randint(0, 9) for _ in range(4))))
            self.random_barcode_data = f"{self.random_tube_code}{datetime.today().strftime('%d%m%y')}{''.join(map(str, (random.randint(0, 9) for _ in range(6))))}"
            self.ui.tube_code_LineEdit.setText(self.random_tube_code)

            # Создание и отображение штрих-кода
            img_path = generate_barcode_pdf(
                self.random_barcode_data)
            print(img_path, " ", self.random_barcode_data)
            self.ui.barcode_Label.setPixmap(QPixmap(img_path))

            # Активация соответствующих элементов интерфейса
            self.ui.patient_LineEdit.setEnabled(True)
            self.ui.service_LineEdit.setEnabled(True)
            self.ui.add_patient_Btn.setEnabled(True)
            self.ui.add_service_Btn.setEnabled(True)
            self.ui.information_TextEdit.setEnabled(True)
            self.ui.create_order_Btn.setEnabled(True)

            self.ui.save_tube_code_Btn.setEnabled(False)
            self.ui.save_scan_code_Btn.setEnabled(False)
            self.ui.tube_code_LineEdit.setEnabled(False)

        except Exception as e:
            print(f"Ошибка: {e}")

    def add_patient(self):
        """Открывает диалог добавления нового пациента"""
        dialog = QtWidgets.QDialog(self)
        dialog_ui = Ui_AddPatient()
        dialog_ui.setupUi(dialog)

        try:
            # Загрузка данных для выпадающих списков
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT DISTINCT name FROM insurance_company")
            types = cursor.fetchall()
            for material_type in types:
                dialog_ui.insurance_company_ComboBox.addItem(material_type[0])
            cursor.close()

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT type FROM policies_type")
            types = cursor.fetchall()
            for material_type in types:
                dialog_ui.policy_type_ComboBox.addItem(material_type[0])
            cursor.close()
        except Exception as e:
            print(f"Ошибка: {e}")

        # Сбор данных из формы
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                patient_data = [dialog_ui.name_LineEdit.text(),
                                dialog_ui.sername_LineEdit.text(),
                                dialog_ui.patronymic_LineEdit.text(),
                                dialog_ui.birthda_LineEdit.text(),
                                dialog_ui.phone_LineEdit.text(),
                                dialog_ui.email_LineEdit.text()]
                policy_data = [dialog_ui.insurance_company_ComboBox.currentText(),
                               dialog_ui.policy_LineEdit.text(),
                               dialog_ui.policy_type_ComboBox.currentText()]

                cursor = self.db_connection.cursor()
                cursor.execute("select id from insurance_company where name = %s", (policy_data[0],))
                policy_data[0] = cursor.fetchall()[0][0]
                cursor.close()
                cursor = self.db_connection.cursor()
                cursor.execute("select id from policies_type where type = %s", (policy_data[2],))
                policy_data[2] = cursor.fetchone()[0]
                cursor.close()

                passport_data = [dialog_ui.pasport_series_LineEdit.text(),
                                 dialog_ui.passport_num_LineEdit.text()]

                patient_data[3] = datetime.strptime(str(patient_data[3]), "%d.%m.%Y").date()

                print(patient_data, ' ', policy_data, ' ', passport_data)

                # Добавление пациента в базу данных
                cursor = self.db_connection.cursor()
                try:
                    cursor.execute("""
                        INSERT INTO patient (lastname, name, middlename, birthdate, phone_number, email)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, patient_data)
                    self.db_connection.commit()
                    new_patient_id = cursor.lastrowid  # Получаем ID нового пациента
                    print(f"Пациент добавлен с ID: {new_patient_id}")

                    policy_data.insert(0, new_patient_id)
                    cursor = self.db_connection.cursor()
                    cursor.execute("""
                        INSERT INTO ipolicies (id_patient, id_company, policy_number, policy_type)
                        VALUES (%s, %s, %s, %s)
                    """, policy_data)
                    self.db_connection.commit()

                    passport_data.insert(0, new_patient_id)
                    cursor.execute("""
                        INSERT INTO passport (id_patient, series, number)
                        VALUES (%s, %s, %s)
                    """, passport_data)
                    self.db_connection.commit()

                except pymysql.Error as err:
                    QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при выполнении операции: {err}")

                finally:
                    cursor.close()
                    QtWidgets.QMessageBox.information(self, "Успех", "Пациент успешно добавлен!")
                    self.load_patients()

        except pymysql.Error as err:
            # В случае ошибки выводим сообщение
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при добавлении пациента: {err}")

    def add_service(self):
        """Активирует интерфейс для добавления дополнительной услуги"""
        self.ui.extra_service_LineEdit.show()
        self.ui.save_extra_service_Btn.show()

    def save_extra_service(self):
        """Сохраняет выбранные дополнительные услуги"""
        current_text = self.ui.information_TextEdit.toPlainText()

        # Если текст уже содержит "Дополнительные услуги", обновляем этот раздел
        if "Дополнительные услуги:" in current_text:
            # Удаляем старый раздел с дополнительными услугами
            parts = current_text.split("Дополнительные услуги:")
            main_text = parts[0].strip()
        else:
            main_text = current_text

        # Формируем новый текст с дополнительными услугами
        extra_services_text = "\n".join([f"- {service[1]}" for service in self.selected_extra_services_data])
        new_text = f"{main_text}\nДополнительные услуги:\n{extra_services_text}"

        # Устанавливаем обновленный текст
        self.ui.information_TextEdit.setPlainText(new_text)

        self.ui.extra_service_LineEdit.clear()
        self.ui.extra_service_LineEdit.hide()
        self.ui.save_extra_service_Btn.hide()

    def create_order(self):
        """Создает заказ в базе данных"""
        print(self.selected_patient_data, ' ', self.selected_services_data, ' ', self.selected_extra_services_data)

        try:
            cursor = self.db_connection.cursor()

            # Вставка данных биоматериала
            barcode = self.random_barcode_data if self.is_barcode_random else self.barcode_data
            tube_code = self.random_tube_code if self.is_barcode_random else self.tube_code
            cursor.execute(
                "INSERT INTO biomaterial (id_patient, tube_code, barcode, date_bio) VALUES (%s, %s, %s, %s)",
                (self.selected_patient_data[0], tube_code, barcode, datetime.now().date())
            )
            bio_id = cursor.lastrowid
            self.db_connection.commit()

            # Подготовка списка всех услуг (основная + дополнительные)
            all_services_id = [self.selected_services_data[0]]  # основная услуга
            all_services_id.extend(service[0] for service in self.selected_extra_services_data)  # доп. услуги

            # Вставка заказов для каждой услуги
            for service_id in all_services_id:
                cursor.execute('''
                        INSERT INTO orders 
                        (date_create, id_biomaterial, id_services, status_order, approved, result) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (
                    datetime.now().date(),
                    bio_id,
                    service_id,
                    "New",
                    0,
                    0
                ))

            self.db_connection.commit()
            QtWidgets.QMessageBox.information(self, "Успех", "Заказ успешно создан!")

        except pymysql.Error as err:
            self.db_connection.rollback()
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Ошибка при создании заказа: {err}")
        finally:
            cursor.close()
            self.reset_form()

    def reset_form(self):
        """Сбрасывает форму к начальному состоянию"""
        self.selected_patient_data = []
        self.selected_services_data = []
        self.selected_extra_services_data = []
        self.tube_code = None
        self.barcode_data = None
        self.random_tube_code = None
        self.random_barcode_data = None
        self.is_barcode_random = False

        self.ui.tube_code_LineEdit.setEnabled(True)
        self.ui.tube_code_LineEdit.clear()
        self.ui.save_scan_code_Btn.setEnabled(True)
        self.ui.save_tube_code_Btn.setEnabled(True)
        self.ui.barcode_Label.clear()

        self.ui.patient_LineEdit.setEnabled(False)
        self.ui.patient_LineEdit.clear()
        self.ui.service_LineEdit.setEnabled(False)
        self.ui.service_LineEdit.clear()
        self.ui.add_patient_Btn.setEnabled(False)
        self.ui.add_service_Btn.setEnabled(False)
        self.ui.extra_service_LineEdit.hide()
        self.ui.save_extra_service_Btn.hide()
        self.ui.information_TextEdit.setEnabled(False)
        self.ui.information_TextEdit.clear()
        self.ui.create_order_Btn.setEnabled(False)

        self.load_patients()
        self.load_services()
        self.load_extra_services()


