

.PHONY: build
build:
	hugo mod graph
	hugo mod get -u
	hugo mod tidy
	hugo mod npm pack
	npm install
	npm audit fix

.PHONY: run
run: build
	hugo server --gc --disableFastRender --cleanDestinationDir