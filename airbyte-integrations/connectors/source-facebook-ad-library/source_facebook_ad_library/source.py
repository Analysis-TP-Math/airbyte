#
# MIT License
#
# Copyright (c) 2020 Airbyte
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#


from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple, Dict
from math import floor
from copy import deepcopy
import re
import json
from functools import cached_property

import requests
from requests.models import HTTPError
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream

def flatten(iterable: Iterable) -> Iterable:
    it = iter(iterable)
    for e in it:
        if not (isinstance(e, (list, tuple))):
            yield e
        else:
            for f in flatten(e):
                yield f

class AdsArchive(HttpStream):
    url_base = "https://graph.facebook.com/v11.0/"

    # Set this as a noop.
    data_field = "data"
    primary_key = None

    def __init__(self, params: Dict, **kwargs):
        super().__init__()
        self.params = params
        self.params.update({'fields': ",".join(self.fields)})
        self.params.update({'limit': 1000})

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        # TODO: The API does offer pagination, so we should implement this method properly
        try:
            return response.json()["paging"]["cursors"]
        except KeyError:
            return None

    def path(
        self, 
        stream_state: Mapping[str, Any] = None, 
        stream_slice: Mapping[str, Any] = None, 
        next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "ads_archive"  # TODO

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        # The api requires that we include ads_reached_countries and search_page_ids or search_terms in the request
        query_params = deepcopy(self.params)
        query_params.update({'search_page_ids': ",".join(stream_slice)})
        if next_page_token is not None:
            query_params.update(next_page_token)
        return query_params

    def parse_response(
        self,
        response: requests.Response,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping]:
        response_json = response.json().get("data", [])
        for record in response_json:
            record.update({"ad_snapshot_url": "https://www.facebook.com/ads/library/?"+re.search(r"(id=[0-9]*)", record.get("ad_snapshot_url")).group(1)})
        return response_json

    def stream_slices(
        self, 
        stream_state: Mapping[str, Any] = None, **kwargs
    ) -> Iterable[Optional[Mapping[str, any]]]:
        stream_state = stream_state or {}
        return [self.get_page_ids_list[10*i:10*(i+1)] for i in range(floor(1+len(self.get_page_ids_list)/10))]

    @cached_property    
    def fields(self) -> List[str]:
        # get list of fields to query from schema
        return list(self.get_json_schema().get("properties", {}).keys())
    
    @cached_property
    def get_page_ids_list(self) -> List[int]:
        return list(filter(lambda page_id: self.test_valid_page_id(page_id),
                           [i for i in flatten([list(item.values()) for item in json.loads(self.params.get("search_page_ids", [{}]))])]
                          ))
    
    def test_valid_page_id(self, page_id: str) -> bool:
        result=True
        query_params = deepcopy(self.params)
        query_params.update({"search_page_ids": page_id})
        query_params.update({"fields": "id"})
        response = requests.get(self.url_base+self.path(), query_params)
        try:
            result = response.json().get("error").get("error_user_title") != "Invalid Page ID"
        except AttributeError:
            pass
        finally:
            return result


# Source
class SourceFacebookAdLibrary(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        :param config:  the user-input config object conforming to the connector's spec.json
        :param logger:  logger object
        :return Tuple[bool, any]: (True, None) if the input config can be used to connect to the API successfully, (False, error) otherwise.
        """
        try:
            print(config)
            params = deepcopy(config)
            params.update({'fields': 'id'})
            params.update({'limit': 1})
            for id in [i for i in flatten([record.values() for record in json.loads(config.get("search_page_ids", []))])]:
                params.update({"search_page_ids": id})
                test_response = requests.get("https://graph.facebook.com/v11.0/ads_archive", params)
                status = test_response.status_code
                logger.info(f"Ping response code {status}")
                if test_response.status_code == 200:
                    return True, None
                error = test_response.json().get("error")
                message = error.get("message") or error.get("info")
            else:
                return False, message
        except Exception as e:
            return False, e

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        return [AdsArchive(params=config)]
