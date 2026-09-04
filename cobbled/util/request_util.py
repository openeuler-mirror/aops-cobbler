"""Request validation helpers for REST resources."""

from flask import request
from flask_restful import Resource

from cobbled.util.response_util import ResUtil


class JsonObjectResource(Resource):
    """Require the request body to contain a JSON object."""

    def dispatch_request(self, *args, **kwargs):
        json_data = request.get_json()
        if not isinstance(json_data, dict):
            response = ResUtil.failed("Request body must be a JSON object.")
            response.status_code = 400
            return response
        return super().dispatch_request(*args, **kwargs)
