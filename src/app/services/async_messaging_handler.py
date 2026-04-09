# Copyright (c) 2025-2026 AccelByte Inc. All Rights Reserved.
# This is licensed software from AccelByte Inc, for limitations
# and restrictions contact your company contract manager.

import json
import logging
from logging import Logger
from typing import Optional

import grpc
from accelbyte_py_sdk import AccelByteSDK
import accelbyte_py_sdk.api.cloudsave as cloudsave_service
import accelbyte_py_sdk.api.cloudsave.models as cloudsave_models

from google.protobuf.empty_pb2 import Empty

from async_messaging.consumer_service_pb2 import ReceivedMessage, DESCRIPTOR
from async_messaging.consumer_service_pb2_grpc import AsyncMessagingConsumerServiceServicer


class AsyncMessagingHandlerService(AsyncMessagingConsumerServiceServicer):
    full_name: str = DESCRIPTOR.services_by_name[
        "AsyncMessagingConsumerService"
    ].full_name

    def __init__(
        self,
        namespace: str,
        store_enabled: bool = False,
        sdk: Optional[AccelByteSDK] = None,
        logger: Optional[Logger] = None,
    ) -> None:
        self.namespace = namespace
        self.store_enabled = store_enabled
        self.sdk = sdk
        self.logger = logger or logging.getLogger(__name__)

    async def onMessage(self, request: ReceivedMessage, context) -> Empty:
        self.logger.info(
            "received message",
            extra={"topic": request.topic, "body": request.body, "metadata": dict(request.metadata)},
        )

        player_id = request.metadata.get("PlayerId")
        if player_id:
            if self.store_enabled:
                try:
                    event = json.loads(request.body)
                except json.JSONDecodeError as e:
                    self.logger.error("failed to unmarshal PlayerJoinedEvent: %s", e)
                    await context.abort(grpc.StatusCode.INTERNAL, str(e))
                    return Empty()

                body = cloudsave_models.ModelsGameRecordRequest.create(dict_=event)
                key = f"player_joined_event_{player_id}"

                self.logger.info(
                    "storing PlayerJoinedEvent to CloudSave",
                    extra={"playerId": player_id, "namespace": self.namespace},
                )
                _, error = await cloudsave_service.admin_post_game_record_handler_v1_async(
                    body=body,
                    key=key,
                    namespace=self.namespace,
                    sdk=self.sdk,
                )
                if error:
                    await context.abort(grpc.StatusCode.INTERNAL, f"failed to store to CloudSave: {error}")
                    return Empty()
        else:
            self.logger.info("PlayerId not found in metadata")

        return Empty()
