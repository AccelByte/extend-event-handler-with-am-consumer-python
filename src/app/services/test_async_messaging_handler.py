# Copyright (c) 2025-2026 AccelByte Inc. All Rights Reserved.
# This is licensed software from AccelByte Inc, for limitations
# and restrictions contact your company contract manager.

import pytest

import grpc
import grpc.aio

from async_messaging.consumer_service_pb2 import ReceivedMessage
from async_messaging.consumer_service_pb2_grpc import (
    add_AsyncMessagingConsumerServiceServicer_to_server,
    AsyncMessagingConsumerServiceStub,
)
from app.services.async_messaging_handler import AsyncMessagingHandlerService


@pytest.mark.asyncio
async def test_on_message_via_grpc():
    handler = AsyncMessagingHandlerService(
        namespace="test",
        store_enabled=False,
        sdk=None,
    )

    server = grpc.aio.server()
    add_AsyncMessagingConsumerServiceServicer_to_server(handler, server)
    port = server.add_insecure_port("[::]:0")
    await server.start()

    try:
        async with grpc.aio.insecure_channel(f"localhost:{port}") as channel:
            stub = AsyncMessagingConsumerServiceStub(channel)
            response = await stub.onMessage(
                ReceivedMessage(topic="PlayerSaved", body="Saved.")
            )
            assert response is not None
    finally:
        await server.stop(0)
