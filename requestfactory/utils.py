# -*- coding: utf-8 -*-
# Copyright 2008 Google Inc.
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

from paste.httpheaders import \
    ACCEPT_ENCODING, CONTENT_ENCODING, CONTENT_TYPE


class ServletException(Exception):
    pass


def readContent(request, expectedContentType, expectedCharSet=None):
    """Returns the content of an {@link HTTPRequest} by decoding it using
    <code>expectedCharSet</code>, or <code>UTF-8</code> if
    <code>expectedCharSet</code> is <code>null</null>.

    @param request the servlet request whose content we want to read
    @param expectedContentType the expected content (i.e. 'type/subtype' only)
             in the Content-Type request header, or <code>null</code> if no
             validation is to be performed, and you are willing to allow for
             some types of cross type security attacks
    @param expectedCharSet the expected request charset, or <code>null</code>
             if no charset validation is to be performed and <code>UTF-8</code>
             should be assumed
    @return the content of an {@link HTTPRequest} by decoding it using
            <code>expectedCharSet</code>, or <code>UTF-8</code> if
            <code>expectedCharSet</code> is <code>null</code>
    @throws IOException if the request's input stream cannot be accessed, read
            from or closed
    @throws ServletException if the request's content type does not
            equal the supplied <code>expectedContentType</code> or
            <code>expectedCharSet</code>
    """
    if expectedContentType is not None:
        checkContentTypeIgnoreCase(request, expectedContentType)
    if expectedCharSet is not None:
        checkCharacterEncodingIgnoreCase(request, expectedCharSet)
    else:
        expectedCharSet = "UTF-8"

    in_ = request.rawInput(rewind=True)
    return in_.encode(expectedCharSet)


def checkCharacterEncodingIgnoreCase(request, expectedCharSet):
    """Performs validation of the character encoding, ignoring case.

    @param request the incoming request
    @param expectedCharSet the expected charset of the request
    @throws ServletException if requests encoding is not <code>null</code> and
            does not equal, ignoring case, <code>expectedCharSet</code>
    """
    assert expectedCharSet is not None
    encodingOkay = False
    characterEncoding = CONTENT_ENCODING(request.environ())
    if characterEncoding is not None:
        # TODO: It would seem that we should be able to use equalsIgnoreCase here
        # instead of indexOf. Need to be sure that servlet engines return a
        # properly parsed character encoding string if we decide to make this
        # change.
        if characterEncoding.lower().find(expectedCharSet.lower()) != -1:
            encodingOkay = True
    if not encodingOkay:
        raise ServletException('Character Encoding is \''
                + ('(null)' if characterEncoding is None else characterEncoding)
                + '\'. Expected \'' + expectedCharSet + '\'')


def checkContentTypeIgnoreCase(request, expectedContentType):
    """Performs Content-Type validation of the incoming request, ignoring case
    and any <code>charset</code> parameter.

    @see   #checkCharacterEncodingIgnoreCase(HttpServletRequest, String)
    @param request the incoming request
    @param expectedContentType the expected Content-Type for the incoming
           request
    @throws ServletException if the request's content type is not
            <code>null</code> and does not, ignoring case, equal
            <code>expectedContentType</code>,
    """
    assert expectedContentType is not None
    contentType = CONTENT_TYPE(request.environ())
    contentTypeIsOkay = False
    if contentType is not None:
        contentType = contentType.lower()
        # NOTE:We use startsWith because some servlet engines, do
        # not remove the charset component but others do.
        if contentType.startswith(expectedContentType.lower()):
            contentTypeIsOkay = True
    if not contentTypeIsOkay:
        raise ServletException('Content-Type was \''
                + ('(null)' if contentType is None else contentType)
                + '\'. Expected \'' + expectedContentType + '\'.')
