#!/bin/bash
clear
echo "attempting to convert qt qrc file to a python file..."

# New version for PySide6
for f in *.qrc
	do
		if [ -f "$f" ]
		then
			 pyside6-rcc "$f" -o "${f%.qrc}_rc.py"

		fi
	done
#cp *.py ../gemsrun/main/python/gui/


echo "done."
