from pydantic import BaseModel

class CarData(BaseModel):
    make: str
    model: str
    year: int
    mileage: int
    features: list[str]
    condition: str
