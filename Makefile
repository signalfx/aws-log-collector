# Copyright 2021 Splunk, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Signifies our desired python version
# Makefile macros (or variables) are defined a little bit differently than traditional bash, keep in mind that in the Makefile there's top-level Makefile-only syntax, and everything else is bash script syntax.
PYTHON = python3
PIP = pip3

# Defines the default target that `make` will to try to make, or in the case of a phony target, execute the specified commands
# This target is executed whenever we just type `make`
.DEFAULT_GOAL = help

clean:
	rm -f aws-log-collector.test.zip
	rm -f aws-log-collector.stage.zip
	rm -f aws-log-collector.release.zip
	rm -rf package

coverage:
	coverage run --source=aws_log_collector -m unittest discover tests
	coverage report

# The @ makes sure that the command itself isn't echoed in the terminal
help:
	@echo "---------------HELP-----------------"
	@echo "To install all dependencies type make init"
	@echo "To test the project type make test"
	@echo "To generate coverage report type make coverage"
	@echo "To run pylint type make lint"
	@echo "To create a lambda zip for local testing type make local-zip"
	@echo "To clean type make clean"
	@echo "------------------------------------"

init:
	${PIP} install -r requirements.txt
	${PIP} install -r requirements-dev.txt

lint:
	pylint aws_log_collector
	pylint tests
	pylint function.py

local-zip:
	pip3 install -r requirements.txt --target package
	cd package && zip -r ../aws-log-collector.test.zip .
	zip -g aws-log-collector.test.zip function.py
	zip -gr aws-log-collector.test.zip aws_log_collector -x '*__pycache__*'
	git rev-parse HEAD > commitId.txt
	zip -g aws-log-collector.test.zip commitId.txt
	unzip -l aws-log-collector.test.zip

release-zip: local-zip
	mv aws-log-collector.test.zip aws-log-collector.release.zip

stage-zip: local-zip
	mv aws-log-collector.test.zip aws-log-collector.stage.zip

test: init
	${PYTHON} -m unittest discover tests

tests: test

#intended for use from CI only. Use with care - will be called with your default AWS profile!
publish-release:
	./publish-to-aws.sh
