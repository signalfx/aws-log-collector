# Signifies our desired python version
# Makefile macros (or variables) are defined a little bit differently than traditional bash, keep in mind that in the Makefile there's top-level Makefile-only syntax, and everything else is bash script syntax.
PYTHON = python3
PIP = pip3

# .PHONY defines parts of the makefile that are not dependant on any specific file
# This is most often used to store functions
.PHONY = help init test tests coverage lint docker-image

# Defining an array variable
FILES = input output

# Defines the default target that `make` will to try to make, or in the case of a phony target, execute the specified commands
# This target is executed whenever we just type `make`
.DEFAULT_GOAL = help

coverage:
	coverage run --source=aws_log_collector -m unittest discover tests
	coverage report

# The @ makes sure that the command itself isn't echoed in the terminal
help:
	@echo "---------------HELP-----------------"
	@echo "To test the project type make test"
	@echo "To test the project with coverage type make coverage"
	@echo "------------------------------------"

init:
	${PIP} install -r requirements.txt
	${PIP} install -r requirements-dev.txt

lint: tests
	pylint aws_log_collector
	pylint tests
	pylint function.py

test: setup
	${PYTHON} -m unittest discover tests

tests: setup
	${PYTHON} -m unittest discover tests



