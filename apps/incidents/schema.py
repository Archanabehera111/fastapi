from pydantic import BaseModel, Field,  FieldValidationInfo, field_validator, ValidationError
from typing import List


# Pydantic model for the input
class GetIncidentId(BaseModel):
    user_id: str = Field(..., example="user123", alias="userId")


class TimelineInputSchema(BaseModel):
    filters: dict = Field({}, example={"from": "2024-03-04T00:00:00Z", "to": "2024-03-04T23:59:59Z"})
    key: str = Field(..., example="country")

class GetEventsSchema(BaseModel):
    sort: str = Field("desc", example="asc")
    incident_id: str = Field(..., example="44505bb8-18b5-46fa-adf4-6a87e380516b", alias="incidentId")

    @field_validator('incident_id')
    def incident_id_must_not_be_empty(cls, v: str, info: FieldValidationInfo):
        if not v.strip():
            raise ValueError('incidentId cannot be empty or just whitespace')
        return v

class IncidentRequest(BaseModel):
    incident_id: str = Field(..., example="21c02f9d-10be-48a0-a96e-710e9dc9f0f6", alias="incidentId")

    @field_validator('incident_id')
    def incident_id_must_not_be_empty(cls, v: str, info: FieldValidationInfo):
        if not v.strip():
            raise ValueError('incidentId cannot be empty or just whitespace')
        return v

class IncidentResponse(BaseModel):
    id: str = Field(..., example="6271be2d-0922-4603-84c9-f39afe58a80e")
    title: str = Field(..., example="Attack from 205.210.31.69 on 2024-03-01 09:07:34 +0000 UTC")
    created_at: str = Field(..., example="2024-03-01T09:07:34Z")

class IncidentResponseSchema(BaseModel):
    message: str = Field(..., example="Success")
    data: List[IncidentResponse] = Field(..., )

class IncidentMitigationRequestSchema(BaseModel):
    incident_id: str = Field(..., example="d7e716ec-5ba2-4363-80c4-9ff6b8e5e8c7", alias="incidentId")

    # Validator to ensure that incidentId is not empty or just whitespace
    @field_validator('incident_id')
    def incident_id_must_not_be_empty(cls, v: str, info: FieldValidationInfo):
        if not v.strip():
            raise ValueError('incidentId cannot be empty or just whitespace')
        return v

class IncidentMitigationResponseSchema(BaseModel):
    message: str = Field(..., example="Data fetched sucessfully")
    data: List[str]
