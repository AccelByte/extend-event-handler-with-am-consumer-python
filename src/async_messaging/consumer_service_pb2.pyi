from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor
TOPICS_SUBSCRIPTION_FIELD_NUMBER: _ClassVar[int]
topics_subscription: _descriptor.FieldDescriptor

class ReceivedMessage(_message.Message):
    __slots__ = ("body", "topic", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    BODY_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    body: str
    topic: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, body: _Optional[str] = ..., topic: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...
