# Makefile — reference for the clang invocation (actual build runs on GitHub Actions)
# This won't work on Windows, it's here for documentation and CI

SDK_PATH ?= $(shell xcrun --sdk iphoneos --show-sdk-path)
MIN_IOS   = 14.0
ARCH      = arm64
OUTPUT    = SpinLogger.dylib

DOBBY_DIR ?= dobby
DOBBY_INC ?= $(DOBBY_DIR)/include
DOBBY_LIB ?= $(DOBBY_DIR)/build/libdobby.a

SOURCES = $(wildcard src/*.m)

CFLAGS = -target $(ARCH)-apple-ios$(MIN_IOS) \
         -isysroot $(SDK_PATH) \
         -fPIC -shared \
         -fobjc-arc \
         -I $(DOBBY_INC) \
         -framework Foundation \
         -framework UIKit \
         -framework CoreGraphics \
         -framework QuartzCore \
         -framework WebKit \
         -O2

LDFLAGS = $(DOBBY_LIB) -lc++

all: $(OUTPUT)

$(OUTPUT): $(SOURCES)
	clang $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(OUTPUT)

.PHONY: all clean
