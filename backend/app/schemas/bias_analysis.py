from typing import List, Dict, Any, Optional
from pydantic import BaseModel, validator, root_validator

class DatasetSchema(BaseModel):
    """
    Schema for defining the structure of a dataset for bias analysis.
    This schema is extensible for future fields (e.g., privileged_groups, instance_weights).
    """
    data: List[Dict[str, Any]]
    feature_names: List[str]
    label_name: str
    protected_attributes: List[str]
    favorable_label: Any
    unfavorable_label: Any
    metadata: Optional[Dict[str, Any]] = None

    @validator('protected_attributes')
    def validate_protected_attributes_not_empty(cls, value):
        if not value:
            raise ValueError("protected_attributes list cannot be empty.")
        return value

    @root_validator
    def validate_labels_distinct_and_defined(cls, values):
        favorable_label = values.get('favorable_label')
        unfavorable_label = values.get('unfavorable_label')

        # Pydantic already ensures they are defined if not Optional
        # This check is more for explicit clarity if they could be None,
        # but given the schema, they cannot be None unless type is changed to Optional[Any]
        if favorable_label is None or unfavorable_label is None:
            # This case should ideally not be hit if fields are not Optional
            raise ValueError("Both favorable_label and unfavorable_label must be defined.")

        if favorable_label == unfavorable_label:
            raise ValueError("favorable_label and unfavorable_label must be distinct.")

        return values

    # Future fields like privileged_groups, instance_weights can be added here.
    # privileged_groups: Optional[List[Dict[str, Any]]] = None
    # instance_weights: Optional[List[float]] = None
