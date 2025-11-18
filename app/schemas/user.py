from pydantic import BaseModel, ConfigDict
import uuid

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    telegram_id: int
