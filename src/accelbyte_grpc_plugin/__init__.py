# Copyright (c) 2023 AccelByte Inc. All Rights Reserved.
# This is licensed software from AccelByte Inc, for limitations
# and restrictions contact your company contract manager.

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum, auto as enum_auto
from logging import Logger
from typing import Any, Callable, Optional, Protocol, List, Union

from environs import Env

import grpc.aio
from grpc.aio import Server, ServerInterceptor

import opentelemetry.metrics
import opentelemetry.trace
from opentelemetry.instrumentation.grpc import aio_server_interceptor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME as RESOURCE_SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider

DEFAULT_LOGGER_NAME: str = "extend-app-event-handler"
DEFAULT_LOGGER_LEVEL: Union[int, str] = logging.DEBUG


class App:
    def __init__(
        self,
        port: int,
        env: Env,
        opts: Optional[List[AppOpt]] = None,
        logger: Optional[Logger] = None,
        **kwargs,
    ) -> None:
        opts = opts if opts else []
        if logger is None:
            logger = logging.getLogger(DEFAULT_LOGGER_NAME)
            logger.setLevel(DEFAULT_LOGGER_LEVEL)

        self.port = port
        self.env = env
        self.logger = logger

        v = self.env.str("SERVICE_NAME", self.env.str("OTEL_SERVICE_NAME", None))
        self.service_name = f"extend-app-eh-{v.strip().lower()}" if v else "extend-app-event-handler"
        self.grpc_interceptors: List[ServerInterceptor] = [aio_server_interceptor()]
        self.grpc_service_names: List[str] = []
        self.otel_metric_readers: List[MetricReader] = []
        self.otel_resource = Resource({RESOURCE_SERVICE_NAME: self.service_name})

        # apply default options
        self.__apply_opts(opts, AppOptOrder.DEFAULT)
        self.logger.info("default options applied")

        # set opentelemetry tracer provider
        self.__apply_opts(opts, AppOptOrder.BEFORE_SET_OTEL_TRACER_PROVIDER)
        opentelemetry.trace.set_tracer_provider(
            TracerProvider(resource=self.otel_resource)
        )
        self.logger.info("opentelemetry tracer provider set")
        self.__apply_opts(opts, AppOptOrder.AFTER_SET_OTEL_TRACER_PROVIDER)

        # set opentelemetry meter provider
        self.__apply_opts(opts, AppOptOrder.BEFORE_SET_OTEL_METER_PROVIDER)
        if self.otel_metric_readers:
            opentelemetry.metrics.set_meter_provider(
                MeterProvider(self.otel_metric_readers, resource=self.otel_resource)
            )
        self.logger.info("opentelemetry meter provider set")
        self.__apply_opts(opts, AppOptOrder.AFTER_SET_OTEL_METER_PROVIDER)

        # set gRPC server
        self.__apply_opts(opts, AppOptOrder.BEFORE_CREATE_GRPC_SERVER)
        self.grpc_server = grpc.aio.server(interceptors=self.grpc_interceptors)
        self.logger.info("gRPC server set")
        self.__apply_opts(opts, AppOptOrder.AFTER_CREATE_GRPC_SERVER)

        # add gRPC service
        self.__apply_opts(opts, AppOptOrder.BEFORE_ADD_GRPC_SERVICES)
        self.logger.info("gRPC services set")
        self.__apply_opts(opts, AppOptOrder.AFTER_ADD_GRPC_SERVICES)

    async def run(self, termination_timeout: Optional[float] = None) -> None:
        self.grpc_server.add_insecure_port(f"[::]:{self.port}")
        self.logger.info("gRPC server starting")
        await self.grpc_server.start()
        self.logger.info("gRPC server started")
        await self.grpc_server.wait_for_termination(termination_timeout)
        self.logger.info("gRPC server terminated")

    def __apply_opts(
        self, opts: List[AppOpt], order: AppOptOrder, *args, **kwargs
    ) -> None:
        for opt in opts:
            if opt.apply_order() == order:
                opt.apply(self, *args, **kwargs)
                self.logger.info(f"{self.__get_opt_name(opt)} option applied")

    # noinspection PyMethodMayBeStatic
    def __get_opt_name(self, opt: AppOpt) -> str:
        if hasattr(opt, "__name__"):
            return opt.__name__
        if hasattr(opt, "__class__"):
            return opt.__class__.__name__
        return str(opt)


class AppOptOrder(Enum):
    DEFAULT = enum_auto()
    BEFORE_SET_OTEL_TRACER_PROVIDER = enum_auto()
    AFTER_SET_OTEL_TRACER_PROVIDER = enum_auto()
    BEFORE_SET_OTEL_METER_PROVIDER = enum_auto()
    AFTER_SET_OTEL_METER_PROVIDER = enum_auto()
    BEFORE_CREATE_GRPC_SERVER = enum_auto()
    AFTER_CREATE_GRPC_SERVER = enum_auto()
    BEFORE_ADD_GRPC_SERVICES = enum_auto()
    AFTER_ADD_GRPC_SERVICES = enum_auto()


class AppOpt(Protocol):
    # noinspection PyMethodMayBeStatic
    def apply_order(self) -> AppOptOrder:
        ...

    def apply(self, app: App, *args, **kwargs) -> None:
        ...


class AppOptABC(ABC):
    # noinspection PyMethodMayBeStatic
    def apply_order(self) -> AppOptOrder:
        return AppOptOrder.DEFAULT

    @abstractmethod
    def apply(self, app: App, *args, **kwargs) -> None:
        pass


class AppGRPCInterceptorOpt(AppOptABC):
    def __init__(self, interceptor: ServerInterceptor) -> None:
        self.interceptor = interceptor
        self.__name__ = f"AppGRPCInterceptorOpt[{interceptor.__class__.__name__}]"

    def apply_order(self) -> AppOptOrder:
        return AppOptOrder.BEFORE_CREATE_GRPC_SERVER

    def apply(self, app: App, *args, **kwargs) -> None:
        app.grpc_interceptors.append(self.interceptor)


class AppGRPCServiceOpt(AppOptABC):
    def __init__(
        self,
        service: Any,
        service_full_name: str,
        add_service_func: Callable[[Any, Server], None],
    ) -> None:
        self.service = service
        self.service_name = service_full_name
        self.add_service_func = add_service_func
        self.__name__ = f"AppGRPCServiceOpt[{self.service_name}]"

    def apply_order(self) -> AppOptOrder:
        return AppOptOrder.BEFORE_ADD_GRPC_SERVICES

    def apply(self, app: App, *args, **kwargs) -> None:
        self.add_service_func(self.service, app.grpc_server)
        app.grpc_service_names.append(self.service_name)


__all__ = [
    "App",
    "AppOpt",
    "AppOptABC",
    "AppOptOrder",
    "AppGRPCInterceptorOpt",
    "AppGRPCServiceOpt",
]
