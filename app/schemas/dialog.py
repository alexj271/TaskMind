from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import uuid

class DialogSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    summary: Optional[str]
    last_messages: List[str]
