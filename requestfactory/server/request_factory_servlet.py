# -*- coding: utf-8 -*-
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import logging

from requestfactory.server.default_exception_handler import DefaultExceptionHandler
from requestfactory.shared.RequestFactory import RequestFactory
from requestfactory.server.service_layer import ServiceLayer
from requestfactory.server.simple_request_processor import SimpleRequestProcessor

from requestfactory.utils import readContent

from paste.webkit.wkservlet import HTTPServlet


SC_OK = 200
SC_INTERNAL_SERVER_ERROR = 500

DUMP_PAYLOAD = False
JSON_CHARSET = 'UTF-8'
JSON_CONTENT_TYPE = 'application/json'

LOGGER = logging.getLogger(__name__)


class RequestFactoryServlet(HttpServlet):
    """Handles GWT RequestFactory JSON requests."""


    def __init__(self, exceptionHandler=None, *serviceDecorators):
        """Constructs a new {@link RequestFactoryServlet} with a
        {@code DefaultExceptionHandler} unless provided.

        @param exceptionHandler an {@link ExceptionHandler} instance
        @param serviceDecorators an array of ServiceLayerDecorators that change how
                 the RequestFactory request processor interact with the domain
                 objects
        """
        if exceptionHandler is None:
            exceptionHandler = DefaultExceptionHandler()

        self._processor = SimpleRequestProcessor(ServiceLayer.create(
                serviceDecorators))
        self._processor.setExceptionHandler(exceptionHandler)


    def respondToPost(self, transaction):
        """Processes a POST to the server.

        @param transaction an {@link Transaction} instance
        @throws IOException if an internal I/O error occurs
        @throws ServletException if an error occurs in the servlet
        """
        request, response = transaction.request(), transaction.response()

        jsonRequestString = readContent(request, JSON_CONTENT_TYPE, JSON_CHARSET)
        if DUMP_PAYLOAD:
            print '>>> ' + jsonRequestString
        try:
            payload = self._processor.process(jsonRequestString)
            if DUMP_PAYLOAD:
                print '<<< ' + payload
            response.setStatus(SC_OK)
            response.setContentType(RequestFactory.JSON_CONTENT_TYPE_UTF8)
            # Write after setting the content type
            response.write(payload)
            response.flush()
        except RuntimeError, e:
            response.sendError(SC_INTERNAL_SERVER_ERROR)
            LOGGER.log(logging.CRITICAL, 'Unexpected error', e)
