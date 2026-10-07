OUT ?= Tool.exe

.PHONY: all build verify wizard clean

all: build

build:
	OUT_NAME=$(OUT) bash scripts/build.sh

verify:
	python3 scripts/verify.py $(OUT)

wizard:
	python3 scripts/wizard.py

clean:
	rm -rf build $(OUT) $(OUT).sha256
