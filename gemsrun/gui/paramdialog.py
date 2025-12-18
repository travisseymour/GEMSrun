
################################################################################
## Form generated from reading UI file 'paramdialog.ui'
##
## Created by: Qt User Interface Compiler version 6.6.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QVBoxLayout,
)


class Ui_paramDialog:
    def setupUi(self, paramDialog):
        if not paramDialog.objectName():
            paramDialog.setObjectName("paramDialog")
        paramDialog.setWindowModality(Qt.ApplicationModal)
        paramDialog.resize(879, 632)
        font = QFont()
        font.setFamilies(["Verdana"])
        paramDialog.setFont(font)
        paramDialog.setSizeGripEnabled(False)
        paramDialog.setModal(True)
        self.gridLayout = QGridLayout(paramDialog)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(8, 5, 8, 5)
        self.label = QLabel(paramDialog)
        self.label.setObjectName("label")
        self.label.setMaximumSize(QSize(16777215, 50))
        font1 = QFont()
        font1.setFamilies(["Verdana"])
        font1.setPointSize(18)
        self.label.setFont(font1)
        self.label.setScaledContents(False)

        self.verticalLayout.addWidget(self.label)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.label_5 = QLabel(paramDialog)
        self.label_5.setObjectName("label_5")

        self.horizontalLayout_4.addWidget(self.label_5)

        self.envLineEdit = QLineEdit(paramDialog)
        self.envLineEdit.setObjectName("envLineEdit")
        font2 = QFont()
        font2.setFamilies(["Verdana"])
        font2.setPointSize(12)
        self.envLineEdit.setFont(font2)
        self.envLineEdit.setReadOnly(False)

        self.horizontalLayout_4.addWidget(self.envLineEdit)

        self.toolButton = QToolButton(paramDialog)
        self.toolButton.setObjectName("toolButton")
        font3 = QFont()
        font3.setFamilies(["Verdana"])
        font3.setPointSize(14)
        font3.setBold(True)
        self.toolButton.setFont(font3)

        self.horizontalLayout_4.addWidget(self.toolButton)

        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label_2 = QLabel(paramDialog)
        self.label_2.setObjectName("label_2")

        self.horizontalLayout.addWidget(self.label_2)

        self.userLineEdit = QLineEdit(paramDialog)
        self.userLineEdit.setObjectName("userLineEdit")
        self.userLineEdit.setFont(font2)
        self.userLineEdit.setReadOnly(False)

        self.horizontalLayout.addWidget(self.userLineEdit)

        self.verticalLayout.addLayout(self.horizontalLayout)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.skipdataCheckBox = QCheckBox(paramDialog)
        self.skipdataCheckBox.setObjectName("skipdataCheckBox")
        self.skipdataCheckBox.setFont(font3)
        self.skipdataCheckBox.setLayoutDirection(Qt.LeftToRight)

        self.horizontalLayout_2.addWidget(self.skipdataCheckBox)

        self.horizontalSpacer = QSpacerItem(408, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.overwriteCheckBox = QCheckBox(paramDialog)
        self.overwriteCheckBox.setObjectName("overwriteCheckBox")
        self.overwriteCheckBox.setFont(font3)
        self.overwriteCheckBox.setLayoutDirection(Qt.LeftToRight)

        self.horizontalLayout_6.addWidget(self.overwriteCheckBox)

        self.horizontalSpacer_3 = QSpacerItem(408, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_3)

        self.verticalLayout.addLayout(self.horizontalLayout_6)

        self.horizontalLayout_7 = QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.debugCheckBox = QCheckBox(paramDialog)
        self.debugCheckBox.setObjectName("debugCheckBox")
        self.debugCheckBox.setFont(font3)
        self.debugCheckBox.setLayoutDirection(Qt.LeftToRight)

        self.horizontalLayout_7.addWidget(self.debugCheckBox)

        self.horizontalSpacer_4 = QSpacerItem(408, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer_4)

        self.verticalLayout.addLayout(self.horizontalLayout_7)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.skipmediaCheckBox = QCheckBox(paramDialog)
        self.skipmediaCheckBox.setObjectName("skipmediaCheckBox")
        self.skipmediaCheckBox.setFont(font3)
        self.skipmediaCheckBox.setLayoutDirection(Qt.LeftToRight)

        self.horizontalLayout_5.addWidget(self.skipmediaCheckBox)

        self.horizontalSpacer_2 = QSpacerItem(408, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_2)

        self.verticalLayout.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.fullscreenCheckBox = QCheckBox(paramDialog)
        self.fullscreenCheckBox.setObjectName("fullscreenCheckBox")
        self.fullscreenCheckBox.setFont(font3)
        self.fullscreenCheckBox.setLayoutDirection(Qt.LeftToRight)

        self.horizontalLayout_9.addWidget(self.fullscreenCheckBox)

        self.horizontalSpacer_6 = QSpacerItem(408, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_6)

        self.verticalLayout.addLayout(self.horizontalLayout_9)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.horizontalSpacer_5 = QSpacerItem(438, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer_5)

        self.cancelPushButton = QPushButton(paramDialog)
        self.cancelPushButton.setObjectName("cancelPushButton")
        self.cancelPushButton.setFont(font3)

        self.horizontalLayout_8.addWidget(self.cancelPushButton)

        self.startPushButton = QPushButton(paramDialog)
        self.startPushButton.setObjectName("startPushButton")
        self.startPushButton.setFont(font3)

        self.horizontalLayout_8.addWidget(self.startPushButton)

        self.verticalLayout.addLayout(self.horizontalLayout_8)

        self.gridLayout.addLayout(self.verticalLayout, 0, 0, 1, 1)

        self.retranslateUi(paramDialog)

        self.startPushButton.setDefault(True)

        QMetaObject.connectSlotsByName(paramDialog)

    # setupUi

    def retranslateUi(self, paramDialog):
        paramDialog.setWindowTitle(QCoreApplication.translate("paramDialog", "Dialog", None))
        self.label.setText(
            QCoreApplication.translate(
                "paramDialog",
                '<html><head/><body><p><span style=" font-size:22pt; font-weight:600;">GEMS Runner Parameters</span></p></body></html>',
                None,
            )
        )
        # if QT_CONFIG(tooltip)
        self.label_5.setToolTip(QCoreApplication.translate("paramDialog", "Current GEMS Environment FIle Path", None))
        # endif // QT_CONFIG(tooltip)
        self.label_5.setText(
            QCoreApplication.translate(
                "paramDialog",
                '<html><head/><body><p><span style=" font-size:14pt; font-weight:600;">Environment:</span></p></body></html>',
                None,
            )
        )
        # if QT_CONFIG(tooltip)
        self.envLineEdit.setToolTip(
            QCoreApplication.translate("paramDialog", "Current GEMS Environment FIle Path", None)
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(tooltip)
        self.toolButton.setToolTip(QCoreApplication.translate("paramDialog", "Choose GEMS Environment File", None))
        # endif // QT_CONFIG(tooltip)
        self.toolButton.setText(QCoreApplication.translate("paramDialog", "...", None))
        # if QT_CONFIG(tooltip)
        self.label_2.setToolTip(QCoreApplication.translate("paramDialog", "Filename stub used for data filename", None))
        # endif // QT_CONFIG(tooltip)
        self.label_2.setText(
            QCoreApplication.translate(
                "paramDialog",
                '<html><head/><body><p><span style=" font-size:14pt; font-weight:600;">User ID:</span></p></body></html>',
                None,
            )
        )
        # if QT_CONFIG(tooltip)
        self.userLineEdit.setToolTip(
            QCoreApplication.translate("paramDialog", "Filename stub used for data filename", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.skipdataCheckBox.setText(
            QCoreApplication.translate("paramDialog", "SkipData (Suppress output data file)", None)
        )
        self.overwriteCheckBox.setText(
            QCoreApplication.translate("paramDialog", "Overwrite (Overwrite duplicate data file)", None)
        )
        # if QT_CONFIG(tooltip)
        self.debugCheckBox.setToolTip("")
        # endif // QT_CONFIG(tooltip)
        self.debugCheckBox.setText(
            QCoreApplication.translate(
                "paramDialog", "Debug (Write extra debugging  information to terminal and data file)", None
            )
        )
        self.skipmediaCheckBox.setText(
            QCoreApplication.translate("paramDialog", "SkipMedia (Disable playback of audio and video files)", None)
        )
        self.fullscreenCheckBox.setText(
            QCoreApplication.translate(
                "paramDialog", "FullScreen (Show FullScreen Ignoring Environment File Setttings)", None
            )
        )
        self.cancelPushButton.setText(QCoreApplication.translate("paramDialog", "Cancel", None))
        self.startPushButton.setText(QCoreApplication.translate("paramDialog", "Start", None))

    # retranslateUi
