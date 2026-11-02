"""Read-only shapes from the supplied Party handbook; extras are never copied."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Party(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    account_id: int = Field(gt=0)
    account_name: str = Field(min_length=1)
    party_type: Literal["CUSTOMER", "SUPPLIER"]
    is_active: bool
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
    state: str | None = None
    pincode: str | None = None
    updated_dtm: str | None = None


class Pagination(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
