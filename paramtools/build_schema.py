import json
import os

from marshmallow import fields

from paramtools.schema import EmptySchema, BaseValidatorSchema, get_param_schema
from paramtools import utils


class SchemaBuilder:
    """
    Uses data from:
    - a schema definition file
    - a baseline specification file

    to extend:
    - `schema.BaseParamSchema`
    - `schema.BaseValidatorSchema`

    Once this has been completed, the `load_params` method can be used to
    deserialize and validate parameter data.
    """

    def __init__(self, schema_def_path, base_spec_path, field_map={}):
        schema_def = utils.read_json(schema_def_path)
        (self.BaseParamSchema, self.dim_validators) = get_param_schema(
            schema_def, field_map=field_map
        )
        self.base_spec = utils.read_json(base_spec_path)

    def build_schemas(self):
        """
        For each parameter defined in the baseline specification file:
        - define a parameter schema for that specific parameter
        - define a validation schema for that specific parameter

        Next, create a baseline specification schema class (`ParamSchema`) for
        all parameters listed in the baseline specification file and a
        validator schema class (`ValidatorSchema`) for all parameters in the
        baseline specification file.

        - `ParamSchema` reads and validates the baseline specification file
        - `ValidatorSchema` reads revisions to the baseline parameters and
          validates their type, structure, and whether they are within the
          specified range.

        `param_schema` is defined and used to read and validate the baseline
        specifications file. `validator_schema` is defined to read and validate
        the parameter revisions. The output from the baseline specification
        deserialization is saved in the `context` attribute on
        `validator_schema` and will be utilized when doing range validation.
        """
        param_dict = {}
        validator_dict = {}
        for k, v in self.base_spec.items():
            fieldtype = utils.get_type(v)
            classattrs = {"value": fieldtype, **self.dim_validators}
            validator_dict[k] = type(
                "ValidatorItem", (EmptySchema,), classattrs
            )

            classattrs = {"value": fields.Nested(validator_dict[k], many=True)}
            param_dict[k] = type(
                "IndividualParamSchema", (self.BaseParamSchema,), classattrs
            )

        classattrs = {k: fields.Nested(v) for k, v in param_dict.items()}
        ParamSchema = type("ParamSchema", (EmptySchema,), classattrs)
        self.param_schema = ParamSchema()
        cleaned_base_spec = self.param_schema.load(self.base_spec)

        classattrs = {
            k: fields.Nested(v(many=True)) for k, v in validator_dict.items()
        }
        ValidatorSchema = type(
            "ValidatorSchema", (BaseValidatorSchema,), classattrs
        )
        self.validator_schema = ValidatorSchema()
        self.validator_schema.context["base_spec"] = cleaned_base_spec

    def load_params(self, params_or_path):
        """
        Method to deserialize and validate parameter revision.
        `params_or_path` can be a file path or a `dict` that has not been
        fully deserialized.

        Returns: serialized data.

        Throws: `marshmallow.exceptions.ValidationError` if data is not valid.
        """
        if isinstance(params_or_path, str) and os.path.exists(params_or_path):
            params = utils.read_json(params_or_path)
        elif isinstance(params_or_path, str):
            params = json.loads(params_or_path)
        elif isinstance(params_or_path, dict):
            params = params_or_path
        else:
            raise ValueError("params_or_path is not dict or file path")
        return self.validator_schema.load(params)