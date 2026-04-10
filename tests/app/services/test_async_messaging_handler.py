# Copyright (c) 2025-2026 AccelByte Inc. All Rights Reserved.
# This is licensed software from AccelByte Inc, for limitations
# and restrictions contact your company contract manager.

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

import grpc
import grpc.aio

from async_messaging.consumer_service_pb2 import ReceivedMessage
from async_messaging.consumer_service_pb2_grpc import (
    add_AsyncMessagingConsumerServiceServicer_to_server,
    AsyncMessagingConsumerServiceStub,
)
from app.services.async_messaging_handler import AsyncMessagingHandlerService


# Step 2 — Happy path, no PlayerId (store disabled)
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
            from google.protobuf.empty_pb2 import Empty
            assert isinstance(response, Empty)
    finally:
        await server.stop(0)


# Step 3 — PlayerId present, store disabled (Branch B)
@pytest.mark.asyncio
async def test_on_message_with_player_id_store_disabled():
    handler = AsyncMessagingHandlerService(namespace="test", store_enabled=False, sdk=None)

    server = grpc.aio.server()
    add_AsyncMessagingConsumerServiceServicer_to_server(handler, server)
    port = server.add_insecure_port("[::]:0")
    await server.start()

    try:
        async with grpc.aio.insecure_channel(f"localhost:{port}") as channel:
            stub = AsyncMessagingConsumerServiceStub(channel)
            response = await stub.onMessage(
                ReceivedMessage(
                    topic="PlayerJoined",
                    body=json.dumps({"eventType": "PlayerJoined", "playerId": "user-123", "timestamp": "2026-01-01T00:00:00Z"}),
                    metadata={"PlayerId": "user-123"},
                )
            )
            assert response is not None
    finally:
        await server.stop(0)


# Step 4 — PlayerId missing from metadata (Branch D)
@pytest.mark.asyncio
async def test_on_message_without_player_id():
    # store_enabled=True intentionally — proves CloudSave is NOT reached when PlayerId absent
    handler = AsyncMessagingHandlerService(namespace="test", store_enabled=True, sdk=None)

    server = grpc.aio.server()
    add_AsyncMessagingConsumerServiceServicer_to_server(handler, server)
    port = server.add_insecure_port("[::]:0")
    await server.start()

    try:
        async with grpc.aio.insecure_channel(f"localhost:{port}") as channel:
            stub = AsyncMessagingConsumerServiceStub(channel)
            response = await stub.onMessage(
                ReceivedMessage(topic="PlayerKilled", body="{}"),
            )
            assert response is not None
    finally:
        await server.stop(0)


# Step 5A — Invalid JSON body, store enabled: unit test verifies context.abort called (Branch C)
@pytest.mark.asyncio
async def test_on_message_invalid_json_aborts_with_internal():
    handler = AsyncMessagingHandlerService(namespace="test", store_enabled=True, sdk=None)

    context = AsyncMock()
    context.abort = AsyncMock()

    request = ReceivedMessage(
        topic="PlayerJoined",
        body="this is not json {{{",
        metadata={"PlayerId": "user-123"},
    )

    await handler.onMessage(request, context)

    args = context.abort.call_args
    assert args[0][0] == grpc.StatusCode.INTERNAL
    assert isinstance(args[0][1], str) and len(args[0][1]) > 0


# Step 5B — Invalid JSON body, store enabled: gRPC integration verifies INTERNAL propagates (Branch C)
@pytest.mark.asyncio
async def test_on_message_invalid_json_raises_grpc_error():
    handler = AsyncMessagingHandlerService(namespace="test", store_enabled=True, sdk=None)

    server = grpc.aio.server()
    add_AsyncMessagingConsumerServiceServicer_to_server(handler, server)
    port = server.add_insecure_port("[::]:0")
    await server.start()

    try:
        async with grpc.aio.insecure_channel(f"localhost:{port}") as channel:
            stub = AsyncMessagingConsumerServiceStub(channel)
            with pytest.raises(grpc.aio.AioRpcError) as exc_info:
                await stub.onMessage(
                    ReceivedMessage(
                        topic="PlayerJoined",
                        body="not valid json",
                        metadata={"PlayerId": "user-123"},
                    )
                )
            assert exc_info.value.code() == grpc.StatusCode.INTERNAL
    finally:
        await server.stop(0)


# Step 6 — CloudSave success path (Branch E)
@pytest.mark.asyncio
async def test_on_message_store_enabled_calls_cloudsave():
    mock_sdk = MagicMock()

    with patch(
        "app.services.async_messaging_handler.cloudsave_service.admin_post_game_record_handler_v1_async",
        new_callable=AsyncMock,
        return_value=(None, None),
    ) as mock_cloudsave:
        handler = AsyncMessagingHandlerService(
            namespace="test-namespace",
            store_enabled=True,
            sdk=mock_sdk,
        )

        server = grpc.aio.server()
        add_AsyncMessagingConsumerServiceServicer_to_server(handler, server)
        port = server.add_insecure_port("[::]:0")
        await server.start()

        try:
            async with grpc.aio.insecure_channel(f"localhost:{port}") as channel:
                stub = AsyncMessagingConsumerServiceStub(channel)
                response = await stub.onMessage(
                    ReceivedMessage(
                        topic="PlayerJoined",
                        body=json.dumps({"eventType": "PlayerJoined", "playerId": "user-456", "timestamp": "2026-01-01T00:00:00Z"}),
                        metadata={"PlayerId": "user-456"},
                    )
                )
                assert response is not None
        finally:
            await server.stop(0)

        mock_cloudsave.assert_called_once()
        call_kwargs = mock_cloudsave.call_args.kwargs
        assert call_kwargs["key"] == "player_joined_event_user-456"
        assert call_kwargs["namespace"] == "test-namespace"
        assert call_kwargs["sdk"] is mock_sdk
        assert call_kwargs["body"] is not None


# Step 7 — CloudSave error propagates as INTERNAL gRPC error (Branch F)
@pytest.mark.asyncio
async def test_on_message_cloudsave_error_returns_internal():
    mock_sdk = MagicMock()
    fake_error = Exception("cloudsave unavailable")

    with patch(
        "app.services.async_messaging_handler.cloudsave_service.admin_post_game_record_handler_v1_async",
        new_callable=AsyncMock,
        return_value=(None, fake_error),
    ):
        handler = AsyncMessagingHandlerService(
            namespace="test",
            store_enabled=True,
            sdk=mock_sdk,
        )

        server = grpc.aio.server()
        add_AsyncMessagingConsumerServiceServicer_to_server(handler, server)
        port = server.add_insecure_port("[::]:0")
        await server.start()

        try:
            async with grpc.aio.insecure_channel(f"localhost:{port}") as channel:
                stub = AsyncMessagingConsumerServiceStub(channel)
                with pytest.raises(grpc.aio.AioRpcError) as exc_info:
                    await stub.onMessage(
                        ReceivedMessage(
                            topic="PlayerJoined",
                            body=json.dumps({"eventType": "PlayerJoined", "playerId": "user-789", "timestamp": "2026-01-01T00:00:00Z"}),
                            metadata={"PlayerId": "user-789"},
                        )
                    )
                assert exc_info.value.code() == grpc.StatusCode.INTERNAL
        finally:
            await server.stop(0)
