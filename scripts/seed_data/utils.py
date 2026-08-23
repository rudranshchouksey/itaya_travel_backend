import hashlib
import uuid
import random

def generate_deterministic_uuid(namespace: str, unique_id: str) -> uuid.UUID:
    """Generate a deterministic UUID based on a namespace and unique ID."""
    hash_object = hashlib.md5(f"{namespace}:{unique_id}".encode())
    return uuid.UUID(hash_object.hexdigest())

def get_demo_image_url(seed: str, width: int = 800, height: int = 600, category: str = "travel") -> str:
    """Generate a stable placeholder image URL from Unsplash Source or Picsum."""
    # Using picsum with seed for deterministic stable images
    # Example: https://picsum.photos/seed/demo-goa-hero/800/600
    return f"https://picsum.photos/seed/{seed}/{width}/{height}"

def get_demo_avatar_url(seed: str) -> str:
    """Generate a stable avatar image."""
    return f"https://api.dicebear.com/7.x/avataaars/png?seed={seed}"
