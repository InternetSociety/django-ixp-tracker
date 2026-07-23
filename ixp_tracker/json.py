from json import JSONEncoder, JSONDecoder

import orjson


class OrJSONSerializer(JSONEncoder, JSONDecoder):
    def encode(self, o):
        return orjson.dumps(
            o, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_OMIT_MICROSECONDS
        )

    def decode(self, s, _w=...):
        return orjson.loads(s)
