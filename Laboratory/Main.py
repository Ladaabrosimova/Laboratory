import sys
from PyQt6.QtWidgets import QApplication
from Entrance import AuthSystem

def main():
    app = QApplication(sys.argv)
    auth_window = AuthSystem()
    auth_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()


