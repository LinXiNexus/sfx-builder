OUT ?= Tool.exe

.PHONY: all build verify clean

all: build

build:
	OUT_NAME=$(OUT) bash scripts/build.sh

verify:
	python3 scripts/verify.py $(OUT)

clean:
	rm -rf build $(OUT) $(OUT).sha256
