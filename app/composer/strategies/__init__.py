from app.composer.strategies.dentists import DentistsStrategy
from app.composer.strategies.salons import SalonsStrategy
from app.composer.strategies.restaurants import RestaurantsStrategy
from app.composer.strategies.gyms import GymsStrategy
from app.composer.strategies.pharmacies import PharmaciesStrategy

STRATEGY_MAP = {
    "dentists": DentistsStrategy,
    "salons": SalonsStrategy,
    "restaurants": RestaurantsStrategy,
    "gyms": GymsStrategy,
    "pharmacies": PharmaciesStrategy,
}
