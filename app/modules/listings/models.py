import uuid
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel


class PropertyType(str, PyEnum):
    HOTEL = "hotel"
    HOSTEL = "hostel"
    HOMESTAY = "homestay"
    APARTMENT = "apartment"
    VILLA = "villa"
    CAMP = "camp"
    MONASTERY = "monastery"
    ASHRAM = "ashram"
    RESORT = "resort"
    CO_LIVING = "co-living"
    UNIQUE_STAY = "unique-stay"


class ListingStatus(str, PyEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNLISTED = "unlisted"


class VerificationStatus(str, PyEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Amenity(BaseModel):
    __tablename__ = "amenities"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ListingAmenity(BaseModel):
    __tablename__ = "listing_amenities"

    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    amenity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("amenities.id", ondelete="CASCADE"), nullable=False, index=True)
    
    __table_args__ = (
        UniqueConstraint("listing_id", "amenity_id", name="uq_listing_amenity"),
    )


class ListingImage(BaseModel):
    __tablename__ = "listing_images"

    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ListingAvailability(BaseModel):
    __tablename__ = "listing_availabilities"

    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("listing_id", "date", name="uq_listing_date"),
    )


class Listing(BaseModel):
    __tablename__ = "listings"

    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    destination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    property_type: Mapped[PropertyType] = mapped_column(Enum(PropertyType, name="property_type_enum"), nullable=False, index=True)
    
    guest_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bedrooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    beds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bathrooms: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus, name="listing_status_enum"), default=ListingStatus.DRAFT, nullable=False, index=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus, name="verification_status_enum"), default=VerificationStatus.PENDING, nullable=False)

    # Relationships
    images: Mapped[list[ListingImage]] = relationship(
        "ListingImage",
        primaryjoin="Listing.id == ListingImage.listing_id",
        cascade="all, delete-orphan",
        order_by="ListingImage.display_order"
    )
    
    amenities: Mapped[list[Amenity]] = relationship(
        "Amenity",
        secondary="listing_amenities",
        primaryjoin="Listing.id == ListingAmenity.listing_id",
        secondaryjoin="Amenity.id == ListingAmenity.amenity_id",
        viewonly=True
    )
