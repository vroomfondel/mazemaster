.PHONY: tests
SHELL := /usr/bin/bash
.ONESHELL:

help:
	@printf "\ninstall\n\tinstall requirements\n"
	@printf "\nisort\n\tmake isort import corrections\n"
	@printf "\nlint\n\tmake linter check with black\n"
	@printf "\ntcheck\n\tmake static type checks with mypy\n"
	@printf "\ntests\n\tLaunch tests\n"
	@printf "\nprepare\n\tLaunch tests and commit-checks\n"
	@printf "\ncommit-checks\n\trun pre-commit checks on all files\n"
	@printf "\nstart \n\tstart app in uvicorn - listening on port 18889\n"
	@printf "\ndocker-build \n\tbuild docker-image\n"
	@printf "\ndocker-run \n\trun in (locally) built docker-image\n"
	@printf "\ndocker-run-dh \n\trun LATEST image from DockerHub\n"

venv_activated=if [ -z $${VIRTUAL_ENV+x} ]; then printf "activating venv...\n" ; source venv/bin/activate || exit 123; else printf "venv already activated\n"; fi

install: venv

venv: venv/touchfile

venv/touchfile: requirements.txt requirements-dev.txt requirements-local.txt
	test -d venv || python3.9 -m venv
	source venv/bin/activate
	pip install -r requirements-dev.txt
	mypy --install-types
	touch venv/touchfile


tests: venv
	@$(venv_activated)
	pytest .

lint: venv
	@$(venv_activated)
	black -l 120 mazemaster tests


start: venv
	@$(venv_activated)
	python3 main.py

isort: venv
	@$(venv_activated)
	isort mazemaster tests

tcheck: venv
	@$(venv_activated)
	mypy mazemaster

.git/hooks/pre-commit: venv
	@$(venv_activated)
	pre-commit install

commit-checks: .git/hooks/pre-commit
	@$(venv_activated)
	pre-commit run --all-files


prepare: tests commit-checks

docker-build:
	buildtime=$(date +'%Y-%m-%d %H:%M:%S %Z')
	docker build --build-arg buildtime="${buildtime}" -t mazemaster:latest .

#in .detaSECRET (without leading #):
#DETA_PROJECT_KEY=PROJECTKEYYOUSHOULDGETFROM_DETA.SH  => only using deta-base from here ==> https://docs.deta.sh/docs/base/about

docker-run: docker-build
	 docker run --rm -ti --env-file=.detaSECRET -p 18890:18890 mazemaster:latest

docker-run-dh:
	docker run --rm -ti --env-file=.detaSECRET -p 18890:18890 vroofoo/mazemaster:latest


