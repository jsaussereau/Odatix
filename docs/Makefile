

.PHONY: build
build: install css

.PHONY: install
install:
	npm install

.PHONY: css
css:
	npm run css

.PHONY: run
run: build
	hugo server --gc --disableFastRender --cleanDestinationDir
