# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'equations_gui.ui'
#
# Created by: PyQt5 UI code generator 5.15.4
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QIcon


class UIEquationWindow(QtWidgets.QWidget):
    def setupUi(self, case):
        self.setObjectName("Algoritmo")
        self.setObjectName("EquationDialog")
        self.setWindowIcon(QIcon("assets/icons/g868.ico"))
        self.horizontalLayout = QtWidgets.QHBoxLayout(self)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.equationGroupBox = QtWidgets.QGroupBox(self)
        self.equationGroupBox.setObjectName("equationGroupBox")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.equationGroupBox)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.equation = QtWidgets.QLabel(self.equationGroupBox)
        self.equation.setText("")
        self.equation.setPixmap(QtGui.QPixmap("assets/equations/fista.png"))
        self.equation.setScaledContents(False)
        self.equation.setObjectName("equation")
        self.horizontalLayout_2.addWidget(self.equation)
        self.horizontalLayout.addWidget(self.equationGroupBox)
        self.update_equation(case)

        self.retranslateUi(case)
        QtCore.QMetaObject.connectSlotsByName(self)

    def retranslateUi(self, case):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("UIEquationWindow", f"Algoritmo {case}"))
        self.equationGroupBox.setTitle(_translate("UIEquationWindow", "Algoritmo y parámetros"))

    def update_equation(self, case):
        self.equation.setPixmap(QtGui.QPixmap(f'assets/equations/{case.lower()}.png'))
        self.resize(10, 10)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    UIEquationWindow = QtWidgets.QWidget()
    ui = UIEquationWindow()
    ui.setupUi(UIEquationWindow, "example")
    UIEquationWindow.show()
    sys.exit(app.exec_())
