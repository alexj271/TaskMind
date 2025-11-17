from pydantic import BaseModel
import uuid

class UserOut(BaseModel):
    id: uuid.UUID
    telegram_id: int

    class Config:
        from_attributes = True
