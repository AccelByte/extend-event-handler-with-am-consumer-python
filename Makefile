# Copyright (c) 2025 AccelByte Inc. All Rights Reserved.
# This is licensed software from AccelByte Inc, for limitations
# and restrictions contact your company contract manager.

SHELL := /bin/bash

PROTOC_IMAGE := proto-builder

IS_INSIDE_DEVCONTAINER := $(REMOTE_CONTAINERS)

.PHONY: build proto_image proto test

proto_image:
ifneq ($(IS_INSIDE_DEVCONTAINER),true)
	docker build --target proto-builder -t $(PROTOC_IMAGE) .
endif

proto: proto_image
ifneq ($(IS_INSIDE_DEVCONTAINER),true)
	docker run --tty --rm --user $$(id -u):$$(id -g) \
		--volume $$(pwd):/build \
		--workdir /build \
		--entrypoint /bin/bash \
		$(PROTOC_IMAGE) \
		proto.sh
else
	./proto.sh
endif

test:
	pytest

build: proto
