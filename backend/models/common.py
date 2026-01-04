from enum import Enum

class AnimalType(str, Enum):
    """Pre-defined animal types - users can only choose from these"""
    DAIRY_COW = "dairy_cow"
    BEEF_COW = "beef_cow"
    CAT = "cat"
    DOG = "dog"

    @classmethod
    def get_display_name(cls, value: str) -> str:
        """Get display name for animal type"""
        names = {
            cls.DAIRY_COW: "奶牛 Dairy Cow",
            cls.BEEF_COW: "肉牛 Beef Cow",
            cls.CAT: "猫 Cat",
            cls.DOG: "狗 Dog",
        }
        return names.get(value, value)
