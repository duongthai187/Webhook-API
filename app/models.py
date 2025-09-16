from typing import Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class WebhookRequest(BaseModel):
    """Model for incoming webhook data from bank"""
    timestamp: datetime = Field(..., description="Request timestamp")
    transaction_id: str = Field(..., description="Unique transaction ID")
    account_number: str = Field(..., description="Account number")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(default="VND", description="Currency code")
    transaction_type: str = Field(..., description="Type of transaction (debit/credit)")
    reference: str = Field(None, description="Transaction reference")
    description: str = Field(None, description="Transaction description")
    signature: str = Field(..., description="SHA512withRSA signature")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookResponse(BaseModel):
    """Response model for webhook endpoint"""
    success: bool = Field(..., description="Request processing status")
    message: str = Field(..., description="Response message")
    transaction_id: str = Field(None, description="Transaction ID for reference")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }