from pydantic import BaseModel, Field, AliasChoices
from typing import Dict, List, Optional
from .common import AnimalType

class FeedData(BaseModel):
    """Individual feed data structure"""
    dm_percent: float = Field(
        ..., ge=0, le=100, description="Dry matter percentage",
        validation_alias=AliasChoices("dm_percent", "dry_matter_percent")
    )
    nutrients: Dict[str, float] = Field(..., description="Nutrient composition")
    cost_per_kg: float = Field(..., ge=0, description="Cost per kilogram")
    display_name: Optional[str] = Field(
        default=None,
        description="Localized feed name resolved for the current user locale",
    )


class FeedbaseData(BaseModel):
    """Complete feedbase structure"""
    animal_type: AnimalType = AnimalType.DAIRY_COW
    feeds: Dict[str, FeedData] = Field(default_factory=dict, description="Collection of feeds")
    feed_labels: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Optional localized feed names keyed by locale code, e.g. {'en': 'Corn', 'zh': '玉米'}",
    )


class FeedbaseListResponse(BaseModel):
    """Response for listing user's feedbases"""
    feedbases: List[str] = Field(default_factory=list, description="List of feedbase names")


class FeedbaseResponse(BaseModel):
    """Response for getting feedbase details"""
    name: str = Field(..., description="Feedbase name")
    data: FeedbaseData = Field(..., description="Feedbase data")


class FeedbaseUpdateRequest(BaseModel):
    """Request for updating/creating a feedbase"""
    data: FeedbaseData = Field(..., description="Feedbase data to store")


class FeedbaseDeleteResponse(BaseModel):
    """Response for feedbase deletion"""
    message: str = Field(..., description="Success/error message")
    feedbase_name: str = Field(..., description="Name of deleted feedbase")
