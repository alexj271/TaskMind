from pydantic import BaseModel
from typing import List, Optional
import uuid

class DialogSessionOut(BaseModel):
    id: uuid.UUID
    summary: Optional[str]
    last_messages: List[str]

    class Config:
        from_attributes = True
