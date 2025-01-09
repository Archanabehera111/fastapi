from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union

# Pydantic model for the input
class SaveFields(BaseModel):
    user_id: str = Field(..., example="user123", alias="userId")
    fields: List[str] = Field(..., example=["column1", "column2", "column3", "column4"])
    table_name: str = Field(..., example="example_table", alias="tableName")

    @field_validator('user_id', 'table_name')
    def fields_not_empty(cls, v, field):
        if not v.strip():
            raise ValueError(f'{field.field_name} must not be empty')
        return v

# Pydantic models for the output
class SaveFieldsOutputData(BaseModel):
    id: str = Field(..., example="bdf54457-eedc-465c-83ed-ab5f0df1ff80")
    userId: str = Field(..., example="user123")
    fields: List[str] = Field(..., example=["column1", "column2", "column3", "column4"])
    tableName: str = Field(..., example="example_table")

class SaveFieldsOutput(BaseModel):
    message: str = Field(..., example="Fields saved successfully")
    data: SaveFieldsOutputData


# Pydantic model for the input
class GetFields(BaseModel):
    user_id: str = Field(..., example="user123", alias="userId")
    table_name: str = Field(..., example="example_table", alias="tableName")

    @field_validator('user_id', 'table_name')
    def fields_not_empty(cls, v, field):
        if not v.strip():
            raise ValueError(f'{field.field_name} must not be empty')
        return v

# Pydantic models for the output
class GetFieldsOutputData(BaseModel):
    id: str = Field(..., example="bdf54457-eedc-465c-83ed-ab5f0df1ff80")
    userId: str = Field(..., example="user123")
    fields: List[str] = Field(..., example=["column1", "column2", "column3", "column4"])
    tableName: str = Field(..., example="example_table")

class GetFieldsOutput(BaseModel):
    message: str = Field(..., example="Fields retrieved successfully")
    data: Union[GetFieldsOutputData, None]

class SaveFiltersInputSchema(BaseModel):
    user_id: str = Field(..., example="user123", alias="userId")
    name: str = Field(..., example="filter1")
    filters: dict = Field(..., example={"from": "2024-03-04T00:00:00Z", "to": "2024-03-04T23:59:59Z"})
    table_name: str = Field(..., example="example_table", alias="tableName")
    fields: List[str] = Field(default_factory=list, example=["column1", "column2", "column3", "column4"])

    @field_validator('user_id', 'name', 'table_name')
    def fields_not_empty(cls, v, field):
        if not v.strip():
            raise ValueError(f'{field.field_name} must not be empty')
        return v

    @field_validator('filters')
    def filters_not_empty(cls, v, field):
        if not v:
            raise ValueError(f'{field.field_name} must not be empty')
        return v

class SavedFiltersSchema(BaseModel):
    id: str = Field(..., example="bdf54457-eedc-465c-83ed-ab5f0df1ff80")
    user_id: str = Field(..., example="user123")
    name: str = Field(..., example="filter1")
    filters: dict = Field(..., example={"from": "2024-03-04T00:00:00Z", "to": "2024-03-04T23:59:59Z"})
    table_name: str = Field(..., example="example_table")
    fields: Union[List[str], None]= Field(default_factory=list, example=["column1", "column2", "column3", "column4"])
    
class SaveFiltersOutputSchema(BaseModel):
    message: str = Field(..., example="Filters saved successfully")
    data: Union[SavedFiltersSchema, None]

class GetFiltersInputSchema(BaseModel):
    user_id: str = Field(..., example="user123", alias="userId")
    table_name: str = Field(..., example="example_table", alias="tableName")

    @field_validator('user_id', 'table_name')
    def fields_not_empty(cls, v, field):
        if not v.strip():
            raise ValueError(f'{field.field_name} must not be empty')
        return v

class GetFiltersOutputSchema(BaseModel):
    message: str = Field(..., example="Filters retrieved successfully")
    data: List[SavedFiltersSchema]

class UpdateFiltersInputSchema(BaseModel):
    id: str = Field(..., example="bdf54457-eedc-465c-83ed-ab5f0df1ff80")
    user_id: str = Field(..., example="user123", alias="userId")
    name: str = Field(..., example="filter1")
    filters: dict = Field(..., example={"from": "2024-03-04T00:00:00Z", "to": "2024-03-04T23:59:59Z"})
    fields: List[str] = Field(default_factory=list, example=["column1", "column2", "column3", "column4"])

    @field_validator('id', 'user_id', 'name')
    def fields_not_empty(cls, v, field):
        if not v.strip():
            raise ValueError(f'{field.field_name} must not be empty')
        return v
    
    @field_validator('filters')
    def filters_not_empty(cls, v, field):
        if not v:
            raise ValueError(f'{field.field_name} must not be empty')
        return v
# Pydantic model for the input schema to delete a filter
class DeleteFilterInputSchema(BaseModel):
    id: str = Field(..., example="bdf54457-eedc-465c-83ed-ab5f0df1ff80")
    # user_id: str = Field(..., example="user123", alias="userId")

    @field_validator('id')
    def fields_not_empty(cls, v, field):
        if not v.strip():
            raise ValueError(f'{field.field_name} must not be empty')
        return v

# Pydantic model for the output schema after deleting a filter
class DeleteFilterOutputSchema(BaseModel):
    message: str = Field(..., example="Filter deleted successfully")
    data: Optional[dict] = None  # Optional data, will contain the deleted filter's info if needed

