with open('tests/test_bookings.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"listing_id": listing_id,', '"listing_id": str(listing_id),')

with open('tests/test_bookings.py', 'w', encoding='utf-8') as f:
    f.write(content)
