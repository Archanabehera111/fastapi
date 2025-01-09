from pydantic import BaseModel, field_validator, Field
from datetime import datetime
from typing import List, Union


class NoteInputSchema(BaseModel):
    incident_id: str = Field(..., example="bdf54457-eedc-465c-83ed-ab5f0df1ff80", alias="incidentId")
    user_id: str = Field(..., example="user123", alias="userId")
    note: str


class HistorySchema(BaseModel):
    updated_at: datetime
    value: str


class NoteResponseObjectSchema(BaseModel):
    id: str
    incident_id: str
    user_id: str
    note: str
    created_at: datetime
    updated_at: datetime
    history: List[HistorySchema]


class NoteResponseSchema(BaseModel):
    message: str
    data: Union[NoteResponseObjectSchema, List[NoteResponseObjectSchema], None]


class NoteUpdateInputSchema(BaseModel):
    id: str
    note: str
    user_id: str = Field(..., example="user123", alias="userId")


class GetNotesInputSchema(BaseModel):
    incident_id: str = Field(..., example="bdf54457-eedc-465c-83ed-ab5f0df1ff80", alias="incidentId")


class NoteDeleteInputSchema(BaseModel):
    id: str
    user_id: str = Field(..., example="user123", alias="userId")

    @field_validator('id', 'user_id')
    def fields_not_empty(cls, v, field):
        if not v.strip():
            raise ValueError(f'{field.field_name} must not be empty')
        return v

class NoteDeleteResponseSchema(BaseModel):
    message: str
    data: None
