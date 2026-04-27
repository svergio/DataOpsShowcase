import random
from dataclasses import dataclass, field
from typing import List

from faker import Faker


COUNTRY_CURRENCY = {
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "JP": "JPY",
    "CN": "CNY",
    "AU": "AUD",
    "CA": "CAD",
    "CH": "CHF",
}

COUNTRY_WEIGHTS = [
    ("US", 40),
    ("GB", 15),
    ("DE", 10),
    ("FR", 8),
    ("JP", 12),
    ("CN", 10),
    ("AU", 2),
    ("CA", 2),
    ("CH", 1),
]

CATEGORIES = [
    "Smartphones",
    "Laptops",
    "Tablets",
    "Headphones",
    "Smartwatches",
    "Cameras",
    "Monitors",
    "Keyboards",
    "Speakers",
    "Gaming",
]

BRANDS = [
    "Apple",
    "Samsung",
    "Sony",
    "Lenovo",
    "Dell",
    "HP",
    "Asus",
    "Logitech",
    "Bose",
    "Xiaomi",
]


def weighted_country(rng: random.Random) -> str:
    countries, weights = zip(*COUNTRY_WEIGHTS)
    return rng.choices(countries, weights=weights, k=1)[0]


@dataclass
class UserRef:
    user_id: int
    email: str
    full_name: str
    country: str
    currency: str


@dataclass
class SellerRef:
    seller_id: int
    seller_name: str
    rating: float
    country: str


@dataclass
class ProductRef:
    product_id: int
    seller_id: int
    sku: str
    product_name: str
    category: str
    brand: str
    price: float
    is_active: bool


@dataclass
class ReferenceState:
    users: List[UserRef] = field(default_factory=list)
    sellers: List[SellerRef] = field(default_factory=list)
    products: List[ProductRef] = field(default_factory=list)


class ReferenceFactory:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.faker = Faker()
        Faker.seed(seed)

    def make_user(self, user_id: int) -> UserRef:
        country = weighted_country(self.rng)
        currency = COUNTRY_CURRENCY[country]
        first = self.faker.first_name()
        last = self.faker.last_name()
        email_seed = self.rng.randint(100, 9999)
        email = f"{first.lower()}.{last.lower()}{email_seed}@example.com"
        return UserRef(
            user_id=user_id,
            email=email,
            full_name=f"{first} {last}",
            country=country,
            currency=currency,
        )

    def make_seller(self, seller_id: int) -> SellerRef:
        country = weighted_country(self.rng)
        rating = round(self.rng.betavariate(20, 4) * 5, 2)
        return SellerRef(
            seller_id=seller_id,
            seller_name=self.faker.company(),
            rating=rating,
            country=country,
        )

    def make_product(self, product_id: int, seller: SellerRef) -> ProductRef:
        category = self.rng.choice(CATEGORIES)
        brand = self.rng.choice(BRANDS)
        price_low, price_high = {
            "Smartphones": (200, 1500),
            "Laptops": (400, 3500),
            "Tablets": (150, 1200),
            "Headphones": (20, 600),
            "Smartwatches": (100, 800),
            "Cameras": (250, 2500),
            "Monitors": (120, 1800),
            "Keyboards": (20, 300),
            "Speakers": (50, 1500),
            "Gaming": (100, 2000),
        }.get(category, (50, 1000))
        price = round(self.rng.uniform(price_low, price_high), 2)
        sku = f"SKU-{seller.seller_id:04d}-{product_id:06d}"
        return ProductRef(
            product_id=product_id,
            seller_id=seller.seller_id,
            sku=sku,
            product_name=f"{brand} {category} {self.faker.word().capitalize()}",
            category=category,
            brand=brand,
            price=price,
            is_active=self.rng.random() > 0.05,
        )
